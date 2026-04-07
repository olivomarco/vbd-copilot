import { create } from "zustand";

interface SettingsStore {
  theme: "light" | "dark" | "system";
  sidebarCollapsed: boolean;
  verboseMode: boolean;
  setTheme: (t: "light" | "dark" | "system") => void;
  toggleSidebar: () => void;
  setVerboseMode: (v: boolean) => void;
}

export const useSettingsStore = create<SettingsStore>((set) => ({
  theme: "light",
  sidebarCollapsed: false,
  verboseMode: false,
  setTheme: (theme) => set({ theme }),
  toggleSidebar: () => set((s) => ({ sidebarCollapsed: !s.sidebarCollapsed })),
  setVerboseMode: (verboseMode) => set({ verboseMode }),
}));
