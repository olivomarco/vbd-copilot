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
# Per-session state for concurrent WebSocket connections.
# server.py manages one WS per session_id via /ws/{session_id}.
# ---------------------------------------------------------------------------

_ws_map: dict[str, set[Any]] = {}                  # session_id -> set of WebSockets
_cancel_flags: dict[str, bool] = {}             # session_id -> cancelled
_input_queues: dict[str, asyncio.Queue[str]] = {}  # session_id -> Queue
_seen_ids: dict[str, set[str]] = {}             # session_id -> seen event ids
_tool_starts: dict[str, dict[str, float]] = {}  # session_id -> {tool: epoch}
_last_times: dict[str, float] = {}              # session_id -> last event epoch

# Legacy single-session aliases (used by terminal mode / backward compat)
_active_ws: Any | None = None
_cancel_flag: bool = False
_user_input_queue: asyncio.Queue[str] = asyncio.Queue()


_SENTINEL = object()  # distinguishes "no ws arg" from "ws=None"


def set_active_ws(ws_or_session_id: Any | None, ws: Any = _SENTINEL) -> None:
    """Set the active WebSocket.

    Supports two calling conventions:
      - set_active_ws(ws)                 — legacy single-WS mode
      - set_active_ws(session_id, ws)     — per-session mode (ws can be None/False to remove)
    """
    global _active_ws
    if ws is _SENTINEL:
        # Legacy single-arg: set_active_ws(ws)
        _active_ws = ws_or_session_id
    else:
        # Per-session two-arg: set_active_ws(session_id, ws)
        sid = str(ws_or_session_id)
        if ws is False or ws is None:
            # Remove this specific websocket from the set
            conns = _ws_map.get(sid)
            if conns is not None:
                # If we were passed None without a specific ws to remove,
                # it means the caller wants a full teardown (legacy compat).
                # In the new multi-WS flow, server.py calls remove_ws() instead.
                pass
        else:
            if sid not in _ws_map:
                _ws_map[sid] = set()
                _cancel_flags[sid] = False
                _seen_ids[sid] = set()
                _tool_starts[sid] = {}
                _last_times[sid] = 0.0
                _input_queues.setdefault(sid, asyncio.Queue())
            _ws_map[sid].add(ws)


def add_ws(session_id: str, ws: Any) -> None:
    """Add a WebSocket connection to a session's subscriber set."""
    sid = str(session_id)
    if sid not in _ws_map:
        _ws_map[sid] = set()
        _cancel_flags[sid] = False
        _seen_ids[sid] = set()
        _tool_starts[sid] = {}
        _last_times[sid] = 0.0
        _input_queues.setdefault(sid, asyncio.Queue())
    _ws_map[sid].add(ws)


def remove_ws(session_id: str, ws: Any) -> None:
    """Remove a single WebSocket from a session's subscriber set."""
    sid = str(session_id)
    conns = _ws_map.get(sid)
    if conns is not None:
        conns.discard(ws)
        # Only clean up session state when ALL connections are gone
        if not conns:
            _ws_map.pop(sid, None)
            _cancel_flags.pop(sid, None)
            _seen_ids.pop(sid, None)
            _tool_starts.pop(sid, None)
            _last_times.pop(sid, None)


def get_active_ws() -> Any | None:
    return _active_ws


def set_cancel_flag(value: bool, session_id: str | None = None) -> None:
    global _cancel_flag
    if session_id:
        _cancel_flags[session_id] = value
    else:
        _cancel_flag = value


def get_cancel_flag(session_id: str | None = None) -> bool:
    if session_id:
        return _cancel_flags.get(session_id, False)
    return _cancel_flag


def push_user_response(content: str, session_id: str | None = None) -> None:
    """Push a user response for the current waiting_for_input prompt."""
    if session_id:
        q = _input_queues.setdefault(session_id, asyncio.Queue())
        q.put_nowait(content)
    else:
        _user_input_queue.put_nowait(content)


async def pop_user_response(timeout: float = 300.0, session_id: str | None = None) -> str:
    """Block until the renderer sends a user_response message."""
    if session_id:
        q = _input_queues.setdefault(session_id, asyncio.Queue())
        return await asyncio.wait_for(q.get(), timeout=timeout)
    return await asyncio.wait_for(_user_input_queue.get(), timeout=timeout)


# ---------------------------------------------------------------------------
# Helper: send a JSON message over a WebSocket (fire-and-forget)
# ---------------------------------------------------------------------------

def _send(payload: dict[str, Any], session_id: str | None = None) -> None:
    """Fan out a JSON message to all WebSockets subscribed to a session."""
    connections: set[Any] | None = None
    if session_id:
        connections = _ws_map.get(session_id)
    if not connections:
        # Fallback to legacy single-WS
        if _active_ws is not None:
            connections = {_active_ws}
        else:
            return

    text = json.dumps(payload, ensure_ascii=False)
    loop = asyncio.get_event_loop()
    for ws in list(connections):  # list() to avoid mutation during iteration
        coro = ws.send_text(text)
        if loop.is_running():
            asyncio.ensure_future(coro)


# ---------------------------------------------------------------------------
# Phase detection from tool / subagent patterns
# ---------------------------------------------------------------------------

_RESEARCH_TOOLS = {"bing_search", "web_fetch"}
_QA_TOOLS = {"run_pptx_qa_checks", "run_demo_qa_checks", "run_hackathon_qa_checks",
             "run_architecture_qa_checks", "run_infra_qa_checks"}


