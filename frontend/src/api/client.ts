/**
 * REST API client for the CSA-Copilot FastAPI backend.
 *
 * In dev mode, Vite proxies /api/* to the Python server.
 * In production (Electron), we call the server directly.
 */

const BASE =
  import.meta.env.VITE_API_URL ?? "";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...init?.headers,
    },
  });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`API ${res.status}: ${body}`);
  }
  return res.json();
}

// ── Health ─────────────────────────────────────────

export async function checkHealth() {
  return request<{ status: string; version: string }>("/health");
}

// ── Agents ─────────────────────────────────────────

import type { Agent, OutputFile, GroupedOutput, PptxSlide, SessionInfo, Turn, Invocation, UsageStats } from "./types";

export async function listAgents(): Promise<Agent[]> {
  return request<Agent[]>("/agents");
}

// ── Sessions ───────────────────────────────────────

export async function createSession(agent?: string, model?: string) {
  return request<{ session_id: string; model: string }>("/sessions", {
    method: "POST",
    body: JSON.stringify({ agent, model }),
  });
}

export async function listSessions(all = false): Promise<SessionInfo[]> {
  return request<SessionInfo[]>(`/sessions?all=${all}`);
}

export async function getSession(id: string): Promise<SessionInfo> {
  return request<SessionInfo>(`/sessions/${id}`);
}

export async function getSessionTurns(id: string): Promise<Turn[]> {
  return request<Turn[]>(`/sessions/${id}/turns`);
}

export async function getTurnInvocations(
  sessionId: string,
  turnNumber: number,
): Promise<Invocation[]> {
  return request<Invocation[]>(
    `/sessions/${sessionId}/turns/${turnNumber}/invocations`,
  );
}

export async function resumeSession(id: string) {
  return request<{ session_id: string; agent: string; model: string; turn_count: number }>(
    `/sessions/${id}/resume`,
    { method: "POST", body: JSON.stringify({}) },
  );
}

export async function endSession(id: string) {
  return request<{ ok: boolean }>(`/sessions/${id}`, { method: "DELETE" });
}

export async function getSessionStatus(id: string): Promise<{
  session_id: string;
  status: string;
  in_memory: boolean;
  has_running_turn: boolean;
  turn_count: number;
  resumable: boolean;
  pending_input?: { type: string; question: string; choices?: string[] } | null;
  output_files?: string[];
}> {
  return request(`/sessions/${id}/status`);
}

export async function getSessionEvents(id: string): Promise<Array<{
  type: string;
  time: string;
  data: Record<string, unknown>;
}>> {
  return request(`/sessions/${id}/events`);
}

// ── Outputs ────────────────────────────────────────

export async function listOutputs(): Promise<OutputFile[]> {
  return request<OutputFile[]>("/outputs");
}

export async function listGroupedOutputs(): Promise<GroupedOutput[]> {
  return request<GroupedOutput[]>("/outputs/grouped");
}

export async function deleteGroupedOutput(id: string): Promise<{ ok: boolean; deleted: string[] }> {
  return request<{ ok: boolean; deleted: string[] }>(
    `/outputs/grouped?id=${encodeURIComponent(id)}`,
    { method: "DELETE" },
  );
}

export async function readFile(path: string): Promise<{ path: string; content: string }> {
  return request<{ path: string; content: string }>(
    `/file?path=${encodeURIComponent(path)}`,
  );
}

export async function previewPptx(
  path: string,
  maxWidth = 1280,
): Promise<{ slides: PptxSlide[]; total: number }> {
  return request<{ slides: PptxSlide[]; total: number }>("/preview/pptx", {
    method: "POST",
    body: JSON.stringify({ path, max_width: maxWidth }),
  });
}

export async function previewPptxHifi(
  path: string,
  maxWidth = 1280,
): Promise<{ slides: PptxSlide[]; total: number }> {
  return request<{ slides: PptxSlide[]; total: number }>("/preview/pptx-hifi", {
    method: "POST",
    body: JSON.stringify({ path, max_width: maxWidth }),
  });
}

// ── Usage ──────────────────────────────────────────

export async function getUsage(
  period = "all",
  agent?: string,
  model?: string,
): Promise<UsageStats> {
  const params = new URLSearchParams({ period });
  if (agent) params.set("agent", agent);
  if (model) params.set("model", model);
  return request<UsageStats>(`/usage?${params}`);
}

// ── File download helper ───────────────────────────

export function getDownloadUrl(path: string): string {
  return `${BASE}/file?path=${encodeURIComponent(path)}`;
}
