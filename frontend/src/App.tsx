import { Routes, Route, Navigate } from "react-router-dom";
import { Shell } from "./components/layout/Shell";
import { Launchpad } from "./pages/Launchpad";
import { OutputLibrary } from "./pages/OutputLibrary";
import { SlideViewer } from "./components/viewers/SlideViewer";
import { MarkdownViewer } from "./components/viewers/MarkdownViewer";
import { ProjectExplorer } from "./components/viewers/ProjectExplorer";
import { Sessions } from "./pages/Sessions";
import { Settings } from "./pages/Settings";
import { AgentWorkspace } from "./pages/AgentWorkspace";
import { MissionControl } from "./pages/MissionControl";
import { useJobStore } from "./stores/jobStore";

// Run ONCE at module load: clean up stale jobs from previous browser sessions.
const _cleanupDone = (() => {
  // Small delay to let zustand/persist hydrate from localStorage
  setTimeout(() => {
    const jobs = useJobStore.getState().jobs;
    for (const [id, job] of Object.entries(jobs)) {
      if (job.status === "running" || job.status === "queued" || job.status === "waiting") {
        // If the job had real work done (events, tool calls), mark as completed
        // — it likely finished but the status didn't persist.
        // If it never started (0 events), mark as failed.
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
      <Routes>
        <Route path="/" element={<Launchpad />} />
        <Route path="/mission" element={<MissionControl />} />
        <Route path="/workspace" element={<AgentWorkspace />} />
        <Route path="/library" element={<OutputLibrary />} />
        <Route path="/library/slides" element={<SlideViewer />} />
        <Route path="/library/markdown" element={<MarkdownViewer />} />
        <Route path="/library/project" element={<ProjectExplorer />} />
        <Route path="/sessions" element={<Sessions />} />
        <Route path="/settings" element={<Settings />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Shell>
  );
}
