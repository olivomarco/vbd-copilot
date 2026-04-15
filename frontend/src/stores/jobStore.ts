import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { AgentType, ContentLevel } from "@/api/types";

/* ------------------------------------------------------------------ */
/* Cross-tab sync via BroadcastChannel                                 */
/* ------------------------------------------------------------------ */

const CHANNEL_NAME = "csa-studio-jobs-sync";
let _bc: BroadcastChannel | null = null;
let _suppressBroadcast = false;

try {
  _bc = new BroadcastChannel(CHANNEL_NAME);
} catch {
  // BroadcastChannel not supported — cross-tab sync disabled.
}

function broadcastJobUpdate(id: string, patch: Partial<Job>) {
  if (_suppressBroadcast || !_bc) return;
  try {
    // Strip non-serialisable fields
    const { _ws, ...safe } = patch as any;
    _bc.postMessage({ action: "updateJob", id, patch: safe });
  } catch { /* quota / closed channel */ }
}

function broadcastJobAdd(job: Job) {
  if (_suppressBroadcast || !_bc) return;
  try {
    const { _ws, ...safe } = job as any;
    _bc.postMessage({ action: "addJob", job: safe });
  } catch {}
}

function broadcastJobRemove(id: string) {
  if (_suppressBroadcast || !_bc) return;
  try {
    _bc.postMessage({ action: "removeJob", id });
  } catch {}
}

function broadcastPushEvent(id: string, event: Omit<JobEvent, "id" | "time">) {
  if (_suppressBroadcast || !_bc) return;
  try {
    _bc.postMessage({ action: "pushEvent", id, event });
  } catch {}
}

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
  /** Path to an existing architecture project (used by ai-implementor). */
  architecturePath?: string;
  /** Paths to architecture design documents to feed to the agent. */
  architectureDocs?: string[];
  /** Path to an existing built project (used by ai-demo-conductor). */
  projectPath?: string;
  /** Paths to project files to feed to the agent. */
  projectDocs?: string[];
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
    /** Server-generated request ID for correlating responses. */
    requestId?: string;
    /** True after the user sent a response; cleared by `input_resolved`. */
    submitted?: boolean;
    /** Epoch ms when the response was sent — drives retry timeout. */
    submittedAt?: number;
  }[];
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
  /** IDs of jobs whose "Ready" notification has been dismissed. */
  dismissedNotifications: Set<string>;

  addJob: (job: Job) => void;
  removeJob: (id: string) => void;
  updateJob: (id: string, patch: Partial<Job>) => void;
  pushEvent: (id: string, event: Omit<JobEvent, "id" | "time">) => void;
  setWs: (id: string, ws: WebSocket | null) => void;
  dismissNotification: (id: string) => void;

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
  dismissedNotifications: new Set<string>(),

  addJob: (job) => {
    set((s) => ({ jobs: { ...s.jobs, [job.id]: job } }));
    broadcastJobAdd(job);
  },

  removeJob: (id) => {
    set((s) => {
      const { [id]: _, ...rest } = s.jobs;
      return { jobs: rest };
    });
    broadcastJobRemove(id);
  },

  dismissNotification: (id) => {
    set((s) => ({ dismissedNotifications: new Set([...s.dismissedNotifications, id]) }));
  },

  updateJob: (id, patch) => {
    set((s) => {
      const existing = s.jobs[id];
      if (!existing) return s;
      const isTerminal =
        existing.status === "completed" ||
        existing.status === "failed" ||
        existing.status === "cancelled";
      const isReactivation =
        patch.status === "running" || patch.status === "queued" || patch.status === "waiting";
      if (isTerminal && !isReactivation && patch.status !== undefined) {
        return s;
      }
      return { jobs: { ...s.jobs, [id]: { ...existing, ...patch } } };
    });
    broadcastJobUpdate(id, patch);
  },

  pushEvent: (id, event) => {
    set((s) => {
      const job = s.jobs[id];
      if (!job) return s;

      // Defense-in-depth dedup: if an identical event (same type + data) was pushed
      // within the last 2 seconds, drop it. This catches events that bypass envelope
      // dedup (e.g. getSessionEvents hydration which lacks envelope IDs) and any
      // remaining reconnect replay edge cases.
      const now = Date.now();
      const dataKey = JSON.stringify(event.data);
      const isDuplicate = job.events
        .slice(-30)
        .some((e: JobEvent) => e.type === event.type && JSON.stringify(e.data) === dataKey && now - e.time < 2000);
      if (isDuplicate) return s;

      const newEvent: JobEvent = {
        ...event,
        id: ++_eventCounter,
        time: now,
      };
      // Keep only last 2000 events to preserve full session history
      const events = [...job.events, newEvent].slice(-2000);
      return {
        jobs: {
          ...s.jobs,
          [id]: { ...job, events },
        },
      };
    });
    broadcastPushEvent(id, event);
  },

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
        dismissedNotifications: [...state.dismissedNotifications],
      }),
      merge: (persisted: any, current: any) => ({
        ...current,
        ...persisted,
        dismissedNotifications: new Set(persisted?.dismissedNotifications || []),
      }),
    },
  ),
);

/* ------------------------------------------------------------------ */
/* Listen for cross-tab broadcasts                                     */
/* ------------------------------------------------------------------ */

if (_bc) {
  _bc.onmessage = (ev: MessageEvent) => {
    const data = ev.data;
    if (!data || typeof data !== "object") return;
    // Suppress re-broadcast to avoid infinite loops
    _suppressBroadcast = true;
    try {
      switch (data.action) {
        case "updateJob":
          useJobStore.getState().updateJob(data.id, data.patch);
          break;
        case "addJob":
          useJobStore.getState().addJob(data.job);
          break;
        case "removeJob":
          useJobStore.getState().removeJob(data.id);
          break;
        case "pushEvent":
          useJobStore.getState().pushEvent(data.id, data.event);
          break;
      }
    } finally {
      _suppressBroadcast = false;
    }
  };
}
