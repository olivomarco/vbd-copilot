import { useNavigate, useLocation } from "react-router-dom";
import {
  Button,
  Tooltip,
  Badge,
  Divider,
  Text,
} from "@fluentui/react-components";
import {
  Home24Regular,
  Home24Filled,
  Library24Regular,
  Library24Filled,
  Settings24Regular,
  Settings24Filled,
  PanelLeftContract24Regular,
  PanelLeftExpand24Regular,
  PlayCircle24Regular,
  PlayCircle24Filled,
  Checkmark12Regular,
  Dismiss12Regular,
  BookQuestionMark24Regular,
} from "@fluentui/react-icons";
import { useTutorialStore } from "@/stores/tutorialStore";
import { useSettingsStore } from "@/stores/settingsStore";
import { useJobStore, type Job } from "@/stores/jobStore";
import { AGENT_META, type AgentType } from "@/api/types";
import { AgentIcon } from "@/components/common/AgentIcon";
import { formatElapsedShort } from "@/utils/formatElapsed";

const NAV_ITEMS = [
  {
    path: "/",
    label: "Launchpad",
    Icon: Home24Regular,
    IconFilled: Home24Filled,
    tutorialId: "nav-launchpad",
  },
  {
    path: "/mission",
    label: "Mission Control",
    Icon: PlayCircle24Regular,
    IconFilled: PlayCircle24Filled,
    tutorialId: "nav-mission",
  },
  {
    path: "/library",
    label: "Library",
    Icon: Library24Regular,
    IconFilled: Library24Filled,
    tutorialId: "nav-library",
  },
  {
    path: "/settings",
    label: "Settings",
    Icon: Settings24Regular,
    IconFilled: Settings24Filled,
    tutorialId: "nav-settings",
  },
];

/** Sidebar job item — shows a compact row with a pulsing attention dot when input is needed. */
function SidebarJobItem({ job, navigate }: { job: Job; navigate: (to: string) => void }) {
  const isWaiting = job.status === "waiting" && !!job.pendingInput?.length;
  const isRunning = job.status === "running" || job.status === "queued";

  return (
    <Tooltip
      content={isWaiting ? `Needs input: ${job.pendingInput![0].question}` : job.brief.topic}
      relationship="description"
      positioning="after"
    >
      <Button
        appearance="transparent"
        icon={<AgentIcon agent={job.agent} size="inline" />}
        onClick={() => navigate(`/workspace?id=${job.id}`)}
        style={{
          justifyContent: "flex-start",
          width: "100%",
          minHeight: 32,
          borderRadius: 6,
          fontSize: 12,
          gap: 4,
        }}
      >
        <span
          className={isRunning ? "wave-text" : undefined}
          style={{
            overflow: "hidden",
            textOverflow: "ellipsis",
            whiteSpace: "nowrap",
          }}
        >
          {job.brief.topic.slice(0, 20)}
        </span>
        {isWaiting && (
          <span
            className="pulse-attention"
            style={{
              width: 8,
              height: 8,
              borderRadius: "50%",
              background: "#FFB900",
              marginLeft: "auto",
              flexShrink: 0,
              boxShadow: "0 0 6px 2px rgba(255, 185, 0, 0.5)",
            }}
          />
        )}
      </Button>
    </Tooltip>
  );
}

