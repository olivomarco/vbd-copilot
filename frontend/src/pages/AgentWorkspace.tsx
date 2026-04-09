import { useEffect, useMemo, useRef, useState, useCallback } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";
import {
  Text,
  Button,
  Card,
  Spinner,
  Textarea,
  Badge,
  Switch,
} from "@fluentui/react-components";
import {
  ArrowLeft20Regular,
  Dismiss20Regular,
  Checkmark20Regular,
  ArrowDownload20Regular,
  Send20Regular,
  ChevronDown12Regular,
  ChevronRight12Regular,
  Wrench20Regular,
  Flash20Regular,
  Warning20Regular,
  Bot20Regular,
  SlideText20Regular,
  Code20Regular,
  Document20Regular,
  Settings20Regular,
  DocumentText20Regular,
  FolderOpen20Regular,
  CheckmarkCircle20Regular,
  Pause20Regular,
  DataBarVertical20Regular,
  Timer20Regular,
  ClipboardTask20Regular,
  Chat20Regular,
  ArrowSync20Regular,
  Play20Regular,
} from "@fluentui/react-icons";
import { useJobStore, type Job, type JobEvent } from "@/stores/jobStore";
import { useWebSocket } from "@/hooks/useWebSocket";
import { useAutoSendBrief } from "@/hooks/useAutoSendBrief";
import { AGENT_META } from "@/api/types";
import { getSessionEvents } from "@/api/client";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { AgentIcon } from "@/components/common/AgentIcon";
import { clearInputNotification } from "@/utils/notifications";
import { useSettingsStore } from "@/stores/settingsStore";



import { formatElapsed } from "@/utils/formatElapsed";

/** Format tool args JSON into a short preview string. */
function argPreview(argsStr?: string): string {
  if (!argsStr || argsStr === "{}" || argsStr === "null") return "";
  try {
    const obj = typeof argsStr === "string" ? JSON.parse(argsStr) : argsStr;
    // For common tools, pick the most informative field
    const keys = Object.keys(obj);
    if (keys.length === 0) return "";
    // Build a compact summary: first string value, truncated
    for (const k of keys) {
      const v = obj[k];
      if (typeof v === "string" && v.length > 0) {
        const clean = v.replace(/\n/g, " ").trim();
        return clean.length > 60 ? clean.slice(0, 58) + "…" : clean;
      }
    }
    // Fallback: key names only
    return keys.slice(0, 3).join(", ");
  } catch {
    const clean = String(argsStr).replace(/\n/g, " ").trim();
    return clean.length > 60 ? clean.slice(0, 58) + "…" : clean;
  }
}

/** Pretty-print JSON args for the expanded view. */
function formatArgs(argsStr?: string): string {
  if (!argsStr || argsStr === "{}" || argsStr === "null") return "";
  try {
    const obj = typeof argsStr === "string" ? JSON.parse(argsStr) : argsStr;
    return JSON.stringify(obj, null, 2);
  } catch {
    return String(argsStr);
  }
}

interface EventDataMap {
  tool_started: { tool?: string; args?: string; _subagent?: string };
  tool_completed: { tool?: string; duration_ms?: number; output_preview?: string; _subagent?: string };
  subagent_started: { agent?: string };
  subagent_completed: { agent?: string };
  delta: { content?: string };
  new_files: { files?: string[] };
  done: { status?: string };
  error: { message?: string };
  waiting_for_input: { question?: string; choices?: string[] };
  user_response: { content?: string };
  input_timed_out: { question?: string };
  phase_changed: { phase?: string };
  user_followup: { content?: string };
  input_resolved: Record<string, never>;
  connection_error: { message?: string };
  assistant_message: { content?: string };
  subagent_failed: { agent?: string; error?: string };
}

function eventData<T extends keyof EventDataMap>(event: JobEvent, _type: T): EventDataMap[T] {
  return event.data as EventDataMap[T];
}

function fileIcon(ext: string | undefined) {
  switch (ext) {
    case "pptx": return <SlideText20Regular />;
    case "py": return <Code20Regular />;
    case "md": return <Document20Regular />;
    case "sh": return <Settings20Regular />;
    default: return <DocumentText20Regular />;
  }
}

