import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { AgentType, ContentLevel } from "@/api/types";

/* ------------------------------------------------------------------ */
/* Types                                                               */
/* ------------------------------------------------------------------ */

export type JobStatus =
  | "queued"
  | "running"
  | "waiting"
  | "completed"
  | "failed"
  | "cancelled";

export type AgentPhase =
  | "researching"
  | "planning"
  | "reviewing"
  | "building"
  | "qa"
  | "delivering"
  | "done";

export interface JobBrief {
  topic: string;
  contentLevel: ContentLevel;
  duration: string;
  audience?: string;
  notes?: string;
}

export interface JobEvent {
  id: number;
  time: number;
  type: string;
  data: Record<string, unknown>;
}

export interface Job {
  id: string; // session_id
  title: string;
  agent: AgentType;
  brief: JobBrief;
  status: JobStatus;
  phase: AgentPhase;
  startedAt: number;
  completedAt?: number;
  progress: {
    toolCalls: number;
    subagentRuns: number;
    currentStep: string;
  };
  events: JobEvent[];
  pendingInput?: {
    question: string;
    choices?: string[];
  };
  outputFiles: string[];
  usage: {
    inputTokens: number;
    outputTokens: number;
    estimatedCostUsd: number;
  };
  /** The WebSocket instance for this job (not serialised) */
  _ws?: WebSocket | null;
}

/* ------------------------------------------------------------------ */
/* Store                                                               */
/* ------------------------------------------------------------------ */

interface JobStore {
  jobs: Record<string, Job>;

  addJob: (job: Job) => void;
  removeJob: (id: string) => void;
  updateJob: (id: string, patch: Partial<Job>) => void;
  pushEvent: (id: string, event: Omit<JobEvent, "id" | "time">) => void;
  setWs: (id: string, ws: WebSocket | null) => void;

  /** Computed helpers */
  activeJobs: () => Job[];
  waitingJobs: () => Job[];
  completedJobs: () => Job[];
  getJob: (id: string) => Job | undefined;
}

let _eventCounter = 0;

export const useJobStore = create<JobStore>()(
  persist(
    (set, get) => ({
  jobs: {},

  addJob: (job) =>
    set((s) => ({ jobs: { ...s.jobs, [job.id]: job } })),

  removeJob: (id) =>
    set((s) => {
      const { [id]: _, ...rest } = s.jobs;
      return { jobs: rest };
    }),

  updateJob: (id, patch) =>
    set((s) => {
      const existing = s.jobs[id];
      if (!existing) return s;
      return { jobs: { ...s.jobs, [id]: { ...existing, ...patch } } };
    }),

  pushEvent: (id, event) =>
    set((s) => {
      const job = s.jobs[id];
      if (!job) return s;
      const newEvent: JobEvent = {
        ...event,
        id: ++_eventCounter,
        time: Date.now(),
      };
      // Keep only last 200 events to avoid localStorage bloat
      const events = [...job.events, newEvent].slice(-200);
      return {
        jobs: {
          ...s.jobs,
          [id]: { ...job, events },
        },
      };
    }),

  setWs: (id, ws) =>
    set((s) => {
      const job = s.jobs[id];
      if (!job) return s;
      return { jobs: { ...s.jobs, [id]: { ...job, _ws: ws } } };
    }),

  activeJobs: () =>
    Object.values(get().jobs).filter(
      (j) => j.status === "running" || j.status === "queued",
    ),

  waitingJobs: () =>
    Object.values(get().jobs).filter((j) => j.status === "waiting"),

  completedJobs: () =>
    Object.values(get().jobs).filter(
      (j) => j.status === "completed" || j.status === "failed" || j.status === "cancelled",
    ),

  getJob: (id) => get().jobs[id],
    }),
    {
      name: "csa-studio-jobs",
      // Don't persist WebSocket references
      partialize: (state) => ({
        jobs: Object.fromEntries(
          Object.entries(state.jobs).map(([k, v]) => [
            k,
            { ...v, _ws: undefined },
          ]),
        ),
      }),
    },
  ),
);
