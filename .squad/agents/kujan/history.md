# Kujan — History

## Project Context
- **Owner:** Marco Olivo
- **Project:** CSA-Copilot — AI-powered engagement platform for Cloud Solution Architects
- **Stack:** Python 3.11+, GitHub Copilot SDK, FastAPI, Rich, python-pptx, Electron/TypeScript
- **Workflows:** Presentations (slides), demos, AI projects, hackathons
- **Architecture:** 27+ agent definitions, 28 skills, Electron desktop + web frontend, CLI terminal UI

## Learnings

### Product Overview

CSA-Copilot is an AI-powered engagement platform for Microsoft Cloud Solution Architects (CSAs). It solves the chronic time-sink of preparing customer-facing technical content: slide decks, demo guides, hackathon packages, and full Azure project implementations. A task that typically takes 4-8 hours of manual work (researching docs, copy-pasting into PowerPoint, writing scripts) is reduced to a single natural-language prompt with ~1 hour of automated generation.

**Target users:** Microsoft Cloud Solution Architects, Solution Engineers, Partner Technical Strategists — anyone who regularly presents Microsoft Cloud technology to customers and needs production-quality content fast.

**Core value proposition:** "Deep research, not instant generation." Every output is sourced from official Microsoft documentation, goes through automated QA checks, and requires human approval at key stops. The result is a strong first draft — not autopilot, but an accelerator.

**Four workflows:**
1. **Presentations** — `.pptx` files with full speaker notes from a single prompt
2. **Demos** — Step-by-step guides with runnable companion scripts
3. **AI Projects** — End-to-end Azure projects: brainstorm → architecture → Bicep + app code + CI/CD + tests
4. **Hackathons** — What-The-Hack-style event packages with progressive challenges

**Version:** 3.0.0. Two interfaces: CLI (stable, battle-tested) and Desktop/Web UI (experimental, Electron-based).

### Architecture Summary

**Runtime Stack:**
- **Backend:** Python 3.11+, GitHub Copilot SDK (v0.1.29), FastAPI, SQLite (WAL mode)
- **Frontend:** React 19, Vite 6, Fluent UI v9, Zustand, Electron 41, TypeScript 5.7
- **AI Models:** claude-sonnet-4.6 (slides/demos/implementation), claude-opus-4.6 (brainstorming/architecture/default), GPT-4.1 (routing classifier)

**Key modules and data flow:**

1. **Entry points:**
   - `app.py` — CLI entry point. Creates CopilotClient, session, interactive REPL loop with slash commands. Handles the full turn lifecycle: prompt → route → send_and_wait → collect events → display.
   - `server.py` — FastAPI server for the desktop app. Exposes REST endpoints (/health, /agents, /sessions, /outputs, /usage, /file) and a WebSocket endpoint (/ws/{session_id}) for real-time streaming.
   - `server_adapter.py` — WebSocket event bridge. Translates SDK session events into JSON messages for the frontend. Manages per-session state (WS connections, cancel flags, input queues, seen event dedup, phase detection).

2. **Agent system** (`agents/` package):
   - `models.py` — `AgentConfig` dataclass (name, display_name, description, prompt, tools, infer)
   - `loader.py` — `FileSystemAgentSource` reads `*.agent.md` files with YAML frontmatter from `agent_defs/`, parses them into `AgentConfig` objects
   - `registry.py` — `AgentCatalog` holds the immutable catalog of all agents, provides lookups for routable agents, skill directories. Default model: claude-opus-4.6, default timeout: 4 hours (14400s).
   - `__init__.py` — Shim that exports backward-compatible constants (AGENTS, ROUTABLE_AGENTS, ALL_AGENT_CONFIGS, ALL_SKILL_DIRS, DEFAULT_MODEL, DEFAULT_TIMEOUT)

3. **Routing** (`router.py`):
   - Two-tier: explicit `@agent-name` prefix, or LLM-based intent classification via a dedicated GPT-4.1 classifier session
   - Fallback: no agent selected → default Copilot agent handles it

4. **Tools** (`tools.py`):
   - Custom tools: `bing_search`, `run_pptx_qa_checks`, `run_demo_qa_checks`, `run_hackathon_qa_checks`
   - Built-in SDK tools: bash, str_replace_editor, web_fetch, grep, glob, ask_user, task (subagent dispatch), report_intent

