"""Additional server_adapter.py tests targeting uncovered event handler lines."""

from __future__ import annotations

import asyncio
import time
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

import server_adapter
from server_adapter import (
    _connections,
    _get_or_create,
    _make_ws_handler,
    install_task_keeping_factory,
    set_collector,
    stop_heartbeat,
    ws_reset,
)


@pytest.fixture(autouse=True)
def _clear_state():
    _connections.clear()
    old_collector = server_adapter._collector
    server_adapter._collector = None
    yield
    _connections.clear()
    server_adapter._collector = old_collector
    stop_heartbeat()


# ---------------------------------------------------------------------------
# Fake SDK event types
# ---------------------------------------------------------------------------


class FakeSessionEventType:
    ASSISTANT_MESSAGE_DELTA = "ASSISTANT_MESSAGE_DELTA"
    ASSISTANT_STREAMING_DELTA = "ASSISTANT_STREAMING_DELTA"
    ASSISTANT_REASONING_DELTA = "ASSISTANT_REASONING_DELTA"
    TOOL_EXECUTION_START = "TOOL_EXECUTION_START"
    TOOL_EXECUTION_COMPLETE = "TOOL_EXECUTION_COMPLETE"
    TOOL_EXECUTION_PARTIAL_RESULT = "TOOL_EXECUTION_PARTIAL_RESULT"
    TOOL_EXECUTION_PROGRESS = "TOOL_EXECUTION_PROGRESS"
    SUBAGENT_STARTED = "SUBAGENT_STARTED"
    SUBAGENT_COMPLETED = "SUBAGENT_COMPLETED"
    SUBAGENT_FAILED = "SUBAGENT_FAILED"
    SUBAGENT_SELECTED = "SUBAGENT_SELECTED"
    SUBAGENT_DESELECTED = "SUBAGENT_DESELECTED"
    ASSISTANT_USAGE = "ASSISTANT_USAGE"
    SESSION_ERROR = "SESSION_ERROR"
    SESSION_COMPACTION_START = "SESSION_COMPACTION_START"
    SESSION_COMPACTION_COMPLETE = "SESSION_COMPACTION_COMPLETE"
    ASSISTANT_TURN_END = "ASSISTANT_TURN_END"


def _make_event(etype, **kwargs):
    return SimpleNamespace(
        type=etype,
        id=str(id(etype)) + str(time.time()),
        data=SimpleNamespace(**kwargs),
    )


def _setup_handler(session_id="test-sid"):
    conn = _get_or_create(session_id)
    handler = _make_ws_handler(session_id)
    return conn, handler


# ---------------------------------------------------------------------------
# Tool lifecycle events
# ---------------------------------------------------------------------------


