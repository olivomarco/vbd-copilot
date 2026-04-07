"""Tests for server_adapter.py Phase 1: SessionConnection, envelope, snapshot."""

import asyncio

import pytest

import server_adapter as sa


@pytest.fixture(autouse=True)
def _clean_connections():
    """Ensure connection registry is clean between tests."""
    sa._connections.clear()
    yield
    sa._connections.clear()


class TestSessionConnection:
    def test_init(self):
        conn = sa.SessionConnection("test-123")
        assert conn.session_id == "test-123"
        assert len(conn.websockets) == 0
        assert conn.cancel_flag is False
        assert conn.pending_input is None
        assert conn.last_done is None
        assert conn._seq == 0

    def test_add_ws_first(self):
        conn = sa.SessionConnection("s1")
        assert conn.add_ws("ws1") is True

    def test_add_ws_second(self):
        conn = sa.SessionConnection("s1")
        conn.add_ws("ws1")
        assert conn.add_ws("ws2") is False

    def test_remove_ws(self):
        conn = sa.SessionConnection("s1")
        conn.add_ws("ws1")
        conn.add_ws("ws2")
        assert conn.remove_ws("ws1") is False
        assert conn.remove_ws("ws2") is True

    def test_next_seq(self):
        conn = sa.SessionConnection("s1")
        assert conn.next_seq() == 1
        assert conn.next_seq() == 2
        assert conn.next_seq() == 3

    def test_reset_turn(self):
        conn = sa.SessionConnection("s1")
        conn.cancel_flag = True
        conn.seen_event_ids.add("e1")
        conn.tool_starts["t1"] = (1.0, "corr-1")
        conn.active_subagents.append("agent1")
        conn.subagent_correlations["agent1"] = "corr-2"
        conn._seq = 5
        conn.reset_turn()
        assert conn.cancel_flag is False
        assert len(conn.seen_event_ids) == 0
        assert len(conn.tool_starts) == 0
        assert len(conn.active_subagents) == 0
        assert len(conn.subagent_correlations) == 0
        assert conn._seq == 0

    def test_cleanup(self):
        conn = sa.SessionConnection("s1")
        conn.pending_input = {"q": "test"}
        conn.last_done = {"status": "ok"}
        conn.cleanup()
        assert conn.pending_input is None
        assert conn.last_done is None


class TestEnvelope:
    def test_basic(self):
        env = sa._envelope(None, "test", {"foo": "bar"})
        assert env["v"] == 1
        assert env["type"] == "test"
        assert env["seq"] == 0
        assert env["correlationId"] is None
        assert env["data"] == {"foo": "bar"}
        assert "id" in env
        assert "ts" in env

    def test_with_connection(self):
        conn = sa.SessionConnection("s1")
        env = sa._envelope(conn, "delta", {"content": "hi"})
        assert env["seq"] == 1
        env2 = sa._envelope(conn, "delta", {"content": "there"})
        assert env2["seq"] == 2

    def test_with_correlation_id(self):
        env = sa._envelope(None, "tool_started", {"tool": "t"}, correlation_id="corr-abc")
        assert env["correlationId"] == "corr-abc"


class TestBuildSnapshot:
    def test_nonexistent_session(self):
        assert sa.build_snapshot("nonexistent") is None

    def test_idle_session(self):
        conn = sa._get_or_create("snap-1")
        snap = sa.build_snapshot("snap-1")
        assert snap is not None
        assert snap["type"] == "session_snapshot"
        assert snap["data"]["status"] == "idle"
        assert snap["data"]["pending_input"] is None
        assert snap["data"]["active_subagents"] == []

    def test_waiting_session(self):
        conn = sa._get_or_create("snap-2")
        conn.add_ws("ws1")
        conn.pending_input = {"question": "hello"}
        snap = sa.build_snapshot("snap-2")
        assert snap["data"]["status"] == "waiting"
        assert snap["data"]["pending_input"] == {"question": "hello"}

    def test_active_session(self):
        conn = sa._get_or_create("snap-3")
        conn.add_ws("ws1")
        snap = sa.build_snapshot("snap-3")
        assert snap["data"]["status"] == "active"

    def test_snapshot_includes_last_done(self):
        conn = sa._get_or_create("snap-4")
        conn.last_done = {"type": "done", "status": "success"}
        snap = sa.build_snapshot("snap-4")
        assert snap["data"]["last_done"] == {"type": "done", "status": "success"}


class TestPublicFunctionDelegation:
    def test_add_ws_returns_bool(self):
        assert sa.add_ws("s1", "ws1") is True
        assert sa.add_ws("s1", "ws2") is False

    def test_remove_ws_cleans_up(self):
        sa.add_ws("s2", "ws1")
        assert sa.get_connection("s2") is not None
        sa.remove_ws("s2", "ws1")
        assert sa.get_connection("s2") is None

    def test_cancel_flag(self):
        sa.add_ws("s3", "ws1")
        sa.set_cancel_flag(True, "s3")
        assert sa.get_cancel_flag("s3") is True
        sa.set_cancel_flag(False, "s3")
        assert sa.get_cancel_flag("s3") is False

    def test_pending_input(self):
        sa.add_ws("s4", "ws1")
        sa.set_pending_input("s4", {"q": "test"})
        assert sa.get_pending_input("s4") == {"q": "test"}
        sa.set_pending_input("s4", None)
        assert sa.get_pending_input("s4") is None

    def test_last_done(self):
        sa.add_ws("s5", "ws1")
        sa.set_last_done("s5", {"type": "done"})
        assert sa.get_last_done("s5") == {"type": "done"}
        sa.clear_last_done("s5")
        assert sa.get_last_done("s5") is None

    def test_legacy_cancel_flag(self):
        sa.set_cancel_flag(True)
        assert sa.get_cancel_flag() is True
        sa.set_cancel_flag(False)
        assert sa.get_cancel_flag() is False

    def test_ws_reset_session(self):
        sa.add_ws("s6", "ws1")
        conn = sa.get_connection("s6")
        conn.cancel_flag = True
        conn.seen_event_ids.add("e1")
        conn._seq = 10
        sa.ws_reset("s6")
        assert conn.cancel_flag is False
        assert len(conn.seen_event_ids) == 0
        assert conn._seq == 0

    def test_ws_reset_legacy(self):
        sa._cancel_flag = True
        sa._seen_event_ids.add("e1")
        sa.ws_reset()
        assert sa._cancel_flag is False
        assert len(sa._seen_event_ids) == 0

    def test_push_pop_user_response(self):
        sa.add_ws("s7", "ws1")

        sa.push_user_response("hello", "s7")
        conn = sa.get_connection("s7")
        assert not conn.input_queue.empty()

        loop = asyncio.new_event_loop()
        result = loop.run_until_complete(sa.pop_user_response(timeout=1.0, session_id="s7"))
        loop.close()
        assert result == "hello"

    def test_has_event_handler_false(self):
        assert sa.has_event_handler("no-such") is False

    def test_get_connection_returns_none(self):
        assert sa.get_connection("nonexistent") is None
