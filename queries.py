"""Shared query and aggregation logic for observability data.

All functions accept an :class:`EventStore` as first argument and return
plain dicts or lists.  No Rich, no HTML, no formatting - frontends
decide how to present the data.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from store import EventStore

# ── Sessions ──────────────────────────────────────────────────────────────


def list_sessions(
    store: EventStore,
    *,
    agent: str | None = None,
    since: str | None = None,
    status: str | None = None,
    frontend: str | None = None,
    limit: int = 50,
) -> list[dict]:
    """Return recent sessions, newest first."""
    return store.list_sessions(
        agent=agent, since=since, status=status, frontend=frontend, limit=limit
    )


def get_session_detail(store: EventStore, session_id: str) -> dict | None:
    """Session metadata + list of turns (without full response text)."""
    session = store.get_session(session_id)
    if not session:
        return None
    turns = store.get_turns(session_id)
    for t in turns:
        resp = t.get("assistant_response", "")
        t["response_preview"] = resp[:200] + "..." if len(resp) > 200 else resp
    session["turns"] = turns
    return session


def get_turn_detail(store: EventStore, turn_id: str) -> dict | None:
    """Full turn data including invocations."""
    turn = store.get_turn(turn_id)
    if not turn:
        return None
    turn["invocations"] = store.get_invocations_for_turn(turn_id)
    return turn


def get_session_invocations(store: EventStore, session_id: str) -> list[dict]:
    """All invocations across all turns for a session."""
    return store.get_invocations_for_session(session_id)


def get_invocation_detail(store: EventStore, invocation_id: str) -> dict | None:
    """Full detail of a single invocation."""
    return store.get_invocation(invocation_id)


def get_resumable_sessions(
    store: EventStore, *, frontend: str | None = None
) -> list[dict]:
    """Sessions that can potentially be resumed."""
    sessions = store.list_sessions(status="ended", frontend=frontend, limit=100)
    return [s for s in sessions if s.get("resumable")]


# ── Usage / Cost ──────────────────────────────────────────────────────────


def _period_cutoff(period: str | None) -> str | None:
    """Convert a period name to an ISO cutoff timestamp."""
    if not period or period == "all":
        return None
    now = datetime.now(UTC)
    deltas = {
        "today": timedelta(days=1),
        "week": timedelta(weeks=1),
        "month": timedelta(days=30),
    }
    delta = deltas.get(period)
    if not delta:
        return None
    return (now - delta).isoformat()


def usage_summary(
    store: EventStore,
    *,
    agent: str | None = None,
    model: str | None = None,
    period: str | None = None,
) -> dict:
    """Aggregate token usage and estimated cost."""
    cutoff = _period_cutoff(period)

    clauses: list[str] = []
    params: list[str] = []
    if agent:
        clauses.append("agent=?")
        params.append(agent)
    if model:
        clauses.append("model=?")
        params.append(model)
    if cutoff:
        clauses.append("started_at>=?")
        params.append(cutoff)
    where = " AND ".join(clauses) if clauses else "1=1"

    row = store._fetchone(
        f"SELECT "
        f"COALESCE(SUM(input_tokens), 0) AS total_input_tokens, "
        f"COALESCE(SUM(output_tokens), 0) AS total_output_tokens, "
        f"COALESCE(SUM(estimated_cost_usd), 0.0) AS total_cost_usd, "
        f"COUNT(*) AS turn_count "
        f"FROM turns WHERE {where}",
        tuple(params),
    )
    result = dict(row) if row else {
        "total_input_tokens": 0,
        "total_output_tokens": 0,
        "total_cost_usd": 0.0,
        "turn_count": 0,
    }
    result["by_agent"] = usage_by_agent(store, period=period)
    result["by_model"] = usage_by_model(store, period=period)
    return result


def usage_by_agent(store: EventStore, *, period: str | None = None) -> list[dict]:
    """Token usage grouped by agent."""
    cutoff = _period_cutoff(period)
    where = "started_at>=?" if cutoff else "1=1"
    params = (cutoff,) if cutoff else ()
    return store._fetchall(
        f"SELECT agent, "
        f"COALESCE(SUM(input_tokens), 0) AS input_tokens, "
        f"COALESCE(SUM(output_tokens), 0) AS output_tokens, "
        f"COALESCE(SUM(estimated_cost_usd), 0.0) AS cost_usd, "
        f"COUNT(*) AS turn_count "
        f"FROM turns WHERE {where} "
        f"GROUP BY agent ORDER BY cost_usd DESC",
        params,
    )


def usage_by_model(store: EventStore, *, period: str | None = None) -> list[dict]:
    """Token usage grouped by model."""
    cutoff = _period_cutoff(period)
    where = "started_at>=?" if cutoff else "1=1"
    params = (cutoff,) if cutoff else ()
    return store._fetchall(
        f"SELECT model, "
        f"COALESCE(SUM(input_tokens), 0) AS input_tokens, "
        f"COALESCE(SUM(output_tokens), 0) AS output_tokens, "
        f"COALESCE(SUM(estimated_cost_usd), 0.0) AS cost_usd, "
        f"COUNT(*) AS turn_count "
        f"FROM turns WHERE {where} "
        f"GROUP BY model ORDER BY cost_usd DESC",
        params,
    )
