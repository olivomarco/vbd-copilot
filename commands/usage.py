"""/usage command - token usage and cost aggregation."""

from __future__ import annotations

from rich.console import Console
from rich.table import Table

import queries as q
from store import EventStore


def handle_usage(
    arg: str,
    event_store: EventStore,
    console: Console,
    *,
    session_id: str | None = None,
    current_agent: str | None = None,
    current_model: str | None = None,
    last_input_tokens: int = 0,
    model_limits: dict[str, int] | None = None,
) -> None:
    """Dispatch ``/usage`` command."""
    parts = arg.split() if arg else []

    if not parts and session_id:
        _show_session_usage(
            session_id,
            event_store,
            console,
            current_agent=current_agent,
            current_model=current_model,
            last_input_tokens=last_input_tokens,
            model_limits=model_limits or {},
        )
        return

    agent = None
    model = None
    period = None

    i = 0
    while i < len(parts):
        if parts[i] == "--agent" and i + 1 < len(parts):
            agent = parts[i + 1]
            i += 2
        elif parts[i] == "--model" and i + 1 < len(parts):
            model = parts[i + 1]
            i += 2
        elif parts[i] == "--period" and i + 1 < len(parts):
            period = parts[i + 1]
            i += 2
        elif parts[i] in ("today", "week", "month", "all"):
            period = parts[i]
            i += 1
        else:
            i += 1

    _show_global_usage(event_store, console, agent=agent, model=model, period=period)


def _show_session_usage(
    session_id: str,
    store: EventStore,
    console: Console,
    *,
    current_agent: str | None = None,
    current_model: str | None = None,
    last_input_tokens: int = 0,
    model_limits: dict[str, int] | None = None,
) -> None:
    s = store.get_session(session_id)
    console.print()
    console.print("  [bold]Current Session[/bold]")
    console.print(f"  [dim]Session ID:[/dim]  [cyan]{session_id}[/cyan]")
    console.print(f"  [dim]Agent:[/dim]       [#00d4ff]{current_agent or '?'}[/#00d4ff]")
    console.print(f"  [dim]Model:[/dim]       {current_model or '?'}")

    turns = s.get("turn_count", 0) if s else 0
    in_tok = s.get("total_input_tokens", 0) if s else 0
    out_tok = s.get("total_output_tokens", 0) if s else 0

    from pricing import estimate_cost

    cost = estimate_cost(current_model or "", in_tok, out_tok)
    console.print(f"  [dim]Turns:[/dim]       {turns}")
    console.print(f"  [dim]Tokens:[/dim]      {in_tok:,} in / {out_tok:,} out")
    console.print(f"  [dim]Est. cost:[/dim]   ${cost:.4f}")

    limits = model_limits or {}
    max_ctx = limits.get(current_model or "", 0)
    ctx_used = last_input_tokens

    console.print()
    console.print("  [bold]Context Window[/bold]")
    if max_ctx > 0 and ctx_used > 0:
        pct = min(ctx_used / max_ctx * 100, 100.0)
        remaining = max(max_ctx - ctx_used, 0)
        bar_width = 30
        filled = int(pct / 100 * bar_width)
        bar_color = "green" if pct < 70 else ("yellow" if pct < 90 else "red")
        bar = f"[{bar_color}]{'█' * filled}[/{bar_color}][dim]{'░' * (bar_width - filled)}[/dim]"
        console.print(f"  {bar} {pct:.0f}%")
        console.print(f"  [dim]Used:[/dim]        {ctx_used:,} tokens")
        console.print(f"  [dim]Capacity:[/dim]    {max_ctx:,} tokens")
        console.print(f"  [dim]Remaining:[/dim]   {remaining:,} tokens")
    elif max_ctx > 0:
        console.print(f"  [dim]Capacity:[/dim]    {max_ctx:,} tokens")
        console.print("  [dim]Used:[/dim]        [dim italic]no data yet (send a message first)[/dim italic]")
    else:
        console.print(f"  [dim]Last input:[/dim]  {ctx_used:,} tokens" if ctx_used else "  [dim]No usage data yet.[/dim]")

    console.print()
    console.print("  [dim]Use [cyan]/usage all[/cyan] for global aggregates.[/dim]")
    console.print()


def _show_global_usage(
    store: EventStore,
    console: Console,
    *,
    agent: str | None = None,
    model: str | None = None,
    period: str | None = None,
) -> None:
    usage = q.usage_summary(store, agent=agent, model=model, period=period)

    console.print()
    console.print("  [bold]Token Usage Summary[/bold]")
    if agent:
        console.print(f"  [dim]Agent:[/dim] {agent}")
    if model:
        console.print(f"  [dim]Model:[/dim] {model}")
    if period:
        console.print(f"  [dim]Period:[/dim] {period}")

    console.print(
        f"  [dim]Total turns:[/dim]  {usage.get('turn_count', 0)}\n"
        f"  [dim]Input tokens:[/dim] {usage.get('total_input_tokens', 0):,}\n"
        f"  [dim]Output tokens:[/dim] {usage.get('total_output_tokens', 0):,}\n"
        f"  [dim]Est. cost:[/dim]    ${usage.get('total_cost_usd', 0):.4f}"
    )

    by_agent = usage.get("by_agent", [])
    if by_agent and not agent:
        console.print()
        console.print("  [bold]By Agent[/bold]")
        table = Table(box=None, padding=(0, 1), show_edge=False)
        table.add_column("Agent", style="#00d4ff")
        table.add_column("Turns", justify="right")
        table.add_column("Input", justify="right")
        table.add_column("Output", justify="right")
        table.add_column("Cost", justify="right", style="green")

        for row in by_agent:
            table.add_row(
                row["agent"],
                str(row.get("turn_count", 0)),
                f"{row.get('input_tokens', 0):,}",
                f"{row.get('output_tokens', 0):,}",
                f"${row.get('cost_usd', 0):.4f}",
            )
        console.print(table)

    by_model = usage.get("by_model", [])
    if by_model and not model:
        console.print()
        console.print("  [bold]By Model[/bold]")
        table = Table(box=None, padding=(0, 1), show_edge=False)
        table.add_column("Model", style="dim")
        table.add_column("Turns", justify="right")
        table.add_column("Input", justify="right")
        table.add_column("Output", justify="right")
        table.add_column("Cost", justify="right", style="green")

        for row in by_model:
            table.add_row(
                row["model"],
                str(row.get("turn_count", 0)),
                f"{row.get('input_tokens', 0):,}",
                f"{row.get('output_tokens', 0):,}",
                f"${row.get('cost_usd', 0):.4f}",
            )
        console.print(table)

    console.print()
