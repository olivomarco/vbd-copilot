import { useEffect, useRef, useState, useMemo } from "react";
import {
  Text,
  Badge,
  Spinner,
} from "@fluentui/react-components";
import {
  ChevronDown12Regular,
  ChevronRight12Regular,
  Wrench20Regular,
  Warning20Regular,
  Bot20Regular,
  CheckmarkCircle20Regular,
  Pause20Regular,
  FolderOpen20Regular,
  ArrowSync20Regular,
  Dismiss20Regular,
  Flash20Regular,
  DataBarVertical20Regular,
  Play20Regular,
} from "@fluentui/react-icons";
import type { JobEvent } from "@/stores/jobStore";
import { useSettingsStore } from "@/stores/settingsStore";

const MAX_VISIBLE_EVENTS = 200;

/* ------------------------------------------------------------------ */
/* Helpers                                                             */
/* ------------------------------------------------------------------ */

function relativeTime(ts: number): string {
  const diff = Math.max(0, Math.floor((Date.now() - ts) / 1000));
  if (diff < 5) return "now";
  if (diff < 60) return `${diff}s ago`;
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  return `${Math.floor(diff / 3600)}h ago`;
}

/** Classify an event for rendering purposes. */
type EventCategory = "always" | "verbose" | "skip";

function categorize(type: string): EventCategory {
  switch (type) {
    // Always shown
    case "phase_changed":
    case "subagent_started":
    case "subagent_completed":
    case "subagent_failed":
    case "waiting_for_input":
    case "done":
    case "cancelled":
    case "error":
    case "connection_error":
    case "new_files":
    case "input_resolved":
      return "always";

    // Verbose only
    case "delta":
    case "reasoning_delta":
    case "tool_started":
    case "tool_completed":
    case "tool_partial_result":
    case "tool_progress":
    case "assistant_intent":
    case "assistant_reasoning":
    case "assistant_message":
    case "session_handoff":
    case "compaction_start":
    case "compaction_complete":
    case "turn_started":
    case "turn_ended":
    case "subagent_deselected":
    case "subagent_selected":
    case "usage":
      return "verbose";

    // Skip
    case "user_response":
    case "input_timed_out":
    case "user_followup":
    case "pong":
    case "heartbeat":
    case "session_snapshot":
    case "session_state_changed":
      return "skip";

    default:
      return "verbose";
  }
}

/* ------------------------------------------------------------------ */
/* Compact event renderers                                             */
/* ------------------------------------------------------------------ */

function PhaseEvent({ data }: { data: Record<string, unknown> }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
      <Badge appearance="tint" color="informative" size="small">
        {String(data.phase || "unknown")}
      </Badge>
    </div>
  );
}

function SubagentEvent({ type, data }: { type: string; data: Record<string, unknown> }) {
  const name = String(data.agent || "agent");
  if (type === "subagent_started") {
    return (
      <span style={{ display: "flex", alignItems: "center", gap: 4 }}>
        <Bot20Regular style={{ fontSize: 14 }} />
        <span>Subagent <strong>{name}</strong> started</span>
      </span>
    );
  }
  if (type === "subagent_completed") {
    return (
      <span style={{ display: "flex", alignItems: "center", gap: 4 }}>
        <CheckmarkCircle20Regular style={{ fontSize: 14, color: "#107c10" }} />
        <span>Subagent <strong>{name}</strong> completed</span>
      </span>
    );
  }
  // subagent_failed
  return (
    <span style={{ display: "flex", alignItems: "center", gap: 4, color: "#d13438" }}>
      <Warning20Regular style={{ fontSize: 14 }} />
      <span>Subagent <strong>{name}</strong> failed{data.error ? `: ${String(data.error).slice(0, 60)}` : ""}</span>
    </span>
  );
}