5. **Observability** (`store.py`, `collector.py`, `pricing.py`, `queries.py`):
   - SQLite database at `~/.csa-copilot/csa-copilot.db` with 3 tables: sessions, turns, invocations
   - `EventCollector` maps high-level events to store writes (frontend-agnostic)
   - `pricing.py` has per-model token pricing for cost estimation (OpenAI + Anthropic models)
   - `queries.py` provides pure query functions for usage/session data (no formatting)

6. **UI** (`ui.py`):
   - Rich console output + prompt_toolkit for input (history, tab completion, auto-suggest)
   - ASCII art banner, agent routing display, streaming delta rendering, debug mode
   - `AgentRunTracker` for per-turn stats

7. **Commands** (`commands/sessions.py`, `commands/usage.py`):
   - Slash command dispatchers for /sessions and /usage, rendering Rich tables

**Data flow (CLI):**
```
User prompt → router.py (classify intent) → session.rpc.agent.select → session.send_and_wait
  → SDK events stream through ui.handle_event + collector → SQLite
  → Output files land in outputs/{workflow}/
```

**Data flow (Desktop):**
```
BriefForm → POST /sessions → POST /sessions/{id}/turn → WebSocket /ws/{id}
  → server_adapter.py translates events → JSON over WS → jobStore (Zustand)
  → React renders AgentWorkspace page
```

### Workflow Capabilities

**1. Presentations (4 agents: 1 conductor + 3 subagents)**
- `slide-conductor` (routable) orchestrates: research-subagent, slide-builder-subagent, pptx-qa-subagent
- Phases: Pre-Research → Clarify → Deep Research → Plan (user approval) → Build PPTX → QA → Complete
- Parallel dispatch: conductor batches multiple task calls in one response for concurrent subagent execution
- Output: `.pptx` + `generate_*.py` script in `outputs/slides/`, fragments in `.fragments/`
- QA: `run_pptx_qa_checks` validates overflow, placeholder text, speaker notes, font sizes, slide count

**2. Demos (5 agents: 1 conductor + 4 subagents)**
- `demo-conductor` (routable) orchestrates: demo-research-subagent, demo-builder-subagent, demo-reviewer-subagent, demo-editor-subagent
- Phases: Pre-Research → Clarify → Deep Research → Plan → Build → Validate → Review → Complete
- Output: main guide `.md` + companion scripts in `outputs/demos/`
- QA: `run_demo_qa_checks` validates placeholders, emoji, em-dashes, script syntax, cross-references

**3. AI Projects (13 agents: 3 conductors + 10 subagents)**
- `ai-brainstorming` (routable) — standalone: discovery questions, research, 10+ ranked ideas, phased roadmap
- `ai-solution-architect` (routable) orchestrates: architecture-builder-subagent, architecture-reviewer-subagent
  - Produces 7 docs: executive brief, solution design, drawio diagram, data assessment, cost estimation, delivery plan, ASCII diagram
- `ai-implementor` (routable) orchestrates: code-builder-subagent, code-reviewer-subagent, infra-reviewer-subagent, pipeline-reviewer-subagent, docs-reviewer-subagent
  - Produces 8 work packages: infra (Bicep), app code, CI/CD, deploy script, unit tests, smoke tests, validate script, README
  - 4-reviewer gate: all must APPROVE before delivery
  - 80% test coverage enforced via pytest --cov
- `ai-demo-conductor` (routable) — orchestrates demo creation for existing AI projects

**4. Hackathons (5 agents: 1 conductor + 4 subagents)**
- `hackathon-conductor` (routable) orchestrates: hackathon-research-subagent, hackathon-challenge-builder-subagent, hackathon-coach-builder-subagent, hackathon-reviewer-subagent
- Output: complete folder in `outputs/hackathons/{event-slug}/` with challenges, coach materials, devcontainer, reference architecture
- Challenge scaling: 2h = 3-4 challenges, 4h = 5-6, 8h = 8-10 (setup → easy → medium → hard → expert)
- QA: `run_hackathon_qa_checks` validates numbering, required sections, devcontainer, coach materials, cross-references

**Total: 27 agent definitions across 4 workflow categories.**

### Agent System

**Definition format:** Markdown files with YAML frontmatter in `agent_defs/{category}/*.agent.md`. The frontmatter specifies: name, display_name, description, infer (routable?), tools. The body is the system prompt.

**Loading:** `FileSystemAgentSource` recursively scans `agent_defs/` for `*.agent.md` files → parses YAML + prompt → creates `AgentConfig` objects → `AgentCatalog` indexes them.

