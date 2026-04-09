# Project Context

- **Owner:** Marco Olivo
- **Project:** CSA-Copilot — AI-powered engagement platform for Cloud Solution Architects. Built on GitHub Copilot SDK with 4 workflows: presentations, demos, AI projects, hackathons. 27 agent definitions orchestrated by conductor agents.
- **Stack:** Python 3.11+, GitHub Copilot SDK (0.1.29), FastAPI, Rich, python-pptx, Electron/TypeScript frontend, YAML agent definitions
- **Key files:** app.py (CLI entry), router.py (agent routing), tools.py (custom tools), store.py (SQLite event store), collector.py (event collector), server.py (FastAPI desktop server), ui.py (Rich terminal UI)
- **Agent defs:** agent_defs/{slides,demos,ai-project,hackathons}/ — Markdown with YAML frontmatter, loaded by agents/ package
- **Skills:** 28 skills in skills/ — pptx-generator, demo-generator, hackathon-generator, architecture-design, code-project, content-humanizer, 22 Azure skills
- **Tests:** 13 test files in tests/, 80% coverage gate (pytest --cov)
- **Created:** 2026-04-02

## Learnings

<!-- Append new learnings below. Each entry is something lasting about the project. -->

## Deep Codebase Study — 2026-04-04

### Architecture Overview

CSA-Copilot is a two-mode AI orchestration platform (CLI + desktop server) built on GitHub Copilot SDK (v0.1.29):
- **CLI mode** (default): Rich terminal UI + interactive sessions via prompt_toolkit
- **Server mode** (`--server`): FastAPI + WebSocket for Electron desktop frontend
- Entry points: `main()` (CLI) and `_server_main(port)` (FastAPI+uvicorn)
- Both share identical agent/tool registration and event collection pipelines

Core orchestration: 4 conductor workflows (slides, demos, ai-projects, hackathons) with 27 total agent definitions delegating to specialized subagents via SDK's native `task` tool.

### Key File Map

| File | Lines | Purpose |
|------|-------|---------|
| app.py | ~850 | Main entry, session lifecycle, 13 slash commands, turn loop |
| ui.py | ~1400 | Rich terminal UI, 40+ event types, spinner, prompt, tutorial |
| server.py | ~400 | FastAPI: /sessions, /usage, /outputs, /file endpoints |
| server_adapter.py | ~300 | Per-session WebSocket multiplexing, event serialization |
| router.py | ~185 | Two-stage routing: @mention regex → LLM classifier (GPT-4.1) |
| tools.py | ~550 | Custom tools: bing_search, run_pptx_qa_checks, run_demo_qa_checks |
| store.py | ~900 | SQLite WAL, 3 tables: sessions/turns/invocations, 90-day retention |
| collector.py | ~230 | Event bridge: SDK events → EventStore writes |
| queries.py | ~150 | Stateless aggregation over EventStore for dashboards |
| pricing.py | ~60 | Model→cost lookup, estimate_cost(model, in_tokens, out_tokens) |
| agents/__init__.py | ~60 | Backward-compat shim: AGENTS, ROUTABLE_AGENTS, ALL_AGENT_CONFIGS |
| agents/loader.py | ~50 | FileSystemAgentSource: scans agent_defs/**/*.agent.md |
| agents/models.py | ~20 | AgentConfig dataclass |
| agents/registry.py | ~70 | AgentCatalog: immutable registry, model/timeout accessors |
| commands/sessions.py | ~150 | /sessions slash command handler |
| commands/usage.py | ~100 | /usage slash command handler |

### SDK Integration Patterns

- CopilotClient spawns CLI subprocess (stdio). Auth via GITHUB_TOKEN env or host keychain.
- Session created with: model, streaming, custom_agents (ALL_AGENT_CONFIGS), tools (ALL_CUSTOM_TOOLS), skill_directories (ALL_SKILL_DIRS), hooks.
- Events streamed via session.on(callback) → handle_event(). 40+ event types (SessionEventType enum).
- Each event has .id (UUID) for dedup via _seen_event_ids set.
- Subagent delegation: conductors use `task` tool (SDK-native). SDK spawns fresh session for subagent.
- Session resumption: client.resume_session(id) reconnects to server-side state.
- DEFAULT_MODEL = "claude-opus-4.6", DEFAULT_TIMEOUT = 14400s (4h).

