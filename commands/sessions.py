"""/sessions command - list and inspect chat sessions."""

from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

import queries as q
from store import EventStore


def handle_sessions(
    arg: str,
    event_store: EventStore,
    console: Console,
    *,
    current_session_id: str | None = None,
) -> str | None:
    """Dispatch ``/sessions`` and its subcommands.

    Returns ``_CURRENT_SESSION_ENDED`` if the user killed the current session,
    so the caller can recreate it.
    """
    parts = arg.split() if arg else []

    if not parts:
        _list_sessions(event_store, console, current_session_id=current_session_id)
    elif parts[0] == "all":
        _list_sessions(
            event_store, console, current_session_id=current_session_id,
            show_all=True,
        )
    elif parts[0] == "end" and len(parts) > 1:
        return _end_session(
            parts[1], event_store, console, current_session_id=current_session_id,
        )
    elif parts[0] == "name":
        _name_session(
            parts[1:], event_store, console,
            current_session_id=current_session_id,
        )
    elif parts[0] == "cleanup":
        _cleanup_sessions(event_store, console, current_session_id=current_session_id)
    elif len(parts) == 1:
        _show_session(parts[0], event_store, console)
    elif len(parts) >= 2 and parts[1] == "turn":
        turn_num = parts[2] if len(parts) > 2 else None
        _show_session_turn(parts[0], turn_num, event_store, console)
    elif len(parts) >= 2 and parts[1] == "invocations":
        _show_session_invocations(parts[0], event_store, console)
    else:
        _show_session(parts[0], event_store, console)
    return None


def _list_sessions(
    store: EventStore,
    console: Console,
    *,
    current_session_id: str | None = None,
    show_all: bool = False,
) -> None:
    sessions = q.list_sessions(store, limit=30)
    if not show_all:
        sessions = [
            s for s in sessions
            if s["status"] == "active" or s.get("resumable")
        ]
    if not sessions:
        console.print("  [dim]No sessions found.[/dim]")
        return

    table = Table(box=None, padding=(0, 1), show_edge=False)
    table.add_column("", max_width=1)
    table.add_column("ID", style="cyan", max_width=14)
    table.add_column("Name", style="#58a6ff", max_width=16)
    table.add_column("Agent", style="#00d4ff")
    table.add_column("Model", style="dim")
    table.add_column("Started", style="dim")
    table.add_column("Turns", justify="right")
    table.add_column("Tokens (in/out)", justify="right")
    table.add_column("Status", style="bold")

    for s in sessions:
        is_current = s["id"] == current_session_id
        marker = "[bold green]\u25b6[/bold green]" if is_current else ""
        sid = s["id"][:12] + "..."
        if is_current:
            sid = f"[bold cyan]{sid}[/bold cyan]"
        nick = s.get("nickname") or ""
        started = s.get("started_at", "")[:19]
        tokens = f"{s.get('total_input_tokens', 0)}/{s.get('total_output_tokens', 0)}"
        status_style = "green" if s["status"] == "active" else "dim"
        table.add_row(
            marker, sid, nick,
            s.get("agent", ""), s.get("model", ""),
            started, str(s.get("turn_count", 0)), tokens,
            f"[{status_style}]{s['status']}[/{status_style}]",
        )

    console.print()
    console.print("  [bold]Sessions[/bold]")
    console.print(table)
    console.print()


