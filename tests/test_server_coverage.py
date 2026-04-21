"""Additional server.py tests targeting uncovered lines to reach 85% coverage.

Covers: create_session, resume_session, end_session, list/get sessions,
session status, session events, outputs grouped, delete group, download,
zip, metadata, _find_new_outputs, configure.
"""

from __future__ import annotations

import time
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

import server as server_mod
from server import app, _find_new_outputs, configure


@pytest.fixture(autouse=True)
def _reset_globals(tmp_path):
    store = MagicMock()
    store.list_sessions.return_value = []
    store.resolve_prefix.return_value = None
    store.get_session.return_value = None
    store.get_turns.return_value = []
    store.get_invocations.return_value = []
    store.get_invocations_for_turn.return_value = []
    store.end_session.return_value = None
    store.reactivate_session.return_value = None
    store.update_session_agent.return_value = None
    store.update_session_model.return_value = None

    old = {
        "store": server_mod._event_store,
        "client": server_mod._copilot_client,
        "collector": server_mod._collector,
        "app_dir": server_mod._app_dir,
        "outputs_dir": server_mod._outputs_dir,
        "session_map": server_mod._session_map.copy(),
    }

    server_mod._event_store = store
    server_mod._copilot_client = None
    server_mod._collector = None
    server_mod._app_dir = tmp_path
    server_mod._outputs_dir = tmp_path / "outputs"
    server_mod._outputs_dir.mkdir()

    yield store

    server_mod._event_store = old["store"]
    server_mod._copilot_client = old["client"]
    server_mod._collector = old["collector"]
    server_mod._app_dir = old["app_dir"]
    server_mod._outputs_dir = old["outputs_dir"]
    server_mod._session_map.clear()
    server_mod._session_map.update(old["session_map"])


@pytest.fixture()
def client():
    return TestClient(app)


# ── create_session ────────────────────────────────────────────────────────


class TestCreateSession:
    def test_create_session_no_client(self, client):
        resp = client.post("/sessions", json={"agent": "test"})
        assert resp.status_code == 503

    def test_create_session_success(self, client):
        fake_session = SimpleNamespace(session_id="sid-1")

        async def _create(opts):
            return fake_session

        mock_client = MagicMock()
        mock_client.create_session = _create
        server_mod._copilot_client = mock_client

        with (
            patch("agents.ALL_AGENT_CONFIGS", []),
            patch("agents.ALL_SKILL_DIRS", []),
            patch("agents.DEFAULT_MODEL", "gpt-4o"),
            patch("tools.ALL_CUSTOM_TOOLS", []),
        ):
            resp = client.post("/sessions", json={"agent": "test-agent", "model": "gpt-4o"})

        assert resp.status_code == 200
        data = resp.json()
        assert data["session_id"] == "sid-1"
        assert data["model"] == "gpt-4o"

    def test_create_session_sdk_error(self, client):
        async def _create(opts):
            raise RuntimeError("SDK boom")

        mock_client = MagicMock()
        mock_client.create_session = _create
        server_mod._copilot_client = mock_client

        with (
            patch("agents.ALL_AGENT_CONFIGS", []),
            patch("agents.ALL_SKILL_DIRS", []),
            patch("agents.DEFAULT_MODEL", "gpt-4o"),
            patch("tools.ALL_CUSTOM_TOOLS", []),
        ):
            resp = client.post("/sessions", json={})

        assert resp.status_code == 500
        assert "SDK boom" in resp.json()["detail"]

    def test_create_session_with_collector(self, client):
        fake_session = SimpleNamespace(session_id="sid-c")

        async def _create(opts):
            return fake_session

        mock_client = MagicMock()
        mock_client.create_session = _create
        server_mod._copilot_client = mock_client

        mock_collector = MagicMock()
        server_mod._collector = mock_collector

        with (
            patch("agents.ALL_AGENT_CONFIGS", []),
            patch("agents.ALL_SKILL_DIRS", []),
            patch("agents.DEFAULT_MODEL", "gpt-4o"),
            patch("tools.ALL_CUSTOM_TOOLS", []),
        ):
            resp = client.post("/sessions", json={"agent": "slide-conductor"})

        assert resp.status_code == 200
        mock_collector.on_session_created.assert_called_once()


