import { useNavigate } from "react-router-dom";
import { Text, Card, Button, Badge, Tooltip } from "@fluentui/react-components";
import { ArrowRight16Regular, ChevronLeft20Regular, ChevronRight20Regular, LockClosed16Regular } from "@fluentui/react-icons";
import { AGENT_META, type AgentType, type ContentLevel } from "@/api/types";
import { useOutputStore } from "@/stores/outputStore";
import React, { useEffect, useState, useRef, useCallback } from "react";
import { BriefForm } from "@/components/brief/BriefForm";
import { listGroupedOutputs } from "@/api/client";
import { AgentIcon } from "@/components/common/AgentIcon";

const AGENTS = Object.entries(AGENT_META) as [AgentType, (typeof AGENT_META)[AgentType]][];

const CONTENT_AGENTS: AgentType[] = ["slide-conductor", "demo-conductor", "hackathon-conductor"];
const PIPELINE_AGENTS: AgentType[] = ["ai-brainstorming", "ai-solution-architect", "ai-implementor", "ai-demo-conductor"];

interface Template {
  title: string;
  agent: AgentType;
  brief: { topic: string; contentLevel: ContentLevel; duration: string; notes?: string };
}

const TEMPLATES: Template[] = [
  {
    title: "Quick AKS Overview",
    agent: "slide-conductor",
    brief: { topic: "Azure Kubernetes Service overview", contentLevel: "L100", duration: "15 min" },
  },
  {
    title: "GitHub Copilot Deep Dive",
    agent: "slide-conductor",
    brief: { topic: "GitHub Copilot for enterprise developers", contentLevel: "L300", duration: "1 hour" },
  },
  {
    title: "KEDA Autoscaling Demo",
    agent: "demo-conductor",
    brief: { topic: "KEDA event-driven autoscaling on AKS", contentLevel: "L300", duration: "30 min" },
  },
  {
    title: "Azure AI Hackathon",
    agent: "hackathon-conductor",
    brief: { topic: "Building intelligent apps with Azure AI Services", contentLevel: "L300", duration: "2 hours" },
  },
  {
    title: "Container Apps Architecture",
    agent: "slide-conductor",
    brief: { topic: "Azure Container Apps microservices architecture", contentLevel: "L200", duration: "30 min" },
  },
  {
    title: "RAG Chatbot on Azure",
    agent: "ai-solution-architect",
    brief: { topic: "RAG chatbot using Azure OpenAI and AI Search", contentLevel: "L300", duration: "1 hour" },
  },
];

