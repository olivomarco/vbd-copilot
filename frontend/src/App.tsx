import { lazy, Suspense } from "react";
import { Routes, Route, Navigate } from "react-router-dom";
import { Shell } from "./components/layout/Shell";
import { useJobStore } from "./stores/jobStore";
import { useActiveJobWatcher } from "./hooks/useActiveJobWatcher";
import { getSessionStatus } from "./api/client";

const Launchpad = lazy(() => import("./pages/Launchpad").then(m => ({ default: m.Launchpad })));
const OutputLibrary = lazy(() => import("./pages/OutputLibrary").then(m => ({ default: m.OutputLibrary })));
const SlideViewer = lazy(() => import("./components/viewers/SlideViewer").then(m => ({ default: m.SlideViewer })));
const MarkdownViewer = lazy(() => import("./components/viewers/MarkdownViewer").then(m => ({ default: m.MarkdownViewer })));
const ProjectExplorer = lazy(() => import("./components/viewers/ProjectExplorer").then(m => ({ default: m.ProjectExplorer })));
const DrawioViewer = lazy(() => import("./components/viewers/DrawioViewer").then(m => ({ default: m.DrawioViewer })));
const Settings = lazy(() => import("./pages/Settings").then(m => ({ default: m.Settings })));
const AgentWorkspace = lazy(() => import("./pages/AgentWorkspace").then(m => ({ default: m.AgentWorkspace })));
const MissionControl = lazy(() => import("./pages/MissionControl").then(m => ({ default: m.MissionControl })));

// Run ONCE at module load: clean up stale jobs from previous browser sessions.
// Checks the server before marking jobs as completed to avoid killing sessions
// that are still running (e.g. long agent work with >60s between events).
const _cleanupDone = (() => {
  // Small delay to let zustand/persist hydrate from localStorage
  setTimeout(async () => {
    const jobs = useJobStore.getState().jobs;
    for (const [id, job] of Object.entries(jobs)) {
      if (job.status === "running" || job.status === "queued" || job.status === "waiting") {
        // Ask the server if the session is still alive with retries.
        let serverReachable = false;
        let serverSaysAlive = false;
        for (let attempt = 0; attempt < 3; attempt++) {
          try {
            const srv = await getSessionStatus(id);
            serverReachable = true;
            if (srv.status === "active" && (srv.in_memory || srv.has_running_turn)) {
              serverSaysAlive = true;
            }
            break;
          } catch {
            // Wait before retry: 1s, 3s, 5s
            if (attempt < 2) await new Promise(r => setTimeout(r, (attempt + 1) * 2000));
          }
        }

        if (serverSaysAlive) {
          // Server confirms this session is still running — leave it alone.
          continue;
        }

        if (!serverReachable) {
          // Server unreachable after retries — mark as stale, NOT terminal.
          // The session may still be alive; the WS reconnect will recover it.
          useJobStore.getState().updateJob(id, {
            progress: {
              ...job.progress,
              currentStep: "Server unreachable — reconnecting…",
            },
          });
          continue;
        }

        // Server says session is ended.
        const hadWork = job.progress.toolCalls > 0 || job.events.length > 5;
        useJobStore.getState().updateJob(id, {
          status: hadWork ? "completed" : "cancelled",
          phase: "done",
          completedAt: job.completedAt || Date.now(),
          progress: {
            ...job.progress,
            currentStep: hadWork ? "Completed (connection lost)" : "Cancelled (app restarted)",
          },
        });
      }
    }
  }, 100);
  return true;
})();

export function App() {
  // Maintain lightweight WS connections for all active jobs so notifications
  // (sound, badge, system) fire even when the user is not on the workspace page.
  useActiveJobWatcher();

  return (
    <Shell>
      <Suspense fallback={<div style={{ display: "flex", justifyContent: "center", padding: 80 }}>Loading...</div>}>
        <Routes>
          <Route path="/" element={<Launchpad />} />
          <Route path="/mission" element={<MissionControl />} />
          <Route path="/workspace" element={<AgentWorkspace />} />
          <Route path="/library" element={<OutputLibrary />} />
          <Route path="/library/slides" element={<SlideViewer />} />
          <Route path="/library/markdown" element={<MarkdownViewer />} />
          <Route path="/library/project" element={<ProjectExplorer />} />
          <Route path="/library/drawio" element={<DrawioViewer />} />
          <Route path="/settings" element={<Settings />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Suspense>
    </Shell>
  );
}
