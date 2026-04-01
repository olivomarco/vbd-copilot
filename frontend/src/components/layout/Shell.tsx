import type { ReactNode } from "react";
import { Sidebar } from "./Sidebar";
import { useSettingsStore } from "@/stores/settingsStore";
import { useKeyboardShortcuts } from "@/hooks/useKeyboardShortcuts";

export function Shell({ children }: { children: ReactNode }) {
  const collapsed = useSettingsStore((s) => s.sidebarCollapsed);
  useKeyboardShortcuts();

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
        }}
      >
        {children}
      </main>
    </div>
  );
}
