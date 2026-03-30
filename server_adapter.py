"""WebSocket adapter that bridges CopilotUI events to JSON messages.

``WebSocketEventAdapter`` is a plain event sink (not a subclass of CopilotUI)
that receives the same ``session.on(handler)`` callback events and serialises
them as newline-delimited JSON over an active WebSocket connection.

The existing ``CopilotUI`` + ``EventCollector`` → SQLite pipeline is never
touched; this adapter is wired in *addition* to it via a second ``session.on``
subscriber so that no terminal-side code breaks.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Shared state for the current WS connection (one active WS at a time).
# server.py replaces this reference when a new /ws/{session_id} connects.
# ---------------------------------------------------------------------------

_active_ws: Any | None = None  # starlette WebSocket
_cancel_flag: bool = False
_user_input_queue: asyncio.Queue[str] = asyncio.Queue()


def set_active_ws(ws: Any | None) -> None:
    global _active_ws
    _active_ws = ws


def get_active_ws() -> Any | None:
    return _active_ws


def set_cancel_flag(value: bool) -> None:
    global _cancel_flag
    _cancel_flag = value


def get_cancel_flag() -> bool:
    return _cancel_flag


def push_user_response(content: str) -> None:
    """Push a user response for the current waiting_for_input prompt."""
    _user_input_queue.put_nowait(content)


async def pop_user_response(timeout: float = 300.0) -> str:
    """Block until the renderer sends a user_response message."""
    return await asyncio.wait_for(_user_input_queue.get(), timeout=timeout)


# ---------------------------------------------------------------------------
# Helper: send a JSON message over the active WebSocket (fire-and-forget)
# ---------------------------------------------------------------------------

def _send(payload: dict[str, Any]) -> None:
    ws = _active_ws
    if ws is None:
        return
    loop = asyncio.get_event_loop()
    coro = ws.send_text(json.dumps(payload, ensure_ascii=False))
    if loop.is_running():
        asyncio.ensure_future(coro)


# ---------------------------------------------------------------------------
# Event handler (wired via session.on(ws_handle_event))
# ---------------------------------------------------------------------------

_seen_event_ids: set[str] = set()
_last_event_time: float = 0.0
_pending_tool_starts: dict[str, float] = {}  # tool_name -> start_epoch


def ws_handle_event(event: Any) -> None:
    """Handle a Copilot SDK session event and push it as JSON to the WS."""
    global _last_event_time
    _last_event_time = time.time()

    try:
        from copilot.generated.session_events import SessionEventType
    except ImportError:
        return

    etype = event.type
    d = event.data

    if etype in (
        SessionEventType.ASSISTANT_MESSAGE_DELTA,
        SessionEventType.ASSISTANT_STREAMING_DELTA,
    ):
        eid = str(event.id)
        if eid in _seen_event_ids:
            return
        _seen_event_ids.add(eid)
        delta = getattr(d, "delta_content", None) or ""
        if delta:
            _send({"type": "delta", "content": delta})
        return

    if etype == SessionEventType.ASSISTANT_REASONING_DELTA:
        delta = getattr(d, "delta_content", None) or ""
        if delta:
            _send({"type": "reasoning_delta", "content": delta})
        return

    if etype == SessionEventType.TOOL_EXECUTION_START:
        tool = getattr(d, "tool_name", None) or getattr(d, "mcp_tool_name", "?")
        args_raw = getattr(d, "arguments", None)
        args_str = json.dumps(args_raw, ensure_ascii=False) if args_raw else "{}"
        _pending_tool_starts[str(tool)] = time.time()
        _send({
            "type": "tool_started",
            "tool": str(tool),
            "args": args_str,
        })
        return

    if etype == SessionEventType.TOOL_EXECUTION_COMPLETE:
        tool = getattr(d, "tool_name", None) or getattr(d, "mcp_tool_name", "?")
        started = _pending_tool_starts.pop(str(tool), _last_event_time)
        duration_ms = int((time.time() - started) * 1000)
        output_raw = getattr(d, "output", None)
        output_str = str(output_raw)[:500] if output_raw else None
        _send({
            "type": "tool_completed",
            "tool": str(tool),
            "duration_ms": duration_ms,
            "output_preview": output_str,
        })
        return

    if etype == SessionEventType.SUBAGENT_STARTED:
        name = getattr(d, "agent_name", "?") or "?"
        _send({"type": "subagent_started", "agent": str(name)})
        return

    if etype == SessionEventType.SUBAGENT_COMPLETED:
        name = getattr(d, "agent_name", "?") or "?"
        _send({"type": "subagent_completed", "agent": str(name)})
        return

    if etype == SessionEventType.ASSISTANT_USAGE:
        input_t = getattr(d, "input_tokens", 0) or 0
        output_t = getattr(d, "output_tokens", 0) or 0
        cache_r = getattr(d, "cache_read_tokens", 0) or 0
        cache_w = getattr(d, "cache_write_tokens", 0) or 0
        _send({
            "type": "usage",
            "input_tokens": input_t,
            "output_tokens": output_t,
            "cache_read_tokens": cache_r,
            "cache_write_tokens": cache_w,
        })
        return

    if etype == SessionEventType.SESSION_ERROR:
        msg = getattr(d, "message", str(d))
        _send({"type": "error", "message": str(msg)})
        return


def ws_reset() -> None:
    """Clear per-turn state when a new turn begins."""
    global _cancel_flag
    _seen_event_ids.clear()
    _pending_tool_starts.clear()
    _cancel_flag = False
    # Drain any stale user-input responses
    while not _user_input_queue.empty():
        try:
            _user_input_queue.get_nowait()
        except asyncio.QueueEmpty:
            break
