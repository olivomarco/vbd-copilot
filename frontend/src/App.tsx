import { lazy, Suspense } from "react";
import { Routes, Route, Navigate } from "react-router-dom";
import { Shell } from "./components/layout/Shell";
import { useJobStore } from "./stores/jobStore";

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
// Only marks a job as lost if no other tab is actively updating it.
const _cleanupDone = (() => {
  // Small delay to let zustand/persist hydrate from localStorage
  setTimeout(() => {
    const jobs = useJobStore.getState().jobs;
    const now = Date.now();
    for (const [id, job] of Object.entries(jobs)) {
      if (job.status === "running" || job.status === "queued" || job.status === "waiting") {
        // Check if the job has recent event activity (within last 60s).
        // If it does, another tab is likely driving it — leave it alone.
        const lastEvent = job.events.length > 0 ? job.events[job.events.length - 1].time : 0;
        const isRecentlyActive = lastEvent > 0 && (now - lastEvent) < 60_000;
        if (isRecentlyActive) continue;

        // No recent activity — this job is genuinely orphaned.
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
