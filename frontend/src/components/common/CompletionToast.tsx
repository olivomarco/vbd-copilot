import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Text, Button } from "@fluentui/react-components";
import {
  Dismiss16Regular,
  ArrowDownload20Regular,
  Open20Regular,
  CheckmarkCircle20Filled,
} from "@fluentui/react-icons";
import { useJobStore, type Job } from "@/stores/jobStore";
import { AGENT_META, type AgentType } from "@/api/types";
import { AgentIcon } from "@/components/common/AgentIcon";
import { playNotificationSound } from "@/utils/notifications";
import { formatElapsed } from "@/utils/formatElapsed";

const AUTO_DISMISS_MS = 15_000;

interface ToastEntry {
  job: Job;
  /** monotonic id for React key */
  key: number;
}

let _toastCounter = 0;

export function CompletionToast() {
  const navigate = useNavigate();
  const [toasts, setToasts] = useState<ToastEntry[]>([]);
  const seenRef = useRef(new Set<string>());
  /** Track which jobs we've already seen as "completed" to detect transitions. */
  const prevStatusRef = useRef(new Map<string, string>());
  const dismissNotification = useJobStore((s) => s.dismissNotification);

  // Watch all jobs — surface newly completed ones as toasts
  const jobs = useJobStore((s) => s.jobs);
  const dismissedNotifications = useJobStore((s) => s.dismissedNotifications);

  useEffect(() => {
    for (const job of Object.values(jobs)) {
      const prevStatus = prevStatusRef.current.get(job.id);
      const justCompleted = job.status === "completed" && prevStatus !== undefined && prevStatus !== "completed";
      const hasFiles = job.outputFiles.length > 0;

      // Show toast when:
      // 1. Job JUST transitioned to completed (we saw it in a non-completed state before)
      // 2. OR: Job is completed with files and within 30s window (handles page refresh / reconnect)
      const withinWindow = job.completedAt && (Date.now() - job.completedAt < 30_000);
      const shouldShow =
        hasFiles &&
        job.status === "completed" &&
        (justCompleted || withinWindow) &&
        !seenRef.current.has(job.id) &&
        !dismissedNotifications.has(job.id);

      if (shouldShow) {
        seenRef.current.add(job.id);
        const key = ++_toastCounter;
        setToasts((prev) => [...prev, { job, key }]);
        playNotificationSound();

        // Auto-dismiss after timeout
        setTimeout(() => {
          setToasts((prev) => prev.filter((t) => t.key !== key));
        }, AUTO_DISMISS_MS);
      }
    }

    // Update previous status tracking
    for (const job of Object.values(jobs)) {
      prevStatusRef.current.set(job.id, job.status);
    }
  }, [jobs, dismissedNotifications]);

  const dismiss = (key: number, jobId: string) => {
    setToasts((prev) => prev.filter((t) => t.key !== key));
    dismissNotification(jobId);
  };

  const openInLibrary = (job: Job, key: number) => {
    const primaryFile = job.outputFiles[0] || "";
    const isPptx = primaryFile.endsWith(".pptx");

    // Derive the route matching OutputLibrary's handlePreview logic.
    // Parse the path to find the category segment after "outputs/".
    let path: string;
    if (isPptx) {
      path = `/library/slides?path=${encodeURIComponent(primaryFile)}`;
    } else {
      // Extract category + slug from the outputs directory structure:
      //   .../outputs/demos/{slug}-demos.md        → demos/{slug}
      //   .../outputs/hackathons/{event}/...        → hackathons/{event}
      //   .../outputs/ai-projects/{project}/...     → ai-projects/{project}
      const outputsIdx = primaryFile.lastIndexOf("/outputs/");
      const afterOutputs = outputsIdx >= 0 ? primaryFile.slice(outputsIdx + "/outputs/".length) : "";
      const segments = afterOutputs.split("/");
      const category = segments[0]; // demos | hackathons | ai-projects | slides

      if (category === "demos" && job.outputFiles.length === 1 && primaryFile.endsWith(".md")) {
        // Single-file demo → markdown viewer
        path = `/library/markdown?path=${encodeURIComponent(primaryFile)}`;
      } else if (category && segments.length >= 2) {
        // Multi-file demos, hackathons, ai-projects → project explorer
        let slug: string;
        if (category === "demos") {
          // slug from the md filename: {slug}-demos.md
          const mdFile = job.outputFiles.find((f) => f.endsWith("-demos.md"));
          const mdName = mdFile ? mdFile.split("/").pop()!.replace("-demos.md", "") : segments[1];
          slug = mdName;
        } else {
          // hackathons / ai-projects: slug is the subfolder name
          slug = segments[1];
        }
        const groupId = `${category}/${slug}`;
        path = `/library/project?path=${encodeURIComponent(primaryFile)}&id=${encodeURIComponent(groupId)}`;
      } else {
        path = "/library";
      }
    }

    dismiss(key, job.id);
    navigate(path);
  };

  if (toasts.length === 0) return null;

  return (
    <div
      style={{
        position: "fixed",
        top: 16,
        right: 16,
        zIndex: 10000,
        display: "flex",
        flexDirection: "column",
        gap: 10,
        pointerEvents: "none",
        maxWidth: 400,
      }}
    >
      {toasts.map(({ job, key }) => {
        const meta = AGENT_META[job.agent as AgentType];
        const fileCount = job.outputFiles.length;
        const primaryFile = job.outputFiles[0] || "";
        const fileName = primaryFile.split("/").pop() || "";
        const elapsedStr = formatElapsed(
          job.completedAt
            ? job.completedAt - job.startedAt
            : 0
        );

        return (
          <div
            key={key}
            style={{
              pointerEvents: "auto",
              background: "var(--bg-card-elevated)",
              borderRadius: 12,
              boxShadow:
                "0 8px 32px rgba(0,0,0,0.12), 0 2px 8px rgba(0,0,0,0.08)",
              border: "1px solid #7FBA0060",
              overflow: "hidden",
              animation: "toast-slide-in 0.35s cubic-bezier(0.16, 1, 0.3, 1)",
            }}
          >
            {/* Green accent bar at top */}
            <div
              style={{
                height: 3,
                background:
                  "linear-gradient(90deg, #7FBA00, #107C10)",
              }}
            />

            <div style={{ padding: "14px 16px" }}>
              {/* Header row */}
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 10,
                  marginBottom: 10,
                }}
              >
                <span
                  style={{
                    width: 32,
                    height: 32,
                    borderRadius: "50%",
                    background: "var(--bg-success)",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    flexShrink: 0,
                  }}
                >
                  <CheckmarkCircle20Filled
                    style={{ color: "#7FBA00", fontSize: 20 }}
                  />
                </span>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <Text
                    weight="semibold"
                    size={300}
                    style={{
                      display: "block",
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      whiteSpace: "nowrap",
                      color: "var(--text-success)",
                    }}
                  >
                    Content ready
                  </Text>
                  <Text
                    size={200}
                    style={{
                      display: "block",
                      color: "var(--text-secondary)",
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      whiteSpace: "nowrap",
                    }}
                  >
                    {job.brief.topic}
                  </Text>
                </div>
                <button
                  onClick={() => dismiss(key, job.id)}
                  style={{
                    background: "none",
                    border: "none",
                    cursor: "pointer",
                    padding: 4,
                    borderRadius: 4,
                    display: "flex",
                    alignItems: "center",
                    color: "var(--text-secondary)",
                    flexShrink: 0,
                  }}
                >
                  <Dismiss16Regular />
                </button>
              </div>

              {/* File info row */}
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 8,
                  padding: "8px 10px",
                  background: "var(--bg-subtle)",
                  borderRadius: 8,
                  marginBottom: 10,
                  fontSize: 12,
                }}
              >
                <AgentIcon agent={job.agent} size="inline" />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <Text
                    size={200}
                    weight="semibold"
                    style={{
                      display: "block",
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      whiteSpace: "nowrap",
                    }}
                  >
                    {fileName}
                    {fileCount > 1 && (
                      <span style={{ fontWeight: 400, color: "var(--text-secondary)" }}>
                        {" "}+{fileCount - 1} more
                      </span>
                    )}
                  </Text>
                  <Text size={100} style={{ color: "var(--text-secondary)" }}>
                    {meta?.label || job.agent} · {elapsedStr} · {job.progress.toolCalls} tools
                  </Text>
                </div>
              </div>

              {/* Action buttons */}
              <div style={{ display: "flex", gap: 8 }}>
                <Button
                  appearance="primary"
                  size="small"
                  icon={<Open20Regular />}
                  onClick={() => openInLibrary(job, key)}
                  style={{ flex: 1, borderRadius: 6 }}
                >
                  Open
                </Button>
                <Button
                  appearance="outline"
                  size="small"
                  icon={<ArrowDownload20Regular />}
                  onClick={() => {
                    if (primaryFile) {
                      const a = document.createElement("a");
                      a.href = `/file/download?path=${encodeURIComponent(primaryFile)}`;
                      a.download = fileName;
                      a.click();
                    }
                    dismiss(key, job.id);
                  }}
                  style={{ borderRadius: 6 }}
                >
                  Download
                </Button>
              </div>
            </div>

            {/* Auto-dismiss progress bar */}
            <div
              style={{
                height: 2,
                background: "#e0e0e0",
                position: "relative",
                overflow: "hidden",
              }}
            >
              <div
                style={{
                  height: "100%",
                  background: "#7FBA00",
                  animation: `toast-progress ${AUTO_DISMISS_MS}ms linear forwards`,
                }}
              />
            </div>
          </div>
        );
      })}
    </div>
  );
}
