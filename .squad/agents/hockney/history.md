# Project Context

- **Owner:** Marco Olivo
- **Project:** CSA-Copilot — AI-powered engagement platform for Cloud Solution Architects. 80% test coverage gate enforced via pytest --cov.
- **Stack:** Python 3.11+, pytest with pytest-asyncio (asyncio_mode = auto), coverage config in pyproject.toml
- **Test files:** test_store.py, test_router.py, test_collector.py, test_models.py, test_queries.py, test_hackathon_qa.py, test_pricing.py, test_tools.py, test_loader.py, test_commands.py, test_app.py, test_registry.py
- **QA scripts:** skills/pptx-generator/pptx_qa_checks.py, skills/demo-generator/demo_qa_checks.py, skills/architecture-design/architecture_qa_checks.py, skills/code-project/infra_qa_checks.py, skills/code-project/pipeline_qa_checks.py, skills/code-project/docs_qa_checks.py, skills/hackathon-generator/hackathon_qa_checks.py
- **Coverage config:** source=["."], omit app.py, ui.py, tests/, skills/, agent_defs/, scripts/, outputs/, plans/
- **Created:** 2026-04-02

## Learnings

<!-- Append new learnings below. Each entry is something lasting about the project. -->

## Deep Test Suite Study — 2026-04-04

### Test Inventory (15 files, 200+ tests)

**Core Infrastructure (97 tests):**
- test_store.py — 60 tests: SQLite event store (session/turn/invocation lifecycle, nickname validation, prefix resolution)
- test_collector.py — 17 tests: event collector state machine (on_session/turn/usage/tool/subagent)
- test_queries.py — 18 tests: data aggregation (period filters, usage summaries, preview truncation)

**Agent & Routing (41 tests):**
- test_router.py — 15 tests: @mention priority, LLM intent classification
- test_loader.py — 10 tests: agent definition loading (YAML frontmatter, recursive discovery)
- test_registry.py — 14 tests: agent catalog (filtering, model/timeout lookups)
- test_models.py — 2 tests: AgentConfig dataclass

**Data & Tools (46 tests):**
- test_pricing.py — 10 tests: token→USD conversion (pytest.approx for floats)
- test_tools.py — 25 tests: Bing search HTML parsing, API integration, QA param validation
- test_app.py — 11 tests: output file discovery (timestamp spoofing with os.utime)

**CLI & Commands (16 tests):**
- test_commands.py — 14 tests: session/usage commands (Rich console output capture)
- test_server_ws.py — 2 tests: WebSocket user_response flow

**QA & Integration (12 tests):**
- test_hackathon_qa.py — 12 tests: hackathon directory structure validation

### Coverage Configuration (pyproject.toml)

```ini
[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]

[tool.coverage.run]
source = ["."]
omit = ["app.py", "ui.py", "tests/*", "skills/*", "agent_defs/*", "scripts/*", "outputs/*", "plans/*"]

[tool.coverage.report]
fail_under = 80
show_missing = true
exclude_lines = ["pragma: no cover", "if __name__", "if TYPE_CHECKING"]
```

### Test Patterns

**Fixtures:**
- tmp_path (pytest built-in) for temp dirs
- EventStore(db, retention_days=0) with yield + close()
- Collector/Router fixtures depend on store, mock global state
- Console: StringIO + Rich Console(force_terminal=True, width=120)

**Mocking:**
- AsyncMock for async callbacks with @patch
- monkeypatch urllib.request.urlopen for network isolation
- MagicMock with assert_called_once() / assert_not_called()
- tmp_path + monkeypatch for filesystem constants

**Async:** @pytest.mark.asyncio decorator, asyncio_mode="auto" handles setup

**Naming:** test_<action>_<scenario>_<expected>

### QA Check Scripts (7 scripts)

All return JSON: {"status", "summary", "issues"}. Exit codes: 0=CLEAN, 1=ISSUES, 2=ERROR.
Severity levels: CRITICAL > MAJOR > MINOR. Unified placeholder regex (IGNORECASE) across all scripts.

### Gaps & Testing Opportunities

**NOT tested:** UI output (ui.py), skill implementations, agent execution (task() mocked), concurrent sessions, DB migrations, cache tokens
**Recommendations:** Property-based tests (Hypothesis) for pricing, parametrized router tests, integration tests with real EventStore, unified regex pattern tests, stress tests for invocation counts

### Key Conventions

1. Fixture names follow pytest idioms (store, collector, catalog, console)
2. Helper functions use `_` prefix (_populate_store, _create_valid_hackathon)
3. Severity across QA: CRITICAL (must fix) > MAJOR > MINOR
4. Test coverage ≥ 80% — this is the floor, not the goal
5. Every bug should become a missing test case
