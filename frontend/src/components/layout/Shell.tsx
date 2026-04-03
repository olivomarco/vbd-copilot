import type { ReactNode } from "react";
import { Sidebar } from "./Sidebar";
import { useSettingsStore } from "@/stores/settingsStore";
import { useJobStore } from "@/stores/jobStore";
import { useKeyboardShortcuts } from "@/hooks/useKeyboardShortcuts";

export function Shell({ children }: { children: ReactNode }) {
  const collapsed = useSettingsStore((s) => s.sidebarCollapsed);
  useKeyboardShortcuts();

  const allJobs = Object.values(useJobStore((s) => s.jobs));
  const hasRunning = allJobs.some(
    (j) => j.status === "running" || j.status === "queued",
  );
  const hasWaiting = allJobs.some((j) => j.status === "waiting");
  const showBar = hasRunning || hasWaiting;

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
    </div>
  );
}
