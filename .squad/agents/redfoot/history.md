# Project Context

- **Owner:** Marco Olivo
- **Project:** CSA-Copilot — AI-powered engagement platform for Cloud Solution Architects. Built on GitHub Copilot SDK with 4 workflows: presentations, demos, AI projects, hackathons. 27 agent definitions orchestrated by conductor agents.
- **Stack:** Python 3.11+, GitHub Copilot SDK (0.1.29), FastAPI, Rich, python-pptx, Electron/TypeScript frontend, YAML agent definitions
- **Key files:** frontend/ (Electron + React app), frontend/src/components/ (React components), frontend/src/pages/ (page views), vite.config.ts (build config), server.py (backend API)
- **Frontend:** React + TypeScript + Vite. Fluent UI icons (no emoji in UI). AgentIcon component for agent rendering. WebSocket for real-time backend communication.
- **Dependencies:** package.json in frontend/ — React, Fluent UI, Vite, TypeScript
- **Created:** 2026-04-03

## Learnings

<!-- Append new learnings below. Each entry is something lasting about the project. -->

## Deep Frontend Study — 2026-04-04

### Project Setup

- **Stack:** React 19 + TypeScript + Vite + Zustand (state) + Fluent UI (components) + Electron (desktop shell)
- **Build:** Vite dev server + Electron main process. Scripts in frontend/package.json.
- **Dependencies:** @fluentui/react-components, @fluentui/react-icons, zustand, react-router-dom, @microsoft/fetch-event-source, react-markdown, remark-gfm

### Component Architecture

- **Shell:** Layout wrapper with Sidebar + main content area
- **Sidebar:** Navigation, session list, agent status indicators
- **Pages:** 8 routes — Home, AgentWorkspace (live monitoring), OutputLibrary (file browser), SlideViewer (PPTX preview), Settings, Sessions, Usage, NewJob
- **BriefForm:** Modal for job creation — agent selection, topic input, content level, duration
- **AgentWorkspace:** Real-time job monitoring — event feed, tool calls, subagent spawns, phase indicators
- **OutputLibrary:** File browser for outputs/ directory — grouped by type, download support
- **SlideViewer:** PPTX preview with keyboard navigation through slides
- **AgentIcon:** Canonical icon renderer — maps 6 agent types to Fluent UI icons with branded colors. NEVER use emoji.

### State Management (Zustand)

- **jobStore:** Main store — persisted to localStorage with cross-tab sync via BroadcastChannel. Caps events at 2000. Tracks jobs, current job, events, phases.
- **settingsStore:** Theme preference (light/dark) + sidebar collapse state
- **outputStore:** Downloaded files cache for output previews

### API Layer

- Backend communicates via FastAPI (server.py) + WebSocket
- WebSocket in useWebSocket hook — streams job events (turn_started, tool_started/completed, phase_changed, waiting_for_input, user_response)
- REST: /sessions (CRUD), /usage, /outputs, /file (path-validated)
- Events flow: WebSocket → jobStore → component re-renders

### Electron Shell

- frontend/electron/ — main process, preload script, IPC channels
- Window management, native menus, app lifecycle
- Wraps the Vite dev server / built web app

### Key Conventions

- **NEVER use emoji in the UI** — always @fluentui/react-icons components
- AgentIcon component is the CANONICAL icon renderer for agents
- AGENT_META emoji field is legacy metadata only — never rendered
- Follow existing component patterns before introducing new ones
- Keep desktop app responsive — agent workflows can run for an hour
- WebSocket reconnection on disconnect

## Phase 1 — Envelope Protocol & Dual-WS Fix — 2026-04-07

### Changes Made
- **types.ts**: Added `WsEnvelope<T>` generic + 15 typed data payload interfaces for all WS event types (tool, subagent, delta, done, error, usage, snapshot, etc.)
- **useWebSocket.ts**: Envelope unwrap (`raw.v === 1` check) with backward compat for raw messages. ID-based dedup via `seenIds` Set (cleared on connect). `session_snapshot` handler restores subagent stack, pending input, and done state on reconnect. Event hydration via `getSessionEvents()` for cold-start/reconnect with <5 events. New cases: `subagent_failed` (removes from stack, updates progress) and `subagent_selected` (informational no-op).
- **useActiveJobWatcher.ts**: Same envelope unwrap. Added guard: when workspace WS (`_ws`) is active, watcher skips all events except terminal `done`/`cancelled` — fixes the dual-WS double-counting bug.