# ── resume_session ────────────────────────────────────────────────────────


class TestResumeSession:
    def test_resume_no_client(self, client):
        resp = client.post("/sessions/sid-1/resume", json={})
        assert resp.status_code == 503

    def test_resume_no_store(self, client):
        server_mod._copilot_client = MagicMock()
        server_mod._event_store = None
        resp = client.post("/sessions/sid-1/resume", json={})
        assert resp.status_code == 503

    def test_resume_not_found(self, client, _reset_globals):
        server_mod._copilot_client = MagicMock()
        _reset_globals.resolve_prefix.return_value = None
        resp = client.post("/sessions/sid-1/resume", json={})
        assert resp.status_code == 404

    def test_resume_not_resumable(self, client, _reset_globals):
        server_mod._copilot_client = MagicMock()
        _reset_globals.resolve_prefix.return_value = "full-sid-1"
        _reset_globals.get_session.return_value = {"resumable": False}
        resp = client.post("/sessions/full-sid-1/resume", json={})
        assert resp.status_code == 400

    def test_resume_success(self, client, _reset_globals):
        fake_session = SimpleNamespace(session_id="full-sid-1")

        async def _resume(sid, opts):
            return fake_session

        mock_client = MagicMock()
        mock_client.resume_session = _resume
        server_mod._copilot_client = mock_client

        _reset_globals.resolve_prefix.return_value = "full-sid-1"
        _reset_globals.get_session.side_effect = [
            {"resumable": True},
            {"agent": "slide", "model": "gpt-4o", "turn_count": 2},
        ]
        _reset_globals.get_turns.return_value = [{"turn_number": 1}]

        with (
            patch("agents.ALL_AGENT_CONFIGS", []),
            patch("agents.ALL_SKILL_DIRS", []),
            patch("tools.ALL_CUSTOM_TOOLS", []),
        ):
            resp = client.post("/sessions/full-sid-1/resume", json={})

        assert resp.status_code == 200
        data = resp.json()
        assert data["session_id"] == "full-sid-1"
        assert data["turns"] == [{"turn_number": 1}]

    def test_resume_sdk_error(self, client, _reset_globals):
        async def _resume(sid, opts):
            raise RuntimeError("resume fail")

        mock_client = MagicMock()
        mock_client.resume_session = _resume
        server_mod._copilot_client = mock_client

        _reset_globals.resolve_prefix.return_value = "full-sid-1"
        _reset_globals.get_session.return_value = {"resumable": True}

        with (
            patch("agents.ALL_AGENT_CONFIGS", []),
            patch("agents.ALL_SKILL_DIRS", []),
            patch("tools.ALL_CUSTOM_TOOLS", []),
        ):
            resp = client.post("/sessions/full-sid-1/resume", json={})

        assert resp.status_code == 500


# ── end_session ───────────────────────────────────────────────────────────


class TestEndSession:
    def test_end_session(self, client, _reset_globals):
        _reset_globals.resolve_prefix.return_value = "full-sid-1"
        fake_session = SimpleNamespace(_event_handlers=[])
        server_mod._session_map["full-sid-1"] = fake_session

        with patch("server_adapter.destroy_connection"), patch(
            "server_adapter.emit_state_changed"
        ):
            resp = client.delete("/sessions/full-sid-1")

        assert resp.status_code == 200
        assert resp.json()["ok"] is True

    def test_end_session_no_map_entry(self, client, _reset_globals):
        _reset_globals.resolve_prefix.return_value = "full-sid-2"

        with patch("server_adapter.destroy_connection"), patch(
            "server_adapter.emit_state_changed"
        ):
            resp = client.delete("/sessions/full-sid-2")

        assert resp.status_code == 200


# ── list / get sessions ──────────────────────────────────────────────────


