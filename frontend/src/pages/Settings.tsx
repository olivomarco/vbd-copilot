import { useEffect, useState } from "react";
import {
  Text,
  Card,
  Badge,
  Spinner,
  Dropdown,
  Option,
  Switch,
} from "@fluentui/react-components";
import { checkHealth, getUsage } from "@/api/client";
import type { UsageStats } from "@/api/types";
import { useSettingsStore } from "@/stores/settingsStore";

function formatTokens(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(0)}k`;
  return String(n);
}

export function Settings() {
  const [health, setHealth] = useState<{ status: string; version: string } | null>(null);
  const [usage, setUsage] = useState<UsageStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [usagePeriod, setUsagePeriod] = useState("all");
  const theme = useSettingsStore((s) => s.theme);
  const setTheme = useSettingsStore((s) => s.setTheme);
  const verboseMode = useSettingsStore((s) => s.verboseMode);
  const setVerboseMode = useSettingsStore((s) => s.setVerboseMode);

  useEffect(() => {
    Promise.all([
      checkHealth().catch(() => null),
      getUsage(usagePeriod).catch(() => null),
    ]).then(([h, u]) => {
      setHealth(h);
      setUsage(u);
      setLoading(false);
    });
  }, [usagePeriod]);

  if (loading) {
    return (
      <div style={{ display: "flex", justifyContent: "center", padding: 80 }}>
        <Spinner label="Loading..." />
      </div>
    );
  }

  return (
    <div className="page-container" style={{ padding: "32px 48px", maxWidth: 900, margin: "0 auto" }}>
      <Text
        as="h1"
        size={700}
        weight="bold"
        style={{ display: "block", marginBottom: 32, letterSpacing: "-0.03em" }}
      >
        Settings
      </Text>

      {/* General */}
      <Text
        as="h2"
        size={500}
        weight="semibold"
        style={{ display: "block", marginBottom: 14 }}
      >
        General
      </Text>

      <Card
        style={{
          border: "1px solid var(--border)",
          borderRadius: 10,
          padding: "20px 24px",
          marginBottom: 32,
        }}
      >
        <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <Text size={300}>Theme</Text>
            <Dropdown
              value={theme === "light" ? "Light" : theme === "dark" ? "Dark" : "System"}
              onOptionSelect={(_, d) => setTheme(d.optionValue as "light" | "dark" | "system")}
              style={{ minWidth: 140 }}
            >
              <Option value="light">Light</Option>
              <Option value="dark">Dark</Option>
              <Option value="system">System</Option>
            </Dropdown>
          </div>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <div>
              <Text size={300} style={{ display: "block" }}>Verbose Mode</Text>
              <Text size={200} style={{ color: "var(--text-secondary)", display: "block", marginTop: 2 }}>
                Show detailed model output including thinking tokens, tool I/O, and reasoning in Mission Control
              </Text>
            </div>
            <Switch
              checked={verboseMode}
              onChange={(_, d) => setVerboseMode(d.checked)}
            />
          </div>
        </div>
      </Card>

      {/* Connection Status */}
      <Text
        as="h2"
        size={500}
        weight="semibold"
        style={{ display: "block", marginBottom: 14 }}
      >
        Connection
      </Text>

      <Card
        style={{
          border: "1px solid var(--border)",
          borderRadius: 10,
          padding: "20px 24px",
          marginBottom: 32,
        }}
      >
        <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <Text size={300}>Server Status</Text>
            {health ? (
              <Badge appearance="filled" color="success" size="small">
                Healthy — v{health.version}
              </Badge>
            ) : (
              <Badge appearance="filled" color="danger" size="small">
                Unreachable
              </Badge>
            )}
          </div>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <Text size={300}>Copilot SDK</Text>
            <Badge appearance="tint" color="informative" size="small">
              v{health?.version ?? "—"}
            </Badge>
          </div>
        </div>
      </Card>

      {/* Usage Dashboard */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 14 }}>
        <Text
          as="h2"
          size={500}
          weight="semibold"
        >
          Usage
        </Text>
        <Dropdown
          value={usagePeriod === "all" ? "All Time" : usagePeriod === "day" ? "Today" : usagePeriod === "week" ? "This Week" : "This Month"}
          onOptionSelect={(_, d) => setUsagePeriod(d.optionValue || "all")}
          style={{ minWidth: 140 }}
        >
          <Option value="all">All Time</Option>
          <Option value="day">Today</Option>
          <Option value="week">This Week</Option>
          <Option value="month">This Month</Option>
        </Dropdown>
      </div>

      {usage ? (
        <>
          {/* Summary cards */}
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fill, minmax(180px, 1fr))",
              gap: 12,
              marginBottom: 24,
            }}
          >
            <Card
              style={{
                border: "1px solid var(--border)",
                borderRadius: 10,
                padding: "16px 20px",
                textAlign: "center",
              }}
            >
              <Text
                size={200}
                style={{
                  display: "block",
                  color: "var(--text-secondary)",
                  textTransform: "uppercase",
                  fontWeight: 600,
                  fontSize: 10,
                  letterSpacing: "0.04em",
                  marginBottom: 6,
                }}
              >
                Sessions
              </Text>
              <Text size={700} weight="bold">
                {usage.turn_count}
              </Text>
            </Card>
            <Card
              style={{
                border: "1px solid var(--border)",
                borderRadius: 10,
                padding: "16px 20px",
                textAlign: "center",
              }}
            >
              <Text
                size={200}
                style={{
                  display: "block",
                  color: "var(--text-secondary)",
                  textTransform: "uppercase",
                  fontWeight: 600,
                  fontSize: 10,
                  letterSpacing: "0.04em",
                  marginBottom: 6,
                }}
              >
                Est. Cost
              </Text>
              <Text size={700} weight="bold">
                ${usage.total_cost_usd.toFixed(2)}
              </Text>
            </Card>
          </div>

          {/* By Agent breakdown */}
          {usage.by_agent.length > 0 && (
            <Card
              style={{
                border: "1px solid var(--border)",
                borderRadius: 10,
                padding: "20px 24px",
                marginBottom: 16,
              }}
            >
              <Text
                weight="semibold"
                size={300}
                style={{
                  display: "block",
                  marginBottom: 14,
                  textTransform: "uppercase",
                  fontSize: 11,
                  letterSpacing: "0.04em",
                  color: "var(--text-secondary)",
                }}
              >
                By Agent
              </Text>
              <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                {usage.by_agent.map((entry) => {
                  const total = usage.total_input_tokens + usage.total_output_tokens;
                  const agentTotal = entry.input_tokens + entry.output_tokens;
                  const pct = total > 0 ? (agentTotal / total) * 100 : 0;
                  return (
                    <div key={entry.agent}>
                      <div
                        style={{
                          display: "flex",
                          justifyContent: "space-between",
                          marginBottom: 4,
                        }}
                      >
                        <Text size={300}>{entry.agent}</Text>
                        <Text size={200} style={{ color: "var(--text-secondary)" }}>
                          {formatTokens(agentTotal)} · ${entry.cost_usd.toFixed(2)}
                        </Text>
                      </div>
                      <div
                        style={{
                          height: 6,
                          background: "var(--hover-bg)",
                          borderRadius: 3,
                          overflow: "hidden",
                        }}
                      >
                        <div
                          style={{
                            height: "100%",
                            width: `${pct}%`,
                            background: "var(--brand-primary)",
                            borderRadius: 3,
                            transition: "width 0.5s ease",
                          }}
                        />
                      </div>
                    </div>
                  );
                })}
              </div>
            </Card>
          )}
        </>
      ) : (
        <Text size={300} style={{ color: "var(--text-secondary)" }}>
          No usage data available
        </Text>
      )}
    </div>
  );
}
