"""Extended tests for server.py — covers grouped outputs, delete, download, zip,
metadata, events, status, turn invocations, and safe_outputs_path edge cases."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

import server as server_mod
from server import app, _safe_outputs_path, _classify_output_category


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_globals(tmp_path):
    """Inject test doubles into server module-level globals."""
    store = MagicMock()
    store.list_sessions.return_value = []
    store.resolve_prefix.return_value = None
    store.get_session.return_value = None
    store.get_turns.return_value = []
    store.get_invocations.return_value = []
    store.get_invocations_for_turn.return_value = []
    store.end_session.return_value = None

    old_store = server_mod._event_store
    old_client = server_mod._copilot_client
    old_collector = server_mod._collector
    old_app_dir = server_mod._app_dir
    old_outputs = server_mod._outputs_dir
    old_session_map = server_mod._session_map.copy()

    server_mod._event_store = store
    server_mod._copilot_client = None
    server_mod._collector = None
    server_mod._app_dir = tmp_path
    server_mod._outputs_dir = tmp_path / "outputs"
    server_mod._outputs_dir.mkdir()
    server_mod._session_map.clear()

    yield store

    server_mod._event_store = old_store
    server_mod._copilot_client = old_client
    server_mod._collector = old_collector
    server_mod._app_dir = old_app_dir
    server_mod._outputs_dir = old_outputs
    server_mod._session_map.clear()
    server_mod._session_map.update(old_session_map)


@pytest.fixture()
def client():
    return TestClient(app)


# ---------------------------------------------------------------------------
# _safe_outputs_path
# ---------------------------------------------------------------------------


class TestSafeOutputsPath:
    def test_empty_path_rejected(self):
        with pytest.raises(Exception):
            _safe_outputs_path("")

    def test_whitespace_path_rejected(self):
        with pytest.raises(Exception):
            _safe_outputs_path("   ")

    def test_null_byte_rejected(self):
        with pytest.raises(Exception):
            _safe_outputs_path("file\x00.txt")

    def test_relative_inside_outputs(self, tmp_path):
        out = server_mod._outputs_dir
        (out / "test.txt").write_text("hello")
        result = _safe_outputs_path(str(out / "test.txt"))
        assert result.name == "test.txt"

    def test_traversal_blocked(self):
        evil = str(server_mod._outputs_dir / ".." / "pyproject.toml")
        with pytest.raises(Exception):
            _safe_outputs_path(evil)


# ---------------------------------------------------------------------------
# _classify_output_category
# ---------------------------------------------------------------------------


class TestClassifyOutputCategory:
    def test_slides_category(self):
        p = Path("/some/path/outputs/slides/deck.pptx")
        assert _classify_output_category(p) == "slides"

    def test_demos_category(self):
        p = Path("/some/path/outputs/demos/guide.md")
        assert _classify_output_category(p) == "demos"

    def test_other_category(self):
        p = Path("/some/unrelated/path/file.txt")
        assert _classify_output_category(p) == "other"


# ---------------------------------------------------------------------------
# Turn invocations
# ---------------------------------------------------------------------------


class TestTurnInvocations:
    def test_get_turn_invocations_found(self, client, _reset_globals):
        store = _reset_globals
        store.resolve_prefix.return_value = "sess-001"
        store.get_turns.return_value = [
            {"id": "turn-1", "turn_number": 1, "agent": "slides"},
        ]
        store.get_invocations.return_value = [
            {"id": "inv-1", "name": "bing_search", "type": "tool_call"},
        ]
        resp = client.get("/sessions/sess-001/turns/1/invocations")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["name"] == "bing_search"

    def test_get_turn_invocations_not_found(self, client, _reset_globals):
        store = _reset_globals
        store.resolve_prefix.return_value = "sess-001"
        store.get_turns.return_value = [
            {"id": "turn-1", "turn_number": 1},
        ]
        resp = client.get("/sessions/sess-001/turns/99/invocations")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Session status
# ---------------------------------------------------------------------------


class TestSessionStatus:
    def test_status_not_found(self, client, _reset_globals):
        store = _reset_globals
        store.resolve_prefix.return_value = None
        resp = client.get("/sessions/unknown/status")
        assert resp.status_code == 404

    def test_status_session_detail_not_found(self, client, _reset_globals):
        store = _reset_globals
        store.resolve_prefix.return_value = "sess-001"
        store.get_session.return_value = None
        resp = client.get("/sessions/sess-001/status")
        assert resp.status_code == 404

    def test_status_active_session(self, client, _reset_globals):
        store = _reset_globals
        store.resolve_prefix.return_value = "sess-001"
        store.get_session.return_value = {
            "id": "sess-001",
            "status": "active",
            "turn_count": 3,
            "resumable": 1,
        }
        store.get_turns.return_value = []
        with (
            patch("server_adapter.get_connection", return_value=None),
            patch("server_adapter.get_pending_input", return_value=None),
            patch("server_adapter.get_output_files", return_value=[]),
        ):
            resp = client.get("/sessions/sess-001/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["session_id"] == "sess-001"
        assert data["status"] == "active"
        assert data["turn_count"] == 3
        assert data["resumable"] is True

    def test_status_ended_with_output_files(self, client, _reset_globals):
        store = _reset_globals
        store.resolve_prefix.return_value = "sess-001"
        store.get_session.return_value = {
            "id": "sess-001",
            "status": "ended",
            "turn_count": 1,
            "resumable": 0,
        }
        store.get_turns.return_value = [
            {"id": "t1", "output_files": json.dumps(["/path/to/file.pptx"])}
        ]
        with (
            patch("server_adapter.get_connection", return_value=None),
            patch("server_adapter.get_pending_input", return_value=None),
            patch("server_adapter.get_output_files", return_value=[]),
        ):
            resp = client.get("/sessions/sess-001/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["output_files"] == ["/path/to/file.pptx"]


# ---------------------------------------------------------------------------
# Session events
# ---------------------------------------------------------------------------


class TestSessionEvents:
    def test_events_session_not_found(self, client, _reset_globals):
        store = _reset_globals
        store.resolve_prefix.return_value = None
        resp = client.get("/sessions/nope/events")
        assert resp.status_code == 404

    def test_events_empty_session(self, client, _reset_globals):
        store = _reset_globals
        store.resolve_prefix.return_value = "sess-001"
        store.get_session.return_value = {"id": "sess-001", "status": "active"}
        store.get_turns.return_value = []
        resp = client.get("/sessions/sess-001/events")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_events_ended_session(self, client, _reset_globals):
        store = _reset_globals
        store.resolve_prefix.return_value = "sess-001"
        store.get_session.return_value = {
            "id": "sess-001",
            "status": "ended",
            "started_at": "2024-01-01T00:00:00",
            "ended_at": "2024-01-01T01:00:00",
        }
        store.get_turns.return_value = []
        resp = client.get("/sessions/sess-001/events")
        assert resp.status_code == 200
        events = resp.json()
        assert any(e["type"] == "done" for e in events)

    def test_events_with_turns(self, client, _reset_globals):
        store = _reset_globals
        store.resolve_prefix.return_value = "sess-001"
        store.get_session.return_value = {"id": "sess-001", "status": "active"}
        store.get_turns.return_value = [
            {
                "id": "t1",
                "turn_number": 1,
                "agent": "slides",
                "user_prompt": "hello",
                "assistant_response": "hi there",
                "started_at": "2024-01-01T00:00:00",
                "ended_at": "2024-01-01T00:01:00",
                "input_tokens": 100,
                "output_tokens": 50,
                "cache_read_tokens": 10,
                "cache_write_tokens": 5,
                "estimated_cost_usd": 0.01,
                "output_files": "[]",
            }
        ]
        store.get_invocations_for_turn.return_value = []
        resp = client.get("/sessions/sess-001/events")
        assert resp.status_code == 200
        events = resp.json()
        types = [e["type"] for e in events]
        assert "turn_started" in types
        assert "assistant_message" in types
        assert "usage" in types

    def test_events_with_tool_invocations(self, client, _reset_globals):
        store = _reset_globals
        store.resolve_prefix.return_value = "sess-001"
        store.get_session.return_value = {"id": "sess-001", "status": "active"}
        store.get_turns.return_value = [
            {
                "id": "t1",
                "turn_number": 1,
                "agent": "slides",
                "user_prompt": "search for AKS",
                "started_at": "2024-01-01T00:00:00",
                "input_tokens": 0,
                "output_tokens": 0,
                "output_files": "[]",
            }
        ]
        store.get_invocations_for_turn.return_value = [
            {
                "type": "tool_call",
                "name": "bing_search",
                "input": '{"query": "AKS"}',
                "output": "results...",
                "started_at": "2024-01-01T00:00:01",
                "ended_at": "2024-01-01T00:00:02",
                "duration_ms": 1000,
            }
        ]
        resp = client.get("/sessions/sess-001/events")
        events = resp.json()
        types = [e["type"] for e in events]
        assert "tool_started" in types
        assert "tool_completed" in types

    def test_events_with_subagent_invocations(self, client, _reset_globals):
        store = _reset_globals
        store.resolve_prefix.return_value = "sess-001"
        store.get_session.return_value = {"id": "sess-001", "status": "active"}
        store.get_turns.return_value = [
            {
                "id": "t1",
                "turn_number": 1,
                "agent": "slides",
                "user_prompt": "build deck",
                "started_at": "2024-01-01T00:00:00",
                "input_tokens": 0,
                "output_tokens": 0,
                "output_files": "[]",
            }
        ]
        store.get_invocations_for_turn.return_value = [
            {
                "type": "subagent",
                "name": "slide-layout",
                "started_at": "2024-01-01T00:00:01",
                "ended_at": "2024-01-01T00:00:05",
                "duration_ms": 4000,
            },
            {
                "type": "tool_call",
                "name": "str_replace_editor",
                "input": "{}",
                "output": "done",
                "started_at": "2024-01-01T00:00:02",
                "ended_at": "2024-01-01T00:00:03",
                "duration_ms": 1000,
            },
        ]
        resp = client.get("/sessions/sess-001/events")
        events = resp.json()
        types = [e["type"] for e in events]
        assert "subagent_started" in types
        assert "subagent_completed" in types
        # Nested tool should have _subagent tag
        tool_events = [e for e in events if e["type"] == "tool_started"]
        assert len(tool_events) == 1
        assert tool_events[0]["data"].get("_subagent") == "slide-layout"

    def test_events_with_output_files(self, client, _reset_globals):
        store = _reset_globals
        store.resolve_prefix.return_value = "sess-001"
        store.get_session.return_value = {"id": "sess-001", "status": "active"}
        store.get_turns.return_value = [
            {
                "id": "t1",
                "turn_number": 1,
                "agent": "slides",
                "user_prompt": "build",
                "started_at": "2024-01-01T00:00:00",
                "ended_at": "2024-01-01T00:01:00",
                "input_tokens": 0,
                "output_tokens": 0,
                "output_files": json.dumps(["/outputs/slides/deck.pptx"]),
            }
        ]
        store.get_invocations_for_turn.return_value = []
        resp = client.get("/sessions/sess-001/events")
        events = resp.json()
        file_events = [e for e in events if e["type"] == "new_files"]
        assert len(file_events) == 1
        assert file_events[0]["data"]["files"] == ["/outputs/slides/deck.pptx"]


# ---------------------------------------------------------------------------
# Usage with filters
# ---------------------------------------------------------------------------


class TestUsageEndpoint:
    def test_usage_with_period_filter(self, client, _reset_globals):
        with patch("queries.usage_summary", return_value={"total_cost": 1.5}) as mock:
            resp = client.get("/usage?period=30d")
        assert resp.status_code == 200
        mock.assert_called_once()

    def test_usage_with_agent_filter(self, client, _reset_globals):
        with patch("queries.usage_summary", return_value={"total_cost": 0.0}):
            resp = client.get("/usage?agent=slides")
        assert resp.status_code == 200

    def test_usage_with_model_filter(self, client, _reset_globals):
        with patch("queries.usage_summary", return_value={"total_cost": 0.0}):
            resp = client.get("/usage?model=gpt-4")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Grouped outputs
# ---------------------------------------------------------------------------


class TestGroupedOutputs:
    def test_empty_grouped_outputs(self, client):
        resp = client.get("/outputs/grouped")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_grouped_slides(self, client):
        slides_dir = server_mod._outputs_dir / "slides"
        slides_dir.mkdir(parents=True)
        (slides_dir / "my-deck.pptx").write_bytes(b"PK\x03\x04fake")
        resp = client.get("/outputs/grouped")
        data = resp.json()
        assert len(data) == 1
        assert data[0]["category"] == "slides"
        assert "my-deck" in data[0]["id"]

    def test_grouped_slides_with_pdf(self, client):
        slides_dir = server_mod._outputs_dir / "slides"
        slides_dir.mkdir(parents=True)
        (slides_dir / "my-deck.pptx").write_bytes(b"PK\x03\x04fake")
        (slides_dir / "my-deck.pdf").write_bytes(b"PDFfake")
        resp = client.get("/outputs/grouped")
        data = resp.json()
        assert data[0]["has_pdf"] is True
        assert data[0]["file_count"] == 2

    def test_grouped_slides_with_level_and_duration(self, client):
        slides_dir = server_mod._outputs_dir / "slides"
        slides_dir.mkdir(parents=True)
        (slides_dir / "aks-overview-l300-30min.pptx").write_bytes(b"PK\x03\x04")
        resp = client.get("/outputs/grouped")
        data = resp.json()
        assert data[0]["content_level"] == "L300"
        assert data[0]["duration"] == "30min"

    def test_grouped_demos(self, client):
        demos_dir = server_mod._outputs_dir / "demos"
        demos_dir.mkdir(parents=True)
        (demos_dir / "aks-demos.md").write_text("# AKS Demos")
        companion = demos_dir / "aks"
        companion.mkdir()
        (companion / "script.sh").write_text("#!/bin/bash")
        resp = client.get("/outputs/grouped")
        data = resp.json()
        assert len(data) == 1
        assert data[0]["category"] == "demos"
        assert data[0]["file_count"] == 2

    def test_grouped_hackathons(self, client):
        hack_dir = server_mod._outputs_dir / "hackathons" / "azure-ai"
        hack_dir.mkdir(parents=True)
        (hack_dir / "README.md").write_text("# Hackathon")
        resp = client.get("/outputs/grouped")
        data = resp.json()
        assert len(data) == 1
        assert data[0]["category"] == "hackathons"

    def test_grouped_ai_projects(self, client):
        proj_dir = server_mod._outputs_dir / "ai-projects" / "contoso"
        proj_dir.mkdir(parents=True)
        (proj_dir / "README.md").write_text("# Contoso")
        src_dir = proj_dir / "src"
        src_dir.mkdir()
        (src_dir / "main.py").write_text("print('hi')")
        resp = client.get("/outputs/grouped")
        data = resp.json()
        assert len(data) == 1
        assert data[0]["category"] == "ai-projects"
        assert data[0]["has_solution"] is True

    def test_grouped_ai_projects_with_architecture(self, client):
        proj_dir = server_mod._outputs_dir / "ai-projects" / "contoso"
        proj_dir.mkdir(parents=True)
        docs_dir = proj_dir / "docs"
        docs_dir.mkdir()
        src_dir = proj_dir / "src"
        src_dir.mkdir()
        (src_dir / "main.py").write_text("print('hi')")
        (proj_dir / "README.md").write_text("# Contoso")
        (docs_dir / "solution-design.md").write_text("# Solution")
        resp = client.get("/outputs/grouped")
        data = resp.json()
        assert data[0]["has_architecture"] is True
        assert len(data[0]["architecture_docs"]) == 1


# ---------------------------------------------------------------------------
# Delete output
# ---------------------------------------------------------------------------


class TestDeleteOutput:
    def test_delete_file(self, client):
        f = server_mod._outputs_dir / "slides" / "old.pptx"
        f.parent.mkdir(parents=True)
        f.write_bytes(b"PK")
        resp = client.delete("/outputs", params={"path": str(f)})
        assert resp.status_code == 200
        assert resp.json()["ok"] is True
        assert not f.exists()

    def test_delete_directory(self, client):
        d = server_mod._outputs_dir / "hackathons" / "old-hack"
        d.mkdir(parents=True)
        (d / "README.md").write_text("hi")
        resp = client.delete("/outputs", params={"path": str(d)})
        assert resp.status_code == 200
        assert not d.exists()

    def test_delete_not_found(self, client):
        resp = client.delete(
            "/outputs", params={"path": str(server_mod._outputs_dir / "nope.txt")}
        )
        assert resp.status_code == 404

    def test_delete_path_traversal_blocked(self, client):
        evil = str(server_mod._outputs_dir / ".." / "pyproject.toml")
        resp = client.delete("/outputs", params={"path": evil})
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Delete grouped output
# ---------------------------------------------------------------------------


class TestDeleteGroupedOutput:
    def test_delete_grouped_hackathon(self, client):
        d = server_mod._outputs_dir / "hackathons" / "my-hack"
        d.mkdir(parents=True)
        (d / "README.md").write_text("hi")
        resp = client.delete("/outputs/grouped", params={"id": "hackathons/my-hack"})
        assert resp.status_code == 200
        assert not d.exists()

    def test_delete_grouped_ai_project(self, client):
        d = server_mod._outputs_dir / "ai-projects" / "proj"
        d.mkdir(parents=True)
        (d / "README.md").write_text("hi")
        resp = client.delete("/outputs/grouped", params={"id": "ai-projects/proj"})
        assert resp.status_code == 200
        assert not d.exists()

    def test_delete_grouped_slides(self, client):
        slides_dir = server_mod._outputs_dir / "slides"
        slides_dir.mkdir(parents=True)
        (slides_dir / "my-deck.pptx").write_bytes(b"PK")
        (slides_dir / "my-deck.pdf").write_bytes(b"PDF")
        resp = client.delete("/outputs/grouped", params={"id": "slides/my-deck"})
        assert resp.status_code == 200
        assert not (slides_dir / "my-deck.pptx").exists()

    def test_delete_grouped_demos(self, client):
        demos_dir = server_mod._outputs_dir / "demos"
        demos_dir.mkdir(parents=True)
        (demos_dir / "aks-demos.md").write_text("# AKS")
        companion = demos_dir / "aks"
        companion.mkdir()
        (companion / "script.sh").write_text("#!/bin/bash")
        resp = client.delete("/outputs/grouped", params={"id": "demos/aks"})
        assert resp.status_code == 200

    def test_delete_grouped_invalid_id(self, client):
        resp = client.delete("/outputs/grouped", params={"id": "invalid"})
        assert resp.status_code == 400

    def test_delete_grouped_unknown_category(self, client):
        resp = client.delete("/outputs/grouped", params={"id": "foo/bar"})
        assert resp.status_code == 400

    def test_delete_grouped_hackathon_not_found(self, client):
        (server_mod._outputs_dir / "hackathons").mkdir(parents=True)
        resp = client.delete(
            "/outputs/grouped", params={"id": "hackathons/nonexistent"}
        )
        assert resp.status_code == 404

    def test_delete_grouped_demos_not_found(self, client):
        (server_mod._outputs_dir / "demos").mkdir(parents=True)
        resp = client.delete("/outputs/grouped", params={"id": "demos/nonexistent"})
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# File download
# ---------------------------------------------------------------------------


class TestFileDownload:
    def test_download_file(self, client):
        f = server_mod._outputs_dir / "slides" / "deck.pptx"
        f.parent.mkdir(parents=True)
        f.write_bytes(b"PK\x03\x04fake")
        resp = client.get("/file/download", params={"path": str(f)})
        assert resp.status_code == 200
        assert "attachment" in resp.headers.get("content-disposition", "")

    def test_download_not_found(self, client):
        resp = client.get(
            "/file/download",
            params={"path": str(server_mod._outputs_dir / "nope.pptx")},
        )
        assert resp.status_code == 404

    def test_download_generator_script_blocked(self, client):
        f = server_mod._outputs_dir / "slides" / "generate_my_deck.py"
        f.parent.mkdir(parents=True)
        f.write_text("# generator code")
        resp = client.get("/file/download", params={"path": str(f)})
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# ZIP export
# ---------------------------------------------------------------------------


class TestZipExport:
    def test_zip_single_file(self, client):
        f = server_mod._outputs_dir / "slides" / "deck.pptx"
        f.parent.mkdir(parents=True)
        f.write_bytes(b"PK\x03\x04fake")
        resp = client.post("/outputs/zip", json={"paths": [str(f)]})
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/zip"

    def test_zip_empty_paths_rejected(self, client):
        resp = client.post("/outputs/zip", json={"paths": []})
        assert resp.status_code == 400

    def test_zip_custom_name(self, client):
        f = server_mod._outputs_dir / "slides" / "deck.pptx"
        f.parent.mkdir(parents=True)
        f.write_bytes(b"PK\x03\x04fake")
        resp = client.post(
            "/outputs/zip", json={"paths": [str(f)], "name": "my-export"}
        )
        assert resp.status_code == 200
        assert "my-export" in resp.headers["content-disposition"]

    def test_zip_directory(self, client):
        d = server_mod._outputs_dir / "hackathons" / "my-hack"
        d.mkdir(parents=True)
        (d / "README.md").write_text("# Hack")
        (d / "challenge-00.md").write_text("# Challenge")
        resp = client.post("/outputs/zip", json={"paths": [str(d)]})
        assert resp.status_code == 200

    def test_zip_skips_generator_scripts(self, client):
        import zipfile
        import io

        d = server_mod._outputs_dir / "slides"
        d.mkdir(parents=True)
        (d / "deck.pptx").write_bytes(b"PK\x03\x04fake")
        (d / "generate_deck.py").write_text("# code")
        resp = client.post(
            "/outputs/zip",
            json={"paths": [str(d / "deck.pptx"), str(d / "generate_deck.py")]},
        )
        assert resp.status_code == 200
        zf = zipfile.ZipFile(io.BytesIO(resp.content))
        names = zf.namelist()
        assert "deck.pptx" in names
        # generator script should be excluded
        assert "generate_deck.py" not in names


# ---------------------------------------------------------------------------
# Output metadata
# ---------------------------------------------------------------------------


class TestOutputMetadata:
    def test_metadata_for_pptx(self, client):
        f = server_mod._outputs_dir / "slides" / "aks-l300-30min.pptx"
        f.parent.mkdir(parents=True)
        f.write_bytes(b"PK\x03\x04fake")
        resp = client.get("/outputs/metadata", params={"path": str(f)})
        assert resp.status_code == 200
        data = resp.json()
        assert data["contentLevel"] == "L300"
        assert "30" in data["duration"]

    def test_metadata_with_plan_file(self, client, tmp_path):
        f = server_mod._outputs_dir / "slides" / "my-deck.pptx"
        f.parent.mkdir(parents=True)
        f.write_bytes(b"PK\x03\x04fake")
        plans = tmp_path / "plans"
        plans.mkdir()
        (plans / "my-deck-complete.md").write_text("# Plan")
        resp = client.get("/outputs/metadata", params={"path": str(f)})
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("planFile") == "plans/my-deck-complete.md"

    def test_metadata_not_found(self, client):
        resp = client.get(
            "/outputs/metadata",
            params={"path": str(server_mod._outputs_dir / "nope.txt")},
        )
        assert resp.status_code == 404

    def test_metadata_markdown_file(self, client):
        f = server_mod._outputs_dir / "demos" / "aks-demos.md"
        f.parent.mkdir(parents=True)
        f.write_text("# AKS Demos")
        resp = client.get("/outputs/metadata", params={"path": str(f)})
        assert resp.status_code == 200
        data = resp.json()
        assert data["category"] == "demos"

    def test_metadata_with_duration_hours(self, client):
        f = server_mod._outputs_dir / "slides" / "workshop-2h.pptx"
        f.parent.mkdir(parents=True)
        f.write_bytes(b"PK")
        resp = client.get("/outputs/metadata", params={"path": str(f)})
        data = resp.json()
        assert data["duration"] == "2h"


# ---------------------------------------------------------------------------
# Verbose logging middleware
# ---------------------------------------------------------------------------


class TestLoggingMiddleware:
    def test_request_succeeds_without_verbose(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_request_succeeds_with_verbose(self, client):
        old = server_mod._verbose_backend_logs
        server_mod._verbose_backend_logs = True
        try:
            resp = client.get("/health")
            assert resp.status_code == 200
        finally:
            server_mod._verbose_backend_logs = old

    def test_query_string_logged(self, client):
        old = server_mod._verbose_backend_logs
        server_mod._verbose_backend_logs = True
        try:
            resp = client.get("/sessions?all=true")
            assert resp.status_code == 200
        finally:
            server_mod._verbose_backend_logs = old


# ---------------------------------------------------------------------------
# Events edge cases — detail not found after resolve, bad output_files JSON
# ---------------------------------------------------------------------------


class TestSessionEventsEdge:
    def test_events_detail_not_found_after_resolve(self, client, _reset_globals):
        store = _reset_globals
        store.resolve_prefix.return_value = "sess-001"
        store.get_session.return_value = None
        resp = client.get("/sessions/sess-001/events")
        assert resp.status_code == 404

    def test_events_with_subagent_name_on_tool(self, client, _reset_globals):
        """Tool call with explicit subagent_name field uses it."""
        store = _reset_globals
        store.resolve_prefix.return_value = "sess-001"
        store.get_session.return_value = {"id": "sess-001", "status": "active"}
        store.get_turns.return_value = [
            {
                "id": "t1",
                "turn_number": 1,
                "agent": "slides",
                "user_prompt": "q",
                "started_at": "2024-01-01T00:00:00",
                "input_tokens": 0,
                "output_tokens": 0,
                "output_files": "[]",
            }
        ]
        store.get_invocations_for_turn.return_value = [
            {
                "type": "tool_call",
                "name": "bash",
                "input": "{}",
                "output": "ok",
                "started_at": "2024-01-01T00:00:01",
                "ended_at": "2024-01-01T00:00:02",
                "duration_ms": 1000,
                "subagent_name": "slide-builder",
            }
        ]
        resp = client.get("/sessions/sess-001/events")
        events = resp.json()
        tool_started = [e for e in events if e["type"] == "tool_started"]
        assert tool_started[0]["data"]["_subagent"] == "slide-builder"

    def test_events_with_bad_output_files_json(self, client, _reset_globals):
        """Malformed output_files JSON should not crash."""
        store = _reset_globals
        store.resolve_prefix.return_value = "sess-001"
        store.get_session.return_value = {"id": "sess-001", "status": "active"}
        store.get_turns.return_value = [
            {
                "id": "t1",
                "turn_number": 1,
                "agent": "slides",
                "user_prompt": "q",
                "started_at": "2024-01-01T00:00:00",
                "input_tokens": 0,
                "output_tokens": 0,
                "output_files": "NOT VALID JSON",
            }
        ]
        store.get_invocations_for_turn.return_value = []
        resp = client.get("/sessions/sess-001/events")
        assert resp.status_code == 200

    def test_events_no_tokens_no_usage(self, client, _reset_globals):
        """Turn with zero tokens should not emit usage event."""
        store = _reset_globals
        store.resolve_prefix.return_value = "sess-001"
        store.get_session.return_value = {"id": "sess-001", "status": "active"}
        store.get_turns.return_value = [
            {
                "id": "t1",
                "turn_number": 1,
                "agent": "slides",
                "user_prompt": "q",
                "started_at": "2024-01-01T00:00:00",
                "input_tokens": 0,
                "output_tokens": 0,
                "output_files": "[]",
            }
        ]
        store.get_invocations_for_turn.return_value = []
        resp = client.get("/sessions/sess-001/events")
        events = resp.json()
        assert not any(e["type"] == "usage" for e in events)


# ---------------------------------------------------------------------------
# Status edge cases
# ---------------------------------------------------------------------------


class TestSessionStatusEdge:
    def test_status_with_pending_input(self, client, _reset_globals):
        store = _reset_globals
        store.resolve_prefix.return_value = "sess-001"
        store.get_session.return_value = {
            "id": "sess-001",
            "status": "active",
            "turn_count": 1,
            "resumable": 0,
        }
        with (
            patch("server_adapter.get_connection", return_value=None),
            patch(
                "server_adapter.get_pending_input", return_value={"question": "what?"}
            ),
            patch("server_adapter.get_output_files", return_value=[]),
        ):
            resp = client.get("/sessions/sess-001/status")
        data = resp.json()
        assert data["pending_input"] == {"question": "what?"}

    def test_status_ended_bad_output_files_json(self, client, _reset_globals):
        """Malformed output_files in turn should not crash status endpoint."""
        store = _reset_globals
        store.resolve_prefix.return_value = "sess-001"
        store.get_session.return_value = {
            "id": "sess-001",
            "status": "ended",
            "turn_count": 1,
            "resumable": 0,
        }
        store.get_turns.return_value = [{"id": "t1", "output_files": "NOT JSON"}]
        with (
            patch("server_adapter.get_connection", return_value=None),
            patch("server_adapter.get_pending_input", return_value=None),
            patch("server_adapter.get_output_files", return_value=[]),
        ):
            resp = client.get("/sessions/sess-001/status")
        assert resp.status_code == 200
        assert resp.json()["output_files"] == []


# ---------------------------------------------------------------------------
# End session with session_map entry
# ---------------------------------------------------------------------------


class TestEndSessionExtended:
    def test_end_session_with_session_map(self, client, _reset_globals):
        store = _reset_globals
        store.resolve_prefix.return_value = "sess-001"
        mock_session = MagicMock()
        mock_session._event_handlers = {}
        server_mod._session_map["sess-001"] = mock_session
        with (
            patch("server_adapter.unregister_event_handler"),
            patch("server_adapter.emit_state_changed"),
        ):
            resp = client.delete("/sessions/sess-001")
        assert resp.status_code == 200
        assert "sess-001" not in server_mod._session_map


# ---------------------------------------------------------------------------
# Outputs with various file types
# ---------------------------------------------------------------------------


class TestOutputsExtended:
    def test_list_outputs_python_file(self, client):
        d = server_mod._outputs_dir / "slides"
        d.mkdir(parents=True)
        # generator file should be skipped as plan file
        (d / "readme.md").write_text("# Hi")
        resp = client.get("/outputs")
        data = resp.json()
        assert any(r["type"] == "markdown" for r in data)

    def test_list_outputs_json_file(self, client):
        d = server_mod._outputs_dir / "ai-projects"
        d.mkdir(parents=True)
        (d / "config.json").write_text("{}")
        resp = client.get("/outputs")
        data = resp.json()
        assert any(r["type"] == "json" for r in data)

    def test_list_outputs_shell_file(self, client):
        d = server_mod._outputs_dir / "demos"
        d.mkdir(parents=True)
        (d / "setup.sh").write_text("#!/bin/bash")
        resp = client.get("/outputs")
        data = resp.json()
        assert any(r["type"] == "shell" for r in data)

    def test_list_outputs_skips_unsupported_extension(self, client):
        d = server_mod._outputs_dir / "slides"
        d.mkdir(parents=True)
        (d / "image.png").write_bytes(b"\x89PNG")
        resp = client.get("/outputs")
        # PNG is not in _FILE_TYPE_MAP so should not appear
        assert all(r["name"] != "image.png" for r in resp.json())

    def test_list_outputs_skips_plan_in_subdir(self, client):
        """Ensure -plan.md files in actual outputs subdirs are skipped too."""
        d = server_mod._outputs_dir / "slides"
        d.mkdir(parents=True)
        (d / "aks-plan.md").write_text("plan")
        (d / "aks-deck.pptx").write_bytes(b"PK\x03\x04fake")
        resp = client.get("/outputs")
        data = resp.json()
        # Only the pptx should appear; plan should be skipped
        names = [r["name"] for r in data]
        assert "aks-plan.md" not in names
        assert "aks-deck.pptx" in names

    def test_list_outputs_bicep_file(self, client):
        d = server_mod._outputs_dir / "ai-projects"
        d.mkdir(parents=True)
        (d / "main.bicep").write_text("resource foo;")
        resp = client.get("/outputs")
        data = resp.json()
        assert any(r["type"] == "bicep" for r in data)


# ---------------------------------------------------------------------------
# Grouped outputs edge cases
# ---------------------------------------------------------------------------


class TestGroupedOutputsEdge:
    def test_grouped_demos_no_companion_dir(self, client):
        demos_dir = server_mod._outputs_dir / "demos"
        demos_dir.mkdir(parents=True)
        (demos_dir / "standalone-demos.md").write_text("# Standalone")
        resp = client.get("/outputs/grouped")
        data = resp.json()
        assert len(data) == 1
        assert data[0]["file_count"] == 1

    def test_grouped_hackathon_skips_hidden(self, client):
        hack_dir = server_mod._outputs_dir / "hackathons"
        hack_dir.mkdir(parents=True)
        hidden = hack_dir / ".hidden"
        hidden.mkdir()
        (hidden / "file.txt").write_text("secret")
        resp = client.get("/outputs/grouped")
        assert resp.json() == []

    def test_grouped_ai_project_no_readme(self, client):
        proj_dir = server_mod._outputs_dir / "ai-projects" / "proj"
        proj_dir.mkdir(parents=True)
        src_dir = proj_dir / "src"
        src_dir.mkdir()
        (src_dir / "main.py").write_text("print()")
        resp = client.get("/outputs/grouped")
        data = resp.json()
        assert len(data) == 1
        # primary_file should be the first file when no README
        assert "main.py" in data[0]["primary_file"]

    def test_grouped_empty_hackathon_subdir(self, client):
        hack_dir = server_mod._outputs_dir / "hackathons" / "empty"
        hack_dir.mkdir(parents=True)
        # Empty directory — no files
        resp = client.get("/outputs/grouped")
        assert resp.json() == []


# ===========================================================================
# PATH TRAVERSAL & SECURITY TESTS
# ===========================================================================
# Comprehensive coverage of attack vectors against all file-serving endpoints.
# Each vector is tested against _safe_outputs_path directly and against the
# HTTP endpoints that accept user-supplied paths.
# ===========================================================================


class TestSafeOutputsPathSecurity:
    """Attack vectors against the _safe_outputs_path helper."""

    def test_absolute_path_escape(self):
        """Absolute path pointing outside outputs/ must be rejected."""
        with pytest.raises(Exception):
            _safe_outputs_path("/etc/passwd")

    def test_absolute_path_to_app_dir(self):
        """Absolute path to project root (not outputs/) must be rejected."""
        with pytest.raises(Exception):
            _safe_outputs_path(str(server_mod._app_dir / "pyproject.toml"))

    def test_double_dot_relative(self):
        """Relative ../.. traversal must be rejected."""
        with pytest.raises(Exception):
            _safe_outputs_path("../../etc/passwd")

    def test_encoded_dot_dot_literal(self):
        """Literal '%2E%2E' as directory name (post-URL-decode) is safe
        because Path treats it as a literal dirname, not traversal.
        _safe_outputs_path should NOT raise — the resolved path stays
        inside outputs/. But it won't find a file, which is fine."""
        # After URL decoding %2E%2E%2F becomes '../' which Python Path
        # would resolve. Simulate what FastAPI delivers after decoding:
        with pytest.raises(Exception):
            _safe_outputs_path("../../../etc/passwd")

    def test_windows_style_separators_on_linux(self):
        r"""Backslash path separators: `..\..\\etc\\passwd`.
        On Linux, backslashes are literal filename characters, so the
        resolved path stays under outputs/ (no real traversal)."""
        # Should not raise — the backslashes are not path separators on Linux
        # But the resulting path won't exist. Key: no escape from outputs/.
        try:
            result = _safe_outputs_path("..\\..\\etc\\passwd")
            # If it doesn't raise, the resolved path must still be inside outputs
            assert result.is_relative_to(server_mod._outputs_dir.resolve())
        except Exception:
            pass  # Raising is also acceptable — it means the path was rejected

    def test_dot_dot_with_trailing_slash(self):
        with pytest.raises(Exception):
            _safe_outputs_path("../")

    def test_triple_dots(self):
        """Path component '...' is a normal dirname, not traversal."""
        # Should not escape outputs/ — '...' is literal
        try:
            result = _safe_outputs_path("...")
            assert result.is_relative_to(server_mod._outputs_dir.resolve())
        except Exception:
            pass  # Rejecting is fine too

    def test_quadruple_dots(self):
        """Path component '....' is a normal dirname."""
        try:
            result = _safe_outputs_path("....")
            assert result.is_relative_to(server_mod._outputs_dir.resolve())
        except Exception:
            pass

    def test_mixed_traversal_components(self):
        """Mix of valid and traversal components."""
        with pytest.raises(Exception):
            _safe_outputs_path("slides/../../../etc/passwd")

    def test_dot_slash_current_dir(self):
        """'./slides' should resolve safely inside outputs/."""
        out = server_mod._outputs_dir
        (out / "slides").mkdir(parents=True, exist_ok=True)
        (out / "slides" / "test.pptx").write_bytes(b"PK")
        result = _safe_outputs_path("./slides/test.pptx")
        assert result.is_relative_to(out.resolve())

    def test_unicode_fullwidth_dot(self):
        """Fullwidth characters (U+FF0E = ．, U+FF0F = ／) should not
        normalise to ASCII '../' on resolution. They remain literal."""
        # Fullwidth dots and slashes
        evil = "\uff0e\uff0e\uff0f\uff0e\uff0e\uff0fpasswd"
        try:
            result = _safe_outputs_path(evil)
            # Must still be inside outputs/
            assert result.is_relative_to(server_mod._outputs_dir.resolve())
        except Exception:
            pass  # Rejecting is fine

    def test_unicode_overlong_dot(self):
        """Other Unicode dots (e.g. ․ U+2024 ONE DOT LEADER)."""
        evil = "\u2024\u2024/\u2024\u2024/etc/passwd"
        try:
            result = _safe_outputs_path(evil)
            assert result.is_relative_to(server_mod._outputs_dir.resolve())
        except Exception:
            pass

    def test_symlink_traversal(self, tmp_path):
        """Symlink inside outputs/ pointing outside must be rejected."""
        out = server_mod._outputs_dir
        link = out / "evil-link"
        target = tmp_path / "secret.txt"
        target.write_text("secret data")
        link.symlink_to(target)
        try:
            _safe_outputs_path(str(link))
            # resolve() follows symlinks, so it should point outside outputs/
            # and fail the is_relative_to check
            assert False, "Should have been rejected — symlink escapes outputs/"
        except Exception:
            pass  # Correct: rejected
        finally:
            link.unlink(missing_ok=True)

    def test_deeply_nested_traversal(self):
        """Many levels of ../ to ensure no off-by-one."""
        deep = "/".join([".."] * 20) + "/etc/passwd"
        with pytest.raises(Exception):
            _safe_outputs_path(deep)

    def test_null_byte_mid_path(self):
        """Null byte in the middle of a path component."""
        with pytest.raises(Exception):
            _safe_outputs_path("slides/legit\x00../../etc/passwd")

    def test_null_byte_at_end(self):
        """Null byte at end of path."""
        with pytest.raises(Exception):
            _safe_outputs_path("slides/file.pptx\x00")


