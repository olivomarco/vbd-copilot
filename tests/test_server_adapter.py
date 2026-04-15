"""Tests for server_adapter.py — SessionConnection, envelope protocol, snapshot, registry."""

from __future__ import annotations

import asyncio
import time
import uuid
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from server_adapter import (
    SessionConnection,
    _connections,
    _envelope,
    _make_ws_handler,
    add_ws,
    build_snapshot,
    destroy_connection,
    emit_state_changed,
    get_accumulated_response,
    get_cancel_flag,
    get_connection,
    _get_or_create,
    pop_user_response,
    push_user_response,
    remove_ws,
    set_cancel_flag,
    start_heartbeat,
    stop_heartbeat,
    ws_reset,
)
import server_adapter


# ---------------------------------------------------------------------------
# Fixture: clear the module-level _connections registry between tests
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clear_connections():
    """Ensure a clean connection registry for every test."""
    _connections.clear()
    yield
    _connections.clear()
    # Ensure heartbeat task is stopped after every test
    stop_heartbeat()


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
        assert conn.add_ws(ws1) is True  # first connection
        assert conn.add_ws(ws2) is False  # second connection
        assert ws1 in conn.websockets
        assert ws2 in conn.websockets
        assert conn.remove_ws(ws1) is False  # still has ws2
        assert conn.remove_ws(ws2) is True  # empty now

    def test_reset_turn_clears_per_turn_state(self):
        conn = SessionConnection("s1")
        conn.cancel_flag = True
        conn.seen_event_ids.add("evt-1")
        conn.tool_starts["search"] = (123.0, "corr-1")
        conn.active_subagents.append("agent-1")
        conn._seq = 42

        conn.reset_turn()

        assert conn.cancel_flag is False
        # seen_event_ids is pruned only when over 5000, not cleared on every reset
        assert len(conn.seen_event_ids) == 1
        assert len(conn.tool_starts) == 0
        assert len(conn.active_subagents) == 0
        assert conn._seq == 0

    def test_reset_turn_prunes_large_seen_event_ids(self):
        """seen_event_ids is pruned when it exceeds 5000 entries."""
        conn = SessionConnection("s1")
        for i in range(5500):
            conn.seen_event_ids.add(f"evt-{i}")
        assert len(conn.seen_event_ids) == 5500
        conn.reset_turn()
        assert len(conn.seen_event_ids) == 0  # cleared because >5000

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
        # Connection is preserved (handler stays registered) — only
        # destroy_connection() removes it from the registry.
        assert get_connection("s3") is not None

    def test_remove_ws_keeps_connection_with_remaining(self):
        ws1, ws2 = object(), object()
        add_ws("s3b", ws1)
        add_ws("s3b", ws2)
        assert remove_ws("s3b", ws1) is False
        assert get_connection("s3b") is not None

    def test_remove_ws_unknown_session(self):
        ws = object()
        assert remove_ws("ghost", ws) is True

    def test_destroy_connection_removes_from_registry(self):
        ws = object()
        add_ws("s-destroy", ws)
        assert get_connection("s-destroy") is not None
        destroy_connection("s-destroy")
        assert get_connection("s-destroy") is None

    def test_destroy_connection_unknown_session_is_noop(self):
        destroy_connection("nonexistent")  # should not raise


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
        env = _envelope(
            conn, "tool_started", {"tool": "search"}, correlation_id="corr-abc"
        )
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
        # seen_event_ids is preserved (pruned only when >5000)
        assert len(conn.seen_event_ids) == 1
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


# ===================================================================
# 9. emit_state_changed
# ===================================================================


class TestEmitStateChanged:
    @pytest.mark.asyncio
    async def test_emit_state_changed_with_connection(self):
        """emit_state_changed should not raise when clients are connected."""
        add_ws("state-1", object())
        conn = get_connection("state-1")
        assert conn is not None
        # _send will try ws.send_text on the bare object and silently fail
        # but emit_state_changed itself should not raise
        emit_state_changed("state-1", "ended", "test_reason")

    def test_emit_state_changed_no_connection(self):
        """emit_state_changed should be a no-op for unknown sessions."""
        emit_state_changed("nonexistent", "ended", "test")

    def test_emit_state_changed_no_websockets(self):
        """emit_state_changed should be a no-op when session has no connected WS."""
        conn = _get_or_create("state-empty")
        assert len(conn.websockets) == 0
        emit_state_changed("state-empty", "ended", "test")  # should not raise


