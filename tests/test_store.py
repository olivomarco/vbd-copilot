"""Tests for store.py - SQLite event store."""

import pytest
from pathlib import Path
from store import EventStore


@pytest.fixture
def store(tmp_path):
    """Create a fresh EventStore with an in-tmp-dir database."""
    db_path = tmp_path / "test.db"
    s = EventStore(db_path, retention_days=0)
    yield s
    s.close()


class TestSessionLifecycle:

    def test_start_and_get_session(self, store):
        store.start_session("s1", agent="slide-conductor", model="gpt-4o")
        session = store.get_session("s1")
        assert session is not None
        assert session["id"] == "s1"
        assert session["agent"] == "slide-conductor"
        assert session["model"] == "gpt-4o"
        assert session["status"] == "active"

    def test_end_session(self, store):
        store.start_session("s1")
        store.end_session("s1")
        session = store.get_session("s1")
        assert session["status"] == "ended"
        assert session["ended_at"] is not None

    def test_end_session_resumable(self, store):
        store.start_session("s1")
        store.end_session("s1", resumable=True)
        session = store.get_session("s1")
        assert session["status"] == "ended"
        assert session["resumable"] == 1

    def test_reactivate_session(self, store):
        store.start_session("s1")
        store.end_session("s1")
        store.reactivate_session("s1")
        session = store.get_session("s1")
        assert session["status"] == "active"
        assert session["ended_at"] is None
        assert session["resumable"] == 0

    def test_end_all_active_except(self, store):
        store.start_session("s1")
        store.start_session("s2")
        store.start_session("s3")
        count = store.end_all_active_except("s1")
        assert count == 2
        assert store.get_session("s1")["status"] == "active"
        assert store.get_session("s2")["status"] == "ended"
        assert store.get_session("s3")["status"] == "ended"

    def test_end_all_active_except_none(self, store):
        store.start_session("s1")
        store.start_session("s2")
        count = store.end_all_active_except(None)
        assert count == 2

    def test_get_missing_session(self, store):
        assert store.get_session("nonexistent") is None

    def test_list_sessions(self, store):
        store.start_session("s1", agent="a1")
        store.start_session("s2", agent="a2")
        sessions = store.list_sessions()
        assert len(sessions) == 2

    def test_list_sessions_filter_agent(self, store):
        store.start_session("s1", agent="a1")
        store.start_session("s2", agent="a2")
        sessions = store.list_sessions(agent="a1")
        assert len(sessions) == 1
        assert sessions[0]["agent"] == "a1"

    def test_list_sessions_filter_status(self, store):
        store.start_session("s1")
        store.start_session("s2")
        store.end_session("s2")
        active = store.list_sessions(status="active")
        assert len(active) == 1
        assert active[0]["id"] == "s1"

    def test_list_sessions_limit(self, store):
        for i in range(5):
            store.start_session(f"s{i}")
        sessions = store.list_sessions(limit=3)
        assert len(sessions) == 3

    def test_update_session_counters(self, store):
        store.start_session("s1")
        store.update_session_counters("s1", turn_count_delta=1, input_tokens_delta=100, output_tokens_delta=50)
        session = store.get_session("s1")
        assert session["turn_count"] == 1
        assert session["total_input_tokens"] == 100
        assert session["total_output_tokens"] == 50

        store.update_session_counters("s1", turn_count_delta=1, input_tokens_delta=200, output_tokens_delta=100)
        session = store.get_session("s1")
        assert session["turn_count"] == 2
        assert session["total_input_tokens"] == 300
        assert session["total_output_tokens"] == 150

    def test_update_session_model(self, store):
        store.start_session("s1", model="gpt-4o")
        store.update_session_model("s1", "claude-sonnet-4.6")
        session = store.get_session("s1")
        assert session["model"] == "claude-sonnet-4.6"

    def test_update_session_agent(self, store):
        store.start_session("s1", agent="old")
        store.update_session_agent("s1", "new")
        session = store.get_session("s1")
        assert session["agent"] == "new"


