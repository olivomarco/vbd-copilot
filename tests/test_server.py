"""Tests for server.py REST endpoints (no Copilot SDK required)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

import server as server_mod
from server import app


@pytest.fixture(autouse=True)
def _reset_globals(tmp_path):
    """Inject test doubles into server module-level globals."""
    store = MagicMock()
    store.list_sessions.return_value = []
    store.resolve_prefix.return_value = None
    store.get_session.return_value = None
    store.get_turns.return_value = []
    store.end_session.return_value = None

    old_store = server_mod._event_store
    old_client = server_mod._copilot_client
    old_collector = server_mod._collector
    old_app_dir = server_mod._app_dir
    old_outputs = server_mod._outputs_dir

    server_mod._event_store = store
    server_mod._copilot_client = None
    server_mod._collector = None
    server_mod._app_dir = tmp_path
    server_mod._outputs_dir = tmp_path / "outputs"
    server_mod._outputs_dir.mkdir()

    yield store

    server_mod._event_store = old_store
    server_mod._copilot_client = old_client
    server_mod._collector = old_collector
    server_mod._app_dir = old_app_dir
    server_mod._outputs_dir = old_outputs


@pytest.fixture()
def client():
    return TestClient(app)


# ── Health ────────────────────────────────────────────────────────────────────


class TestHealth:
    def test_health_returns_ok(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "version" in data

    def test_health_version_format(self, client):
        resp = client.get("/health")
        data = resp.json()
        # Version should be a non-empty string
        assert isinstance(data["version"], str)
        assert len(data["version"]) > 0


# ── Agents ────────────────────────────────────────────────────────────────────


class TestAgents:
    def test_list_agents_returns_list(self, client):
        resp = client.get("/agents")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)

    def test_agent_entries_have_required_fields(self, client):
        resp = client.get("/agents")
        data = resp.json()
        for agent in data:
            assert "name" in agent
            assert "display_name" in agent
            assert "description" in agent
            assert "infer" in agent


# ── Sessions list ─────────────────────────────────────────────────────────────


class TestListSessions:
    def test_list_sessions_default(self, client, _reset_globals):
        store = _reset_globals
        store.list_sessions.return_value = [
            {"id": "abc123", "agent": "slides", "status": "active"},
        ]
        resp = client.get("/sessions")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["id"] == "abc123"
        store.list_sessions.assert_called_once_with(status="active")

    def test_list_sessions_all(self, client, _reset_globals):
        store = _reset_globals
        store.list_sessions.return_value = []
        resp = client.get("/sessions?all=true")
        assert resp.status_code == 200
        store.list_sessions.assert_called_once_with()

    def test_sessions_503_when_store_missing(self, client):
        server_mod._event_store = None
        resp = client.get("/sessions")
        assert resp.status_code == 503


# ── Session detail ────────────────────────────────────────────────────────────


class TestGetSession:
    def test_get_session_found(self, client, _reset_globals):
        store = _reset_globals
        store.resolve_prefix.return_value = "full-session-id"
        store.get_session.return_value = {
            "id": "full-session-id",
            "agent": "slides",
            "status": "active",
        }
        resp = client.get("/sessions/full")
        assert resp.status_code == 200
        assert resp.json()["id"] == "full-session-id"

    def test_get_session_not_found(self, client, _reset_globals):
        store = _reset_globals
        store.resolve_prefix.return_value = "nonexistent"
        store.get_session.return_value = None
        resp = client.get("/sessions/nonexistent")
        assert resp.status_code == 404


# ── Delete session ────────────────────────────────────────────────────────────


class TestDeleteSession:
    def test_delete_session(self, client, _reset_globals):
        store = _reset_globals
        store.resolve_prefix.return_value = "sess-001"
        with patch("server_adapter.unregister_event_handler"):
            resp = client.delete("/sessions/sess-001")
        assert resp.status_code == 200
        assert resp.json()["ok"] is True
        store.end_session.assert_called_once()

    def test_delete_session_without_store(self, client):
        server_mod._event_store = None
        with patch("server_adapter.unregister_event_handler"):
            resp = client.delete("/sessions/anything")
        assert resp.status_code == 200
        assert resp.json()["ok"] is True


# ── Session turns ─────────────────────────────────────────────────────────────


class TestSessionTurns:
    def test_get_turns(self, client, _reset_globals):
        store = _reset_globals
        store.resolve_prefix.return_value = "sess-001"
        store.get_turns.return_value = [
            {"id": "t1", "turn_number": 1, "agent": "slides"},
        ]
        resp = client.get("/sessions/sess-001/turns")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["turn_number"] == 1


# ── Create session (requires SDK → 503) ──────────────────────────────────────


class TestCreateSession:
    def test_create_session_503_no_client(self, client):
        resp = client.post("/sessions", json={"agent": "slides"})
        assert resp.status_code == 503
        assert "Copilot client" in resp.json()["detail"]


# ── Outputs ───────────────────────────────────────────────────────────────────


class TestOutputs:
    def test_list_outputs_empty(self, client):
        resp = client.get("/outputs")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_outputs_with_files(self, client, tmp_path):
        slides_dir = server_mod._outputs_dir / "slides"
        slides_dir.mkdir(parents=True)
        (slides_dir / "test.pptx").write_bytes(b"PK\x03\x04fake")
        resp = client.get("/outputs")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["name"] == "test.pptx"
        assert data[0]["category"] == "slides"
        assert data[0]["type"] == "pptx"

    def test_list_outputs_skips_plan_files(self, client):
        slides_dir = server_mod._outputs_dir / "slides"
        slides_dir.mkdir(parents=True)
        (slides_dir / "foo-plan.md").write_text("plan")
        resp = client.get("/outputs")
        assert resp.json() == []

    def test_list_outputs_skips_fragments_dir(self, client):
        frags = server_mod._outputs_dir / "slides" / ".fragments"
        frags.mkdir(parents=True)
        (frags / "chunk.py").write_text("code")
        resp = client.get("/outputs")
        assert resp.json() == []


# ── File read ─────────────────────────────────────────────────────────────────


class TestFileRead:
    def test_read_file_success(self, client):
        out = server_mod._outputs_dir / "slides"
        out.mkdir(parents=True)
        target = out / "readme.md"
        target.write_text("hello world")
        resp = client.get("/file", params={"path": str(target)})
        assert resp.status_code == 200
        assert resp.json()["content"] == "hello world"

    def test_read_file_not_found(self, client):
        resp = client.get(
            "/file", params={"path": str(server_mod._outputs_dir / "nope.md")}
        )
        assert resp.status_code == 404

    def test_read_file_path_traversal_blocked(self, client):
        # Attempt to escape outputs directory
        evil = str(server_mod._outputs_dir / ".." / "pyproject.toml")
        resp = client.get("/file", params={"path": evil})
        assert resp.status_code == 400
        assert "outside" in resp.json()["detail"].lower()


# ── Usage ─────────────────────────────────────────────────────────────────────


class TestUsage:
    def test_usage_endpoint(self, client, _reset_globals):
        with patch("queries.usage_summary", return_value={"total_cost": 0.0}):
            resp = client.get("/usage")
        assert resp.status_code == 200
        assert "total_cost" in resp.json()