# ===================================================================
# 10. Heartbeat start / stop
# ===================================================================


class TestHeartbeat:
    @pytest.mark.asyncio
    async def test_start_stop_heartbeat(self):
        """Heartbeat task should start and be cancellable."""
        start_heartbeat()
        await asyncio.sleep(0.05)
        task = server_adapter._heartbeat_task
        assert task is not None
        assert not task.done()
        stop_heartbeat()
        await asyncio.sleep(0.05)
        assert server_adapter._heartbeat_task is None

    @pytest.mark.asyncio
    async def test_start_heartbeat_idempotent(self):
        """Calling start_heartbeat twice should not create duplicate tasks."""
        start_heartbeat()
        await asyncio.sleep(0.01)
        task1 = server_adapter._heartbeat_task
        start_heartbeat()
        await asyncio.sleep(0.01)
        task2 = server_adapter._heartbeat_task
        assert task1 is task2  # same task, not a new one
        stop_heartbeat()


# ===================================================================
# 11. Envelope shapes for heartbeat and state_changed
# ===================================================================


class TestPhase3EnvelopeShapes:
    def test_heartbeat_envelope_shape(self):
        """Heartbeat envelopes should have the correct structure."""
        conn = SessionConnection("hb-test")
        env = _envelope(conn, "heartbeat", {"ts": 1234567890.0})
        assert env["v"] == 1
        assert env["type"] == "heartbeat"
        assert env["data"]["ts"] == 1234567890.0
        assert env["id"]  # UUID present
        assert env["seq"] == 1

    def test_state_changed_envelope_shape(self):
        """session_state_changed envelopes should include status and reason."""
        conn = SessionConnection("sc-test")
        env = _envelope(
            conn,
            "session_state_changed",
            {
                "session_id": "sc-test",
                "status": "ended",
                "reason": "session_deleted",
            },
        )
        assert env["v"] == 1
        assert env["type"] == "session_state_changed"
        assert env["data"]["status"] == "ended"
        assert env["data"]["reason"] == "session_deleted"


# ===================================================================
# 12. Snapshot during response accumulation
# ===================================================================


class TestSnapshotDuringResponse:
    def test_snapshot_during_response(self):
        """Snapshot should build correctly when response_buffer has content."""
        ws = object()
        add_ws("snap-resp", ws)
        conn = get_connection("snap-resp")
        conn.response_buffer.append("Hello ")
        conn.response_buffer.append("world")
        snap = build_snapshot("snap-resp")
        assert snap is not None
        assert snap["data"]["status"] == "active"
        # response_buffer is internal state, not exposed in snapshot,
        # but snapshot should still build without errors


# ===================================================================
# 13. Event handler — verbose/debug event forwarding
# ===================================================================

# --- Helpers -----------------------------------------------------------


class _FakeSessionEventType:
    """Minimal stand-in for SessionEventType with all event types we need."""

    ASSISTANT_MESSAGE_DELTA = "ASSISTANT_MESSAGE_DELTA"
    ASSISTANT_STREAMING_DELTA = "ASSISTANT_STREAMING_DELTA"
    TOOL_EXECUTION_START = "TOOL_EXECUTION_START"
    TOOL_EXECUTION_COMPLETE = "TOOL_EXECUTION_COMPLETE"
    SUBAGENT_STARTED = "SUBAGENT_STARTED"
    SUBAGENT_COMPLETED = "SUBAGENT_COMPLETED"
    SUBAGENT_FAILED = "SUBAGENT_FAILED"
    SUBAGENT_SELECTED = "SUBAGENT_SELECTED"
    ASSISTANT_USAGE = "ASSISTANT_USAGE"
    SESSION_ERROR = "SESSION_ERROR"
    # New verbose/debug event types
    ASSISTANT_REASONING_DELTA = "ASSISTANT_REASONING_DELTA"
    TOOL_EXECUTION_PARTIAL_RESULT = "TOOL_EXECUTION_PARTIAL_RESULT"
    TOOL_EXECUTION_PROGRESS = "TOOL_EXECUTION_PROGRESS"
    ASSISTANT_INTENT = "ASSISTANT_INTENT"
    ASSISTANT_REASONING = "ASSISTANT_REASONING"
    SESSION_HANDOFF = "SESSION_HANDOFF"
    SESSION_COMPACTION_START = "SESSION_COMPACTION_START"
    SESSION_COMPACTION_COMPLETE = "SESSION_COMPACTION_COMPLETE"
    ASSISTANT_TURN_START = "ASSISTANT_TURN_START"
    ASSISTANT_TURN_END = "ASSISTANT_TURN_END"
    SUBAGENT_DESELECTED = "SUBAGENT_DESELECTED"