function WaitingEvent({ data }: { data: Record<string, unknown> }) {
  const q = String(data.question || "The agent has a question");
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 6,
        padding: "4px 8px",
        background: "#fff8e1",
        borderRadius: 4,
        border: "1px solid #ffe082",
      }}
    >
      <Pause20Regular style={{ fontSize: 14, color: "#d48806", flexShrink: 0 }} />
      <span style={{ fontWeight: 600, color: "#b8860b" }}>
        {q.length > 80 ? q.slice(0, 78) + "\u2026" : q}
      </span>
    </div>
  );
}

function ToolEvent({ type, data }: { type: string; data: Record<string, unknown> }) {
  const [expanded, setExpanded] = useState(false);
  const toolName = String(data.tool || "tool");
  const isComplete = type === "tool_completed";
  const duration = data.duration_ms != null ? `${data.duration_ms}ms` : null;

  const argsStr = data.args ? String(data.args) : "";
  const outputStr = data.output_preview ? String(data.output_preview) : "";
  const hasDetails = argsStr.length > 2 || outputStr.length > 0;

  return (
    <div style={{ borderRadius: 4 }}>
      <div
        onClick={hasDetails ? () => setExpanded(!expanded) : undefined}
        style={{
          display: "flex",
          alignItems: "center",
          gap: 6,
          cursor: hasDetails ? "pointer" : "default",
          userSelect: "none",
        }}
      >
        {hasDetails && (
          <span style={{ fontSize: 10, color: "var(--text-secondary)", width: 12, display: "inline-flex" }}>
            {expanded ? <ChevronDown12Regular /> : <ChevronRight12Regular />}
          </span>
        )}
        <Wrench20Regular style={{ fontSize: 14, color: "#0078d4", flexShrink: 0 }} />
        <strong style={{ color: "#0078d4" }}>{toolName}</strong>
        {isComplete && <CheckmarkCircle20Regular style={{ fontSize: 12, color: "#107c10" }} />}
        {duration && (
          <span style={{ fontSize: 11, color: "var(--text-secondary)" }}>{duration}</span>
        )}
      </div>
      {expanded && hasDetails && (
        <div style={{ marginTop: 4, marginLeft: 32 }}>
          {argsStr.length > 2 && (
            <pre
              style={{
                margin: 0,
                padding: "4px 8px",
                background: "rgba(0,0,0,0.04)",
                borderRadius: 4,
                fontSize: 10,
                lineHeight: 1.4,
                overflowX: "auto",
                maxHeight: 120,
                whiteSpace: "pre-wrap",
                wordBreak: "break-word",
                fontFamily: "'Cascadia Code', 'Fira Code', monospace",
              }}
            >
              {(() => {
                try {
                  const obj = typeof argsStr === "string" ? JSON.parse(argsStr) : argsStr;
                  return JSON.stringify(obj, null, 2);
                } catch {
                  return argsStr;
                }
              })()}
            </pre>
          )}
          {outputStr && (
            <pre
              style={{
                margin: "4px 0 0",
                padding: "4px 8px",
                background: "rgba(0,150,0,0.04)",
                borderRadius: 4,
                fontSize: 10,
                lineHeight: 1.4,
                overflowX: "auto",
                maxHeight: 120,
                whiteSpace: "pre-wrap",
                wordBreak: "break-word",
                fontFamily: "'Cascadia Code', 'Fira Code', monospace",
              }}
            >
              {outputStr}
            </pre>
          )}
        </div>
      )}
    </div>
  );
}

function ToolProgressEvent({ type, data }: { type: string; data: Record<string, unknown> }) {
  return (
    <span style={{ display: "flex", alignItems: "center", gap: 6 }}>
      <Wrench20Regular style={{ fontSize: 14, color: "#0078d4" }} />
      <span style={{ color: "var(--text-secondary)" }}>
        {type === "tool_progress" ? "Tool progress" : "Partial result"}: {String(data.tool || "")}
      </span>
    </span>
  );
}

/* ------------------------------------------------------------------ */
/* Delta accumulator                                                   */
/* ------------------------------------------------------------------ */

interface AccumulatedBlock {
  kind: "delta" | "reasoning";
  text: string;
  startTime: number;
  endTime: number;
}

