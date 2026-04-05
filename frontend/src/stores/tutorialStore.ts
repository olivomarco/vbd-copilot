import { create } from "zustand";

const STORAGE_KEY = "csa-copilot-tutorial-seen";

interface TutorialStore {
  /** Whether the tutorial overlay is currently visible */
  active: boolean;
  /** Current step index (0-based) */
  currentStep: number;
  /** Whether the user has completed the tutorial at least once */
  hasSeenTutorial: boolean;

  start: () => void;
  next: () => void;
  prev: () => void;
  goTo: (step: number) => void;
  finish: () => void;
  skip: () => void;
}

function readSeen(): boolean {
  try {
    return localStorage.getItem(STORAGE_KEY) === "true";
  } catch {
    return false;
  }
}

function writeSeen() {
  try {
    localStorage.setItem(STORAGE_KEY, "true");
  } catch {
    // localStorage unavailable
  }
}

export const useTutorialStore = create<TutorialStore>((set) => ({
  active: false,
  currentStep: 0,
  hasSeenTutorial: readSeen(),

  start: () => set({ active: true, currentStep: 0 }),

  next: () =>
    set((s) => ({ currentStep: s.currentStep + 1 })),

  prev: () =>
    set((s) => ({ currentStep: Math.max(0, s.currentStep - 1) })),

  goTo: (step: number) => set({ currentStep: step }),

  finish: () => {
    writeSeen();
    set({ active: false, currentStep: 0, hasSeenTutorial: true });
  },

  skip: () => {
    writeSeen();
    set({ active: false, currentStep: 0, hasSeenTutorial: true });
  },
}));