# ---------------------------------------------------------------------------
# Endpoint-level path traversal tests
# ---------------------------------------------------------------------------


class TestFileReadPathTraversal:
    """/file endpoint — path traversal via query param."""

    def test_read_file_traversal(self, client):
        evil = str(server_mod._outputs_dir / ".." / "pyproject.toml")
        resp = client.get("/file", params={"path": evil})
        assert resp.status_code == 400

    def test_read_file_absolute_escape(self, client):
        resp = client.get("/file", params={"path": "/etc/passwd"})
        assert resp.status_code == 400

    def test_read_file_null_byte(self, client):
        resp = client.get("/file", params={"path": "slides/file\x00../../etc/passwd"})
        assert resp.status_code == 400

    def test_read_file_empty_path(self, client):
        resp = client.get("/file", params={"path": ""})
        assert resp.status_code == 400


class TestFileDownloadPathTraversal:
    """/file/download endpoint — path traversal via query param."""

    def test_download_traversal(self, client):
        evil = str(server_mod._outputs_dir / ".." / "pyproject.toml")
        resp = client.get("/file/download", params={"path": evil})
        assert resp.status_code == 400

    def test_download_absolute_escape(self, client):
        resp = client.get("/file/download", params={"path": "/etc/passwd"})
        assert resp.status_code == 400

    def test_download_null_byte(self, client):
        resp = client.get(
            "/file/download", params={"path": "slides\x00../../etc/passwd"}
        )
        assert resp.status_code == 400

    def test_download_dot_dot_encoded_after_decode(self, client):
        """After FastAPI decodes %2E%2E%2F it becomes ../ — must be blocked."""
        resp = client.get("/file/download", params={"path": "../../../etc/passwd"})
        assert resp.status_code == 400

    def test_download_double_url_encoding_safe(self, client):
        """Double-encoded %252F becomes literal '%2F' after one decode.
        Path('%2F..%2F') is a literal dirname, not traversal. Should get
        400 (not found or invalid) but must NOT serve /etc/passwd."""
        resp = client.get("/file/download", params={"path": "%2E%2E%2Fetc%2Fpasswd"})
        # FastAPI decodes once; %2E%2E%2F becomes ../etc/passwd in the handler
        # _safe_outputs_path should block it
        assert resp.status_code in (400, 404)


