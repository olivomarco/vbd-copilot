import type { ReactNode } from "react";
import { useEffect } from "react";
import { Sidebar } from "./Sidebar";
import { GuidedTutorial } from "@/components/common/GuidedTutorial";
import { CompletionToast } from "@/components/common/CompletionToast";
import { useSettingsStore } from "@/stores/settingsStore";
import { useJobStore } from "@/stores/jobStore";
import { useTutorialStore } from "@/stores/tutorialStore";
import { useKeyboardShortcuts } from "@/hooks/useKeyboardShortcuts";

export function Shell({ children }: { children: ReactNode }) {
  const collapsed = useSettingsStore((s) => s.sidebarCollapsed);
  const setSidebarCollapsed = useSettingsStore((s) => s.setSidebarCollapsed);
  useKeyboardShortcuts();

  // Auto-collapse sidebar when window is narrow
  useEffect(() => {
    const mq = window.matchMedia("(max-width: 860px)");
    const handle = (e: MediaQueryListEvent | MediaQueryList) => {
      if (e.matches) setSidebarCollapsed(true);
    };
    handle(mq);
    mq.addEventListener("change", handle);
    return () => mq.removeEventListener("change", handle);
  }, [setSidebarCollapsed]);

  const allJobs = Object.values(useJobStore((s) => s.jobs));
  const hasRunning = allJobs.some(
    (j) => j.status === "running" || j.status === "queued",
  );
  const hasWaiting = allJobs.some((j) => j.status === "waiting");
  const showBar = hasRunning || hasWaiting;

  // Auto-start tutorial on first visit
  const hasSeenTutorial = useTutorialStore((s) => s.hasSeenTutorial);
  const tutorialActive = useTutorialStore((s) => s.active);
  const startTutorial = useTutorialStore((s) => s.start);
  useEffect(() => {
    if (!hasSeenTutorial && !tutorialActive) {
      // Small delay to let page render so data-tutorial targets exist
      const timer = setTimeout(() => startTutorial(), 600);
      return () => clearTimeout(timer);
    }
  }, [hasSeenTutorial, tutorialActive, startTutorial]);

  return (
    <div
      style={{
        display: "flex",
        height: "100vh",
        width: "100vw",
        overflow: "hidden",
      }}
    >
      <Sidebar />
      <main
        style={{
          flex: 1,
          marginLeft: collapsed ? 56 : 260,
          transition: "margin-left 0.25s cubic-bezier(0.4, 0, 0.2, 1)",
          overflow: "auto",
          height: "100vh",
          background: "var(--brand-light)",
          display: "flex",
          flexDirection: "column",
        }}
      >
        {showBar && (
          <div
            className={
              hasWaiting && !hasRunning
                ? "top-status-bar-waiting"
                : "top-status-bar-running"
            }
            style={{ flexShrink: 0 }}
          />
        )}
        <div style={{ flex: 1, overflow: "auto" }}>
          {children}
        </div>
      </main>
      <GuidedTutorial />
      <CompletionToast />
    </div>
  );
}