/**
 * Accumulate consecutive delta / reasoning_delta events into text blocks.
 * Returns an interleaved list of accumulated blocks and regular events.
 */
function accumulateDeltas(
  events: JobEvent[],
): (JobEvent | AccumulatedBlock)[] {
  const result: (JobEvent | AccumulatedBlock)[] = [];
  let currentBlock: AccumulatedBlock | null = null;

  for (const ev of events) {
    const isDelta = ev.type === "delta";
    const isReasoning = ev.type === "reasoning_delta";

    if (isDelta || isReasoning) {
      const kind = isReasoning ? "reasoning" : "delta";
      const content = String((ev.data as any).content || "");
      if (!content) continue;

      if (currentBlock && currentBlock.kind === kind) {
        currentBlock.text += content;
        currentBlock.endTime = ev.time;
      } else {
        if (currentBlock) result.push(currentBlock);
        currentBlock = { kind, text: content, startTime: ev.time, endTime: ev.time };
      }
    } else {
      if (currentBlock) {
        result.push(currentBlock);
        currentBlock = null;
      }
      result.push(ev);
    }
  }
  if (currentBlock) result.push(currentBlock);
  return result;
}

function isAccumulatedBlock(item: JobEvent | AccumulatedBlock): item is AccumulatedBlock {
  return "kind" in item && ("text" in item);
}

/* ------------------------------------------------------------------ */
/* Main component                                                      */
/* ------------------------------------------------------------------ */

interface LiveActivityLogProps {
  events: JobEvent[];
  isRunning: boolean;
}

