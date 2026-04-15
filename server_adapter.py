"""WebSocket adapter that bridges CopilotUI events to JSON messages.

``WebSocketEventAdapter`` is a plain event sink (not a subclass of CopilotUI)
that receives the same ``session.on(handler)`` callback events and serialises
them as newline-delimited JSON over an active WebSocket connection.

The existing ``CopilotUI`` + ``EventCollector`` → SQLite pipeline is never
touched; this adapter is wired in *addition* to it via a second ``session.on``
subscriber so that no terminal-side code breaks.

v2: Introduces ``SessionConnection`` to encapsulate per-session state,
    a v1 message envelope protocol, session snapshots for reconnection,
    and correlation IDs for tool/subagent lifecycle events.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import time
import uuid
from typing import Any

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# SessionConnection — encapsulates all per-session WebSocket state
# ---------------------------------------------------------------------------


class SessionConnection:
    """Manages WebSocket state for a single Copilot SDK session.

    Replaces the previous module-level dicts (_ws_map, _cancel_flags, etc.)
    with a single object per session.  Lifecycle: created on first WS connect,
    destroyed when the last WS disconnects.
    """

    __slots__ = (
        "session_id",
        "websockets",
        "cancel_flag",
        "input_queue",
        "pending_input",
        "pending_input_request_id",
        "last_done",
        "active_subagents",
        "subagent_correlations",
        "seen_event_ids",
        "tool_starts",
        "last_event_time",
        "event_handler_unsub",
        "_seq",
        "created_at",
        "response_buffer",
        "output_files",
        "ask_user_lock",
        "pending_invocations",
        "current_turn_task",
        "turn_lock",
        "_send_queues",
        "_send_workers",
    )

    def __init__(self, session_id: str) -> None:
        self.session_id = session_id
        self.websockets: set[Any] = set()
        self.cancel_flag: bool = False
        self.input_queue: asyncio.Queue[tuple[str, str | None]] = asyncio.Queue()
        self.pending_input: dict[str, Any] | None = None
        self.pending_input_request_id: str | None = None
        self.last_done: dict[str, Any] | None = None
        self.active_subagents: list[str] = []
        self.subagent_correlations: dict[str, str] = {}  # agent_name -> correlation_id
        self.seen_event_ids: set[str] = set()
        self.tool_starts: dict[
            str, tuple[float, str]
        ] = {}  # tool -> (epoch, correlation_id)
        self.last_event_time: float = 0.0
        self.event_handler_unsub: Any | None = None
        self._seq: int = 0  # monotonic sequence counter for envelope
        self.created_at: float = time.time()
        self.response_buffer: list[str] = []
        self.output_files: list[str] = []
        self.ask_user_lock: asyncio.Lock = asyncio.Lock()
        self.pending_invocations: dict[
            str, str
        ] = {}  # tool/subagent key -> invocation_id
        self.current_turn_task: asyncio.Task[Any] | None = None
        self.turn_lock: asyncio.Lock = asyncio.Lock()
        # Per-WS ordered send queues (Fix 2: serialize sends)
        self._send_queues: dict[Any, asyncio.Queue[str]] = {}
        self._send_workers: dict[Any, asyncio.Task[Any]] = {}

    def next_seq(self) -> int:
        """Return the next monotonic sequence number."""
        self._seq += 1
        return self._seq

    def add_ws(self, ws: Any) -> bool:
        """Add a WebSocket. Returns True if this is the first connection."""
        is_first = len(self.websockets) == 0
        self.websockets.add(ws)
        return is_first

    def remove_ws(self, ws: Any) -> bool:
        """Remove a WebSocket. Returns True if no connections remain."""
        self.websockets.discard(ws)
        # Clean up per-WS send queue and worker
        worker = self._send_workers.pop(ws, None)
        if worker and not worker.done():
            worker.cancel()
        self._send_queues.pop(ws, None)
        return len(self.websockets) == 0

    def reset_turn(self) -> None:
        """Clear per-turn state for a new turn."""
        self.cancel_flag = False
        # Bound seen_event_ids to prevent unbounded growth (Fix 4)
        if len(self.seen_event_ids) > 5000:
            self.seen_event_ids.clear()
        self.tool_starts.clear()
        self.active_subagents.clear()
        self.subagent_correlations.clear()
        self._seq = 0
        self.response_buffer.clear()
        self.pending_invocations.clear()
        # Drain input queue ONLY if no _user_input callback is actively
        # waiting for a response.  When the lock is held a callback is
        # blocked on ``input_queue.get()``; draining the queue would
        # discard any response the user already pushed and leave the
        # callback stuck until it times out.
        if not self.ask_user_lock.locked():
            while not self.input_queue.empty():
                try:
                    self.input_queue.get_nowait()
                except asyncio.QueueEmpty:
                    break

    def cleanup(self) -> None:
        """Full cleanup when session is destroyed."""
        # Cancel active turn task on explicit session deletion
        if self.current_turn_task and not self.current_turn_task.done():
            self.current_turn_task.cancel()
            self.current_turn_task = None
        self.reset_turn()
        self.pending_input = None
        self.pending_input_request_id = None
        self.last_done = None
        if self.event_handler_unsub is not None:
            with contextlib.suppress(Exception):
                self.event_handler_unsub()
            self.event_handler_unsub = None
        # Clean up all send workers
        for worker in self._send_workers.values():
            if not worker.done():
                worker.cancel()
        self._send_workers.clear()
        self._send_queues.clear()

    def get_response_text(self) -> str:
        """Return accumulated assistant response text."""
        return "".join(self.response_buffer)


# ---------------------------------------------------------------------------
# Connection registry + legacy single-session state
# ---------------------------------------------------------------------------

_connections: dict[str, SessionConnection] = {}

# Strong reference set for fire-and-forget asyncio tasks.
# Python 3.12+ only keeps weak references to tasks; without this set,
# tasks created via asyncio.ensure_future() can be garbage-collected
# mid-execution, silently dropping WebSocket sends.
_background_tasks: set[asyncio.Task[Any]] = set()


# ---------------------------------------------------------------------------
# Task-keeping factory — prevents GC of ALL tasks, including SDK internals
# ---------------------------------------------------------------------------
# Python 3.12+ event loops only hold *weak* references to tasks.  The SDK's
# JsonRpcClient._handle_request calls run_coroutine_threadsafe() and discards
# the returned Future.  Under GC pressure (two concurrent sessions) the
# underlying Task can be collected mid-execution, silently dropping tool-call
# responses, user-input callbacks, and permission requests.
#
# Installing a custom task factory that keeps strong references guarantees
# every task runs to completion.

_all_tasks: set[asyncio.Task[Any]] = set()
_task_factory_installed: bool = False


def install_task_keeping_factory(loop: asyncio.AbstractEventLoop | None = None) -> None:
    """Install a task factory that prevents GC of asyncio tasks.

    Safe to call multiple times; only installs once per loop.
    """
    global _task_factory_installed
    if _task_factory_installed:
        return

    target_loop = loop or asyncio.get_event_loop()

    def _keeping_factory(
        loop: asyncio.AbstractEventLoop,
        coro: Any,
        **kwargs: Any,
    ) -> asyncio.Task[Any]:
        task = asyncio.Task(coro, loop=loop, **kwargs)
        _all_tasks.add(task)
        task.add_done_callback(_all_tasks.discard)
        return task

    target_loop.set_task_factory(_keeping_factory)
    _task_factory_installed = True


# EventCollector reference — injected by server.py via set_collector()
_collector: Any = None


def set_collector(collector: Any) -> None:
    """Inject the EventCollector so WS handlers can persist events to DB."""
    global _collector
    _collector = collector


# Legacy single-session aliases (used by terminal mode / backward compat)
_active_ws: Any | None = None
_cancel_flag: bool = False
_user_input_queue: asyncio.Queue[str] = asyncio.Queue()

# Legacy globals for the __legacy__ handler path (terminal mode)
_seen_event_ids: set[str] = set()
_pending_tool_starts: dict[str, float] = {}


def get_connection(session_id: str) -> SessionConnection | None:
    """Return the SessionConnection for *session_id*, or None."""
    return _connections.get(session_id)


def _get_or_create(session_id: str) -> SessionConnection:
    """Return existing or create a new SessionConnection."""
    conn = _connections.get(session_id)
    if conn is None:
        conn = SessionConnection(session_id)
        _connections[session_id] = conn
    return conn


# ---------------------------------------------------------------------------
# Public functions — same signatures as before, delegate to SessionConnection
# ---------------------------------------------------------------------------

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
            # Legacy compat — server.py uses remove_ws() in new flow
            pass
        else:
            conn = _get_or_create(sid)
            conn.add_ws(ws)


def add_ws(session_id: str, ws: Any) -> bool:
    """Add a WebSocket connection to a session.  Returns True if first."""
    conn = _get_or_create(str(session_id))
    return conn.add_ws(ws)


def remove_ws(session_id: str, ws: Any) -> bool:
    """Remove a single WebSocket from a session.  Returns True if none remain.

    The SessionConnection and its SDK event handler are **preserved** even
    when all WebSockets disconnect.  This is critical for multi-session
    reliability: the SDK keeps dispatching events regardless of WS state,
    and the handler must stay registered so that no events are lost during
    reconnect windows.  When a new WS connects, ``add_ws`` puts it into
    the existing conn and events resume flowing immediately.

    Full cleanup only happens via :func:`destroy_connection` (called when
    the session is explicitly deleted).
    """
    sid = str(session_id)
    conn = _connections.get(sid)
    if conn is None:
        return True
    is_empty = conn.remove_ws(ws)
    return is_empty


def destroy_connection(session_id: str) -> None:
    """Fully tear down a session's connection state and event handler.

    Called when a session is explicitly deleted — NOT on transient WS
    disconnects.  This is the only path that unregisters the SDK event
    handler and removes the SessionConnection from the registry.
    """
    conn = _connections.pop(session_id, None)
    if conn:
        conn.cleanup()


def get_active_ws() -> Any | None:
    return _active_ws


def set_cancel_flag(value: bool, session_id: str | None = None) -> None:
    global _cancel_flag
    if session_id:
        conn = _connections.get(session_id)
        if conn:
            conn.cancel_flag = value
    else:
        _cancel_flag = value


def get_cancel_flag(session_id: str | None = None) -> bool:
    if session_id:
        conn = _connections.get(session_id)
        return conn.cancel_flag if conn else False
    return _cancel_flag


def set_pending_input(session_id: str, payload: dict[str, Any] | None) -> None:
    """Track or clear the pending waiting_for_input state for a session."""
    conn = _connections.get(session_id)
    if conn:
        conn.pending_input = payload


def get_pending_input(session_id: str) -> dict[str, Any] | None:
    """Return the pending waiting_for_input payload, or None."""
    conn = _connections.get(session_id)
    return conn.pending_input if conn else None


def set_last_done(session_id: str, payload: dict[str, Any]) -> None:
    """Store the last done event for a session so reconnecting clients receive it."""
    conn = _connections.get(session_id)
    if conn:
        conn.last_done = payload


def get_last_done(session_id: str) -> dict[str, Any] | None:
    """Return the stored done payload, or None."""
    conn = _connections.get(session_id)
    return conn.last_done if conn else None


def clear_last_done(session_id: str) -> None:
    """Clear the stored done status (e.g. when a new turn starts)."""
    conn = _connections.get(session_id)
    if conn:
        conn.last_done = None


def set_output_files(session_id: str, files: list[str]) -> None:
    """Store output files detected for a session so reconnecting clients receive them."""
    conn = _connections.get(session_id)
    if conn:
        conn.output_files = list(set(conn.output_files + files))


def get_output_files(session_id: str) -> list[str]:
    """Return the stored output files list."""
    conn = _connections.get(session_id)
    return conn.output_files if conn else []


def get_ask_user_lock(session_id: str) -> asyncio.Lock:
    """Return the per-session lock for serializing ask_user calls."""
    conn = _get_or_create(session_id)
    return conn.ask_user_lock


def has_event_handler(session_id: str) -> bool:
    """Check if a session already has a registered WS event handler."""
    conn = _connections.get(session_id)
    return conn is not None and conn.event_handler_unsub is not None


def register_event_handler(session_id: str, session: Any) -> None:
    """Register a WS event handler for a session (idempotent)."""
    conn = _get_or_create(session_id)
    if conn.event_handler_unsub is not None:
        return  # already registered
    handler = _make_ws_handler(session_id)
    unsub = session.on(handler)
    conn.event_handler_unsub = unsub


def unregister_event_handler(session_id: str) -> None:
    """Unregister the WS event handler for a session if one exists."""
    conn = _connections.get(session_id)
    if conn is not None and conn.event_handler_unsub is not None:
        with contextlib.suppress(Exception):
            conn.event_handler_unsub()
        conn.event_handler_unsub = None


def push_user_response(
    content: str, session_id: str | None = None, request_id: str | None = None
) -> None:
    """Push a user response for the current waiting_for_input prompt."""
    if session_id:
        conn = _get_or_create(session_id)
        conn.pending_input = None  # clear pending input on response
        conn.pending_input_request_id = None
        conn.input_queue.put_nowait((content, request_id))
    else:
        _user_input_queue.put_nowait(content)


async def pop_user_response(
    timeout: float = 300.0,
    session_id: str | None = None,
    expected_request_id: str | None = None,
) -> str:
    """Block until the renderer sends a user_response message.

    If *expected_request_id* is provided, discard any queued responses
    whose request_id does not match (stale responses from a previous
    prompt).  This prevents late/duplicate answers from satisfying the
    wrong question.
    """
    if session_id:
        conn = _get_or_create(session_id)

        async def _get_matching() -> str:
            while True:
                content, rid = await conn.input_queue.get()
                # Accept if: no expected ID, no provided ID, or IDs match
                if expected_request_id is None or rid is None or rid == expected_request_id:
                    return content
                log.warning(
                    "[ask_user] Discarding stale response (expected=%s, got=%s)",
                    expected_request_id,
                    rid,
                )

        return await asyncio.wait_for(_get_matching(), timeout=timeout)
    return await asyncio.wait_for(_user_input_queue.get(), timeout=timeout)


def get_accumulated_response(session_id: str) -> str:
    """Return the accumulated assistant response text for a session."""
    conn = _connections.get(session_id)
    return conn.get_response_text() if conn else ""


# ---------------------------------------------------------------------------
# Turn task management (Fix 1: atomic turn claiming)
# ---------------------------------------------------------------------------


def get_turn_task(session_id: str) -> asyncio.Task[Any] | None:
    """Return the active turn task for a session, or None."""
    conn = _connections.get(session_id)
    if conn is None:
        return None
    task = conn.current_turn_task
    if task is not None and task.done():
        conn.current_turn_task = None
        return None
    return task


def set_turn_task(session_id: str, task: asyncio.Task[Any] | None) -> None:
    """Set the active turn task for a session."""
    conn = _connections.get(session_id)
    if conn:
        conn.current_turn_task = task


def get_turn_lock(session_id: str) -> asyncio.Lock:
    """Return the per-session lock for atomic turn claiming."""
    conn = _get_or_create(session_id)
    return conn.turn_lock


def has_active_turn(session_id: str) -> bool:
    """Return True if a turn is currently running for this session."""
    return get_turn_task(session_id) is not None


# ---------------------------------------------------------------------------
# Idle session reaper (Fix 4: memory cleanup)
# ---------------------------------------------------------------------------

_reaper_task: asyncio.Task[Any] | None = None
_REAPER_INTERVAL_S = 300  # 5 minutes
_IDLE_EXPIRY_S = 7200  # 2 hours (matches _ASK_USER_TIMEOUT)


async def _reaper_loop() -> None:
    """Periodically remove abandoned SessionConnections."""
    while True:
        await asyncio.sleep(_REAPER_INTERVAL_S)
        now = time.time()
        to_remove: list[str] = []
        for sid, conn in list(_connections.items()):
            # Never reap sessions that are still active
            if conn.websockets:
                continue
            if conn.pending_input is not None:
                continue
            if conn.ask_user_lock.locked():
                continue
            if conn.current_turn_task and not conn.current_turn_task.done():
                continue
            if conn.event_handler_unsub is not None:
                # Session still registered with SDK — only reap if idle long enough
                idle_since = max(conn.last_event_time, conn.created_at)
                if now - idle_since < _IDLE_EXPIRY_S:
                    continue
            to_remove.append(sid)
        for sid in to_remove:
            conn = _connections.pop(sid, None)
            if conn:
                conn.cleanup()
                log.debug("Reaped idle session connection: %s", sid)


def start_reaper() -> None:
    """Start the idle session reaper (call once at server startup)."""
    global _reaper_task
    if _reaper_task is None or _reaper_task.done():
        _reaper_task = asyncio.ensure_future(_reaper_loop())
        _all_tasks.add(_reaper_task)
        _reaper_task.add_done_callback(_all_tasks.discard)


def stop_reaper() -> None:
    """Stop the idle session reaper."""
    global _reaper_task
    if _reaper_task and not _reaper_task.done():
        _reaper_task.cancel()
        _reaper_task = None


# ---------------------------------------------------------------------------
# Message envelope protocol (v1)
# ---------------------------------------------------------------------------


def _envelope(
    conn: SessionConnection | None,
    msg_type: str,
    data: dict[str, Any],
    correlation_id: str | None = None,
) -> dict[str, Any]:
    """Wrap a message in the v1 envelope protocol."""
    return {
        "v": 1,
        "type": msg_type,
        "id": str(uuid.uuid4()),
        "seq": conn.next_seq() if conn else 0,
        "ts": time.time(),
        "correlationId": correlation_id,
        "data": data,
    }


# ---------------------------------------------------------------------------
# Session snapshot for reconnecting clients
# ---------------------------------------------------------------------------


def build_snapshot(session_id: str) -> dict[str, Any] | None:
    """Build a ``session_snapshot`` envelope for a reconnecting client.

    Returns None if the session has no active connection state.
    """
    conn = _connections.get(session_id)
    if conn is None:
        return None
    has_turn = conn.current_turn_task is not None and not conn.current_turn_task.done()
    status = (
        "waiting" if conn.pending_input else ("active" if (conn.websockets or has_turn) else "idle")
    )
    return _envelope(
        conn,
        "session_snapshot",
        {
            "session_id": session_id,
            "status": status,
            "pending_input": conn.pending_input,
            "pending_input_request_id": conn.pending_input_request_id,
            "last_done": conn.last_done,
            "active_subagents": list(conn.active_subagents),
            "output_files": conn.output_files,
            "has_running_turn": has_turn,
            "seq": conn._seq,
        },
    )


# ---------------------------------------------------------------------------
# Server-push: session state changed
# ---------------------------------------------------------------------------


def emit_state_changed(session_id: str, status: str, reason: str = "") -> None:
    """Push a ``session_state_changed`` event to all connected clients.

    No-op if the session has no active WebSocket connections.
    """
    conn = _connections.get(session_id)
    if conn and conn.websockets:
        _send(
            _envelope(
                conn,
                "session_state_changed",
                {
                    "session_id": session_id,
                    "status": status,
                    "reason": reason,
                },
            ),
            session_id,
        )


# ---------------------------------------------------------------------------
# Server-side heartbeat
# ---------------------------------------------------------------------------

_heartbeat_task: asyncio.Task[Any] | None = None
HEARTBEAT_INTERVAL_S: int = 15


async def _heartbeat_loop() -> None:
    """Send a heartbeat to every connected session every HEARTBEAT_INTERVAL_S."""
    while True:
        await asyncio.sleep(HEARTBEAT_INTERVAL_S)
        for sid, conn in list(_connections.items()):
            if conn.websockets:
                try:
                    _send(_envelope(conn, "heartbeat", {"ts": time.time()}), sid)
                except Exception:
                    pass


def start_heartbeat() -> None:
    """Start the background heartbeat loop (call once at server startup)."""
    global _heartbeat_task
    if _heartbeat_task is None or _heartbeat_task.done():
        _heartbeat_task = asyncio.ensure_future(_heartbeat_loop())
        # Also add to _all_tasks as a safety net
        _all_tasks.add(_heartbeat_task)
        _heartbeat_task.add_done_callback(_all_tasks.discard)


def stop_heartbeat() -> None:
    """Stop the background heartbeat loop (for clean shutdown / tests)."""
    global _heartbeat_task
    if _heartbeat_task and not _heartbeat_task.done():
        _heartbeat_task.cancel()
        _heartbeat_task = None


# ---------------------------------------------------------------------------
# Helper: send a JSON message over a WebSocket (serialized per-WS)
# ---------------------------------------------------------------------------

_MAX_SEND_QUEUE = 500  # drop oldest if a slow client falls behind


def _ensure_send_worker(conn: SessionConnection, ws: Any, session_id: str) -> None:
    """Lazily create a per-WS send worker that drains the send queue in order."""
    if ws in conn._send_workers and not conn._send_workers[ws].done():
        return  # already running

    q = conn._send_queues.setdefault(ws, asyncio.Queue())

    async def _worker() -> None:
        try:
            while True:
                text = await q.get()
                try:
                    await ws.send_text(text)
                except (RuntimeError, Exception):
                    # WS is dead — clean up and exit
                    conn.websockets.discard(ws)
                    break
        except asyncio.CancelledError:
            pass
        finally:
            conn._send_queues.pop(ws, None)
            conn._send_workers.pop(ws, None)

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return
    task = loop.create_task(_worker())
    conn._send_workers[ws] = task
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)


def _send(payload: dict[str, Any], session_id: str | None = None) -> None:
    """Fan out a JSON message to all WebSockets subscribed to a session.

    Messages are serialized per-WS via ordered send queues so events
    always arrive in the order they were emitted.
    """
    ws_set: set[Any] | None = None
    conn: SessionConnection | None = None
    if session_id:
        conn = _connections.get(session_id)
        ws_set = conn.websockets if conn else None
    if not ws_set:
        # Fallback to legacy single-WS
        if _active_ws is not None:
            ws_set = {_active_ws}
        else:
            return

    text = json.dumps(payload, ensure_ascii=False)
    dead: list[Any] = []

    for ws in list(ws_set):  # list() to avoid mutation during iteration
        try:
            # Skip WebSockets that are already closed
            if hasattr(ws, "client_state") and ws.client_state.name == "DISCONNECTED":
                dead.append(ws)
                continue
            if conn:
                _ensure_send_worker(conn, ws, session_id or "")
                q = conn._send_queues.get(ws)
                if q:
                    # Drop oldest messages if queue is too large (slow client)
                    if q.qsize() >= _MAX_SEND_QUEUE:
                        try:
                            q.get_nowait()
                        except asyncio.QueueEmpty:
                            pass
                    q.put_nowait(text)
            else:
                # Legacy path — no conn, fire-and-forget
                try:
                    loop = asyncio.get_running_loop()
                except RuntimeError:
                    continue

                async def _safe_send(w: Any, t: str) -> None:
                    try:
                        await w.send_text(t)
                    except (RuntimeError, Exception):
                        pass

                if loop.is_running():
                    task = loop.create_task(_safe_send(ws, text))
                    _background_tasks.add(task)
                    task.add_done_callback(_background_tasks.discard)
        except RuntimeError:
            dead.append(ws)
    # Clean up dead connections
    if dead and session_id and conn:
        for ws in dead:
            conn.websockets.discard(ws)


async def send_direct(
    ws: Any, payload: dict[str, Any], session_id: str | None = None
) -> None:
    """Send a message to a specific WebSocket, using the serialized queue.

    Use this instead of ``await ws.send_text(...)`` so all sends on a
    given WS are ordered.  Falls back to direct send if no session
    connection exists.
    """
    text = json.dumps(payload, ensure_ascii=False)
    conn = _connections.get(session_id) if session_id else None
    if conn:
        _ensure_send_worker(conn, ws, session_id or "")
        q = conn._send_queues.get(ws)
        if q:
            q.put_nowait(text)
            return
    # Fallback: direct send (legacy / no conn)
    await ws.send_text(text)


# ---------------------------------------------------------------------------
# Phase detection from tool / subagent patterns
# ---------------------------------------------------------------------------

_RESEARCH_TOOLS = {"bing_search", "web_fetch"}
_QA_TOOLS = {
    "run_pptx_qa_checks",
    "run_demo_qa_checks",
    "run_hackathon_qa_checks",
    "run_architecture_qa_checks",
    "run_infra_qa_checks",
    "run_pipeline_qa_checks",
    "run_docs_qa_checks",
}


def _detect_phase(tool: str = "", agent: str = "") -> str | None:
    tl = tool.lower()
    al = agent.lower()

    # Research phase: web search, fetching, research subagents
    if tool in _RESEARCH_TOOLS:
        return "researching"
    if "research" in al:
        return "researching"

    # Planning phase: ask_user (discovery questions), report_intent
    if tl in ("ask_user", "report_intent"):
        return "planning"

    # Building phase: builder subagents, code/file tools
    if "builder" in al or "implementor" in al:
        return "building"
    if tl in ("str_replace_editor", "bash"):
        return "building"

    # QA phase: QA tools, reviewer subagents
    if tool in _QA_TOOLS:
        return "qa"
    if "reviewer" in al or "review" in al:
        return "qa"

    return None


# ---------------------------------------------------------------------------
# Event handler (wired via session.on())
# ---------------------------------------------------------------------------


def _make_ws_handler(session_id: str):
    """Return an event handler closure bound to a specific *session_id*.

    All outgoing messages are wrapped in v1 envelopes.  Tool and subagent
    lifecycle events carry correlation IDs so the frontend can pair
    start/complete messages.
    """
    last_phase = ""

    def _handler(event: Any) -> None:
        nonlocal last_phase
        conn = _connections.get(session_id)
        if conn:
            conn.last_event_time = time.time()

        try:
            from copilot.generated.session_events import SessionEventType
        except ImportError:
            return

        etype = event.type
        d = event.data

        # Resolve dedup set: per-connection or legacy global
        seen = conn.seen_event_ids if conn else _seen_event_ids

        def emit(
            msg_type: str, data: dict[str, Any], correlation_id: str | None = None
        ) -> None:
            """Wrap *data* in an envelope and send."""
            _send(_envelope(conn, msg_type, data, correlation_id), session_id)

        # -- Reasoning deltas (thinking tokens) ----------------------------

        if (
            hasattr(SessionEventType, "ASSISTANT_REASONING_DELTA")
            and etype == SessionEventType.ASSISTANT_REASONING_DELTA
        ):
            delta = getattr(d, "delta_content", None) or ""
            if delta:
                emit("reasoning_delta", {"content": delta})
            return

        # -- Streaming deltas -----------------------------------------------

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
                emit("delta", {"content": delta})
                if conn:
                    conn.response_buffer.append(delta)
            return

        # -- Tool lifecycle -------------------------------------------------

        if etype == SessionEventType.TOOL_EXECUTION_START:
            # Agent is running tools — clear any pending input
            if conn:
                conn.pending_input = None
            tool = (
                getattr(d, "tool_name", None)
                or getattr(d, "mcp_tool_name", None)
                or "?"
            )
            args_raw = getattr(d, "arguments", None)
            args_str = json.dumps(args_raw, ensure_ascii=False) if args_raw else "{}"
            corr_id = str(uuid.uuid4())
            if conn:
                conn.tool_starts[str(tool)] = (time.time(), corr_id)
            sa_stack = conn.active_subagents if conn else []
            parent_sa = sa_stack[-1] if sa_stack else None
            payload: dict[str, Any] = {"tool": str(tool), "args": args_str}
            if parent_sa:
                payload["_subagent"] = parent_sa
            # Always emit to WebSocket first — DB persistence must never block delivery
            emit("tool_started", payload, correlation_id=corr_id)
            phase = _detect_phase(tool=str(tool))
            if phase and phase != last_phase:
                last_phase = phase
                emit("phase_changed", {"phase": phase})
            # Best-effort DB persistence
            try:
                if _collector:
                    inv_id = _collector.on_tool_start(
                        str(tool),
                        args_str,
                        subagent_name=parent_sa,
                        session_id=session_id,
                    )
                    if inv_id and conn:
                        conn.pending_invocations[str(tool)] = inv_id
            except Exception:
                log.debug("collector.on_tool_start failed", exc_info=True)
            return

        if etype == SessionEventType.TOOL_EXECUTION_COMPLETE:
            tool = (
                getattr(d, "tool_name", None)
                or getattr(d, "mcp_tool_name", None)
                or "?"
            )
            started, corr_id = (0.0, None)
            if conn:
                started, corr_id = conn.tool_starts.pop(
                    str(tool), (conn.last_event_time, None)
                )
            duration_ms = int((time.time() - started) * 1000)
            output_raw = getattr(d, "output", None)
            output_str = str(output_raw)[:500] if output_raw else None
            payload = {
                "tool": str(tool),
                "duration_ms": duration_ms,
                "output_preview": output_str,
            }
            sa_stack = conn.active_subagents if conn else []
            if sa_stack:
                payload["_subagent"] = sa_stack[-1]
            emit("tool_completed", payload, correlation_id=corr_id)
            # Best-effort DB persistence
            try:
                if _collector and conn:
                    inv_id = conn.pending_invocations.pop(str(tool), None)
                    if inv_id:
                        _collector.on_tool_end(
                            inv_id, output=output_str, status="success"
                        )
            except Exception:
                log.debug("collector.on_tool_end failed", exc_info=True)
            return

        # -- Tool partial/progress events --------------------------------

        if (
            hasattr(SessionEventType, "TOOL_EXECUTION_PARTIAL_RESULT")
            and etype == SessionEventType.TOOL_EXECUTION_PARTIAL_RESULT
        ):
            partial = getattr(d, "partial_output", None) or ""
            emit("tool_partial_result", {"content": partial[:2000]})
            return

        if (
            hasattr(SessionEventType, "TOOL_EXECUTION_PROGRESS")
            and etype == SessionEventType.TOOL_EXECUTION_PROGRESS
        ):
            msg = getattr(d, "progress_message", None) or ""
            emit("tool_progress", {"message": msg})
            return

        # -- Subagent lifecycle ---------------------------------------------

        if etype == SessionEventType.SUBAGENT_STARTED:
            # Agent is running subagents — clear any pending input
            if conn:
                conn.pending_input = None
            name = getattr(d, "agent_name", "?") or "?"
            corr_id = str(uuid.uuid4())
            if conn:
                conn.active_subagents.append(str(name))
                conn.subagent_correlations[str(name)] = corr_id
            emit("subagent_started", {"agent": str(name)}, correlation_id=corr_id)
            phase = _detect_phase(agent=str(name))
            if phase and phase != last_phase:
                last_phase = phase
                emit("phase_changed", {"phase": phase})
            # Best-effort DB persistence
            try:
                if _collector:
                    inv_id = _collector.on_subagent_start(
                        str(name), session_id=session_id
                    )
                    if inv_id and conn:
                        conn.pending_invocations[f"subagent:{name}"] = inv_id
            except Exception:
                log.debug("collector.on_subagent_start failed", exc_info=True)
            return

        if etype == SessionEventType.SUBAGENT_COMPLETED:
            name = getattr(d, "agent_name", "?") or "?"
            corr_id: str | None = None
            if conn:
                corr_id = conn.subagent_correlations.pop(str(name), None)
                sa_stack = conn.active_subagents
                try:
                    sa_stack.remove(str(name))
                except ValueError:
                    if sa_stack:
                        sa_stack.pop()
            emit("subagent_completed", {"agent": str(name)}, correlation_id=corr_id)
            # Best-effort DB persistence
            try:
                if _collector and conn:
                    inv_id = conn.pending_invocations.pop(f"subagent:{name}", None)
                    if inv_id:
                        _collector.on_subagent_end(inv_id, status="success")
            except Exception:
                log.debug("collector.on_subagent_end failed", exc_info=True)
            return

        # SUBAGENT_FAILED — forward the error to the frontend
        if (
            hasattr(SessionEventType, "SUBAGENT_FAILED")
            and etype == SessionEventType.SUBAGENT_FAILED
        ):
            name = getattr(d, "agent_name", "?") or "?"
            error = getattr(d, "message", None) or getattr(d, "error", None) or str(d)
            corr_id = None
            if conn:
                corr_id = conn.subagent_correlations.pop(str(name), None)
                sa_stack = conn.active_subagents
                try:
                    sa_stack.remove(str(name))
                except ValueError:
                    if sa_stack:
                        sa_stack.pop()
            emit(
                "subagent_failed",
                {"agent": str(name), "error": str(error)},
                correlation_id=corr_id,
            )
            # Best-effort DB persistence
            try:
                if _collector and conn:
                    inv_id = conn.pending_invocations.pop(f"subagent:{name}", None)
                    if inv_id:
                        _collector.on_subagent_end(
                            inv_id,
                            status="error",
                            error_message=str(error)[:500],
                        )
            except Exception:
                log.debug("collector.on_subagent_end failed", exc_info=True)
            return

        # SUBAGENT_SELECTED — notify frontend when the SDK picks a subagent
        if (
            hasattr(SessionEventType, "SUBAGENT_SELECTED")
            and etype == SessionEventType.SUBAGENT_SELECTED
        ):
            name = getattr(d, "agent_name", "?") or "?"
            emit("subagent_selected", {"agent": str(name)})
            return

        # SUBAGENT_DESELECTED
        if (
            hasattr(SessionEventType, "SUBAGENT_DESELECTED")
            and etype == SessionEventType.SUBAGENT_DESELECTED
        ):
            name = getattr(d, "agent_name", "?") or "?"
            emit("subagent_deselected", {"agent": str(name)})
            return

        # -- Reasoning / intent events --------------------------------------

        if (
            hasattr(SessionEventType, "ASSISTANT_REASONING")
            and etype == SessionEventType.ASSISTANT_REASONING
        ):
            text = getattr(d, "reasoning_text", None) or ""
            if text:
                emit("assistant_reasoning", {"text": text[:2000]})
            return

        if (
            hasattr(SessionEventType, "ASSISTANT_INTENT")
            and etype == SessionEventType.ASSISTANT_INTENT
        ):
            intent = getattr(d, "intent", None) or ""
            if intent:
                emit("assistant_intent", {"intent": intent})
            return

        # -- Session lifecycle events ---------------------------------------

        if (
            hasattr(SessionEventType, "SESSION_HANDOFF")
            and etype == SessionEventType.SESSION_HANDOFF
        ):
            name = getattr(d, "agent_name", None) or "?"
            emit("session_handoff", {"agent": str(name)})
            return

        if (
            hasattr(SessionEventType, "ASSISTANT_TURN_START")
            and etype == SessionEventType.ASSISTANT_TURN_START
        ):
            emit("turn_started", {})
            return

        if (
            hasattr(SessionEventType, "ASSISTANT_TURN_END")
            and etype == SessionEventType.ASSISTANT_TURN_END
        ):
            emit("turn_ended", {})
            return

        # -- Usage / errors -------------------------------------------------

        if etype == SessionEventType.ASSISTANT_USAGE:
            input_t = getattr(d, "input_tokens", 0) or 0
            output_t = getattr(d, "output_tokens", 0) or 0
            cache_r = getattr(d, "cache_read_tokens", 0) or 0
            cache_w = getattr(d, "cache_write_tokens", 0) or 0
            model_name = getattr(d, "model", None) or ""
            from pricing import estimate_cost

            cost = estimate_cost(model_name, input_t, output_t)
            emit(
                "usage",
                {
                    "input_tokens": input_t,
                    "output_tokens": output_t,
                    "cache_read_tokens": cache_r,
                    "cache_write_tokens": cache_w,
                    "estimated_cost_usd": cost,
                },
            )
            # Best-effort DB persistence
            try:
                if _collector:
                    _collector.on_usage(
                        input_tokens=input_t,
                        output_tokens=output_t,
                        cache_read_tokens=cache_r,
                        cache_write_tokens=cache_w,
                        model=model_name,
                        session_id=session_id,
                    )
            except Exception:
                log.debug("collector.on_usage failed", exc_info=True)
            return

        if etype == SessionEventType.SESSION_ERROR:
            error_msg = getattr(d, "message", str(d))
            emit("error", {"message": str(error_msg)})
            return

        if (
            hasattr(SessionEventType, "SESSION_COMPACTION_START")
            and etype == SessionEventType.SESSION_COMPACTION_START
        ):
            emit("compaction_start", {})
            return

        if (
            hasattr(SessionEventType, "SESSION_COMPACTION_COMPLETE")
            and etype == SessionEventType.SESSION_COMPACTION_COMPLETE
        ):
            post = int(getattr(d, "post_compaction_tokens", 0) or 0)
            emit("compaction_complete", {"post_tokens": post})
            return

        # Catch-all for any unhandled event types
        log.debug("Unhandled session event type %s for session %s", etype, session_id)

    return _handler


def ws_reset(session_id: str | None = None) -> None:
    """Clear per-turn state when a new turn begins."""
    global _cancel_flag
    if session_id:
        conn = _connections.get(session_id)
        if conn:
            conn.reset_turn()
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
