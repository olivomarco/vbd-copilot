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
