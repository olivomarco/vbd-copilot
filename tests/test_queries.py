"""Tests for queries.py - shared query and aggregation logic."""

import pytest

from queries import (
    _period_cutoff,
    get_invocation_detail,
    get_resumable_sessions,
    get_session_detail,
    get_session_invocations,
    get_turn_detail,
    list_sessions,
    usage_by_agent,
    usage_by_model,
    usage_summary,
)
from store import EventStore


@pytest.fixture
def store(tmp_path):
    db = tmp_path / "test.db"
    s = EventStore(db, retention_days=0)
    yield s
    s.close()


def _populate_store(store):
    """Add sample data to the store."""
    store.start_session("s1", agent="slide-conductor", model="gpt-4o")
    t1 = store.start_turn(session_id="s1", agent="slide-conductor", model="gpt-4o", user_prompt="make slides")
    store.end_turn(t1, assistant_response="here are your slides", input_tokens=1000, output_tokens=500, estimated_cost_usd=0.01)
    store.record_invocation(turn_id=t1, session_id="s1", inv_type="tool_call", name="bing_search")

    store.start_session("s2", agent="demo-conductor", model="claude-sonnet-4.6")
    t2 = store.start_turn(session_id="s2", agent="demo-conductor", model="claude-sonnet-4.6", user_prompt="make demos")
    store.end_turn(t2, assistant_response="here are demos", input_tokens=2000, output_tokens=800, estimated_cost_usd=0.05)


class TestPeriodCutoff:

    def test_none_period(self):
        assert _period_cutoff(None) is None

    def test_all_period(self):
        assert _period_cutoff("all") is None

    def test_today_period(self):
        result = _period_cutoff("today")
        assert result is not None
        assert "T" in result  # ISO format

    def test_week_period(self):
        result = _period_cutoff("week")
        assert result is not None

    def test_month_period(self):
        result = _period_cutoff("month")
        assert result is not None

    def test_unknown_period(self):
        assert _period_cutoff("century") is None


class TestListSessions:

    def test_list_sessions(self, store):
        _populate_store(store)
        sessions = list_sessions(store)
        assert len(sessions) == 2

    def test_list_sessions_filter_agent(self, store):
        _populate_store(store)
        sessions = list_sessions(store, agent="slide-conductor")
        assert len(sessions) == 1
        assert sessions[0]["agent"] == "slide-conductor"

    def test_list_sessions_empty(self, store):
        sessions = list_sessions(store)
        assert sessions == []


class TestGetSessionDetail:

    def test_get_session_detail(self, store):
        _populate_store(store)
        detail = get_session_detail(store, "s1")
        assert detail is not None
        assert detail["id"] == "s1"
        assert "turns" in detail
        assert len(detail["turns"]) == 1
        # Check response preview
        assert "response_preview" in detail["turns"][0]

    def test_get_session_detail_not_found(self, store):
        assert get_session_detail(store, "nonexistent") is None

    def test_response_preview_truncation(self, store):
        store.start_session("s1")
        tid = store.start_turn(session_id="s1")
        store.end_turn(tid, assistant_response="x" * 300)
        detail = get_session_detail(store, "s1")
        preview = detail["turns"][0]["response_preview"]
        assert preview.endswith("...")
        assert len(preview) == 203  # 200 chars + "..."


class TestGetTurnDetail:

    def test_get_turn_detail(self, store):
        _populate_store(store)
        turns = store.get_turns("s1")
        detail = get_turn_detail(store, turns[0]["id"])
        assert detail is not None
        assert "invocations" in detail

    def test_get_turn_detail_not_found(self, store):
        assert get_turn_detail(store, "nonexistent") is None


class TestGetSessionInvocations:

    def test_invocations(self, store):
        _populate_store(store)
        invs = get_session_invocations(store, "s1")
        assert len(invs) == 1
        assert invs[0]["name"] == "bing_search"


class TestGetInvocationDetail:

    def test_invocation_detail(self, store):
        _populate_store(store)
        invs = get_session_invocations(store, "s1")
        detail = get_invocation_detail(store, invs[0]["id"])
        assert detail is not None
        assert detail["name"] == "bing_search"

    def test_invocation_detail_not_found(self, store):
        assert get_invocation_detail(store, "nonexistent") is None


class TestGetResumableSessions:

    def test_resumable_sessions(self, store):
        store.start_session("s1")
        store.end_session("s1", resumable=True)
        store.start_session("s2")
        store.end_session("s2", resumable=False)
        resumable = get_resumable_sessions(store)
        assert len(resumable) == 1
        assert resumable[0]["id"] == "s1"


class TestUsageSummary:

    def test_usage_summary(self, store):
        _populate_store(store)
        usage = usage_summary(store)
        assert usage["total_input_tokens"] == 3000
        assert usage["total_output_tokens"] == 1300
        assert usage["turn_count"] == 2
        assert "by_agent" in usage
        assert "by_model" in usage

    def test_usage_summary_filter_agent(self, store):
        _populate_store(store)
        usage = usage_summary(store, agent="slide-conductor")
        assert usage["turn_count"] == 1

    def test_usage_summary_filter_model(self, store):
        _populate_store(store)
        usage = usage_summary(store, model="gpt-4o")
        assert usage["turn_count"] == 1

    def test_usage_summary_with_period(self, store):
        _populate_store(store)
        usage = usage_summary(store, period="today")
        # All data was just created, so it should all be within today
        assert usage["turn_count"] == 2

    def test_usage_summary_empty(self, store):
        usage = usage_summary(store)
        assert usage["total_input_tokens"] == 0
        assert usage["turn_count"] == 0


class TestUsageByAgent:

    def test_by_agent(self, store):
        _populate_store(store)
        result = usage_by_agent(store)
        assert len(result) == 2
        agents = {r["agent"] for r in result}
        assert "slide-conductor" in agents
        assert "demo-conductor" in agents


class TestUsageByModel:

    def test_by_model(self, store):
        _populate_store(store)
        result = usage_by_model(store)
        assert len(result) == 2
        models = {r["model"] for r in result}
        assert "gpt-4o" in models
        assert "claude-sonnet-4.6" in models
