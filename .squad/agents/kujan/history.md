# Kujan — History

## Project Context
- **Owner:** Marco Olivo
- **Project:** CSA-Copilot — AI-powered engagement platform for Cloud Solution Architects
- **Stack:** Python 3.11+, GitHub Copilot SDK, FastAPI, Rich, python-pptx, Electron/TypeScript
- **Workflows:** Presentations (slides), demos, AI projects, hackathons
- **Architecture:** 27+ agent definitions, 28 skills, Electron desktop + web frontend, CLI terminal UI

## Core Context

*Summarized from onboarding deep-read (2026-04-06). Full text archived.*

**Product:** CSA-Copilot v3.0.0 — AI content platform for Microsoft CSAs. Single prompt → production-quality content in ~1 hour. "Deep research, not instant generation."

**Four workflows:** Presentations (.pptx), Demos (.md + scripts), AI Projects (brainstorm→architecture→Bicep+code+CI/CD), Hackathons (What-The-Hack packages). 27 agent defs across 4 categories. 28 skills (6 custom + 22 Azure).

**Stack:** Python 3.11+, Copilot SDK 0.1.29, FastAPI, SQLite WAL, Rich + prompt_toolkit (CLI), React 19 + Vite 6 + Fluent UI v9 + Zustand + Electron 41 (desktop). Models: claude-sonnet-4.6 (work), claude-opus-4.6 (brainstorming/default), GPT-4.1 (routing).

**Architecture:** CLI (`app.py`) and desktop (`server.py`+`server_adapter.py`) share agent/tool/event pipelines. Agent defs are Markdown+YAML in `agent_defs/`, loaded by `agents/` package. Routing: @mention or GPT-4.1 classifier. Conductors orchestrate subagents via SDK `task` tool (parallel dispatch mandatory). Observability: SQLite 3-table schema (sessions/turns/invocations), EventCollector bridge, pricing module.

**Frontend:** 6 pages (Launchpad, AgentWorkspace, MissionControl, OutputLibrary, Sessions, Settings). Zustand stores: jobStore (core), outputStore, settingsStore, tutorialStore. WebSocket streaming, cross-tab sync, PPTX/Markdown/DrawIO viewers. NO emoji in UI — Fluent UI icons only.

**Key conventions:** `uv` not `pip`, 80% test coverage gate, fragments are unindented by design, don't refactor `pptx_utils.py`, outputs never in repo root, agent defs use YAML frontmatter.

**Team consolidation (2026-04-04):** 4 dev roles → 2. McManus = all Python, Redfoot = all TypeScript/frontend.

## Learnings

### Product Gaps & Priorities (from onboarding audit)

**High priority:**
1. Per-agent model/timeout silently broken — `registry.py` ignores agent name, all agents use claude-opus-4.6 (5x cost vs claude-sonnet-4.6). YAML fields parsed but never injected into AgentConfig.
2. SSL verification disabled in Bing scraping (`tools.py` line ~37) — MITM risk.
3. Content humanizer skill integration opaque — exists in skills/ but no agent references it in tools.

**Medium:** Frontend zero test coverage, no crash recovery for long jobs, minimal desktop settings store.

**Low:** Plugin distribution (private repo), no rate limiting, need E2E smoke tests.

**Quick wins:** Parse per-agent model/timeout from YAML, fix SSL context, add frontend error boundary for PPTX viewer.

### Current State Assessment

- CLI is production-quality for single-user use.
- Desktop UI is functional 0.x — needs hardening (WS reconnection logic is complex).
- Agent system architecture is clean and extensible (zero-code new workflows).
- Quality gates comprehensive: QA checks, human approval, 4-reviewer gate, 80% coverage.
- 17 backend test files. Zero frontend tests.

## Cross-Agent Update — Phase 1 SDK↔Frontend Bridge (2026-04-07)

Phase 1 completed by McManus + Redfoot + Hockney in parallel:
- **server_adapter.py** refactored: `SessionConnection` class, v1 envelope protocol, `build_snapshot()` for reconnect, correlation IDs
- **Frontend** updated: envelope unwrap, ID-based dedup, snapshot hydration, dual-WS double-counting fix
- **34 new tests**, 346 total passing, zero new errors
- **Relevance to backlog:** McManus's refactor addresses some of the reconnection reliability concerns. Frontend test coverage (#4 in observations) still at zero — only backend tests added. Per-agent model/timeout (#1) not yet addressed.
