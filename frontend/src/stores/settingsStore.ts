import { create } from "zustand";

const STORAGE_KEY = "csa-copilot-settings";

interface PersistedSettings {
  theme: "light" | "dark" | "system";
  sidebarCollapsed: boolean;
  verboseMode: boolean;
}

interface SettingsStore extends PersistedSettings {
  setTheme: (t: "light" | "dark" | "system") => void;
  toggleSidebar: () => void;
  setSidebarCollapsed: (v: boolean) => void;
  setVerboseMode: (v: boolean) => void;
}

const DEFAULTS: PersistedSettings = {
  theme: "light",
  sidebarCollapsed: false,
  verboseMode: false,
};

function readSettings(): PersistedSettings {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return DEFAULTS;
    return { ...DEFAULTS, ...JSON.parse(raw) };
  } catch {
    return DEFAULTS;
  }
}

function writeSettings(patch: Partial<PersistedSettings>) {
  try {
    const current = readSettings();
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ ...current, ...patch }));
  } catch {
    // localStorage unavailable
  }
}

export const useSettingsStore = create<SettingsStore>((set) => ({
  ...readSettings(),
  setTheme: (theme) => {
    writeSettings({ theme });
    set({ theme });
  },
  toggleSidebar: () =>
    set((s) => {
      const sidebarCollapsed = !s.sidebarCollapsed;
      writeSettings({ sidebarCollapsed });
      return { sidebarCollapsed };
    }),
  setSidebarCollapsed: (sidebarCollapsed) => {
    writeSettings({ sidebarCollapsed });
    set({ sidebarCollapsed });
  },
  setVerboseMode: (verboseMode) => {
    writeSettings({ verboseMode });
    set({ verboseMode });
  },
}));