### Data Flow

```
User prompt → ui.prompt() → route_to_agent() → @mention OR LLM classify
  → session.rpc.agent.select() + model.switch_to()
  → collector.on_turn_start() → EventStore.start_turn()
  → session.send_and_wait() → SDK → LLM → tool calls → event stream
  → ui.handle_event() → (display + collector.on_* + server_adapter)
  → send_and_wait() returns → _find_new_outputs() → collector.on_turn_end()
```

### Agent System

- Discovery: FileSystemAgentSource scans agent_defs/ recursively for *.agent.md
- YAML frontmatter: name, display_name, description, infer, tools[], skills[]
- Routable (infer=true): slide-conductor, demo-conductor, hackathon-conductor, ai-brainstorming, ai-solution-architect, ai-implementor
- Subagents (infer=false): researchers, builders, editors, reviewers, QA agents
- Conductor pattern: conductors dispatch parallel subagent batches via task tool

### Conventions & Landmines

- `uv` not `pip` for all dependency ops
- Agent defs: *.agent.md files, NO extra `---` in prompt body
- Fragment files in outputs/slides/.fragments/ are UNINDENTED by design
- skills/pptx-generator/pptx_utils.py: DO NOT REFACTOR (shared contract)
- Output paths: outputs/{slides,demos,hackathons,ai-projects}/ — NEVER repo root
- Test coverage ≥ 80% (fail_under=80 in pyproject.toml)
- Frontend: NO emoji — use Fluent UI @fluentui/react-icons
- SQLite WAL mode, foreign keys ON, 90-day retention auto-purge
- Server: _safe_outputs_path() prevents directory traversal

### Key Dependencies (pyproject.toml)

- github-copilot-sdk==0.1.29, pydantic>=2.0, pyyaml>=6.0
- rich>=13.0, prompt-toolkit>=3.0.43, python-pptx>=1.0.2
- fastapi>=0.115, uvicorn[standard]>=0.32, websockets>=13.0
- mcp>=1.0, pillow>=11.0, pymupdf>=1.24, markitdown>=0.1.0

## Cross-Agent Update — Phase 1 SDK↔Frontend Bridge (2026-04-07)

Phase 1 completed by McManus + Redfoot + Hockney in parallel:
- **server_adapter.py** now uses `SessionConnection` class (replaces module-level dicts), v1 envelope protocol `{v, type, id, seq, ts, correlationId, data}`, `build_snapshot()` for reconnect
- **Frontend** unwraps envelopes with backward compat, ID-based dedup, snapshot hydration, dual-WS bug fixed
- **34 new tests** in `tests/test_server_adapter.py`, 346 total passing
- Decisions recorded: SessionConnection pattern, envelope protocol structure, frontend backward-compat strategy

## Security Review — Path Traversal Analysis (2026-04-09)

Reviewed all file-path-accepting endpoints in `server.py` for path traversal, double-encoding, symlink, and null byte attacks.

### Key Findings
- **HIGH:** `DELETE /outputs/grouped` demos branch — `slug` from user input used directly in `Path()` construction without `resolve()` + `relative_to()` check. Can escape `outputs/` via `../../`. The hackathons/ai-projects branches have proper guards; demos was missed. Fix: add same containment check.
- **LOW:** Grouped delete responses leak absolute server paths (all branches). Single-file `DELETE /outputs` correctly returns relative paths.
- **LOW:** `GET /outputs` follows symlinks via `rglob()`, can leak external file metadata. Content reads are safe via `_safe_outputs_path()`.
- **SAFE:** `_safe_outputs_path()` is correct — handles null bytes, symlinks, double-encoding, `..` traversal. Covers `/file`, `/file/download`, `DELETE /outputs`, `/outputs/zip`, `/outputs/metadata`, `/preview/pptx`.
- **SAFE:** Double-encoding is not exploitable — Starlette decodes once, `%252F` becomes literal `%2F` which `Path()` treats as filename chars.
- **SAFE:** ZIP arcname uses relative paths only.

### Architecture Pattern
- **Critical contract:** Any new endpoint that touches file paths MUST use `_safe_outputs_path()` or replicate `resolve()` + `is_relative_to(outputs_resolved)`. No exceptions.
- The demos grouped delete is the one place this contract was broken.