class TestToolLifecycleHandler:
    def test_tool_start_emits_and_records(self):
        conn, handler = _setup_handler()
        sent = []
        with patch("server_adapter._send", side_effect=lambda p, s: sent.append(p)):
            with patch(
                "copilot.generated.session_events.SessionEventType",
                FakeSessionEventType,
            ):
                handler(
                    _make_event(
                        FakeSessionEventType.TOOL_EXECUTION_START,
                        tool_name="bing_search",
                        arguments={"q": "test"},
                    )
                )

        assert any(m.get("type") == "tool_started" for m in sent)
        assert "bing_search" in conn.tool_starts

    def test_tool_complete_emits(self):
        conn, handler = _setup_handler()
        conn.tool_starts["read_file"] = (time.time(), "corr-1")
        sent = []
        with patch("server_adapter._send", side_effect=lambda p, s: sent.append(p)):
            with patch(
                "copilot.generated.session_events.SessionEventType",
                FakeSessionEventType,
            ):
                handler(
                    _make_event(
                        FakeSessionEventType.TOOL_EXECUTION_COMPLETE,
                        tool_name="read_file",
                        output="content here",
                    )
                )

        assert any(m.get("type") == "tool_completed" for m in sent)

    def test_tool_start_with_collector(self):
        conn, handler = _setup_handler()
        mock_collector = MagicMock()
        mock_collector.on_tool_start.return_value = "inv-123"
        server_adapter._collector = mock_collector

        with patch("server_adapter._send"):
            with patch(
                "copilot.generated.session_events.SessionEventType",
                FakeSessionEventType,
            ):
                handler(
                    _make_event(
                        FakeSessionEventType.TOOL_EXECUTION_START,
                        tool_name="bing_search",
                        arguments=None,
                    )
                )

        mock_collector.on_tool_start.assert_called_once()
        assert conn.pending_invocations.get("bing_search") == "inv-123"

    def test_tool_complete_with_collector(self):
        conn, handler = _setup_handler()
        conn.pending_invocations["bing_search"] = "inv-123"
        mock_collector = MagicMock()
        server_adapter._collector = mock_collector

        with patch("server_adapter._send"):
            with patch(
                "copilot.generated.session_events.SessionEventType",
                FakeSessionEventType,
            ):
                handler(
                    _make_event(
                        FakeSessionEventType.TOOL_EXECUTION_COMPLETE,
                        tool_name="bing_search",
                        output="done",
                    )
                )

        mock_collector.on_tool_end.assert_called_once_with(
            "inv-123", output="done"[:500], status="success"
        )

    def test_tool_start_with_parent_subagent(self):
        conn, handler = _setup_handler()
        conn.active_subagents.append("researcher")
        sent = []
        with patch("server_adapter._send", side_effect=lambda p, s: sent.append(p)):
            with patch(
                "copilot.generated.session_events.SessionEventType",
                FakeSessionEventType,
            ):
                handler(
                    _make_event(
                        FakeSessionEventType.TOOL_EXECUTION_START,
                        tool_name="read_file",
                        arguments=None,
                    )
                )

        tool_msg = next(m for m in sent if m.get("type") == "tool_started")
        assert tool_msg["data"]["_subagent"] == "researcher"

    def test_tool_partial_result(self):
        conn, handler = _setup_handler()
        sent = []
        with patch("server_adapter._send", side_effect=lambda p, s: sent.append(p)):
            with patch(
                "copilot.generated.session_events.SessionEventType",
                FakeSessionEventType,
            ):
                handler(
                    _make_event(
                        FakeSessionEventType.TOOL_EXECUTION_PARTIAL_RESULT,
                        partial_output="partial data",
                    )
                )

        assert any(m.get("type") == "tool_partial_result" for m in sent)

    def test_tool_progress(self):
        conn, handler = _setup_handler()
        sent = []
        with patch("server_adapter._send", side_effect=lambda p, s: sent.append(p)):
            with patch(
                "copilot.generated.session_events.SessionEventType",
                FakeSessionEventType,
            ):
                handler(
                    _make_event(
                        FakeSessionEventType.TOOL_EXECUTION_PROGRESS,
                        progress_message="50% done",
                    )
                )

        assert any(m.get("type") == "tool_progress" for m in sent)


# ---------------------------------------------------------------------------
# Subagent lifecycle events
# ---------------------------------------------------------------------------


