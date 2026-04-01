import { useState, useCallback } from "react";
import {
  Text,
  Button,
  Input,
  Textarea,
  RadioGroup,
  Radio,
  Dropdown,
  Option,
  Spinner,
} from "@fluentui/react-components";
import { Dismiss24Regular } from "@fluentui/react-icons";
import {
  AGENT_META,
  CONTENT_LEVELS,
  CONTENT_LEVEL_META,
  DURATIONS,
  type AgentType,
  type ContentLevel,
} from "@/api/types";
import { createSession } from "@/api/client";
import { useJobStore, type JobBrief, type Job } from "@/stores/jobStore";
import { AgentIcon } from "@/components/common/AgentIcon";

interface BriefFormProps {
  agent: AgentType;
  onClose: () => void;
  onJobCreated: (jobId: string) => void;
}

export function BriefForm({ agent, onClose, onJobCreated }: BriefFormProps) {
  const meta = AGENT_META[agent];
  const addJob = useJobStore((s) => s.addJob);

  const [topic, setTopic] = useState("");
  const [level, setLevel] = useState<ContentLevel>(meta.defaultLevel);
  const [duration, setDuration] = useState("30 min");
  const [audience, setAudience] = useState("");
  const [notes, setNotes] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = useCallback(async () => {
    if (!topic.trim()) return;
    setSubmitting(true);

    try {
      const res = await createSession(agent);

      const brief: JobBrief = {
        topic: topic.trim(),
        contentLevel: level,
        duration,
        audience: audience.trim() || undefined,
        notes: notes.trim() || undefined,
      };

      const titleParts = [topic.trim()];
      if (meta.showContentLevel) titleParts.push(level);
      if (meta.showDuration) titleParts.push(duration);

      const job: Job = {
        id: res.session_id,
        title: titleParts.join(" "),
        agent,
        brief,
        status: "queued",
        phase: "researching",
        startedAt: Date.now(),
        progress: { toolCalls: 0, subagentRuns: 0, currentStep: "Queued" },
        events: [],
        outputFiles: [],
        usage: { inputTokens: 0, outputTokens: 0, estimatedCostUsd: 0 },
      };

      addJob(job);
      onJobCreated(res.session_id);
    } catch (e: any) {
      alert(`Failed to create session: ${e.message}`);
    } finally {
      setSubmitting(false);
    }
  }, [topic, level, duration, audience, notes, agent, addJob, onJobCreated]);

  return (
    <>
      {/* Backdrop */}
      <div
        onClick={onClose}
        style={{
          position: "fixed",
          inset: 0,
          background: "rgba(0,0,0,0.25)",
          zIndex: 200,
          animation: "fadeIn 0.2s ease",
        }}
      />

      {/* Panel */}
      <div
        style={{
          position: "fixed",
          top: 0,
          right: 0,
          bottom: 0,
          width: 420,
          maxWidth: "90vw",
          background: "var(--card-bg)",
          zIndex: 201,
          boxShadow: "-8px 0 32px rgba(0,0,0,0.1)",
          display: "flex",
          flexDirection: "column",
          animation: "slideInRight 0.25s ease",
        }}
      >
        {/* Header */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            padding: "20px 24px 16px",
            borderBottom: "1px solid var(--border)",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <AgentIcon agent={agent} size="inline" />
            <Text weight="semibold" size={500}>
              {meta.label}
            </Text>
          </div>
          <Button
            appearance="subtle"
            icon={<Dismiss24Regular />}
            onClick={onClose}
          />
        </div>

        {/* Form */}
        <div
          style={{
            flex: 1,
            overflow: "auto",
            padding: "20px 24px",
            display: "flex",
            flexDirection: "column",
            gap: 20,
          }}
        >
          {/* Topic */}
          <div>
            <Text
              weight="semibold"
              size={300}
              style={{ display: "block", marginBottom: 6 }}
            >
              Topic *
            </Text>
            <Input
              value={topic}
              onChange={(_, d) => setTopic(d.value)}
              placeholder="e.g. KEDA autoscaling for banking workloads"
              style={{ width: "100%" }}
              autoFocus
            />
          </div>

          {/* Content Level — only for slides, demos, hackathons */}
          {meta.showContentLevel && (
          <div>
            <Text
              weight="semibold"
              size={300}
              style={{ display: "block", marginBottom: 6 }}
            >
              Content Level
            </Text>
            <RadioGroup
              value={level}
              onChange={(_, d) => setLevel(d.value as ContentLevel)}
            >
              {CONTENT_LEVELS.map((l) => (
                <Radio
                  key={l}
                  value={l}
                  label={
                    <span>
                      <span
                        style={{
                          display: "inline-block",
                          width: 10,
                          height: 10,
                          borderRadius: "50%",
                          background: CONTENT_LEVEL_META[l].color,
                          marginRight: 8,
                          verticalAlign: "middle",
                        }}
                      />
                      {l} — {CONTENT_LEVEL_META[l].meaning}
                    </span>
                  }
                />
              ))}
            </RadioGroup>
          </div>
          )}

          {/* Duration — only for time-bound outputs */}
          {meta.showDuration && (
          <div>
            <Text
              weight="semibold"
              size={300}
              style={{ display: "block", marginBottom: 6 }}
            >
              Duration
            </Text>
            <Dropdown
              value={duration}
              onOptionSelect={(_, d) => setDuration(d.optionValue || "30 min")}
              style={{ width: "100%" }}
            >
              {DURATIONS.map((d) => (
                <Option key={d} value={d}>
                  {d}
                </Option>
              ))}
            </Dropdown>
          </div>
          )}

          {/* Audience */}
          <div>
            <Text
              weight="semibold"
              size={300}
              style={{ display: "block", marginBottom: 6 }}
            >
              Audience{" "}
              <span style={{ fontWeight: 400, color: "var(--text-secondary)" }}>
                (optional)
              </span>
            </Text>
            <Input
              value={audience}
              onChange={(_, d) => setAudience(d.value)}
              placeholder="e.g. Banking IT architects"
              style={{ width: "100%" }}
            />
          </div>

          {/* Notes */}
          <div>
            <Text
              weight="semibold"
              size={300}
              style={{ display: "block", marginBottom: 6 }}
            >
              Special Instructions{" "}
              <span style={{ fontWeight: 400, color: "var(--text-secondary)" }}>
                (optional)
              </span>
            </Text>
            <Textarea
              value={notes}
              onChange={(_, d) => setNotes(d.value)}
              placeholder="e.g. Focus on Azure Service Bus triggers, include cost comparison with VMs"
              style={{ width: "100%" }}
              rows={3}
            />
          </div>
        </div>

        {/* Footer */}
        <div
          style={{
            padding: "16px 24px",
            borderTop: "1px solid var(--border)",
            display: "flex",
            flexDirection: "column",
            gap: 10,
          }}
        >
          <Button
            appearance="primary"
            size="large"
            onClick={handleSubmit}
            disabled={!topic.trim() || submitting}
            style={{
              width: "100%",
              height: 44,
              fontSize: 15,
              fontWeight: 600,
              borderRadius: 8,
            }}
          >
            {submitting ? <Spinner size="tiny" /> : "🚀 Generate"}
          </Button>
          <Text
            size={200}
            style={{
              color: "var(--text-secondary)",
              textAlign: "center",
            }}
          >
            Estimated time: 8-15 min · Cost: ~$0.30-$1.00
          </Text>
        </div>
      </div>

      <style>{`
        @keyframes slideInRight {
          from { transform: translateX(100%); }
          to { transform: translateX(0); }
        }
        @keyframes fadeIn {
          from { opacity: 0; }
          to { opacity: 1; }
        }
      `}</style>
    </>
  );
}