def _make_event(etype, **data_attrs):
    """Build a fake event compatible with _handler's expectations."""
    data = SimpleNamespace(**data_attrs)
    return SimpleNamespace(type=etype, id=str(uuid.uuid4()), data=data)


@pytest.fixture
def handler_env():
    """Set up a handler with a mock _send, returning (handler, sent_messages).

    Patches SessionEventType so the handler sees all event type attributes.
    """
    sid = "handler-test"
    add_ws(sid, object())
    sent: list[dict] = []

    def fake_send(payload, session_id=None):
        sent.append(payload)

    with patch("server_adapter._send", side_effect=fake_send):
        with patch(
            "copilot.generated.session_events.SessionEventType",
            _FakeSessionEventType,
            create=True,
        ):
            handler = _make_ws_handler(sid)
            yield handler, sent, sid


# --- Tests for each new event type ---


class TestVerboseEventForwarding:
    """Tests that each new verbose/debug event type is correctly forwarded."""

    def test_reasoning_delta(self, handler_env):
        handler, sent, sid = handler_env
        handler(
            _make_event(
                _FakeSessionEventType.ASSISTANT_REASONING_DELTA,
                delta_content="thinking about this...",
            )
        )
        assert len(sent) == 1
        assert sent[0]["type"] == "reasoning_delta"
        assert sent[0]["data"]["content"] == "thinking about this..."

    def test_reasoning_delta_empty_skipped(self, handler_env):
        handler, sent, sid = handler_env
        handler(
            _make_event(
                _FakeSessionEventType.ASSISTANT_REASONING_DELTA,
                delta_content="",
            )
        )
        assert len(sent) == 0

    def test_reasoning_delta_none_skipped(self, handler_env):
        handler, sent, sid = handler_env
        handler(
            _make_event(
                _FakeSessionEventType.ASSISTANT_REASONING_DELTA,
                delta_content=None,
            )
        )
        assert len(sent) == 0

    def test_tool_partial_result(self, handler_env):
        handler, sent, sid = handler_env
        handler(
            _make_event(
                _FakeSessionEventType.TOOL_EXECUTION_PARTIAL_RESULT,
                partial_output="partial data here",
            )
        )
        assert len(sent) == 1
        assert sent[0]["type"] == "tool_partial_result"
        assert sent[0]["data"]["content"] == "partial data here"

    def test_tool_partial_result_truncated_at_2000(self, handler_env):
        handler, sent, sid = handler_env
        long_output = "x" * 3000
        handler(
            _make_event(
                _FakeSessionEventType.TOOL_EXECUTION_PARTIAL_RESULT,
                partial_output=long_output,
            )
        )
        assert len(sent[0]["data"]["content"]) == 2000

    def test_tool_progress(self, handler_env):
        handler, sent, sid = handler_env
        handler(
            _make_event(
                _FakeSessionEventType.TOOL_EXECUTION_PROGRESS,
                progress_message="Searching files...",
            )
        )
        assert len(sent) == 1
        assert sent[0]["type"] == "tool_progress"
        assert sent[0]["data"]["message"] == "Searching files..."

    def test_assistant_intent(self, handler_env):
        handler, sent, sid = handler_env
        handler(
            _make_event(
                _FakeSessionEventType.ASSISTANT_INTENT,
                intent="I will search the codebase",
            )
        )
        assert len(sent) == 1
        assert sent[0]["type"] == "assistant_intent"
        assert sent[0]["data"]["intent"] == "I will search the codebase"

    def test_assistant_intent_empty_skipped(self, handler_env):
        handler, sent, sid = handler_env
        handler(
            _make_event(
                _FakeSessionEventType.ASSISTANT_INTENT,
                intent="",
            )
        )
        assert len(sent) == 0

    def test_assistant_reasoning(self, handler_env):
        handler, sent, sid = handler_env
        handler(
            _make_event(
                _FakeSessionEventType.ASSISTANT_REASONING,
                reasoning_text="The user wants to refactor the auth module",
            )
        )
        assert len(sent) == 1
        assert sent[0]["type"] == "assistant_reasoning"
        assert sent[0]["data"]["text"] == "The user wants to refactor the auth module"

    def test_assistant_reasoning_truncated_at_2000(self, handler_env):
        handler, sent, sid = handler_env
        long_text = "y" * 3000
        handler(
            _make_event(
                _FakeSessionEventType.ASSISTANT_REASONING,
                reasoning_text=long_text,
            )
        )
        assert len(sent[0]["data"]["text"]) == 2000

    def test_assistant_reasoning_empty_skipped(self, handler_env):
        handler, sent, sid = handler_env
        handler(
            _make_event(
                _FakeSessionEventType.ASSISTANT_REASONING,
                reasoning_text="",
            )
        )
        assert len(sent) == 0

    def test_session_handoff(self, handler_env):
        handler, sent, sid = handler_env
        handler(
            _make_event(
                _FakeSessionEventType.SESSION_HANDOFF,
                agent_name="slide-builder",
            )
        )
        assert len(sent) == 1
        assert sent[0]["type"] == "session_handoff"
        assert sent[0]["data"]["agent"] == "slide-builder"

    def test_compaction_start(self, handler_env):
        handler, sent, sid = handler_env
        handler(
            _make_event(
                _FakeSessionEventType.SESSION_COMPACTION_START,
            )
        )
        assert len(sent) == 1
        assert sent[0]["type"] == "compaction_start"
        assert sent[0]["data"] == {}

    def test_compaction_complete(self, handler_env):
        handler, sent, sid = handler_env
        handler(
            _make_event(
                _FakeSessionEventType.SESSION_COMPACTION_COMPLETE,
                post_compaction_tokens=4096,
            )
        )
        assert len(sent) == 1
        assert sent[0]["type"] == "compaction_complete"
        assert sent[0]["data"]["post_tokens"] == 4096

    def test_compaction_complete_none_defaults_to_zero(self, handler_env):
        handler, sent, sid = handler_env
        handler(
            _make_event(
                _FakeSessionEventType.SESSION_COMPACTION_COMPLETE,
                post_compaction_tokens=None,
            )
        )
        assert sent[0]["data"]["post_tokens"] == 0

    def test_turn_started(self, handler_env):
        handler, sent, sid = handler_env
        handler(
            _make_event(
                _FakeSessionEventType.ASSISTANT_TURN_START,
            )
        )
        assert len(sent) == 1
        assert sent[0]["type"] == "turn_started"
        assert sent[0]["data"] == {}

    def test_turn_ended(self, handler_env):
        handler, sent, sid = handler_env
        handler(
            _make_event(
                _FakeSessionEventType.ASSISTANT_TURN_END,
            )
        )
        assert len(sent) == 1
        assert sent[0]["type"] == "turn_ended"
        assert sent[0]["data"] == {}

    def test_subagent_deselected(self, handler_env):
        handler, sent, sid = handler_env
        handler(
            _make_event(
                _FakeSessionEventType.SUBAGENT_DESELECTED,
                agent_name="qa-reviewer",
            )
        )
        assert len(sent) == 1
        assert sent[0]["type"] == "subagent_deselected"
        assert sent[0]["data"]["agent"] == "qa-reviewer"


