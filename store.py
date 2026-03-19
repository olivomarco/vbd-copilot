"""SQLite-backed event store for VBD-Copilot observability.

Manages three tables:
  - ``sessions`` - chat sessions
  - ``turns`` - conversation turns within sessions
  - ``invocations`` - tool calls and subagent dispatches within turns

Uses WAL mode for concurrent reader/writer access.
"""

from __future__ import annotations

import re
import sqlite3
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _new_id(length: int = 12) -> str:
    return uuid.uuid4().hex[:length]


_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS sessions (
    id              TEXT PRIMARY KEY,
    agent           TEXT NOT NULL DEFAULT '',
    model           TEXT NOT NULL DEFAULT '',
    started_at      TEXT NOT NULL,
    ended_at        TEXT,
    status          TEXT NOT NULL DEFAULT 'active',
    frontend        TEXT NOT NULL DEFAULT 'cli',
    summary         TEXT,
    nickname        TEXT,
    turn_count      INTEGER NOT NULL DEFAULT 0,
    total_input_tokens  INTEGER NOT NULL DEFAULT 0,
    total_output_tokens INTEGER NOT NULL DEFAULT 0,
    server_mode     TEXT NOT NULL DEFAULT 'stdio',
    resumable       INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS turns (
    id              TEXT PRIMARY KEY,
    session_id      TEXT NOT NULL REFERENCES sessions(id),
    turn_number     INTEGER NOT NULL DEFAULT 0,
    agent           TEXT NOT NULL DEFAULT '',
    model           TEXT NOT NULL DEFAULT '',
    user_prompt     TEXT NOT NULL DEFAULT '',
    assistant_response TEXT NOT NULL DEFAULT '',
    started_at      TEXT NOT NULL,
    ended_at        TEXT,
    duration_ms     INTEGER NOT NULL DEFAULT 0,
    input_tokens    INTEGER NOT NULL DEFAULT 0,
    output_tokens   INTEGER NOT NULL DEFAULT 0,
    cache_read_tokens  INTEGER NOT NULL DEFAULT 0,
    cache_write_tokens INTEGER NOT NULL DEFAULT 0,
    estimated_cost_usd REAL NOT NULL DEFAULT 0.0,
    tool_call_count INTEGER NOT NULL DEFAULT 0,
    subagent_count  INTEGER NOT NULL DEFAULT 0,
    status          TEXT NOT NULL DEFAULT 'in_progress'
);

CREATE TABLE IF NOT EXISTS invocations (
    id              TEXT PRIMARY KEY,
    turn_id         TEXT NOT NULL REFERENCES turns(id),
    session_id      TEXT NOT NULL REFERENCES sessions(id),
    type            TEXT NOT NULL,
    name            TEXT NOT NULL DEFAULT '',
    input           TEXT NOT NULL DEFAULT '{}',
    output          TEXT,
    started_at      TEXT NOT NULL,
    ended_at        TEXT,
    duration_ms     INTEGER NOT NULL DEFAULT 0,
    status          TEXT NOT NULL DEFAULT 'in_progress',
    error_message   TEXT
);
"""

_INDEX_SQL = """
CREATE INDEX IF NOT EXISTS idx_turns_session ON turns(session_id);
CREATE INDEX IF NOT EXISTS idx_invocations_turn ON invocations(turn_id);
CREATE INDEX IF NOT EXISTS idx_invocations_session ON invocations(session_id);
CREATE INDEX IF NOT EXISTS idx_sessions_status ON sessions(status);
CREATE UNIQUE INDEX IF NOT EXISTS idx_sessions_nickname
    ON sessions(nickname) WHERE nickname IS NOT NULL;
"""

_MIGRATIONS: list[str] = [
    "ALTER TABLE sessions ADD COLUMN nickname TEXT",
]


class EventStore:
    """SQLite-backed persistence for VBD-Copilot observability data.

    Parameters
    ----------
    db_path:
        Path to the SQLite database file.  Created if it does not exist.
    retention_days:
        Auto-purge observability data older than this many days on open.
        Set to 0 to disable.
    """

    def __init__(self, db_path: Path, *, retention_days: int = 90) -> None:
        self._db_path = db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.row_factory = sqlite3.Row
        self._init_schema()
        if retention_days > 0:
            self.cleanup_old(retention_days)

    def _init_schema(self) -> None:
        self._conn.executescript(_SCHEMA_SQL)
        self._apply_migrations()
        self._conn.executescript(_INDEX_SQL)

    def _apply_migrations(self) -> None:
        """Run best-effort schema migrations for existing databases."""
        for stmt in _MIGRATIONS:
            try:
                self._conn.execute(stmt)
                self._conn.commit()
            except sqlite3.OperationalError:
                pass  # column/index already exists

    def close(self) -> None:
        self._conn.close()

    # ── helpers ───────────────────────────────────────────────────────────

    def _execute(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        return self._conn.execute(sql, params)

    def _commit(self) -> None:
        self._conn.commit()

    def _fetchone(self, sql: str, params: tuple = ()) -> dict | None:
        row = self._execute(sql, params).fetchone()
        return dict(row) if row else None

    def _fetchall(self, sql: str, params: tuple = ()) -> list[dict]:
        return [dict(r) for r in self._execute(sql, params).fetchall()]

    # ── Sessions ──────────────────────────────────────────────────────────

    def start_session(
        self,
        session_id: str,
        *,
        agent: str = "",
        model: str = "",
        frontend: str = "cli",
        server_mode: str = "stdio",
    ) -> None:
        self._execute(
            "INSERT OR REPLACE INTO sessions "
            "(id, agent, model, started_at, status, frontend, server_mode) "
            "VALUES (?, ?, ?, ?, 'active', ?, ?)",
            (session_id, agent, model, _now_iso(), frontend, server_mode),
        )
        self._commit()

    def end_session(self, session_id: str, *, resumable: bool = False) -> None:
        self._execute(
            "UPDATE sessions SET ended_at=?, status='ended', resumable=? WHERE id=?",
            (_now_iso(), int(resumable), session_id),
        )
        self._commit()

    def reactivate_session(self, session_id: str) -> None:
        """Re-open an ended session (for /resume)."""
        self._execute(
            "UPDATE sessions SET status='active', ended_at=NULL, resumable=0 WHERE id=?",
            (session_id,),
        )
        self._commit()

    def end_all_active_except(self, current_session_id: str | None) -> int:
        """End all active sessions except *current_session_id*.

        Marks them as resumable so they can still be resumed later.
        Returns the number of sessions ended.
        """
        if current_session_id:
            cur = self._execute(
                "UPDATE sessions SET ended_at=?, status='ended', resumable=1 "
                "WHERE status='active' AND id!=?",
                (_now_iso(), current_session_id),
            )
        else:
            cur = self._execute(
                "UPDATE sessions SET ended_at=?, status='ended', resumable=1 "
                "WHERE status='active'",
                (_now_iso(),),
            )
        self._commit()
        return cur.rowcount

    def get_session(self, session_id: str) -> dict | None:
        return self._fetchone("SELECT * FROM sessions WHERE id=?", (session_id,))

    def resolve_prefix(
        self, table: str, prefix: str
    ) -> str | None:
        """Resolve an ID prefix to a full ID in the given table.

        Returns the full ID if exactly one row matches, else ``None``.
        """
        if table not in {"sessions", "turns", "invocations"}:
            return None
        # Try exact match first
        row = self._fetchone(
            f"SELECT id FROM {table} WHERE id=?",
            (prefix,),
        )
        if row:
            return row["id"]
        # Prefix match via LIKE (prefix is sanitised by parameterised query)
        rows = self._fetchall(
            f"SELECT id FROM {table} WHERE id LIKE ? LIMIT 2",
            (prefix + "%",),
        )
        if len(rows) == 1:
            return rows[0]["id"]
        # Nickname match (sessions only)
        if table == "sessions":
            row = self._fetchone(
                "SELECT id FROM sessions WHERE nickname=?",
                (prefix.lower(),),
            )
            if row:
                return row["id"]
        return None

    def list_sessions(
        self,
        *,
        agent: str | None = None,
        since: str | None = None,
        status: str | None = None,
        frontend: str | None = None,
        limit: int = 50,
    ) -> list[dict]:
        clauses: list[str] = []
        params: list[str | int] = []
        if agent:
            clauses.append("agent=?")
            params.append(agent)
        if since:
            clauses.append("started_at>=?")
            params.append(since)
        if status:
            clauses.append("status=?")
            params.append(status)
        if frontend:
            clauses.append("frontend=?")
            params.append(frontend)
        where = " AND ".join(clauses) if clauses else "1=1"
        params.append(limit)
        return self._fetchall(
            f"SELECT * FROM sessions WHERE {where} ORDER BY started_at DESC LIMIT ?",
            tuple(params),
        )

    def update_session_counters(
        self,
        session_id: str,
        *,
        turn_count_delta: int = 0,
        input_tokens_delta: int = 0,
        output_tokens_delta: int = 0,
    ) -> None:
        self._execute(
            "UPDATE sessions SET "
            "turn_count = turn_count + ?, "
            "total_input_tokens = total_input_tokens + ?, "
            "total_output_tokens = total_output_tokens + ? "
            "WHERE id=?",
            (turn_count_delta, input_tokens_delta, output_tokens_delta, session_id),
        )
        self._commit()

    def update_session_model(self, session_id: str, model: str) -> None:
        self._execute(
            "UPDATE sessions SET model=? WHERE id=?",
            (model, session_id),
        )
        self._commit()

    def set_nickname(
        self, session_id: str, nickname: str | None
    ) -> None:
        """Set or clear a session nickname.

        Raises ``ValueError`` on invalid format or duplicate.
        """
        if nickname is not None:
            nickname = nickname.strip().lower()
            if not nickname:
                nickname = None
            elif len(nickname) > 30 or not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", nickname):
                raise ValueError(
                    "Nickname must be 1-30 chars: lowercase letters, digits, "
                    "hyphens, underscores (must start with letter/digit)."
                )
            elif nickname is not None:
                existing = self._fetchone(
                    "SELECT id FROM sessions WHERE nickname=? AND id!=?",
                    (nickname, session_id),
                )
                if existing:
                    raise ValueError(
                        f"Nickname '{nickname}' is already used by session "
                        f"{existing['id'][:12]}..."
                    )
        self._execute(
            "UPDATE sessions SET nickname=? WHERE id=?",
            (nickname, session_id),
        )
        self._commit()

    def update_session_agent(self, session_id: str, agent: str) -> None:
        self._execute(
            "UPDATE sessions SET agent=? WHERE id=?",
            (agent, session_id),
        )
        self._commit()

    # ── Turns ─────────────────────────────────────────────────────────────

    def start_turn(
        self,
        *,
        session_id: str,
        agent: str = "",
        model: str = "",
        user_prompt: str = "",
    ) -> str:
        turn_id = _new_id()
        turn_number = (
            self._execute(
                "SELECT COALESCE(MAX(turn_number), 0) FROM turns WHERE session_id=?",
                (session_id,),
            ).fetchone()[0]
            + 1
        )
        self._execute(
            "INSERT INTO turns "
            "(id, session_id, turn_number, agent, model, user_prompt, started_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (turn_id, session_id, turn_number, agent, model, user_prompt, _now_iso()),
        )
        self._commit()
        return turn_id

    def end_turn(
        self,
        turn_id: str,
        *,
        assistant_response: str = "",
        input_tokens: int = 0,
        output_tokens: int = 0,
        cache_read_tokens: int = 0,
        cache_write_tokens: int = 0,
        estimated_cost_usd: float = 0.0,
        tool_call_count: int = 0,
        subagent_count: int = 0,
        status: str = "success",
    ) -> None:
        now = _now_iso()
        row = self._fetchone(
            "SELECT started_at, input_tokens, output_tokens, "
            "cache_read_tokens, cache_write_tokens, estimated_cost_usd, "
            "tool_call_count, subagent_count FROM turns WHERE id=?",
            (turn_id,),
        )
        duration_ms = 0
        if row:
            started = datetime.fromisoformat(row["started_at"])
            duration_ms = int((datetime.now(UTC) - started).total_seconds() * 1000)
            # Preserve values already written by on_usage / increment helpers
            if input_tokens == 0 and output_tokens == 0:
                input_tokens = row["input_tokens"]
                output_tokens = row["output_tokens"]
                cache_read_tokens = cache_read_tokens or row["cache_read_tokens"]
                cache_write_tokens = cache_write_tokens or row["cache_write_tokens"]
                estimated_cost_usd = estimated_cost_usd or row["estimated_cost_usd"]
            if tool_call_count == 0:
                tool_call_count = row["tool_call_count"]
            if subagent_count == 0:
                subagent_count = row["subagent_count"]
        self._execute(
            "UPDATE turns SET "
            "assistant_response=?, ended_at=?, duration_ms=?, "
            "input_tokens=?, output_tokens=?, cache_read_tokens=?, cache_write_tokens=?, "
            "estimated_cost_usd=?, tool_call_count=?, subagent_count=?, status=? "
            "WHERE id=?",
            (
                assistant_response, now, duration_ms,
                input_tokens, output_tokens, cache_read_tokens, cache_write_tokens,
                estimated_cost_usd, tool_call_count, subagent_count, status,
                turn_id,
            ),
        )
        self._commit()

    def get_turn(self, turn_id: str) -> dict | None:
        return self._fetchone("SELECT * FROM turns WHERE id=?", (turn_id,))

    def get_turns(self, session_id: str) -> list[dict]:
        return self._fetchall(
            "SELECT * FROM turns WHERE session_id=? ORDER BY turn_number",
            (session_id,),
        )

    def increment_turn_tool_count(self, turn_id: str) -> None:
        self._execute(
            "UPDATE turns SET tool_call_count = tool_call_count + 1 WHERE id=?",
            (turn_id,),
        )
        self._commit()

    def increment_turn_subagent_count(self, turn_id: str) -> None:
        self._execute(
            "UPDATE turns SET subagent_count = subagent_count + 1 WHERE id=?",
            (turn_id,),
        )
        self._commit()

    # ── Invocations ───────────────────────────────────────────────────────

    def record_invocation(
        self,
        *,
        turn_id: str,
        session_id: str,
        inv_type: str,
        name: str = "",
        input_data: str = "{}",
    ) -> str:
        inv_id = _new_id()
        self._execute(
            "INSERT INTO invocations "
            "(id, turn_id, session_id, type, name, input, started_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (inv_id, turn_id, session_id, inv_type, name, input_data, _now_iso()),
        )
        self._commit()
        return inv_id

    def complete_invocation(
        self,
        invocation_id: str,
        *,
        output: str | None = None,
        status: str = "success",
        error_message: str | None = None,
    ) -> None:
        now = _now_iso()
        row = self._fetchone(
            "SELECT started_at FROM invocations WHERE id=?", (invocation_id,)
        )
        duration_ms = 0
        if row:
            started = datetime.fromisoformat(row["started_at"])
            duration_ms = int((datetime.now(UTC) - started).total_seconds() * 1000)
        self._execute(
            "UPDATE invocations SET ended_at=?, duration_ms=?, output=?, status=?, error_message=? "
            "WHERE id=?",
            (now, duration_ms, output, status, error_message, invocation_id),
        )
        self._commit()

    def get_invocation(self, invocation_id: str) -> dict | None:
        return self._fetchone(
            "SELECT * FROM invocations WHERE id=?", (invocation_id,)
        )

    def get_invocations_for_turn(self, turn_id: str) -> list[dict]:
        return self._fetchall(
            "SELECT * FROM invocations WHERE turn_id=? ORDER BY started_at",
            (turn_id,),
        )

    def get_invocations_for_session(self, session_id: str) -> list[dict]:
        return self._fetchall(
            "SELECT * FROM invocations WHERE session_id=? ORDER BY started_at",
            (session_id,),
        )

    # ── Cleanup ───────────────────────────────────────────────────────────

    def cleanup_old(self, retention_days: int) -> None:
        """Purge observability data older than *retention_days*."""
        cutoff_iso = (datetime.now(UTC) - timedelta(days=retention_days)).isoformat()

        # Delete invocations for old turns
        self._execute(
            "DELETE FROM invocations WHERE session_id IN "
            "(SELECT id FROM sessions WHERE started_at < ?)",
            (cutoff_iso,),
        )
        # Delete old turns
        self._execute(
            "DELETE FROM turns WHERE session_id IN "
            "(SELECT id FROM sessions WHERE started_at < ?)",
            (cutoff_iso,),
        )
        # Delete old sessions
        self._execute(
            "DELETE FROM sessions WHERE started_at < ?", (cutoff_iso,)
        )
        self._commit()