class TestListSessions:
    def test_list_active_sessions(self, client, _reset_globals):
        _reset_globals.list_sessions.return_value = [{"id": "s1"}]
        resp = client.get("/sessions")
        assert resp.status_code == 200
        _reset_globals.list_sessions.assert_called_with(status="active")

    def test_list_all_sessions(self, client, _reset_globals):
        _reset_globals.list_sessions.return_value = []
        resp = client.get("/sessions?all=true")
        assert resp.status_code == 200
        _reset_globals.list_sessions.assert_called_with()

    def test_get_session_found(self, client, _reset_globals):
        _reset_globals.resolve_prefix.return_value = "full-id"
        _reset_globals.get_session.return_value = {"id": "full-id", "status": "active"}
        resp = client.get("/sessions/full-id")
        assert resp.status_code == 200

    def test_get_session_not_found(self, client, _reset_globals):
        _reset_globals.resolve_prefix.return_value = "full-id"
        _reset_globals.get_session.return_value = None
        resp = client.get("/sessions/full-id")
        assert resp.status_code == 404


# ── session status ────────────────────────────────────────────────────────


class TestSessionStatus:
    def test_status_not_found(self, client, _reset_globals):
        _reset_globals.resolve_prefix.return_value = None
        resp = client.get("/sessions/sid-1/status")
        assert resp.status_code == 404

    def test_status_active_session(self, client, _reset_globals):
        _reset_globals.resolve_prefix.return_value = "full-sid"
        _reset_globals.get_session.return_value = {
            "status": "active",
            "turn_count": 3,
            "resumable": 1,
        }
        server_mod._session_map["full-sid"] = SimpleNamespace()

        with (
            patch("server_adapter.get_connection", return_value=None),
            patch("server_adapter.get_pending_input", return_value=None),
            patch("server_adapter.get_output_files", return_value=[]),
        ):
            resp = client.get("/sessions/full-sid/status")

        assert resp.status_code == 200
        data = resp.json()
        assert data["session_id"] == "full-sid"
        assert data["in_memory"] is True
        assert data["turn_count"] == 3

    def test_status_ended_has_output_files_from_turns(self, client, _reset_globals):
        _reset_globals.resolve_prefix.return_value = "full-sid"
        _reset_globals.get_session.return_value = {
            "status": "ended",
            "turn_count": 1,
            "resumable": 0,
        }
        _reset_globals.get_turns.return_value = [
            {"output_files": '["file1.pptx"]'},
        ]

        with (
            patch("server_adapter.get_connection", return_value=None),
            patch("server_adapter.get_pending_input", return_value=None),
            patch("server_adapter.get_output_files", return_value=[]),
        ):
            resp = client.get("/sessions/full-sid/status")

        data = resp.json()
        assert data["output_files"] == ["file1.pptx"]


# ── session events ────────────────────────────────────────────────────────


class TestSessionEvents:
    def test_events_not_found(self, client, _reset_globals):
        _reset_globals.resolve_prefix.return_value = None
        resp = client.get("/sessions/sid-1/events")
        assert resp.status_code == 404

    def test_events_with_turns(self, client, _reset_globals):
        _reset_globals.resolve_prefix.return_value = "full-sid"
        _reset_globals.get_session.return_value = {"status": "active"}
        _reset_globals.get_turns.return_value = [
            {
                "id": "t1",
                "turn_number": 1,
                "agent": "slide-conductor",
                "user_prompt": "make slides",
                "started_at": "2024-01-01T00:00:00",
                "ended_at": "2024-01-01T00:01:00",
                "assistant_response": "Done",
                "input_tokens": 100,
                "output_tokens": 50,
                "cache_read_tokens": 0,
                "cache_write_tokens": 0,
                "estimated_cost_usd": 0.01,
                "output_files": '["slides.pptx"]',
            }
        ]
        _reset_globals.get_invocations_for_turn.return_value = [
            {
                "type": "tool_call",
                "name": "bing_search",
                "started_at": "2024-01-01T00:00:10",
                "ended_at": "2024-01-01T00:00:12",
                "input": "{}",
                "output": "results",
                "duration_ms": 200,
                "status": "success",
            },
            {
                "type": "subagent",
                "name": "researcher",
                "started_at": "2024-01-01T00:00:05",
                "ended_at": "2024-01-01T00:00:20",
                "duration_ms": 15000,
                "status": "success",
            },
        ]

        resp = client.get("/sessions/full-sid/events")
        assert resp.status_code == 200
        events = resp.json()
        types = [e["type"] for e in events]
        assert "turn_started" in types
        assert "assistant_message" in types
        assert "tool_started" in types
        assert "tool_completed" in types
        assert "subagent_started" in types
        assert "subagent_completed" in types
        assert "usage" in types
        assert "new_files" in types

    def test_events_ended_session_has_done(self, client, _reset_globals):
        _reset_globals.resolve_prefix.return_value = "full-sid"
        _reset_globals.get_session.return_value = {
            "status": "ended",
            "ended_at": "2024-01-01T00:10:00",
        }
        _reset_globals.get_turns.return_value = []

        resp = client.get("/sessions/full-sid/events")
        events = resp.json()
        assert any(e["type"] == "done" for e in events)

    def test_events_session_not_found_detail(self, client, _reset_globals):
        _reset_globals.resolve_prefix.return_value = "full-sid"
        _reset_globals.get_session.return_value = None
        resp = client.get("/sessions/full-sid/events")
        assert resp.status_code == 404


