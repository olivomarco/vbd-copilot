import { useEffect, useRef, useCallback } from "react";
import { useJobStore } from "@/stores/jobStore";
import type { AgentPhase } from "@/stores/jobStore";
import { getSessionStatus, getSessionEvents } from "@/api/client";
import { notifyInputRequired, clearInputNotification, notifyJobCompleted } from "@/utils/notifications";

const WS_PROTOCOL = window.location.protocol === "https:" ? "wss:" : "ws:";
const BASE_WS = import.meta.env.VITE_WS_URL ?? `${WS_PROTOCOL}//${window.location.hostname}:${window.location.port}`;

const MAX_RECONNECT_ATTEMPTS = 12;
const RECONNECT_DELAY_MS = 2000;
const HEARTBEAT_INTERVAL_MS = 25000;
const MAX_SERVER_CHECK_ATTEMPTS = 3;

/**
 * Opens a WebSocket to /ws/{sessionId}, parses events, and updates
 * the job store. Handles reconnection and React StrictMode gracefully.
 */
export function useWebSocket(sessionId: string | null) {
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectAttempts = useRef(0);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const intentionalClose = useRef(false);
  const jobDone = useRef(false); // tracks if we received a "done"/"cancelled" event
  const serverCheckAttempts = useRef(0);
  const updateJob = useJobStore((s) => s.updateJob);
  const pushEvent = useJobStore((s) => s.pushEvent);
  const setWs = useJobStore((s) => s.setWs);

  /** Stack of active subagent names — supports nested subagents. */
  const activeSubagentStack = useRef<string[]>([]);

  /** Seen envelope IDs for deduplication. */
  const seenIds = useRef<Set<string>>(new Set());

  /** Apply a session_snapshot from the server to restore state. */
  function handleSnapshot(sid: string, snap: any) {
    const currentJob = useJobStore.getState().getJob(sid);
    if (!currentJob) return;

    // Restore active subagent stack from server
    activeSubagentStack.current = [...(snap.active_subagents || [])];

    // Restore pending input if server has one
    if (snap.pending_input) {
      const q = snap.pending_input.question || "The agent has a question";
      const alreadyQueued = (currentJob.pendingInput || []).some((p: any) => p.question === q);
      if (!alreadyQueued) {
        updateJob(sid, {
          status: "waiting",
          pendingInput: [...(currentJob.pendingInput || []), { question: q, choices: snap.pending_input.choices }],
        });
      }
    }

    // Restore done state if server says so
    if (snap.last_done) {
      if (currentJob.status !== "completed" && currentJob.status !== "failed" && currentJob.status !== "cancelled") {
        pushEvent(sid, { type: "done", data: snap.last_done });
      }
    }
  }

  const connect = useCallback((sid: string) => {
    // Close any existing connection first
    if (wsRef.current && wsRef.current.readyState < WebSocket.CLOSING) {
      intentionalClose.current = true;
      wsRef.current.close();
      intentionalClose.current = false;
    }

    jobDone.current = false;
    activeSubagentStack.current = [];
    const url = `${BASE_WS}/ws/${sid}`;
    const ws = new WebSocket(url);
    wsRef.current = ws;
    setWs(sid, ws);

    ws.onopen = () => {
      reconnectAttempts.current = 0;
      seenIds.current.clear();

      const job = useJobStore.getState().getJob(sid);

      // Hydrate: fetch history for active jobs with few events (cold start / reconnect)
      if (job && job.events.length < 5 && job.status !== "completed" && job.status !== "failed" && job.status !== "cancelled") {
        getSessionEvents(sid)
          .then((serverEvents) => {
            const currentJob = useJobStore.getState().getJob(sid);
            if (!currentJob) return;
            const existingKeys = new Set(currentJob.events.map(e => `${e.type}:${JSON.stringify(e.data)}`));
            for (const se of serverEvents) {
              const key = `${se.type}:${JSON.stringify(se.data)}`;
              if (!existingKeys.has(key)) {
                pushEvent(sid, { type: se.type, data: se.data });
              }
            }
          })
          .catch(() => {});
      }

      // Preserve a waiting review gate if the socket reconnects mid-approval.
      if (job && job.status !== "completed" && job.status !== "failed" && job.status !== "cancelled") {
        updateJob(sid, { status: job.pendingInput?.length ? "waiting" : "running" });
      }

      // Safety net: poll the server status endpoint shortly after reconnect.
      // If the turn already completed while we were disconnected and the server
      // cleaned up before we reconnected, the WS will never receive a "done"
      // event. The status API tells us the session ended and we can finalize.
      setTimeout(() => {
        const currentJob = useJobStore.getState().getJob(sid);
        if (!currentJob || currentJob.status === "completed" || currentJob.status === "failed" || currentJob.status === "cancelled") return;
        getSessionStatus(sid)
          .then((srv) => {
            // Re-check — a "done" WS event may have arrived in the meantime
            const freshJob = useJobStore.getState().getJob(sid);
            if (!freshJob || freshJob.status === "completed" || freshJob.status === "failed" || freshJob.status === "cancelled") return;

            if (srv.status === "ended" || (!srv.in_memory && !srv.has_running_turn)) {
              jobDone.current = true;
              clearInputNotification();
              notifyJobCompleted(freshJob.title || "Your content is ready");
              updateJob(sid, {
                status: "completed",
                phase: "done",
                completedAt: Date.now(),
                pendingInput: [],
              });
            }
          })
          .catch(() => { /* server unreachable — WS will handle it */ });
      }, 3000);
    };

    ws.onmessage = (ev) => {
      let raw: any;
      try {
        raw = JSON.parse(ev.data);
      } catch {
        return;
      }

      // Unwrap v1 envelope — backward compat: raw messages still work
      const isEnvelope = raw.v === 1 && raw.id && raw.data;
      const t: string = raw.type;
      const msg = isEnvelope ? raw.data : raw;
      const msgId: string | null = isEnvelope ? raw.id : null;

      // Dedup by envelope ID
      if (msgId && seenIds.current.has(msgId)) return;
      if (msgId) seenIds.current.add(msgId);

      // Handle session_snapshot — initialize state from server
      if (t === "session_snapshot") {
        handleSnapshot(sid, msg);
        return;
      }

      if (t !== "pong" && t !== "heartbeat") {
        // Deduplicate waiting_for_input events BEFORE pushing to the feed.
        // Handles two cases:
        //   A) WS reconnect replays a pending ask_user the user hasn't answered yet
        //   B) Server re-asks a question the user already answered (stale replay)
        if (t === "waiting_for_input") {
          const q = msg.question || "The agent has a question";
          const currentJob = useJobStore.getState().getJob(sid);
          if (currentJob) {
            // Find the last waiting_for_input with the same question text
            const lastWaiting = [...currentJob.events].reverse().find(
              (e) => e.type === "waiting_for_input" && (e.data as any).question === q,
            );

            if (lastWaiting) {
              const hasAnswerAfter = currentJob.events.some(
                (e) => e.type === "user_response" && e.id > lastWaiting.id,
              );

              if (!hasAnswerAfter) {
                // Case A: unanswered duplicate — restore pendingInput, skip feed event
                const alreadyQueued = (currentJob.pendingInput || []).some(
                  (p) => p.question === q,
                );
                updateJob(sid, {
                  status: "waiting",
                  ...(!alreadyQueued && {
                    pendingInput: [
                      ...(currentJob.pendingInput || []),
                      { question: q, choices: msg.choices || undefined },
                    ],
                  }),
                });
                return;
              }

              // Case B: already answered — ignore stale replay.
              // Never auto-send answers from the client; responses must be explicit user action.
              return;
            }
          }
        }

        // Skip duplicate terminal events for jobs that already finished.
        // The server replays the last "done" payload on WS reconnect, which
        // would otherwise add a second "Job completed!" card to the feed.
        if (t === "done" || t === "cancelled") {
          const existingJob = useJobStore.getState().getJob(sid);
          if (existingJob && (existingJob.status === "completed" || existingJob.status === "failed" || existingJob.status === "cancelled")) {
            // Job is already terminal — skip the duplicate event entirely
            return;
          }
        }

        // Push raw event to the activity feed.
        // Tag tool events with the active subagent so the UI can group them.
        // Prefer the server-provided _subagent tag (more reliable); fall back to client stack.
        const isToolEvent = t === "tool_started" || t === "tool_completed";
        const serverTag = isToolEvent ? msg._subagent : undefined;
        const clientTag = activeSubagentStack.current.length > 0 ? activeSubagentStack.current[activeSubagentStack.current.length - 1] : undefined;
        const subagentTag = serverTag || clientTag;
        const eventData = isToolEvent && subagentTag
          ? { ...msg, _subagent: subagentTag }
          : msg;
        pushEvent(sid, { type: t, data: eventData });
      }

      switch (t) {
        case "turn_started": {
          const currentJob = useJobStore.getState().getJob(sid);
          const hasPendingQuestions = !!(currentJob?.pendingInput?.length);
          updateJob(sid, {
            status: hasPendingQuestions ? "waiting" : "running",
            phase: "researching",
            // Only clear pendingInput if there are no unanswered questions
            ...(hasPendingQuestions ? {} : { pendingInput: [] }),
            progress: {
              toolCalls: 0,
              subagentRuns: 0,
              currentStep: "Starting...",
            },
          });
          break;
        }

        case "phase_changed":
          updateJob(sid, { phase: msg.phase as AgentPhase });
          break;

        case "tool_started": {
          const job = useJobStore.getState().getJob(sid);
          if (job) {
            updateJob(sid, {
              progress: {
                ...job.progress,
                toolCalls: job.progress.toolCalls + 1,
                currentStep: `Running ${msg.tool || "tool"}`,
              },
            });
          }
          break;
        }

        case "subagent_started": {
          const agentName = msg.agent || "agent";
          activeSubagentStack.current.push(agentName);
          const job = useJobStore.getState().getJob(sid);
          if (job) {
            updateJob(sid, {
              progress: {
                ...job.progress,
                subagentRuns: job.progress.subagentRuns + 1,
                currentStep: `Subagent: ${agentName}`,
              },
            });
          }
          break;
        }

        case "subagent_completed": {
          const completedName = msg.agent || "agent";
          const idx = activeSubagentStack.current.lastIndexOf(completedName);
          if (idx >= 0) {
            activeSubagentStack.current.splice(idx, 1);
          } else if (activeSubagentStack.current.length > 0) {
            activeSubagentStack.current.pop();
          }
          break;
        }

        case "subagent_failed": {
          const failedName = msg.agent || "agent";
          const failIdx = activeSubagentStack.current.lastIndexOf(failedName);
          if (failIdx >= 0) {
            activeSubagentStack.current.splice(failIdx, 1);
          } else if (activeSubagentStack.current.length > 0) {
            activeSubagentStack.current.pop();
          }
          const failJob = useJobStore.getState().getJob(sid);
          if (failJob) {
            updateJob(sid, {
              progress: {
                ...failJob.progress,
                currentStep: `Subagent failed: ${failedName}`,
              },
            });
          }
          break;
        }

        case "subagent_selected":
          // Informational — agent was selected but not yet started
          break;

        case "waiting_for_input": {
          // Dedup is handled above (before pushEvent). If we reach here,
          // this is a genuinely new question — add to pendingInput queue.
          const question = msg.question || "The agent has a question";
          const choices = msg.choices || undefined;
          const currentJob = useJobStore.getState().getJob(sid);
          const prevQueue = currentJob?.pendingInput || [];
          updateJob(sid, {
            status: "waiting",
            pendingInput: [...prevQueue, { question, choices }],
          });
          void notifyInputRequired();
          break;
        }

        case "input_resolved": {
          // Backend signals that the waiting_for_input prompt was resolved
          // (user responded via another client, or backend timed out)
          const curJob = useJobStore.getState().getJob(sid);
          const remaining = (curJob?.pendingInput || []).slice(1);
          updateJob(sid, {
            status: remaining.length > 0 ? "waiting" : "running",
            pendingInput: remaining.length > 0 ? remaining : undefined,
          });
          if (remaining.length === 0) clearInputNotification();
          break;
        }

        case "usage": {
          const job = useJobStore.getState().getJob(sid);
          if (job) {
            updateJob(sid, {
              usage: {
                inputTokens: job.usage.inputTokens + (msg.input_tokens || 0),
                outputTokens: job.usage.outputTokens + (msg.output_tokens || 0),
                estimatedCostUsd: job.usage.estimatedCostUsd,
              },
            });
          }
          break;
        }

        case "pong":
        case "heartbeat":
          break;

        case "new_files": {
          const job = useJobStore.getState().getJob(sid);
          if (job) {
            const files = msg.files as string[];
            updateJob(sid, {
              outputFiles: [...job.outputFiles, ...files],
              phase: "delivering",
            });
          }
          break;
        }

        case "done": {
          jobDone.current = true;
          clearInputNotification();
          // Notify user if they're in a different window/tab
          const doneJob = useJobStore.getState().getJob(sid);
          if (msg.status === "success" && doneJob) {
            notifyJobCompleted(doneJob.title || "Your content is ready");
          }
          let jobStatus: "completed" | "failed" | "cancelled";
          if (msg.status === "success") {
            jobStatus = "completed";
          } else if (msg.status === "cancelled") {
            jobStatus = "cancelled";
          } else if (msg.status === "timeout") {
            // Match CLI behavior: timeout is non-fatal. The session is still
            // alive on the server. Let the user keep chatting.
            jobDone.current = false; // don't prevent reconnect
            updateJob(sid, {
              status: "running",
              phase: "building",
              pendingInput: [],
              progress: {
                ...(useJobStore.getState().getJob(sid)?.progress || { toolCalls: 0, subagentRuns: 0, currentStep: "" }),
                currentStep: "Turn timed out — you can send a follow-up message",
              },
            });
            break;
          } else {
            jobStatus = "failed";
          }
          updateJob(sid, {
            status: jobStatus,
            phase: "done",
            completedAt: Date.now(),
            pendingInput: [],
          });
          break;
        }

        case "cancelled":
          jobDone.current = true;
          clearInputNotification();
          updateJob(sid, {
            status: "cancelled",
            phase: "done",
            completedAt: Date.now(),
          });
          break;

        case "error": {
          const job = useJobStore.getState().getJob(sid);
          if (job) {
            updateJob(sid, {
              progress: {
                ...job.progress,
                currentStep: `⚠️ ${msg.message || "Error occurred"}`,
              },
            });
          }
          break;
        }

        default:
          break;
      }
    };

    ws.onerror = () => {
      // Suppress errors for intentional closes or completed jobs
    };

    ws.onclose = () => {
      setWs(sid, null);

      // Don't reconnect if:
      // - We closed intentionally (navigation, cleanup)
      // - The job completed normally (we got a "done" event)
      if (intentionalClose.current || jobDone.current) return;

      const job = useJobStore.getState().getJob(sid);
      if (!job) return;

      // Don't reconnect completed/failed/cancelled jobs
      if (job.status === "completed" || job.status === "failed" || job.status === "cancelled") return;

      if (reconnectAttempts.current < MAX_RECONNECT_ATTEMPTS) {
        reconnectAttempts.current += 1;
        reconnectTimer.current = setTimeout(() => connect(sid), RECONNECT_DELAY_MS);
      } else if (serverCheckAttempts.current < MAX_SERVER_CHECK_ATTEMPTS) {
        // Don't give up yet — ask the server if the session is still alive
        serverCheckAttempts.current += 1;
        getSessionStatus(sid)
          .then((srv) => {
            if (srv.status === "active" && srv.in_memory) {
              // Server says session is alive — reset and keep trying
              reconnectAttempts.current = 0;
              const delay = RECONNECT_DELAY_MS * serverCheckAttempts.current;
              reconnectTimer.current = setTimeout(() => connect(sid), delay);
            } else {
              // Server confirms session is ended
              updateJob(sid, {
                status: "failed",
                phase: "done",
                completedAt: Date.now(),
                progress: { ...job.progress, currentStep: "Session ended on server." },
              });
            }
          })
          .catch(() => {
            // Status endpoint unreachable — give up
            updateJob(sid, {
              status: "failed",
              phase: "done",
              completedAt: Date.now(),
              progress: { ...job.progress, currentStep: "Connection lost. Restart the server and try again." },
            });
            pushEvent(sid, {
              type: "connection_error",
              data: { message: "Connection lost. Restart the server and try again." },
            });
          });
      } else {
        const hasPendingInput = !!job.pendingInput?.length;
        updateJob(sid, {
          status: hasPendingInput ? "waiting" : "failed",
          phase: hasPendingInput ? "reviewing" : "done",
          completedAt: hasPendingInput ? undefined : Date.now(),
          progress: {
            ...job.progress,
            currentStep: hasPendingInput
              ? "Connection interrupted — reconnecting…"
              : "Connection lost. Restart the server and try again.",
          },
        });
        pushEvent(sid, {
          type: "connection_error",
          data: {
            message: hasPendingInput
              ? "Connection interrupted while waiting for input. Reconnect in progress."
              : "Connection lost. Restart the server and try again.",
          },
        });
      }
    };
  }, []);

  useEffect(() => {
    if (!sessionId) return;

    // Don't connect for already-completed jobs — but check server first
    const job = useJobStore.getState().getJob(sessionId);
    if (job && (job.status === "failed" || job.status === "cancelled")) {
      // Session may still be live on the server — verify before giving up
      const sid = sessionId;
      getSessionStatus(sid)
        .then((srv) => {
          if (srv.status === "active" && srv.in_memory) {
            reconnectAttempts.current = 0;
            serverCheckAttempts.current = 0;
            // Preserve pending input state — if the server is still waiting,
            // the reconnected WS will receive the waiting_for_input event again.
            const hasPending = !!job.pendingInput?.length;
            updateJob(sid, {
              status: hasPending ? "waiting" : "running",
              phase: job.phase === "done" ? "researching" : job.phase,
              completedAt: undefined,
            });
            intentionalClose.current = false;
            jobDone.current = false;
            connect(sid);
          }
        })
        .catch(() => { /* server unreachable — stay in current state */ });
      return;
    }

    intentionalClose.current = false;
    jobDone.current = false;
    const timer = setTimeout(() => connect(sessionId), 800);

    return () => {
      clearTimeout(timer);
      intentionalClose.current = true;
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
      if (wsRef.current && wsRef.current.readyState < WebSocket.CLOSING) {
        wsRef.current.close();
      }
      if (sessionId) setWs(sessionId, null);
    };
  }, [sessionId, connect]);

  useEffect(() => {
    if (!sessionId) return;

    const interval = setInterval(() => {
      const job = useJobStore.getState().getJob(sessionId);
      if (!job) return;
      if (job.status === "completed" || job.status === "failed" || job.status === "cancelled") return;

      const ws = wsRef.current;
      if (ws?.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: "ping" }));
      } else if (!ws || ws.readyState === WebSocket.CLOSED) {
        connect(sessionId);
      }
    }, HEARTBEAT_INTERVAL_MS);

    return () => clearInterval(interval);
  }, [sessionId, connect]);

  const safeSend = useCallback((data: string) => {
    let ws = wsRef.current;

    if (ws?.readyState === WebSocket.OPEN) {
      ws.send(data);
      return;
    }

    const attachOpenHandler = (socket: WebSocket) => {
      const handler = () => {
        socket.removeEventListener("open", handler);
        if (socket.readyState === WebSocket.OPEN) {
          socket.send(data);
        }
      };
      socket.addEventListener("open", handler);
    };

    if (ws?.readyState === WebSocket.CONNECTING) {
      attachOpenHandler(ws);
      return;
    }

    if (!sessionId) return;

    connect(sessionId);
    ws = wsRef.current;
    if (ws) {
      attachOpenHandler(ws);
    }
  }, [sessionId, connect]);

  const sendMessage = useCallback(
    (content: string) => {
      // Reset done flag so the WS can reconnect for follow-up turns.
      // This matches the CLI where the user can type after any turn ends.
      jobDone.current = false;
      safeSend(JSON.stringify({ type: "message", content }));
    },
    [safeSend],
  );

  // Guard: track the question text we last responded to so we never
  // double-send for the same prompt (e.g. accidental rapid clicks).
  const lastAnsweredQuestion = useRef<string | null>(null);

  const sendUserResponse = useCallback(
    (content: string, origin: "explicit" | "choice" | "skip" = "explicit") => {
      if (!sessionId) return;
      const normalized = content.trim();
      if (!normalized) return;

      // Prevent duplicate sends for the exact same pending question
      const currentJob = useJobStore.getState().getJob(sessionId);
      const currentQuestion = currentJob?.pendingInput?.[0]?.question ?? null;
      if (currentQuestion && currentQuestion === lastAnsweredQuestion.current) return;
      lastAnsweredQuestion.current = currentQuestion;

      safeSend(JSON.stringify({ type: "user_response", content: normalized }));
      // Push the response as an event so it appears in the activity feed
      pushEvent(sessionId, { type: "user_response", data: { content: normalized, origin } });
      // Remove the answered question (first in queue) — keep remaining
      const rest = (currentJob?.pendingInput || []).slice(1);
      updateJob(sessionId, {
        status: rest.length > 0 ? "waiting" : "running",
        pendingInput: rest.length > 0 ? rest : undefined,
      });
      if (rest.length === 0) clearInputNotification();
    },
    [sessionId, safeSend],
  );

  // Reset the duplicate guard whenever a new question arrives
  const currentPendingQuestion = useJobStore(
    (s) => s.getJob(sessionId ?? "")?.pendingInput?.[0]?.question ?? null,
  );
  useEffect(() => {
    if (currentPendingQuestion) {
      lastAnsweredQuestion.current = null;
    }
  }, [currentPendingQuestion]);

  const cancel = useCallback(
    () => safeSend(JSON.stringify({ type: "cancel" })),
    [safeSend],
  );

  return { sendMessage, sendUserResponse, cancel };
}