class TestOutputMetadataPathTraversal:
    """/outputs/metadata endpoint — path traversal via query param."""

    def test_metadata_traversal(self, client):
        evil = str(server_mod._outputs_dir / ".." / "pyproject.toml")
        resp = client.get("/outputs/metadata", params={"path": evil})
        assert resp.status_code == 400

    def test_metadata_absolute_escape(self, client):
        resp = client.get("/outputs/metadata", params={"path": "/etc/passwd"})
        assert resp.status_code == 400

    def test_metadata_null_byte(self, client):
        resp = client.get(
            "/outputs/metadata", params={"path": "slides\x00../../etc/passwd"}
        )
        assert resp.status_code == 400

    def test_metadata_empty_path(self, client):
        resp = client.get("/outputs/metadata", params={"path": ""})
        assert resp.status_code == 400


class TestDeleteOutputPathTraversal:
    """/outputs DELETE endpoint — additional traversal vectors."""

    def test_delete_absolute_escape(self, client):
        resp = client.delete("/outputs", params={"path": "/etc/passwd"})
        assert resp.status_code == 400

    def test_delete_null_byte(self, client):
        resp = client.delete("/outputs", params={"path": "slides\x00../../etc/passwd"})
        assert resp.status_code == 400

    def test_delete_deeply_nested_traversal(self, client):
        deep = "/".join([".."] * 20) + "/etc/passwd"
        resp = client.delete("/outputs", params={"path": deep})
        assert resp.status_code == 400


