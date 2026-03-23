"""Tests for commands/usage.py and commands/sessions.py."""

import pytest
from io import StringIO

from rich.console import Console

import queries as q
from commands.sessions import handle_sessions
from commands.usage import handle_usage
from store import EventStore


@pytest.fixture
def store(tmp_path):
    db = tmp_path / "test.db"
    s = EventStore(db, retention_days=0)
    yield s
    s.close()


@pytest.fixture
def console():
    return Console(file=StringIO(), force_terminal=True, width=120)


def _populate(store):
    store.start_session("session-001", agent="slide-conductor", model="gpt-4o")
    t1 = store.start_turn(session_id="session-001", agent="slide-conductor", model="gpt-4o", user_prompt="make slides")
    store.end_turn(t1, assistant_response="Done", input_tokens=1000, output_tokens=500, estimated_cost_usd=0.01)
    store.record_invocation(turn_id=t1, session_id="session-001", inv_type="tool_call", name="bing_search")
    store.end_session("session-001", resumable=True)
    store.start_session("session-002", agent="demo-conductor", model="gpt-4o")


class TestHandleSessions:

    def test_list_sessions(self, store, console):
        _populate(store)
        handle_sessions("", store, console, current_session_id="session-002")

    def test_list_sessions_all(self, store, console):
        _populate(store)
        handle_sessions("all", store, console)

    def test_show_session(self, store, console):
        _populate(store)
        handle_sessions("session-001", store, console)

    def test_show_session_not_found(self, store, console):
        handle_sessions("nonexistent", store, console)

    def test_session_turn(self, store, console):
        _populate(store)
        handle_sessions("session-001 turn 1", store, console)

    def test_session_turn_no_number(self, store, console):
        _populate(store)
        handle_sessions("session-001 turn", store, console)

    def test_session_turn_invalid_number(self, store, console):
        _populate(store)
        handle_sessions("session-001 turn abc", store, console)

    def test_session_turn_not_found(self, store, console):
        _populate(store)
        handle_sessions("session-001 turn 99", store, console)

    def test_session_invocations(self, store, console):
        _populate(store)
        handle_sessions("session-001 invocations", store, console)

    def test_session_invocations_empty(self, store, console):
        _populate(store)
        handle_sessions("session-002 invocations", store, console)

    def test_name_session(self, store, console):
        _populate(store)
        handle_sessions("name session-001 my-slides", store, console,
                        current_session_id="session-001")

    def test_cleanup_sessions(self, store, console):
        _populate(store)
        handle_sessions("cleanup", store, console, current_session_id="session-002")

    def test_end_session(self, store, console):
        _populate(store)
        result = handle_sessions("end session-002", store, console,
                                 current_session_id="session-002")
        # If the ended session is the current one, returns a signal
        # Otherwise returns None


class TestHandleUsage:

    def test_session_usage(self, store, console):
        _populate(store)
        handle_usage(
            "", store, console,
            session_id="session-002",
            current_agent="demo-conductor",
            current_model="gpt-4o",
            last_input_tokens=500,
            model_limits={"gpt-4o": 128000},
        )

    def test_session_usage_no_limits(self, store, console):
        _populate(store)
        handle_usage(
            "", store, console,
            session_id="session-002",
            current_agent="demo-conductor",
            current_model="gpt-4o",
        )

    def test_global_usage(self, store, console):
        _populate(store)
        handle_usage("all", store, console)

    def test_global_usage_with_agent_filter(self, store, console):
        _populate(store)
        handle_usage("--agent slide-conductor", store, console)

    def test_global_usage_with_model_filter(self, store, console):
        _populate(store)
        handle_usage("--model gpt-4o", store, console)

    def test_global_usage_with_period(self, store, console):
        _populate(store)
        handle_usage("--period today", store, console)

    def test_global_usage_period_shortcut(self, store, console):
        _populate(store)
        handle_usage("week", store, console)
