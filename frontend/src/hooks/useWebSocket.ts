import { useEffect, useRef, useCallback } from "react";
import { useJobStore } from "@/stores/jobStore";
import type { AgentPhase } from "@/stores/jobStore";
import { getSessionStatus } from "@/api/client";

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

  const connect = useCallback((sid: string) => {
    // Close any existing connection first
    if (wsRef.current && wsRef.current.readyState < WebSocket.CLOSING) {
      intentionalClose.current = true;
      wsRef.current.close();
      intentionalClose.current = false;
    }

    jobDone.current = false;
    const url = `${BASE_WS}/ws/${sid}`;
    const ws = new WebSocket(url);
    wsRef.current = ws;
    setWs(sid, ws);

    ws.onopen = () => {
      reconnectAttempts.current = 0;
      // Preserve a waiting review gate if the socket reconnects mid-approval.
      const job = useJobStore.getState().getJob(sid);
      if (job && job.status !== "completed" && job.status !== "failed" && job.status !== "cancelled") {
        updateJob(sid, { status: job.pendingInput?.length ? "waiting" : "running" });
      }
    };

    ws.onmessage = (ev) => {
      let msg: any;
      try {
        msg = JSON.parse(ev.data);
      } catch {
        return;
      }

      const t = msg.type as string;

      if (t !== "pong" && t !== "heartbeat") {
        // Push raw event to the activity feed
        pushEvent(sid, { type: t, data: msg });
      }

      switch (t) {
        case "turn_started":
          updateJob(sid, {
            status: "running",
            phase: "researching",
            pendingInput: [],
            progress: {
              toolCalls: 0,
              subagentRuns: 0,
              currentStep: "Starting...",
            },
          });
          break;

        case "phase_changed":
          updateJob(sid, { phase: msg.phase as AgentPhase });
          break;

        case "tool_started": {
          const job = useJobStore.getState().getJob(sid);
          if (job) {
            const patch: Record<string, unknown> = {
              progress: {
                ...job.progress,
                toolCalls: job.progress.toolCalls + 1,
                currentStep: `Running ${msg.tool || "tool"}`,
              },
            };
            // Agent moved past waiting — clear pendingInput
            if (job.status === "waiting" || job.pendingInput?.length) {
              patch.status = "running";
              patch.pendingInput = [];
            }
            updateJob(sid, patch);
          }
          break;
        }

        case "subagent_started": {
          const job = useJobStore.getState().getJob(sid);
          if (job) {
            const patch: Record<string, unknown> = {
              progress: {
                ...job.progress,
                subagentRuns: job.progress.subagentRuns + 1,
                currentStep: `Subagent: ${msg.agent || "agent"}`,
              },
            };
            // Agent moved past waiting — clear pendingInput
            if (job.status === "waiting" || job.pendingInput?.length) {
              patch.status = "running";
              patch.pendingInput = [];
            }
            updateJob(sid, patch);
          }
          break;
        }

        case "waiting_for_input": {
          const question = msg.question || "The agent has a question";
          const choices = msg.choices || undefined;
          // Deduplicate: if the last waiting_for_input event in the feed
          // has the same question, skip pushing a new event (happens on WS reconnect).
          const currentJob = useJobStore.getState().getJob(sid);
          if (currentJob) {
            const lastWaiting = [...currentJob.events].reverse().find(
              (e) => e.type === "waiting_for_input",
            );
            const isDuplicate =
              lastWaiting &&
              (lastWaiting.data as any).question === question &&
              // Only if there's no user_response after the last waiting event
              !currentJob.events.some(
                (e) => e.type === "user_response" && e.id > lastWaiting.id,
              );
            if (isDuplicate) {
              // Still update the job status but don't push a duplicate event
              updateJob(sid, { status: "waiting" });
              break;
            }
          }
          const prevQueue = currentJob?.pendingInput || [];
          updateJob(sid, {
            status: "waiting",
            pendingInput: [...prevQueue, { question, choices }],
          });
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

  const sendUserResponse = useCallback(
    (content: string) => {
      if (!sessionId) return;
      safeSend(JSON.stringify({ type: "user_response", content }));
      // Push the response as an event so it appears in the activity feed
      pushEvent(sessionId, { type: "user_response", data: { content } });
      // Remove the answered question (first in queue) — keep remaining
      const currentJob = useJobStore.getState().getJob(sessionId);
      const rest = (currentJob?.pendingInput || []).slice(1);
      updateJob(sessionId, {
        status: rest.length > 0 ? "waiting" : "running",
        pendingInput: rest.length > 0 ? rest : undefined,
      });
    },
    [sessionId, safeSend],
  );

  const cancel = useCallback(
    () => safeSend(JSON.stringify({ type: "cancel" })),
    [safeSend],
  );

  return { sendMessage, sendUserResponse, cancel };
}
