/**
 * Global hook that maintains lightweight WebSocket connections for all
 * non-terminal jobs so that notifications (sound, favicon badge, system
 * notification) fire even when the user is not on the AgentWorkspace page.
 *
 * Mounted once in App.tsx. The full useWebSocket hook in AgentWorkspace
 * handles the detailed event feed and user interaction — this hook only
 * cares about detecting `waiting_for_input` to trigger notifications and
 * `done`/`cancelled` to finalize the job status.
 */

import { useEffect, useRef } from "react";
import { useJobStore } from "@/stores/jobStore";
import { notifyInputRequired, clearInputNotification, notifyJobCompleted } from "@/utils/notifications";

const WS_PROTOCOL = window.location.protocol === "https:" ? "wss:" : "ws:";
const BASE_WS = import.meta.env.VITE_WS_URL ?? `${WS_PROTOCOL}//${window.location.hostname}:${window.location.port}`;

const POLL_INTERVAL_MS = 8000;

/**
 * For each active (running/queued/waiting) job that does NOT already have a
 * WebSocket (_ws is null), open a lightweight WS that listens for key events
 * and updates the job store + fires notifications accordingly.
 */
export function useActiveJobWatcher() {
  const connections = useRef<Map<string, WebSocket>>(new Map());

  const jobs = useJobStore((s) => s.jobs);
  const updateJob = useJobStore((s) => s.updateJob);
  const pushEvent = useJobStore((s) => s.pushEvent);

  useEffect(() => {
    const liveIds = new Set<string>();

    for (const [id, job] of Object.entries(jobs)) {
      const isLive = job.status === "running" || job.status === "queued" || job.status === "waiting";
      if (!isLive) continue;

      // If the AgentWorkspace's useWebSocket already has a WS open, close
      // our watcher connection so only one WS is active per session.
      if (job._ws && job._ws.readyState < WebSocket.CLOSING) {
        liveIds.add(id);
        const existing = connections.current.get(id);
        if (existing) {
          existing.close();
          connections.current.delete(id);
        }
        continue;
      }

      liveIds.add(id);

      // Already have a watcher WS for this job
      if (connections.current.has(id)) continue;

      const ws = new WebSocket(`${BASE_WS}/ws/${id}`);
      connections.current.set(id, ws);

      ws.onmessage = (ev) => {
        let raw: any;
        try {
          raw = JSON.parse(ev.data);
        } catch {
          return;
        }

        // Unwrap v1 envelope
        const isEnvelope = raw.v === 1 && raw.id && raw.data;
        const t: string = raw.type;
        const msg = isEnvelope ? raw.data : raw;

        // If the workspace WS is handling this session, only process
        // terminal events (done/cancelled) as a safety net
        const wsCheckJob = useJobStore.getState().getJob(id);
        if (wsCheckJob?._ws && wsCheckJob._ws.readyState < WebSocket.CLOSING) {
          if (t !== "done" && t !== "cancelled") return;
        }

        if (t === "waiting_for_input") {
          const question = msg.question || "The agent has a question";
          const choices = msg.choices || undefined;
          const currentJob = useJobStore.getState().getJob(id);
          if (!currentJob) return;

          // Don't duplicate if the workspace WS already handled this
          const alreadyQueued = (currentJob.pendingInput || []).some(
            (p) => p.question === question,
          );
          if (alreadyQueued) return;

          updateJob(id, {
            status: "waiting",
            pendingInput: [
              ...(currentJob.pendingInput || []),
              { question, choices },
            ],
          });
          // Push to event feed so the workspace shows it when the user navigates
          pushEvent(id, { type: t, data: msg });
          void notifyInputRequired();
        }

        if (t === "input_resolved") {
          const currentJob = useJobStore.getState().getJob(id);
          if (!currentJob) return;
          const remaining = (currentJob.pendingInput || []).slice(1);
          updateJob(id, {
            status: remaining.length > 0 ? "waiting" : "running",
            pendingInput: remaining.length > 0 ? remaining : undefined,
          });
          if (remaining.length === 0) clearInputNotification();
        }

        if (t === "done") {
          const currentJob = useJobStore.getState().getJob(id);
          if (!currentJob) return;
          // Skip if already terminal
          if (currentJob.status === "completed" || currentJob.status === "failed" || currentJob.status === "cancelled") return;

          clearInputNotification();
          if (msg.status === "success") {
            notifyJobCompleted(currentJob.title || "Your content is ready");
          }
          if (msg.status === "timeout") return; // non-fatal

          const jobStatus = msg.status === "success"
            ? "completed" as const
            : msg.status === "cancelled"
              ? "cancelled" as const
              : "failed" as const;

          updateJob(id, {
            status: jobStatus,
            phase: "done",
            completedAt: Date.now(),
            pendingInput: [],
          });
        }

        if (t === "cancelled") {
          clearInputNotification();
          updateJob(id, {
            status: "cancelled",
            phase: "done",
            completedAt: Date.now(),
          });
        }

        // Forward subagent and tool progress so MissionControl cards update
        if (t === "subagent_started") {
          const currentJob = useJobStore.getState().getJob(id);
          if (currentJob) {
            updateJob(id, {
              progress: {
                ...currentJob.progress,
                subagentRuns: currentJob.progress.subagentRuns + 1,
                currentStep: `Subagent: ${msg.agent || "agent"}`,
              },
            });
          }
        }

        if (t === "tool_started") {
          const currentJob = useJobStore.getState().getJob(id);
          if (currentJob) {
            updateJob(id, {
              progress: {
                ...currentJob.progress,
                toolCalls: currentJob.progress.toolCalls + 1,
                currentStep: `Running ${msg.tool || "tool"}`,
              },
            });
          }
        }
      };

      ws.onerror = () => {};
      ws.onclose = () => {
        connections.current.delete(id);
      };
    }

    // Close WS for jobs that are no longer live
    for (const [id, ws] of connections.current) {
      if (!liveIds.has(id)) {
        ws.close();
        connections.current.delete(id);
      }
    }
  }, [
    // Re-run when the set of jobs or any status changes
    Object.entries(jobs)
      .filter(([, j]) => j.status === "running" || j.status === "queued" || j.status === "waiting")
      .map(([id, j]) => `${id}:${j.status}:${j._ws ? "ws" : ""}`)
      .join(","),
  ]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      for (const ws of connections.current.values()) {
        ws.close();
      }
      connections.current.clear();
    };
  }, []);
}
