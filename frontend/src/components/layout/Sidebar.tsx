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
  History24Regular,
  History24Filled,
  Settings24Regular,
  Settings24Filled,
  PanelLeftContract24Regular,
  PanelLeftExpand24Regular,
  PlayCircle24Regular,
  PlayCircle24Filled,
} from "@fluentui/react-icons";
import { useSettingsStore } from "@/stores/settingsStore";
import { useJobStore } from "@/stores/jobStore";
import { AGENT_META } from "@/api/types";
import { AgentIcon } from "@/components/common/AgentIcon";

const NAV_ITEMS = [
  {
    path: "/",
    label: "Launchpad",
    Icon: Home24Regular,
    IconFilled: Home24Filled,
  },
  {
    path: "/mission",
    label: "Mission Control",
    Icon: PlayCircle24Regular,
    IconFilled: PlayCircle24Filled,
  },
  {
    path: "/library",
    label: "Library",
    Icon: Library24Regular,
    IconFilled: Library24Filled,
  },
  {
    path: "/sessions",
    label: "Sessions",
    Icon: History24Regular,
    IconFilled: History24Filled,
  },
  {
    path: "/settings",
    label: "Settings",
    Icon: Settings24Regular,
    IconFilled: Settings24Filled,
  },
];

export function Sidebar() {
  const navigate = useNavigate();
  const location = useLocation();
  const collapsed = useSettingsStore((s) => s.sidebarCollapsed);
  const toggleSidebar = useSettingsStore((s) => s.toggleSidebar);
  const allJobs = Object.values(useJobStore((s) => s.jobs));
  const activeJobs = allJobs.filter(
    (j) => j.status === "running" || j.status === "queued" || j.status === "waiting",
  );

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
      <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: 2, padding: "0 8px" }}>
        {NAV_ITEMS.map(({ path, label, Icon, IconFilled }) => {
          const active =
            path === "/"
              ? location.pathname === "/"
              : location.pathname.startsWith(path);
          const CurrentIcon = active ? IconFilled : Icon;

          const button = (
            <Button
              key={path}
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
          {activeJobs.map((job) => {
            const meta = AGENT_META[job.agent];
            return (
              <Button
                key={job.id}
                appearance="transparent"
                onClick={() => navigate(`/workspace?id=${job.id}`)}
                style={{
                  justifyContent: "flex-start",
                  width: "100%",
                  minHeight: 32,
                  borderRadius: 6,
                  paddingLeft: 12,
                  fontSize: 12,
                }}
              >
                <span style={{ marginRight: 6 }}>
                  {job.status === "waiting" ? "⚠️" : <AgentIcon agent={job.agent} size="inline" />}
                </span>
                <span
                  style={{
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                    whiteSpace: "nowrap",
                  }}
                >
                  {job.brief.topic.slice(0, 20)}
                </span>
              </Button>
            );
          })}
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

      {/* Collapse toggle */}
      <div style={{ padding: "8px", borderTop: "1px solid var(--border)" }}>
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
