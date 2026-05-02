import { useNavigate } from "react-router-dom";
import {
  Text,
  Button,
  Card,
  Badge,
  Menu,
  MenuTrigger,
  MenuPopover,
  MenuList,
  MenuItem,
  Input,
  Spinner,
  TabList,
  Tab,
} from "@fluentui/react-components";
import {
  Add20Regular,
  Delete20Regular,
  ChevronDown20Regular,
  ChevronRight20Regular,
  ArrowDownload20Regular,
  Search20Regular,
  Play20Regular,
  Rocket20Regular,
  Warning20Regular,
} from "@fluentui/react-icons";
import { useJobStore, type Job } from "@/stores/jobStore";
import { useWebSocket } from "@/hooks/useWebSocket";
import { useAutoSendBrief } from "@/hooks/useAutoSendBrief";
import { AGENT_META } from "@/api/types";
import { useState, useEffect } from "react";
import { BriefForm } from "@/components/brief/BriefForm";
import type { AgentType } from "@/api/types";
import type { SessionInfo, Turn } from "@/api/types";
import { AgentIcon } from "@/components/common/AgentIcon";
import { listSessions, getSessionTurns, resumeSession as apiResumeSession, getSessionStatus } from "@/api/client";


import { formatElapsed } from "@/utils/formatElapsed";

function formatJobElapsed(job: Job): string {
  const ms = (job.completedAt || Date.now()) - job.startedAt;
  return formatElapsed(ms);
}

function formatTokens(n: number): string {
  if (n >= 1000) return `${(n / 1000).toFixed(0)}k`;
  return String(n);
}