class TestSubagentLifecycleHandler:
    def test_subagent_started(self):
        conn, handler = _setup_handler()
        sent = []
        with patch("server_adapter._send", side_effect=lambda p, s: sent.append(p)):
            with patch(
                "copilot.generated.session_events.SessionEventType",
                FakeSessionEventType,
            ):
                handler(
                    _make_event(
                        FakeSessionEventType.SUBAGENT_STARTED,
                        agent_name="researcher",
                    )
                )

        assert any(m.get("type") == "subagent_started" for m in sent)
        assert "researcher" in conn.active_subagents

    def test_subagent_completed(self):
        conn, handler = _setup_handler()
        conn.active_subagents.append("researcher")
        conn.subagent_correlations["researcher"] = "corr-sa"
        sent = []
        with patch("server_adapter._send", side_effect=lambda p, s: sent.append(p)):
            with patch(
                "copilot.generated.session_events.SessionEventType",
                FakeSessionEventType,
            ):
                handler(
                    _make_event(
                        FakeSessionEventType.SUBAGENT_COMPLETED,
                        agent_name="researcher",
                    )
                )

        assert any(m.get("type") == "subagent_completed" for m in sent)
        assert "researcher" not in conn.active_subagents

    def test_subagent_completed_unknown_pops_stack(self):
        conn, handler = _setup_handler()
        conn.active_subagents.append("other-agent")
        sent = []
        with patch("server_adapter._send", side_effect=lambda p, s: sent.append(p)):
            with patch(
                "copilot.generated.session_events.SessionEventType",
                FakeSessionEventType,
            ):
                handler(
                    _make_event(
                        FakeSessionEventType.SUBAGENT_COMPLETED,
                        agent_name="unknown-agent",
                    )
                )

        assert len(conn.active_subagents) == 0

    def test_subagent_failed(self):
        conn, handler = _setup_handler()
        conn.active_subagents.append("researcher")
        conn.subagent_correlations["researcher"] = "corr-f"
        sent = []
        with patch("server_adapter._send", side_effect=lambda p, s: sent.append(p)):
            with patch(
                "copilot.generated.session_events.SessionEventType",
                FakeSessionEventType,
            ):
                handler(
                    _make_event(
                        FakeSessionEventType.SUBAGENT_FAILED,
                        agent_name="researcher",
                        message="out of tokens",
                    )
                )

        assert any(m.get("type") == "subagent_failed" for m in sent)
        failed_msg = next(m for m in sent if m.get("type") == "subagent_failed")
        assert failed_msg["data"]["error"] == "out of tokens"

    def test_subagent_selected(self):
        conn, handler = _setup_handler()
        sent = []
        with patch("server_adapter._send", side_effect=lambda p, s: sent.append(p)):
            with patch(
                "copilot.generated.session_events.SessionEventType",
                FakeSessionEventType,
            ):
                handler(
                    _make_event(
                        FakeSessionEventType.SUBAGENT_SELECTED,
                        agent_name="slide-writer",
                    )
                )

        assert any(m.get("type") == "subagent_selected" for m in sent)

    def test_subagent_deselected(self):
        conn, handler = _setup_handler()
        sent = []
        with patch("server_adapter._send", side_effect=lambda p, s: sent.append(p)):
            with patch(
                "copilot.generated.session_events.SessionEventType",
                FakeSessionEventType,
            ):
                handler(
                    _make_event(
                        FakeSessionEventType.SUBAGENT_DESELECTED,
                        agent_name="slide-writer",
                    )
                )

        assert any(m.get("type") == "subagent_deselected" for m in sent)

    def test_subagent_started_with_collector(self):
        conn, handler = _setup_handler()
        mock_collector = MagicMock()
        mock_collector.on_subagent_start.return_value = "inv-sa-1"
        server_adapter._collector = mock_collector

        with patch("server_adapter._send"):
            with patch(
                "copilot.generated.session_events.SessionEventType",
                FakeSessionEventType,
            ):
                handler(
                    _make_event(
                        FakeSessionEventType.SUBAGENT_STARTED,
                        agent_name="researcher",
                    )
                )

        mock_collector.on_subagent_start.assert_called_once()
        assert conn.pending_invocations.get("subagent:researcher") == "inv-sa-1"

    def test_subagent_completed_with_collector(self):
        conn, handler = _setup_handler()
        conn.pending_invocations["subagent:researcher"] = "inv-sa-1"
        mock_collector = MagicMock()
        server_adapter._collector = mock_collector

        with patch("server_adapter._send"):
            with patch(
                "copilot.generated.session_events.SessionEventType",
                FakeSessionEventType,
            ):
                handler(
                    _make_event(
                        FakeSessionEventType.SUBAGENT_COMPLETED,
                        agent_name="researcher",
                    )
                )

        mock_collector.on_subagent_end.assert_called_once_with(
            "inv-sa-1", status="success"
        )

    def test_subagent_failed_with_collector(self):
        conn, handler = _setup_handler()
        conn.pending_invocations["subagent:researcher"] = "inv-sa-2"
        mock_collector = MagicMock()
        server_adapter._collector = mock_collector

        with patch("server_adapter._send"):
            with patch(
                "copilot.generated.session_events.SessionEventType",
                FakeSessionEventType,
            ):
                handler(
                    _make_event(
                        FakeSessionEventType.SUBAGENT_FAILED,
                        agent_name="researcher",
                        message="error msg",
                    )
                )

        mock_collector.on_subagent_end.assert_called_once()
        call_kwargs = mock_collector.on_subagent_end.call_args
        assert call_kwargs[1]["status"] == "error"


# ---------------------------------------------------------------------------
# Other event types
# ---------------------------------------------------------------------------


