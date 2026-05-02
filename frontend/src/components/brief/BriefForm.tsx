import { useState, useCallback, useEffect } from "react";
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
import {
  Dismiss24Regular,
  Building20Regular,
  Checkmark12Regular,
  RocketRegular,
  FolderOpen20Regular,
} from "@fluentui/react-icons";
import {
  AGENT_META,
  CONTENT_LEVELS,
  CONTENT_LEVEL_META,
  DURATIONS,
  PRESENTATION_THEMES,
  type AgentType,
  type ContentLevel,
  type PresentationTheme,
  type GroupedOutput,
} from "@/api/types";
import { createSession, listGroupedOutputs } from "@/api/client";
import { useJobStore, type JobBrief, type Job } from "@/stores/jobStore";
import { AgentIcon } from "@/components/common/AgentIcon";
import {
  WeatherMoon20Regular,
  WeatherSunny20Regular,
} from "@fluentui/react-icons";

/** Agents where the topic field expects longer descriptive text. */
const LONG_TOPIC_AGENTS: Set<AgentType> = new Set([
  "ai-brainstorming",
  "ai-solution-architect",
  "ai-implementor",
  "ai-demo-conductor",
]);

interface BriefFormProps {
  agent: AgentType;
  onClose: () => void;
  onJobCreated: (jobId: string) => void;
  /** Optional initial values to pre-populate from a template. */
  initialBrief?: Partial<{ topic: string; contentLevel: ContentLevel; duration: string; audience: string; notes: string; theme: PresentationTheme }>;
}

