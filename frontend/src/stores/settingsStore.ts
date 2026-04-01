import { create } from "zustand";

interface SettingsStore {
  theme: "light" | "dark" | "system";
  sidebarCollapsed: boolean;
  setTheme: (t: "light" | "dark" | "system") => void;
  toggleSidebar: () => void;
}

export const useSettingsStore = create<SettingsStore>((set) => ({
  theme: "light",
  sidebarCollapsed: false,
  setTheme: (theme) => set({ theme }),
  toggleSidebar: () => set((s) => ({ sidebarCollapsed: !s.sidebarCollapsed })),
}));
