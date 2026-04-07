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
  SlideText20Regular,
  Code20Regular,
  Document20Regular,
  Settings20Regular,
  DocumentText20Regular,
} from "@fluentui/react-icons";
import { useJobStore, type Job } from "@/stores/jobStore";
import { AGENT_META } from "@/api/types";
import { useState, useEffect } from "react";
import { BriefForm } from "@/components/brief/BriefForm";
import type { AgentType } from "@/api/types";
import type { SessionInfo, Turn } from "@/api/types";
import { AgentIcon } from "@/components/common/AgentIcon";
import { listSessions, getSessionTurns, resumeSession as apiResumeSession, getSessionStatus } from "@/api/client";

function formatElapsed(job: Job): string {
  const ms = (job.completedAt || Date.now()) - job.startedAt;
  const sec = Math.floor(ms / 1000);
  const m = Math.floor(sec / 60);
  const s = sec % 60;
  return `${m}m ${String(s).padStart(2, "0")}s`;
}

function formatTokens(n: number): string {
  if (n >= 1000) return `${(n / 1000).toFixed(0)}k`;
  return String(n);
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

function JobCard({ job }: { job: Job }) {
  const navigate = useNavigate();
  const meta = AGENT_META[job.agent] || { icon: "", label: job.agent, color: "#666" };

  return (
    <Card
      style={{
        border: job.status === "waiting" ? "2px solid #FFB900" : "1px solid #edebe9",
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
          <Text size={200} style={{ color: "var(--text-secondary)", whiteSpace: "nowrap" }}>
            {formatElapsed(job)}
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

        {/* Progress indication for running jobs */}
        {job.status === "running" && (
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
        )}
      </div>

      {/* Waiting indicator */}
      {job.status === "waiting" && job.pendingInput?.[0] && (
        <div
          style={{
            marginTop: 10,
            padding: "8px 12px",
            background: "#fffbf0",
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
          <span>
            {formatTokens(job.usage.inputTokens + job.usage.outputTokens)} tokens
          </span>
          <span>{job.progress.toolCalls} tools</span>
          <span>{job.progress.subagentRuns} subagents</span>
        </div>
      )}

      {/* Output artifacts for completed jobs */}
      {job.status === "completed" && job.outputFiles.filter((f) => !/\/generate_.*\.py$/.test(f)).length > 0 && (
        <div
          style={{
            marginTop: 10,
            padding: "8px 12px",
            background: "linear-gradient(135deg, #f0fff0 0%, #f5fef5 100%)",
            borderRadius: 6,
            border: "1px solid rgba(127, 186, 0, 0.2)",
          }}
        >
          <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
            {job.outputFiles.filter((f) => !/\/generate_.*\.py$/.test(f)).map((f) => {
              const name = f.split("/").pop() || f;
              const ext = name.includes(".") ? name.split(".").pop()?.toLowerCase() : "";
              return (
                <div
                  key={f}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 8,
                    fontSize: 12,
                  }}
                >
                  <span style={{ display: "inline-flex" }}>{fileIcon(ext)}</span>
                  <span
                    style={{
                      flex: 1,
                      fontWeight: 500,
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      whiteSpace: "nowrap",
                    }}
                  >
                    {name}
                  </span>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      const a = document.createElement("a");
                      a.href = `/file/download?path=${encodeURIComponent(f)}`;
                      a.download = name;
                      a.click();
                    }}
                    style={{
                      padding: "1px 7px",
                      fontSize: 10,
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
      )}
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
    <div style={{ padding: "32px 48px", maxWidth: 1000, margin: "0 auto" }}>
      <div
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

      {/* Running */}
      {running.length > 0 && (
        <div style={{ marginBottom: 28 }}>
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
              <JobCard key={j.id} job={j} />
            ))}
          </div>
        </div>
      )}

      {/* Waiting */}
      {waiting.length > 0 && (
        <div style={{ marginBottom: 28 }}>
          <Text
            weight="semibold"
            size={300}
            style={{
              display: "block",
              marginBottom: 10,
              textTransform: "uppercase",
              fontSize: 11,
              letterSpacing: "0.04em",
              color: "#d48806",
            }}
          >
            ⚠️ Waiting for Input ({waiting.length})
          </Text>
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {waiting.map((j) => (
              <JobCard key={j.id} job={j} />
            ))}
          </div>
        </div>
      )}

      {/* Completed */}
      {completed.length > 0 && (
        <div style={{ marginBottom: 28 }}>
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
                padding: "0 16px 8px 40px",
                fontSize: 11,
                fontWeight: 600,
                color: "var(--text-secondary)",
                textTransform: "uppercase",
                letterSpacing: "0.04em",
              }}
            >
              <span style={{ minWidth: 80 }}>ID</span>
              <span style={{ minWidth: 120 }}>Agent</span>
              <span style={{ minWidth: 90 }}>Model</span>
              <span style={{ minWidth: 50, textAlign: "center" }}>Turns</span>
              <span style={{ minWidth: 60 }}>Tokens</span>
              <span style={{ minWidth: 70 }}>Duration</span>
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
          style={{ fontFamily: "monospace", minWidth: 80, color: "var(--text-secondary)" }}
        >
          {session.id.slice(0, 8)}
        </Text>

        <Text weight="semibold" size={200} style={{ minWidth: 120 }}>
          {session.agent || "copilot"}
        </Text>

        <Text size={200} style={{ color: "var(--text-secondary)", minWidth: 90 }}>
          {session.model ? session.model.split("/").pop()?.slice(0, 15) : "—"}
        </Text>

        <Text size={200} style={{ minWidth: 50, textAlign: "center" }}>
          {session.turn_count}
        </Text>

        <Text size={200} style={{ minWidth: 60, color: "var(--text-secondary)" }}>
          {formatTokens(session.total_input_tokens + session.total_output_tokens)}
        </Text>

        <Text size={200} style={{ minWidth: 70, color: "var(--text-secondary)" }}>
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
