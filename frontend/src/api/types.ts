/* API response types matching the FastAPI backend */

export interface Agent {
  name: string;
  display_name: string;
  description: string;
  model: string;
  infer: boolean;
}

export interface OutputFile {
  path: string;
  relative: string;
  name: string;
  type: string; // "pptx" | "markdown" | "python" | "shell" | "bicep" | "json" | "yaml" | "typescript" | "text"
  category: string; // "slides" | "demos" | "hackathons" | "ai-projects"
  size: number;
  modified: number;
}

export interface SessionInfo {
  id: string;
  agent: string;
  model: string;
  started_at: string;
  ended_at: string | null;
  status: string;
  frontend: string;
  summary: string | null;
  nickname: string | null;
  turn_count: number;
  total_input_tokens: number;
  total_output_tokens: number;
  resumable: number;
}

export interface Turn {
  id: string;
  session_id: string;
  turn_number: number;
  agent: string;
  model: string;
  user_prompt: string;
  assistant_response: string;
  started_at: string;
  ended_at: string | null;
  duration_ms: number;
  input_tokens: number;
  output_tokens: number;
  estimated_cost_usd: number;
  tool_call_count: number;
  subagent_count: number;
  status: string;
}

export interface Invocation {
  id: string;
  turn_id: string;
  session_id: string;
  type: string;
  name: string;
  input: string;
  output: string | null;
  started_at: string;
  ended_at: string | null;
  duration_ms: number;
  status: string;
  error_message: string | null;
}

export interface PptxSlide {
  index: number;
  title: string;
  body_preview: string;
  notes: string;
  png_base64: string;
  width: number;
  height: number;
}

export interface UsageAgentEntry {
  agent: string;
  input_tokens: number;
  output_tokens: number;
  cost_usd: number;
  turn_count: number;
}

export interface GroupedOutput {
  id: string;
  title: string;
  category: string;
  primary_file: string;
  file_count: number;
  files: string[];
  content_level: string | null;
  duration: string | null;
  has_pdf: boolean;
  has_architecture?: boolean;
  architecture_docs?: string[];
  has_solution?: boolean;
  size: number;
  modified: number;
}

export interface UsageStats {
  total_input_tokens: number;
  total_output_tokens: number;
  total_cost_usd: number;
  turn_count: number;
  by_agent: UsageAgentEntry[];
  by_model: { model: string; input_tokens: number; output_tokens: number; cost_usd: number; turn_count: number }[];
}

export interface WsAssistantMessage { content: string; }

export interface WsSessionStateChanged {
  session_id: string;
  status: string;
  reason: string;
}

export interface WsHeartbeat {
  ts: number;
}

// Agent type mappings
export type AgentType =
  | "slide-conductor"
  | "demo-conductor"
  | "ai-demo-conductor"
  | "hackathon-conductor"
  | "ai-brainstorming"
  | "ai-solution-architect"
  | "ai-implementor";

export const AGENT_META: Record<
  AgentType,
  {
    label: string;
    icon: string;
    color: string;
    description: string;
    showContentLevel: boolean;
    showDuration: boolean;
    showAudience: boolean;
    defaultLevel: ContentLevel;
    beta?: boolean;
    /** Override the "Topic" field label and placeholder per agent. */
    topicLabel?: string;
    topicPlaceholder?: string;
    /** Override the duration dropdown options per agent. Falls back to DURATIONS. */
    durationOptions?: readonly string[];
  }
