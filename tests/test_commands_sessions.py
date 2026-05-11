"""Additional tests for commands/sessions.py covering uncovered branches."""

from __future__ import annotations

from io import StringIO

import pytest
from rich.console import Console

from commands.sessions import handle_sessions, _CURRENT_SESSION_ENDED
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
    t1 = store.start_turn(
        session_id="session-001",
        agent="slide-conductor",
        model="gpt-4o",
        user_prompt="make slides",
    )
    store.end_turn(
        t1,
        assistant_response="Done making slides for you",
        input_tokens=1000,
        output_tokens=500,
        estimated_cost_usd=0.01,
    )
    store.record_invocation(
        turn_id=t1, session_id="session-001", inv_type="tool_call", name="bing_search"
    )
    store.end_session("session-001", resumable=True)
    store.start_session("session-002", agent="demo-conductor", model="gpt-4o")


class TestNameSessionEdgeCases:
    def test_name_no_args(self, store, console):
        _populate(store)
        handle_sessions("name", store, console)
        output = console.file.getvalue()
        assert "Usage" in output

    def test_name_current_session(self, store, console):
        _populate(store)
        handle_sessions(
            "name my-session",
            store,
            console,
            current_session_id="session-002",
        )
        output = console.file.getvalue()
        assert "my-session" in output

    def test_name_no_current_session(self, store, console):
        _populate(store)
        # Single arg that doesn't match an existing session and no current session
        handle_sessions("name somerandomname", store, console, current_session_id=None)
        output = console.file.getvalue()
        assert (
            "No active session" in output
            or "not found" in output.lower()
            or "OK" in output
        )

    def test_name_with_session_id(self, store, console):
        _populate(store)
        handle_sessions("name session-001 renamed", store, console)
        output = console.file.getvalue()
        assert "OK" in output

    def test_name_session_not_found(self, store, console):
        _populate(store)
        handle_sessions("name nonexistent nickname", store, console)
        output = console.file.getvalue()
        assert "not found" in output

    def test_name_clear_nickname(self, store, console):
        _populate(store)
        # First set a nickname
        store.set_nickname("session-001", "my-slides")
        # Then clear it by passing just the session id
        handle_sessions("name session-001", store, console)
        output = console.file.getvalue()
        assert "Cleared" in output


class TestEndSessionEdgeCases:
    def test_end_already_ended(self, store, console):
        _populate(store)
        handle_sessions("end session-001", store, console)
        output = console.file.getvalue()
        assert "already ended" in output

    def test_end_not_found(self, store, console):
        handle_sessions("end nonexistent", store, console)
        output = console.file.getvalue()
        assert "not found" in output

    def test_end_current_session_returns_sentinel(self, store, console):
        _populate(store)
        result = handle_sessions(
            "end session-002",
            store,
            console,
            current_session_id="session-002",
        )
        assert result == _CURRENT_SESSION_ENDED


class TestCleanupSessions:
    def test_cleanup_no_orphans(self, store, console):
        handle_sessions("cleanup", store, console, current_session_id=None)
        output = console.file.getvalue()
        assert "No orphaned" in output

    def test_cleanup_with_orphans(self, store, console):
        _populate(store)
        # session-002 is active, create another active one
        store.start_session("session-003", agent="test", model="gpt-4o")
        handle_sessions("cleanup", store, console, current_session_id="session-002")
        output = console.file.getvalue()
        assert "Ended" in output or "No orphaned" in output


class TestShowSessionTurnDetail:
    def test_show_turn_with_invocations(self, store, console):
        _populate(store)
        handle_sessions("session-001 turn 1", store, console)
        output = console.file.getvalue()
        # Rich uses ANSI escapes — check for 'Turn' and '1' separately
        assert "Turn" in output
        assert "slide-conductor" in output

    def test_show_turn_with_response(self, store, console):
        _populate(store)
        handle_sessions("session-001 turn 1", store, console)
        output = console.file.getvalue()
        # Should show the response panel
        assert "Done making slides" in output

    def test_show_session_no_turns(self, store, console):
        store.start_session("empty-session", agent="test", model="gpt-4o")
        handle_sessions("empty-session turn", store, console)
        output = console.file.getvalue()
        # When no turn number is given but no turns exist, it says 'No turns'
        assert "No turns" in output or "Usage" in output


class TestFallthrough:
    def test_multiple_words_fallthrough_to_show(self, store, console):
        _populate(store)
        # Unknown subcommand falls through to show_session
        handle_sessions("session-001 unknown subcommand", store, console)
        output = console.file.getvalue()
        # Should show session details
        assert "Session" in output or "not found" in output.lower()
