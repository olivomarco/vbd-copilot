"""
Beautiful terminal UI for VBD-Copilot.
Uses prompt_toolkit for input and rich for output rendering.
"""

from __future__ import annotations

import os
import shutil
import sys
import time
from pathlib import Path
from typing import Any

from prompt_toolkit import PromptSession
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.completion import NestedCompleter, WordCompleter
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.history import FileHistory
from prompt_toolkit.styles import Style as PTStyle

from rich import box
from rich.console import Console, Group
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.text import Text


# ── Version ───────────────────────────────────────────────────────────────────
VERSION = "1.0.0"


# =============================================================================
# AgentRunTracker  (lightweight stats-only tracker)
# =============================================================================


class AgentRunTracker:
    """Tracks tool/subagent counts during an agent run for a summary line."""

    def __init__(self, agent: str | None = None, model: str = "") -> None:
        self.agent = agent or "copilot"
        self.model = model
        self.start_time: float = time.time()
        self.tool_count: int = 0
        self.subagent_count: int = 0

    def summary(self) -> str:
        elapsed = int(time.time() - self.start_time)
        m, s = divmod(elapsed, 60)
        return (
            f"[dim]{self.agent} finished in {m}m{s:02d}s "
            f"({self.tool_count} tool calls, "
            f"{self.subagent_count} subagent runs)[/dim]"
        )


# ── Blue gradient for banner (light -> deep) ─────────────────────────────────
GRADIENT = [
    "#00e5ff",
    "#00c8ff",
    "#00aaff",
    "#0088ff",
    "#0066ee",
    "#0044dd",
    "#0033cc",
]

# ── VBD-Copilot ASCII art banner ─────────────────────────────────────────────
BANNER_ART = [
    " ██╗   ██╗██████╗ ██████╗         ██████╗ ██████╗ ██████╗ ██╗██╗      ██████╗ ████████╗  ",
    " ██║   ██║██╔══██╗██╔══██╗       ██╔════╝██╔═══██╗██╔══██╗██║██║     ██╔═══██╗╚══██╔══╝  ",
    " ██║   ██║██████╔╝██║  ██║ █████╗██║     ██║   ██║██████╔╝██║██║     ██║   ██║   ██║     ",
    " ╚██╗ ██╔╝██╔══██╗██║  ██║ ╚════╝██║     ██║   ██║██╔═══╝ ██║██║     ██║   ██║   ██║     ",
    "  ╚████╔╝ ██████╔╝██████╔╝       ╚██████╗╚██████╔╝██║     ██║███████╗╚██████╔╝   ██║     ",
    "   ╚═══╝  ╚═════╝ ╚═════╝         ╚═════╝ ╚═════╝ ╚═╝     ╚═╝╚══════╝ ╚═════╝    ╚═╝     ",
]

# ── Microsoft 4-square logo (brand colors) ───────────────────────────────────
MS_LOGO = [
    [("████", "#f25022"), ("  ", ""), ("████", "#7fba00")],
    [("████", "#f25022"), ("  ", ""), ("████", "#7fba00")],
    [("    ", ""),         ("  ", ""), ("    ", "")],
    [("████", "#00a4ef"), ("  ", ""), ("████", "#ffb900")],
    [("████", "#00a4ef"), ("  ", ""), ("████", "#ffb900")],
    [("  Microsoft  ", "dim")],
]

# ── Compact banner for narrow terminals ───────────────────────────────────────
COMPACT_ART = [
    "╻ ╻┏┓ ╺┳┓   ┏━╸┏━┓┏━┓╻╻  ┏━┓╺┳╸",
    "┃ ┃┣┻┓ ┃┃╺━╸┃  ┃ ┃┣━┛┃┃  ┃ ┃ ┃ ",
    " ╹ ┗━┛╺┻┛   ┗━╸┗━┛╹  ╹┗━╸┗━┛ ╹ ",
]

# ── Workflow info ─────────────────────────────────────────────────────────────
WORKFLOWS = [
    ("slide-conductor", "Research -> Plan -> Build PPTX -> QA -> Deliver"),
    ("demo-conductor",  "Research -> Plan -> Build -> Validate -> Review -> Deliver"),
]

# ── Content levels ────────────────────────────────────────────────────────────
CONTENT_LEVELS = [
    ("L100", "Executive overview, no code"),
    ("L200", "Architecture, key concepts"),
    ("L300", "Deep dive, code samples"),
    ("L400", "Expert, internals, advanced"),
]

# ── prompt_toolkit style ─────────────────────────────────────────────────────
PT_STYLE = PTStyle.from_dict({
    "":             "#e0e0e0",
    "prompt":       "#00aaff bold",
    "agent-name":   "#00d4ff",
})