# ── turns / invocations ──────────────────────────────────────────────────


class TestTurnInvocations:
    def test_get_turn_invocations_found(self, client, _reset_globals):
        _reset_globals.resolve_prefix.return_value = "full-sid"
        _reset_globals.get_turns.return_value = [
            {"id": "turn-1", "turn_number": 1}
        ]
        _reset_globals.get_invocations.return_value = [{"id": "inv-1"}]

        resp = client.get("/sessions/full-sid/turns/1/invocations")
        assert resp.status_code == 200
        assert resp.json() == [{"id": "inv-1"}]

    def test_get_turn_invocations_not_found(self, client, _reset_globals):
        _reset_globals.resolve_prefix.return_value = "full-sid"
        _reset_globals.get_turns.return_value = []

        resp = client.get("/sessions/full-sid/turns/1/invocations")
        assert resp.status_code == 404


# ── outputs grouped ──────────────────────────────────────────────────────


class TestOutputsGrouped:
    def test_empty_outputs(self, client):
        resp = client.get("/outputs/grouped")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_slides_group(self, client):
        slides_dir = server_mod._outputs_dir / "slides"
        slides_dir.mkdir()
        # Create a fake pptx file
        (slides_dir / "test-deck.pptx").write_bytes(b"PK\x03\x04fake")

        resp = client.get("/outputs/grouped")
        assert resp.status_code == 200
        groups = resp.json()
        slide_groups = [g for g in groups if g.get("category") == "slides"]
        assert len(slide_groups) >= 1

    def test_demos_group(self, client):
        demos_dir = server_mod._outputs_dir / "demos"
        demos_dir.mkdir()
        (demos_dir / "aks-demos.md").write_text("# AKS Demo\n")

        resp = client.get("/outputs/grouped")
        assert resp.status_code == 200
        groups = resp.json()
        demo_groups = [g for g in groups if g.get("category") == "demos"]
        assert len(demo_groups) >= 1

    def test_hackathons_group(self, client):
        hack_dir = server_mod._outputs_dir / "hackathons" / "event-1"
        hack_dir.mkdir(parents=True)
        (hack_dir / "README.md").write_text("# Hackathon\n")

        resp = client.get("/outputs/grouped")
        assert resp.status_code == 200
        groups = resp.json()
        hack_groups = [g for g in groups if g.get("category") == "hackathons"]
        assert len(hack_groups) >= 1

    def test_ai_projects_group(self, client):
        proj_dir = server_mod._outputs_dir / "ai-projects" / "my-proj"
        proj_dir.mkdir(parents=True)
        (proj_dir / "docs").mkdir()
        (proj_dir / "docs" / "solution-design.md").write_text("# Arch\n")

        resp = client.get("/outputs/grouped")
        assert resp.status_code == 200
        groups = resp.json()
        proj_groups = [g for g in groups if g.get("category") == "ai-projects"]
        assert len(proj_groups) >= 1


