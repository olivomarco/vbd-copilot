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

## Path Traversal Security Audit — 2026-04-09

Added 48 security-focused tests to `test_server_extended.py` covering path traversal attack vectors across all file-serving endpoints. 8 new test classes:

- **TestSafeOutputsPathSecurity** (16 tests): Direct attacks against `_safe_outputs_path` — absolute path escape, `../../` traversal, encoded dot-dot, Windows backslashes, triple/quad dots, Unicode fullwidth characters, symlink traversal, null bytes (mid-path + end), deeply nested `../`, mixed traversal components.
- **TestFileReadPathTraversal** (4 tests): `/file` endpoint — traversal, absolute escape, null byte, empty path.
- **TestFileDownloadPathTraversal** (5 tests): `/file/download` endpoint — traversal, absolute escape, null byte, decoded `%2E%2E%2F`, double URL encoding.
- **TestOutputMetadataPathTraversal** (4 tests): `/outputs/metadata` — traversal, absolute, null byte, empty.
- **TestDeleteOutputPathTraversal** (3 tests): `/outputs` DELETE — absolute, null byte, deeply nested.
- **TestGroupedOutputPathTraversal** (6 tests): `/outputs/grouped` DELETE with crafted slugs — `hackathons/../../etc`, absolute slug, ai-project traversal, null in slug, slides traversal, demos traversal.
- **TestZipPathTraversal** (6 tests): `/outputs/zip` — traversal, absolute, null byte, mixed safe+unsafe paths, deep nesting, filename injection in Content-Disposition header.

**Key findings:**
- **No vulnerabilities discovered.** The `_safe_outputs_path()` function is well-designed: it resolves paths (normalizing `../`), then checks `is_relative_to(outputs_resolved)`. This catches all tested vectors.
- The `/outputs/grouped` DELETE endpoint has separate `resolve().relative_to()` checks for hackathon/ai-project categories — also solid.
- Symlink traversal is correctly blocked because `resolve()` follows symlinks before the `is_relative_to` check.
- Zip filename injection is sanitised via regex `re.sub(r"[^\w\-.]", "_", ...)`.
- On Linux, backslash-based paths (`..\\..\\`) are treated as literal filenames, not directory separators — no traversal risk.
- Unicode fullwidth dots/slashes (U+FF0E, U+FF0F) are not normalised to ASCII by Python's `Path.resolve()` — they remain harmless literal characters.

All 142 server tests pass (1.56s). No regressions.

Added 11 tests across three files covering McManus's Phase 2 backend changes:

- **test_server_adapter.py** (4 tests): `TestResponseBuffer` — buffer accumulation, reset clearing, `get_accumulated_response` for known/unknown sessions.
- **test_store.py** (3 tests): `TestSubagentName` — `record_invocation` with/without `subagent_name`, plus migration idempotency for the new column.
- **test_collector.py** (4 tests): `TestSubagentNamePassthrough` — `on_tool_start` passes `subagent_name` through to store correctly. `TestAssistantResponsePersistence` — `on_turn_end` persists `assistant_response` to turns table.

All 104 tests pass (0.45s). No regressions.

## Phase 3 Tests — 2026-04-07

Added 8 tests to `test_server_adapter.py` covering McManus's Phase 3 backend changes:

- **TestEmitStateChanged** (3 tests): `emit_state_changed` with active WS connection (async — needs event loop for `_send`), no-op for unknown sessions, no-op when session has zero websockets.
- **TestHeartbeat** (2 tests): `start_heartbeat`/`stop_heartbeat` lifecycle (start creates task, stop cancels it, task ref nulled), idempotency (double-start returns same task).
- **TestPhase3EnvelopeShapes** (2 tests): heartbeat envelope structure (`v`, `type`, `data.ts`, `id`, `seq`), `session_state_changed` envelope includes `status` and `reason`.
- **TestSnapshotDuringResponse** (1 test): `build_snapshot` succeeds when `response_buffer` has accumulated content, confirms `status == "active"`.

Also updated `_clear_connections` autouse fixture to call `stop_heartbeat()` in teardown — prevents heartbeat task leaks across tests.

All 364 tests pass (1.39s). No regressions.

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

## Phase 1 — SessionConnection + Envelope Protocol Tests — 2026-04-07

Added `tests/test_server_adapter.py` with 34 tests covering McManus's server_adapter.py refactor:
- **SessionConnection lifecycle (6):** init defaults, add/remove_ws, reset_turn state clearing, reset_turn preserves pending_input, cleanup clears everything, next_seq monotonic
- **Connection registry (7):** get_connection unknown, get_or_create idempotent, add_ws creates conn, add_ws second returns False, remove_ws cleans up empty, remove_ws keeps remaining, remove_ws unknown session
- **Cancel flag compat (3):** per-session set/get, legacy global set/get, unknown session returns False
- **Envelope protocol (6):** structure validation, correlation ID, seq increments, None conn fallback, unique IDs, timestamp recency
- **Snapshot (5):** active session, waiting session, idle session, unknown returns None, includes last_done
- **User response flow (4):** push/pop roundtrip, timeout raises TimeoutError, push clears pending_input, FIFO ordering
- **ws_reset (3):** delegates to SessionConnection, unknown session is noop, legacy no-arg path

Key pattern: autouse `_clear_connections` fixture clears `_connections` dict before/after every test to isolate module-level state. Imported `_connections` directly for fixture access — private but necessary for test isolation.

Total suite: 346 tests, all green.