def _detect_phase(tool: str = "", agent: str = "") -> str | None:
    if tool in _RESEARCH_TOOLS:
        return "researching"
    if tool in _QA_TOOLS:
        return "qa"
    if "builder" in agent or "implementor" in agent:
        return "building"
    if "researcher" in agent or "research" in agent:
        return "researching"
    if "reviewer" in agent or "review" in agent:
        return "qa"
    return None


# ---------------------------------------------------------------------------
# Event handler (wired via session.on(ws_handle_event))
# ---------------------------------------------------------------------------

_seen_event_ids: set[str] = set()
_last_event_time: float = 0.0
_pending_tool_starts: dict[str, float] = {}  # tool_name -> start_epoch
_current_phase: str = ""  # track last emitted phase for dedup


def _make_ws_handler(session_id: str):
    """Return an event handler closure bound to a specific session_id."""
    last_phase = ""

    def _handler(event: Any) -> None:
        nonlocal last_phase
        _last_times[session_id] = time.time()

        try:
            from copilot.generated.session_events import SessionEventType
        except ImportError:
            return

        etype = event.type
        d = event.data
        seen = _seen_ids.get(session_id, _seen_event_ids)
        tool_starts = _tool_starts.get(session_id, _pending_tool_starts)
        send = lambda p: _send(p, session_id)

        if etype in (
            SessionEventType.ASSISTANT_MESSAGE_DELTA,
            SessionEventType.ASSISTANT_STREAMING_DELTA,
        ):
            eid = str(event.id)
            if eid in seen:
                return
            seen.add(eid)
            delta = getattr(d, "delta_content", None) or ""
            if delta:
                send({"type": "delta", "content": delta})
            return

        if etype == SessionEventType.ASSISTANT_REASONING_DELTA:
            delta = getattr(d, "delta_content", None) or ""
            if delta:
                send({"type": "reasoning_delta", "content": delta})
            return

        if etype == SessionEventType.TOOL_EXECUTION_START:
            tool = getattr(d, "tool_name", None) or getattr(d, "mcp_tool_name", "?")
            args_raw = getattr(d, "arguments", None)
            args_str = json.dumps(args_raw, ensure_ascii=False) if args_raw else "{}"
            tool_starts[str(tool)] = time.time()
            send({"type": "tool_started", "tool": str(tool), "args": args_str})
            # Emit phase detection
            phase = _detect_phase(tool=str(tool))
            if phase and phase != last_phase:
                last_phase = phase
                send({"type": "phase_changed", "phase": phase})
            return

        if etype == SessionEventType.TOOL_EXECUTION_COMPLETE:
            tool = getattr(d, "tool_name", None) or getattr(d, "mcp_tool_name", "?")
            started = tool_starts.pop(str(tool), _last_times.get(session_id, 0))
            duration_ms = int((time.time() - started) * 1000)
            output_raw = getattr(d, "output", None)
            output_str = str(output_raw)[:500] if output_raw else None
            send({"type": "tool_completed", "tool": str(tool), "duration_ms": duration_ms, "output_preview": output_str})
            return

        if etype == SessionEventType.SUBAGENT_STARTED:
            name = getattr(d, "agent_name", "?") or "?"
            send({"type": "subagent_started", "agent": str(name)})
            phase = _detect_phase(agent=str(name))
            if phase and phase != last_phase:
                last_phase = phase
                send({"type": "phase_changed", "phase": phase})
            return

        if etype == SessionEventType.SUBAGENT_COMPLETED:
            name = getattr(d, "agent_name", "?") or "?"
            send({"type": "subagent_completed", "agent": str(name)})
            return

        if etype == SessionEventType.ASSISTANT_USAGE:
            input_t = getattr(d, "input_tokens", 0) or 0
            output_t = getattr(d, "output_tokens", 0) or 0
            cache_r = getattr(d, "cache_read_tokens", 0) or 0
            cache_w = getattr(d, "cache_write_tokens", 0) or 0
            send({"type": "usage", "input_tokens": input_t, "output_tokens": output_t,
                  "cache_read_tokens": cache_r, "cache_write_tokens": cache_w})
            return

        if etype == SessionEventType.SESSION_ERROR:
            msg = getattr(d, "message", str(d))
            send({"type": "error", "message": str(msg)})
            return

        # Catch-all for any unhandled event types
        log.debug("Unhandled session event type %s for session %s", etype, session_id)

    return _handler


def ws_reset(session_id: str | None = None) -> None:
    """Clear per-turn state when a new turn begins."""
    global _cancel_flag
    if session_id:
        _cancel_flags[session_id] = False
        if session_id in _seen_ids:
            _seen_ids[session_id].clear()
        if session_id in _tool_starts:
            _tool_starts[session_id].clear()
        q = _input_queues.get(session_id)
        if q:
            while not q.empty():
                try:
                    q.get_nowait()
                except asyncio.QueueEmpty:
                    break
    else:
        _seen_event_ids.clear()
        _pending_tool_starts.clear()
        _cancel_flag = False
        while not _user_input_queue.empty():
            try:
                _user_input_queue.get_nowait()
            except asyncio.QueueEmpty:
                break


# Keep legacy name for backward compat with terminal mode
def ws_handle_event(event: Any) -> None:
    """Legacy single-session event handler (delegates to global state)."""
    handler = _make_ws_handler("__legacy__")
    handler(event)