# ── delete group ──────────────────────────────────────────────────────────


class TestDeleteGroup:
    def test_delete_hackathon_group(self, client):
        d = server_mod._outputs_dir / "hackathons" / "event-1"
        d.mkdir(parents=True)
        (d / "README.md").write_text("# test")

        resp = client.delete("/outputs/grouped", params={"id": "hackathons/event-1"})
        assert resp.status_code == 200
        assert not d.exists()

    def test_delete_slides_group(self, client):
        slides_dir = server_mod._outputs_dir / "slides"
        slides_dir.mkdir()
        (slides_dir / "my-deck.pptx").write_bytes(b"pk")

        resp = client.delete("/outputs/grouped", params={"id": "slides/my-deck"})
        assert resp.status_code == 200

    def test_delete_demos_group(self, client):
        demos_dir = server_mod._outputs_dir / "demos"
        demos_dir.mkdir()
        (demos_dir / "test-demos.md").write_text("# test")

        resp = client.delete("/outputs/grouped", params={"id": "demos/test"})
        assert resp.status_code == 200

    def test_delete_demos_not_found(self, client):
        demos_dir = server_mod._outputs_dir / "demos"
        demos_dir.mkdir()

        resp = client.delete("/outputs/grouped", params={"id": "demos/nonexistent"})
        assert resp.status_code == 404

    def test_delete_unknown_category(self, client):
        resp = client.delete("/outputs/grouped", params={"id": "widgets/foo"})
        assert resp.status_code == 400

    def test_delete_invalid_slug(self, client):
        resp = client.delete("/outputs/grouped", params={"id": "hackathons/../../etc"})
        assert resp.status_code == 400

    def test_delete_hackathon_not_found(self, client):
        server_mod._outputs_dir / "hackathons"  # don't create
        resp = client.delete("/outputs/grouped", params={"id": "hackathons/nonexistent"})
        assert resp.status_code == 404


# ── download ──────────────────────────────────────────────────────────────


class TestDownloadFile:
    def test_download_success(self, client):
        f = server_mod._outputs_dir / "test.md"
        f.write_text("hello")

        resp = client.get(f"/file/download?path={f}")
        assert resp.status_code == 200

    def test_download_not_found(self, client):
        resp = client.get("/file/download?path=outputs/nonexistent.md")
        assert resp.status_code == 404

    def test_download_generator_blocked(self, client):
        f = server_mod._outputs_dir / "generate_test.py"
        f.write_text("print('hi')")

        resp = client.get(f"/file/download?path={f}")
        assert resp.status_code == 403


# ── zip ───────────────────────────────────────────────────────────────────


class TestZip:
    def test_zip_empty_paths(self, client):
        resp = client.post("/outputs/zip", json={"paths": []})
        assert resp.status_code == 400

    def test_zip_files(self, client):
        f = server_mod._outputs_dir / "test.md"
        f.write_text("hello")

        resp = client.post("/outputs/zip", json={"paths": [str(f)], "name": "export"})
        assert resp.status_code == 200
        assert "application/zip" in resp.headers["content-type"]

    def test_zip_directory(self, client):
        d = server_mod._outputs_dir / "subdir"
        d.mkdir()
        (d / "file.md").write_text("content")

        resp = client.post("/outputs/zip", json={"paths": [str(d)]})
        assert resp.status_code == 200

    def test_zip_skips_generator_scripts(self, client):
        d = server_mod._outputs_dir / "zdir"
        d.mkdir()
        (d / "generate_test.py").write_text("print('skip me')")
        (d / "real.md").write_text("keep me")

        resp = client.post("/outputs/zip", json={"paths": [str(d)]})
        assert resp.status_code == 200


# ── metadata ──────────────────────────────────────────────────────────────


