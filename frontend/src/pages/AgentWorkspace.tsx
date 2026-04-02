import { useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";
import {
  Text,
  Button,
  Card,
  Spinner,
  Badge,
  Textarea,
} from "@fluentui/react-components";
import {
  ArrowLeft20Regular,
  Dismiss20Regular,
  Checkmark20Regular,
  ArrowDownload20Regular,
  Send20Regular,
} from "@fluentui/react-icons";
import { useJobStore, type Job, type AgentPhase, type JobEvent } from "@/stores/jobStore";
import { useWebSocket } from "@/hooks/useWebSocket";
import { AGENT_META } from "@/api/types";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { AgentIcon } from "@/components/common/AgentIcon";

const PHASES: { key: AgentPhase; label: string }[] = [
  { key: "researching", label: "Research" },
  { key: "planning", label: "Planning" },
  { key: "reviewing", label: "Review" },
  { key: "building", label: "Building" },
  { key: "qa", label: "QA" },
  { key: "delivering", label: "Delivery" },
  { key: "done", label: "Done" },
];

function phaseIndex(phase: AgentPhase): number {
  return PHASES.findIndex((p) => p.key === phase);
}

function formatElapsed(ms: number): string {
  const sec = Math.floor(ms / 1000);
  const m = Math.floor(sec / 60);
  const s = sec % 60;
  return `${m}m ${String(s).padStart(2, "0")}s`;
}

function EventCard({ event }: { event: JobEvent }) {
  const t = event.type;
  const d = event.data as any;

  if (t === "tool_started") {
    const toolName = d.tool && d.tool !== "None" && d.tool !== "?" ? d.tool : null;
    if (!toolName) return null;
    return (
      <div style={{ padding: "8px 12px", background: "var(--hover-bg)", borderRadius: 6, fontSize: 13 }}>
        <span style={{ marginRight: 6 }}>🔧</span>
        <strong>{toolName}</strong>
      </div>
    );
  }
  if (t === "tool_completed") {
    const toolName = d.tool && d.tool !== "None" && d.tool !== "?" ? d.tool : null;
    if (!toolName) return null; // suppress unnamed tool completions
    return (
      <div style={{ padding: "8px 12px", background: "#f0faf0", borderRadius: 6, fontSize: 13 }}>
        <span style={{ marginRight: 6 }}>✅</span>
        <strong>{toolName}</strong>
        <span style={{ color: "var(--text-secondary)", marginLeft: 8 }}>
          {d.duration_ms}ms
        </span>
      </div>
    );
  }
  if (t === "subagent_started") {
    return (
      <div style={{ padding: "8px 12px", background: "#fff5e6", borderRadius: 6, fontSize: 13 }}>
        <span style={{ marginRight: 6 }}>🤖</span>
        Subagent: <strong>{d.agent}</strong>
      </div>
    );
  }
  if (t === "subagent_completed") {
    return (
      <div style={{ padding: "8px 12px", background: "#f0faf0", borderRadius: 6, fontSize: 13 }}>
        <span style={{ marginRight: 6 }}>✅</span>
        Subagent <strong>{d.agent}</strong> completed
      </div>
    );
  }
  if (t === "delta") {
    return null; // Don't show raw deltas as cards
  }
  if (t === "new_files") {
    return (
      <div style={{ padding: "8px 12px", background: "#e6f4ff", borderRadius: 6, fontSize: 13 }}>
        <span style={{ marginRight: 6 }}>📁</span>
        New files: {(d.files as string[])?.map((f: string) => f.split("/").pop()).join(", ")}
      </div>
    );
  }
  if (t === "done") {
    return (
      <div style={{ padding: "10px 14px", background: "#e6ffe6", borderRadius: 8, fontSize: 14, fontWeight: 600 }}>
        <span style={{ marginRight: 6 }}>🎉</span>
        Job completed!
      </div>
    );
  }
  if (t === "error" || t === "connection_error") {
    return (
      <div style={{ padding: "8px 12px", background: "#fff0f0", borderRadius: 6, fontSize: 13, color: "#d13438" }}>
        <span style={{ marginRight: 6 }}>⚠️</span>
        {d.message}
      </div>
    );
  }
  if (t === "waiting_for_input") {
    return (
      <div style={{ padding: "8px 12px", background: "#fff5e6", borderRadius: 6, fontSize: 13 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 6 }}>
          <span>⏸️</span>
          <strong>Waiting for input</strong>
        </div>
        <div className="md-content" style={{ fontSize: 13 }}>
          <ReactMarkdown remarkPlugins={[remarkGfm]}>
            {String(d.question || "The agent has a question")}
          </ReactMarkdown>
        </div>
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
  const { sendMessage, sendUserResponse, cancel } = useWebSocket(jobId || null);
  const [editedPlan, setEditedPlan] = useState("");
  const [elapsed, setElapsed] = useState(0);

  // Assemble and send the initial prompt when the WS connects
  const promptSent = useRef(false);

  useEffect(() => {
    // Reset when job ID changes — but only if it's a brand new job with no events
    const existing = useJobStore.getState().getJob(jobId);
    promptSent.current = !!(existing && existing.events.length > 0);
  }, [jobId]);

  useEffect(() => {
    if (!job || promptSent.current) return;
    // Wait until the job transitions from "queued" to "running" (WS connected)
    if (job.status !== "running") return;
    // Don't auto-send for resumed sessions — user will type a follow-up
    if (job.brief.topic === "Resumed session") {
      promptSent.current = true;
      return;
    }

    promptSent.current = true;

    // Build prompt from brief
    const b = job.brief;
    const agentMeta = AGENT_META[job.agent];
    const levelPart = agentMeta?.showContentLevel ? `${b.contentLevel} ` : "";
    const durationPart = agentMeta?.showDuration ? `${b.duration} ` : "";
    let prompt: string;

    if (job.agent === "slide-conductor") {
      prompt = `@${job.agent} Create a ${levelPart}${durationPart}presentation on "${b.topic}"`;
    } else if (job.agent === "demo-conductor") {
      prompt = `@${job.agent} Create a ${levelPart}${durationPart}demo guide on "${b.topic}"`;
    } else if (job.agent === "hackathon-conductor") {
      prompt = `@${job.agent} Create a ${levelPart}${durationPart}hackathon on "${b.topic}"`;
    } else if (job.agent === "ai-brainstorming") {
      prompt = `@${job.agent} Brainstorm AI project ideas for "${b.topic}"`;
    } else if (job.agent === "ai-solution-architect") {
      prompt = `@${job.agent} Design an architecture for "${b.topic}"`;
    } else if (job.agent === "ai-implementor") {
      prompt = `@${job.agent} Build a full project for "${b.topic}"`;
    } else {
      prompt = `@${job.agent} Create ${levelPart}${durationPart}content about "${b.topic}"`;
    }

    if (b.audience) prompt += ` for ${b.audience}`;
    if (b.notes) prompt += `. ${b.notes}`;

    // Send the prompt now — WS is already connected
    sendMessage(prompt);
  }, [job?.id, job?.status]);

  useEffect(() => {
    if (job?.pendingInput?.question) {
      setEditedPlan("");
    }
  }, [job?.pendingInput?.question]);

  // Elapsed time ticker
  useEffect(() => {
    if (!job || job.status === "completed" || job.status === "failed" || job.status === "cancelled") return;
    const interval = setInterval(() => {
      setElapsed(Date.now() - (job?.startedAt || Date.now()));
    }, 1000);
    return () => clearInterval(interval);
  }, [job?.id, job?.status, job?.startedAt]);

  // Collect accumulated delta text for the plan review
  const deltaText = useMemo(() => {
    if (!job) return "";
    return job.events
      .filter((e) => e.type === "delta")
      .map((e) => (e.data as any).content || "")
      .join("");
  }, [job?.events.length]);

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

  const meta = AGENT_META[job.agent] || { icon: "🔧", label: job.agent, color: "#0078D4" };
  const currentPhaseIdx = phaseIndex(job.phase);

  // Determine which phase the job actually reached before failing.
  // Walk the events backwards to find the last real phase_changed event.
  const lastReachedPhase = useMemo(() => {
    if (job.status !== "failed" && job.status !== "cancelled") return currentPhaseIdx;
    // Find the last phase_changed event to know where it actually got to
    for (let i = job.events.length - 1; i >= 0; i--) {
      const e = job.events[i];
      if (e.type === "phase_changed" && (e.data as any).phase) {
        const idx = phaseIndex((e.data as any).phase as AgentPhase);
        if (idx >= 0) return idx;
      }
    }
    // Fallback: use tool/subagent events to infer
    const hadTools = job.progress.toolCalls > 0;
    const hadSubagents = job.progress.subagentRuns > 0;
    if (!hadTools && !hadSubagents) return 0; // never got past research
    return 0; // conservative: only mark research as reached
  }, [job.events, job.status, job.progress, currentPhaseIdx]);

  // Filter to only meaningful events for the activity feed
  const feedEvents = job.events.filter(
    (e) =>
      e.type !== "delta" &&
      e.type !== "reasoning_delta" &&
      e.type !== "usage" &&
      e.type !== "phase_changed" &&
      e.type !== "turn_started",
  );

  return (
    <div style={{ display: "flex", height: "100vh", overflow: "hidden" }}>
      {/* Left: Progress Stepper */}
      <div
        style={{
          width: 200,
          borderRight: "1px solid var(--border)",
          padding: "20px 16px",
          display: "flex",
          flexDirection: "column",
          background: "var(--card-bg)",
          flexShrink: 0,
          overflow: "auto",
        }}
      >
        <Button
          appearance="subtle"
          icon={<ArrowLeft20Regular />}
          size="small"
          onClick={() => navigate("/mission")}
          style={{ marginBottom: 16, justifyContent: "flex-start" }}
        >
          Mission Ctrl
        </Button>

        <Text
          weight="semibold"
          size={200}
          style={{
            display: "block",
            marginBottom: 14,
            textTransform: "uppercase",
            fontSize: 10,
            letterSpacing: "0.06em",
            color: "var(--text-secondary)",
          }}
        >
          Progress
        </Text>

        <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
          {PHASES.map((p, i) => {
            const isFailed = job.status === "failed" || job.status === "cancelled";
            const effectiveIdx = isFailed ? lastReachedPhase : currentPhaseIdx;
            const isDone = isFailed
              ? i < effectiveIdx                      // only phases before the failure point
              : i < currentPhaseIdx;
            const isFailedPhase = isFailed && i === effectiveIdx && p.key !== "done";
            const isActive = !isFailed && i === currentPhaseIdx && job.status !== "completed";
            const isPending = isFailed
              ? i > effectiveIdx || (i === effectiveIdx && !isFailedPhase)
              : i > currentPhaseIdx;

            return (
              <div
                key={p.key}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 10,
                  padding: "6px 8px",
                  borderRadius: 6,
                  background: isActive
                    ? "rgba(0,120,212,0.06)"
                    : isFailedPhase
                      ? "rgba(209,52,56,0.06)"
                      : "transparent",
                }}
              >
                <div
                  style={{
                    width: 22,
                    height: 22,
                    borderRadius: "50%",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    fontSize: 11,
                    fontWeight: 700,
                    flexShrink: 0,
                    background: isDone
                      ? "#7FBA00"
                      : isFailedPhase
                        ? "#d13438"
                        : isActive
                          ? "var(--brand-primary)"
                          : "#edebe9",
                    color: isDone || isActive || isFailedPhase ? "#fff" : "#a19f9d",
                    animation: isActive ? "pulse 2s infinite" : undefined,
                  }}
                >
                  {isDone ? "✓" : isFailedPhase ? "✕" : i + 1}
                </div>
                <div>
                  <Text
                    size={200}
                    weight={isActive || isFailedPhase ? "semibold" : "regular"}
                    style={{
                      color: isPending && !isFailedPhase
                        ? "#a19f9d"
                        : isFailedPhase
                          ? "#d13438"
                          : "var(--text-primary)",
                      display: "block",
                    }}
                  >
                    {p.label}
                  </Text>
                </div>
              </div>
            );
          })}
        </div>

        {/* Stats */}
        <div style={{ marginTop: "auto", paddingTop: 16, borderTop: "1px solid var(--border)" }}>
          <Text
            size={200}
            style={{ display: "block", color: "var(--text-secondary)", marginBottom: 4 }}
          >
            ⏱ {formatElapsed(job.completedAt ? job.completedAt - job.startedAt : elapsed)}
          </Text>
          <Text
            size={200}
            style={{ display: "block", color: "var(--text-secondary)", marginBottom: 4 }}
          >
            🔧 {job.progress.toolCalls} tool calls
          </Text>
          <Text
            size={200}
            style={{ display: "block", color: "var(--text-secondary)", marginBottom: 4 }}
          >
            🤖 {job.progress.subagentRuns} subagents
          </Text>
          <Text
            size={200}
            style={{ display: "block", color: "var(--text-secondary)" }}
          >
            📊 {((job.usage.inputTokens + job.usage.outputTokens) / 1000).toFixed(0)}k tokens
          </Text>
        </div>
      </div>

      {/* Center: Activity Feed */}
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
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <AgentIcon agent={job.agent} size="inline" />
            <Text weight="semibold" size={400}>
              {job.title}
            </Text>
            <Badge
              size="small"
              color={
                job.status === "completed"
                  ? "success"
                  : job.status === "failed"
                    ? "danger"
                    : job.status === "waiting"
                      ? "warning"
                      : "brand"
              }
            >
              {job.status}
            </Badge>
          </div>
          {(job.status === "running" || job.status === "queued") && (
            <Button
              appearance="subtle"
              icon={<Dismiss20Regular />}
              onClick={cancel}
              style={{ color: "#d13438" }}
            >
              Cancel
            </Button>
          )}
        </div>

        {/* Plan Review / Question Gate */}
        {job.status === "waiting" && job.pendingInput && (() => {
          const isPlanReview = deltaText.length > 50;
          const hasChoices = !!(job.pendingInput.choices && job.pendingInput.choices.length > 0);
          return (
          <Card
            style={{
              margin: "16px 24px",
              border: `2px solid ${isPlanReview ? "#FFB900" : "#0078D4"}`,
              borderRadius: 10,
              padding: "20px 24px",
              background: isPlanReview ? "#fffbf0" : "#f0f6ff",
            }}
          >
            {deltaText && (
              <div
                className="md-content"
                style={{
                  padding: "12px 16px",
                  background: "var(--card-bg)",
                  border: "1px solid var(--border)",
                  borderRadius: 8,
                  maxHeight: 300,
                  overflow: "auto",
                  marginBottom: 14,
                  fontSize: 13,
                }}
              >
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {deltaText}
                </ReactMarkdown>
              </div>
            )}

            <div style={{ display: "flex", gap: 10, alignItems: "flex-start", marginBottom: 12 }}>
              <span style={{ fontSize: 18, lineHeight: 1.6 }}>{isPlanReview ? "📋" : "💬"}</span>
              <div className="md-content" style={{ flex: 1, fontSize: 14, fontWeight: 600 }}>
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {job.pendingInput.question}
                </ReactMarkdown>
              </div>
            </div>

            {hasChoices && (
              <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 14 }}>
                {job.pendingInput.choices!.map((choice, i) => (
                  <Button
                    key={i}
                    appearance="outline"
                    onClick={() => sendUserResponse(choice)}
                    style={{ fontSize: 13 }}
                  >
                    {choice}
                  </Button>
                ))}
              </div>
            )}

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
              style={{ marginBottom: 14 }}
            />

            <div style={{ display: "flex", gap: 10 }}>
              {isPlanReview ? (
                <>
                  <Button
                    appearance="primary"
                    icon={<Checkmark20Regular />}
                    onClick={() => sendUserResponse(editedPlan.trim() || "Looks good, proceed with building.")}
                  >
                    Approve
                  </Button>
                  <Button
                    appearance="outline"
                    onClick={() => {
                      const text = editedPlan.trim() || "Approved with modifications";
                      sendUserResponse(text);
                    }}
                  >
                    Edit & Approve
                  </Button>
                  <Button
                    appearance="subtle"
                    onClick={() => sendUserResponse("Reject this plan. Cancel the job.")}
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
                    disabled={!editedPlan.trim() && !hasChoices}
                    onClick={() => {
                      if (editedPlan.trim()) {
                        sendUserResponse(editedPlan.trim());
                      }
                    }}
                  >
                    Reply
                  </Button>
                  <Button
                    appearance="subtle"
                    onClick={() => sendUserResponse("Skip this question and decide for me.")}
                  >
                    Skip
                  </Button>
                </>
              )}
            </div>
          </Card>
          );
        })()}

        {/* Activity feed */}
        <div
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
            {feedEvents.map((e) => (
              <EventCard key={e.id} event={e} />
            ))}
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
                {job.outputFiles.map((f) => (
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

        {/* Bottom bar */}
        <div
          style={{
            padding: "10px 24px",
            borderTop: "1px solid var(--border)",
            background: "var(--card-bg)",
            display: "flex",
            alignItems: "center",
            gap: 16,
            fontSize: 13,
            color: "var(--text-secondary)",
          }}
        >
          <span>⏱ {formatElapsed(job.completedAt ? job.completedAt - job.startedAt : elapsed)}</span>
          <span>│</span>
          <span>{job.progress.toolCalls} tool calls</span>
          <span>│</span>
          <span>{job.progress.subagentRuns} subagents</span>
        </div>

        {/* Follow-up input — for completed or resumed jobs */}
        {(job.status === "completed" || job.status === "running") && (
          <form
            onSubmit={(e) => {
              e.preventDefault();
              const input = (e.currentTarget.elements.namedItem("followup") as HTMLInputElement);
              const text = input?.value?.trim();
              if (!text) return;
              sendMessage(text);
              input.value = "";
            }}
            style={{
              padding: "10px 24px",
              borderTop: "1px solid var(--border)",
              background: "var(--card-bg)",
              display: "flex",
              gap: 8,
            }}
          >
            <input
              name="followup"
              placeholder="Send a follow-up message..."
              style={{
                flex: 1,
                padding: "8px 12px",
                border: "1px solid var(--border)",
                borderRadius: 6,
                fontSize: 14,
                background: "var(--brand-light)",
                color: "var(--text-primary)",
                outline: "none",
              }}
            />
            <Button appearance="primary" type="submit" size="small">
              Send
            </Button>
          </form>
        )}
      </div>
    </div>
  );
}
