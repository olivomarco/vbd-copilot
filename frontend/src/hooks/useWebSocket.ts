import { useEffect, useRef, useCallback } from "react";
import { useJobStore } from "@/stores/jobStore";
import type { AgentPhase } from "@/stores/jobStore";

const BASE_WS = import.meta.env.VITE_WS_URL ?? `ws://${window.location.hostname}:${window.location.port}`;

const MAX_RECONNECT_ATTEMPTS = 3;
const RECONNECT_DELAY_MS = 2000;

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
      // Only set to running if not already completed
      const job = useJobStore.getState().getJob(sid);
      if (job && job.status !== "completed" && job.status !== "failed" && job.status !== "cancelled") {
        updateJob(sid, { status: "running" });
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

      // Push raw event to the activity feed
      pushEvent(sid, { type: t, data: msg });

      switch (t) {
        case "turn_started":
          updateJob(sid, {
            status: "running",
            phase: "researching",
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
          const job = useJobStore.getState().getJob(sid);
          if (job) {
            updateJob(sid, {
              progress: {
                ...job.progress,
                subagentRuns: job.progress.subagentRuns + 1,
                currentStep: `Subagent: ${msg.agent || "agent"}`,
              },
            });
          }
          break;
        }

        case "waiting_for_input":
          updateJob(sid, {
            status: "waiting",
            phase: "reviewing",
            pendingInput: {
              question: msg.question || "The agent has a question",
              choices: msg.choices || undefined,
            },
          });
          break;

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

        case "done":
          jobDone.current = true;
          updateJob(sid, {
            status: msg.status === "success" ? "completed" : "failed",
            phase: "done",
            completedAt: Date.now(),
            pendingInput: undefined,
          });
          break;

        case "cancelled":
          jobDone.current = true;
          updateJob(sid, {
            status: "cancelled",
            phase: "done",
            completedAt: Date.now(),
          });
          break;

        case "error":
          pushEvent(sid, {
            type: "error",
            data: { message: msg.message || "Unknown error" },
          });
          break;

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
      } else {
        updateJob(sid, {
          status: "failed",
          phase: "done",
          completedAt: Date.now(),
        });
        pushEvent(sid, {
          type: "connection_error",
          data: { message: "Connection lost. Restart the server and try again." },
        });
      }
    };
  }, []);

  useEffect(() => {
    if (!sessionId) return;

    // Don't connect for already-completed jobs
    const job = useJobStore.getState().getJob(sessionId);
    if (job && (job.status === "completed" || job.status === "failed" || job.status === "cancelled")) {
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

  const safeSend = useCallback((data: string) => {
    const ws = wsRef.current;
    if (!ws) return;
    if (ws.readyState === WebSocket.OPEN) {
      ws.send(data);
    } else if (ws.readyState === WebSocket.CONNECTING) {
      const handler = () => {
        ws.removeEventListener("open", handler);
        if (ws.readyState === WebSocket.OPEN) ws.send(data);
      };
      ws.addEventListener("open", handler);
    }
  }, []);

  const sendMessage = useCallback(
    (content: string) => safeSend(JSON.stringify({ type: "message", content })),
    [safeSend],
  );

  const sendUserResponse = useCallback(
    (content: string) => {
      if (!sessionId) return;
      safeSend(JSON.stringify({ type: "user_response", content }));
      updateJob(sessionId, { status: "running", pendingInput: undefined });
    },
    [sessionId, safeSend],
  );

  const cancel = useCallback(
    () => safeSend(JSON.stringify({ type: "cancel" })),
    [safeSend],
  );

  return { sendMessage, sendUserResponse, cancel };
}