export function Launchpad() {
  const navigate = useNavigate();
  const outputs = useOutputStore((s) => s.outputs);
  const fetchOutputs = useOutputStore((s) => s.fetch);
  const [briefAgent, setBriefAgent] = useState<AgentType | null>(null);
  const [briefInitial, setBriefInitial] = useState<Partial<{ topic: string; contentLevel: ContentLevel; duration: string; notes: string }> | undefined>(undefined);
  const carouselRef = useRef<HTMLDivElement>(null);
  const [hasArchitectures, setHasArchitectures] = useState<boolean | null>(null); // null = loading
  const [hasProjects, setHasProjects] = useState<boolean | null>(null); // null = loading

  const scrollCarousel = useCallback((direction: "left" | "right") => {
    const el = carouselRef.current;
    if (!el) return;
    const amount = 220;
    el.scrollBy({ left: direction === "right" ? amount : -amount, behavior: "smooth" });
  }, []);

  useEffect(() => {
    fetchOutputs();
    // Check if any architecture-ready projects exist and if any projects are built
    listGroupedOutputs()
      .then((all) => {
        const archReady = all.some((g) => g.category === "ai-projects" && g.has_architecture);
        setHasArchitectures(archReady);
        const projectsExist = all.some((g) => g.category === "ai-projects" && g.file_count > 0);
        setHasProjects(projectsExist);
      })
      .catch(() => { setHasArchitectures(false); setHasProjects(false); });
  }, []);

  const recentOutputs = outputs.slice(0, 6);

  return (
    <div style={{ padding: "40px 48px", maxWidth: 1200, margin: "0 auto" }}>
      {/* Hero */}
      <div
        data-tutorial="launchpad-hero"
        className="animate-in"
        style={{
          display: "flex",
          alignItems: "center",
          gap: 16,
          marginBottom: 40,
        }}
      >
        <div
          style={{
            width: 48,
            height: 48,
            display: "grid",
            gridTemplateColumns: "1fr 1fr",
            gridTemplateRows: "1fr 1fr",
            gap: 3,
            flexShrink: 0,
          }}
        >
          <div style={{ background: "#F25022", borderRadius: 3 }} />
          <div style={{ background: "#7FBA00", borderRadius: 3 }} />
          <div style={{ background: "#00A4EF", borderRadius: 3 }} />
          <div style={{ background: "#FFB900", borderRadius: 3 }} />
        </div>
        <div>
          <Text
            as="h1"
            size={800}
            weight="bold"
            style={{ display: "block", letterSpacing: "-0.03em", lineHeight: 1.1 }}
          >
            CSA Copilot
          </Text>
          <Text
            size={300}
            style={{ color: "var(--text-secondary)", display: "block", marginTop: 2 }}
          >
            The ultimate content factory for Microsoft Cloud Solution Architects
          </Text>
        </div>
      </div>

      {/* ── Content Tools Section ── */}
      <Text
        as="h2"
        size={500}
        weight="semibold"
        style={{ display: "block", marginBottom: 16, letterSpacing: "-0.01em" }}
      >
        Content Tools
      </Text>

      <div
        data-tutorial="content-tools"
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(3, 1fr)",
          gap: 16,
          marginBottom: 40,
        }}
      >
        {CONTENT_AGENTS.map((key, i) => {
          const meta = AGENT_META[key];
          return (
            <Card
              key={key}
              className="animate-in"
              style={{
                animationDelay: `${i * 60}ms`,
                padding: 0,
                border: "1px solid var(--border)",
                borderRadius: 12,
                cursor: "pointer",
                transition: "all 0.2s ease",
                overflow: "hidden",
              }}
              onClick={() => setBriefAgent(key)}
              onMouseEnter={(e) => {
                (e.currentTarget as HTMLElement).style.transform = "translateY(-2px)";
                (e.currentTarget as HTMLElement).style.boxShadow = "0 8px 24px rgba(0,0,0,0.08)";
                (e.currentTarget as HTMLElement).style.borderColor = meta.color;
              }}
              onMouseLeave={(e) => {
                (e.currentTarget as HTMLElement).style.transform = "translateY(0)";
                (e.currentTarget as HTMLElement).style.boxShadow = "none";
                (e.currentTarget as HTMLElement).style.borderColor = "var(--border)";
              }}
            >
              <div style={{ height: 4, background: meta.color }} />
              <div style={{ padding: "28px 28px 32px" }}>
                <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: 18 }}>
                  <AgentIcon agent={key} size="large" />
                  {meta.beta && (
                    <Badge size="small" appearance="tint" color="warning" style={{ fontWeight: 700, fontSize: 10, letterSpacing: "0.05em", textTransform: "uppercase" }}>Beta</Badge>
                  )}
                </div>
                <Text weight="semibold" size={500} style={{ display: "block", marginBottom: 8, letterSpacing: "-0.01em" }}>
                  {meta.label}
                </Text>
                <Text size={300} style={{ color: "var(--text-secondary)", display: "block", lineHeight: 1.5 }}>
                  {meta.description}
                </Text>
              </div>
            </Card>
          );
        })}
      </div>

      {/* ── AI Project Workflow Section ── */}
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 6 }}>
        <Text
          as="h2"
          size={500}
          weight="semibold"
          style={{ letterSpacing: "-0.01em" }}
        >
          AI Project Workflow
        </Text>
        <Badge size="small" appearance="tint" color="warning" style={{ fontWeight: 700, fontSize: 10, letterSpacing: "0.05em", textTransform: "uppercase" }}>Beta</Badge>
      </div>

      <Text
        size={200}
        style={{ display: "block", color: "var(--text-secondary)", marginBottom: 16, lineHeight: 1.5 }}
      >
        Each step builds on the previous — brainstorm ideas, then architect, build, and demo your solution.
      </Text>

      <div
        data-tutorial="ai-workflow"
        style={{
          display: "flex",
          alignItems: "stretch",
          marginBottom: 48,
        }}
      >
          {PIPELINE_AGENTS.map((key, i) => {
            const meta = AGENT_META[key];
            const isImplementor = key === "ai-implementor";
            const isDemoConductor = key === "ai-demo-conductor";
            const locked = (isImplementor && hasArchitectures === false) || (isDemoConductor && hasProjects === false);
            const stepNum = i + 1;

            const cardEl = (
              <Card
                className="animate-in"
                style={{
                  animationDelay: `${i * 60}ms`,
                  padding: 0,
                  border: "1px solid var(--border)",
                  borderRadius: 12,
                  cursor: locked ? "not-allowed" : "pointer",
                  transition: "all 0.2s ease",
                  overflow: "hidden",
                  opacity: locked ? 0.45 : 1,
                  filter: locked ? "grayscale(100%)" : "none",
                  background: locked ? "var(--colorNeutralBackground3)" : "var(--card-bg)",
                  flex: 1,
                  minWidth: 0,
                }}
                onClick={() => { if (!locked) setBriefAgent(key); }}
                onMouseEnter={(e) => {
                  if (locked) return;
                  (e.currentTarget as HTMLElement).style.transform = "translateY(-2px)";
                  (e.currentTarget as HTMLElement).style.boxShadow = "0 8px 24px rgba(0,0,0,0.08)";
                  (e.currentTarget as HTMLElement).style.borderColor = meta.color;
                }}
                onMouseLeave={(e) => {
                  if (locked) return;
                  (e.currentTarget as HTMLElement).style.transform = "translateY(0)";
                  (e.currentTarget as HTMLElement).style.boxShadow = "none";
                  (e.currentTarget as HTMLElement).style.borderColor = "var(--border)";
                }}
              >
                <div style={{ height: 4, background: meta.color }} />
                <div style={{ padding: "24px 20px 28px" }}>
                  <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: 14 }}>
                    <AgentIcon agent={key} size="large" />
                    <div
                      style={{
                        width: 24,
                        height: 24,
                        borderRadius: "50%",
                        background: locked ? "#edebe9" : meta.color,
                        color: locked ? "#a19f9d" : "#fff",
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        fontSize: 12,
                        fontWeight: 700,
                        flexShrink: 0,
                      }}
                    >
                      {stepNum}
                    </div>
                  </div>
                  <Text weight="semibold" size={400} style={{ display: "block", marginBottom: 6, letterSpacing: "-0.01em" }}>
                    {meta.label}
                  </Text>
                  <Text size={200} style={{ color: "var(--text-secondary)", display: "block", lineHeight: 1.5 }}>
                    {meta.description}
                  </Text>

                  {locked && (
                    <div
                      style={{
                        marginTop: 10,
                        padding: "6px 10px",
                        background: "rgba(0,0,0,0.06)",
                        borderRadius: 6,
                        fontSize: 11,
                        color: "var(--text-secondary)",
                        display: "flex",
                        alignItems: "center",
                        gap: 6,
                        fontWeight: 600,
                      }}
                    >
                      <LockClosed16Regular />
                      {isDemoConductor
                        ? <>Requires a built project</>
                        : <>Requires an architecture</>}
                    </div>
                  )}
                </div>
              </Card>
            );

            const wrappedCard = locked ? (
              <Tooltip key={key} content={isDemoConductor ? "Build an AI project with 'Build an AI Project' first" : "Create an architecture with 'Architect a Solution' first"} relationship="description" positioning="below">
                <div style={{ flex: 1, minWidth: 0, display: "flex" }}>{cardEl}</div>
              </Tooltip>
            ) : (
              <div key={key} style={{ flex: 1, minWidth: 0, display: "flex" }}>{cardEl}</div>
            );

            return (
              <React.Fragment key={key}>
                {wrappedCard}
                {i < PIPELINE_AGENTS.length - 1 && (
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      width: 28,
                      flexShrink: 0,
                      color: "var(--text-secondary)",
                      opacity: 0.4,
                    }}
                  >
                    <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                      <path d="M3 8h8M8.5 5l3 3-3 3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                    </svg>
                  </div>
                )}
              </React.Fragment>
            );
          })}
        </div>

      {/* Quick Start Templates */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          marginBottom: 14,
        }}
      >
        <Text
          as="h2"
          size={500}
          weight="semibold"
          style={{ letterSpacing: "-0.01em" }}
        >
          Quick Start Templates
        </Text>
        <div style={{ display: "flex", gap: 6 }}>
          <Button
            appearance="subtle"
            icon={<ChevronLeft20Regular />}
            size="small"
            onClick={() => scrollCarousel("left")}
            style={{ borderRadius: "50%", minWidth: 32, width: 32, height: 32 }}
          />
          <Button
            appearance="subtle"
            icon={<ChevronRight20Regular />}
            size="small"
            onClick={() => scrollCarousel("right")}
            style={{ borderRadius: "50%", minWidth: 32, width: 32, height: 32 }}
          />
        </div>
      </div>
      <div
        style={{
          position: "relative",
          marginBottom: 40,
        }}
      >
        {/* Fade-out overlay on the right edge to hint more content */}
        <div
          style={{
            position: "absolute",
            top: 0,
            right: 0,
            bottom: 0,
            width: 80,
            background: "linear-gradient(to right, transparent, var(--brand-light))",
            zIndex: 2,
            pointerEvents: "none",
            borderRadius: "0 10px 10px 0",
          }}
        />
        <div
          ref={carouselRef}
          style={{
            display: "flex",
            gap: 14,
            overflowX: "auto",
            paddingBottom: 8,
            paddingRight: 80,
            scrollbarWidth: "none",
            scrollSnapType: "x mandatory",
          }}
          className="hide-scrollbar"
        >
          {TEMPLATES.map((t, i) => {
            const meta = AGENT_META[t.agent];
            return (
              <Card
                key={i}
                className="animate-in"
                style={{
                  animationDelay: `${200 + i * 40}ms`,
                  flex: "0 0 200px",
                  border: "1px solid var(--border)",
                  borderRadius: 12,
                  padding: "18px 20px",
                  cursor: "pointer",
                  transition: "all 0.2s ease",
                  scrollSnapAlign: "start",
                }}
                onClick={() => {
                  setBriefInitial({
                    topic: t.brief.topic,
                    contentLevel: t.brief.contentLevel,
                    duration: t.brief.duration,
                    notes: t.brief.notes,
                  });
                  setBriefAgent(t.agent);
                }}
                onMouseEnter={(e) => {
                  (e.currentTarget as HTMLElement).style.borderColor = meta.color;
                  (e.currentTarget as HTMLElement).style.transform = "translateY(-2px)";
                  (e.currentTarget as HTMLElement).style.boxShadow = "0 4px 16px rgba(0,0,0,0.06)";
                }}
                onMouseLeave={(e) => {
                  (e.currentTarget as HTMLElement).style.borderColor = "var(--border)";
                  (e.currentTarget as HTMLElement).style.transform = "translateY(0)";
                  (e.currentTarget as HTMLElement).style.boxShadow = "none";
                }}
              >
                <div style={{ marginBottom: 10 }}>
                  <AgentIcon agent={t.agent} size="small" />
                </div>
                <Text
                  weight="semibold"
                  size={300}
                  style={{ display: "block", marginBottom: 6 }}
                >
                  {t.title}
                </Text>
                <Text
                  size={200}
                  style={{ color: "var(--text-secondary)", display: "block" }}
                >
                  {t.brief.contentLevel} · {t.brief.duration}
                </Text>
              </Card>
            );
          })}
        </div>
      </div>

      {/* Recent Outputs */}
      {recentOutputs.length > 0 && (
        <>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              marginBottom: 14,
            }}
          >
            <Text as="h2" size={500} weight="semibold" style={{ letterSpacing: "-0.01em" }}>
              Recent Outputs
            </Text>
            <Button
              appearance="transparent"
              icon={<ArrowRight16Regular />}
              iconPosition="after"
              size="small"
              onClick={() => navigate("/library")}
            >
              View all in Library
            </Button>
          </div>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fill, minmax(180px, 1fr))",
              gap: 12,
            }}
          >
            {recentOutputs.map((o, i) => (
              <Card
                key={o.path}
                className="animate-in"
                style={{
                  animationDelay: `${300 + i * 50}ms`,
                  border: "1px solid var(--border)",
                  borderRadius: 10,
                  padding: "14px 16px",
                  cursor: "pointer",
                  transition: "all 0.15s ease",
                }}
                onClick={() => {
                  if (o.type === "pptx") {
                    navigate(`/library/slides?path=${encodeURIComponent(o.path)}`);
                  } else if (o.type === "markdown") {
                    navigate(`/library/markdown?path=${encodeURIComponent(o.path)}`);
                  } else {
                    navigate("/library");
                  }
                }}
                onMouseEnter={(e) => {
                  (e.currentTarget as HTMLElement).style.transform = "translateY(-1px)";
                  (e.currentTarget as HTMLElement).style.boxShadow =
                    "0 4px 12px rgba(0,0,0,0.06)";
                }}
                onMouseLeave={(e) => {
                  (e.currentTarget as HTMLElement).style.transform = "translateY(0)";
                  (e.currentTarget as HTMLElement).style.boxShadow = "none";
                }}
              >
                <Text
                  size={200}
                  style={{
                    color: "var(--text-secondary)",
                    textTransform: "uppercase",
                    fontWeight: 600,
                    letterSpacing: "0.04em",
                    fontSize: 10,
                    display: "block",
                    marginBottom: 6,
                  }}
                >
                  {o.category}
                </Text>
                <Text
                  size={300}
                  weight="semibold"
                  style={{
                    display: "block",
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                    whiteSpace: "nowrap",
                  }}
                >
                  {o.name.replace(/\.(pptx|pdf|md|py)$/, "")}
                </Text>
                <Text
                  size={100}
                  style={{ color: "var(--text-secondary)", display: "block", marginTop: 4 }}
                >
                  {new Date(o.modified * 1000).toLocaleDateString()}
                </Text>
              </Card>
            ))}
          </div>
        </>
      )}

      {/* Brief form slide-over */}
      {briefAgent && (
        <BriefForm
          agent={briefAgent}
          initialBrief={briefInitial}
          onClose={() => { setBriefAgent(null); setBriefInitial(undefined); }}
          onJobCreated={(id) => {
            setBriefAgent(null);
            setBriefInitial(undefined);
            navigate(`/workspace?id=${id}`);
          }}
        />
      )}
    </div>
  );
}