function JobCard({ job }: { job: Job }) {
  const navigate = useNavigate();
  const meta = AGENT_META[job.agent] || { icon: "", label: job.agent, color: "#666" };

  return (
    <Card
      style={{
        border: job.status === "waiting" ? "2px solid #FFB900" : "1px solid var(--border-subtle)",
        borderRadius: 10,
        padding: "14px 18px",
        cursor: "pointer",
        transition: "all 0.15s ease",
        animation: job.status === "waiting" ? "pulse 3s infinite" : undefined,
      }}
      onClick={() => navigate(`/workspace?id=${job.id}`)}
      onMouseEnter={(e) => {
        (e.currentTarget as HTMLElement).style.boxShadow = "0 4px 16px rgba(0,0,0,0.06)";
      }}
      onMouseLeave={(e) => {
        (e.currentTarget as HTMLElement).style.boxShadow = "none";
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 12, minWidth: 0 }}>
        <AgentIcon agent={job.agent} size="inline" />
        <div style={{ flex: 1, minWidth: 0 }}>
          <Text
            weight="semibold"
            size={300}
            style={{
              display: "block",
              overflow: "hidden",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap",
            }}
          >
            {job.title}
          </Text>
          <Text
            size={200}
            style={{
              color: "var(--text-secondary)",
              display: "block",
              overflow: "hidden",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap",
            }}
          >
            {job.agent} · {job.progress.currentStep}
          </Text>
          {/* Running subagent + tool activity indicator */}
          {(job.status === "running" || job.status === "queued") &&
            (job.progress.subagentRuns > 0 || job.progress.toolCalls > 0) && (
            <Text
              size={100}
              style={{
                color: "var(--text-secondary)",
                display: "flex",
                gap: 8,
                marginTop: 2,
              }}
            >
              {job.progress.toolCalls > 0 && <span>{job.progress.toolCalls} tools</span>}
              {job.progress.subagentRuns > 0 && <span>{job.progress.subagentRuns} subagents</span>}
            </Text>
          )}
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 10, flexShrink: 0 }}>
          <Text size={200} style={{ color: "var(--text-secondary)", whiteSpace: "nowrap", minWidth: 56, textAlign: "right", fontVariantNumeric: "tabular-nums" }}>
            {formatJobElapsed(job)}
          </Text>
          <span
            style={{
              padding: "2px 8px",
              borderRadius: 5,
              fontSize: 10,
              fontWeight: 600,
              textTransform: "uppercase",
              letterSpacing: "0.02em",
              color: "white",
              whiteSpace: "nowrap",
              minWidth: 64,
              textAlign: "center",
              display: "inline-block",
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
          {/* Individual delete button for completed/failed/cancelled jobs */}
          {(job.status === "completed" || job.status === "failed" || job.status === "cancelled") && (
            <button
              title="Remove this job"
              onClick={(e) => {
                e.stopPropagation();
                useJobStore.getState().removeJob(job.id);
              }}
              style={{
                display: "inline-flex",
                alignItems: "center",
                justifyContent: "center",
                width: 28,
                height: 28,
                borderRadius: 6,
                border: "none",
                background: "transparent",
                color: "var(--text-secondary)",
                cursor: "pointer",
                flexShrink: 0,
                transition: "color 0.15s, background 0.15s",
              }}
              onMouseEnter={(e) => {
                (e.currentTarget as HTMLElement).style.color = "#d13438";
                (e.currentTarget as HTMLElement).style.background = "rgba(209,52,56,0.08)";
              }}
              onMouseLeave={(e) => {
                (e.currentTarget as HTMLElement).style.color = "var(--text-secondary)";
                (e.currentTarget as HTMLElement).style.background = "transparent";
              }}
            >
              <Delete20Regular />
            </button>
          )}
        </div>
      </div>

      {/* Waiting indicator */}
      {job.status === "waiting" && job.pendingInput?.[0] && (
        <div
          style={{
            marginTop: 10,
            padding: "8px 12px",
            background: "var(--bg-hint)",
            borderRadius: 6,
            fontSize: 13,
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
          }}
        >
          <span style={{ display: "flex", alignItems: "center", gap: 4 }}><Warning20Regular /> {job.pendingInput[0].question.slice(0, 60)}{job.pendingInput.length > 1 ? ` (+${job.pendingInput.length - 1})` : ""}</span>
          <Button appearance="primary" size="small" onClick={() => navigate(`/workspace?id=${job.id}`)}>
            Review
          </Button>
        </div>
      )}

      {/* Token / cost info for completed */}
      {(job.status === "completed" || job.status === "failed") && (
        <div
          style={{
            marginTop: 6,
            fontSize: 12,
            color: "var(--text-secondary)",
            display: "flex",
            gap: 12,
          }}
        >
          <span style={{ fontVariantNumeric: "tabular-nums" }}>
            {formatTokens(job.usage.inputTokens + job.usage.outputTokens)} tokens
          </span>
          <span style={{ fontVariantNumeric: "tabular-nums" }}>{job.progress.toolCalls} tools</span>
          <span style={{ fontVariantNumeric: "tabular-nums" }}>{job.progress.subagentRuns} subagents</span>
        </div>
      )}

      {/* Compact deliverable summary for completed jobs */}
      {job.status === "completed" && (() => {
        const deliverables = job.outputFiles.filter((f) => !/\/generate_.*\.py$/.test(f));
        return deliverables.length > 0 ? (
          <div
            style={{
              marginTop: 10,
              padding: "6px 12px",
              background: "var(--bg-success-gradient)",
              borderRadius: 6,
              border: "1px solid rgba(127, 186, 0, 0.2)",
              display: "flex",
              alignItems: "center",
              gap: 8,
              fontSize: 12,
              fontWeight: 500,
              color: "var(--text-primary)",
            }}
          >
            <ArrowDownload20Regular style={{ flexShrink: 0, color: "#7FBA00" }} />
            <span>{deliverables.length} deliverable{deliverables.length !== 1 ? "s" : ""} ready — click to view</span>
          </div>
        ) : null;
      })()}
    </Card>
  );
}

/**
 * LiveJobCard — wraps a running/waiting job card and connects WebSocket.
 */