# ── History file ──────────────────────────────────────────────────────────────
HISTORY_DIR = Path.home() / ".copilot"
HISTORY_FILE = HISTORY_DIR / "vbd-copilot-history"


# =============================================================================
# CopilotUI
# =============================================================================


class CopilotUI:
    """Terminal UI manager for VBD-Copilot."""

    def __init__(self) -> None:
        self.console = Console()
        self.current_agent: str | None = None
        self.current_model: str = "claude-sonnet-4.6"
        self.session_id: str | None = None
        self._received_deltas: bool = False
        self.debug_mode: bool = True
        self._tracker: AgentRunTracker | None = None
        self._needs_newline: bool = False  # True when stdout has pending text without trailing \n
        self._last_width: int = shutil.get_terminal_size().columns

        HISTORY_DIR.mkdir(parents=True, exist_ok=True)

        self.prompt_session = PromptSession(
            history=FileHistory(str(HISTORY_FILE)),
            auto_suggest=AutoSuggestFromHistory(),
            completer=self._build_completer(),
            style=PT_STYLE,
            complete_while_typing=True,
        )

    # ── Completer ─────────────────────────────────────────────────────────────

    @staticmethod
    def _build_completer() -> NestedCompleter:
        return NestedCompleter.from_nested_dict({
            "/new":      {"slide-conductor": None, "demo-conductor": None},
            "/agent":    {"slide-conductor": None, "demo-conductor": None},
            "/agents":   None,
            "/model":    {"claude-sonnet-4.6": None, "claude-opus-4.6": None},
            "/samples":  None,
            "/tutorial": None,
            "/debug":    None,
            "/clear":    None,
            "/help":     None,
            "/quit":     None,
        })

    # ── Prompt message ────────────────────────────────────────────────────────

    def _get_prompt_message(self) -> HTML:
        if self.current_agent:
            return HTML(
                f'<agent-name>[{self.current_agent}]</agent-name> '
                f'<prompt>>>> </prompt>'
            )
        return HTML('<prompt>>>> </prompt>')

    # ── User input ────────────────────────────────────────────────────────────

    @property
    def agent_running(self) -> bool:
        """True while a send_and_wait is active."""
        return self._tracker is not None

    def start_agent_display(self) -> None:
        """Start tracking an agent run (stats only)."""
        self._tracker = AgentRunTracker(
            agent=self.current_agent,
            model=self.current_model,
        )

    def stop_agent_display(self) -> None:
        """Print a summary of the agent run."""
        if self._tracker:
            summary = self._tracker.summary()
            self._tracker = None
            self.console.print(f"  {summary}")

    async def prompt(self) -> str | None:
        # Redraw banner if terminal was resized since last prompt
        current_width = shutil.get_terminal_size().columns
        if current_width != self._last_width:
            self._last_width = current_width
            self.clear()
            self.print_banner()
            if self.session_id:
                self.console.print(
                    f"  [dim]Session [cyan]{self.session_id[:12]}...[/cyan] active[/dim]"
                )
                self.console.print()
        try:
            result = await self.prompt_session.prompt_async(
                self._get_prompt_message()
            )
            return result
        except EOFError:
            return None
        except KeyboardInterrupt:
            return ""

    # ── ask_user sub-prompt ───────────────────────────────────────────────────

    async def ask_user_prompt(
        self,
        question: str,
        choices: list[str] | None = None,
        allow_freeform: bool = True,
    ) -> tuple[str, bool]:
        try:
            self.console.print()
            self.console.print(f"  [yellow bold]? Agent asks:[/yellow bold] {question}")

            completer = None
            if choices:
                self.console.print()
                for i, c in enumerate(choices, 1):
                    self.console.print(f"    [yellow]{i}.[/yellow] {c}")
                self.console.print()
                if allow_freeform:
                    self.console.print(
                        "  [dim]Enter a number to pick, or type a free-form answer[/dim]"
                    )
                else:
                    self.console.print("  [dim]Enter the number of your choice[/dim]")
                completer = WordCompleter(
                    [str(i) for i in range(1, len(choices) + 1)] + choices,
                    sentence=True,
                )

            answer = await self.prompt_session.prompt_async(
                HTML('<style fg="#ffaa00">  -> </style>'),
                completer=completer,
            )
            answer = (answer or "").strip()

            was_freeform = True
            if choices and answer.isdigit():
                idx = int(answer) - 1
                if 0 <= idx < len(choices):
                    answer = choices[idx]
                    was_freeform = False

            self.console.print()
            return answer, was_freeform
        finally:
            pass

    # ── Terminal resize handling ────────────────────────────────────────────────

    def handle_resize(self) -> None:
        """Redraw banner on terminal resize."""
        current_width = shutil.get_terminal_size().columns
        if current_width != self._last_width:
            self._last_width = current_width
            self.clear()
            self.print_banner()
            if self.session_id:
                self.console.print(
                    f"  [dim]Session [cyan]{self.session_id[:12]}...[/cyan] active[/dim]"
                )
                self.console.print()

    # ── Banner ────────────────────────────────────────────────────────────────

    def print_banner(self) -> None:
        term_width = shutil.get_terminal_size().columns

        if term_width >= 115:
            self._print_full_banner()
        else:
            self._print_compact_banner()

        # ── Quick start guide ─────────────────────────────────────────────
        self.console.print()
        qs = Table(show_header=False, show_edge=False, box=None, padding=(0, 1))
        qs.add_column(width=3)
        qs.add_column()
        qs.add_row(
            "[bold cyan]1.[/bold cyan]",
            '[white]Say [cyan]"I need a deck on Azure Container Apps"[/cyan][/white] '
            "- launches Slide Conductor",
        )
        qs.add_row(
            "[bold cyan]2.[/bold cyan]",
            '[white]Say [cyan]"Create 3 L300 demos on GitHub Copilot"[/cyan][/white] '
            "- launches Demo Conductor",
        )
        qs.add_row(
            "[bold cyan]3.[/bold cyan]",
            "[white]Both agents [bold]research official docs[/bold], "
            "[bold]plan with your input[/bold], [bold]build[/bold], and "
            "[bold]auto-QA[/bold] before delivering[/white]",
        )
        qs.add_row(
            "[bold cyan]4.[/bold cyan]",
            "[white]Agents can [bold]run shell commands[/bold], "
            "[bold]create files[/bold], and [bold]search the web[/bold][/white]",
        )
        self.console.print(
            Panel(
                qs,
                title="[bold white]Quick Start[/bold white]",
                border_style="#0055dd",
                padding=(1, 2),
                expand=False,
            )
        )

        # ── Hints ─────────────────────────────────────────────────────────
        self.console.print()
        self.console.print(
            "  [dim]Type [cyan]/help[/cyan] for commands  |  "
            "[cyan]/tutorial[/cyan] for a guided walkthrough  |  "
            "[cyan]@agent[/cyan] to route directly  |  "
            "or just start chatting[/dim]"
        )
        self.console.print()
        self.console.print(Rule(style="blue"))
        self.console.print()

    def _print_full_banner(self) -> None:
        table = Table(
            show_header=False, show_edge=False, box=None,
            padding=(0, 3), expand=False,
        )
        table.add_column()
        table.add_column(width=12, justify="center")

        max_lines = max(len(BANNER_ART), len(MS_LOGO))

        for i in range(max_lines):
            if i < len(BANNER_ART):
                color = GRADIENT[i] if i < len(GRADIENT) else GRADIENT[-1]
                left = Text(BANNER_ART[i], style=color, no_wrap=True)
            else:
                left = Text("")

            right = Text(no_wrap=True)
            if i < len(MS_LOGO):
                for part_text, part_color in MS_LOGO[i]:
                    right.append(part_text, style=part_color if part_color else "")

            table.add_row(left, right)

        version_line = Text()
        version_line.append("  Slides & Demos Builder", style="bold white")
        version_line.append("  |  ", style="dim")
        version_line.append(f"v{VERSION}", style="#58a6ff")

        content = Group(table, Text(""), version_line)
        panel = Panel(
            content, border_style="#0055dd",
            padding=(1, 3), expand=False,
        )
        self.console.print()
        self.console.print(panel)

    def _print_compact_banner(self) -> None:
        art_block = Text()
        for i, line in enumerate(COMPACT_ART):
            color = GRADIENT[i] if i < len(GRADIENT) else GRADIENT[-1]
            art_block.append(line, style=color)
            art_block.append("\n")

        logo_line = Text()
        logo_line.append("##", style="#f25022")
        logo_line.append(" ", style="")
        logo_line.append("##", style="#7fba00")
        logo_line.append("  ", style="")
        logo_line.append("##", style="#00a4ef")
        logo_line.append(" ", style="")
        logo_line.append("##", style="#ffb900")
        logo_line.append("  Microsoft", style="dim")

        subtitle = Text()
        subtitle.append("Slides & Demos Builder", style="bold white")
        subtitle.append("  |  ", style="dim")
        subtitle.append(f"v{VERSION}", style="#58a6ff")

        content = Group(art_block, logo_line, Text(""), subtitle)
        panel = Panel(
            content, border_style="#0055dd",
            padding=(1, 2), expand=False,
        )
        self.console.print()
        self.console.print(panel)

    # ── Streaming event handler ───────────────────────────────────────────────

    def reset_deltas(self) -> None:
        self._received_deltas = False

    @property
    def received_deltas(self) -> bool:
        return self._received_deltas

    def toggle_debug(self) -> bool:
        """Toggle debug mode on/off. Returns the new state."""
        self.debug_mode = not self.debug_mode
        return self.debug_mode

    # ── Live display helpers ───────────────────────────────────────────────────

    def _chat(self, markup: str) -> None:
        """Emit a line to the console."""
        self.console.print(markup)

    def _flush_newline(self) -> None:
        """Emit a pending newline if streaming text didn't end with one."""
        if self._needs_newline:
            sys.stdout.write("\n")
            sys.stdout.flush()
            self._needs_newline = False

    def _sidebar(self, markup: str) -> None:
        """Emit a line to console when tracker active or debug mode."""
        if self._tracker or self.debug_mode:
            self._flush_newline()
            self.console.print(markup)

    def handle_event(self, event: Any) -> None:
        import json
        from copilot.generated.session_events import SessionEventType

        etype = event.type
        d = event.data
        tracker = self._tracker

        # ── Always-on events ──────────────────────────────────────────────────

        if etype == SessionEventType.ASSISTANT_MESSAGE_DELTA:
            self._received_deltas = True
            delta = getattr(d, "delta_content", None) or ""
            if delta:
                sys.stdout.write(delta)
                sys.stdout.flush()
                self._needs_newline = not delta.endswith("\n")
            return

        if etype == SessionEventType.ASSISTANT_REASONING_DELTA:
            if self.debug_mode:
                delta = getattr(d, "delta_content", None) or ""
                if delta:
                    sys.stdout.write(f"\033[2m\033[3m{delta}\033[0m")
                    sys.stdout.flush()
                    self._needs_newline = not delta.endswith("\n")
            return

        if etype == SessionEventType.TOOL_EXECUTION_START:
            self._flush_newline()
            tool = getattr(d, "tool_name", None) or getattr(d, "mcp_tool_name", "?")
            if tracker:
                tracker.tool_count += 1
            self.console.print(f"  [bold blue]>>[/bold blue] [blue]{tool}[/blue]", end="")
            if self.debug_mode:
                args = getattr(d, "arguments", None)
                if args is not None:
                    try:
                        raw = json.dumps(args, ensure_ascii=False)
                        self.console.print(f" [dim]{raw[:80]}[/dim]", end="")
                    except Exception:
                        pass
            self._needs_newline = True
            return

        if etype == SessionEventType.TOOL_EXECUTION_COMPLETE:
            duration = getattr(d, "duration", None)
            dur_markup = f" [dim]{duration}ms[/dim]" if duration else ""
            self.console.print(f" [blue]<< done[/blue]{dur_markup}")
            self._needs_newline = False
            return

        if etype == SessionEventType.SESSION_ERROR:
            self._flush_newline()
            msg = getattr(d, "message", str(d))
            self.console.print(f"\n  [red bold]ERROR: {msg}[/red bold]")
            return

        # ── Subagent + session events (sidebar always when live, debug-only otherwise) ──

        if etype == SessionEventType.SUBAGENT_SELECTED:
            name = getattr(d, "agent_name", "?") or "?"
            self._sidebar(f"[cyan bold]~~ selected: {name}[/cyan bold]")
            return

        if etype == SessionEventType.SUBAGENT_STARTED:
            name = getattr(d, "agent_name", "?") or "?"
            if tracker:
                tracker.subagent_count += 1
            self._sidebar(f"[cyan bold]-> started:  {name}[/cyan bold]")
            return

        if etype == SessionEventType.SUBAGENT_COMPLETED:
            name = getattr(d, "agent_name", "?") or "?"
            self._sidebar(f"[cyan]<- done:     {name}[/cyan]")
            return

        if etype == SessionEventType.SUBAGENT_DESELECTED:
            name = getattr(d, "agent_name", "?") or "?"
            self._sidebar(f"[dim cyan]   deselected: {name}[/dim cyan]")
            return

        if etype == SessionEventType.SUBAGENT_FAILED:
            name = getattr(d, "agent_name", "?") or "?"
            err  = getattr(d, "message", "") or ""
            self._sidebar(f"[red]XX failed: {name} {err}[/red]")
            return

        if etype == SessionEventType.SESSION_HANDOFF:
            name = getattr(d, "agent_name", None) or "?"
            self._sidebar(f"[yellow]~~ handoff -> {name}[/yellow]")
            return

        if etype == SessionEventType.ASSISTANT_USAGE:
            in_t  = int(getattr(d, "input_tokens",       0) or 0)
            out_t = int(getattr(d, "output_tokens",      0) or 0)
            cr_t  = int(getattr(d, "cache_read_tokens",  0) or 0)
            cw_t  = int(getattr(d, "cache_write_tokens", 0) or 0)
            model = getattr(d, "model", None) or ""
            parts = [f"in={in_t}", f"out={out_t}"]
            if cr_t: parts.append(f"cr={cr_t}")
            if cw_t: parts.append(f"cw={cw_t}")
            if model: parts.append(f"[{model}]")
            self._sidebar(f"[dim]tokens: {' | '.join(parts)}[/dim]")
            return

        if etype == SessionEventType.SESSION_COMPACTION_START:
            self._sidebar("[dim yellow]compaction started...[/dim yellow]")
            return

        if etype == SessionEventType.SESSION_COMPACTION_COMPLETE:
            post = int(getattr(d, "post_compaction_tokens", 0) or 0)
            self._sidebar(f"[dim yellow]compaction done tokens={post}[/dim yellow]")
            return

        # ── Debug-only events (sidebar when live, console otherwise) ──────────

        if not self.debug_mode:
            return

        if etype == SessionEventType.TOOL_EXECUTION_PARTIAL_RESULT:
            partial = getattr(d, "partial_output", None) or ""
            snippet = partial[:300] + "..." if len(partial) > 300 else partial
            self._sidebar(f"[dim blue]~ {snippet}[/dim blue]")

        elif etype == SessionEventType.TOOL_EXECUTION_PROGRESS:
            msg = getattr(d, "progress_message", None) or ""
            self._sidebar(f"[dim blue]... {msg}[/dim blue]")

        elif etype == SessionEventType.ASSISTANT_INTENT:
            intent = getattr(d, "intent", None) or ""
            if intent:
                self._sidebar(f"[dim magenta]intent: {intent}[/dim magenta]")

        elif etype == SessionEventType.ASSISTANT_REASONING:
            text = getattr(d, "reasoning_text", None) or ""
            if text:
                self._sidebar(f"[dim italic]reasoning: {text[:400]}[/dim italic]")

        elif etype == SessionEventType.ASSISTANT_TURN_START:
            self._flush_newline()
            self.console.print(Rule(style="dim blue", title="[dim]turn start[/dim]"))

        elif etype == SessionEventType.ASSISTANT_TURN_END:
            self._flush_newline()
            self.console.print(Rule(style="dim blue", title="[dim]turn end[/dim]"))

        elif etype == SessionEventType.HOOK_START:
            hook_type = getattr(d, "hook_type", "?") or "?"
            self._sidebar(f"[dim]hook >> {hook_type}[/dim]")

        elif etype == SessionEventType.HOOK_END:
            hook_type = getattr(d, "hook_type", "?") or "?"
            self._sidebar(f"[dim]hook << {hook_type}[/dim]")

        elif etype == SessionEventType.SESSION_INFO:
            msg = getattr(d, "message", None) or ""
            if msg:
                self._sidebar(f"[dim]info: {msg}[/dim]")

        elif etype == SessionEventType.SESSION_WARNING:
            msg = getattr(d, "message", None) or ""
            if msg:
                self._sidebar(f"[yellow dim]warn: {msg}[/yellow dim]")



    # ── Display helpers ───────────────────────────────────────────────────────

    def print_routing(self, agent_name: str | None, model: str) -> None:
        if agent_name:
            self.console.print(
                f"  [dim]>> routed -> [cyan]{agent_name}[/cyan] | "
                f"model: {model}[/dim]"
            )
        else:
            self.console.print("  [dim]>> routed -> default copilot[/dim]")

    def print_assistant_prefix(self) -> None:
        self.console.print()
        self.console.print("[green bold]Assistant >>>[/green bold]")

    def print_response_end(self) -> None:
        print()
        self.console.print()

    def print_session_created(self, session_id: str) -> None:
        self.session_id = session_id
        self.console.print(
            f"  [dim]Session [cyan]{session_id[:12]}...[/cyan] created[/dim]"
        )
        self.console.print()

    def print_output_files(self, files: list[Path]) -> None:
        """Print paths of newly generated output files."""
        if not files:
            return
        self.console.print()
        self.console.print(Rule(style="#0055dd", title="[bold white]Output Files[/bold white]"))
        for f in sorted(files):
            suffix = f.suffix.lower()
            if suffix == ".pptx":
                label = "[green bold]PPTX [/green bold]"
            elif suffix == ".py":
                label = "[blue bold]SCRIPT[/blue bold]"
            elif suffix == ".md":
                label = "[cyan bold]GUIDE [/cyan bold]"
            else:
                label = "[dim]FILE [/dim]"
            self.console.print(f"  {label}  [cyan]{f}[/cyan]")
        self.console.print()

    def print_help(self) -> None:
        table = Table(
            show_header=True, header_style="bold cyan",
            box=box.SIMPLE, padding=(0, 2),
        )
        table.add_column("Command", style="cyan", no_wrap=True)
        table.add_column("Description")

        table.add_row("/new [agent]", "Start a new session (optionally pre-selecting an agent)")
        table.add_row("/agent <name>", "Switch to a specific agent mid-session")
        table.add_row("/agents", "List all available agents with details")
        table.add_row("/model <id>", "Switch the LLM model")
        table.add_row("/debug", "Toggle debug mode (shows tool I/O, subagent flow, token usage)")
        table.add_row("/samples", "Show sample output library")
        table.add_row("/tutorial", "Interactive guided walkthrough")
        table.add_row("/clear", "Clear the screen and redisplay the banner")
        table.add_row("/help", "Show this help")
        table.add_row("/quit", "Exit VBD-Copilot")

        self.console.print()
        self.console.print(
            Panel(
                table,
                title="[bold white]Commands[/bold white]",
                border_style="#0055dd",
                expand=False,
            )
        )
        # ── Conductors ────────────────────────────────────────────────
        self.console.print()
        self.console.print("  [bold white]Conductors[/bold white]")
        for name, desc in WORKFLOWS:
            self.console.print(
                f"    [cyan bold]>> {name:<22}[/cyan bold] "
                f"[dim]-[/dim] {desc}"
            )

        # ── Content levels ────────────────────────────────────────────────
        self.console.print()
        self.console.print("  [bold white]Content Levels[/bold white]")
        for level, desc in CONTENT_LEVELS:
            self.console.print(f"    [cyan]{level}[/cyan] [dim]-[/dim] {desc}")

        self.console.print()
        self.console.print(
            "  [dim]Tip: prefix any message with [cyan]@agent_name[/cyan]"
            " to route directly.[/dim]"
        )
        self.console.print()

    def print_agents_list(self) -> None:
        from agents import ALL_AGENT_CONFIGS

        table = Table(
            show_header=True, header_style="bold cyan",
            box=box.SIMPLE, padding=(0, 2),
        )
        table.add_column("Agent", style="cyan", no_wrap=True)
        table.add_column("Description")

        for agent in ALL_AGENT_CONFIGS:
            if not agent.get("infer", False):
                continue
            name = agent.get("name", "?")
            desc = agent.get("description", "")
            table.add_row(name, desc)

        self.console.print()
        self.console.print(
            Panel(
                table,
                title="[bold white]Agents[/bold white]",
                border_style="#0055dd",
                expand=False,
            )
        )
        self.console.print()

    def print_samples(self) -> None:
        """Show sample output library."""
        self.console.print()
        self.console.print(
            Panel(
                "[bold white]Sample Output Library[/bold white]\n\n"
                "Generated presentations and demo guides are in the "
                "[cyan]legacy/samples/[/cyan] directory:\n\n"
                "[bold]Slide Decks:[/bold]\n"
                "  [cyan]slides/fabric-trustworthy-data-l300-2h.pptx[/cyan] - "
                "Microsoft Fabric (33 slides)\n"
                "  [cyan]slides/gh-aw-l300-1h.pptx[/cyan] - "
                "GitHub Agentic Workflows (30 slides)\n"
                "  [cyan]slides/keda-banking-l300-30min.pptx[/cyan] - "
                "KEDA for Banking (22 slides)\n\n"
                "[bold]Demo Guides:[/bold]\n"
                "  [cyan]demos/generic-fabric-trustworthy-data-demos.md[/cyan] - "
                "5 L300 demos (~1h 45m)\n"
                "  [cyan]demos/generic-github-agentic-workflows-demos.md[/cyan] - "
                "3 L300 demos\n\n"
                "[dim]New outputs are saved to [cyan]outputs/[/cyan][/dim]",
                title="[bold cyan]Samples[/bold cyan]",
                border_style="#0055dd",
                expand=False,
                padding=(1, 3),
            )
        )
        self.console.print()

    async def print_tutorial(self) -> None:
        c = self.console
        p = self.prompt_session

        # ── Page 1: Welcome ──────────────────────────────────────────────
        c.print()
        c.print(
            Panel(
                "[bold white]Welcome to the VBD-Copilot Tutorial![/bold white]\n\n"
                "This walkthrough teaches you everything you need to know\n"
                "to generate presentations and demo packages.\n\n"
                "[dim]Press Enter to continue, or /quit to exit.[/dim]",
                title="[bold cyan]Tutorial[/bold cyan]",
                subtitle="[dim]1 / 6[/dim]",
                border_style="#0055dd",
                padding=(1, 3),
                expand=False,
            )
        )
        if not await self._tutorial_continue(p):
            return

        # ── Page 2: What is VBD-Copilot? ─────────────────────────────────
        c.print()
        c.print(
            Panel(
                "[bold white]What is VBD-Copilot?[/bold white]\n\n"
                "VBD-Copilot is an AI-powered builder for Microsoft Cloud\n"
                "Solution Architects and Solution Engineers. It has two conductors:\n\n"
                "  [cyan bold]>> Slide Conductor[/cyan bold]\n"
                "    Generates a complete .pptx presentation from a single prompt.\n"
                "    Researches official docs, plans with your input, builds slides\n"
                "    with full speaker notes, and runs automated QA.\n\n"
                "  [cyan bold]>> Demo Conductor[/cyan bold]\n"
                "    Generates step-by-step demo guides and companion scripts.\n"
                "    Researches existing repos, plans demos, builds files,\n"
                "    validates syntax, and reviews for quality.\n\n"
                "[bold]Both conductors:[/bold]\n"
                "  - Research from official Microsoft/GitHub sources first\n"
                "  - Ask you for input before proceeding\n"
                "  - Run automated quality checks\n"
                "  - Never publish without your approval",
                title="[bold cyan]Overview[/bold cyan]",
                subtitle="[dim]2 / 6[/dim]",
                border_style="#0055dd",
                padding=(1, 3),
                expand=False,
            )
        )
        if not await self._tutorial_continue(p):
            return

        # ── Page 3: Slide Conductor ───────────────────────────────────────
        c.print()
        pipeline = Table(show_header=False, box=box.SIMPLE, padding=(0, 2))
        pipeline.add_column("Step", style="bold cyan", width=8)
        pipeline.add_column("Action", style="bold white", width=20)
        pipeline.add_column("What happens")
        pipeline.add_row("0A", "Pre-Research", "Lightweight scan of official docs before asking you anything")
        pipeline.add_row("0B", "Clarify", "Asks you about topic, level, duration, audience")
        pipeline.add_row("1", "Deep Research", "Parallel research shards across official sources")
        pipeline.add_row("2", "Plan", "Creates structured outline - waits for your approval")
        pipeline.add_row("3", "Build PPTX", "Generates python-pptx code fragments, assembles, runs script")
        pipeline.add_row("3F", "QA", "Content check + visual inspection of rendered slides")
        pipeline.add_row("4", "Deliver", "Presents .pptx file path and completion report")

        c.print(
            Panel(
                Group(
                    Text.from_markup(
                        "[bold white]The Slide Conductor Pipeline[/bold white]\n"
                    ),
                    pipeline,
                    Text.from_markup(
                        "\n[dim]Try: \"I need a 1-hour L300 deck on Azure Container Apps\"[/dim]"
                    ),
                ),
                title="[bold cyan]Slide Conductor[/bold cyan]",
                subtitle="[dim]3 / 6[/dim]",
                border_style="#0055dd",
                padding=(1, 3),
                expand=False,
            )
        )
        if not await self._tutorial_continue(p):
            return

        # ── Page 4: Demo Conductor ────────────────────────────────────────
        c.print()
        demo_pipe = Table(show_header=False, box=box.SIMPLE, padding=(0, 2))
        demo_pipe.add_column("Step", style="bold cyan", width=8)
        demo_pipe.add_column("Action", style="bold white", width=20)
        demo_pipe.add_column("What happens")
        demo_pipe.add_row("0A", "Pre-Research", "Scans for existing sample repos and quickstarts")
        demo_pipe.add_row("0B", "Clarify", "Asks: customer name, number of demos, level")
        demo_pipe.add_row("1", "Deep Research", "Finds best demo scenarios with WOW moments")
        demo_pipe.add_row("2", "Plan", "Creates demo plan - waits for your approval")
        demo_pipe.add_row("3", "Build", "Creates guide .md + all companion scripts")
        demo_pipe.add_row("4", "Validate + Review", "Syntax check, URL verify, structured review")
        demo_pipe.add_row("5", "Deliver", "Presents guide path and demo inventory")

        c.print(
            Panel(
                Group(
                    Text.from_markup(
                        "[bold white]The Demo Conductor Pipeline[/bold white]\n"
                    ),
                    demo_pipe,
                    Text.from_markup(
                        "\n[dim]Try: \"Create 3 L300 demos on GitHub Copilot for Contoso\"[/dim]"
                    ),
                ),
                title="[bold cyan]Demo Conductor[/bold cyan]",
                subtitle="[dim]4 / 6[/dim]",
                border_style="#0055dd",
                padding=(1, 3),
                expand=False,
            )
        )
        if not await self._tutorial_continue(p):
            return

        # ── Page 5: Content Levels ────────────────────────────────────────
        c.print()
        levels = Table(show_header=True, header_style="bold cyan",
                       box=box.SIMPLE, padding=(0, 2))
        levels.add_column("Level", style="bold white")
        levels.add_column("Audience")
        levels.add_column("Slides (1h)")
        levels.add_column("Demo Style")
        levels.add_row("L100", "Business / Executive",
                        "25-35", "No code, portal clicks")
        levels.add_row("L200", "Technical decision makers",
                        "25-35", "CLI commands, pre-built samples")
        levels.add_row("L300", "Practitioners",
                        "25-35", "Code samples, SDK calls")
        levels.add_row("L400", "Experts",
                        "25-35", "Live coding, internals")

        c.print(
            Panel(
                Group(
                    Text.from_markup(
                        "[bold white]Content Levels & Duration[/bold white]\n\n"
                        "Both conductors calibrate output to these levels:\n"
                    ),
                    levels,
                    Text.from_markup(
                        "\n[bold white]Slide Duration Guide:[/bold white]\n"
                        "  15min: 10-14 slides  |  30min: 15-20  |  1h: 25-35\n"
                        "  2h: 40-55  |  4h: 70-90  |  8h: 120-150"
                    ),
                ),
                title="[bold cyan]Content Calibration[/bold cyan]",
                subtitle="[dim]5 / 6[/dim]",
                border_style="#0055dd",
                padding=(1, 3),
                expand=False,
            )
        )
        if not await self._tutorial_continue(p):
            return

        # ── Page 6: Commands & tips ───────────────────────────────────────
        c.print()
        cmds = Table(show_header=False, box=None, padding=(0, 2))
        cmds.add_column(style="cyan bold", width=22)
        cmds.add_column()
        cmds.add_row("/new [agent]", "Start a fresh session")
        cmds.add_row("/agent <name>", "Switch agent mid-conversation")
        cmds.add_row("/agents", "See all agents")
        cmds.add_row("/model <id>", "Switch LLM model")
        cmds.add_row("/samples", "View sample output library")
        cmds.add_row("/clear", "Clear screen")
        cmds.add_row("/tutorial", "Re-run this tutorial")
        cmds.add_row("/help", "Quick command reference")
        cmds.add_row("/quit", "Exit")

        c.print(
            Panel(
                Group(
                    Text.from_markup(
                        "[bold white]Commands & Tips[/bold white]\n"
                    ),
                    cmds,
                    Text.from_markup(
                        "\n[bold white]Pro tips:[/bold white]\n"
                        "  >> Use [bold]arrow up/down[/bold] for command history\n"
                        "  >> [bold]Tab[/bold] auto-completes commands and agent names\n"
                        "  >> Use [cyan]@slide-conductor[/cyan] or "
                        "[cyan]@demo-conductor[/cyan] to route directly\n"
                        "  >> History persists across sessions (~/.copilot/)\n"
                        "  >> Set BING_API_KEY env var for reliable web search\n"
                        "  >> Run inside the Dev Container for full functionality\n"
                    ),
                ),
                title="[bold cyan]Commands[/bold cyan]",
                subtitle="[dim]6 / 6[/dim]",
                border_style="#0055dd",
                padding=(1, 3),
                expand=False,
            )
        )

        c.print()
        c.print(
            "  [bold green]Tutorial complete![/bold green] "
            "You're ready to go. Just start typing to begin."
        )
        c.print()

    @staticmethod
    async def _tutorial_continue(p: PromptSession) -> bool:
        try:
            resp = await p.prompt_async(
                HTML('<style fg="#484f58">  Press Enter to continue (/quit to exit tutorial) >>> </style>'),
                completer=None,
            )
            if resp and resp.strip().lower() in ("/quit", "/exit", "quit", "q"):
                return False
            return True
        except (EOFError, KeyboardInterrupt):
            return False

    def print_info(self, msg: str) -> None:
        self.console.print(f"  [dim]{msg}[/dim]")

    def print_error(self, msg: str) -> None:
        self.console.print(f"  [red bold]X[/red bold] [red]{msg}[/red]")

    def print_success(self, msg: str) -> None:
        self.console.print(f"  [green bold]OK[/green bold] [green]{msg}[/green]")

    def clear(self) -> None:
        # Use ANSI escape: clear screen + move cursor to top-left
        # Works in signal handlers unlike os.system("clear")
        sys.stdout.write("\033[2J\033[H")
        sys.stdout.flush()