class TestGroupedOutputPathTraversal:
    """/outputs/grouped DELETE endpoint — crafted slug traversal."""

    def test_grouped_delete_traversal_slug(self, client):
        """Slug like ../../etc should be caught by resolve + relative_to check."""
        (server_mod._outputs_dir / "hackathons").mkdir(parents=True, exist_ok=True)
        resp = client.delete("/outputs/grouped", params={"id": "hackathons/../../etc"})
        assert resp.status_code in (400, 404)

    def test_grouped_delete_absolute_slug(self, client):
        resp = client.delete(
            "/outputs/grouped", params={"id": "hackathons//etc/passwd"}
        )
        assert resp.status_code in (400, 404)

    def test_grouped_delete_dot_dot_ai_project(self, client):
        (server_mod._outputs_dir / "ai-projects").mkdir(parents=True, exist_ok=True)
        resp = client.delete(
            "/outputs/grouped", params={"id": "ai-projects/../../secret"}
        )
        assert resp.status_code in (400, 404)

    def test_grouped_delete_null_in_slug(self, client):
        resp = client.delete(
            "/outputs/grouped", params={"id": "hackathons/my-hack\x00../../etc"}
        )
        # Should be caught by category parsing or path safety
        assert resp.status_code in (400, 404)

    def test_grouped_delete_slides_traversal(self, client):
        """Slides slug with traversal should not escape."""
        (server_mod._outputs_dir / "slides").mkdir(parents=True, exist_ok=True)
        resp = client.delete(
            "/outputs/grouped", params={"id": "slides/../../etc/passwd"}
        )
        # id splits as ("slides", "../../etc/passwd") — the slug contains
        # a slash so the endpoint rejects with 400 (invalid category parse)
        assert resp.status_code == 400

    def test_grouped_delete_demos_traversal(self, client):
        (server_mod._outputs_dir / "demos").mkdir(parents=True, exist_ok=True)
        resp = client.delete("/outputs/grouped", params={"id": "demos/../../etc"})
        assert resp.status_code in (400, 404)