> = {
  "slide-conductor": {
    label: "Create a Presentation",
    icon: "📊",
    color: "#0078D4",
    description: ".pptx with speaker notes",
    showContentLevel: true,
    showDuration: true,
    showAudience: true,
    defaultLevel: "L300",
  },
  "demo-conductor": {
    label: "Build a Demo Guide",
    icon: "🎮",
    color: "#7FBA00",
    description: "Step-by-step guide + companion scripts",
    showContentLevel: true,
    showDuration: true,
    showAudience: false,
    defaultLevel: "L300",
  },
  "hackathon-conductor": {
    label: "Design a Hackathon",
    icon: "🏆",
    color: "#FFB900",
    description: "What-The-Hack challenges + coach guide",
    showContentLevel: true,
    showDuration: true,
    showAudience: true,
    defaultLevel: "L300",
    durationOptions: ["Half day", "Full day", "2 days"],
  },
  "ai-brainstorming": {
    label: "Brainstorm AI Projects",
    icon: "💡",
    color: "#00A4EF",
    description: "10+ ranked ideas with Azure service mapping",
    showContentLevel: false,
    showDuration: false,
    showAudience: false,
    defaultLevel: "L200",
    beta: true,
    topicLabel: "Customer & Industry",
    topicPlaceholder: "e.g. Contoso — retail banking, 500+ branches",
  },
  "ai-solution-architect": {
    label: "Architect a Solution",
    icon: "🏗️",
    color: "#8661C5",
    description: "Design docs + diagrams + cost estimate",
    showContentLevel: false,
    showDuration: false,
    showAudience: false,
    defaultLevel: "L200",
    beta: true,
    topicLabel: "Business Challenge",
    topicPlaceholder: "e.g. Automate claims processing for an insurance company",
  },
  "ai-implementor": {
    label: "Build an AI Project",
    icon: "🚀",
    color: "#F25022",
    description: "Bicep + app code + CI/CD + tests",
    showContentLevel: false,
    showDuration: false,
    showAudience: false,
    defaultLevel: "L200",
    beta: true,
    topicLabel: "Project Focus",
    topicPlaceholder: "e.g. Document intelligence pipeline for invoice processing",
  },
  "ai-demo-conductor": {
    label: "Create Project Demos",
    icon: "🎬",
    color: "#00B294",
    description: "Demo guides + companion scripts from a built project",
    showContentLevel: false,
    showDuration: false,
    showAudience: false,
    defaultLevel: "L300",
    beta: true,
    topicLabel: "Demo Focus",
    topicPlaceholder: "e.g. End-to-end document processing workflow demo",
  },
};

export const CONTENT_LEVELS = ["L100", "L200", "L300", "L400"] as const;
export type ContentLevel = (typeof CONTENT_LEVELS)[number];

export const CONTENT_LEVEL_META: Record<
  ContentLevel,
  { label: string; color: string; meaning: string }
> = {
  L100: { label: "L100", color: "#7FBA00", meaning: "Executive Overview" },
  L200: { label: "L200", color: "#00A4EF", meaning: "Architecture" },
  L300: { label: "L300", color: "#0078D4", meaning: "Deep Dive" },
  L400: { label: "L400", color: "#F25022", meaning: "Expert" },
};

export const DURATIONS = [
  "15 min",
  "30 min",
  "45 min",
  "1 hour",
  "1.5 hours",
  "2 hours",
] as const;

// ── WebSocket envelope protocol ────────────────────────────────────

/** v1 message envelope — all WebSocket messages from the backend are wrapped in this */
export interface WsEnvelope<T = Record<string, unknown>> {
  v: 1;
  type: string;
  id: string;           // UUID for dedup
  seq: number;          // monotonic per-session sequence
  ts: number;           // server epoch seconds
  correlationId: string | null;
  data: T;
}

/** Data payloads for specific message types */
export interface WsToolStarted {
  tool: string;
  args: string;
  _subagent?: string;
}

export interface WsToolCompleted {
  tool: string;
  duration_ms: number;
  output_preview: string | null;
  _subagent?: string;
}

export interface WsSubagentStarted { agent: string; }
export interface WsSubagentCompleted { agent: string; }
export interface WsSubagentFailed { agent: string; error: string; }
export interface WsSubagentSelected { agent: string; }
export interface WsDelta { content: string; }
export interface WsDone { status: string; }
export interface WsError { message: string; }
export interface WsWaitingForInput { question: string; choices?: string[]; }
export interface WsInputResolved {}
export interface WsPhaseChanged { phase: string; }
export interface WsNewFiles { files: string[]; }
export interface WsUsage {
  input_tokens: number;
  output_tokens: number;
  cache_read_tokens: number;
  cache_write_tokens: number;
}
export interface WsSessionSnapshot {
  session_id: string;
  status: "active" | "waiting" | "idle";
  pending_input: { question: string; choices?: string[] } | null;
  last_done: { status: string } | null;
  active_subagents: string[];
  seq: number;
}