class TestNickname:

    def test_set_and_get_nickname(self, store):
        store.start_session("s1")
        store.set_nickname("s1", "my-session")
        session = store.get_session("s1")
        assert session["nickname"] == "my-session"

    def test_clear_nickname(self, store):
        store.start_session("s1")
        store.set_nickname("s1", "my-session")
        store.set_nickname("s1", None)
        session = store.get_session("s1")
        assert session["nickname"] is None

    def test_nickname_validation_empty(self, store):
        store.start_session("s1")
        # Empty string should become None
        store.set_nickname("s1", "  ")
        session = store.get_session("s1")
        assert session["nickname"] is None

    def test_nickname_validation_invalid_chars(self, store):
        store.start_session("s1")
        with pytest.raises(ValueError):
            store.set_nickname("s1", "has spaces!")

    def test_nickname_validation_too_long(self, store):
        store.start_session("s1")
        with pytest.raises(ValueError):
            store.set_nickname("s1", "a" * 31)

    def test_nickname_validation_starts_with_hyphen(self, store):
        store.start_session("s1")
        with pytest.raises(ValueError):
            store.set_nickname("s1", "-invalid")

    def test_nickname_duplicate(self, store):
        store.start_session("s1")
        store.start_session("s2")
        store.set_nickname("s1", "taken")
        with pytest.raises(ValueError, match="already used"):
            store.set_nickname("s2", "taken")


class TestResolvePrefix:

    def test_exact_match(self, store):
        store.start_session("abc123def456")
        assert store.resolve_prefix("sessions", "abc123def456") == "abc123def456"

    def test_prefix_match(self, store):
        store.start_session("abc123def456")
        assert store.resolve_prefix("sessions", "abc123") == "abc123def456"

    def test_ambiguous_prefix(self, store):
        store.start_session("abc123xxx")
        store.start_session("abc123yyy")
        assert store.resolve_prefix("sessions", "abc123") is None

    def test_no_match(self, store):
        assert store.resolve_prefix("sessions", "zzz") is None

    def test_invalid_table(self, store):
        assert store.resolve_prefix("unknown_table", "abc") is None

    def test_nickname_match(self, store):
        store.start_session("abc123")
        store.set_nickname("abc123", "mytest")
        assert store.resolve_prefix("sessions", "mytest") == "abc123"


class TestTurnLifecycle:

    def test_start_and_get_turn(self, store):
        store.start_session("s1")
        turn_id = store.start_turn(session_id="s1", agent="a1", model="m1", user_prompt="hello")
        turn = store.get_turn(turn_id)
        assert turn is not None
        assert turn["session_id"] == "s1"
        assert turn["agent"] == "a1"
        assert turn["user_prompt"] == "hello"
        assert turn["turn_number"] == 1

    def test_turn_numbering(self, store):
        store.start_session("s1")
        t1 = store.start_turn(session_id="s1")
        t2 = store.start_turn(session_id="s1")
        assert store.get_turn(t1)["turn_number"] == 1
        assert store.get_turn(t2)["turn_number"] == 2

    def test_end_turn(self, store):
        store.start_session("s1")
        turn_id = store.start_turn(session_id="s1")
        store.end_turn(
            turn_id,
            assistant_response="hi there",
            input_tokens=100,
            output_tokens=50,
            status="success",
        )
        turn = store.get_turn(turn_id)
        assert turn["assistant_response"] == "hi there"
        assert turn["input_tokens"] == 100
        assert turn["output_tokens"] == 50
        assert turn["status"] == "success"
        assert turn["ended_at"] is not None
        assert turn["duration_ms"] >= 0

    def test_get_turns(self, store):
        store.start_session("s1")
        store.start_turn(session_id="s1")
        store.start_turn(session_id="s1")
        turns = store.get_turns("s1")
        assert len(turns) == 2
        assert turns[0]["turn_number"] < turns[1]["turn_number"]

    def test_increment_turn_tool_count(self, store):
        store.start_session("s1")
        tid = store.start_turn(session_id="s1")
        store.increment_turn_tool_count(tid)
        store.increment_turn_tool_count(tid)
        turn = store.get_turn(tid)
        assert turn["tool_call_count"] == 2

    def test_increment_turn_subagent_count(self, store):
        store.start_session("s1")
        tid = store.start_turn(session_id="s1")
        store.increment_turn_subagent_count(tid)
        turn = store.get_turn(tid)
        assert turn["subagent_count"] == 1

    def test_get_missing_turn(self, store):
        assert store.get_turn("nonexistent") is None