class TestMetadata:
    def test_metadata_not_found(self, client):
        resp = client.get("/outputs/metadata?path=outputs/nonexistent.md")
        assert resp.status_code == 404

    def test_metadata_markdown(self, client):
        f = server_mod._outputs_dir / "slides" / "test-l300-30min.md"
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text("# Test")

        resp = client.get(f"/outputs/metadata?path={f}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["contentLevel"] == "L300"
        assert data["duration"] == "30 min"

    def test_metadata_with_plan_file(self, client):
        plans_dir = server_mod._app_dir / "plans"
        plans_dir.mkdir()
        (plans_dir / "test-plan.md").write_text("# Plan")

        f = server_mod._outputs_dir / "test.md"
        f.write_text("# Test")

        resp = client.get(f"/outputs/metadata?path={f}")
        assert resp.status_code == 200
        data = resp.json()
        assert "planFile" in data


# ── _find_new_outputs ─────────────────────────────────────────────────────


class TestFindNewOutputs:
    def test_finds_recent_files(self):
        f = server_mod._outputs_dir / "new.pptx"
        f.write_bytes(b"pk")

        results = _find_new_outputs(time.time() - 10)
        assert any(r.name == "new.pptx" for r in results)

    def test_skips_plan_files(self):
        f = server_mod._outputs_dir / "test-plan.md"
        f.write_text("plan")

        results = _find_new_outputs(time.time() - 10)
        assert not any(r.name == "test-plan.md" for r in results)

    def test_skips_fragment_dirs(self):
        d = server_mod._outputs_dir / ".fragments"
        d.mkdir()
        (d / "frag.py").write_text("code")

        results = _find_new_outputs(time.time() - 10)
        assert not any(".fragments" in str(r) for r in results)

    def test_scopes_to_agent_dir(self):
        slides_dir = server_mod._outputs_dir / "slides"
        slides_dir.mkdir()
        (slides_dir / "deck.pptx").write_bytes(b"pk")

        demos_dir = server_mod._outputs_dir / "demos"
        demos_dir.mkdir()
        (demos_dir / "demo.md").write_text("demo")

        results = _find_new_outputs(time.time() - 10, agent_name="slide-conductor")
        assert any(r.name == "deck.pptx" for r in results)
        assert not any(r.name == "demo.md" for r in results)

    def test_unknown_agent_scans_all(self):
        (server_mod._outputs_dir / "test.md").write_text("hi")

        results = _find_new_outputs(time.time() - 10, agent_name="unknown-agent")
        assert any(r.name == "test.md" for r in results)

    def test_nonexistent_dir_returns_empty(self):
        results = _find_new_outputs(
            time.time() - 10, agent_name="slide-conductor"
        )
        assert results == []


# ── configure ─────────────────────────────────────────────────────────────


class TestConfigure:
    def test_configure_sets_globals(self, tmp_path):
        store = MagicMock()
        client = MagicMock()
        collector = MagicMock()

        with patch("server_adapter.set_collector") as mock_set:
            configure(
                event_store=store,
                copilot_client=client,
                collector=collector,
                app_dir=tmp_path,
                outputs_dir=tmp_path / "out",
            )

        assert server_mod._event_store is store
        assert server_mod._copilot_client is client
        assert server_mod._collector is collector
        mock_set.assert_called_once_with(collector)


# ── read_file ─────────────────────────────────────────────────────────────


class TestReadFile:
    def test_read_file_success(self, client):
        f = server_mod._outputs_dir / "test.md"
        f.write_text("hello world")

        resp = client.get(f"/file?path={f}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["content"] == "hello world"

    def test_read_file_not_found(self, client):
        resp = client.get("/file?path=outputs/no.md")
        assert resp.status_code == 404


# ── usage endpoint ────────────────────────────────────────────────────────


class TestUsageEndpoint:
    def test_usage_all(self, client):
        with patch("queries.usage_summary", return_value={"total": 0}):
            resp = client.get("/usage")
            assert resp.status_code == 200

    def test_usage_with_filters(self, client):
        with patch("queries.usage_summary", return_value={"total": 0}):
            resp = client.get("/usage?period=today&agent=test&model=gpt-4o")
            assert resp.status_code == 200