export function BriefForm({ agent, onClose, onJobCreated, initialBrief }: BriefFormProps) {
  const meta = AGENT_META[agent];
  const addJob = useJobStore((s) => s.addJob);

  const [topic, setTopic] = useState(initialBrief?.topic || "");
  const [level, setLevel] = useState<ContentLevel>(initialBrief?.contentLevel as ContentLevel || meta.defaultLevel);
  const agentDurations = meta.durationOptions ?? DURATIONS;
  const [duration, setDuration] = useState(initialBrief?.duration || agentDurations[0]);
  const [audience, setAudience] = useState(initialBrief?.audience || "");
  const [notes, setNotes] = useState(initialBrief?.notes || "");
  const [theme, setTheme] = useState<PresentationTheme>(initialBrief?.theme || "light");
  const [submitting, setSubmitting] = useState(false);

  // Close on Escape key
  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [onClose]);

  // Architecture picker state (for ai-implementor)
  const needsArchitecture = agent === "ai-implementor";
  const [architectures, setArchitectures] = useState<GroupedOutput[]>([]);
  const [archLoading, setArchLoading] = useState(false);
  const [selectedArch, setSelectedArch] = useState<GroupedOutput | null>(null);

  // Project picker state (for ai-demo-conductor)
  const needsProject = agent === "ai-demo-conductor";
  const [projects, setProjects] = useState<GroupedOutput[]>([]);
  const [projLoading, setProjLoading] = useState(false);
  const [selectedProject, setSelectedProject] = useState<GroupedOutput | null>(null);

  useEffect(() => {
    if (!needsArchitecture) return;
    setArchLoading(true);
    listGroupedOutputs()
      .then((all) => setArchitectures(
        all.filter((g) => {
          if (g.category !== "ai-projects") return false;
          // Use has_architecture flag if available; fall back to file-name scan
          if (typeof g.has_architecture === "boolean") return g.has_architecture;
          return g.files.some((f) =>
            f.includes("solution-design") || f.includes("architecture-diagram") || f.includes("architecture.md")
          );
        })
      ))
      .catch(() => {})
      .finally(() => setArchLoading(false));
  }, [needsArchitecture]);

  useEffect(() => {
    if (!needsProject) return;
    setProjLoading(true);
    listGroupedOutputs()
      .then((all) => setProjects(
        all.filter((g) => g.category === "ai-projects" && g.has_solution === true)
      ))
      .catch(() => {})
      .finally(() => setProjLoading(false));
  }, [needsProject]);

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
        theme: meta.showTheme ? theme : undefined,
        architecturePath: selectedArch?.primary_file
          ? selectedArch.primary_file
          : undefined,
        architectureDocs: selectedArch?.architecture_docs?.length
          ? selectedArch.architecture_docs
          : undefined,
        projectPath: selectedProject?.primary_file
          ? selectedProject.primary_file
          : undefined,
        projectDocs: selectedProject?.files?.length
          ? selectedProject.files
          : undefined,
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
  }, [topic, level, duration, audience, notes, theme, agent, addJob, onJobCreated]);

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
              {meta.topicLabel || "Topic"} *
            </Text>
            {LONG_TOPIC_AGENTS.has(agent) ? (
              <Textarea
                value={topic}
                onChange={(_, d) => setTopic(d.value)}
                placeholder={meta.topicPlaceholder || "e.g. KEDA autoscaling for banking workloads"}
                style={{ width: "100%" }}
                rows={4}
                autoFocus
              />
            ) : (
              <Input
                value={topic}
                onChange={(_, d) => setTopic(d.value)}
                placeholder={meta.topicPlaceholder || "e.g. KEDA autoscaling for banking workloads"}
                style={{ width: "100%" }}
                autoFocus
              />
            )}
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
              {CONTENT_LEVELS.filter((l) => (agent !== "hackathon-conductor" && agent !== "demo-conductor") || l !== "L100").map((l) => (
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
              onOptionSelect={(_, d) => setDuration(d.optionValue || agentDurations[0])}
              style={{ width: "100%" }}
            >
              {agentDurations.map((d) => (
                <Option key={d} value={d}>
                  {d}
                </Option>
              ))}
            </Dropdown>
          </div>
          )}

          {/* Layout Theme — only for slide-conductor */}
          {meta.showTheme && (
          <div>
            <Text
              weight="semibold"
              size={300}
              style={{ display: "block", marginBottom: 8 }}
            >
              Layout Theme
            </Text>
            <div style={{ display: "flex", gap: 8 }}>
              {PRESENTATION_THEMES.map((t) => {
                const isActive = theme === t;
                return (
                  <button
                    key={t}
                    onClick={() => setTheme(t)}
                    style={{
                      flex: 1,
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      gap: 6,
                      padding: "8px 12px",
                      borderRadius: 8,
                      border: isActive ? "2px solid var(--brand-primary)" : "1px solid var(--border)",
                      background: isActive
                        ? t === "dark" ? "#1A1C23" : "rgba(0,120,212,0.06)"
                        : t === "dark" ? "#1A1C23" : "var(--card-bg)",
                      color: t === "dark" ? "#E8E8E8" : "var(--text-primary)",
                      cursor: "pointer",
                      fontWeight: isActive ? 600 : 400,
                      fontSize: 13,
                      transition: "all 0.15s ease",
                    }}
                  >
                    {t === "light" ? (
                      <WeatherSunny20Regular style={{ color: "#F7A600", flexShrink: 0 }} />
                    ) : (
                      <WeatherMoon20Regular style={{ color: "#8B9DC3", flexShrink: 0 }} />
                    )}
                    {t.charAt(0).toUpperCase() + t.slice(1)}
                  </button>
                );
              })}
            </div>
          </div>
          )}

          {/* Architecture picker — only for ai-implementor */}
          {needsArchitecture && (
            <div>
              <Text
                weight="semibold"
                size={300}
                style={{ display: "block", marginBottom: 6 }}
              >
                Architecture *
              </Text>
              <Text
                size={200}
                style={{ display: "block", marginBottom: 10, color: "var(--text-secondary)" }}
              >
                Select an existing architecture to build from
              </Text>

              {archLoading && (
                <div style={{ padding: 16, textAlign: "center" }}>
                  <Spinner size="small" label="Loading architectures…" />
                </div>
              )}

              {!archLoading && architectures.length === 0 && (
                <div
                  style={{
                    padding: "16px",
                    background: "var(--bg-warning)",
                    borderRadius: 8,
                    border: "1px solid rgba(255, 185, 0, 0.3)",
                    fontSize: 13,
                    color: "var(--text-primary)",
                  }}
                >
                  <span style={{ marginRight: 6 }}>⚠️</span>
                  No architectures found. Use <strong>Architect a Solution</strong> first to
                  create one, then come back here.
                </div>
              )}

              {!archLoading && architectures.length > 0 && (
                <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                  {architectures.map((arch) => {
                    const isSelected = selectedArch?.id === arch.id;
                    const archDocCount = arch.architecture_docs?.length || 0;
                    return (
                      <div
                        key={arch.id}
                        onClick={() => setSelectedArch(isSelected ? null : arch)}
                        style={{
                          padding: "10px 14px",
                          borderRadius: 8,
                          border: isSelected
                            ? "2px solid var(--brand-primary)"
                            : "1px solid var(--border)",
                          background: isSelected
                            ? "rgba(0, 120, 212, 0.06)"
                            : "var(--card-bg)",
                          cursor: "pointer",
                          transition: "all 0.15s ease",
                        }}
                      >
                        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                          <Building20Regular style={{ color: "#8661C5", flexShrink: 0 }} />
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
                              {arch.title}
                            </Text>
                            <Text
                              size={200}
                              style={{ color: "var(--text-secondary)", display: "block" }}
                            >
                              {archDocCount} design doc{archDocCount !== 1 ? "s" : ""} · {arch.file_count} files total
                            </Text>
                          </div>
                          {isSelected && (
                            <span
                              style={{
                                width: 20,
                                height: 20,
                                borderRadius: "50%",
                                background: "var(--brand-primary)",
                                color: "white",
                                display: "flex",
                                alignItems: "center",
                                justifyContent: "center",
                                flexShrink: 0,
                              }}
                            >
                              <Checkmark12Regular />
                            </span>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          )}

          {/* Project picker — only for ai-demo-conductor */}
          {needsProject && (
            <div>
              <Text
                weight="semibold"
                size={300}
                style={{ display: "block", marginBottom: 6 }}
              >
                Project *
              </Text>
              <Text
                size={200}
                style={{ display: "block", marginBottom: 10, color: "var(--text-secondary)" }}
              >
                Select an existing built project to create demos from
              </Text>

              {projLoading && (
                <div style={{ padding: 16, textAlign: "center" }}>
                  <Spinner size="small" label="Loading projects…" />
                </div>
              )}

              {!projLoading && projects.length === 0 && (
                <div
                  style={{
                    padding: "16px",
                    background: "var(--bg-warning)",
                    borderRadius: 8,
                    border: "1px solid rgba(255, 185, 0, 0.3)",
                    fontSize: 13,
                    color: "var(--text-primary)",
                  }}
                >
                  <span style={{ marginRight: 6 }}>⚠️</span>
                  No projects found. Use <strong>Build an AI Project</strong> first to
                  create one, then come back here.
                </div>
              )}

              {!projLoading && projects.length > 0 && (
                <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                  {projects.map((proj) => {
                    const isSelected = selectedProject?.id === proj.id;
                    return (
                      <div
                        key={proj.id}
                        onClick={() => setSelectedProject(isSelected ? null : proj)}
                        style={{
                          padding: "10px 14px",
                          borderRadius: 8,
                          border: isSelected
                            ? "2px solid var(--brand-primary)"
                            : "1px solid var(--border)",
                          background: isSelected
                            ? "rgba(0, 120, 212, 0.06)"
                            : "var(--card-bg)",
                          cursor: "pointer",
                          transition: "all 0.15s ease",
                        }}
                      >
                        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                          <FolderOpen20Regular style={{ color: "#F25022", flexShrink: 0 }} />
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
                              {proj.title}
                            </Text>
                            <Text
                              size={200}
                              style={{ color: "var(--text-secondary)", display: "block" }}
                            >
                              {proj.file_count} files
                            </Text>
                          </div>
                          {isSelected && (
                            <span
                              style={{
                                width: 20,
                                height: 20,
                                borderRadius: "50%",
                                background: "var(--brand-primary)",
                                color: "white",
                                display: "flex",
                                alignItems: "center",
                                justifyContent: "center",
                                flexShrink: 0,
                              }}
                            >
                              <Checkmark12Regular />
                            </span>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          )}

          {/* Audience — only for presentation-style agents */}
          {meta.showAudience && (
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
          )}

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
            disabled={!topic.trim() || submitting || (needsArchitecture && !selectedArch) || (needsProject && !selectedProject)}
            style={{
              width: "100%",
              height: 44,
              fontSize: 15,
              fontWeight: 600,
              borderRadius: 8,
            }}
          >
            {submitting ? <Spinner size="tiny" /> : <><RocketRegular style={{ marginRight: 6 }} />Generate</>}
          </Button>
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