function LiveJobCard({ job }: { job: Job }) {
  const navigate = useNavigate();
  const meta = AGENT_META[job.agent] || { icon: "", label: job.agent, color: "#666" };
  const isLive = job.status === "running" || job.status === "queued" || job.status === "waiting";

  // Connect WebSocket for this job & auto-send brief if not yet sent
  const { sendMessage } = useWebSocket(isLive ? job.id : null);
  useAutoSendBrief(isLive ? job.id : null, sendMessage);

  return (
    <Card
      style={{
        border: job.status === "waiting" ? "2px solid #FFB900" : "1px solid var(--border-subtle)",
        borderRadius: 10,
        padding: "14px 18px",
        transition: "all 0.15s ease",
        animation: job.status === "waiting" ? "pulse 3s infinite" : undefined,
      }}
    >
      {/* Clickable summary row */}
      <div
        style={{ cursor: "pointer" }}
        onClick={() => navigate(`/workspace?id=${job.id}`)}
        onMouseEnter={(e) => {
          (e.currentTarget.parentElement as HTMLElement).style.boxShadow = "0 4px 16px rgba(0,0,0,0.06)";
        }}
        onMouseLeave={(e) => {
          (e.currentTarget.parentElement as HTMLElement).style.boxShadow = "none";
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 12, minWidth: 0 }}>
          <AgentIcon agent={job.agent} size="inline" />
          <div style={{ flex: 1, minWidth: 0 }}>
            <Text
              weight="semibold"
              size={300}
              style={{
                display: "block",
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "nowrap",
              }}
            >
              {job.title}
            </Text>
            <Text
              size={200}
              style={{
                color: "var(--text-secondary)",
                display: "block",
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "nowrap",
              }}
            >
              {job.agent} · {job.progress.currentStep}
            </Text>
            {(job.status === "running" || job.status === "queued") &&
              (job.progress.subagentRuns > 0 || job.progress.toolCalls > 0) && (
              <Text
                size={100}
                style={{
                  color: "var(--text-secondary)",
                  display: "flex",
                  gap: 8,
                  marginTop: 2,
                }}
              >
                {job.progress.toolCalls > 0 && <span>{job.progress.toolCalls} tools</span>}
                {job.progress.subagentRuns > 0 && <span>{job.progress.subagentRuns} subagents</span>}
              </Text>
            )}
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 10, flexShrink: 0 }}>
            <Text size={200} style={{ color: "var(--text-secondary)", whiteSpace: "nowrap", minWidth: 56, textAlign: "right", fontVariantNumeric: "tabular-nums" }}>
              {formatJobElapsed(job)}
            </Text>
            <span
              style={{
                padding: "2px 8px",
                borderRadius: 5,
                fontSize: 10,
                fontWeight: 600,
                textTransform: "uppercase",
                letterSpacing: "0.02em",
                color: "white",
                whiteSpace: "nowrap",
                minWidth: 64,
                textAlign: "center",
                display: "inline-block",
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

          {/* Progress indication — only rendered when running to avoid dead space */}
          {job.status === "running" && (
            <div style={{ width: 60, flexShrink: 0 }}>
              <div
                style={{
                  width: 60,
                  height: 6,
                  background: "var(--border)",
                  borderRadius: 3,
                  overflow: "hidden",
                }}
              >
                <div
                  style={{
                    height: "100%",
                    borderRadius: 3,
                    background: "var(--brand-primary)",
                    animation: "indeterminate 1.5s ease-in-out infinite",
                    width: "40%",
                  }}
                />
              </div>
            </div>
          )}
        </div>

        {/* Waiting indicator */}
        {job.status === "waiting" && job.pendingInput?.[0] && (
          <div
            style={{
              marginTop: 10,
              padding: "8px 12px",
              background: "var(--bg-hint)",
              borderRadius: 6,
              fontSize: 13,
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
            }}
          >
            <span style={{ display: "flex", alignItems: "center", gap: 4 }}><Warning20Regular /> {job.pendingInput[0].question.slice(0, 60)}{job.pendingInput.length > 1 ? ` (+${job.pendingInput.length - 1})` : ""}</span>
            <Button appearance="primary" size="small" onClick={(e) => { e.stopPropagation(); navigate(`/workspace?id=${job.id}`); }}>
              Review
            </Button>
          </div>
        )}
      </div>


    </Card>
  );
}

