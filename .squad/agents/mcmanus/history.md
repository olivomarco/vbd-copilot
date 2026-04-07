# Project Context

- **Owner:** Marco Olivo
- **Project:** CSA-Copilot — AI-powered engagement platform for Cloud Solution Architects. Built on GitHub Copilot SDK with 4 workflows: presentations, demos, AI projects, hackathons. 27 agent definitions orchestrated by conductor agents.
- **Stack:** Python 3.11+, GitHub Copilot SDK (0.1.29), FastAPI, Rich, python-pptx, Electron/TypeScript frontend, YAML agent definitions
- **Key files:** app.py (CLI entry), router.py (agent routing), tools.py (custom tools), store.py (SQLite event store), collector.py (event collector), server.py (FastAPI desktop server), ui.py (Rich terminal UI)
- **Agent loading:** agents/ package — loader.py (FileSystemAgentSource), models.py (AgentConfig), registry.py (AgentCatalog). Scans agent_defs/ recursively for .agent.md files.
- **Dependencies:** pyproject.toml — github-copilot-sdk, mcp, pydantic, fastapi, rich, python-pptx, prompt-toolkit
- **Created:** 2026-04-02

## Learnings

<!-- Append new learnings below. Each entry is something lasting about the project. -->

## Deep Backend Study — 2026-04-04

### app.py — Main Application Lifecycle (~850 lines)

- Entry: main_entry() parses --server flag → main() (CLI) or _server_main(port) (FastAPI)
- CLI init: EventStore(~/.csa-copilot/csa-copilot.db, 90d retention), EventCollector, CopilotUI, resize watcher
- Client: CopilotClient(github_token=env GITHUB_TOKEN), client.start() spawns CLI subprocess
- Session: create_session(agent_hint) → passes ALL_AGENT_CONFIGS, ALL_CUSTOM_TOOLS, ALL_SKILL_DIRS
- Turn loop: prompt → route_to_agent() → send_and_wait(timeout=14400) → event stream → output detection
- 13 slash commands: /new, /agent, /model, /debug, /sessions, /usage, /resume, /compact, /clear, /quit, /help, /agents, /samples, /tutorial
- Error recovery: BrokenPipeError → client.restart() + retry. TimeoutError, JsonRpcError caught per-turn.
- Output detection: _find_new_outputs(since) scans outputs/ for mtime >= epoch, filters by suffix/dir
- Cleanup: end session (resumable=True), stop client, close store

### server.py + server_adapter.py — FastAPI Layer

- server.py (~400 lines): configure() injects globals. Endpoints: /sessions (CRUD), /usage, /outputs, /file (path-validated)
- Security: _safe_outputs_path() validates against directory traversal
- server_adapter.py (~300 lines): WebSocketEventAdapter per-session multiplexing. _ws_map dict of sets of WebSocket connections per session_id. Serializes SDK events to newline-delimited JSON.

### router.py — Message Routing (~185 lines)

- Two-stage: (1) @mention regex `^@([\w-]+)\s` → ROUTABLE_AGENTS lookup, (2) LLM classifier
- Classifier: lazy-created session (GPT-4.1, 15s timeout), system_message lists all routable agents
- detect_agent(prompt) → route_to_agent(session, prompt) → session.rpc.agent.select() + model.switch_to()

### tools.py — Custom Tools (~550 lines)

- bing_search: API call with HTML scraping fallback (urllib)
- run_pptx_qa_checks: subprocess call to pptx_qa_checks.py, returns JSON findings
- run_demo_qa_checks: subprocess call to demo_qa_checks.py
- ALL_CUSTOM_TOOLS list injected into session creation

### store.py + queries.py — Persistence

- store.py (~900 lines): SQLite WAL mode, foreign keys ON. Schema: sessions (id, agent, model, status, token counts, resumable), turns (id, session_id, turn_number, prompt, response, tokens, status), invocations (id, turn_id, type, name, input, output, status)
- Methods: start_session(), end_session(), start_turn(), end_turn(), record_invocation(), complete_invocation(), list_sessions(), resolve_prefix()
- queries.py (~150 lines): Stateless aggregation — list_sessions(), get_session_detail(), usage_by_agent(), usage_by_model(). Returns plain dicts (frontend-agnostic).

### collector.py — Event Bridge (~230 lines)

- EventCollector bridges SDK events → EventStore writes
- Hooks: on_session_created/ended, on_turn_start/end, on_usage, on_tool_start/end, on_subagent_start/end
- on_turn_end(): calls pricing.estimate_cost(), updates session token counters

### pricing.py — Cost Calculation

