"""Event collector - maps frontend events to EventStore operations.

The collector is frontend-agnostic: it maintains lightweight in-memory
state to track the current turn and pending invocations.
"""

from __future__ import annotations

import logging

from pricing import estimate_cost
from store import EventStore

log = logging.getLogger(__name__)


class EventCollector:
    """Maps high-level events (turn start, tool call, etc.) to
    :class:`EventStore` writes.
    """

    def __init__(self, store: EventStore) -> None:
        self._store = store
        self._current_turn_id: str | None = None
        self._current_session_id: str | None = None

    # ── Session lifecycle ─────────────────────────────────────────────────

    def on_session_created(
        self,
        session_id: str,
        *,
        agent: str = "",
        model: str = "",
        frontend: str = "cli",
        server_mode: str = "stdio",
    ) -> None:
        self._current_session_id = session_id
        self._store.start_session(
            session_id,
            agent=agent,
            model=model,
            frontend=frontend,
            server_mode=server_mode,
        )

    def on_session_ended(self, session_id: str, *, resumable: bool = False) -> None:
        self._store.end_session(session_id, resumable=resumable)
        if self._current_session_id == session_id:
            self._current_session_id = None
            self._current_turn_id = None

    # ── Turn lifecycle ────────────────────────────────────────────────────

    def on_turn_start(
        self,
        session_id: str,
        *,
        agent: str = "",
        model: str = "",
        user_prompt: str = "",
    ) -> str:
        """Record the start of a conversation turn.  Returns the turn ID."""
        turn_id = self._store.start_turn(
            session_id=session_id,
            agent=agent,
            model=model,
            user_prompt=user_prompt,
        )
        self._current_turn_id = turn_id
        self._current_session_id = session_id
        return turn_id

    def on_turn_end(
        self,
        turn_id: str,
        *,
        assistant_response: str = "",
        input_tokens: int = 0,
        output_tokens: int = 0,
        cache_read_tokens: int = 0,
        cache_write_tokens: int = 0,
        model: str = "",
        tool_call_count: int = 0,
        subagent_count: int = 0,
        status: str = "success",
    ) -> None:
        cost = estimate_cost(model, input_tokens, output_tokens)
        self._store.end_turn(
            turn_id,
            assistant_response=assistant_response,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cache_read_tokens=cache_read_tokens,
            cache_write_tokens=cache_write_tokens,
            estimated_cost_usd=cost,
            tool_call_count=tool_call_count,
            subagent_count=subagent_count,
            status=status,
        )
        # Update session counters using the actual stored values
        session_id = self._current_session_id
        if session_id:
            turn = self._store.get_turn(turn_id)
            actual_in = turn["input_tokens"] if turn else input_tokens
            actual_out = turn["output_tokens"] if turn else output_tokens
            self._store.update_session_counters(
                session_id,
                turn_count_delta=1,
                input_tokens_delta=actual_in,
                output_tokens_delta=actual_out,
            )
        if self._current_turn_id == turn_id:
            self._current_turn_id = None

    # ── Token usage update (mid-turn, from ASSISTANT_USAGE events) ────────

    def on_usage(
        self,
        *,
        input_tokens: int = 0,
        output_tokens: int = 0,
        cache_read_tokens: int = 0,
        cache_write_tokens: int = 0,
        model: str = "",
    ) -> None:
        """Record token usage for the current turn.

        Called when an ``ASSISTANT_USAGE`` event fires mid-stream.
        Overwrites (not increments) the turn's token fields.
        """
        turn_id = self._current_turn_id
        if not turn_id:
            return
        cost = estimate_cost(model, input_tokens, output_tokens)
        self._store._execute(
            "UPDATE turns SET "
            "input_tokens=?, output_tokens=?, cache_read_tokens=?, "
            "cache_write_tokens=?, estimated_cost_usd=? WHERE id=?",
            (input_tokens, output_tokens, cache_read_tokens, cache_write_tokens, cost, turn_id),
        )
        self._store._commit()

    # ── Tool invocations ──────────────────────────────────────────────────

    def on_tool_start(
        self,
        tool_name: str,
        args: str = "{}",
    ) -> str | None:
        """Record the start of a tool call.  Returns invocation ID."""
        turn_id = self._current_turn_id
        session_id = self._current_session_id
        if not turn_id or not session_id:
            return None
        inv_id = self._store.record_invocation(
            turn_id=turn_id,
            session_id=session_id,
            inv_type="tool_call",
            name=tool_name,
            input_data=args,
        )
        self._store.increment_turn_tool_count(turn_id)
        return inv_id

    def on_tool_end(
        self,
        invocation_id: str | None,
        *,
        output: str | None = None,
        status: str = "success",
        error_message: str | None = None,
    ) -> None:
        if not invocation_id:
            return
        self._store.complete_invocation(
            invocation_id,
            output=output,
            status=status,
            error_message=error_message,
        )

    # ── Subagent invocations ──────────────────────────────────────────────

    def on_subagent_start(self, agent_name: str) -> str | None:
        turn_id = self._current_turn_id
        session_id = self._current_session_id
        if not turn_id or not session_id:
            return None
        inv_id = self._store.record_invocation(
            turn_id=turn_id,
            session_id=session_id,
            inv_type="subagent",
            name=agent_name,
        )
        self._store.increment_turn_subagent_count(turn_id)
        return inv_id

    def on_subagent_end(
        self,
        invocation_id: str | None,
        *,
        status: str = "success",
        error_message: str | None = None,
    ) -> None:
        if not invocation_id:
            return
        self._store.complete_invocation(
            invocation_id,
            status=status,
            error_message=error_message,
        )
