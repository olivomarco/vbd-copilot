import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Text,
  Button,
  Card,
  Spinner,
  Badge,
  Input,
  TabList,
  Tab,
} from "@fluentui/react-components";
import {
  ChevronDown20Regular,
  ChevronRight20Regular,
  ArrowDownload20Regular,
  Search20Regular,
  Play20Regular,
} from "@fluentui/react-icons";
import { listSessions, getSessionTurns, resumeSession as apiResumeSession } from "@/api/client";
import type { SessionInfo, Turn } from "@/api/types";
import { useJobStore, type Job } from "@/stores/jobStore";

function formatDuration(startedAt: string, endedAt: string | null): string {
  const start = new Date(startedAt).getTime();
  const end = endedAt ? new Date(endedAt).getTime() : Date.now();
  const sec = Math.round((end - start) / 1000);
  if (sec < 60) return `${sec}s`;
  const m = Math.floor(sec / 60);
  const s = sec % 60;
  return `${m}m ${s}s`;
}

function formatTokens(n: number): string {
  if (n >= 1000) return `${(n / 1000).toFixed(0)}k`;
  return String(n);
}

function statusBadge(status: string, resumable: number) {
  if (status === "active") {
    return <Badge appearance="filled" color="success" size="small">Active</Badge>;
  }
  if (resumable) {
    return <Badge appearance="tint" color="informative" size="small">Resumable</Badge>;
  }
  return <Badge appearance="tint" color="subtle" size="small">Ended</Badge>;
}

function SessionRow({ session, onResume, onView }: { session: SessionInfo; onResume: (id: string) => void; onView: (id: string) => void }) {
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
      {/* Row header */}
      <div
        onClick={handleExpand}
        style={{
          display: "flex",
          alignItems: "center",
          gap: 12,
          padding: "12px 16px",
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
          {session.id.slice(0, 8)}..
        </Text>

        <Text weight="semibold" size={300} style={{ minWidth: 140 }}>
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
          {formatDuration(session.started_at, session.ended_at)}
        </Text>

        <div style={{ flex: 1 }} />
        {statusBadge(session.status, session.resumable)}
      </div>

      {/* Expanded details */}
      {expanded && (
        <div
          style={{
            padding: "0 16px 16px 48px",
            borderTop: "1px solid var(--border-subtle)",
          }}
        >
          <div style={{ display: "flex", gap: 24, marginTop: 12, marginBottom: 16, flexWrap: "wrap" }}>
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
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {turns.map((t) => (
                <div
                  key={t.id}
                  style={{
                    padding: "8px 12px",
                    background: "var(--hover-bg)",
                    borderRadius: 6,
                    fontSize: 13,
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
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

          <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
            <Button
              appearance="outline"
              size="small"
              onClick={() => onView(session.id)}
            >
              View
            </Button>
            {session.resumable ? (
              <Button
                appearance="primary"
                size="small"
                icon={<Play20Regular />}
                onClick={() => onResume(session.id)}
              >
                Resume Session
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
              Export JSON
            </Button>
          </div>
        </div>
      )}
    </Card>
  );
}

export function Sessions() {
  const navigate = useNavigate();
  const [sessions, setSessions] = useState<SessionInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const addJob = useJobStore((s) => s.addJob);

  useEffect(() => {
    setLoading(true);
    listSessions(true)
      .then(setSessions)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const handleResume = async (sessionId: string) => {
    try {
      const res = await apiResumeSession(sessionId);
      const job: Job = {
        id: res.session_id,
        title: `Resumed: ${res.agent || "session"}`,
        agent: (res.agent || "slide-conductor") as any,
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

  const handleView = (sessionId: string) => {
    // If this session is already a job, navigate to workspace
    const existing = useJobStore.getState().getJob(sessionId);
    if (existing) {
      navigate(`/workspace?id=${sessionId}`);
      return;
    }
    // Otherwise create a job entry from the session info so it's visible
    const session = sessions.find((s) => s.id === sessionId);
    if (!session) return;
    const job: Job = {
      id: session.id,
      title: session.agent || "Session",
      agent: (session.agent || "slide-conductor") as any,
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

  const filtered = sessions.filter((s) => {
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
    <div className="page-container" style={{ padding: "32px 48px", maxWidth: 1200, margin: "0 auto" }}>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          marginBottom: 24,
        }}
      >
        <Text as="h1" size={700} weight="bold" style={{ letterSpacing: "-0.03em" }}>
          Sessions
        </Text>
        <Input
          contentBefore={<Search20Regular />}
          placeholder="Search by ID, agent, nickname..."
          value={search}
          onChange={(_, d) => setSearch(d.value)}
          style={{ width: 260 }}
        />
      </div>

      {/* Filter tabs */}
      <TabList
        selectedValue={statusFilter}
        onTabSelect={(_, d) => setStatusFilter(d.value as string)}
        size="small"
        style={{ marginBottom: 16 }}
      >
        <Tab value="all">All ({sessions.length})</Tab>
        <Tab value="active">Active ({sessions.filter((s) => s.status === "active").length})</Tab>
        <Tab value="resumable">Resumable ({sessions.filter((s) => s.resumable).length})</Tab>
        <Tab value="ended">Ended ({sessions.filter((s) => s.status === "ended" && !s.resumable).length})</Tab>
      </TabList>

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
        <span style={{ minWidth: 140 }}>Agent</span>
        <span style={{ minWidth: 90 }}>Model</span>
        <span style={{ minWidth: 50, textAlign: "center" }}>Turns</span>
        <span style={{ minWidth: 60 }}>Tokens</span>
        <span style={{ minWidth: 70 }}>Duration</span>
        <span style={{ flex: 1 }} />
        <span>Status</span>
      </div>

      {loading ? (
        <div style={{ display: "flex", justifyContent: "center", padding: 64 }}>
          <Spinner label="Loading sessions..." />
        </div>
      ) : filtered.length === 0 ? (
        <div
          style={{
            textAlign: "center",
            padding: "80px 0",
            color: "var(--text-secondary)",
          }}
        >
          <Text size={400}>No sessions found</Text>
        </div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
          {filtered.map((s) => (
            <SessionRow key={s.id} session={s} onResume={handleResume} onView={handleView} />
          ))}
        </div>
      )}
    </div>
  );
}