class TestOtherEventTypes:
    def test_reasoning_delta(self):
        conn, handler = _setup_handler()
        sent = []
        with patch("server_adapter._send", side_effect=lambda p, s: sent.append(p)):
            with patch(
                "copilot.generated.session_events.SessionEventType",
                FakeSessionEventType,
            ):
                handler(
                    _make_event(
                        FakeSessionEventType.ASSISTANT_REASONING_DELTA,
                        delta_content="thinking...",
                    )
                )

        assert any(m.get("type") == "reasoning_delta" for m in sent)

    def test_streaming_delta_deduplicates(self):
        conn, handler = _setup_handler()
        sent = []
        event = _make_event(
            FakeSessionEventType.ASSISTANT_MESSAGE_DELTA,
            delta_content="hello",
        )
        with patch("server_adapter._send", side_effect=lambda p, s: sent.append(p)):
            with patch(
                "copilot.generated.session_events.SessionEventType",
                FakeSessionEventType,
            ):
                handler(event)
                handler(event)  # duplicate

        delta_msgs = [m for m in sent if m.get("type") == "delta"]
        assert len(delta_msgs) == 1
        assert conn.response_buffer == ["hello"]

    def test_usage_event(self):
        conn, handler = _setup_handler()
        sent = []
        with patch("server_adapter._send", side_effect=lambda p, s: sent.append(p)):
            with patch(
                "copilot.generated.session_events.SessionEventType",
                FakeSessionEventType,
            ):
                handler(
                    _make_event(
                        FakeSessionEventType.ASSISTANT_USAGE,
                        input_tokens=100,
                        output_tokens=50,
                        cache_read_tokens=10,
                        cache_write_tokens=5,
                        model="gpt-4o",
                    )
                )

        usage_msg = next(m for m in sent if m.get("type") == "usage")
        assert usage_msg["data"]["input_tokens"] == 100
        assert usage_msg["data"]["output_tokens"] == 50

    def test_usage_event_with_collector(self):
        conn, handler = _setup_handler()
        mock_collector = MagicMock()
        server_adapter._collector = mock_collector

        with patch("server_adapter._send"):
            with patch(
                "copilot.generated.session_events.SessionEventType",
                FakeSessionEventType,
            ):
                handler(
                    _make_event(
                        FakeSessionEventType.ASSISTANT_USAGE,
                        input_tokens=100,
                        output_tokens=50,
                        cache_read_tokens=0,
                        cache_write_tokens=0,
                        model="gpt-4o",
                    )
                )

        mock_collector.on_usage.assert_called_once()

    def test_session_error(self):
        conn, handler = _setup_handler()
        sent = []
        with patch("server_adapter._send", side_effect=lambda p, s: sent.append(p)):
            with patch(
                "copilot.generated.session_events.SessionEventType",
                FakeSessionEventType,
            ):
                handler(
                    _make_event(
                        FakeSessionEventType.SESSION_ERROR,
                        message="something broke",
                    )
                )

        assert any(m.get("type") == "error" for m in sent)

    def test_compaction_start(self):
        conn, handler = _setup_handler()
        sent = []
        with patch("server_adapter._send", side_effect=lambda p, s: sent.append(p)):
            with patch(
                "copilot.generated.session_events.SessionEventType",
                FakeSessionEventType,
            ):
                handler(_make_event(FakeSessionEventType.SESSION_COMPACTION_START))

        assert any(m.get("type") == "compaction_start" for m in sent)

    def test_compaction_complete(self):
        conn, handler = _setup_handler()
        sent = []
        with patch("server_adapter._send", side_effect=lambda p, s: sent.append(p)):
            with patch(
                "copilot.generated.session_events.SessionEventType",
                FakeSessionEventType,
            ):
                handler(
                    _make_event(
                        FakeSessionEventType.SESSION_COMPACTION_COMPLETE,
                        post_compaction_tokens=5000,
                    )
                )

        msg = next(m for m in sent if m.get("type") == "compaction_complete")
        assert msg["data"]["post_tokens"] == 5000

    def test_turn_ended(self):
        conn, handler = _setup_handler()
        sent = []
        with patch("server_adapter._send", side_effect=lambda p, s: sent.append(p)):
            with patch(
                "copilot.generated.session_events.SessionEventType",
                FakeSessionEventType,
            ):
                handler(_make_event(FakeSessionEventType.ASSISTANT_TURN_END))

        assert any(m.get("type") == "turn_ended" for m in sent)


# ---------------------------------------------------------------------------
# install_task_keeping_factory
# ---------------------------------------------------------------------------


class TestTaskKeepingFactory:
    def test_install_idempotent(self):
        old = server_adapter._task_factory_installed
        server_adapter._task_factory_installed = False
        try:
            loop = asyncio.new_event_loop()
            install_task_keeping_factory(loop)
            assert server_adapter._task_factory_installed is True
            # Second call is no-op
            install_task_keeping_factory(loop)
            loop.close()
        finally:
            server_adapter._task_factory_installed = old


# ---------------------------------------------------------------------------
# set_collector
# ---------------------------------------------------------------------------


class TestSetCollector:
    def test_sets_module_global(self):
        mock = MagicMock()
        set_collector(mock)
        assert server_adapter._collector is mock
        server_adapter._collector = None


# ---------------------------------------------------------------------------
# ws_reset legacy path
# ---------------------------------------------------------------------------


class TestWsResetLegacy:
    def test_reset_without_session_id(self):
        server_adapter._seen_event_ids.add("old")
        server_adapter._pending_tool_starts["t"] = 1.0
        server_adapter._cancel_flag = True

        ws_reset(session_id=None)

        assert len(server_adapter._seen_event_ids) == 0
        assert len(server_adapter._pending_tool_starts) == 0
        assert server_adapter._cancel_flag is False