**Routing:**
- `infer: true` = routable from the main loop (conductors + brainstorming)
- `infer: false` = subagent, only invocable via the `task` tool by conductors
- Explicit: `@agent-name` prefix in prompt
- Implicit: GPT-4.1 classifier picks from routable agent descriptions

**Key patterns:**
- Conductors NEVER do work themselves — they only orchestrate subagents via the `task` tool
- Subagents run in FRESH context (no conversation history shared)
- Parallel dispatch is MANDATORY: multiple `task` calls in one response run concurrently (max 5 per batch)
- Microsoft Azure mandate: every solution must use Azure services exclusively
- Content humanization: AI-tell detection with humanity scoring and automatic rewrites

**Skills:** 28 skill directories under `skills/`. Each has a `SKILL.md`. Skills are loaded unconditionally (all skill dirs are passed to every session). Key skills: pptx-generator, demo-generator, hackathon-generator, architecture-design, code-project, content-humanizer. 22 Azure service skills from microsoft/azure-skills.

### Frontend State

**Tech stack:** React 19 + Vite 6 + TypeScript 5.7 + Fluent UI v9 + Zustand 5 + Electron 41
- React Router v7 for navigation
- react-markdown + rehype-highlight + remark-gfm for markdown rendering
- Lazy-loaded pages with Suspense

**Pages (6):**
1. `Launchpad` — form-based briefs, template gallery, agent selection grid
2. `AgentWorkspace` — live conversation view with streaming events, activity feed, user input handling
3. `MissionControl` — monitor multiple concurrent agent runs, session management, resume capability
4. `OutputLibrary` — browse generated artifacts with inline previews, search/filter, grid/list view
5. `Sessions` — (mentioned in routes but session management is on MissionControl)
6. `Settings` — theme toggle, sidebar collapse

**State management (Zustand stores):**
- `jobStore.ts` — core job state: job lifecycle, events, progress, WebSocket management, cross-tab sync via BroadcastChannel, localStorage persistence
- `outputStore.ts` — output file listings, filtering, grouped outputs
- `settingsStore.ts` — theme and sidebar state
- `tutorialStore.ts` — guided tutorial state

**Viewers:**
- `SlideViewer` — PPTX carousel preview
- `MarkdownViewer` — rendered markdown
- `ProjectExplorer` — code tree browser
- `DrawioViewer` — draw.io diagram renderer