export function MissionControl() {
  const navigate = useNavigate();
  const jobs = useJobStore((s) => s.jobs);
  const addJob = useJobStore((s) => s.addJob);
  const allJobs = Object.values(jobs);
  const [briefAgent, setBriefAgent] = useState<AgentType | null>(null);

  // History state (from backend SQLite)
  const [sessions, setSessions] = useState<SessionInfo[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyLoaded, setHistoryLoaded] = useState(false);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [showHistory, setShowHistory] = useState(false);

  const running = allJobs.filter((j) => j.status === "running" || j.status === "queued");
  const waiting = allJobs.filter((j) => j.status === "waiting");
  const completed = allJobs.filter(
    (j) => j.status === "completed" || j.status === "failed" || j.status === "cancelled",
  );

  // Sort by most recent first
  completed.sort((a, b) => (b.completedAt || 0) - (a.completedAt || 0));

  // Tick every second while there are running jobs so elapsed time stays fresh
  const [, setTick] = useState(0);
  useEffect(() => {
    if (running.length === 0) return;
    const id = setInterval(() => setTick((t) => t + 1), 1000);
    return () => clearInterval(id);
  }, [running.length]);

  // Poll the server for running/waiting jobs when the user is on this page
  // (no WS is connected from MissionControl, so job state can go stale).
  const updateJob = useJobStore((s) => s.updateJob);
  useEffect(() => {
    const liveJobs = [...running, ...waiting];
    if (liveJobs.length === 0) return;

    const poll = () => {
      for (const job of liveJobs) {
        getSessionStatus(job.id)
          .then((srv) => {
            const fresh = useJobStore.getState().getJob(job.id);
            if (!fresh || fresh.status === "completed" || fresh.status === "failed" || fresh.status === "cancelled") return;
            if (srv.status === "ended" || (!srv.in_memory && !srv.has_running_turn)) {
              // Restore output files from the server if the WS missed them
              const srvFiles: string[] = srv.output_files || [];
              const existingFiles = new Set(fresh.outputFiles);
              const newFiles = srvFiles.filter((f: string) => !existingFiles.has(f));
              updateJob(job.id, {
                status: "completed",
                phase: "done",
                completedAt: Date.now(),
                pendingInput: [],
                ...(newFiles.length > 0 ? { outputFiles: [...fresh.outputFiles, ...newFiles] } : {}),
              });
            } else if (srv.pending_input && fresh.status !== "waiting") {
              // Server has a pending question the frontend doesn't know about
              const q = srv.pending_input.question || "The agent has a question";
              const alreadyQueued = (fresh.pendingInput || []).some(
                (p) => p.question === q,
              );
              if (!alreadyQueued) {
                updateJob(job.id, {
                  status: "waiting",
                  pendingInput: [
                    ...(fresh.pendingInput || []),
                    { question: q, choices: srv.pending_input.choices || undefined },
                  ],
                });
              }
            }
          })
          .catch(() => {});
      }
    };

    // First poll shortly after mount, then every 10s
    const immediate = setTimeout(poll, 2000);
    const interval = setInterval(poll, 10000);
    return () => {
      clearTimeout(immediate);
      clearInterval(interval);
    };
  }, [running.length, waiting.length]);

  // Lazy-load history when section is expanded
  useEffect(() => {
    if (showHistory && !historyLoaded) {
      setHistoryLoading(true);
      listSessions(true)
        .then(setSessions)
        .catch(() => {})
        .finally(() => {
          setHistoryLoading(false);
          setHistoryLoaded(true);
        });
    }
  }, [showHistory, historyLoaded]);

  const handleResume = async (sessionId: string) => {
    try {
      const res = await apiResumeSession(sessionId);
      const job: Job = {
        id: res.session_id,
        title: `Resumed: ${res.agent || "session"}`,
        agent: (res.agent || "slide-conductor") as AgentType,
        brief: { topic: "Resumed session", contentLevel: "L300", duration: "30 min" },
        status: "queued",
        phase: "researching",
        startedAt: Date.now(),
        progress: { toolCalls: 0, subagentRuns: 0, currentStep: "Resumed — waiting for input" },
        events: [],
        outputFiles: [],
        usage: { inputTokens: 0, outputTokens: 0, estimatedCostUsd: 0 },
      };
      addJob(job);
      navigate(`/workspace?id=${res.session_id}`);
    } catch (e: any) {
      alert(`Failed to resume: ${e.message}`);
    }
  };

  const handleViewSession = (sessionId: string) => {
    const existing = useJobStore.getState().getJob(sessionId);
    if (existing) {
      navigate(`/workspace?id=${sessionId}`);
      return;
    }
    const session = sessions.find((s) => s.id === sessionId);
    if (!session) return;
    const job: Job = {
      id: session.id,
      title: session.agent || "Session",
      agent: (session.agent || "slide-conductor") as AgentType,
      brief: { topic: session.agent || "session", contentLevel: "L300", duration: "" },
      status: session.status === "active" ? "running" : "completed",
      phase: session.status === "active" ? "building" : "done",
      startedAt: new Date(session.started_at).getTime(),
      completedAt: session.ended_at ? new Date(session.ended_at).getTime() : undefined,
      progress: { toolCalls: 0, subagentRuns: 0, currentStep: session.status },
      events: [],
      outputFiles: [],
      usage: {
        inputTokens: session.total_input_tokens,
        outputTokens: session.total_output_tokens,
        estimatedCostUsd: 0,
      },
    };
    addJob(job);
    navigate(`/workspace?id=${sessionId}`);
  };

  // Filter sessions for history tab
  const filteredSessions = sessions.filter((s) => {
    if (statusFilter === "active" && s.status !== "active") return false;
    if (statusFilter === "ended" && s.status !== "ended") return false;
    if (statusFilter === "resumable" && !s.resumable) return false;
    if (search.trim()) {
      const q = search.toLowerCase();
      return (
        s.id.toLowerCase().includes(q) ||
        (s.agent || "").toLowerCase().includes(q) ||
        (s.nickname || "").toLowerCase().includes(q)
      );
    }
    return true;
  });

  return (
    <div className="page-container" style={{ padding: "32px 48px", maxWidth: 1000, margin: "0 auto" }}>
      <div
        className="header-row"
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          marginBottom: 28,
        }}
      >
        <Text
          as="h1"
          size={700}
          weight="bold"
          style={{ letterSpacing: "-0.03em" }}
        >
          Mission Control
        </Text>
        <div style={{ display: "flex", gap: 8 }}>
          {completed.length > 0 && (
            <Button
              appearance="subtle"
              icon={<Delete20Regular />}
              onClick={() => {
                for (const j of completed) {
                  useJobStore.getState().removeJob(j.id);
                }
              }}
            >
              Clear Completed
            </Button>
          )}
          <Menu>
          <MenuTrigger disableButtonEnhancement>
            <Button appearance="primary" icon={<Add20Regular />}>
              New Job
            </Button>
          </MenuTrigger>
          <MenuPopover>
            <MenuList>
              {(Object.entries(AGENT_META) as [AgentType, (typeof AGENT_META)[AgentType]][]).map(
                ([key, meta]) => (
                  <MenuItem
                    key={key}
                    icon={<AgentIcon agent={key} size="inline" />}
                    onClick={() => setBriefAgent(key)}
                  >
                    {meta.label}
                  </MenuItem>
                ),
              )}
            </MenuList>
          </MenuPopover>
        </Menu>
        </div>
      </div>

      {allJobs.length === 0 && !showHistory && (
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            padding: "80px 24px",
            gap: 16,
          }}
        >
          <div
            style={{
              width: 80,
              height: 80,
              borderRadius: 24,
              background: "rgba(0, 120, 212, 0.06)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              marginBottom: 8,
            }}
          >
            <Rocket20Regular style={{ width: 36, height: 36, color: "var(--brand-primary)", opacity: 0.7 }} />
          </div>
          <Text size={500} weight="semibold" style={{ color: "var(--text-primary)" }}>
            No active jobs
          </Text>
          <Text
            size={300}
            style={{
              color: "var(--text-secondary)",
              maxWidth: 420,
              textAlign: "center",
              lineHeight: 1.5,
            }}
          >
            Launch your first content generation from the Launchpad — pick a topic, level, and let the agents handle the rest.
          </Text>
          <Button
            appearance="primary"
            icon={<Rocket20Regular />}
            style={{ marginTop: 8 }}
            onClick={() => navigate("/")}
          >
            Go to Launchpad
          </Button>
        </div>
      )}

      {/* Running — always rendered for stable layout */}
      {allJobs.length > 0 && (
        <div style={{ marginBottom: 28, minHeight: 36 }}>
          <Text
            weight="semibold"
            size={300}
            style={{
              display: "block",
              marginBottom: 10,
              textTransform: "uppercase",
              fontSize: 11,
              letterSpacing: "0.04em",
              color: "var(--text-secondary)",
            }}
          >
            Running ({running.length})
          </Text>
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {running.map((j) => (
              <LiveJobCard key={j.id} job={j} />
            ))}
          </div>
        </div>
      )}

      {/* Waiting — always rendered for stable layout */}
      {allJobs.length > 0 && (
        <div style={{ marginBottom: 28, minHeight: 36 }}>
          <Text
            weight="semibold"
            size={300}
            style={{
              display: "block",
              marginBottom: 10,
              textTransform: "uppercase",
              fontSize: 11,
              letterSpacing: "0.04em",
              color: waiting.length > 0 ? "#d48806" : "var(--text-secondary)",
            }}
          >
            {waiting.length > 0 ? "⚠️ " : ""}Waiting for Input ({waiting.length})
          </Text>
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {waiting.map((j) => (
              <LiveJobCard key={j.id} job={j} />
            ))}
          </div>
        </div>
      )}

      {/* Completed — always rendered for stable layout */}
      {allJobs.length > 0 && (
        <div style={{ marginBottom: 28, minHeight: 36 }}>
          <Text
            weight="semibold"
            size={300}
            style={{
              display: "block",
              marginBottom: 10,
              textTransform: "uppercase",
              fontSize: 11,
              letterSpacing: "0.04em",
              color: "var(--text-secondary)",
            }}
          >
            Completed ({completed.length})
          </Text>
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {completed.map((j) => (
              <JobCard key={j.id} job={j} />
            ))}
          </div>
        </div>
      )}

      {/* ── History (from SQLite backend) ─────────────────────────── */}
      <div
        style={{
          borderTop: "1px solid var(--border)",
          paddingTop: 20,
          marginTop: allJobs.length > 0 ? 12 : 0,
        }}
      >
        <div
          onClick={() => setShowHistory(!showHistory)}
          style={{
            display: "flex",
            alignItems: "center",
            gap: 8,
            cursor: "pointer",
            marginBottom: showHistory ? 16 : 0,
            userSelect: "none",
          }}
        >
          {showHistory ? <ChevronDown20Regular /> : <ChevronRight20Regular />}
          <Text
            weight="semibold"
            size={300}
            style={{
              textTransform: "uppercase",
              fontSize: 11,
              letterSpacing: "0.04em",
              color: "var(--text-secondary)",
            }}
          >
            Session History
          </Text>
          {historyLoaded && (
            <Badge appearance="tint" size="small" color="informative">
              {sessions.length}
            </Badge>
          )}
        </div>

        {showHistory && (
          <div>
            {/* Search + filter bar */}
            <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 12 }}>
              <Input
                contentBefore={<Search20Regular />}
                placeholder="Search by ID, agent, nickname..."
                value={search}
                onChange={(_, d) => setSearch(d.value)}
                style={{ width: 260 }}
                size="small"
              />
              <TabList
                selectedValue={statusFilter}
                onTabSelect={(_, d) => setStatusFilter(d.value as string)}
                size="small"
              >
                <Tab value="all">All</Tab>
                <Tab value="active">Active</Tab>
                <Tab value="resumable">Resumable</Tab>
                <Tab value="ended">Ended</Tab>
              </TabList>
            </div>

            {/* Column headers */}
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 12,
                padding: "0 16px 8px 48px",
                fontSize: 11,
                fontWeight: 600,
                color: "var(--text-secondary)",
                textTransform: "uppercase",
                letterSpacing: "0.04em",
              }}
            >
              <span style={{ flex: "0 0 80px" }}>ID</span>
              <span style={{ flex: "0 0 150px" }}>Agent</span>
              <span style={{ flex: "0 0 130px" }}>Model</span>
              <span style={{ flex: "0 0 50px", textAlign: "center" }}>Turns</span>
              <span style={{ flex: "0 0 60px", textAlign: "center" }}>Tokens</span>
              <span style={{ flex: "0 0 90px" }}>Duration</span>
              <span style={{ flex: 1 }} />
              <span>Status</span>
            </div>

            {historyLoading ? (
              <div style={{ display: "flex", justifyContent: "center", padding: 40 }}>
                <Spinner size="small" label="Loading history..." />
              </div>
            ) : filteredSessions.length === 0 ? (
              <div style={{ textAlign: "center", padding: "40px 0", color: "var(--text-secondary)" }}>
                <Text size={300}>No sessions found</Text>
              </div>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                {filteredSessions.map((s) => (
                  <HistoryRow
                    key={s.id}
                    session={s}
                    onResume={handleResume}
                    onView={handleViewSession}
                  />
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Brief form slide-over */}
      {briefAgent && (
        <BriefForm
          agent={briefAgent}
          onClose={() => setBriefAgent(null)}
          onJobCreated={(id) => {
            setBriefAgent(null);
            navigate(`/workspace?id=${id}`);
          }}
        />
      )}

      <style>{`
        @keyframes indeterminate {
          0% { transform: translateX(-100%); }
          100% { transform: translateX(250%); }
        }
      `}</style>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* History row (from SQLite sessions)                                  */
/* ------------------------------------------------------------------ */

function historyDuration(startedAt: string, endedAt: string | null): string {
  const start = new Date(startedAt).getTime();
  const end = endedAt ? new Date(endedAt).getTime() : Date.now();
  const sec = Math.round((end - start) / 1000);
  if (sec < 60) return `${sec}s`;
  const m = Math.floor(sec / 60);
  const s = sec % 60;
  return `${m}m ${s}s`;
}

function historyStatusBadge(status: string, resumable: number) {
  if (status === "active") {
    return <Badge appearance="filled" color="success" size="small">Active</Badge>;
  }
  if (resumable) {
    return <Badge appearance="tint" color="informative" size="small">Resumable</Badge>;
  }
  return <Badge appearance="tint" color="subtle" size="small">Ended</Badge>;
}

function HistoryRow({
  session,
  onResume,
  onView,
}: {
  session: SessionInfo;
  onResume: (id: string) => void;
  onView: (id: string) => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const [turns, setTurns] = useState<Turn[]>([]);
  const [loadingTurns, setLoadingTurns] = useState(false);

  const handleExpand = () => {
    if (!expanded && turns.length === 0) {
      setLoadingTurns(true);
      getSessionTurns(session.id)
        .then(setTurns)
        .catch(() => {})
        .finally(() => setLoadingTurns(false));
    }
    setExpanded(!expanded);
  };

  return (
    <Card
      style={{
        border: "1px solid var(--border)",
        borderRadius: 8,
        overflow: "hidden",
      }}
    >
      <div
        onClick={handleExpand}
        style={{
          display: "flex",
          alignItems: "center",
          gap: 12,
          padding: "10px 16px",
          cursor: "pointer",
          transition: "background 0.1s",
        }}
        onMouseEnter={(e) => {
          (e.currentTarget as HTMLElement).style.background = "var(--hover-bg)";
        }}
        onMouseLeave={(e) => {
          (e.currentTarget as HTMLElement).style.background = "transparent";
        }}
      >
        {expanded ? <ChevronDown20Regular /> : <ChevronRight20Regular />}

        <Text
          size={200}
          style={{ fontFamily: "monospace", flex: "0 0 80px", color: "var(--text-secondary)" }}
        >
          {session.id.slice(0, 8)}
        </Text>

        <Text weight="semibold" size={200} style={{ flex: "0 0 150px" }}>
          {session.agent || "copilot"}
        </Text>

        <Text size={200} style={{ color: "var(--text-secondary)", flex: "0 0 130px" }}>
          {session.model ? session.model.split("/").pop()?.slice(0, 15) : "—"}
        </Text>

        <Text size={200} style={{ flex: "0 0 50px", textAlign: "center" }}>
          {session.turn_count}
        </Text>

        <Text size={200} style={{ flex: "0 0 60px", textAlign: "center", color: "var(--text-secondary)" }}>
          {formatTokens(session.total_input_tokens + session.total_output_tokens)}
        </Text>

        <Text size={200} style={{ flex: "0 0 90px", color: "var(--text-secondary)" }}>
          {historyDuration(session.started_at, session.ended_at)}
        </Text>

        <div style={{ flex: 1 }} />
        {historyStatusBadge(session.status, session.resumable)}
      </div>

      {expanded && (
        <div style={{ padding: "0 16px 14px 48px", borderTop: "1px solid var(--border)" }}>
          <div style={{ display: "flex", gap: 20, marginTop: 10, marginBottom: 12, flexWrap: "wrap" }}>
            <Text size={200}>
              <strong>Started:</strong> {new Date(session.started_at).toLocaleString()}
            </Text>
            {session.ended_at && (
              <Text size={200}>
                <strong>Ended:</strong> {new Date(session.ended_at).toLocaleString()}
              </Text>
            )}
            <Text size={200}>
              <strong>Frontend:</strong> {session.frontend}
            </Text>
          </div>

          {loadingTurns && <Spinner size="tiny" label="Loading turns..." />}

          {turns.length > 0 && (
            <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              {turns.map((t) => (
                <div
                  key={t.id}
                  style={{
                    padding: "6px 10px",
                    background: "var(--hover-bg)",
                    borderRadius: 6,
                    fontSize: 12,
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 2 }}>
                    <Badge size="small" color="informative">
                      Turn {t.turn_number}
                    </Badge>
                    <Text size={200} style={{ color: "var(--text-secondary)" }}>
                      {t.agent || "copilot"} · {t.tool_call_count} tools · {t.subagent_count} subagents · {formatTokens(t.input_tokens + t.output_tokens)} tok
                    </Text>
                  </div>
                  <Text
                    size={200}
                    style={{
                      display: "block",
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      whiteSpace: "nowrap",
                    }}
                  >
                    {t.user_prompt || "(system)"}
                  </Text>
                </div>
              ))}
            </div>
          )}

          <div style={{ display: "flex", gap: 8, marginTop: 10 }}>
            <Button appearance="outline" size="small" onClick={() => onView(session.id)}>
              View
            </Button>
            {session.resumable ? (
              <Button
                appearance="primary"
                size="small"
                icon={<Play20Regular />}
                onClick={() => onResume(session.id)}
              >
                Resume
              </Button>
            ) : null}
            <Button
              appearance="subtle"
              icon={<ArrowDownload20Regular />}
              size="small"
              onClick={() => {
                const data = { session, turns };
                const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
                const url = URL.createObjectURL(blob);
                const a = document.createElement("a");
                a.href = url;
                a.download = `session-${session.id.slice(0, 8)}.json`;
                a.click();
                URL.revokeObjectURL(url);
              }}
            >
              Export
            </Button>
          </div>
        </div>
      )}
    </Card>
  );
}