def _show_session(session_id: str, store: EventStore, console: Console) -> None:
    full_id = _resolve_session_id(session_id, store)
    if not full_id:
        console.print(f"  [red]Session '{session_id}' not found.[/red]")
        return

    detail = q.get_session_detail(store, full_id)
    if not detail:
        console.print(f"  [red]Session '{session_id}' not found.[/red]")
        return

    console.print()
    console.print(f"  [bold]Session[/bold] [cyan]{detail['id'][:12]}...[/cyan]")
    if detail.get("nickname"):
        console.print(f"  [dim]Name:[/dim] {detail['nickname']}")
    console.print(f"  [dim]Agent:[/dim] {detail.get('agent', '')}")
    console.print(f"  [dim]Model:[/dim] {detail.get('model', '')}")
    console.print(f"  [dim]Status:[/dim] {detail.get('status', '')}")
    console.print(f"  [dim]Started:[/dim] {detail.get('started_at', '')[:19]}")
    if detail.get("ended_at"):
        console.print(f"  [dim]Ended:[/dim] {detail['ended_at'][:19]}")
    console.print(
        f"  [dim]Tokens:[/dim] {detail.get('total_input_tokens', 0)} in / "
        f"{detail.get('total_output_tokens', 0)} out"
    )
    console.print()

    turns = detail.get("turns", [])
    if turns:
        table = Table(box=None, padding=(0, 1), show_edge=False)
        table.add_column("#", justify="right", style="bold")
        table.add_column("Agent", style="#00d4ff")
        table.add_column("Prompt", max_width=40)
        table.add_column("Tokens", justify="right")
        table.add_column("Cost", justify="right", style="green")
        table.add_column("Tools", justify="right")

        for t in turns:
            prompt_preview = t.get("user_prompt", "")[:40]
            tokens = f"{t.get('input_tokens', 0)}/{t.get('output_tokens', 0)}"
            cost = f"${t.get('estimated_cost_usd', 0):.4f}"
            table.add_row(
                str(t.get("turn_number", "")), t.get("agent", ""),
                prompt_preview, tokens, cost,
                str(t.get("tool_call_count", 0)),
            )
        console.print("  [bold]Turns[/bold]")
        console.print(table)
    console.print()


def _show_session_turn(
    session_id: str, turn_num: str | None, store: EventStore, console: Console
) -> None:
    full_id = _resolve_session_id(session_id, store)
    if not full_id:
        console.print(f"  [red]Session '{session_id}' not found.[/red]")
        return

    turns = store.get_turns(full_id)
    if not turns:
        console.print("  [dim]No turns in this session.[/dim]")
        return

    if turn_num:
        try:
            n = int(turn_num)
        except ValueError:
            console.print(f"  [red]Invalid turn number: {turn_num}[/red]")
            return
        turn = next((t for t in turns if t["turn_number"] == n), None)
        if not turn:
            console.print(f"  [red]Turn {n} not found.[/red]")
            return
        _render_turn_detail(turn, store, console)
    else:
        console.print("  [yellow]Usage: /sessions <id> turn <number>[/yellow]")


def _show_session_invocations(session_id: str, store: EventStore, console: Console) -> None:
    full_id = _resolve_session_id(session_id, store)
    if not full_id:
        console.print(f"  [red]Session '{session_id}' not found.[/red]")
        return

    invs = q.get_session_invocations(store, full_id)
    if not invs:
        console.print("  [dim]No invocations in this session.[/dim]")
        return

    table = Table(box=None, padding=(0, 1), show_edge=False)
    table.add_column("ID", style="cyan", max_width=14)
    table.add_column("Type", style="#0066ee")
    table.add_column("Name", style="#00d4ff")
    table.add_column("Duration", justify="right")
    table.add_column("Status")

    for inv in invs:
        iid = inv["id"][:12] + "..."
        dur = f"{inv.get('duration_ms', 0)}ms"
        status_style = "green" if inv["status"] == "success" else "red"
        table.add_row(
            iid, inv["type"], inv["name"], dur,
            f"[{status_style}]{inv['status']}[/{status_style}]",
        )

    console.print()
    console.print("  [bold]Invocations[/bold]")
    console.print(table)
    console.print()