export function Sidebar() {
  const navigate = useNavigate();
  const location = useLocation();
  const collapsed = useSettingsStore((s) => s.sidebarCollapsed);
  const toggleSidebar = useSettingsStore((s) => s.toggleSidebar);
  const allJobs = Object.values(useJobStore((s) => s.jobs));
  const dismissNotification = useJobStore((s) => s.dismissNotification);
  const dismissedNotifications = useJobStore((s) => s.dismissedNotifications);
  const activeJobs = allJobs.filter(
    (j) => j.status === "running" || j.status === "queued" || j.status === "waiting",
  );

  // Recently completed jobs (last 30 min, with output files, not dismissed)
  const RECENT_THRESHOLD = 30 * 60 * 1000; // 30 minutes
  const now = Date.now();
  const recentlyCompleted = allJobs
    .filter(
      (j) =>
        j.status === "completed" &&
        j.completedAt &&
        now - j.completedAt < RECENT_THRESHOLD &&
        j.outputFiles.length > 0 &&
        !dismissedNotifications.has(j.id),
    )
    .sort((a, b) => (b.completedAt || 0) - (a.completedAt || 0))
    .slice(0, 5);

  return (
    <nav
      style={{
        position: "fixed",
        left: 0,
        top: 0,
        bottom: 0,
        width: collapsed ? 56 : 260,
        background: "var(--card-bg)",
        borderRight: "1px solid var(--border)",
        display: "flex",
        flexDirection: "column",
        transition: "width 0.25s cubic-bezier(0.4, 0, 0.2, 1)",
        zIndex: 100,
        overflow: "hidden",
      }}
    >
      {/* Logo */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 10,
          padding: "16px 14px 12px",
          cursor: "pointer",
          minHeight: 56,
        }}
        onClick={() => navigate("/")}
      >
        <div
          style={{
            width: 28,
            height: 28,
            display: "grid",
            gridTemplateColumns: "1fr 1fr",
            gridTemplateRows: "1fr 1fr",
            gap: 2,
            flexShrink: 0,
          }}
        >
          <div style={{ background: "#F25022", borderRadius: 2 }} />
          <div style={{ background: "#7FBA00", borderRadius: 2 }} />
          <div style={{ background: "#00A4EF", borderRadius: 2 }} />
          <div style={{ background: "#FFB900", borderRadius: 2 }} />
        </div>
        {!collapsed && (
          <Text
            weight="semibold"
            size={400}
            style={{ whiteSpace: "nowrap", letterSpacing: "-0.02em" }}
          >
            CSA Copilot
          </Text>
        )}
      </div>

      <Divider style={{ margin: "0 12px 8px" }} />

      {/* Nav items */}
      <div data-tutorial="sidebar-nav" style={{ flex: 1, display: "flex", flexDirection: "column", gap: 2, padding: "0 8px" }}>
        {NAV_ITEMS.map(({ path, label, Icon, IconFilled, tutorialId }) => {
          const active =
            path === "/"
              ? location.pathname === "/"
              : location.pathname.startsWith(path);
          const CurrentIcon = active ? IconFilled : Icon;

          const button = (
            <Button
              key={path}
              data-tutorial={tutorialId}
              appearance={active ? "subtle" : "transparent"}
              icon={<CurrentIcon />}
              onClick={() => navigate(path)}
              style={{
                justifyContent: collapsed ? "center" : "flex-start",
                width: "100%",
                minHeight: 40,
                borderRadius: 8,
                fontWeight: active ? 600 : 400,
                background: active ? "rgba(0, 120, 212, 0.08)" : "transparent",
                color: active ? "var(--brand-primary)" : "var(--text-primary)",
                paddingLeft: collapsed ? 0 : 12,
              }}
            >
              {!collapsed && label}
            </Button>
          );

          return collapsed ? (
            <Tooltip key={path} content={label} relationship="label" positioning="after">
              {button}
            </Tooltip>
          ) : (
            button
          );
        })}
      </div>

      {/* Recently Completed — persistent notification banners */}
      {!collapsed && recentlyCompleted.length > 0 && (
        <div style={{ padding: "0 8px", marginBottom: 4 }}>
          <Divider style={{ margin: "4px 4px 8px" }} />
          <Text
            size={100}
            style={{
              display: "block",
              padding: "0 12px 6px",
              color: "#107C10",
              textTransform: "uppercase",
              fontWeight: 700,
              fontSize: 10,
              letterSpacing: "0.04em",
            }}
          >
            Ready
          </Text>
          {recentlyCompleted.map((job) => {
            const primaryFile = job.outputFiles[0] || "";
            const isPptx = primaryFile.endsWith(".pptx");
            const isMd = primaryFile.endsWith(".md");
            const libraryPath = isPptx
              ? `/library/slides?path=${encodeURIComponent(primaryFile)}`
              : isMd
                ? `/library/markdown?path=${encodeURIComponent(primaryFile)}`
                : "/library";
            const agentMeta = AGENT_META[job.agent as AgentType];
            const elapsedMs = job.completedAt
              ? job.completedAt - job.startedAt
              : 0;
            const elapsedLabel = elapsedMs > 0 ? formatElapsedShort(elapsedMs) : "";

            return (
              <div
                key={job.id}
                style={{
                  position: "relative",
                  margin: "0 4px 6px",
                  padding: "10px 12px",
                  background: "linear-gradient(135deg, #f0fff0 0%, #e8f5e8 100%)",
                  border: "1px solid #7FBA0060",
                  borderLeft: "3px solid #7FBA00",
                  borderRadius: 8,
                  cursor: "pointer",
                  transition: "all 0.15s ease",
                }}
                onClick={() => {
                  dismissNotification(job.id);
                  navigate(libraryPath);
                }}
                onMouseEnter={(e) => {
                  (e.currentTarget as HTMLElement).style.background = "linear-gradient(135deg, #e8f5e8 0%, #d4ebd4 100%)";
                  (e.currentTarget as HTMLElement).style.borderColor = "#7FBA00";
                }}
                onMouseLeave={(e) => {
                  (e.currentTarget as HTMLElement).style.background = "linear-gradient(135deg, #f0fff0 0%, #e8f5e8 100%)";
                  (e.currentTarget as HTMLElement).style.borderColor = "#7FBA0060";
                }}
              >
                {/* Dismiss button */}
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    dismissNotification(job.id);
                  }}
                  style={{
                    position: "absolute",
                    top: 4,
                    right: 4,
                    background: "none",
                    border: "none",
                    cursor: "pointer",
                    padding: 2,
                    borderRadius: 4,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    color: "var(--text-secondary)",
                    opacity: 0.6,
                  }}
                  onMouseEnter={(e) => { (e.currentTarget as HTMLElement).style.opacity = "1"; }}
                  onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.opacity = "0.6"; }}
                >
                  <Dismiss12Regular />
                </button>

                <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 4 }}>
                  <span
                    style={{
                      width: 16,
                      height: 16,
                      borderRadius: "50%",
                      background: "#7FBA00",
                      color: "white",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      flexShrink: 0,
                    }}
                  >
                    <Checkmark12Regular />
                  </span>
                  <Text
                    weight="semibold"
                    size={200}
                    style={{
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      whiteSpace: "nowrap",
                      color: "#107C10",
                    }}
                  >
                    {job.brief.topic.slice(0, 28)}{job.brief.topic.length > 28 ? "…" : ""}
                  </Text>
                </div>
                <Text
                  size={100}
                  style={{
                    display: "block",
                    color: "var(--text-secondary)",
                    fontSize: 10,
                  }}
                >
                  {agentMeta?.label || job.agent} · {job.outputFiles.length} file{job.outputFiles.length !== 1 ? "s" : ""}{elapsedLabel ? ` · ${elapsedLabel}` : ""}
                </Text>
                <Text
                  size={100}
                  weight="semibold"
                  style={{
                    display: "block",
                    marginTop: 4,
                    color: "#0078D4",
                    fontSize: 10,
                  }}
                >
                  View in Library →
                </Text>
              </div>
            );
          })}
        </div>
      )}

      {/* Collapsed mode: completed badge */}
      {collapsed && recentlyCompleted.length > 0 && (
        <div style={{ padding: "0 8px 4px", textAlign: "center" }}>
          <Tooltip
            content={`${recentlyCompleted.length} completed — click to view`}
            relationship="description"
            positioning="after"
          >
            <Badge
              size="small"
              color="success"
              style={{ cursor: "pointer" }}
              onClick={() => navigate("/library")}
            >
              {recentlyCompleted.length} ✓
            </Badge>
          </Tooltip>
        </div>
      )}

      {/* Active Jobs */}
      {!collapsed && activeJobs.length > 0 && (
        <div style={{ padding: "0 8px", marginBottom: 4 }}>
          <Divider style={{ margin: "4px 4px 8px" }} />
          <Text
            size={100}
            style={{
              display: "block",
              padding: "0 12px 6px",
              color: "var(--text-secondary)",
              textTransform: "uppercase",
              fontWeight: 600,
              fontSize: 10,
              letterSpacing: "0.04em",
            }}
          >
            Active Jobs
          </Text>
          {activeJobs.map((job) => (
            <SidebarJobItem key={job.id} job={job} navigate={navigate} />
          ))}
        </div>
      )}

      {/* Mission Control badge in collapsed mode */}
      {collapsed && activeJobs.length > 0 && (
        <div style={{ padding: "0 8px 4px", textAlign: "center" }}>
          <Badge
            size="small"
            color={activeJobs.some((j) => j.status === "waiting") ? "warning" : "brand"}
          >
            {activeJobs.length}
          </Badge>
        </div>
      )}

      {/* Tutorial + Collapse toggle */}
      <div style={{ padding: "8px", borderTop: "1px solid var(--border)", display: "flex", flexDirection: "column", gap: 2 }}>
        <Tooltip
          content={collapsed ? "Tutorial" : ""}
          relationship="label"
          positioning="after"
        >
          <Button
            appearance="transparent"
            icon={<BookQuestionMark24Regular />}
            onClick={() => useTutorialStore.getState().start()}
            style={{
              width: "100%",
              justifyContent: collapsed ? "center" : "flex-start",
              minHeight: 36,
            }}
          >
            {!collapsed && "Tutorial"}
          </Button>
        </Tooltip>
        <Tooltip
          content={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          relationship="label"
          positioning="after"
        >
          <Button
            appearance="transparent"
            icon={collapsed ? <PanelLeftExpand24Regular /> : <PanelLeftContract24Regular />}
            onClick={toggleSidebar}
            style={{
              width: "100%",
              justifyContent: collapsed ? "center" : "flex-start",
              minHeight: 36,
            }}
          >
            {!collapsed && "Collapse"}
          </Button>
        </Tooltip>
      </div>
    </nav>
  );
}
