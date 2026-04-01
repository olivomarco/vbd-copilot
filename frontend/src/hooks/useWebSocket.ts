import { useEffect, useRef, useCallback } from "react";
import { useJobStore } from "@/stores/jobStore";
import type { AgentPhase } from "@/stores/jobStore";

const BASE_WS = import.meta.env.VITE_WS_URL ?? `ws://${window.location.hostname}:${window.location.port}`;

const MAX_RECONNECT_ATTEMPTS = 3;
const RECONNECT_DELAY_MS = 2000;

/**
 * Opens a WebSocket to /ws/{sessionId}, parses events, and updates
 * the job store. Returns helpers to send messages and close.
 * Includes automatic reconnection on unexpected disconnect.
 */
export function useWebSocket(sessionId: string | null) {
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectAttempts = useRef(0);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const intentionalClose = useRef(false);
  const updateJob = useJobStore((s) => s.updateJob);
  const pushEvent = useJobStore((s) => s.pushEvent);
  const setWs = useJobStore((s) => s.setWs);

  const connect = useCallback((sid: string) => {
    const url = `${BASE_WS}/ws/${sid}`;
    const ws = new WebSocket(url);
    wsRef.current = ws;
    setWs(sid, ws);

    ws.onopen = () => {
      reconnectAttempts.current = 0;
      updateJob(sid, { status: "running" });
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
          updateJob(sid, {
            phase: msg.phase as AgentPhase,
          });
          break;

        case "tool_started": {
          const job = useJobStore.getState().getJob(sid);
          if (job) {
            updateJob(sid, {
              progress: {
                ...job.progress,
                toolCalls: job.progress.toolCalls + 1,
                currentStep: `Running ${msg.tool}`,
              },
            });
          }
          break;
        }

        case "tool_completed":
          // Nothing extra needed — event already in feed
          break;

        case "subagent_started": {
          const job = useJobStore.getState().getJob(sid);
          if (job) {
            updateJob(sid, {
              progress: {
                ...job.progress,
                subagentRuns: job.progress.subagentRuns + 1,
                currentStep: `Subagent: ${msg.agent}`,
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
                estimatedCostUsd: job.usage.estimatedCostUsd, // updated lazily
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
          updateJob(sid, {
            status: msg.status === "success" ? "completed" : "failed",
            phase: "done",
            completedAt: Date.now(),
            pendingInput: undefined,
          });
          break;

        case "cancelled":
          updateJob(sid, {
            status: "cancelled",
            phase: "done",
            completedAt: Date.now(),
          });
          break;

        case "error":
          // Don't override status if we're still mid-turn
          pushEvent(sid, { type: "connection_error", data: { message: msg.message } });
          break;
      }
    };

    ws.onerror = () => {
      if (!intentionalClose.current) {
        pushEvent(sid, { type: "connection_error", data: { message: "WebSocket connection error" } });
      }
    };

    ws.onclose = () => {
      setWs(sid, null);
      // Auto-reconnect if the job is still running and we didn't close on purpose
      const job = useJobStore.getState().getJob(sid);
      if (
        !intentionalClose.current &&
        job &&
        (job.status === "running" || job.status === "waiting") &&
        reconnectAttempts.current < MAX_RECONNECT_ATTEMPTS
      ) {
        reconnectAttempts.current += 1;
        pushEvent(sid, {
          type: "connection_error",
          data: { message: `Reconnecting... (attempt ${reconnectAttempts.current})` },
        });
        reconnectTimer.current = setTimeout(() => connect(sid), RECONNECT_DELAY_MS);
      }
    };
  }, []);  // connect is stable — no deps needed

  useEffect(() => {
    if (!sessionId) return;
    intentionalClose.current = false;
    connect(sessionId);

    return () => {
      intentionalClose.current = true;
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
      wsRef.current?.close();
      setWs(sessionId, null);
    };
  }, [sessionId, connect]);

  const sendMessage = useCallback(
    (content: string) => {
      wsRef.current?.send(JSON.stringify({ type: "message", content }));
    },
    [],
  );

  const sendUserResponse = useCallback(
    (content: string) => {
      if (!sessionId) return;
      wsRef.current?.send(JSON.stringify({ type: "user_response", content }));
      updateJob(sessionId, {
        status: "running",
        pendingInput: undefined,
      });
    },
    [sessionId],
  );

  const cancel = useCallback(() => {
    wsRef.current?.send(JSON.stringify({ type: "cancel" }));
  }, []);

  return { sendMessage, sendUserResponse, cancel };
}