def _render_turn_detail(turn: dict, store: EventStore, console: Console) -> None:
    detail = q.get_turn_detail(store, turn["id"])
    if not detail:
        return

    console.print()
    console.print(f"  [bold]Turn {detail['turn_number']}[/bold]")
    console.print(f"  [dim]Agent:[/dim] {detail.get('agent', '')}")
    console.print(f"  [dim]Model:[/dim] {detail.get('model', '')}")
    console.print(f"  [dim]Status:[/dim] {detail.get('status', '')}")
    console.print(
        f"  [dim]Tokens:[/dim] {detail.get('input_tokens', 0)} in / "
        f"{detail.get('output_tokens', 0)} out"
    )
    console.print(f"  [dim]Cost:[/dim] ${detail.get('estimated_cost_usd', 0):.4f}")
    console.print(f"  [dim]Duration:[/dim] {detail.get('duration_ms', 0)}ms")

    console.print()
    prompt = detail.get("user_prompt", "")
    if prompt:
        console.print(Panel(prompt, title="User Prompt", border_style="dim", width=80))

    response = detail.get("assistant_response", "")
    if response:
        preview = response[:2000] + "..." if len(response) > 2000 else response
        console.print(Panel(preview, title="Response", border_style="dim", width=80))

    invocations = detail.get("invocations", [])
    if invocations:
        table = Table(box=None, padding=(0, 1), show_edge=False)
        table.add_column("ID", style="cyan", max_width=14)
        table.add_column("Type", style="#0066ee")
        table.add_column("Name", style="#00d4ff")
        table.add_column("Duration", justify="right")
        table.add_column("Status")

        for inv in invocations:
            iid = inv["id"][:12] + "..."
            dur = f"{inv.get('duration_ms', 0)}ms"
            status_style = "green" if inv["status"] == "success" else "red"
            table.add_row(
                iid, inv["type"], inv["name"], dur,
                f"[{status_style}]{inv['status']}[/{status_style}]",
            )
        console.print()
        console.print("  [bold]Invocations[/bold]")
        console.print(table)
    console.print()


def _resolve_session_id(prefix: str, store: EventStore) -> str | None:
    return store.resolve_prefix("sessions", prefix)


# ── Name ──────────────────────────────────────────────────────────────────


def _name_session(
    parts: list[str],
    store: EventStore,
    console: Console,
    *,
    current_session_id: str | None = None,
) -> None:
    if not parts:
        console.print("  [yellow]Usage: /sessions name [id] <nickname>[/yellow]")
        return

    if len(parts) == 1:
        resolved = _resolve_session_id(parts[0], store)
        if resolved:
            store.set_nickname(resolved, None)
            console.print(
                f"  [green]OK[/green] Cleared nickname for session "
                f"[cyan]{resolved[:12]}...[/cyan]."
            )
            return
        if not current_session_id:
            console.print("  [red]No active session to name.[/red]")
            return
        try:
            store.set_nickname(current_session_id, parts[0])
        except ValueError as exc:
            console.print(f"  [red]{exc}[/red]")
            return
        console.print(
            f"  [green]OK[/green] Session [cyan]{current_session_id[:12]}...[/cyan] "
            f"named [#58a6ff]{parts[0].lower()}[/#58a6ff]."
        )
    else:
        full_id = _resolve_session_id(parts[0], store)
        if not full_id:
            console.print(f"  [red]Session '{parts[0]}' not found.[/red]")
            return
        try:
            store.set_nickname(full_id, parts[1])
        except ValueError as exc:
            console.print(f"  [red]{exc}[/red]")
            return
        console.print(
            f"  [green]OK[/green] Session [cyan]{full_id[:12]}...[/cyan] "
            f"named [#58a6ff]{parts[1].lower()}[/#58a6ff]."
        )


# ── End / Cleanup ─────────────────────────────────────────────────────────

_CURRENT_SESSION_ENDED = "__current__"


def _end_session(
    session_id: str,
    store: EventStore,
    console: Console,
    *,
    current_session_id: str | None = None,
) -> str | None:
    full_id = _resolve_session_id(session_id, store)
    if not full_id:
        console.print(f"  [red]Session '{session_id}' not found.[/red]")
        return None
    s = store.get_session(full_id)
    if not s or s["status"] != "active":
        console.print(f"  [dim]Session '{session_id}' is already ended.[/dim]")
        return None
    store.end_session(full_id, resumable=False)
    console.print(f"  [green]OK[/green] Session [cyan]{full_id[:12]}...[/cyan] ended.")
    if full_id == current_session_id:
        return _CURRENT_SESSION_ENDED
    return None


def _cleanup_sessions(
    store: EventStore,
    console: Console,
    *,
    current_session_id: str | None = None,
) -> None:
    count = store.end_all_active_except(current_session_id)
    if count:
        console.print(
            f"  [green]OK[/green] Ended {count} orphaned session{'s' if count != 1 else ''}."
        )
    else:
        console.print("  [dim]No orphaned sessions to clean up.[/dim]")
