"""Tests for collector.py - event collector."""

import pytest

from collector import EventCollector
from store import EventStore


@pytest.fixture
def store(tmp_path):
    db = tmp_path / "test.db"
    s = EventStore(db, retention_days=0)
    yield s
    s.close()


@pytest.fixture
def collector(store):
    return EventCollector(store)


class TestSessionLifecycle:

    def test_on_session_created(self, collector, store):
        collector.on_session_created("s1", agent="test-agent", model="gpt-4o")
        session = store.get_session("s1")
        assert session is not None
        assert session["agent"] == "test-agent"
        assert session["model"] == "gpt-4o"
        assert collector._current_session_id == "s1"

    def test_on_session_ended(self, collector, store):
        collector.on_session_created("s1")
        collector.on_session_ended("s1")
        session = store.get_session("s1")
        assert session["status"] == "ended"
        assert collector._current_session_id is None
        assert collector._current_turn_id is None

    def test_on_session_ended_resumable(self, collector, store):
        collector.on_session_created("s1")
        collector.on_session_ended("s1", resumable=True)
        session = store.get_session("s1")
        assert session["resumable"] == 1

    def test_on_session_ended_different_session(self, collector, store):
        collector.on_session_created("s1")
        collector.on_session_ended("other")
        # Current session ID should NOT be cleared since it's a different session
        assert collector._current_session_id == "s1"


class TestTurnLifecycle:

    def test_on_turn_start(self, collector, store):
        collector.on_session_created("s1")
        turn_id = collector.on_turn_start("s1", agent="a1", model="m1", user_prompt="hello")
        assert turn_id is not None
        assert collector._current_turn_id == turn_id
        turn = store.get_turn(turn_id)
        assert turn["user_prompt"] == "hello"

    def test_on_turn_end(self, collector, store):
        collector.on_session_created("s1")
        turn_id = collector.on_turn_start("s1", agent="a1", model="gpt-4o")
        collector.on_turn_end(
            turn_id,
            assistant_response="response",
            input_tokens=100,
            output_tokens=50,
            model="gpt-4o",
            status="success",
        )
        turn = store.get_turn(turn_id)
        assert turn["assistant_response"] == "response"
        assert turn["status"] == "success"
        assert collector._current_turn_id is None
        # Session counters should be updated
        session = store.get_session("s1")
        assert session["turn_count"] == 1

    def test_on_turn_end_different_turn(self, collector, store):
        """Ending a turn that isn't the current one shouldn't clear _current_turn_id."""
        collector.on_session_created("s1")
        t1 = collector.on_turn_start("s1")
        t2 = collector.on_turn_start("s1")
        # Current turn is t2
        collector.on_turn_end(t1, model="gpt-4o")
        # t2 should still be current
        assert collector._current_turn_id == t2


class TestUsageUpdate:

    def test_on_usage(self, collector, store):
        collector.on_session_created("s1")
        turn_id = collector.on_turn_start("s1", model="gpt-4o")
        collector.on_usage(
            input_tokens=500, output_tokens=200,
            cache_read_tokens=100, cache_write_tokens=50,
            model="gpt-4o",
        )
        turn = store.get_turn(turn_id)
        assert turn["input_tokens"] == 500
        assert turn["output_tokens"] == 200

    def test_on_usage_no_current_turn(self, collector, store):
        # Should silently return without error
        collector.on_usage(input_tokens=100, output_tokens=50, model="gpt-4o")


class TestToolInvocations:

    def test_on_tool_start(self, collector, store):
        collector.on_session_created("s1")
        turn_id = collector.on_turn_start("s1")
        inv_id = collector.on_tool_start("bing_search", '{"query": "test"}')
        assert inv_id is not None
        inv = store.get_invocation(inv_id)
        assert inv["type"] == "tool_call"
        assert inv["name"] == "bing_search"
        turn = store.get_turn(turn_id)
        assert turn["tool_call_count"] == 1

    def test_on_tool_start_no_turn(self, collector):
        inv_id = collector.on_tool_start("bing_search")
        assert inv_id is None

    def test_on_tool_end(self, collector, store):
        collector.on_session_created("s1")
        collector.on_turn_start("s1")
        inv_id = collector.on_tool_start("test_tool")
        collector.on_tool_end(inv_id, output="result", status="success")
        inv = store.get_invocation(inv_id)
        assert inv["output"] == "result"
        assert inv["status"] == "success"

    def test_on_tool_end_none(self, collector):
        # Should not raise
        collector.on_tool_end(None)


class TestSubagentInvocations:

    def test_on_subagent_start(self, collector, store):
        collector.on_session_created("s1")
        turn_id = collector.on_turn_start("s1")
        inv_id = collector.on_subagent_start("slide-builder-subagent")
        assert inv_id is not None
        inv = store.get_invocation(inv_id)
        assert inv["type"] == "subagent"
        assert inv["name"] == "slide-builder-subagent"
        turn = store.get_turn(turn_id)
        assert turn["subagent_count"] == 1

    def test_on_subagent_start_no_turn(self, collector):
        inv_id = collector.on_subagent_start("test")
        assert inv_id is None

    def test_on_subagent_end(self, collector, store):
        collector.on_session_created("s1")
        collector.on_turn_start("s1")
        inv_id = collector.on_subagent_start("test-agent")
        collector.on_subagent_end(inv_id, status="success")
        inv = store.get_invocation(inv_id)
        assert inv["status"] == "success"

    def test_on_subagent_end_none(self, collector):
        collector.on_subagent_end(None)