- MODEL_PRICING dict: model_name → (input_cost_per_1M, output_cost_per_1M)
- estimate_cost(model, input_tokens, output_tokens) → USD float
- Default fallback: (2.50, 10.00) per 1M tokens

### agents/ Package — Agent Loading

- __init__.py: Loads via FileSystemAgentSource(agent_defs/) → AgentCatalog. Exports: AGENTS, ROUTABLE_AGENTS, ALL_AGENT_CONFIGS, ALL_SKILL_DIRS, DEFAULT_MODEL ("claude-opus-4.6"), DEFAULT_TIMEOUT (14400s)
- loader.py: FileSystemAgentSource scans agent_defs/**/*.agent.md. yaml.safe_load for frontmatter.
- models.py: AgentConfig(name, display_name, description, prompt, tools, infer)
- registry.py: AgentCatalog immutable. Separates routable (infer=True) from subagents.

### commands/ — CLI Slash Commands

- sessions.py: /sessions [all|end|name|cleanup|<id>] — Rich table rendering, prefix resolution
- usage.py: /usage [all|--agent|--model|--period] — context bar, cost summaries

### ui.py — Terminal UI (~1400 lines)

- CopilotUI: Rich console + prompt_toolkit session
- handle_event(): processes 40+ SDK event types. Always-on: ASSISTANT_MESSAGE_DELTA (stream display), TOOL_EXECUTION_START/COMPLETE (tracker + collector), SESSION_ERROR. Subagent: STARTED/COMPLETED/FAILED. Usage: ASSISTANT_USAGE.
- Spinner: _baking_pulse() — full-width ANSI bar (agent, model, elapsed). Suppresses echo.
- Prompt: prompt_session with history, Tab completion, @mention completer
- Resize: _resize_poll() + full redraw from _history buffer
- Tutorial: 8-page carousel with arrow-key navigation

### Key Patterns

1. Error recovery: BrokenPipeError → client.restart()
2. Event dedup: _seen_event_ids set (UUID-based)
3. Tool pending map: _pending_invocations bridges tool name → inv_id
4. Output detection: mtime-based grace period scan
5. Context tracking: turn-level tokens aggregated to session for /usage
6. Prefix resolution: short session IDs (12 chars) → resolve_prefix() finds full UUID

## Phase 1 Backend — SessionConnection, Envelope, Snapshot (2026-04-07)

### What was done
- **SessionConnection class** added to `server_adapter.py`: encapsulates all per-session WebSocket state (websockets, cancel_flag, input_queue, pending_input, last_done, active_subagents, seen_event_ids, tool_starts, event_handler_unsub, seq counter). Replaces 10+ module-level dicts.
- **_connections registry**: `dict[str, SessionConnection]`. All public functions delegate to it while keeping identical signatures for backward compat.
- **v1 message envelope protocol**: `_envelope(conn, msg_type, data, correlation_id)` wraps every outgoing message with `{v, type, id, seq, ts, correlationId, data}`. Monotonic `seq` per session for ordering; UUID `id` per message.
- **Correlation IDs**: tool lifecycle (start → complete) and subagent lifecycle (started → completed/failed) share a UUID correlation_id so frontend can pair events. Stored in `conn.tool_starts` as `(epoch, corr_id)` tuples and `conn.subagent_correlations` dict.
- **Session snapshot**: `build_snapshot(session_id)` returns an enveloped `session_snapshot` message with status, pending_input, last_done, active_subagents, and seq. Sent on WS reconnect instead of individual replays.
- **New SDK events forwarded**: `SUBAGENT_FAILED` and `SUBAGENT_SELECTED` now emit to frontend. Future placeholders for `TOOL_EXECUTION_PROGRESS` and `ASSISTANT_INTENT`.
- **server.py changes**: imports updated (removed `_ws_map`, added `get_connection`, `build_snapshot`), snapshot replaces individual pending/done replays, `add_ws` now returns bool for is_first detection.
- **Tests**: 26 new tests in `tests/test_session_connection.py`. Full suite: 312 passed, 0 failed.

### Key decisions
- Legacy terminal mode (`_active_ws`, `_cancel_flag`, `_user_input_queue`) preserved untouched.
- `push_user_response` uses `_get_or_create()` (not `_connections.get()`) so push/pop work even without a WS connection (e.g., tests).
- `remove_ws` triggers `cleanup()` when last WS disconnects — unsubscribes the event handler and clears state.
- All event handler messages now go through `emit()` wrapper which envelopes automatically. Raw `_send()` stays available for backward-compat direct calls from server.py.
