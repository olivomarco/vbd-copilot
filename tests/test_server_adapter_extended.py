"""Extended tests for server_adapter.py — covers pending input, last_done,
output_files, event_handler lifecycle, _detect_phase, and emit_state_changed."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from server_adapter import (
    _connections,
    _detect_phase,
    _get_or_create,
    add_ws,
    clear_last_done,
    emit_state_changed,
    get_ask_user_lock,
    get_last_done,
    get_output_files,
    get_pending_input,
    has_event_handler,
    register_event_handler,
    remove_ws,
    set_active_ws,
    get_active_ws,
    set_last_done,
    set_output_files,
    set_pending_input,
    stop_heartbeat,
    unregister_event_handler,
    ws_reset,
)


@pytest.fixture(autouse=True)
def _clear_connections():
    """Ensure a clean connection registry for every test."""
    _connections.clear()
    yield
    _connections.clear()
    stop_heartbeat()


# ---------------------------------------------------------------------------
# Pending input
# ---------------------------------------------------------------------------


class TestPendingInput:
    def test_set_and_get_pending_input(self):
        _get_or_create("s1")
        set_pending_input("s1", {"question": "what?"})
        assert get_pending_input("s1") == {"question": "what?"}

    def test_get_pending_input_no_connection(self):
        assert get_pending_input("nonexistent") is None

    def test_clear_pending_input(self):
        _get_or_create("s1")
        set_pending_input("s1", {"q": "hi"})
        set_pending_input("s1", None)
        assert get_pending_input("s1") is None

    def test_set_pending_input_no_connection(self):
        # Should not raise
        set_pending_input("nonexistent", {"q": "hi"})


# ---------------------------------------------------------------------------
# Last done
# ---------------------------------------------------------------------------


class TestLastDone:
    def test_set_and_get_last_done(self):
        _get_or_create("s1")
        set_last_done("s1", {"reason": "completed"})
        assert get_last_done("s1") == {"reason": "completed"}

    def test_get_last_done_no_connection(self):
        assert get_last_done("nonexistent") is None

    def test_clear_last_done(self):
        _get_or_create("s1")
        set_last_done("s1", {"reason": "done"})
        clear_last_done("s1")
        assert get_last_done("s1") is None

    def test_set_last_done_no_connection(self):
        set_last_done("nonexistent", {"r": "x"})

    def test_clear_last_done_no_connection(self):
        clear_last_done("nonexistent")


# ---------------------------------------------------------------------------
# Output files
# ---------------------------------------------------------------------------


class TestOutputFiles:
    def test_set_and_get_output_files(self):
        _get_or_create("s1")
        set_output_files("s1", ["/path/a.pptx"])
        assert get_output_files("s1") == ["/path/a.pptx"]

    def test_get_output_files_no_connection(self):
        assert get_output_files("nonexistent") == []

    def test_output_files_dedup(self):
        _get_or_create("s1")
        set_output_files("s1", ["/a.pptx"])
        set_output_files("s1", ["/a.pptx", "/b.pptx"])
        files = get_output_files("s1")
        assert "/a.pptx" in files
        assert "/b.pptx" in files
        assert len(files) == 2

    def test_set_output_files_no_connection(self):
        set_output_files("nonexistent", ["/a.pptx"])


# ---------------------------------------------------------------------------
# Ask user lock
# ---------------------------------------------------------------------------


class TestAskUserLock:
    def test_get_ask_user_lock(self):
        _get_or_create("s1")
        lock = get_ask_user_lock("s1")
        assert isinstance(lock, asyncio.Lock)

    def test_same_lock_returned(self):
        _get_or_create("s1")
        l1 = get_ask_user_lock("s1")
        l2 = get_ask_user_lock("s1")
        assert l1 is l2


# ---------------------------------------------------------------------------
# Event handler lifecycle
# ---------------------------------------------------------------------------


class TestEventHandler:
    def test_no_handler_initially(self):
        _get_or_create("s1")
        assert has_event_handler("s1") is False

    def test_has_event_handler_no_connection(self):
        assert has_event_handler("nonexistent") is False

    def test_register_and_check(self):
        mock_session = MagicMock()
        mock_session.on = MagicMock(return_value=MagicMock())
        register_event_handler("s1", mock_session)
        assert has_event_handler("s1") is True

    def test_register_idempotent(self):
        mock_session = MagicMock()
        mock_session.on = MagicMock(return_value=MagicMock())
        register_event_handler("s1", mock_session)
        register_event_handler("s1", mock_session)
        # on() should only be called once
        assert mock_session.on.call_count == 1

    def test_unregister(self):
        mock_unsub = MagicMock()
        mock_session = MagicMock()
        mock_session.on = MagicMock(return_value=mock_unsub)
        register_event_handler("s1", mock_session)
        unregister_event_handler("s1")
        mock_unsub.assert_called_once()
        assert has_event_handler("s1") is False

    def test_unregister_no_connection(self):
        unregister_event_handler("nonexistent")

    def test_unregister_no_handler(self):
        _get_or_create("s1")
        unregister_event_handler("s1")


# ---------------------------------------------------------------------------
# set_active_ws / get_active_ws
# ---------------------------------------------------------------------------


class TestActiveWs:
    def test_legacy_single_arg(self):
        ws = MagicMock()
        set_active_ws(ws)
        assert get_active_ws() is ws
        set_active_ws(None)
        assert get_active_ws() is None

    def test_per_session_two_arg(self):
        ws = MagicMock()
        set_active_ws("s1", ws)
        conn = _connections.get("s1")
        assert conn is not None
        assert ws in conn.websockets

    def test_per_session_remove(self):
        set_active_ws("s1", False)
        # Should not fail
        set_active_ws("s1", None)


# ---------------------------------------------------------------------------
# remove_ws edge cases
# ---------------------------------------------------------------------------


class TestRemoveWsEdgeCases:
    def test_remove_ws_no_connection(self):
        result = remove_ws("nonexistent", MagicMock())
        assert result is True

    def test_remove_ws_keeps_connection_if_locked(self):
        ws = MagicMock()
        _get_or_create("s1")
        add_ws("s1", ws)
        conn = _connections["s1"]
        # Simulate holding the lock
        conn.ask_user_lock._locked = True
        # Monkey-patch locked() to return True
        original_locked = conn.ask_user_lock.locked
        conn.ask_user_lock.locked = lambda: True
        try:
            remove_ws("s1", ws)
            # Connection should be preserved
            assert "s1" in _connections
        finally:
            conn.ask_user_lock.locked = original_locked

    def test_remove_ws_keeps_connection_if_pending_input(self):
        ws = MagicMock()
        _get_or_create("s1")
        add_ws("s1", ws)
        conn = _connections["s1"]
        conn.pending_input = {"question": "something"}
        remove_ws("s1", ws)
        # Connection should be preserved
        assert "s1" in _connections


# ---------------------------------------------------------------------------
# _detect_phase
# ---------------------------------------------------------------------------


class TestDetectPhase:
    def test_research_tool(self):
        assert _detect_phase(tool="bing_search") == "researching"

    def test_research_tool_web_fetch(self):
        assert _detect_phase(tool="web_fetch") == "researching"

    def test_research_agent(self):
        assert _detect_phase(agent="research-agent") == "researching"

    def test_planning_ask_user(self):
        assert _detect_phase(tool="ask_user") == "planning"

    def test_planning_report_intent(self):
        assert _detect_phase(tool="report_intent") == "planning"

    def test_building_agent(self):
        assert _detect_phase(agent="slide-builder") == "building"

    def test_building_implementor(self):
        assert _detect_phase(agent="ai-implementor") == "building"

    def test_building_tool(self):
        assert _detect_phase(tool="str_replace_editor") == "building"

    def test_building_bash(self):
        assert _detect_phase(tool="bash") == "building"

    def test_qa_tool(self):
        assert _detect_phase(tool="run_pptx_qa_checks") == "qa"

    def test_qa_demo_tool(self):
        assert _detect_phase(tool="run_demo_qa_checks") == "qa"

    def test_qa_reviewer_agent(self):
        assert _detect_phase(agent="slide-reviewer") == "qa"

    def test_unknown(self):
        assert _detect_phase(tool="unknown_tool", agent="unknown_agent") is None

    def test_empty(self):
        assert _detect_phase() is None


# ---------------------------------------------------------------------------
# emit_state_changed
# ---------------------------------------------------------------------------


class TestEmitStateChanged:
    def test_emit_with_ws(self):
        ws = MagicMock()
        _get_or_create("s1")
        add_ws("s1", ws)
        with patch("server_adapter._send") as mock_send:
            emit_state_changed("s1", "active", "turn started")
        mock_send.assert_called_once()
        payload = mock_send.call_args[0][0]
        assert payload["type"] == "session_state_changed"

    def test_emit_without_ws(self):
        _get_or_create("s1")
        with patch("server_adapter._send") as mock_send:
            emit_state_changed("s1", "active")
        mock_send.assert_not_called()

    def test_emit_nonexistent_session(self):
        with patch("server_adapter._send") as mock_send:
            emit_state_changed("nonexistent", "active")
        mock_send.assert_not_called()


class TestSendFunction:
    def test_send_no_session_no_active_ws(self):
        """_send with no session and no active_ws should be a no-op."""
        from server_adapter import _send

        _send({"type": "test", "data": {}})  # should not raise

    def test_send_with_legacy_active_ws(self):
        """_send without session_id falls back to _active_ws."""
        from server_adapter import _send
        import asyncio

        ws = MagicMock()
        ws.client_state = MagicMock()
        ws.client_state.name = "CONNECTED"
        set_active_ws(ws)
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                _send({"type": "test", "data": {}})
            finally:
                loop.close()
                asyncio.set_event_loop(None)
        finally:
            set_active_ws(None)


# ---------------------------------------------------------------------------
# ws_reset
# ---------------------------------------------------------------------------


class TestWsReset:
    def test_ws_reset_session(self):
        conn = _get_or_create("s1")
        conn.response_buffer.append("text")
        conn.cancel_flag = True
        ws_reset("s1")
        assert conn.cancel_flag is False
        assert conn.response_buffer == []

    def test_ws_reset_session_drains_queue(self):
        conn = _get_or_create("s1")
        conn.input_queue.put_nowait("stale response")
        ws_reset("s1")
        assert conn.input_queue.empty()

    def test_ws_reset_legacy(self):
        ws_reset()

    def test_ws_reset_nonexistent(self):
        ws_reset("nonexistent")


# ---------------------------------------------------------------------------
# SessionConnection cleanup
# ---------------------------------------------------------------------------


class TestSessionConnectionCleanup:
    def test_cleanup_clears_state(self):
        conn = _get_or_create("s1")
        conn.pending_input = {"q": "test"}
        conn.last_done = {"reason": "done"}
        mock_unsub = MagicMock()
        conn.event_handler_unsub = mock_unsub
        conn.cleanup()
        assert conn.pending_input is None
        assert conn.last_done is None
        assert conn.event_handler_unsub is None
        mock_unsub.assert_called_once()

    def test_remove_ws_triggers_cleanup(self):
        ws = MagicMock()
        _get_or_create("s1")
        add_ws("s1", ws)
        remove_ws("s1", ws)
        # Connection is preserved (handler stays registered) — only
        # destroy_connection() removes it from the registry.
        assert "s1" in _connections


# ---------------------------------------------------------------------------
# ws_handle_event (legacy)
# ---------------------------------------------------------------------------


class TestWsHandleEvent:
    def test_legacy_handler_noop(self):
        from server_adapter import ws_handle_event

        # Create a minimal event
        from copilot.generated.session_events import SessionEventType

        event = SimpleNamespace(
            type=SessionEventType.ASSISTANT_MESSAGE_DELTA,
            id="evt-1",
            data=SimpleNamespace(delta_content="hello"),
        )
        # Should not raise
        ws_handle_event(event)


# ---------------------------------------------------------------------------
# push/pop user response legacy (no session_id)
# ---------------------------------------------------------------------------


class TestLegacyUserResponse:
    def test_push_legacy(self):
        from server_adapter import push_user_response, _user_input_queue

        push_user_response("hello")
        assert _user_input_queue.get_nowait() == "hello"

    @pytest.mark.asyncio
    async def test_pop_legacy(self):
        from server_adapter import pop_user_response, _user_input_queue

        _user_input_queue.put_nowait("world")
        result = await pop_user_response(timeout=1.0)
        assert result == "world"


# ---------------------------------------------------------------------------
# _heartbeat_loop task lifecycle
# ---------------------------------------------------------------------------


class TestHeartbeatTask:
    @pytest.mark.asyncio
    async def test_start_and_stop(self):
        from server_adapter import start_heartbeat, stop_heartbeat
        import server_adapter as sa

        stop_heartbeat()
        start_heartbeat()
        assert sa._heartbeat_task is not None
        stop_heartbeat()
        assert sa._heartbeat_task is None
