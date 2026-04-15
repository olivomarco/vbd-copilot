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
        # seen_event_ids is preserved (pruned only when >5000)
        assert len(conn.seen_event_ids) == 1
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
        env = sa._envelope(
            None, "tool_started", {"tool": "t"}, correlation_id="corr-abc"
        )
        assert env["correlationId"] == "corr-abc"


class TestBuildSnapshot:
    def test_nonexistent_session(self):
        assert sa.build_snapshot("nonexistent") is None

    def test_idle_session(self):
        sa._get_or_create("snap-1")
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
        # Connection is preserved — only destroy_connection removes it.
        assert sa.get_connection("s2") is not None

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
        # seen_event_ids is preserved (pruned only when >5000)
        assert len(conn.seen_event_ids) == 1
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
        result = loop.run_until_complete(
            sa.pop_user_response(timeout=1.0, session_id="s7")
        )
        loop.close()
        assert result == "hello"

    def test_has_event_handler_false(self):
        assert sa.has_event_handler("no-such") is False

    def test_get_connection_returns_none(self):
        assert sa.get_connection("nonexistent") is None


class TestConcurrentConnectionPreservation:
    """Tests for the watcher→workspace WS handoff fix.

    When a _user_input callback is waiting (ask_user_lock held) or
    pending_input is set, the SessionConnection must NOT be destroyed
    when all WebSockets disconnect.  This preserves the input_queue so
    the callback can receive the user's answer from the reconnecting WS.
    """

    def test_remove_ws_preserves_connection_when_lock_held(self):
        """Connection survives WS disconnect when ask_user_lock is held."""
        loop = asyncio.new_event_loop()
        try:
            sa.add_ws("locked-1", "ws-watcher")
            conn = sa.get_connection("locked-1")

            # Simulate a _user_input callback holding the lock
            loop.run_until_complete(conn.ask_user_lock.acquire())
            try:
                sa.remove_ws("locked-1", "ws-watcher")
                # Connection must still exist
                assert sa.get_connection("locked-1") is conn
            finally:
                conn.ask_user_lock.release()
        finally:
            loop.close()

    def test_remove_ws_preserves_connection_when_pending_input(self):
        """Connection survives WS disconnect when pending_input is set."""
        sa.add_ws("pending-1", "ws-watcher")
        conn = sa.get_connection("pending-1")
        conn.pending_input = {"question": "What topic?"}

        sa.remove_ws("pending-1", "ws-watcher")
        # Connection must still exist
        assert sa.get_connection("pending-1") is conn
        assert conn.pending_input == {"question": "What topic?"}

    def test_remove_ws_cleans_up_when_idle(self):
        """Connection is preserved even when idle — handler must stay registered."""
        sa.add_ws("idle-1", "ws-watcher")
        assert sa.get_connection("idle-1") is not None

        sa.remove_ws("idle-1", "ws-watcher")
        # Connection preserved (no websockets, but handler stays active)
        assert sa.get_connection("idle-1") is not None

    def test_new_ws_reuses_preserved_connection(self):
        """A new WS joining a preserved connection shares the same queue."""
        sa.add_ws("reuse-1", "ws-watcher")
        conn = sa.get_connection("reuse-1")
        conn.pending_input = {"question": "Pick a topic"}

        # Watcher disconnects — connection preserved
        sa.remove_ws("reuse-1", "ws-watcher")
        assert sa.get_connection("reuse-1") is conn

        # Workspace WS connects — joins the SAME connection
        is_first = sa.add_ws("reuse-1", "ws-workspace")
        assert is_first is True  # first WS in the set (watcher was removed)
        assert sa.get_connection("reuse-1") is conn
        assert "ws-workspace" in conn.websockets

    def test_push_response_reaches_preserved_queue(self):
        """User response pushed to a preserved connection reaches the waiting pop."""
        loop = asyncio.new_event_loop()
        try:
            sa.add_ws("queue-1", "ws-watcher")
            conn = sa.get_connection("queue-1")
            loop.run_until_complete(conn.ask_user_lock.acquire())

            # Watcher disconnects — connection preserved
            sa.remove_ws("queue-1", "ws-watcher")
            assert sa.get_connection("queue-1") is conn

            # Workspace connects
            sa.add_ws("queue-1", "ws-workspace")
            # Same connection, same queue
            assert sa.get_connection("queue-1") is conn

            # User pushes response
            sa.push_user_response("My answer", "queue-1")

            # The pop should find the response on the same queue
            result = loop.run_until_complete(
                sa.pop_user_response(timeout=1.0, session_id="queue-1")
            )
            assert result == "My answer"
            conn.ask_user_lock.release()
        finally:
            loop.close()

    def test_reset_turn_preserves_queue_when_lock_held(self):
        """reset_turn does NOT drain the input_queue when ask_user_lock is held."""
        loop = asyncio.new_event_loop()
        try:
            conn = sa.SessionConnection("rt-1")
            conn.input_queue.put_nowait("pending-answer")
            loop.run_until_complete(conn.ask_user_lock.acquire())
            try:
                conn.reset_turn()
                # Queue must NOT be drained
                assert not conn.input_queue.empty()
                assert conn.input_queue.get_nowait() == "pending-answer"
            finally:
                conn.ask_user_lock.release()
        finally:
            loop.close()

    def test_reset_turn_drains_queue_when_unlocked(self):
        """reset_turn DOES drain the input_queue when ask_user_lock is NOT held."""
        conn = sa.SessionConnection("rt-2")
        conn.input_queue.put_nowait("stale-answer")
        conn.reset_turn()
        assert conn.input_queue.empty()