class TestInvocations:

    def test_record_and_get_invocation(self, store):
        store.start_session("s1")
        tid = store.start_turn(session_id="s1")
        inv_id = store.record_invocation(
            turn_id=tid, session_id="s1", inv_type="tool_call", name="bing_search",
            input_data='{"query": "test"}'
        )
        inv = store.get_invocation(inv_id)
        assert inv is not None
        assert inv["type"] == "tool_call"
        assert inv["name"] == "bing_search"

    def test_complete_invocation(self, store):
        store.start_session("s1")
        tid = store.start_turn(session_id="s1")
        inv_id = store.record_invocation(
            turn_id=tid, session_id="s1", inv_type="tool_call", name="test"
        )
        store.complete_invocation(inv_id, output="result", status="success")
        inv = store.get_invocation(inv_id)
        assert inv["output"] == "result"
        assert inv["status"] == "success"
        assert inv["ended_at"] is not None
        assert inv["duration_ms"] >= 0

    def test_complete_invocation_error(self, store):
        store.start_session("s1")
        tid = store.start_turn(session_id="s1")
        inv_id = store.record_invocation(
            turn_id=tid, session_id="s1", inv_type="tool_call", name="test"
        )
        store.complete_invocation(inv_id, status="error", error_message="boom")
        inv = store.get_invocation(inv_id)
        assert inv["status"] == "error"
        assert inv["error_message"] == "boom"

    def test_get_invocations_for_turn(self, store):
        store.start_session("s1")
        tid = store.start_turn(session_id="s1")
        store.record_invocation(turn_id=tid, session_id="s1", inv_type="tool_call", name="t1")
        store.record_invocation(turn_id=tid, session_id="s1", inv_type="tool_call", name="t2")
        invs = store.get_invocations_for_turn(tid)
        assert len(invs) == 2

    def test_get_invocations_for_session(self, store):
        store.start_session("s1")
        t1 = store.start_turn(session_id="s1")
        t2 = store.start_turn(session_id="s1")
        store.record_invocation(turn_id=t1, session_id="s1", inv_type="tool_call", name="a")
        store.record_invocation(turn_id=t2, session_id="s1", inv_type="subagent", name="b")
        invs = store.get_invocations_for_session("s1")
        assert len(invs) == 2

    def test_get_missing_invocation(self, store):
        assert store.get_invocation("nonexistent") is None


class TestCleanup:

    def test_cleanup_old_keeps_recent(self, store):
        store.start_session("s1")
        store.start_turn(session_id="s1")
        # Retention of 1 day should keep data we just created
        store.cleanup_old(retention_days=1)
        assert store.get_session("s1") is not None

    def test_cleanup_old_removes_old(self, store):
        store.start_session("s1")
        # retention_days=0 means cutoff is now, so everything is old
        store.cleanup_old(retention_days=0)
        assert store.get_session("s1") is None


class TestSchemaIdempotency:

    def test_reopen_database(self, tmp_path):
        """Schema creation should be idempotent."""
        db = tmp_path / "test.db"
        s1 = EventStore(db, retention_days=0)
        s1.start_session("s1")
        s1.close()
        s2 = EventStore(db, retention_days=0)
        assert s2.get_session("s1") is not None
        s2.close()