### Key Patterns
- Envelope unwrap: `const isEnvelope = raw.v === 1 && raw.id && raw.data;` — `msg` becomes `raw.data` for envelopes, `raw` for legacy
- ID dedup: `seenIds.current` Set of UUID strings, checked before processing, cleared on `ws.onopen`
- Snapshot hydration: `handleSnapshot()` is a function declaration (hoisted) in hook body, called from inside `connect` callback
- Event hydration: `getSessionEvents()` fetched on open, merged by `type:data` composite key to avoid dupes
- Backward compat: all handlers work with both envelope and raw message formats
- `sendMessage`/`sendUserResponse` unchanged — client→server doesn't use envelopes

## Phase 2 — History Rendering & New Event Types — 2026-04-07

### Changes Made
- **types.ts**: Added `WsAssistantMessage` interface for complete assistant response text from history reconstruction
- **AgentWorkspace.tsx**: Added `assistant_message` and `subagent_failed` to `EventDataMap`. Added rendering: `assistant_message` renders full markdown content (like deltaText but for history), `subagent_failed` renders a danger-styled alert with agent name and error. Both placed before the `delta` null-return in `EventCard`.

### Key Patterns
- `assistant_message` is NOT filtered from `feedEvents` — it passes through naturally since it's not in the exclusion list
- Hydration in `useWebSocket.ts` already works for `assistant_message` — the `ws.onopen` handler fetches `getSessionEvents()` and pushes all unmatched events via composite key dedup
- `assistant_message` is for history only (complete response text); live streaming still uses `delta` events accumulated into `deltaText`
- `subagent_failed` uses Fluent UI semantic color tokens (`colorStatusDangerBackground1`/`colorStatusDangerForeground1`)
- Pre-existing tsc errors in `jobStore.ts` are unrelated (implicit `any` types from Zustand persist middleware)

## Phase 3 — Server-Push State, Stale Detection & Exponential Backoff — 2026-04-07

### Changes Made
- **types.ts**: Added `WsSessionStateChanged` (session_id, status, reason) and `WsHeartbeat` (ts) interfaces
- **useWebSocket.ts**:
  - `session_state_changed` handler in switch — when status="ended", marks job completed and pushes synthetic done event. Replaces reliance on 3s status polling for session end detection.
  - `lastServerMessage` ref updated on every incoming WS message (not just heartbeats) — any message proves connection is alive.
  - Stale detection in heartbeat interval: if no server message in 45s (3 missed 15s heartbeats), force-close and reconnect.
  - Exponential backoff: `getReconnectDelay(attempt)` — 1s, 2s, 4s, 8s, 16s, cap 30s with ±25% jitter. Replaces fixed 2s `RECONNECT_DELAY_MS` for reconnect timer.
  - Safety-net status poll changed from 3s to 10s (rarely needed now with server-push).
- **useActiveJobWatcher.ts**: Added `session_state_changed` handler — finalizes job, clears notifications, fires completion notification when server pushes session ended.

### Key Patterns
- `lastServerMessage.current = Date.now()` at top of `onmessage` before any parsing — covers all message types
- Stale threshold constant `STALE_THRESHOLD_MS = 45_000` — only triggers for non-terminal jobs (checked in the interval guard)
- Jitter formula: `delay * 0.25 * (Math.random() * 2 - 1)` gives ±25% range
- `reconnectAttempts.current` is reset to 0 on successful open, so backoff resets naturally
- `session_state_changed` in watcher uses same terminal-state guard as `done` handler

### 2026-04-07: Verbose Mode + LiveActivityLog for MissionControl
- **settingsStore.ts**: Added `verboseMode: boolean` (default false) + `setVerboseMode` action. Follows existing create-only pattern (no persist middleware).
- **Settings.tsx**: Added Fluent UI `Switch` toggle for verbose mode in the General card, below Theme dropdown. Description text explains what it controls.
- **LiveActivityLog.tsx**: New component at `frontend/src/components/mission/LiveActivityLog.tsx`. Categorizes events into "always" (phase, subagent, waiting, done, errors, files), "verbose" (deltas, tools, reasoning, usage, compaction, turns), and "skip" (pong, heartbeat, snapshot). Accumulates consecutive delta/reasoning_delta events into text blocks. Auto-scroll with scroll-away detection. Caps at 200 visible events. Relative timestamps updated every 10s.
- **MissionControl.tsx**: Created `LiveJobCard` component that wraps running/waiting jobs. Each LiveJobCard calls `useWebSocket(jobId)` to connect WS, reads events from jobStore reactively, and renders a collapsible `LiveActivityLog` below the job summary. Running/waiting sections render `<LiveJobCard>`, completed still uses `<JobCard>`.
- **Key design decision**: Rather than creating `useMultiWebSocket`, used a per-card component wrapper (`LiveJobCard`) that calls `useWebSocket` once per job. This follows React's hooks rules naturally and mirrors how AgentWorkspace does it.
- **Waiting-for-input visibility**: Always shown prominently in yellow highlight even when verbose is off — this is the key fix for "stuck job" perception on MissionControl.