# ===================================================================
# 14. hasattr guards — events missing from SessionEventType
# ===================================================================


class _MinimalSessionEventType:
    """SessionEventType WITHOUT the new verbose attributes.

    Simulates an older SDK where these event types don't exist.
    """

    ASSISTANT_MESSAGE_DELTA = "ASSISTANT_MESSAGE_DELTA"
    ASSISTANT_STREAMING_DELTA = "ASSISTANT_STREAMING_DELTA"
    TOOL_EXECUTION_START = "TOOL_EXECUTION_START"
    TOOL_EXECUTION_COMPLETE = "TOOL_EXECUTION_COMPLETE"
    SUBAGENT_STARTED = "SUBAGENT_STARTED"
    SUBAGENT_COMPLETED = "SUBAGENT_COMPLETED"
    ASSISTANT_USAGE = "ASSISTANT_USAGE"
    SESSION_ERROR = "SESSION_ERROR"
    # Deliberately MISSING: ASSISTANT_REASONING_DELTA, TOOL_EXECUTION_PARTIAL_RESULT,
    # TOOL_EXECUTION_PROGRESS, ASSISTANT_INTENT, ASSISTANT_REASONING, SESSION_HANDOFF,
    # SESSION_COMPACTION_START, SESSION_COMPACTION_COMPLETE, ASSISTANT_TURN_START,
    # ASSISTANT_TURN_END, SUBAGENT_DESELECTED


