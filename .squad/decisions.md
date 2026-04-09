# Squad Decisions

## Active Decisions

### 2026-04-04: Team consolidation — 4 dev roles → 2

**By:** Marco Olivo (via Squad Coordinator)

**What:** Consolidated overlapping dev roles to reduce redundancy:
- **McManus** expanded from Backend Dev → **Backend & CLI Dev** (absorbs Kobayashi's CLI work)
- **Redfoot** expanded from Web Dev → **Full-Stack Frontend Dev** (absorbs Verbal's Electron work)
- **Verbal** (Frontend Dev) → retired to alumni
- **Kobayashi** (CLI Dev) → retired to alumni

**Why:** User identified overlap between backend/CLI (both Python, shared ownership of app.py) and frontend/web (Electron wraps the React app). Two consolidated roles create cleaner ownership boundaries: McManus = all Python, Redfoot = all TypeScript/frontend.

**Impact:** Team reduced from 7 active members + Scribe/Ralph to 5 active members + Scribe/Ralph. All knowledge preserved in alumni folders.

### 2026-04-07: Phase 1 Backend — SessionConnection + v1 Envelope Protocol

**By:** McManus (Backend & CLI Dev)

**What:** Replaced 10+ module-level dicts in `server_adapter.py` with a `SessionConnection` class. Added v1 message envelope protocol — every outgoing WebSocket message wrapped with `{v, type, id, seq, ts, correlationId, data}`. Added `build_snapshot()` for reconnecting clients. Forwarded `SUBAGENT_FAILED` and `SUBAGENT_SELECTED` SDK events. Updated `server.py` to send snapshot on WS connect.

**Why:** Module-level dicts caused memory leaks, race conditions, and unreliable reconnection. Raw JSON messages had no ordering, dedup, or correlation support. Snapshot gives reconnecting clients a single consistent state picture.

**Impact:** server_adapter.py rewritten, server.py updated, 34 new tests. All backward compat preserved.

### 2026-04-07: Frontend envelope protocol — backward-compatible unwrap + dual-WS fix

**By:** Redfoot (Full-Stack Frontend Dev)

**What:** Frontend supports v1 WS envelope protocol with backward compat for raw messages. ID-based dedup replaces text-based dedup. `session_snapshot` handler restores state on reconnect. `useActiveJobWatcher` skips non-terminal events when workspace WS is active — fixes dual-WS double-counting bug.

**Why:** McManus shipped backend envelope protocol. Frontend needed matching parser, reliable dedup, reconnect hydration, and the dual-WS bug needed fixing.

**Impact:** types.ts (15 new interfaces), useWebSocket.ts (envelope unwrap + dedup + snapshot), useActiveJobWatcher.ts (dual-WS guard). No component API changes.

### 2026-04-07: Phase 2 Backend — Response persistence, subagent_name, envelope consistency

**By:** McManus (Backend & CLI Dev)

**What:** Four changes to server-mode backend:
1. Assistant response text now persisted via `response_buffer` on `SessionConnection` — deltas accumulated during streaming, flushed at `on_turn_end()`.
2. `subagent_name` column added to invocations table (idempotent migration). `record_invocation()` and `collector.on_tool_start()` both accept the param. `get_session_events` uses DB column with timestamp fallback for old data.
3. All three `_user_input` callbacks in server.py now use `_envelope()` wrapping — consistent with Phase 1 envelope protocol.
4. `get_session_events` now emits `assistant_message` events from persisted response text for full conversation history rendering.

**Why:** Server mode was losing assistant responses, tool→subagent mapping relied on fragile timestamp heuristics, and `_user_input` callbacks bypassed the envelope protocol.

**Impact:** server_adapter.py, store.py, collector.py, server.py modified. 356 tests pass. CLI mode unaffected.

### 2026-04-07: Phase 3 Backend — Server-push state events, heartbeat, full envelope coverage

**By:** McManus (Backend & CLI Dev)

**What:** Three reliability improvements to server-mode WebSocket layer:
1. `emit_state_changed()` pushes `session_state_changed` events when sessions are deleted. Frontend can stop its 3s polling and rely on server-push instead.
2. Server-side heartbeat sends `heartbeat` messages every 15s to all connected sessions. Lets frontend detect stale connections without relying on SDK event flow.
3. Every remaining raw `_send({"type": ...})` in server.py now uses the v1 envelope protocol. Zero raw sends remain — 100% envelope coverage.

Bonus: Switched from deprecated `@app.on_event("startup/shutdown")` to `lifespan` context manager.

**Why:** Frontend was polling `/sessions/{id}/status` every 3s to detect session end — expensive and fragile. Heartbeat fills the gap when no SDK events flow (idle sessions, slow agent operations). Envelope coverage ensures all messages get dedup IDs, sequence numbers, and timestamps.

**Impact:** server_adapter.py (emit_state_changed, heartbeat functions), server.py (lifespan, all raw sends wrapped), test_server_ws.py (assertion updated). 364 tests pass. CLI mode unaffected.

### 2026-04-07: Phase 3 Frontend — Server-push state changes, stale detection, exponential backoff

**By:** Redfoot (Full-Stack Frontend Dev)

**What:** Frontend now handles `session_state_changed` server-push events to detect session endings immediately (both in workspace WS and background watcher). Stale connection detection added — if no server message in 45s (3 missed heartbeats), force reconnect. Reconnection uses exponential backoff (1s→30s cap, ±25% jitter) instead of fixed 2s delay. Safety-net status poll pushed from 3s to 10s since server-push makes it rarely needed.

**Why:** McManus added server-side heartbeat (15s) and `session_state_changed` push events. Frontend needed matching handlers. Fixed delay reconnect could cause thundering herd on server restart. Stale detection catches TCP half-open / zombie connections that never close cleanly.

**Impact:** types.ts (+2 interfaces), useWebSocket.ts (new handler, stale detection, backoff), useActiveJobWatcher.ts (new handler). No component API changes. Backward compatible — envelope unwrap handles both old and new message types.

### 2026-04-06: Kujan onboarding observations — product priorities

**By:** Kujan (Product Owner)

**What:** Nine observations from onboarding deep-read. High priority: (1) per-agent model/timeout silently broken — all agents run on claude-opus-4.6 instead of cheaper models, (2) SSL verification disabled in Bing scraping (MITM risk), (3) content-humanizer skill integration opaque. Medium: frontend zero test coverage, no crash recovery for long jobs, minimal desktop settings. Low: plugin distribution, rate limiting, E2E smoke tests.

**Why:** Product owner onboarding audit to establish prioritized backlog.

**Impact:** Informs next sprint priorities. Cost savings from fixing model/timeout parsing (#1) are immediate.

### 2026-04-07: Forward verbose/debug SDK events + frontend LiveActivityLog

**By:** McManus (Backend & CLI Dev), Redfoot (Full-Stack Frontend Dev)

**What:** Backend now forwards 11 additional SDK event types over WebSocket (reasoning deltas, tool progress, intent, compaction, turn start/end, handoff, subagent deselected). Frontend adds verbose mode toggle in Settings and a LiveActivityLog component in MissionControl — running jobs show collapsible activity feeds with always-visible critical events and verbose-only debug events. 200-event cap with auto-scroll.

**Why:** Frontend had no WebSocket in MissionControl — jobs appeared "stuck" when waiting for input. Verbose mode gives the same event visibility as CLI `/debug` mode.

**Impact:** server_adapter.py (11 new event handlers), settingsStore.ts, Settings.tsx, MissionControl.tsx, new LiveActivityLog.tsx. No API changes. Backward compatible — verbose defaults to off.

### 2026-04-09: Path traversal fix in grouped delete (demos branch) + security hardening

**By:** Keaton (Lead), McManus (Backend & CLI Dev), Hockney (Tester)

**What:** Found and fixed a HIGH-severity path traversal vulnerability in `DELETE /outputs/grouped` demos branch. The `slug` from user input was used directly in `Path()` construction without `resolve()` + `relative_to()` validation — allowing `../../` to escape `outputs/` and delete arbitrary directories via `shutil.rmtree`. Hackathons/ai-projects branches already had the guard; demos was missed. Fix adds defence-in-depth slug validation (rejects `..`, `/`, `\`, null bytes) plus `resolve()` + `relative_to()` containment matching the other branches. 48 security tests added covering all file-serving endpoints — no additional vulnerabilities found. All 142 tests pass.

**Why:** Security audit requested by Marco Olivo. All file-handling endpoints reviewed for traversal, symlink, double-encoding, and null byte attacks.

**Impact:** server.py `delete_grouped_output()` patched. test_server_extended.py +48 tests. Two LOW findings noted: grouped delete responses leak absolute paths; `rglob()` follows symlinks in metadata. Critical contract reaffirmed: any new endpoint touching file paths MUST use `_safe_outputs_path()` or replicate `resolve()` + `is_relative_to()`.

## Governance

- All meaningful changes require team consensus
- Document architectural decisions here
- Keep history focused on work, decisions focused on direction
