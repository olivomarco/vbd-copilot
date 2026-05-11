import { useEffect, useRef } from "react";
import { useJobStore, type Job } from "@/stores/jobStore";
import { AGENT_META } from "@/api/types";

/**
 * Build the initial prompt string from a job's brief metadata.
 * Shared between AgentWorkspace and MissionControl so every page
 * can auto-send the brief when the WebSocket connects.
 */
export function buildPromptFromBrief(job: Job): string | null {
  if (job.brief.topic === "Resumed session") return null;

  const b = job.brief;
  const agentMeta = AGENT_META[job.agent];
  const levelPart = agentMeta?.showContentLevel ? `${b.contentLevel} ` : "";
  const durationPart = agentMeta?.showDuration ? `${b.duration} ` : "";
  let prompt: string;

  if (job.agent === "slide-conductor") {
    const themePart = b.theme ? ` with a ${b.theme} layout theme` : "";
    prompt = `@${job.agent} Create a ${levelPart}${durationPart}presentation on "${b.topic}"${themePart}`;
  } else if (job.agent === "demo-conductor") {
    prompt = `@${job.agent} Create a ${levelPart}${durationPart}demo guide on "${b.topic}"`;
  } else if (job.agent === "hackathon-conductor") {
    prompt = `@${job.agent} Create a ${levelPart}${durationPart}hackathon on "${b.topic}"`;
  } else if (job.agent === "ai-brainstorming") {
    prompt = `@${job.agent} Brainstorm AI project ideas for "${b.topic}"`;
  } else if (job.agent === "ai-solution-architect") {
    prompt = `@${job.agent} Design an architecture for "${b.topic}"`;
  } else if (job.agent === "ai-implementor") {
    let archRef = "";
    if (b.architectureDocs?.length) {
      archRef = ` Read and use these architecture documents as your foundation: ${b.architectureDocs.join(", ")}.`;
    } else if (b.architecturePath) {
      archRef = ` Use the existing architecture at ${b.architecturePath} as the foundation.`;
    }
    prompt = `@${job.agent} Build a full project for "${b.topic}".${archRef}`;
  } else if (job.agent === "ai-demo-conductor") {
    let projRef = "";
    if (b.projectDocs?.length) {
      projRef = ` The project files are: ${b.projectDocs.join(", ")}.`;
    } else if (b.projectPath) {
      projRef = ` The project is at ${b.projectPath}.`;
    }
    prompt = `@${job.agent} Create demos for "${b.topic}".${projRef}`;
  } else {
    prompt = `@${job.agent} Create ${levelPart}${durationPart}content about "${b.topic}"`;
  }

  if (b.audience) prompt += ` for ${b.audience}`;
  if (b.notes) prompt += `. ${b.notes}`;

  return prompt;
}

/**
 * Hook that auto-sends the initial brief prompt when a job transitions
 * from "queued" to "running" (WebSocket connected). Safe to call from
 * any page — deduplicates via a ref so the prompt is sent at most once.
 */
export function useAutoSendBrief(
  jobId: string | null,
  sendMessage: (content: string) => void,
) {
  const promptSent = useRef(false);

  // Reset when job ID changes — but only if it's a brand new job with no events
  useEffect(() => {
    if (!jobId) return;
    const existing = useJobStore.getState().getJob(jobId);
    promptSent.current = !!(existing && existing.events.length > 0);
  }, [jobId]);

  const job = useJobStore((s) => (jobId ? s.getJob(jobId) : undefined));

  useEffect(() => {
    if (!job || promptSent.current) return;
    // Wait until the job transitions from "queued" to "running" (WS connected)
    if (job.status !== "running") return;

    const prompt = buildPromptFromBrief(job);
    if (!prompt) {
      promptSent.current = true;
      return;
    }

    promptSent.current = true;
    sendMessage(prompt);
  }, [job?.id, job?.status, sendMessage]);
}