class TestHasattrGuards:
    """Events guarded by hasattr should not crash when the enum lacks the attribute."""

    @pytest.fixture
    def minimal_handler_env(self):
        sid = "guard-test"
        add_ws(sid, object())
        sent: list[dict] = []

        def fake_send(payload, session_id=None):
            sent.append(payload)

        with patch("server_adapter._send", side_effect=fake_send):
            with patch(
                "copilot.generated.session_events.SessionEventType",
                _MinimalSessionEventType,
                create=True,
            ):
                handler = _make_ws_handler(sid)
                yield handler, sent

    def test_unknown_event_type_does_not_crash(self, minimal_handler_env):
        """An event with an unrecognized type should hit the catch-all without error."""
        handler, sent = minimal_handler_env
        handler(_make_event("TOTALLY_UNKNOWN_TYPE"))
        assert len(sent) == 0  # not forwarded, but no exception


# ===================================================================
# 15. Existing delta handling still works
# ===================================================================


class TestExistingDeltaStillWorks:
    """Verify ASSISTANT_MESSAGE_DELTA forwarding was not broken."""

    def test_message_delta_forwarded(self, handler_env):
        handler, sent, sid = handler_env
        handler(
            _make_event(
                _FakeSessionEventType.ASSISTANT_MESSAGE_DELTA,
                delta_content="Hello world",
            )
        )
        assert len(sent) == 1
        assert sent[0]["type"] == "delta"
        assert sent[0]["data"]["content"] == "Hello world"

    def test_message_delta_accumulates_response_buffer(self, handler_env):
        handler, sent, sid = handler_env
        handler(
            _make_event(
                _FakeSessionEventType.ASSISTANT_MESSAGE_DELTA,
                delta_content="chunk1",
            )
        )
        handler(
            _make_event(
                _FakeSessionEventType.ASSISTANT_MESSAGE_DELTA,
                delta_content="chunk2",
            )
        )
        conn = get_connection(sid)
        assert conn.get_response_text() == "chunk1chunk2"

    def test_message_delta_dedup_by_event_id(self, handler_env):
        handler, sent, sid = handler_env
        evt = _make_event(
            _FakeSessionEventType.ASSISTANT_MESSAGE_DELTA,
            delta_content="dup",
        )
        handler(evt)
        handler(evt)  # same event object → same id → deduped
        assert len(sent) == 1

    def test_streaming_delta_forwarded(self, handler_env):
        handler, sent, sid = handler_env
        handler(
            _make_event(
                _FakeSessionEventType.ASSISTANT_STREAMING_DELTA,
                delta_content="streaming chunk",
            )
        )
        assert len(sent) == 1
        assert sent[0]["type"] == "delta"
        assert sent[0]["data"]["content"] == "streaming chunk"
