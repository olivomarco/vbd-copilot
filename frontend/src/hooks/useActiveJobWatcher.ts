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
import { getSessionStatus } from "@/api/client";

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
  /** Seen envelope IDs for waiting_for_input dedup across hooks. */
  const seenWaitingIds = useRef<Set<string>>(new Set());

  const jobs = useJobStore((s) => s.jobs);
  const updateJob = useJobStore((s) => s.updateJob);
  const pushEvent = useJobStore((s) => s.pushEvent);

  useEffect(() => {
    const liveIds = new Set<string>();

    for (const [id, job] of Object.entries(jobs)) {
      const isLive = job.status === "running" || job.status === "queued" || job.status === "waiting";
      if (!isLive) continue;

      // If the AgentWorkspace's useWebSocket already has a WS **fully
      // connected** (OPEN), keep our watcher WS alive as a backup
      // transport — but skip creating a new one if we already have one.
      // Having two WSes receiving the same events is fine: the processing
      // gate below skips most events when the workspace WS is active,
      // and the store's pushEvent dedup handles the rest.
      //
      // CRITICAL: Do NOT close the watcher WS here.  If the workspace WS
      // drops briefly (reconnect, stale timeout, tab throttle), the
      // watcher provides continuity — without it, _send() sees 0 WSes
      // and silently drops events, causing permanent gaps in the feed.
      if (job._ws && job._ws.readyState === WebSocket.OPEN) {
        liveIds.add(id);
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
        const msgId: string | null = isEnvelope ? raw.id : null;

        // Handle session_snapshot — restore critical state (Fix 5)
        if (t === "session_snapshot") {
          const currentJob = useJobStore.getState().getJob(id);
          if (!currentJob) return;
          // Only process if the workspace WS is NOT active (it handles snapshots itself)
          if (currentJob._ws && currentJob._ws.readyState === WebSocket.OPEN) return;

          // Restore pending input
          if (msg.pending_input) {
            const q = msg.pending_input.question || "The agent has a question";
            const alreadyQueued = (currentJob.pendingInput || []).some((p: any) => p.question === q);
            if (!alreadyQueued) {
              updateJob(id, {
                status: "waiting",
                pendingInput: [
                  ...(currentJob.pendingInput || []),
                  { question: q, choices: msg.pending_input.choices, requestId: msg.pending_input_request_id },
                ],
              });
              void notifyInputRequired();
            }
          } else if (currentJob.pendingInput?.length && !currentJob.pendingInput[0].submitted) {
            clearInputNotification();
            updateJob(id, { status: "running", pendingInput: [] });
          }

          // Restore terminal state from snapshot
          if (msg.last_done && currentJob.status !== "completed" && currentJob.status !== "failed" && currentJob.status !== "cancelled") {
            const doneStatus = msg.last_done.status as string | undefined;
            if (doneStatus && doneStatus !== "timeout") {
              const jobStatus = doneStatus === "success" ? "completed" as const
                : doneStatus === "cancelled" ? "cancelled" as const
                : "failed" as const;
              clearInputNotification();
              updateJob(id, { status: jobStatus, phase: "done", completedAt: Date.now(), pendingInput: [] });
              if (jobStatus === "completed") notifyJobCompleted(currentJob.title || "Your content is ready");
            }
          }

          // Restore output files
          if (msg.output_files?.length) {
            const existing = new Set(currentJob.outputFiles);
            const newFiles = (msg.output_files as string[]).filter((f: string) => !existing.has(f));
            if (newFiles.length > 0) {
              updateJob(id, { outputFiles: [...currentJob.outputFiles, ...newFiles] });
            }
          }
          return;
        }

        // If the workspace WS is handling this session, skip most events.
        const wsCheckJob = useJobStore.getState().getJob(id);
        if (wsCheckJob?._ws && wsCheckJob._ws.readyState === WebSocket.OPEN) {
          if (t !== "done" && t !== "cancelled" && t !== "new_files" && t !== "input_timed_out") return;
        }

        // Guard against race conditions for waiting_for_input.
        if (t === "waiting_for_input" && msgId) {
          if (seenWaitingIds.current.has(msgId)) return;
          seenWaitingIds.current.add(msgId);
          // Prune dedup set (Fix 4)
          if (seenWaitingIds.current.size > 200) {
            const entries = Array.from(seenWaitingIds.current);
            seenWaitingIds.current = new Set(entries.slice(-100));
          }
          const raceCheckJob = useJobStore.getState().getJob(id);
          if (raceCheckJob) {
            const alreadyInFeed = raceCheckJob.events.some(
              (e) => e.type === "waiting_for_input" && (e.data as any).question === (msg.question || "The agent has a question"),
            );
            if (alreadyInFeed) return;
          }
        }

        if (t === "session_state_changed" && msg.status === "ended") {
          const currentJob = useJobStore.getState().getJob(id);
          if (currentJob && currentJob.status !== "completed" && currentJob.status !== "failed" && currentJob.status !== "cancelled") {
            updateJob(id, {
              status: "completed",
              phase: "done",
              completedAt: Date.now(),
              pendingInput: [],
            });
            clearInputNotification();
            notifyJobCompleted(currentJob.title || "Your content is ready");
          }
        }

        if (t === "waiting_for_input") {
          const question = msg.question || "The agent has a question";
          const choices = msg.choices || undefined;
          const requestId = msg.request_id || undefined;
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
              { question, choices, requestId },
            ],
          });
          // NOTE: Do NOT pushEvent here. The useWebSocket hook (from
          // AgentWorkspace or LiveJobCard) is responsible for pushing
          // waiting_for_input to the event feed. If the watcher also pushes,
          // the feed shows duplicate "Waiting for input" cards. The watcher
          // only needs to update pendingInput (for the UI badge/status) and
          // fire the notification sound.
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

        // Push input_timed_out to event feed so skipped questions render properly
        if (t === "input_timed_out") {
          pushEvent(id, { type: t, data: msg });
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

          // If output files weren't captured (WS race), fetch from server
          if (jobStatus === "completed") {
            const afterJob = useJobStore.getState().getJob(id);
            if (afterJob && afterJob.outputFiles.length === 0) {
              getSessionStatus(id)
                .then((srv) => {
                  const srvFiles: string[] = srv.output_files || [];
                  if (srvFiles.length > 0) {
                    const freshJob = useJobStore.getState().getJob(id);
                    if (freshJob) {
                      const existing = new Set(freshJob.outputFiles);
                      const newFiles = srvFiles.filter((f: string) => !existing.has(f));
                      if (newFiles.length > 0) {
                        updateJob(id, {
                          outputFiles: [...freshJob.outputFiles, ...newFiles],
                        });
                      }
                    }
                  }
                })
                .catch(() => {});
            }
          }
        }

        if (t === "cancelled") {
          clearInputNotification();
          updateJob(id, {
            status: "cancelled",
            phase: "done",
            completedAt: Date.now(),
          });
        }

        // Capture output files so CompletionToast and MissionControl have them
        if (t === "new_files") {
          const currentJob = useJobStore.getState().getJob(id);
          if (currentJob && Array.isArray(msg.files)) {
            const existing = new Set(currentJob.outputFiles);
            const newFiles = (msg.files as string[]).filter((f: string) => !existing.has(f));
            if (newFiles.length > 0) {
              updateJob(id, {
                outputFiles: [...currentJob.outputFiles, ...newFiles],
                phase: "delivering",
              });
            }
          }
          // Push to event feed so the workspace shows the card when user navigates
          pushEvent(id, { type: t, data: msg });
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
        // Reconnect if the job is still live (transient WS drop)
        const freshJob = useJobStore.getState().getJob(id);
        if (freshJob && (freshJob.status === "running" || freshJob.status === "queued" || freshJob.status === "waiting")) {
          setTimeout(() => {
            // Re-check — status may have changed during the delay
            const recheck = useJobStore.getState().getJob(id);
            if (recheck && (recheck.status === "running" || recheck.status === "queued" || recheck.status === "waiting") && !connections.current.has(id)) {
              // Trigger re-render to re-create the WS via the useEffect
              updateJob(id, { progress: { ...recheck.progress } });
            }
          }, 3000);
        }
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

  // Repeating reminder: re-fire notification every 60s while any job is waiting for input
  const waitingJobs = Object.values(jobs).filter((j) => j.status === "waiting");
  useEffect(() => {
    if (waitingJobs.length === 0) return;
    const interval = setInterval(() => {
      const current = Object.values(useJobStore.getState().jobs).filter(
        (j) => j.status === "waiting" && j.pendingInput?.length,
      );
      if (current.length > 0) {
        void notifyInputRequired();
      }
    }, 60_000);
    return () => clearInterval(interval);
  }, [waitingJobs.length > 0]);
}
