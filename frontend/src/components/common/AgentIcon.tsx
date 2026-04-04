import {
  SlideText24Regular,
  Play24Regular,
  Trophy24Regular,
  Lightbulb24Regular,
  Building24Regular,
  Rocket24Regular,
  Document24Regular,
  Presenter24Regular,
} from "@fluentui/react-icons";
import type { AgentType } from "@/api/types";
import type { ComponentType } from "react";

type FluentIcon = ComponentType<{ style?: React.CSSProperties; className?: string }>;

const ICON_MAP: Record<AgentType, FluentIcon> = {
  "slide-conductor": SlideText24Regular,
  "demo-conductor": Play24Regular,
  "ai-demo-conductor": Presenter24Regular,
  "hackathon-conductor": Trophy24Regular,
  "ai-brainstorming": Lightbulb24Regular,
  "ai-solution-architect": Building24Regular,
  "ai-implementor": Rocket24Regular,
};

export const COLOR_MAP: Record<AgentType, string> = {
  "slide-conductor": "#0078D4",
  "demo-conductor": "#7FBA00",
  "ai-demo-conductor": "#00B294",
  "hackathon-conductor": "#FFB900",
  "ai-brainstorming": "#00A4EF",
  "ai-solution-architect": "#8661C5",
  "ai-implementor": "#F25022",
};

const CATEGORY_AGENT_MAP: Record<string, AgentType> = {
  slides: "slide-conductor",
  demos: "demo-conductor",
  hackathons: "hackathon-conductor",
  "ai-projects": "ai-implementor",
};

interface AgentIconProps {
  agent: AgentType;
  size?: "inline" | "small" | "large";
}

/**
 * Renders a premium Fluent UI icon for an agent type.
 * - "inline" (20px icon only, no background — for menus, sidebar, compact lists)
 * - "small" (40px with tinted background)
 * - "large" (56px with tinted background)
 */
export function AgentIcon({ agent, size = "small" }: AgentIconProps) {
  const Icon = ICON_MAP[agent];
  const color = COLOR_MAP[agent] || "#0078D4";

  if (!Icon) return <span>●</span>;

  if (size === "inline") {
    return <Icon style={{ color, width: 20, height: 20, flexShrink: 0 }} />;
  }

  const dim = size === "large" ? 56 : 40;
  const iconDim = size === "large" ? 28 : 20;
  const radius = size === "large" ? 16 : 12;

  return (
    <div
      style={{
        width: dim,
        height: dim,
        borderRadius: radius,
        background: `${color}14`,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        flexShrink: 0,
      }}
    >
      <Icon style={{ color, width: iconDim, height: iconDim }} />
    </div>
  );
}

/**
 * Icon for an output category (slides, demos, hackathons, ai-projects).
 */
export function CategoryIcon({ category, size = "small" }: { category: string; size?: "inline" | "small" | "large" }) {
  const agent = CATEGORY_AGENT_MAP[category];
  if (agent) return <AgentIcon agent={agent} size={size} />;
  // Fallback for unknown categories
  const Icon = Document24Regular;
  if (size === "inline") return <Icon style={{ color: "#605E5C", width: 20, height: 20 }} />;
  const dim = size === "large" ? 56 : 40;
  return (
    <div style={{ width: dim, height: dim, borderRadius: 12, background: "var(--hover-bg)", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
      <Icon style={{ color: "#605E5C", width: 20, height: 20 }} />
    </div>
  );
}