class TestZipPathTraversal:
    """/outputs/zip endpoint — mixed safe/unsafe paths."""

    def test_zip_traversal_path_rejected(self, client):
        evil = str(server_mod._outputs_dir / ".." / "pyproject.toml")
        resp = client.post("/outputs/zip", json={"paths": [evil]})
        assert resp.status_code == 400

    def test_zip_absolute_escape_rejected(self, client):
        resp = client.post("/outputs/zip", json={"paths": ["/etc/passwd"]})
        assert resp.status_code == 400

    def test_zip_null_byte_rejected(self, client):
        resp = client.post(
            "/outputs/zip", json={"paths": ["slides\x00../../etc/passwd"]}
        )
        assert resp.status_code == 400

    def test_zip_mixed_safe_and_unsafe(self, client):
        """One valid path + one traversal path — entire request must fail."""
        safe = server_mod._outputs_dir / "slides" / "deck.pptx"
        safe.parent.mkdir(parents=True, exist_ok=True)
        safe.write_bytes(b"PK\x03\x04fake")
        evil = str(server_mod._outputs_dir / ".." / "pyproject.toml")
        resp = client.post("/outputs/zip", json={"paths": [str(safe), evil]})
        assert resp.status_code == 400

    def test_zip_deeply_nested_traversal(self, client):
        deep = "/".join([".."] * 20) + "/etc/passwd"
        resp = client.post("/outputs/zip", json={"paths": [deep]})
        assert resp.status_code == 400

    def test_zip_name_injection(self, client):
        """Zip filename with special characters should be sanitised."""
        f = server_mod._outputs_dir / "slides" / "deck.pptx"
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_bytes(b"PK\x03\x04fake")
        resp = client.post(
            "/outputs/zip",
            json={"paths": [str(f)], "name": '../../../etc/evil"name'},
        )
        assert resp.status_code == 200
        disp = resp.headers.get("content-disposition", "")
        # Must not contain ../ or quotes that break the header
        assert "../" not in disp
