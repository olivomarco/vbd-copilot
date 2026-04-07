"""Tests for server_adapter.py — SessionConnection, envelope protocol, snapshot, registry."""

from __future__ import annotations

import asyncio
import time

import pytest

from server_adapter import (
    SessionConnection,
    _connections,
    _envelope,
    add_ws,
    build_snapshot,
    get_accumulated_response,
    get_cancel_flag,
    get_connection,
    _get_or_create,
    pop_user_response,
    push_user_response,
    remove_ws,
    set_cancel_flag,
    ws_reset,
)


# ---------------------------------------------------------------------------
# Fixture: clear the module-level _connections registry between tests
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _clear_connections():
    """Ensure a clean connection registry for every test."""
    _connections.clear()
    yield
    _connections.clear()


# ===================================================================
# 1. SessionConnection lifecycle
# ===================================================================

class TestSessionConnectionInit:
    def test_defaults(self):
        conn = SessionConnection("test-123")
        assert conn.session_id == "test-123"
        assert len(conn.websockets) == 0
        assert conn.cancel_flag is False
        assert conn.pending_input is None
        assert conn.last_done is None
        assert conn.active_subagents == []
        assert conn._seq == 0
        assert conn.created_at > 0

    def test_add_remove_ws(self):
        conn = SessionConnection("s1")
        ws1, ws2 = object(), object()
        assert conn.add_ws(ws1) is True   # first connection
        assert conn.add_ws(ws2) is False  # second connection
        assert ws1 in conn.websockets
        assert ws2 in conn.websockets
        assert conn.remove_ws(ws1) is False  # still has ws2
        assert conn.remove_ws(ws2) is True   # empty now

    def test_reset_turn_clears_per_turn_state(self):
        conn = SessionConnection("s1")
        conn.cancel_flag = True
        conn.seen_event_ids.add("evt-1")
        conn.tool_starts["search"] = (123.0, "corr-1")
        conn.active_subagents.append("agent-1")
        conn._seq = 42

        conn.reset_turn()

        assert conn.cancel_flag is False
        assert len(conn.seen_event_ids) == 0
        assert len(conn.tool_starts) == 0
        assert len(conn.active_subagents) == 0
        assert conn._seq == 0

    def test_reset_turn_preserves_pending_input(self):
        conn = SessionConnection("s1")
        conn.pending_input = {"question": "test"}
        conn.reset_turn()
        assert conn.pending_input == {"question": "test"}

    def test_cleanup_clears_everything(self):
        conn = SessionConnection("s1")
        conn.pending_input = {"question": "test"}
        conn.last_done = {"status": "success"}
        conn.cancel_flag = True
        conn._seq = 5

        conn.cleanup()

        assert conn.pending_input is None
        assert conn.last_done is None
        assert conn.cancel_flag is False
        assert conn._seq == 0

    def test_next_seq_monotonic(self):
        conn = SessionConnection("s1")
        seqs = [conn.next_seq() for _ in range(5)]
        assert seqs == [1, 2, 3, 4, 5]


# ===================================================================
# 2. Connection registry
# ===================================================================

class TestConnectionRegistry:
    def test_get_connection_returns_none_for_unknown(self):
        assert get_connection("nonexistent") is None

    def test_get_or_create_creates_then_returns_same(self):
        conn = _get_or_create("new-session")
        assert conn is not None
        assert conn.session_id == "new-session"
        assert get_connection("new-session") is conn

    def test_add_ws_creates_connection(self):
        ws = object()
        is_first = add_ws("s2", ws)
        assert is_first is True
        conn = get_connection("s2")
        assert conn is not None
        assert ws in conn.websockets

    def test_add_ws_second_returns_false(self):
        ws1, ws2 = object(), object()
        assert add_ws("s2b", ws1) is True
        assert add_ws("s2b", ws2) is False

    def test_remove_ws_cleans_up_when_empty(self):
        ws = object()
        add_ws("s3", ws)
        is_empty = remove_ws("s3", ws)
        assert is_empty is True
        assert get_connection("s3") is None  # cleaned up from registry

    def test_remove_ws_keeps_connection_with_remaining(self):
        ws1, ws2 = object(), object()
        add_ws("s3b", ws1)
        add_ws("s3b", ws2)
        assert remove_ws("s3b", ws1) is False
        assert get_connection("s3b") is not None

    def test_remove_ws_unknown_session(self):
        ws = object()
        assert remove_ws("ghost", ws) is True


# ===================================================================
# 3. Cancel flag (backward compat)
# ===================================================================

class TestCancelFlag:
    def test_set_cancel_flag_with_session(self):
        add_ws("s4", object())
        set_cancel_flag(True, "s4")
        assert get_cancel_flag("s4") is True
        set_cancel_flag(False, "s4")
        assert get_cancel_flag("s4") is False

    def test_set_cancel_flag_legacy(self):
        set_cancel_flag(True)
        assert get_cancel_flag() is True
        set_cancel_flag(False)
        assert get_cancel_flag() is False

    def test_get_cancel_flag_unknown_session(self):
        assert get_cancel_flag("no-such-session") is False


# ===================================================================
# 4. Envelope protocol
# ===================================================================