**Components:**
- `Shell` + `Sidebar` — app layout
- `BriefForm` — multi-field form for submitting briefs to agents
- `AgentIcon` — Fluent UI icon renderer for agents (NOT emoji — that's a landmine)
- `CompletionToast`, `ContentLevelBadge`, `GuidedTutorial`

**Hooks:**
- `useWebSocket` — WebSocket connection to /ws/{sessionId}, auto-reconnect, heartbeat, event parsing, session status polling
- `useActiveJobWatcher` — maintains WS connections for all active jobs (cross-page notifications)
- `useKeyboardShortcuts` — keyboard navigation

**API client** (`client.ts`):
- REST client wrapping fetch, proxy-aware (Vite dev proxy or direct Electron calls)
- Full coverage of backend endpoints: health, agents, sessions, turns, invocations, outputs, usage, files

### Key Technical Decisions

1. **Team consolidation (2026-04-04):** 4 dev roles → 2. McManus = Backend & CLI Dev (all Python). Redfoot = Full-Stack Frontend Dev (all TypeScript/Electron). Verbal and Kobayashi retired to alumni.

2. **GitHub Copilot SDK as the AI runtime:** The entire system delegates to the Copilot CLI in server mode via JSON-RPC. No direct model API calls. This means model routing, tool execution, and agent lifecycle are all managed by the SDK.

3. **Agent definitions as Markdown files:** Not code. This enables non-developers to modify agent behavior and makes adding new workflows a zero-code operation.

4. **Parallel subagent dispatch:** Conductors MUST batch independent task calls in one response. This is a key performance optimization — serial dispatch would make generation significantly slower.

5. **Two-interface strategy:** CLI is the stable path, desktop is experimental. This is explicitly documented and warned about.

6. **`uv` over `pip`:** All Python dependency operations use `uv`. This is a landmine — using pip will cause problems.

7. **80% test coverage threshold:** Enforced in pyproject.toml via `fail_under = 80`.

### Product Gaps & Opportunities

**Gaps identified from code/docs review:**

1. **No frontend tests.** The frontend has zero test files. For an experimental UI, this is acceptable short-term, but as it stabilizes, component tests (Vitest + Testing Library) would catch regressions.

2. **Settings page is minimal.** `settingsStore.ts` only has theme and sidebar state. The README mentions model selection in Settings, but the store doesn't persist model preferences. The `/model` CLI command works, but the desktop equivalent seems thin.

3. **No automated E2E tests.** The test suite covers unit tests for backend modules (17 test files), but there are no integration tests that exercise the full flow (prompt → agent → output). Given the 1-hour generation times this is understandable, but lightweight smoke tests (mock SDK, verify routing + QA pipeline) would add confidence.

4. **AgentCatalog doesn't use per-agent model/timeout.** `registry.py` has `get_model_for()` and `get_timeout_for()` methods, but they both ignore the agent_name argument (`noqa: ARG002`) and return the defaults. The YAML frontmatter supports `model` and `timeout` fields (visible in loader.py docs), but they're never parsed into `AgentConfig`. This means all agents run with claude-opus-4.6 and 4-hour timeout regardless of what the agent definition specifies.

5. **Content humanization skill exists but integration is unclear.** The `content-humanizer` skill has a `SKILL.md` and `humanizer_scorer.py`, but it's not referenced in any agent definition's tools list. The README mentions it as a quality layer, but the actual invocation path isn't visible in the code. This may be invoked implicitly via skills directories, but it's worth verifying.

6. **No progress persistence for long-running jobs.** If the CLI crashes mid-generation (1+ hour runs), all progress is lost. The session is marked as ended in SQLite, but the intermediate fragments and partial outputs aren't tracked in a way that enables recovery. The `/resume` command restores the SDK session, but the agent's internal state (which phase it was in, what subagents completed) is in the SDK's context window, not in persisted state.

7. **Desktop UI PPTX preview depends on system dependencies.** LibreOffice and poppler are required for PPTX thumbnail generation. The desktop installation docs mention this, but there's no graceful degradation if they're missing — the viewer might just fail silently.

8. **No rate limiting or concurrent session caps in the server.** The FastAPI server creates sessions on demand with no limit. In a multi-user deployment scenario (not the current use case, but worth noting), this could exhaust resources.

9. **SSL verification disabled in tools.py.** The `_SSL_CTX` used for Bing scraping has `check_hostname = False` and `verify_mode = ssl.CERT_NONE`. This is a security concern for the Bing HTML scraping fallback path. It should use proper certificate verification.

10. **Plugin distribution is ready but not published.** The `.github/plugin/` directory has a complete plugin manifest, MCP server config, and startup script. The README documents `copilot plugin install`, but it points to the private repo `olivomarco/vbd-copilot`. Wider distribution would require the repo to be public or a different distribution mechanism.

**Quick wins:**
- Parse and use per-agent `model` and `timeout` from YAML frontmatter (item 4) — straightforward code change, enables fine-tuning cost/speed per workflow
- Add model preference persistence to the desktop settings store
- Add frontend error boundary around PPTX viewer for graceful degradation
- Fix SSL context in tools.py to use proper certificate verification

### Current State Assessment

**What's working well:**
- The CLI is mature and battle-tested. The full turn lifecycle (routing, streaming, session management, resume, usage tracking) is solid.
- The agent system architecture is clean and extensible. Adding a new workflow is a zero-code operation: drop a `.agent.md` file and a skill directory.
- Quality gates are comprehensive: automated QA checks, human approval stops, 4-reviewer gate, 80% test coverage.
- The observability layer (SQLite + EventCollector + queries) provides good visibility into cost and usage.
- Documentation is excellent — README, INSTALLATION, USAGE, QUALITY, RESPONSIBLE-AI are all thorough and well-written.
- 17 test files covering core modules. The test infrastructure is in place.
- The desktop UI is ambitious and functional: real-time streaming, multi-job monitoring, output previews, session resume, cross-tab sync.

**What needs attention:**
- Desktop UI stability — explicitly marked experimental, and for good reason. The WebSocket reconnection logic is complex (server_adapter.py is dense with edge cases).
- Per-agent model/timeout configuration is broken (defaults always used).
- Frontend test coverage is zero.
- SSL verification is disabled in the Bing scraping path.
- Content humanizer integration path is unclear.

**Overall product maturity:** The CLI is production-quality for its intended single-user use case. The agent system and workflow architecture are well-designed and extensible. The desktop UI is a strong 0.x — functional but needs hardening. The 27-agent, 28-skill setup represents significant domain investment. The product solves a real pain point for CSAs and the quality gates ensure output reliability.
