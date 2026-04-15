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
const STALE_THRESHOLD_MS = 45_000; // 3 missed server heartbeats at 15s

/**
 * Exponential backoff: 1s, 2s, 4s, 8s, 16s, cap at 30s.
 * Adds ±25% jitter to prevent thundering herd.
 */
function getReconnectDelay(attempt: number): number {
  const base = 1000;
  const delay = Math.min(base * Math.pow(2, attempt), 30_000);
  const jitter = delay * 0.25 * (Math.random() * 2 - 1);
  return Math.round(delay + jitter);
}

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

  /** Timestamp of last message received from server — for stale connection detection. */
  const lastServerMessage = useRef<number>(Date.now());

  /** Apply a session_snapshot from the server to restore state. */
  function handleSnapshot(sid: string, snap: any) {
    const currentJob = useJobStore.getState().getJob(sid);
    if (!currentJob) return;

    // Restore active subagent stack from server
    activeSubagentStack.current = [...(snap.active_subagents || [])];

    // Restore pending input if server has one, or CLEAR if server resolved it
    if (snap.pending_input) {
      const q = snap.pending_input.question || "The agent has a question";
      const existingIdx = (currentJob.pendingInput || []).findIndex((p: any) => p.question === q);
      if (existingIdx === -1) {
        // Server has a question we don't know about — add it
        updateJob(sid, {
          status: "waiting",
          pendingInput: [...(currentJob.pendingInput || []), { question: q, choices: snap.pending_input.choices }],
        });
      } else if (currentJob.pendingInput![existingIdx].submitted) {
        // We sent a response but the server still has pending_input — the
        // response was lost during the WS drop. Reset to allow retry.
        const queue = [...currentJob.pendingInput!];
        queue[existingIdx] = { question: q, choices: snap.pending_input.choices };
        updateJob(sid, { status: "waiting", pendingInput: queue });
      }
    } else if (currentJob.pendingInput?.length) {
      // Server has NO pending input but the frontend still does — the
      // input was resolved while we were disconnected.  The input_resolved
      // event was lost (no WS at the time), but the server state is
      // authoritative.  Clear the stale question so the user doesn't get
      // stuck on "waiting for confirmation" / have to submit twice.
      clearInputNotification();
      updateJob(sid, {
        status: "running",
        pendingInput: [],
      });
    }

    // Restore done state if server says so.
    // A snapshot with last_done means the session already completed — mark it
    // terminal immediately so the reconnect loop doesn't re-arm.
    if (snap.last_done) {
      const doneStatus = snap.last_done.status as string | undefined;
      const isTimeout = doneStatus === "timeout";

      // Timeouts are non-fatal; every other outcome is terminal.
      if (!isTimeout) {
        jobDone.current = true;
      }

      if (currentJob.status !== "completed" && currentJob.status !== "failed" && currentJob.status !== "cancelled") {
        if (isTimeout) {
          // Timeout is non-fatal — replay the event; the session stays alive.
          pushEvent(sid, { type: "done", data: snap.last_done });
        } else {
          const jobStatus: "completed" | "failed" | "cancelled" =
            doneStatus === "success" ? "completed" :
            doneStatus === "cancelled" ? "cancelled" :
            "failed";
          clearInputNotification();
          updateJob(sid, {
            status: jobStatus,
            phase: "done",
            completedAt: Date.now(),
            pendingInput: [],
          });
          pushEvent(sid, { type: "done", data: snap.last_done });
          if (jobStatus === "completed") {
            notifyJobCompleted(currentJob.title || "Your content is ready");
          }
        }
      }
    }

    // Restore output files from server snapshot
    if (snap.output_files && Array.isArray(snap.output_files) && snap.output_files.length > 0) {
      const existingFiles = new Set(currentJob.outputFiles);
      const newFiles = (snap.output_files as string[]).filter((f: string) => !existingFiles.has(f));
      if (newFiles.length > 0) {
        updateJob(sid, {
          outputFiles: [...currentJob.outputFiles, ...newFiles],
        });
        // Also push a new_files event so the card appears in the feed.
        // Use `newFiles` (the delta), not `snap.output_files` (the full list),
        // so the card accurately reflects what was just added and isn't
        // duplicated if the same snapshot arrives again on reconnect.
        pushEvent(sid, { type: "new_files", data: { files: newFiles } });
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

    // Only clear jobDone when the job is not already in a terminal state.
    // Stale status-check timers from previous connections can set jobDone=true;
    // unconditionally resetting it here would re-arm the reconnect cycle.
    const existingJob = useJobStore.getState().getJob(sid);
    if (!existingJob || (existingJob.status !== "completed" && existingJob.status !== "failed" && existingJob.status !== "cancelled")) {
      jobDone.current = false;
    }
    activeSubagentStack.current = [];
    const url = `${BASE_WS}/ws/${sid}`;
    const ws = new WebSocket(url);
    wsRef.current = ws;
    setWs(sid, ws);

    ws.onopen = () => {
      reconnectAttempts.current = 0;
      // Do NOT clear seenIds here. The set must persist across reconnects so that
      // replayed envelopes (same UUID) are still recognised as duplicates.
      // Clearing it was the root cause of tool-call / turn_ended duplication on reconnect.

      const job = useJobStore.getState().getJob(sid);

      // Hydrate: fetch history for active jobs on every (re)connect so events
      // lost during WS disconnects are recovered from the server's DB.
      if (job && job.status !== "completed" && job.status !== "failed" && job.status !== "cancelled") {
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
      }, 10000);
    };

    ws.onmessage = (ev) => {
      let raw: any;
      try {
        raw = JSON.parse(ev.data);
      } catch {
        return;
      }

      // Any message from the server proves the connection is alive
      lastServerMessage.current = Date.now();

      // Unwrap v1 envelope — backward compat: raw messages still work
      const isEnvelope = raw.v === 1 && raw.id && raw.data;
      const t: string = raw.type;
      const msg = isEnvelope ? raw.data : raw;
      const msgId: string | null = isEnvelope ? raw.id : null;

      // Dedup by envelope ID
      if (msgId && seenIds.current.has(msgId)) return;
      if (msgId) {
        seenIds.current.add(msgId);
        // Prune dedup set to prevent unbounded growth (Fix 4)
        if (seenIds.current.size > 6000) {
          const entries = Array.from(seenIds.current);
          seenIds.current = new Set(entries.slice(-5000));
        }
      }

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
          const requestId = msg.request_id || undefined;
          const currentJob = useJobStore.getState().getJob(sid);
          const prevQueue = currentJob?.pendingInput || [];
          // Guard against the watcher hook having already queued this question
          const alreadyNotified = prevQueue.some((p) => p.question === question);
          if (!alreadyNotified) {
            updateJob(sid, {
              status: "waiting",
              pendingInput: [...prevQueue, { question, choices, requestId }],
            });
            void notifyInputRequired();
          } else {
            // Question already queued by watcher — just ensure status is waiting
            updateJob(sid, { status: "waiting" });
          }
          break;
        }

        case "input_resolved": {
          // Backend confirms the pending prompt was answered successfully.
          // Remove the first (submitted) item and advance the queue.
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
                estimatedCostUsd: job.usage.estimatedCostUsd + (msg.estimated_cost_usd || 0),
              },
            });
          }
          break;
        }

        case "session_state_changed": {
          if (msg.status === "ended") {
            jobDone.current = true;
            clearInputNotification();
            const stateJob = useJobStore.getState().getJob(sid);
            if (stateJob && stateJob.status !== "completed" && stateJob.status !== "failed" && stateJob.status !== "cancelled") {
              updateJob(sid, {
                status: "completed",
                phase: "done",
                completedAt: Date.now(),
                pendingInput: [],
              });
              pushEvent(sid, { type: "done", data: { status: "success", reason: msg.reason || "Session ended" } });
            }
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
        reconnectTimer.current = setTimeout(() => connect(sid), getReconnectDelay(reconnectAttempts.current));
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

      // Stale connection detection: if no message from server in 45s
      // (3 missed heartbeats at 15s interval), force reconnect
      if (ws?.readyState === WebSocket.OPEN && (Date.now() - lastServerMessage.current) > STALE_THRESHOLD_MS) {
        intentionalClose.current = false; // allow reconnect
        ws.close();
        return;
      }

      if (ws?.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: "ping" }));
      } else if (!ws || ws.readyState === WebSocket.CLOSED) {
        connect(sessionId);
      }
    }, HEARTBEAT_INTERVAL_MS);

    return () => clearInterval(interval);
  }, [sessionId, connect]);

  // When the tab/window regains visibility, immediately check whether the
  // session completed while we were off-screen. Browsers throttle or freeze
  // WebSocket traffic for background tabs, so the "done" event can be lost.
  useEffect(() => {
    if (!sessionId) return;
    const sid = sessionId;

    const onVisible = () => {
      if (document.visibilityState !== "visible") return;
      const job = useJobStore.getState().getJob(sid);
      if (!job) return;
      if (job.status === "completed" || job.status === "failed" || job.status === "cancelled") return;

      getSessionStatus(sid)
        .then((srv) => {
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

            // Restore output files from server if we missed the new_files event
            if (srv.output_files && srv.output_files.length > 0) {
              const existingFiles = new Set(freshJob.outputFiles);
              const newFiles = srv.output_files.filter((f: string) => !existingFiles.has(f));
              if (newFiles.length > 0) {
                updateJob(sid, { outputFiles: [...freshJob.outputFiles, ...newFiles] });
                pushEvent(sid, { type: "new_files", data: { files: newFiles } });
              }
            }
          } else if (srv.status === "active" && srv.in_memory) {
            // Session still alive — ensure WS is connected
            const ws = wsRef.current;
            if (!ws || ws.readyState === WebSocket.CLOSED || ws.readyState === WebSocket.CLOSING) {
              reconnectAttempts.current = 0;
              connect(sid);
            }
          }
        })
        .catch(() => { /* server unreachable — WS reconnect will handle it */ });
    };

    document.addEventListener("visibilitychange", onVisible);
    return () => document.removeEventListener("visibilitychange", onVisible);
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

      // Include request_id so the server can correlate with the correct prompt
      const requestId = currentJob?.pendingInput?.[0]?.requestId;
      const payload: Record<string, string> = { type: "user_response", content: normalized };
      if (requestId) payload.request_id = requestId;
      safeSend(JSON.stringify(payload));
      // Push the response as an event so it appears in the activity feed
      pushEvent(sessionId, { type: "user_response", data: { content: normalized, origin } });
      // Mark the first item as submitted rather than removing it.
      const queue = currentJob?.pendingInput || [];
      if (queue.length > 0) {
        const updated = [{ ...queue[0], submitted: true, submittedAt: Date.now() }, ...queue.slice(1)];
        updateJob(sessionId, { pendingInput: updated });
      }
    },
    [sessionId, safeSend],
  );

  // Reset the duplicate guard whenever a genuinely new (non-submitted) question arrives
  const currentPendingQuestion = useJobStore(
    (s) => {
      const input = s.getJob(sessionId ?? "")?.pendingInput?.[0];
      return input && !input.submitted ? input.question : null;
    },
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
