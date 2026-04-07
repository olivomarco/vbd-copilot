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

### 2026-04-06: Kujan onboarding observations — product priorities

**By:** Kujan (Product Owner)

**What:** Nine observations from onboarding deep-read. High priority: (1) per-agent model/timeout silently broken — all agents run on claude-opus-4.6 instead of cheaper models, (2) SSL verification disabled in Bing scraping (MITM risk), (3) content-humanizer skill integration opaque. Medium: frontend zero test coverage, no crash recovery for long jobs, minimal desktop settings. Low: plugin distribution, rate limiting, E2E smoke tests.

**Why:** Product owner onboarding audit to establish prioritized backlog.

**Impact:** Informs next sprint priorities. Cost savings from fixing model/timeout parsing (#1) are immediate.

## Governance

- All meaningful changes require team consensus
- Document architectural decisions here
- Keep history focused on work, decisions focused on direction