class TestEnvelope:
    def test_envelope_structure(self):
        conn = SessionConnection("env-test")
        env = _envelope(conn, "test_type", {"key": "value"})
        assert env["v"] == 1
        assert env["type"] == "test_type"
        assert isinstance(env["id"], str) and len(env["id"]) > 0
        assert env["seq"] == 1
        assert env["ts"] > 0
        assert env["correlationId"] is None
        assert env["data"] == {"key": "value"}

    def test_envelope_with_correlation_id(self):
        conn = SessionConnection("env-corr")
        env = _envelope(conn, "tool_started", {"tool": "search"}, correlation_id="corr-abc")
        assert env["correlationId"] == "corr-abc"

    def test_envelope_seq_increments(self):
        conn = SessionConnection("env-seq")
        e1 = _envelope(conn, "a", {})
        e2 = _envelope(conn, "b", {})
        e3 = _envelope(conn, "c", {})
        assert e1["seq"] == 1
        assert e2["seq"] == 2
        assert e3["seq"] == 3

    def test_envelope_with_none_conn(self):
        env = _envelope(None, "test", {"x": 1})
        assert env["seq"] == 0
        assert env["v"] == 1
        assert env["data"] == {"x": 1}

    def test_envelope_id_is_unique(self):
        conn = SessionConnection("uid-test")
        ids = {_envelope(conn, "t", {})["id"] for _ in range(10)}
        assert len(ids) == 10  # all unique

    def test_envelope_ts_is_recent(self):
        before = time.time()
        env = _envelope(SessionConnection("ts-test"), "x", {})
        after = time.time()
        assert before <= env["ts"] <= after


# ===================================================================
# 5. Snapshot
# ===================================================================

class TestBuildSnapshot:
    def test_snapshot_active_session(self):
        ws = object()
        add_ws("snap-1", ws)
        conn = get_connection("snap-1")
        conn.active_subagents = ["agent-a", "agent-b"]

        snap = build_snapshot("snap-1")
        assert snap is not None
        assert snap["type"] == "session_snapshot"
        assert snap["v"] == 1
        data = snap["data"]
        assert data["session_id"] == "snap-1"
        assert data["status"] == "active"
        assert data["active_subagents"] == ["agent-a", "agent-b"]
        assert data["pending_input"] is None

    def test_snapshot_waiting_session(self):
        ws = object()
        add_ws("snap-2", ws)
        conn = get_connection("snap-2")
        conn.pending_input = {"question": "Continue?", "choices": ["yes", "no"]}

        snap = build_snapshot("snap-2")
        assert snap["data"]["status"] == "waiting"
        assert snap["data"]["pending_input"] == {
            "question": "Continue?",
            "choices": ["yes", "no"],
        }

    def test_snapshot_idle_session(self):
        """A session with a connection object but no websockets is idle."""
        _get_or_create("snap-idle")
        snap = build_snapshot("snap-idle")
        assert snap is not None
        assert snap["data"]["status"] == "idle"

    def test_snapshot_returns_none_for_unknown(self):
        assert build_snapshot("nonexistent") is None

    def test_snapshot_includes_last_done(self):
        add_ws("snap-done", object())
        conn = get_connection("snap-done")
        conn.last_done = {"status": "success", "message": "All good"}
        snap = build_snapshot("snap-done")
        assert snap["data"]["last_done"] == {"status": "success", "message": "All good"}


# ===================================================================
# 6. Pending input / user response flow
# ===================================================================

class TestUserResponseFlow:
    @pytest.mark.asyncio
    async def test_push_pop_user_response(self):
        add_ws("resp-1", object())
        push_user_response("hello", session_id="resp-1")
        result = await pop_user_response(timeout=1.0, session_id="resp-1")
        assert result == "hello"

    @pytest.mark.asyncio
    async def test_pop_user_response_timeout(self):
        add_ws("resp-2", object())
        with pytest.raises(asyncio.TimeoutError):
            await pop_user_response(timeout=0.1, session_id="resp-2")

    def test_push_clears_pending_input(self):
        add_ws("resp-3", object())
        conn = get_connection("resp-3")
        conn.pending_input = {"question": "test?"}
        push_user_response("answer", session_id="resp-3")
        assert conn.pending_input is None

    @pytest.mark.asyncio
    async def test_multiple_responses_fifo(self):
        add_ws("resp-fifo", object())
        push_user_response("first", session_id="resp-fifo")
        push_user_response("second", session_id="resp-fifo")
        assert await pop_user_response(timeout=1.0, session_id="resp-fifo") == "first"
        assert await pop_user_response(timeout=1.0, session_id="resp-fifo") == "second"


# ===================================================================
# 7. ws_reset delegates to SessionConnection
# ===================================================================

class TestWsReset:
    def test_ws_reset_delegates(self):
        add_ws("reset-1", object())
        conn = get_connection("reset-1")
        conn.cancel_flag = True
        conn.seen_event_ids.add("x")
        conn.tool_starts["t"] = (1.0, "c")
        conn._seq = 10

        ws_reset("reset-1")

        assert conn.cancel_flag is False
        assert len(conn.seen_event_ids) == 0
        assert len(conn.tool_starts) == 0
        assert conn._seq == 0

    def test_ws_reset_unknown_session_is_noop(self):
        # Should not raise
        ws_reset("no-such-session")

    def test_ws_reset_legacy(self):
        # Legacy path (no session_id) should not raise
        ws_reset()


# ===================================================================
# 8. Response buffer
# ===================================================================

class TestResponseBuffer:
    def test_response_buffer_accumulates(self):
        conn = SessionConnection("buf-1")
        conn.response_buffer.append("Hello ")
        conn.response_buffer.append("world")
        assert conn.get_response_text() == "Hello world"

    def test_response_buffer_cleared_on_reset(self):
        conn = SessionConnection("buf-2")
        conn.response_buffer.append("some text")
        conn.reset_turn()
        assert conn.get_response_text() == ""

    def test_get_accumulated_response(self):
        add_ws("buf-3", object())
        conn = _connections["buf-3"]
        conn.response_buffer.append("chunk1")
        conn.response_buffer.append("chunk2")
        assert get_accumulated_response("buf-3") == "chunk1chunk2"

    def test_get_accumulated_response_unknown_session(self):
        assert get_accumulated_response("nonexistent") == ""