/** Collapsible tool card: shows tool name + preview, expands to show args & output. */
function ToolCard({ event, completion }: { event: JobEvent; completion?: JobEvent }) {
  const [open, setOpen] = useState(false);
  const d = eventData(event, "tool_started");
  const cd = completion ? eventData(completion, "tool_completed") : undefined;

  const toolName = d.tool && d.tool !== "None" && d.tool !== "?" ? d.tool : null;
  if (!toolName) return null;

  const isComplete = !!completion;
  const durationMs = cd?.duration_ms;
  const preview = argPreview(d.args);
  const fullArgs = formatArgs(d.args);
  const output = cd?.output_preview;

  const hasDetails = !!(fullArgs || output);

  return (
    <div
      style={{
        borderRadius: 6,
        fontSize: 13,
        background: isComplete ? "#f0faf0" : "var(--hover-bg)",
        border: open ? "1px solid var(--border)" : "1px solid transparent",
        transition: "border 0.15s ease",
      }}
    >
      {/* Header row — always visible */}
      <div
        onClick={hasDetails ? () => setOpen(!open) : undefined}
        style={{
          padding: "7px 12px",
          display: "flex",
          alignItems: "center",
          gap: 6,
          cursor: hasDetails ? "pointer" : "default",
          userSelect: "none",
        }}
      >
        {hasDetails && (
          <span style={{ fontSize: 10, color: "var(--text-secondary)", flexShrink: 0, width: 12, display: "inline-flex" }}>
            {open ? <ChevronDown12Regular /> : <ChevronRight12Regular />}
          </span>
        )}
        <span style={{ flexShrink: 0, display: "inline-flex" }}>{isComplete ? <Checkmark20Regular /> : <Wrench20Regular />}</span>
        <strong style={{ flexShrink: 0 }}>{toolName}</strong>
        {durationMs != null && (
          <span style={{ color: "var(--text-secondary)", fontSize: 11, flexShrink: 0 }}>
            {durationMs}ms
          </span>
        )}
        {!open && preview && (
          <span
            style={{
              color: "var(--text-secondary)",
              fontSize: 11,
              marginLeft: 4,
              overflow: "hidden",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap",
              flex: 1,
              minWidth: 0,
            }}
          >
            {preview}
          </span>
        )}
      </div>

      {/* Expanded details */}
      {open && hasDetails && (
        <div style={{ padding: "0 12px 10px", paddingLeft: hasDetails ? 30 : 12 }}>
          {fullArgs && (
            <div style={{ marginBottom: output ? 8 : 0 }}>
              <div style={{ fontSize: 10, color: "var(--text-secondary)", marginBottom: 2, textTransform: "uppercase", letterSpacing: "0.04em" }}>
                Arguments
              </div>
              <pre
                style={{
                  margin: 0,
                  padding: "6px 10px",
                  background: "rgba(0,0,0,0.04)",
                  borderRadius: 4,
                  fontSize: 11,
                  lineHeight: 1.5,
                  overflowX: "auto",
                  maxHeight: 200,
                  whiteSpace: "pre-wrap",
                  wordBreak: "break-word",
                  fontFamily: "'Cascadia Code', 'Fira Code', monospace",
                }}
              >
                {fullArgs}
              </pre>
            </div>
          )}
          {output && (
            <div>
              <div style={{ fontSize: 10, color: "var(--text-secondary)", marginBottom: 2, textTransform: "uppercase", letterSpacing: "0.04em" }}>
                Output
              </div>
              <pre
                style={{
                  margin: 0,
                  padding: "6px 10px",
                  background: "rgba(0,0,0,0.04)",
                  borderRadius: 4,
                  fontSize: 11,
                  lineHeight: 1.5,
                  overflowX: "auto",
                  maxHeight: 200,
                  whiteSpace: "pre-wrap",
                  wordBreak: "break-word",
                  fontFamily: "'Cascadia Code', 'Fira Code', monospace",
                }}
              >
                {output}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

/** Collapsible warning/error row. Non-fatal errors are dimmed; click to expand the full message. */
function CollapsibleWarning({ message, subtle }: { message: string; subtle?: boolean }) {
  const [open, setOpen] = useState(false);
  const short = message.length > 80 ? message.slice(0, 78) + "…" : message;

  return (
    <div
      style={{
        padding: "6px 12px",
        background: subtle ? "transparent" : "#fff0f0",
        borderRadius: 6,
        fontSize: subtle ? 12 : 13,
        color: subtle ? "var(--text-secondary)" : "#d13438",
        cursor: message.length > 80 ? "pointer" : "default",
        border: subtle ? "1px dashed var(--border)" : "none",
      }}
      onClick={message.length > 80 ? () => setOpen(!open) : undefined}
    >
      <span style={{ marginRight: 6, display: "inline-flex" }}>{subtle ? <Flash20Regular /> : <Warning20Regular />}</span>
      {open ? message : short}
    </div>
  );
}

/** Collapsible group of events that occurred while a subagent was running. */
function SubagentGroup({
  agentName,
  events,
  completionMap,
  isComplete,
}: {
  agentName: string;
  events: JobEvent[];
  completionMap: Map<number, JobEvent>;
  isComplete: boolean;
}) {
  const [open, setOpen] = useState(true);
  const toolCount = events.filter((e) => e.type === "tool_started").length;

  // Filter out tool_completed events that are already merged into tool_started rows
  const mergedIds = new Set<number>();
  for (const e of events) {
    if (e.type === "tool_started") {
      const c = completionMap.get(e.id);
      if (c) mergedIds.add(c.id);
    }
  }
  const filteredEvents = events.filter((e) => !mergedIds.has(e.id));

  return (
    <div
      style={{
        borderRadius: 8,
        border: `1px solid ${isComplete ? "rgba(0,150,0,0.15)" : "rgba(0,120,212,0.2)"}`,
        overflow: "hidden",
      }}
    >
      {/* Header */}
      <div
        onClick={() => setOpen(!open)}
        style={{
          padding: "8px 12px",
          display: "flex",
          alignItems: "center",
          gap: 8,
          cursor: "pointer",
          userSelect: "none",
          background: isComplete ? "#f0faf0" : "#fff5e6",
        }}
      >
        <span style={{ fontSize: 10, color: "var(--text-secondary)", flexShrink: 0, width: 12, display: "inline-flex" }}>
          {open ? <ChevronDown12Regular /> : <ChevronRight12Regular />}
        </span>
        <span style={{ flexShrink: 0, display: "inline-flex" }}>
          {isComplete ? <Checkmark20Regular /> : <Bot20Regular />}
        </span>
        <strong style={{ fontSize: 13 }}>{agentName}</strong>
        {toolCount > 0 && (
          <span style={{ fontSize: 11, color: "var(--text-secondary)" }}>
            {toolCount} tool call{toolCount !== 1 ? "s" : ""}
          </span>
        )}
        {!isComplete && (
          <Spinner size="tiny" style={{ marginLeft: "auto" }} />
        )}
      </div>

      {/* Nested events */}
      {open && filteredEvents.length > 0 && (
        <div
          style={{
            padding: "6px 10px 8px 28px",
            display: "flex",
            flexDirection: "column",
            gap: 4,
            background: "rgba(0,0,0,0.015)",
          }}
        >
          {filteredEvents.map((e) => (
            <EventCard key={e.id} event={e} completion={completionMap.get(e.id)} />
          ))}
        </div>
      )}

      {/* Collapsed summary when no nested events */}
      {open && filteredEvents.length === 0 && !isComplete && (
        <div style={{ padding: "6px 12px 8px 28px", fontSize: 12, color: "var(--text-secondary)" }}>
          Running...
        </div>
      )}
    </div>
  );
}

function EventCard({ event, completion, userAnswer }: { event: JobEvent; completion?: JobEvent; userAnswer?: JobEvent }) {
  const t = event.type;
  const d = event.data as any;

  if (t === "tool_started" || (t === "tool_completed" && !completion)) {
    return <ToolCard event={event} completion={t === "tool_started" ? completion : undefined} />;
  }
  // tool_completed events that were already merged with a tool_started — skip
  if (t === "tool_completed") return null;

  if (t === "subagent_started") {
    return (
      <div style={{ padding: "8px 12px", background: "#fff5e6", borderRadius: 6, fontSize: 13 }}>
        <span style={{ marginRight: 6, display: "inline-flex" }}><Bot20Regular /></span>
        Subagent: <strong>{d.agent}</strong>
      </div>
    );
  }
  if (t === "subagent_completed") {
    return (
      <div style={{ padding: "8px 12px", background: "#f0faf0", borderRadius: 6, fontSize: 13 }}>
        <span style={{ marginRight: 6, display: "inline-flex" }}><Checkmark20Regular /></span>
        Subagent <strong>{d.agent}</strong> completed
      </div>
    );
  }
  if (t === "assistant_message") {
    const content = (d as EventDataMap["assistant_message"]).content || "";
    if (!content.trim()) return null;
    return (
      <div key={event.id} style={{ padding: "8px 12px" }}>
        <div className="md-content">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
        </div>
      </div>
    );
  }
  if (t === "subagent_failed") {
    const fd = d as EventDataMap["subagent_failed"];
    return (
      <div style={{
        padding: "6px 12px",
        borderRadius: 6,
        fontSize: 12,
        background: "var(--colorStatusDangerBackground1)",
        color: "var(--colorStatusDangerForeground1)",
      }}>
        <span style={{ marginRight: 6, display: "inline-flex" }}><Warning20Regular /></span>
        <strong>Subagent failed:</strong> {fd.agent || "unknown"} — {fd.error || "Unknown error"}
      </div>
    );
  }
  if (t === "delta" || t === "reasoning_delta") {
    return null; // Deltas are accumulated into blocks — see displayGroups
  }
  if (t === "phase_changed") {
    return (
      <div style={{ display: "flex", alignItems: "center", gap: 6, padding: "6px 12px" }}>
        <Badge appearance="tint" color="informative" size="small">
          {String(d.phase || "unknown")}
        </Badge>
      </div>
    );
  }
  if (t === "turn_started") {
    return (
      <div style={{ padding: "4px 12px", fontSize: 12, color: "var(--text-secondary)", display: "flex", alignItems: "center", gap: 6 }}>
        <Play20Regular style={{ width: 14, height: 14 }} /> Turn started
      </div>
    );
  }
  if (t === "turn_ended") {
    return (
      <div style={{ padding: "4px 12px", fontSize: 12, color: "var(--text-secondary)", display: "flex", alignItems: "center", gap: 6 }}>
        <CheckmarkCircle20Regular style={{ width: 14, height: 14 }} /> Turn ended
      </div>
    );
  }
  if (t === "usage") {
    return (
      <div style={{ padding: "4px 12px", fontSize: 12, color: "var(--text-secondary)", display: "flex", alignItems: "center", gap: 6 }}>
        <DataBarVertical20Regular style={{ width: 14, height: 14 }} />
        Tokens: {String(d.input_tokens || 0)} in / {String(d.output_tokens || 0)} out
        {d.cache_read_tokens ? ` / ${String(d.cache_read_tokens)} cached` : ""}
      </div>
    );
  }
  if (t === "assistant_intent") {
    return (
      <div style={{ padding: "6px 12px", fontSize: 12, color: "#8764b8", display: "flex", alignItems: "center", gap: 6 }}>
        <Flash20Regular style={{ width: 14, height: 14 }} />
        <span style={{ fontStyle: "italic" }}>Intent: {String(d.intent || d.content || "").slice(0, 120)}</span>
      </div>
    );
  }
  if (t === "assistant_reasoning") {
    return (
      <div style={{ padding: "6px 12px", fontSize: 12, color: "#888", fontStyle: "italic", fontFamily: "'Cascadia Code', 'Fira Code', monospace" }}>
        {String(d.content || d.reasoning || "").slice(0, 200)}
      </div>
    );
  }
  if (t === "compaction_start" || t === "compaction_complete") {
    return (
      <div style={{ padding: "4px 12px", fontSize: 12, color: "var(--text-secondary)", display: "flex", alignItems: "center", gap: 6 }}>
        <ArrowSync20Regular style={{ width: 14, height: 14 }} />
        Context compaction {t === "compaction_start" ? "started" : "complete"}
      </div>
    );
  }
  if (t === "session_handoff") {
    return (
      <div style={{ padding: "4px 12px", fontSize: 12, color: "#8764b8", display: "flex", alignItems: "center", gap: 6 }}>
        <ArrowSync20Regular style={{ width: 14, height: 14 }} />
        Session handoff{d.target ? `: ${String(d.target)}` : ""}
      </div>
    );
  }
  if (t === "subagent_selected" || t === "subagent_deselected") {
    return (
      <div style={{ padding: "4px 12px", fontSize: 12, color: "var(--text-secondary)", display: "flex", alignItems: "center", gap: 6 }}>
        <Bot20Regular style={{ width: 14, height: 14 }} />
        Subagent {t === "subagent_selected" ? "selected" : "deselected"}: {String(d.agent || "unknown")}
      </div>
    );
  }
  if (t === "input_resolved") {
    return (
      <div style={{ padding: "4px 12px", fontSize: 12, color: "var(--text-secondary)", display: "flex", alignItems: "center", gap: 6 }}>
        <CheckmarkCircle20Regular style={{ width: 14, height: 14 }} /> Input resolved
      </div>
    );
  }
  if (t === "new_files") {
    const files = ((d.files as string[]) || []).filter(
      (f) => !/\/generate_.*\.py$/.test(f)
    );
    if (files.length === 0) return null;
    return (
      <div
        style={{
          padding: "12px 16px",
          background: "linear-gradient(135deg, #e6f4ff 0%, #f0f8ff 100%)",
          borderRadius: 8,
          border: "1px solid rgba(0, 120, 212, 0.2)",
          fontSize: 13,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: files.length > 1 ? 8 : 0 }}>
          <span style={{ fontSize: 16, display: "inline-flex" }}><FolderOpen20Regular /></span>
          <strong style={{ fontSize: 13 }}>
            {files.length === 1 ? "File created" : `${files.length} files created`}
          </strong>
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
          {files.map((f: string) => {
            const name = f.split("/").pop() || f;
            const ext = name.includes(".") ? name.split(".").pop()?.toLowerCase() : "";
            return (
              <div
                key={f}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 8,
                  padding: "5px 10px",
                  background: "rgba(255,255,255,0.7)",
                  borderRadius: 6,
                  border: "1px solid rgba(0,0,0,0.06)",
                }}
              >
                <span style={{ flexShrink: 0, display: "inline-flex" }}>{fileIcon(ext)}</span>
                <span style={{ flex: 1, fontWeight: 500, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                  {name}
                </span>
                <button
                  onClick={() => {
                    const a = document.createElement("a");
                    a.href = `/file/download?path=${encodeURIComponent(f)}`;
                    a.download = name;
                    a.click();
                  }}
                  style={{
                    padding: "2px 8px",
                    fontSize: 11,
                    borderRadius: 4,
                    border: "1px solid var(--border)",
                    background: "white",
                    color: "var(--brand-primary)",
                    cursor: "pointer",
                    flexShrink: 0,
                    fontWeight: 500,
                  }}
                >
                  Download
                </button>
              </div>
            );
          })}
        </div>
      </div>
    );
  }
  if (t === "done") {
    return (
      <div style={{ padding: "10px 14px", background: "#e6ffe6", borderRadius: 8, fontSize: 14, fontWeight: 600 }}>
        <span style={{ marginRight: 6, display: "inline-flex" }}><CheckmarkCircle20Regular /></span>
        Job completed!
      </div>
    );
  }
  if (t === "error" || t === "connection_error") {
    const msg = d.message || "Unknown error";
    // SDK-internal errors that don't stop the job — show as subtle collapsible warnings
    const isNonFatal = t === "error" && (
      msg.includes("has no attribute") ||
      msg.includes("object is not") ||
      msg.includes("NoneType")
    );
    return (
      <CollapsibleWarning message={msg} subtle={isNonFatal} />
    );
  }
  if (t === "waiting_for_input") {
    const wasTimedOut = userAnswer?.type === "input_timed_out";
    const answered = !!userAnswer && !wasTimedOut;
    const answerText = answered ? eventData(userAnswer!, "user_response").content : undefined;
    const cardBg = wasTimedOut ? "#f5f5f5" : answered ? "#f5f5f5" : "#fff5e6";
    const cardOpacity = wasTimedOut || answered ? 0.85 : 1;
    return (
      <div style={{
        padding: "8px 12px",
        background: cardBg,
        borderRadius: 6,
        fontSize: 13,
        opacity: cardOpacity,
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 6 }}>
          <span style={{ display: "inline-flex" }}>
            {wasTimedOut ? <Warning20Regular /> : answered ? <Checkmark20Regular /> : <Pause20Regular />}
          </span>
          <strong>
            {wasTimedOut ? "Skipped (no response)" : answered ? "Question answered" : "Waiting for input"}
          </strong>
        </div>
        <div className="md-content" style={{ fontSize: 13 }}>
          <ReactMarkdown remarkPlugins={[remarkGfm]}>
            {String(d.question || "The agent has a question")}
          </ReactMarkdown>
        </div>
        {answered && answerText && (
          <div style={{
            marginTop: 8,
            padding: "6px 10px",
            background: "rgba(0, 120, 212, 0.06)",
            borderRadius: 6,
            borderLeft: "3px solid var(--brand-primary)",
            fontSize: 12,
            color: "var(--text-primary)",
          }}>
            <strong style={{ fontSize: 10, color: "var(--text-secondary)", textTransform: "uppercase", letterSpacing: "0.04em", display: "block", marginBottom: 2 }}>Your answer</strong>
            {answerText}
          </div>
        )}
      </div>
    );
  }
  // user_response / input_timed_out events that were merged into a waiting_for_input — skip
  if (t === "user_response" || t === "input_timed_out") return null;
  // input_resolved is handled by the store — no UI needed
  if (t === "input_resolved") return null;
  // Follow-up messages from the user
  if (t === "user_followup") {
    return (
      <div style={{
        padding: "8px 12px",
        background: "rgba(0, 120, 212, 0.06)",
        borderRadius: 6,
        borderLeft: "3px solid var(--brand-primary)",
        fontSize: 13,
      }}>
        <strong style={{ fontSize: 10, color: "var(--text-secondary)", textTransform: "uppercase", letterSpacing: "0.04em", display: "block", marginBottom: 2 }}>You</strong>
        {String(d.content || "")}
      </div>
    );
  }
  // Catch-all for unknown event types — show them so nothing is silently lost
  return (
    <div style={{ padding: "6px 12px", borderRadius: 6, fontSize: 12, color: "var(--text-secondary)" }}>
      <span style={{ fontFamily: "monospace", marginRight: 6 }}>{t}</span>
      {d.tool && <span>{String(d.tool)}</span>}
      {d.agent && <span>{String(d.agent)}</span>}
      {d.content && typeof d.content === "string" && <span>{d.content.slice(0, 80)}</span>}
    </div>
  );
}

export function AgentWorkspace() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const jobId = params.get("id") || "";
  const job = useJobStore((s) => s.getJob(jobId));
  const pushEvent = useJobStore((s) => s.pushEvent);
  const updateJob = useJobStore((s) => s.updateJob);
  const { sendMessage, sendUserResponse, cancel } = useWebSocket(jobId || null);
  useAutoSendBrief(jobId || null, sendMessage);
  const verboseMode = useSettingsStore((s) => s.verboseMode);
  const setVerboseMode = useSettingsStore((s) => s.setVerboseMode);
  const [editedPlan, setEditedPlan] = useState("");
  const [elapsed, setElapsed] = useState(0);
  const [followUp, setFollowUp] = useState("");
  // Guard: disable response buttons immediately after a send to prevent double-clicks
  const [respondedToCurrentQ, setRespondedToCurrentQ] = useState(false);
  // Retry state: becomes true after 15s without input_resolved from backend
  const [retryAvailable, setRetryAvailable] = useState(false);

  // Reset the responded flag whenever a genuinely new (non-submitted) question arrives
  useEffect(() => {
    const input = job?.pendingInput?.[0];
    if (input?.question && !input.submitted) {
      setRespondedToCurrentQ(false);
      setRetryAvailable(false);
    }
  }, [job?.pendingInput?.[0]?.question, job?.pendingInput?.[0]?.submitted]);

  // Retry timeout: 15s after submission with no input_resolved, allow retry
  useEffect(() => {
    const input = job?.pendingInput?.[0];
    if (!input?.submitted || !input.submittedAt) {
      setRetryAvailable(false);
      return;
    }
    const elapsed = Date.now() - input.submittedAt;
    const remaining = Math.max(0, 15_000 - elapsed);
    const timer = setTimeout(() => setRetryAvailable(true), remaining);
    return () => clearTimeout(timer);
  }, [job?.pendingInput?.[0]?.submitted, job?.pendingInput?.[0]?.submittedAt]);

  const guardedSendResponse = useCallback(
    (content: string, origin: "explicit" | "choice" | "skip" = "explicit") => {
      if (respondedToCurrentQ) return;
      setRespondedToCurrentQ(true);
      setRetryAvailable(false);
      sendUserResponse(content, origin);
    },
    [respondedToCurrentQ, sendUserResponse],
  );

  const retryLastResponse = useCallback(() => {
    if (!jobId) return;
    const currentJob = useJobStore.getState().getJob(jobId);
    const input = currentJob?.pendingInput?.[0];
    if (!input?.submitted) return;
    // Reset submission state so the card reverts to interactive
    const queue = currentJob?.pendingInput || [];
    const reset = [{ question: input.question, choices: input.choices }, ...queue.slice(1)];
    useJobStore.getState().updateJob(jobId, { pendingInput: reset });
    setRespondedToCurrentQ(false);
    setRetryAvailable(false);
  }, [jobId]);

  useEffect(() => {
    if (job?.pendingInput?.[0]?.question) {
      setEditedPlan("");
    }
  }, [job?.pendingInput?.[0]?.question]);

  // Elapsed time ticker
  useEffect(() => {
    if (!job || job.status === "completed" || job.status === "failed" || job.status === "cancelled") return;
    const interval = setInterval(() => {
      setElapsed(Date.now() - (job?.startedAt || Date.now()));
    }, 1000);
    return () => clearInterval(interval);
  }, [job?.id, job?.status, job?.startedAt]);

  // Hydrate events for terminal sessions that have few/no captured events
  const hydratedRef = useRef<string | null>(null);
  useEffect(() => {
    if (!job || hydratedRef.current === jobId) return;
    const isTerminal =
      job.status === "completed" || job.status === "failed" || job.status === "cancelled";
    if (!isTerminal || job.events.length >= 5) return;

    hydratedRef.current = jobId;
    getSessionEvents(jobId)
      .then((serverEvents) => {
        const currentJob = useJobStore.getState().getJob(jobId);
        if (!currentJob) return;
        const existingTimes = new Set(currentJob.events.map((e) => e.time));
        // Track which event types we already have to prevent duplicating
        // one-shot events like "done" (client timestamps differ from server).
        const hasDone = currentJob.events.some((e) => e.type === "done");
        const hydratedFiles: string[] = [];
        for (const se of serverEvents) {
          if ((se.type === "done" || se.type === "cancelled") && hasDone) continue;
          const ts = new Date(se.time).getTime();
          if (!existingTimes.has(ts)) {
            pushEvent(jobId, { type: se.type, data: se.data });
          }
          // Collect output files from new_files events regardless of dedup
          if (se.type === "new_files" && se.data?.files) {
            hydratedFiles.push(...(se.data.files as string[]));
          }
        }
        // Restore outputFiles on the job if server has files we don't
        if (hydratedFiles.length > 0) {
          const freshJob = useJobStore.getState().getJob(jobId);
          if (freshJob) {
            const existing = new Set(freshJob.outputFiles);
            const newFiles = hydratedFiles.filter((f) => !existing.has(f));
            if (newFiles.length > 0) {
              updateJob(jobId, {
                outputFiles: [...freshJob.outputFiles, ...newFiles],
              });
            }
          }
        }
      })
      .catch(() => { /* server unreachable — skip hydration */ });
  }, [job?.status, job?.events.length, jobId, pushEvent]);

  // Collect accumulated delta text for the plan review
  const deltaText = useMemo(() => {
    if (!job) return "";
    return job.events
      .filter((e) => e.type === "delta")
      .map((e) => eventData(e, "delta").content || "")
      .join("");
  }, [job?.events.length]);

  // Ref for auto-scroll (initialized here so hooks are unconditional)
  const feedRef = useRef<HTMLDivElement>(null);
  const userScrolledUp = useRef(false);

  if (!job) {
    return (
      <div style={{ padding: 48, textAlign: "center" }}>
        <Text size={500}>Job not found</Text>
        <br />
        <Button appearance="subtle" onClick={() => navigate("/")}>
          Back to Launchpad
        </Button>
      </div>
    );
  }

  const meta = AGENT_META[job.agent] || { icon: "", label: job.agent, color: "#0078D4" };

  // Filter events for the activity feed, respecting verbose mode setting.
  // When verbose is ON, include detailed events like deltas, usage, phase changes, etc.
  // When verbose is OFF, only show high-level meaningful events.
  const feedEvents = useMemo(() => {
    const isAskUserTool = (e: JobEvent) =>
      (e.type === "tool_started" || e.type === "tool_completed") &&
      String((e.data as any).tool || "").toLowerCase() === "ask_user";

    // Events that are always noise — never shown
    const alwaysSkip = new Set([
      "pong", "heartbeat", "session_snapshot", "session_state_changed",
    ]);

    // Events only shown when verbose mode is enabled
    const verboseOnly = new Set([
      "delta", "reasoning_delta", "usage", "phase_changed",
      "turn_started", "turn_ended", "input_resolved",
      "assistant_intent", "assistant_reasoning",
      "compaction_start", "compaction_complete",
      "session_handoff", "subagent_selected", "subagent_deselected",
    ]);

    const base = job.events.filter((e) => {
      if (alwaysSkip.has(e.type)) return false;
      if (isAskUserTool(e)) return false;
      if (!verboseMode && verboseOnly.has(e.type)) return false;
      return true;
    });

    // Deduplicate waiting_for_input: if multiple appear in a row (or near
    // each other) for the same question, keep only the one with real text.
    const seenQuestions = new Set<string>();
    return base.filter((e) => {
      if (e.type !== "waiting_for_input") {
        // Reset seen questions when a non-waiting event occurs (new turn cycle)
        if (e.type === "user_response" || e.type === "done") seenQuestions.clear();
        return true;
      }
      const q = String((e.data as any).question || "");
      // Skip generic fallback entries if we already have a real question
      if (!q || q === "The agent has a question") {
        return seenQuestions.size === 0; // only show if no real question exists
      }
      if (seenQuestions.has(q)) return false;
      seenQuestions.add(q);
      return true;
    });
  }, [job.events.length, verboseMode]);

  // Build a map from tool_started events to their matching tool_completed events.
  // We match by tool name, pairing the most recent unmatched start with its completion.
  const completionMap = useMemo(() => {
    const map = new Map<number, JobEvent>(); // tool_started event id → tool_completed event
    const pending: { id: number; tool: string }[] = [];
    for (const e of feedEvents) {
      const d = e.data as any;
      if (e.type === "tool_started" && d.tool) {
        pending.push({ id: e.id, tool: String(d.tool) });
      } else if (e.type === "tool_completed" && d.tool) {
        // Find the last unmatched start for this tool
        for (let i = pending.length - 1; i >= 0; i--) {
          if (pending[i].tool === String(d.tool)) {
            map.set(pending[i].id, e);
            pending.splice(i, 1);
            break;
          }
        }
      }
    }
    return map;
  }, [feedEvents.length]);

  // Filter out tool_completed events that are already merged into a tool_started row.
  const mergedCompletionIds = useMemo(() => {
    const ids = new Set<number>();
    for (const ce of completionMap.values()) ids.add(ce.id);
    return ids;
  }, [completionMap]);

  // Build a map from waiting_for_input events to their matching user_response or input_timed_out events.
  const answerMap = useMemo(() => {
    const map = new Map<number, JobEvent>(); // waiting_for_input event id → user_response/input_timed_out event
    let pendingWaiting: number | null = null;
    for (const e of feedEvents) {
      if (e.type === "waiting_for_input") {
        pendingWaiting = e.id;
      } else if ((e.type === "user_response" || e.type === "input_timed_out") && pendingWaiting !== null) {
        map.set(pendingWaiting, e);
        pendingWaiting = null;
      }
    }
    return map;
  }, [feedEvents.length]);

  // IDs of user_response / input_timed_out events already merged into waiting_for_input cards
  const mergedAnswerIds = useMemo(() => {
    const ids = new Set<number>();
    for (const ae of answerMap.values()) ids.add(ae.id);
    return ids;
  }, [answerMap]);

  const displayEvents = feedEvents.filter(
    (e) => !mergedCompletionIds.has(e.id) && !mergedAnswerIds.has(e.id),
  );

  // Build display groups: standalone events + subagent groups with nested tool calls.
  // A SubagentGroup spans from subagent_started to subagent_completed, collecting
  // any tool_started/tool_completed events with a matching _subagent tag.
  // In verbose mode, consecutive delta/reasoning_delta events are accumulated into text blocks.
  type DisplayItem =
    | { kind: "event"; event: JobEvent }
    | { kind: "subagent"; name: string; events: JobEvent[]; isComplete: boolean; id: number }
    | { kind: "delta-block"; text: string; blockKind: "delta" | "reasoning"; startTime: number; endTime: number; id: number };

  const displayGroups = useMemo<DisplayItem[]>(() => {
    const result: DisplayItem[] = [];
    // Track active subagent groups by name (stack for nested subagents)
    const activeGroups = new Map<string, { events: JobEvent[]; id: number }>();

    for (const e of displayEvents) {
      const d = e.data as any;

      if (e.type === "subagent_started") {
        activeGroups.set(d.agent || "agent", { events: [], id: e.id });
        continue; // don't render standalone — will be the group header
      }

      if (e.type === "subagent_completed") {
        const name = d.agent || "agent";
        const group = activeGroups.get(name);
        if (group) {
          result.push({ kind: "subagent", name, events: group.events, isComplete: true, id: group.id });
          activeGroups.delete(name);
        } else {
          // Orphan completed event (missed the start) — show inline
          result.push({ kind: "event", event: e });
        }
        continue;
      }

      // Check if this event belongs to an active subagent
      const subagentTag = d._subagent as string | undefined;
      if (subagentTag && activeGroups.has(subagentTag)) {
        activeGroups.get(subagentTag)!.events.push(e);
        continue;
      }

      // Standalone event
      result.push({ kind: "event", event: e });
    }

    // Flush any still-active subagent groups.
    // If the job is in a terminal state, all subagents must have finished.
    const jobIsDone = job.status === "completed" || job.status === "failed" || job.status === "cancelled";
    for (const [name, group] of activeGroups) {
      result.push({ kind: "subagent", name, events: group.events, isComplete: jobIsDone, id: group.id });
    }

    // In verbose mode, accumulate consecutive standalone delta/reasoning_delta events into text blocks
    if (verboseMode) {
      const accumulated: DisplayItem[] = [];
      let currentBlock: { text: string; blockKind: "delta" | "reasoning"; startTime: number; endTime: number; id: number } | null = null;

      for (const item of result) {
        if (item.kind === "event" && (item.event.type === "delta" || item.event.type === "reasoning_delta")) {
          const content = String((item.event.data as any).content || "");
          if (!content) continue;
          const bk = item.event.type === "reasoning_delta" ? "reasoning" as const : "delta" as const;
          if (currentBlock && currentBlock.blockKind === bk) {
            currentBlock.text += content;
            currentBlock.endTime = item.event.time;
          } else {
            if (currentBlock) accumulated.push({ kind: "delta-block", ...currentBlock });
            currentBlock = { text: content, blockKind: bk, startTime: item.event.time, endTime: item.event.time, id: item.event.id };
          }
        } else {
          if (currentBlock) {
            accumulated.push({ kind: "delta-block", ...currentBlock });
            currentBlock = null;
          }
          accumulated.push(item);
        }
      }
      if (currentBlock) accumulated.push({ kind: "delta-block", ...currentBlock });
      return accumulated;
    }

    return result;
  }, [displayEvents.length, job.status, verboseMode]);

  // Auto-scroll the activity feed to the bottom when new events arrive
  useEffect(() => {
    const el = feedRef.current;
    if (!el) return;
    const onScroll = () => {
      userScrolledUp.current = el.scrollHeight - el.scrollTop - el.clientHeight > 80;
    };
    el.addEventListener("scroll", onScroll, { passive: true });
    return () => el.removeEventListener("scroll", onScroll);
  }, []);

  useEffect(() => {
    const el = feedRef.current;
    if (!el || userScrolledUp.current) return;
    el.scrollTop = el.scrollHeight;
  }, [displayGroups.length]);

  return (
    <div style={{ display: "flex", height: "100vh", overflow: "hidden" }}>
      {/* Activity Feed */}
      <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>
        {/* Header */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            padding: "14px 24px",
            borderBottom: "1px solid var(--border)",
            background: "var(--card-bg)",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 10, minWidth: 0, flex: 1 }}>
            <Button
              appearance="subtle"
              icon={<ArrowLeft20Regular />}
              size="small"
              onClick={() => navigate("/mission")}
              style={{ flexShrink: 0 }}
            />
            <AgentIcon agent={job.agent} size="inline" />
            <Text
              weight="semibold"
              size={400}
              style={{
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "nowrap",
                minWidth: 0,
              }}
            >
              {job.title}
            </Text>
            <span
              style={{
                flexShrink: 0,
                padding: "3px 10px",
                borderRadius: 6,
                fontSize: 11,
                fontWeight: 600,
                letterSpacing: "0.02em",
                textTransform: "uppercase",
                color: "white",
                background:
                  job.status === "completed"
                    ? "#7FBA00"
                    : job.status === "failed"
                      ? "#d13438"
                      : job.status === "waiting"
                        ? "#d48806"
                        : "var(--brand-primary)",
              }}
            >
              {job.status}
            </span>
          </div>
          {(job.status === "running" || job.status === "queued" || job.status === "waiting") && (
            <Button
              appearance="subtle"
              icon={<Dismiss20Regular />}
              onClick={() => {
                cancel();
                clearInputNotification();
                useJobStore.getState().updateJob(jobId, {
                  status: "cancelled",
                  phase: "done",
                  completedAt: Date.now(),
                  pendingInput: [],
                });
              }}
              style={{ color: "#d13438" }}
            >
              Cancel
            </Button>
          )}
        </div>

        {/* Stats bar */}
        <div
          className="stats-bar"
          style={{
            display: "flex",
            alignItems: "center",
            gap: 16,
            padding: "6px 24px",
            borderBottom: "1px solid var(--border)",
            background: "var(--card-bg)",
          }}
        >
          <Text size={200} style={{ display: "flex", alignItems: "center", gap: 4, color: "var(--text-secondary)" }}>
            <Wrench20Regular style={{ width: 14, height: 14 }} /> {job.progress.toolCalls} tool calls
          </Text>
          <Text size={200} style={{ display: "flex", alignItems: "center", gap: 4, color: "var(--text-secondary)" }}>
            <Bot20Regular style={{ width: 14, height: 14 }} /> {job.progress.subagentRuns} subagents
          </Text>
          <Text size={200} style={{ display: "flex", alignItems: "center", gap: 4, color: "var(--text-secondary)" }}>
            <DataBarVertical20Regular style={{ width: 14, height: 14 }} /> {((job.usage.inputTokens + job.usage.outputTokens) / 1000).toFixed(0)}k tokens
          </Text>
          <Text size={200} style={{ display: "flex", alignItems: "center", gap: 4, color: "var(--text-secondary)" }}>
            <Timer20Regular style={{ width: 14, height: 14 }} /> {formatElapsed(job.completedAt ? job.completedAt - job.startedAt : elapsed)}
          </Text>
          <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 6 }}>
            <Text size={200} style={{ color: "var(--text-secondary)" }}>Verbose</Text>
            <Switch
              checked={verboseMode}
              onChange={(_, d) => setVerboseMode(d.checked as boolean)}
              style={{ margin: 0 }}
            />
          </div>
        </div>

        {/* Activity feed */}
        <div
          ref={feedRef}
          style={{ flex: 1, overflow: "auto", padding: "16px 24px" }}
        >
          {job.status === "queued" && (
            <div style={{ textAlign: "center", padding: 40 }}>
              <Spinner label="Connecting..." />
            </div>
          )}

          {job.status === "running" && job.events.length === 0 && (
            <div style={{ textAlign: "center", padding: 40 }}>
              <Spinner label="Starting agent..." size="large" />
            </div>
          )}

          {job.status === "running" && job.events.length > 0 && feedEvents.length === 0 && (
            <div style={{ textAlign: "center", padding: 20, color: "var(--text-secondary)", fontSize: 13 }}>
              Agent is working... ({job.events.length} events received, {job.progress.toolCalls} tool calls)
            </div>
          )}

          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            {displayGroups.map((item) =>
              item.kind === "subagent" ? (
                <SubagentGroup
                  key={`sa-${item.id}`}
                  agentName={item.name}
                  events={item.events}
                  completionMap={completionMap}
                  isComplete={item.isComplete}
                />
              ) : item.kind === "delta-block" ? (
                <div
                  key={`db-${item.id}`}
                  style={{
                    padding: "8px 12px",
                    borderRadius: 6,
                    fontSize: 13,
                    lineHeight: 1.6,
                    maxHeight: 200,
                    overflow: "auto",
                    whiteSpace: "pre-wrap",
                    wordBreak: "break-word",
                    ...(item.blockKind === "reasoning"
                      ? {
                          fontStyle: "italic",
                          color: "#888",
                          fontFamily: "'Cascadia Code', 'Fira Code', monospace",
                          background: "rgba(0,0,0,0.03)",
                        }
                      : {
                          color: "var(--text-primary)",
                          background: "rgba(0, 120, 212, 0.04)",
                        }),
                  }}
                >
                  {item.text}
                </div>
              ) : (
                <EventCard
                  key={item.event.id}
                  event={item.event}
                  completion={completionMap.get(item.event.id)}
                  userAnswer={answerMap.get(item.event.id)}
                />
              ),
            )}
          </div>

          {/* Completion actions */}
          {job.status === "completed" && job.outputFiles.length > 0 && (
            <Card
              style={{
                marginTop: 16,
                border: "1px solid #7FBA00",
                borderRadius: 10,
                padding: "20px 24px",
                background: "#f0fff0",
              }}
            >
              <Text weight="semibold" size={400} style={{ display: "block", marginBottom: 12 }}>
                🎉 Your content is ready!
              </Text>
              <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                <Button
                  appearance="primary"
                  onClick={() => navigate("/library")}
                >
                  View in Library
                </Button>
                {job.outputFiles
                  .filter((f) => !/\/generate_.*\.py$/.test(f))
                  .map((f) => (
                  <Button
                    key={f}
                    appearance="outline"
                    icon={<ArrowDownload20Regular />}
                    onClick={() => {
                      const a = document.createElement("a");
                      a.href = `/file/download?path=${encodeURIComponent(f)}`;
                      a.download = f.split("/").pop() || "download";
                      a.click();
                    }}
                  >
                    {f.split("/").pop()}
                  </Button>
                ))}
              </div>
            </Card>
          )}
        </div>

        {/* Bottom bar — question input / follow-up input */}
        <div
          style={{
            padding: "10px 24px",
            borderTop: "1px solid var(--border)",
            background: "var(--card-bg)",
            display: "flex",
            flexDirection: "column",
            gap: 8,
          }}
        >
          {/* Plan Review / Question Gate — pinned at bottom so it's always visible */}
          {job.status === "waiting" && job.pendingInput?.[0] && (() => {
            const currentInput = job.pendingInput![0];
            const queueLength = job.pendingInput!.length;
            const isPlanReview = deltaText.length > 50;
            const hasChoices = !!(currentInput.choices && currentInput.choices.length > 0);
            const isSubmitted = !!currentInput.submitted;
            return (
            <Card
              style={{
                border: `2px solid ${isSubmitted ? "#8a8886" : isPlanReview ? "#FFB900" : "#0078D4"}`,
                borderRadius: 10,
                padding: "16px 20px",
                background: isSubmitted ? "#f5f5f5" : isPlanReview ? "#fffbf0" : "#f0f6ff",
                opacity: isSubmitted && !retryAvailable ? 0.8 : 1,
                transition: "opacity 0.3s",
              }}
            >
              {isSubmitted && (
                <div style={{
                  display: "flex", alignItems: "center", gap: 8,
                  padding: "8px 12px", marginBottom: 12, borderRadius: 6,
                  background: retryAvailable ? "#fff4ce" : "#e8f5e9",
                  border: `1px solid ${retryAvailable ? "#f0c800" : "#a5d6a7"}`,
                  fontSize: 13,
                }}>
                  {retryAvailable ? (
                    <>
                      <Warning20Regular style={{ color: "#c87400" }} />
                      <span style={{ flex: 1, color: "#6b5900" }}>Response may not have reached the server.</span>
                      <Button
                        appearance="outline"
                        size="small"
                        icon={<ArrowSync20Regular />}
                        onClick={retryLastResponse}
                      >
                        Retry
                      </Button>
                    </>
                  ) : (
                    <>
                      <Spinner size="tiny" />
                      <span style={{ color: "#4a7c59" }}>Response sent — waiting for confirmation...</span>
                    </>
                  )}
                </div>
              )}

              {!isSubmitted && deltaText.trim() && (
                <div
                  className="md-content"
                  style={{
                    padding: "10px 14px",
                    background: "var(--card-bg)",
                    border: "1px solid var(--border)",
                    borderRadius: 8,
                    maxHeight: 200,
                    overflow: "auto",
                    marginBottom: 12,
                    fontSize: 13,
                  }}
                >
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>
                    {deltaText}
                  </ReactMarkdown>
                </div>
              )}

              <div style={{ display: "flex", gap: 10, alignItems: "flex-start", marginBottom: 10 }}>
                <span style={{ fontSize: 18, lineHeight: 1.6, display: "inline-flex" }}>{isPlanReview ? <ClipboardTask20Regular /> : <Chat20Regular />}</span>
                <div className="md-content" style={{ flex: 1, fontSize: 14, fontWeight: 600, maxHeight: 150, overflowY: "auto" }}>
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>
                    {currentInput.question}
                  </ReactMarkdown>
                </div>
                {queueLength > 1 && (
                  <span style={{ fontSize: 11, color: "var(--text-secondary)", whiteSpace: "nowrap", marginTop: 4 }}>
                    +{queueLength - 1} more
                  </span>
                )}
              </div>

              {!isSubmitted && hasChoices && (
                <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 12 }}>
                  {currentInput.choices!.map((choice, i) => (
                    <Button
                      key={i}
                      appearance="outline"
                      disabled={respondedToCurrentQ}
                      onClick={() => guardedSendResponse(choice, "choice")}
                      style={{ fontSize: 13 }}
                    >
                      {choice}
                    </Button>
                  ))}
                </div>
              )}

              {!isSubmitted && (
                <Textarea
                  id="plan-edit"
                  value={editedPlan}
                  onChange={(_, data) => setEditedPlan(data.value)}
                  placeholder={isPlanReview
                    ? "Optional: add clarifications or edits before approving"
                    : "Type your answer..."
                  }
                  resize="vertical"
                  rows={isPlanReview ? 3 : 2}
                  style={{ marginBottom: 12 }}
                />
              )}

              {!isSubmitted && (
              <div style={{ display: "flex", gap: 10 }}>
                {isPlanReview ? (
                  <>
                    <Button
                      appearance="primary"
                      icon={<Checkmark20Regular />}
                      disabled={respondedToCurrentQ}
                      onClick={() => guardedSendResponse(editedPlan.trim() || "Looks good, proceed with building.")}
                    >
                      Approve
                    </Button>
                    <Button
                      appearance="outline"
                      disabled={respondedToCurrentQ || !editedPlan.trim()}
                      onClick={() => guardedSendResponse(editedPlan.trim())}
                    >
                      Edit & Approve
                    </Button>
                    <Button
                      appearance="subtle"
                      disabled={respondedToCurrentQ}
                      onClick={() => guardedSendResponse("Reject this plan. Cancel the job.")}
                      style={{ color: "#d13438" }}
                    >
                      Reject
                    </Button>
                  </>
                ) : (
                  <>
                    <Button
                      appearance="primary"
                      icon={<Send20Regular />}
                      disabled={respondedToCurrentQ || (!editedPlan.trim() && !hasChoices)}
                      onClick={() => {
                        if (editedPlan.trim()) {
                          guardedSendResponse(editedPlan.trim());
                        }
                      }}
                    >
                      Reply
                    </Button>
                    <Button
                      appearance="subtle"
                      disabled={respondedToCurrentQ}
                      onClick={() => guardedSendResponse("Skip this question and decide for me.", "skip")}
                    >
                      Skip
                    </Button>
                  </>
                )}
              </div>
              )}
            </Card>
            );
          })()}

        </div>
      </div>
    </div>
  );
}