export function LiveActivityLog({ events, isRunning }: LiveActivityLogProps) {
  const verboseMode = useSettingsStore((s) => s.verboseMode);
  const scrollRef = useRef<HTMLDivElement>(null);
  const [autoScroll, setAutoScroll] = useState(true);
  const [, setTick] = useState(0);

  // Refresh relative timestamps every 10s
  useEffect(() => {
    const interval = setInterval(() => setTick((t) => t + 1), 10_000);
    return () => clearInterval(interval);
  }, []);

  // Filter events based on verbose mode, then trim to MAX_VISIBLE
  const filteredEvents = useMemo(() => {
    const filtered = events.filter((ev) => {
      const cat = categorize(ev.type);
      if (cat === "skip") return false;
      if (cat === "verbose" && !verboseMode) return false;
      return true;
    });
    return filtered.slice(-MAX_VISIBLE_EVENTS);
  }, [events, verboseMode]);

  // Accumulate deltas when verbose
  const displayItems = useMemo(() => {
    if (!verboseMode) return filteredEvents;
    return accumulateDeltas(filteredEvents);
  }, [filteredEvents, verboseMode]);

  // Count total events for badge
  const totalCount = events.filter((ev) => categorize(ev.type) !== "skip").length;

  // Auto-scroll
  useEffect(() => {
    if (autoScroll && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [displayItems.length, autoScroll]);

  const handleScroll = () => {
    if (!scrollRef.current) return;
    const { scrollTop, scrollHeight, clientHeight } = scrollRef.current;
    setAutoScroll(scrollHeight - scrollTop - clientHeight < 40);
  };

  if (filteredEvents.length === 0) {
    return (
      <div style={{ padding: "8px 12px", fontSize: 12, color: "var(--text-secondary)", display: "flex", alignItems: "center", gap: 6 }}>
        {isRunning && <Spinner size="tiny" />}
        {isRunning ? "Waiting for events..." : "No events"}
      </div>
    );
  }

  return (
    <div>
      {/* Header with counter */}
      <div style={{ display: "flex", alignItems: "center", gap: 8, padding: "4px 0 6px", fontSize: 11, color: "var(--text-secondary)" }}>
        <Badge appearance="tint" color="informative" size="small">
          {totalCount} event{totalCount !== 1 ? "s" : ""}
        </Badge>
        {!verboseMode && totalCount > filteredEvents.length && (
          <span style={{ fontSize: 10 }}>
            ({totalCount - filteredEvents.length} verbose hidden)
          </span>
        )}
        {isRunning && <Spinner size="tiny" style={{ marginLeft: "auto" }} />}
      </div>

      {/* Scrollable event list */}
      <div
        ref={scrollRef}
        onScroll={handleScroll}
        style={{
          maxHeight: 320,
          overflowY: "auto",
          display: "flex",
          flexDirection: "column",
          gap: 3,
          paddingRight: 4,
        }}
      >
        {displayItems.map((item, idx) => {
          if (isAccumulatedBlock(item)) {
            return (
              <div key={`block-${idx}`} style={{ display: "flex", gap: 8, alignItems: "flex-start" }}>
                <span style={{ fontSize: 10, color: "var(--text-secondary)", minWidth: 44, flexShrink: 0, textAlign: "right", marginTop: 2 }}>
                  {relativeTime(item.startTime)}
                </span>
                <div
                  style={{
                    flex: 1,
                    minWidth: 0,
                    padding: "4px 8px",
                    borderRadius: 4,
                    fontSize: 12,
                    lineHeight: 1.5,
                    maxHeight: 120,
                    overflow: "auto",
                    ...(item.kind === "reasoning"
                      ? {
                          fontStyle: "italic",
                          color: "#888",
                          fontFamily: "'Cascadia Code', 'Fira Code', monospace",
                          background: "rgba(0,0,0,0.03)",
                        }
                      : {
                          color: "var(--text-primary)",
                        }),
                    whiteSpace: "pre-wrap",
                    wordBreak: "break-word",
                  }}
                >
                  {item.text}
                </div>
              </div>
            );
          }

          const ev = item as JobEvent;
          return (
            <div key={ev.id} style={{ display: "flex", gap: 8, alignItems: "flex-start" }}>
              <span style={{ fontSize: 10, color: "var(--text-secondary)", minWidth: 44, flexShrink: 0, textAlign: "right", marginTop: 2 }}>
                {relativeTime(ev.time)}
              </span>
              <div style={{ flex: 1, minWidth: 0, fontSize: 12 }}>
                <CompactEventRow event={ev} verbose={verboseMode} />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Compact event row                                                   */
/* ------------------------------------------------------------------ */

function CompactEventRow({ event, verbose }: { event: JobEvent; verbose: boolean }) {
  const t = event.type;
  const d = event.data as Record<string, unknown>;

  switch (t) {
    case "phase_changed":
      return <PhaseEvent data={d} />;

    case "subagent_started":
    case "subagent_completed":
    case "subagent_failed":
      return <SubagentEvent type={t} data={d} />;

    case "waiting_for_input":
      return <WaitingEvent data={d} />;

    case "done":
      return (
        <span style={{ display: "flex", alignItems: "center", gap: 4, color: "#107c10", fontWeight: 600 }}>
          <CheckmarkCircle20Regular style={{ fontSize: 14 }} />
          Job completed
        </span>
      );

    case "cancelled":
      return (
        <span style={{ display: "flex", alignItems: "center", gap: 4, color: "var(--text-secondary)" }}>
          <Dismiss20Regular style={{ fontSize: 14 }} />
          Cancelled
        </span>
      );

    case "error":
    case "connection_error":
      return (
        <span style={{ display: "flex", alignItems: "center", gap: 4, color: "#d13438" }}>
          <Warning20Regular style={{ fontSize: 14 }} />
          {String(d.message || "Error").slice(0, 100)}
        </span>
      );

    case "new_files": {
      const files = (d.files as string[]) || [];
      const visible = files.filter((f) => !/\/generate_.*\.py$/.test(f));
      if (visible.length === 0) return null;
      return (
        <span style={{ display: "flex", alignItems: "center", gap: 4, color: "#107c10" }}>
          <FolderOpen20Regular style={{ fontSize: 14 }} />
          {visible.length === 1
            ? `Created: ${(visible[0].split("/").pop() || visible[0])}`
            : `${visible.length} files created`}
        </span>
      );
    }

    case "input_resolved":
      return (
        <span style={{ display: "flex", alignItems: "center", gap: 4, color: "var(--text-secondary)" }}>
          <CheckmarkCircle20Regular style={{ fontSize: 14 }} />
          Input resolved
        </span>
      );

    // Verbose-only events below
    case "tool_started":
    case "tool_completed":
      return <ToolEvent type={t} data={d} />;

    case "tool_partial_result":
    case "tool_progress":
      return <ToolProgressEvent type={t} data={d} />;

    case "assistant_intent":
      return (
        <span style={{ display: "flex", alignItems: "center", gap: 4, color: "#8764b8" }}>
          <Flash20Regular style={{ fontSize: 14 }} />
          <span style={{ fontStyle: "italic" }}>Intent: {String(d.intent || d.content || "").slice(0, 80)}</span>
        </span>
      );

    case "assistant_reasoning":
      return (
        <span style={{ color: "#888", fontStyle: "italic", fontFamily: "'Cascadia Code', 'Fira Code', monospace" }}>
          {String(d.content || d.reasoning || "").slice(0, 120)}
        </span>
      );

    case "assistant_message":
      return (
        <span style={{ color: "var(--text-primary)" }}>
          {String(d.content || "").slice(0, 120)}
        </span>
      );

    case "compaction_start":
      return (
        <span style={{ display: "flex", alignItems: "center", gap: 4, color: "var(--text-secondary)" }}>
          <ArrowSync20Regular style={{ fontSize: 14 }} />
          Context compaction started
        </span>
      );

    case "compaction_complete":
      return (
        <span style={{ display: "flex", alignItems: "center", gap: 4, color: "var(--text-secondary)" }}>
          <ArrowSync20Regular style={{ fontSize: 14 }} />
          Context compaction complete
        </span>
      );

    case "turn_started":
      return (
        <span style={{ display: "flex", alignItems: "center", gap: 4, color: "var(--text-secondary)" }}>
          <Play20Regular style={{ fontSize: 14 }} />
          Turn started
        </span>
      );

    case "turn_ended":
      return (
        <span style={{ display: "flex", alignItems: "center", gap: 4, color: "var(--text-secondary)" }}>
          <CheckmarkCircle20Regular style={{ fontSize: 14 }} />
          Turn ended
        </span>
      );

    case "session_handoff":
      return (
        <span style={{ display: "flex", alignItems: "center", gap: 4, color: "#8764b8" }}>
          <ArrowSync20Regular style={{ fontSize: 14 }} />
          Session handoff{d.target ? `: ${String(d.target)}` : ""}
        </span>
      );

    case "subagent_deselected":
      return (
        <span style={{ display: "flex", alignItems: "center", gap: 4, color: "var(--text-secondary)" }}>
          <Bot20Regular style={{ fontSize: 14 }} />
          Subagent deselected: {String(d.agent || "unknown")}
        </span>
      );

    case "subagent_selected":
      return (
        <span style={{ display: "flex", alignItems: "center", gap: 4, color: "#c27d12" }}>
          <Bot20Regular style={{ fontSize: 14 }} />
          Subagent selected: {String(d.agent || "unknown")}
        </span>
      );

    case "usage":
      return (
        <span style={{ display: "flex", alignItems: "center", gap: 4, color: "var(--text-secondary)" }}>
          <DataBarVertical20Regular style={{ fontSize: 14 }} />
          Tokens: {String(d.input_tokens || 0)} in / {String(d.output_tokens || 0)} out
          {d.cache_read_tokens ? ` / ${String(d.cache_read_tokens)} cached` : ""}
        </span>
      );

    default:
      return (
        <span style={{ color: "var(--text-secondary)", fontFamily: "monospace", fontSize: 11 }}>
          {t}
          {d.tool ? ` · ${String(d.tool)}` : ""}
          {d.agent ? ` · ${String(d.agent)}` : ""}
        </span>
      );
  }
}
