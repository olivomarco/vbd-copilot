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
} from "@fluentui/react-components";
import { Add20Regular, Delete20Regular } from "@fluentui/react-icons";
import { useJobStore, type Job } from "@/stores/jobStore";
import { AGENT_META } from "@/api/types";
import { useState } from "react";
import { BriefForm } from "@/components/brief/BriefForm";
import type { AgentType } from "@/api/types";
import { AgentIcon } from "@/components/common/AgentIcon";

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

function JobCard({ job }: { job: Job }) {
  const navigate = useNavigate();
  const meta = AGENT_META[job.agent] || { icon: "🔧", label: job.agent, color: "#666" };

  const statusColor =
    job.status === "running"
      ? "brand"
      : job.status === "waiting"
        ? "warning"
        : job.status === "completed"
          ? "success"
          : job.status === "failed"
            ? "danger"
            : "subtle";

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
      <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
        <AgentIcon agent={job.agent} size="inline" />
        <div style={{ flex: 1 }}>
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
          <Text size={200} style={{ color: "var(--text-secondary)" }}>
            {job.agent} · {job.progress.currentStep}
          </Text>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <Text size={200} style={{ color: "var(--text-secondary)" }}>
            {formatElapsed(job)}
          </Text>
          <Badge size="small" color={statusColor}>
            {job.status}
          </Badge>
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
      {job.status === "waiting" && job.pendingInput && (
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
          <span>⚠️ {job.pendingInput.question.slice(0, 60)}</span>
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
          {job.outputFiles.length > 0 && (
            <span>{job.outputFiles.length} file(s)</span>
          )}
        </div>
      )}
    </Card>
  );
}

export function MissionControl() {
  const navigate = useNavigate();
  const jobs = useJobStore((s) => s.jobs);
  const allJobs = Object.values(jobs);
  const [briefAgent, setBriefAgent] = useState<AgentType | null>(null);

  const running = allJobs.filter((j) => j.status === "running" || j.status === "queued");
  const waiting = allJobs.filter((j) => j.status === "waiting");
  const completed = allJobs.filter(
    (j) => j.status === "completed" || j.status === "failed" || j.status === "cancelled",
  );

  // Sort by most recent first
  completed.sort((a, b) => (b.completedAt || 0) - (a.completedAt || 0));

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

      {allJobs.length === 0 && (
        <div
          style={{
            textAlign: "center",
            padding: "80px 0",
            color: "var(--text-secondary)",
          }}
        >
          <Text size={500} style={{ display: "block", marginBottom: 8 }}>
            No active jobs
          </Text>
          <Text size={300} style={{ display: "block", marginBottom: 20 }}>
            Launch your first content generation from the Launchpad
          </Text>
          <Button appearance="primary" onClick={() => navigate("/")}>
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
