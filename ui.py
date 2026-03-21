"""
Beautiful terminal UI for VBD-Copilot.
Uses prompt_toolkit for input and rich for output rendering.
"""

from __future__ import annotations

import asyncio
import os
import select
import shutil
import sys
import termios
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from prompt_toolkit import PromptSession
from prompt_toolkit.auto_suggest import AutoSuggest, AutoSuggestFromHistory, Suggestion
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.completion import (CompleteEvent, Completer, Completion,
                                       NestedCompleter, WordCompleter,
                                       merge_completers)
from prompt_toolkit.document import Document
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.history import FileHistory
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.styles import Style as PTStyle
from rich import box
from rich.console import Console, Group
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.text import Text


# ── Version ───────────────────────────────────────────────────────────────────
VERSION = "1.1.0"


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


# =============================================================================
# Command-aware auto-suggest (inline ghost text)
# =============================================================================


class _CommandAwareAutoSuggest(AutoSuggest):
    """Inline ghost-text suggestions from commands/agents, then history."""

    def __init__(
        self, slash_commands: list[str], agent_names: list[str]
    ) -> None:
        self._slash = sorted(slash_commands)
        self._agents = sorted(f"@{n}" for n in agent_names)
        self._history = AutoSuggestFromHistory()

    def get_suggestion(
        self, buffer: Buffer, document: Document
    ) -> Suggestion | None:
        text = document.text_before_cursor
        if text.startswith("/"):
            for cmd in self._slash:
                if cmd.startswith(text) and cmd != text:
                    return Suggestion(cmd[len(text):] + " ")
        elif text.startswith("@"):
            for agent in self._agents:
                if agent.startswith(text) and agent != text:
                    return Suggestion(agent[len(text):] + " ")
        return self._history.get_suggestion(buffer, document)


# =============================================================================
# @agent-name completer
# =============================================================================


class _AtMentionCompleter(Completer):
    """Complete ``@agent-name`` at the start of input."""

    def __init__(self, agent_names: list[str]) -> None:
        self._names = sorted(agent_names)

    def get_completions(
        self, document: Document, complete_event: CompleteEvent
    ) -> Completion:
        text = document.text_before_cursor.lstrip()
        if not text.startswith("@"):
            return
        typed = text
        for name in self._names:
            candidate = f"@{name}"
            if candidate.startswith(typed) and candidate != typed:
                yield Completion(
                    candidate,
                    start_position=-len(text),
                    display=candidate,
                    display_meta="agent",
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
    "bottom-toolbar": "noreverse bg:default #0066ee",
    "bottom-toolbar.text": "noreverse bg:default #0066ee",
})

# ── History file ──────────────────────────────────────────────────────────────
HISTORY_DIR = Path.home() / ".vbd-copilot"
HISTORY_FILE = HISTORY_DIR / "vbd-copilot-history"


# =============================================================================
# CopilotUI
# =============================================================================


class CopilotUI:
    """Terminal UI manager for VBD-Copilot."""

    def __init__(self, collector: Any | None = None) -> None:
        self.console = Console()
        self.current_agent: str | None = None
        self.current_model: str = "claude-sonnet-4.6"
        self.session_id: str | None = None
        self._received_deltas: bool = False
        self.debug_mode: bool = False
        self._tracker: AgentRunTracker | None = None
        self._needs_newline: bool = False
        self._in_reasoning: bool = False
        self._baking_task: asyncio.Task[None] | None = None
        self._baking_line_active: bool = False
        self._saved_termios: list[Any] | None = None
        self._prompting: bool = False
        self._at_line_start: bool = True
        self._pending_assistant_prefix: bool = False
        self._last_width: int = shutil.get_terminal_size().columns
        self._cli_health_check: Callable[[], tuple[bool, str]] | None = None
        self._history: list[tuple[str, Any]] = []
        self._current_response: list[str] = []
        self._resize_watcher_task: asyncio.Task[None] | None = None
        self._tutorial_state: dict[str, Any] | None = None
        self._collector = collector
        self._pending_invocations: dict[str, str] = {}
        self._last_displayed_agent: str | None = None
        self._last_input_tokens: int = 0
        self._seen_event_ids: set[str] = set()
        self._last_event_time: float = 0.0
        self._dead_notified: bool = False

        HISTORY_DIR.mkdir(parents=True, exist_ok=True)

        completer, auto_suggest = self._build_input_helpers()
        self.prompt_session = PromptSession(
            history=FileHistory(str(HISTORY_FILE)),
            auto_suggest=auto_suggest,
            completer=completer,
            style=PT_STYLE,
            complete_while_typing=True,
            key_bindings=self._build_key_bindings(),
        )

    # ── Key bindings ──────────────────────────────────────────────────────

    @staticmethod
    def _build_key_bindings() -> KeyBindings:
        kb = KeyBindings()

        @kb.add("tab")
        def _tab_complete(event):
            buff = event.current_buffer
            if buff.complete_state:
                buff.complete_next()
            elif buff.suggestion:
                buff.insert_text(buff.suggestion.text)
            else:
                buff.start_completion()

        return kb

    # ── Completer & auto-suggest ──────────────────────────────────────────

    @staticmethod
    def _build_input_helpers() -> tuple[Completer, AutoSuggest]:
        from agents import ROUTABLE_AGENTS

        agent_names = {n: None for n in ROUTABLE_AGENTS}
        slash_dict = {
            "/new":      agent_names,
            "/agent":    agent_names,
            "/agents":   None,
            "/model":    {"claude-sonnet-4.6": None, "claude-opus-4.6": None},
            "/resume":   None,
            "/compact":  None,
            "/sessions": {"all": None, "end": None, "name": None, "cleanup": None},
            "/usage":    {
                "all": None, "today": None, "week": None, "month": None,
                "--agent": None, "--model": None, "--period": None,
            },
            "/samples":  None,
            "/tutorial": None,
            "/debug":    None,
            "/clear":    None,
            "/help":     None,
            "/quit":     None,
        }
        slash_completer = NestedCompleter.from_nested_dict(slash_dict)
        mention_completer = _AtMentionCompleter(list(ROUTABLE_AGENTS))
        completer = merge_completers([slash_completer, mention_completer])
        auto_suggest = _CommandAwareAutoSuggest(
            list(slash_dict.keys()), list(ROUTABLE_AGENTS),
        )
        return completer, auto_suggest

    # ── Prompt message ────────────────────────────────────────────────────

    @staticmethod
    def _separator(width: int, label: str) -> str:
        """Return ``  --- label ------`` sized to *width*."""
        overhead = 6
        dash_len = max(0, width - overhead - len(label))
        return f"  ---{label} {'-' * dash_len}"

    def _get_prompt_message(self) -> HTML:
        """Separator line + simple prompt prefix on the next line."""
        effective = self.current_agent or "copilot"
        agent_changed = effective != self._last_displayed_agent
        self._last_displayed_agent = effective

        if agent_changed:
            width = shutil.get_terminal_size().columns
            label = f" {self.current_agent} " if self.current_agent else " copilot "
            sep = self._separator(width, label)
            if self.current_agent:
                return HTML(
                    f'<style fg="#0066ee">{sep}</style>\n'
                    f"<agent-name>  [{self.current_agent}]</agent-name> "
                    f"<prompt>\u25b6 </prompt>"
                )
            return HTML(f'<style fg="#0066ee">{sep}</style>\n<prompt>  \u25b6 </prompt>')

        if self.current_agent:
            return HTML(
                f"<agent-name>  [{self.current_agent}]</agent-name> "
                f"<prompt>\u25b6 </prompt>"
            )
        return HTML('<prompt>  \u25b6 </prompt>')

    # ── User input ────────────────────────────────────────────────────────

    @property
    def agent_running(self) -> bool:
        return self._tracker is not None

    def start_agent_display(self) -> None:
        self._tracker = AgentRunTracker(
            agent=self.current_agent,
            model=self.current_model,
        )
        self._last_event_time = 0.0
        self._dead_notified = False
        self._start_baking_indicator()

    def stop_agent_display(self) -> None:
        self._stop_baking_indicator()
        if self._tracker:
            summary = self._tracker.summary()
            self._tracker = None
            self.console.print(f"  {summary}")
            self._record("summary", summary)
            self.console.print()
        if self._current_response:
            self._record("response", "".join(self._current_response))
            self._current_response.clear()

    def _suppress_echo(self) -> None:
        """Disable terminal echo so keystrokes during the spinner are invisible."""
        try:
            fd = sys.stdin.fileno()
            self._saved_termios = termios.tcgetattr(fd)
            new = termios.tcgetattr(fd)
            new[3] &= ~termios.ECHO
            termios.tcsetattr(fd, termios.TCSANOW, new)
        except (termios.error, OSError, ValueError):
            self._saved_termios = None

    def _restore_echo(self) -> None:
        """Restore original terminal settings and drain any buffered input."""
        if self._saved_termios is not None:
            try:
                fd = sys.stdin.fileno()
                termios.tcsetattr(fd, termios.TCSANOW, self._saved_termios)
            except (termios.error, OSError, ValueError):
                pass
            self._saved_termios = None
        self._drain_stdin()

    @staticmethod
    def _drain_stdin() -> None:
        """Discard any characters buffered in stdin."""
        try:
            fd = sys.stdin.fileno()
            while select.select([fd], [], [], 0)[0]:
                os.read(fd, 4096)
        except (OSError, ValueError):
            pass

    def _start_baking_indicator(self) -> None:
        self._stop_baking_indicator()
        self._suppress_echo()
        self._baking_task = asyncio.create_task(self._baking_pulse())

    def _stop_baking_indicator(self) -> None:
        if self._baking_task:
            self._baking_task.cancel()
            self._baking_task = None
        self._clear_baking_line()
        self._restore_echo()

    async def _baking_pulse(self) -> None:
        """Full-width spinner bar showing agent, model, and elapsed time."""
        spinner = ["\u280b", "\u2819", "\u2839", "\u2838", "\u283c", "\u2834", "\u2826", "\u2827", "\u2807", "\u280f"]
        i = 0
        BG = "\033[48;2;0;20;50m"
        FG = "\033[38;2;120;180;220m"
        FG_DIM = "\033[38;2;60;100;150m"
        BOLD = "\033[1m"
        NORM = "\033[22m"
        RESET = "\033[0m"
        ERASE = "\033[2K"
        _DEAD_CHECK_INTERVAL = 30
        try:
            while self._tracker is not None:
                if self._needs_newline or self._in_reasoning:
                    await asyncio.sleep(0.12)
                    continue

                if self._prompting:
                    await asyncio.sleep(0.5)
                    continue

                # Silent dead-process check (no user-visible warning for normal waits)
                if not self._dead_notified and self._cli_health_check:
                    if self._last_event_time > 0:
                        silence = time.time() - self._last_event_time
                    elif self._tracker:
                        silence = time.time() - self._tracker.start_time
                    else:
                        silence = 0
                    if silence >= _DEAD_CHECK_INTERVAL:
                        alive, detail = self._cli_health_check()
                        if not alive:
                            self._dead_notified = True
                            self._clear_baking_line()
                            self.console.print(
                                f"\n  [red bold]CLI process is dead:[/red bold] [red]{detail}[/red]"
                            )
                            self.console.print(
                                "  [yellow]Troubleshooting:[/yellow]\n"
                                "    1. Ensure ~/.copilot is mounted without :ro\n"
                                "    2. Run: docker run --rm --entrypoint copilot vbd-copilot --version\n"
                                "    3. Re-authenticate: npx @anthropic-ai/copilot auth login\n"
                                "    4. Check architecture: docker run --rm --entrypoint uname vbd-copilot -m"
                            )
                            continue

                term_width = shutil.get_terminal_size().columns
                spin = spinner[i % len(spinner)]
                i += 1

                agent = self._tracker.agent if self._tracker else "copilot"
                model = self._tracker.model if self._tracker else ""
                elapsed = int(time.time() - self._tracker.start_time) if self._tracker else 0
                m, s = divmod(elapsed, 60)

                left_text = f"  {spin}  {agent}  \u00b7  ctrl+c to interrupt  "
                right_text = f"  {model}  {m}m{s:02d}s  "
                visible_len = len(left_text) + len(right_text)

                if visible_len > term_width:
                    max_left = max(0, term_width - 1)
                    left_text = left_text[:max_left]
                    right_text = ""

                pad_len = max(0, term_width - len(left_text) - len(right_text))

                line = (
                    f"\r{ERASE}{BG}{FG}  {spin}  {BOLD}{agent}{NORM}"
                    f"{FG_DIM}  \u00b7  {FG}ctrl+c to interrupt  "
                    f"{' ' * pad_len}"
                    f"{FG_DIM}{right_text}{RESET}"
                ) if right_text else (
                    f"\r{ERASE}{BG}{FG}{left_text}{RESET}"
                )
                sys.stdout.write(line)
                sys.stdout.flush()
                self._baking_line_active = True
                await asyncio.sleep(0.12)
        except asyncio.CancelledError:
            pass
        finally:
            self._clear_baking_line()

    def _clear_baking_line(self) -> None:
        if self._baking_line_active:
            sys.stdout.write("\r\033[2K")
            sys.stdout.flush()
            self._baking_line_active = False

    def reset_prompt_state(self) -> None:
        """Force-reset prompt_toolkit state after cancellation or timeout."""
        self._prompting = False
        app = self.prompt_session.app
        if app._is_running:
            app._is_running = False

    def record_user_input(self, text: str) -> None:
        """Record a submitted user prompt for history replay."""
        self._record("user_input", (self.current_agent, text))

    async def prompt(self) -> str | None:
        self.reset_prompt_state()
        self._prompting = True
        try:
            sys.stdout.write("\033[0m")
            sys.stdout.flush()
            result = await self.prompt_session.prompt_async(
                self._get_prompt_message
            )
            return result
        except EOFError:
            return None
        except KeyboardInterrupt:
            return ""
        finally:
            self._prompting = False

    async def prompt_simple(self, label: str = ">>> ") -> str | None:
        """A simple one-off prompt for inline questions."""
        try:
            result = await self.prompt_session.prompt_async(
                HTML(f'<style fg="#00aaff">{label}</style>')
            )
            return result.strip() if result else None
        except (EOFError, KeyboardInterrupt):
            return None

    # ── ask_user sub-prompt ───────────────────────────────────────────────

    async def ask_user_prompt(
        self,
        question: str,
        choices: list[str] | None = None,
        allow_freeform: bool = True,
    ) -> tuple[str, bool]:
        self._stop_baking_indicator()
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
            if self._tracker:
                self._start_baking_indicator()

    # ── Terminal resize handling ────────────────────────────────────────────

    def start_resize_watcher(self) -> None:
        if self._resize_watcher_task is None:
            self._resize_watcher_task = asyncio.create_task(self._resize_poll())

    def stop_resize_watcher(self) -> None:
        if self._resize_watcher_task:
            self._resize_watcher_task.cancel()
            self._resize_watcher_task = None

    async def _resize_poll(self) -> None:
        """Poll terminal width and do a full redraw on change."""
        try:
            while True:
                await asyncio.sleep(0.05)
                current_width = shutil.get_terminal_size().columns
                if current_width != self._last_width:
                    self._last_width = current_width
                    if self._tutorial_state is not None:
                        ts = self._tutorial_state
                        self._render_tutorial_page(
                            ts["pages"], ts["current"], ts["total"]
                        )
                        continue
                    self._full_redraw()
                    if self._prompting:
                        try:
                            app = self.prompt_session.app
                            if app.is_running:
                                app.renderer.reset()
                                app.invalidate()
                        except Exception:
                            pass
        except asyncio.CancelledError:
            pass

    def handle_resize(self) -> None:
        """Immediate redraw (called from signal handler as fallback)."""
        current_width = shutil.get_terminal_size().columns
        if current_width == self._last_width:
            return
        self._last_width = current_width
        self._full_redraw()

    def _full_redraw(self) -> None:
        """Clear screen and reprint banner + conversation history."""
        self.clear()
        self.print_banner(record=False)
        if self.session_id:
            self.console.print(
                f"  [dim]Session [cyan]{self.session_id[:12]}...[/cyan] active[/dim]"
            )
            self.console.print()
        self._replay_history()

    # ── History buffer for redraw ──────────────────────────────────────────

    def _record(self, kind: str, data: Any = None) -> None:
        self._history.append((kind, data))

    def clear_history(self) -> None:
        self._history.clear()
        self._current_response.clear()

    def _replay_history(self) -> None:
        c = self.console
        for kind, data in self._history:
            if kind == "markup":
                c.print(data)
            elif kind == "user_input":
                width = shutil.get_terminal_size().columns
                agent_label, user_text = data
                label = f" {agent_label} " if agent_label else " copilot "
                sep = self._separator(width, label)
                c.print(f"[#0066ee]{sep}[/#0066ee]")
                if agent_label:
                    c.print(f"  [#00d4ff][{agent_label}][/#00d4ff] [bold #00aaff]\u25b6[/bold #00aaff] {user_text}")
                else:
                    c.print(f"  [bold #00aaff]\u25b6[/bold #00aaff] {user_text}")
            elif kind == "response":
                text = data
                if text:
                    for line in text.splitlines():
                        c.print(f"  {line}")
            elif kind == "info":
                c.print(f"  [dim]{data}[/dim]")
            elif kind == "error":
                c.print(f"  [red bold]X[/red bold] [red]{data}[/red]")
            elif kind == "warning":
                c.print(f"  [yellow bold]![/yellow bold] [yellow]{data}[/yellow]")
            elif kind == "success":
                c.print(f"  [green bold]OK[/green bold] [green]{data}[/green]")
            elif kind == "rule":
                c.print(Rule(style=data[0], title=data[1] if len(data) > 1 else None))
            elif kind == "summary":
                c.print(f"  {data}")

    # ── Banner ────────────────────────────────────────────────────────────

    def print_banner(self, record: bool = True) -> None:
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

    # ── Streaming event handler ───────────────────────────────────────────

    def reset_deltas(self) -> None:
        self._received_deltas = False
        self._seen_event_ids.clear()

    @property
    def received_deltas(self) -> bool:
        return self._received_deltas

    def toggle_debug(self) -> bool:
        self.debug_mode = not self.debug_mode
        return self.debug_mode

    # ── Live display helpers ───────────────────────────────────────────────

    def _chat(self, markup: str) -> None:
        self.console.print(markup)

    def _flush_newline(self) -> None:
        self._clear_baking_line()
        if self._needs_newline:
            sys.stdout.write("\n")
            sys.stdout.flush()
            self._needs_newline = False
            self._at_line_start = True

    def _write_indented(self, text: str, indent: str = "  ") -> None:
        """Write text to stdout, prepending *indent* at the start of each line."""
        buf: list[str] = []
        for ch in text:
            if self._at_line_start and ch != "\n":
                if self._pending_assistant_prefix:
                    buf.append("  \033[1;36m\u25b6\033[0m ")
                    self._pending_assistant_prefix = False
                else:
                    buf.append(indent)
                self._at_line_start = False
            buf.append(ch)
            if ch == "\n":
                self._at_line_start = True
        sys.stdout.write("".join(buf))
        sys.stdout.flush()

    def _sidebar(self, markup: str) -> None:
        if self._tracker or self.debug_mode:
            self._flush_newline()
            self.console.print(markup)

    def handle_event(self, event: Any) -> None:
        import json
        from copilot.generated.session_events import SessionEventType

        self._last_event_time = time.time()

        etype = event.type
        d = event.data
        tracker = self._tracker

        # ── Always-on events ──────────────────────────────────────────────

        if etype in (
            SessionEventType.ASSISTANT_MESSAGE_DELTA,
            SessionEventType.ASSISTANT_STREAMING_DELTA,
        ):
            eid = str(event.id)
            if eid in self._seen_event_ids:
                return
            self._seen_event_ids.add(eid)

            self._received_deltas = True
            self._clear_baking_line()
            delta = getattr(d, "delta_content", None) or ""
            if self._in_reasoning and delta:
                self._flush_newline()
                self._in_reasoning = False
            if delta:
                display = delta
                if self._pending_assistant_prefix:
                    display = delta.lstrip("\n")
                if display:
                    self._write_indented(display)
                self._current_response.append(delta)
                self._needs_newline = not delta.endswith("\n")
            return

        if etype == SessionEventType.ASSISTANT_REASONING_DELTA:
            if self.debug_mode:
                self._clear_baking_line()
                self._in_reasoning = True
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
            if self._collector:
                args_raw = getattr(d, "arguments", None)
                args_str = json.dumps(args_raw, ensure_ascii=False) if args_raw else "{}"
                inv_id = self._collector.on_tool_start(str(tool), args_str)
                if inv_id:
                    self._pending_invocations[str(tool)] = inv_id
            if self.debug_mode:
                self._clear_baking_line()
                self.console.print(
                    f" [bold blue]>>[/bold blue] [blue]{tool}[/blue]", end=""
                )
                args = getattr(d, "arguments", None)
                if args is not None:
                    try:
                        raw = json.dumps(args, ensure_ascii=False)
                        self.console.print(f" [dim]{raw[:80]}[/dim]", end="")
                    except Exception:
                        pass
                self._needs_newline = True
            elif tracker and (tracker.tool_count == 1 or tracker.tool_count % 5 == 0):
                self._clear_baking_line()
                self.console.print(
                    f"  [dim cyan]* progress: {tracker.tool_count} tool calls executed[/dim cyan]"
                )
            return

        if etype == SessionEventType.TOOL_EXECUTION_COMPLETE:
            if self._collector:
                tool = getattr(d, "tool_name", None) or getattr(d, "mcp_tool_name", "?")
                inv_id = self._pending_invocations.pop(str(tool), None)
                if inv_id:
                    output_raw = getattr(d, "output", None)
                    output_str = str(output_raw)[:2000] if output_raw else None
                    self._collector.on_tool_end(inv_id, output=output_str, status="success")
            if self.debug_mode:
                self._clear_baking_line()
                duration = getattr(d, "duration", None)
                dur_markup = f" [dim]{duration}ms[/dim]" if duration else ""
                self.console.print(f" [blue]<< done[/blue]{dur_markup}")
            self._needs_newline = False
            return

        if etype == SessionEventType.SESSION_ERROR:
            self._flush_newline()
            self._clear_baking_line()
            msg = getattr(d, "message", str(d))
            self.console.print(f"\n  [red bold]ERROR: {msg}[/red bold]")
            return

        # ── Subagent + session events ─────────────────────────────────────

        if etype == SessionEventType.SUBAGENT_SELECTED:
            name = getattr(d, "agent_name", "?") or "?"
            if self.debug_mode:
                self._sidebar(f"[cyan bold]~~ selected: {name}[/cyan bold]")
            return

        if etype == SessionEventType.SUBAGENT_STARTED:
            name = getattr(d, "agent_name", "?") or "?"
            if tracker:
                tracker.subagent_count += 1
            if self._collector:
                inv_id = self._collector.on_subagent_start(str(name))
                if inv_id:
                    self._pending_invocations[f"subagent:{name}"] = inv_id
            self._sidebar(f"[cyan bold]-> started:  {name}[/cyan bold]")
            return

        if etype == SessionEventType.SUBAGENT_COMPLETED:
            name = getattr(d, "agent_name", "?") or "?"
            if self._collector:
                inv_id = self._pending_invocations.pop(f"subagent:{name}", None)
                if inv_id:
                    self._collector.on_subagent_end(inv_id, status="success")
            self._sidebar(f"[cyan]v subagent done: {name}[/cyan]")
            return

        if etype == SessionEventType.SUBAGENT_DESELECTED:
            name = getattr(d, "agent_name", "?") or "?"
            if self.debug_mode:
                self._sidebar(f"[dim cyan]   deselected: {name}[/dim cyan]")
            return

        if etype == SessionEventType.SUBAGENT_FAILED:
            name = getattr(d, "agent_name", "?") or "?"
            err  = getattr(d, "message", "") or ""
            if self._collector:
                inv_id = self._pending_invocations.pop(f"subagent:{name}", None)
                if inv_id:
                    self._collector.on_subagent_end(
                        inv_id, status="error", error_message=str(err)[:500]
                    )
            self._sidebar(f"[red]XX failed: {name} {err}[/red]")
            return

        if etype == SessionEventType.SESSION_HANDOFF:
            name = getattr(d, "agent_name", None) or "?"
            if self.debug_mode:
                self._sidebar(f"[yellow]~~ handoff -> {name}[/yellow]")
            return

        if etype == SessionEventType.ASSISTANT_USAGE:
            in_t  = int(getattr(d, "input_tokens",       0) or 0)
            out_t = int(getattr(d, "output_tokens",      0) or 0)
            cr_t  = int(getattr(d, "cache_read_tokens",  0) or 0)
            cw_t  = int(getattr(d, "cache_write_tokens", 0) or 0)
            model = getattr(d, "model", None) or ""
            if in_t:
                self._last_input_tokens = in_t
            if self._collector:
                self._collector.on_usage(
                    input_tokens=in_t,
                    output_tokens=out_t,
                    cache_read_tokens=cr_t,
                    cache_write_tokens=cw_t,
                    model=model,
                )
            if not self.debug_mode:
                return
            parts = [f"in={in_t}", f"out={out_t}"]
            if cr_t: parts.append(f"cr={cr_t}")
            if cw_t: parts.append(f"cw={cw_t}")
            if model: parts.append(f"[{model}]")
            self._sidebar(f"[dim]tokens: {' | '.join(parts)}[/dim]")
            return

        if etype == SessionEventType.SESSION_COMPACTION_START:
            if self.debug_mode:
                self._sidebar("[dim yellow]compaction started...[/dim yellow]")
            return

        if etype == SessionEventType.SESSION_COMPACTION_COMPLETE:
            post = int(getattr(d, "post_compaction_tokens", 0) or 0)
            if post:
                self._last_input_tokens = post
            if self.debug_mode:
                self._sidebar(f"[dim yellow]compaction done tokens={post}[/dim yellow]")
            return

        # ── Debug-only events ─────────────────────────────────────────────

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
        label = f"\u2192 {agent_name} | {model}" if agent_name else "\u2192 copilot"
        term_width = shutil.get_terminal_size().columns
        col = max(term_width - len(label), 1)
        sys.stdout.write(f"\033[A\033[{col}G\033[2m{label}\033[0m\033[B\r")
        sys.stdout.flush()

    def print_assistant_prefix(self) -> None:
        self._pending_assistant_prefix = True
        self._at_line_start = True

    def print_input_lock_state(self, locked: bool) -> None:
        pass  # Visual feedback conveyed by the baking spinner bar

    def print_response_end(self) -> None:
        self._flush_newline()
        sys.stdout.write("\033[0m")
        sys.stdout.flush()

    def print_session_created(self, session_id: str) -> None:
        self.session_id = session_id
        self.console.print(
            f"  [dim]Session [cyan]{session_id[:12]}...[/cyan] created[/dim]"
        )
        self.console.print()
        self._record("info", f"Session [cyan]{session_id[:12]}...[/cyan] created")

    def print_output_files(self, files: list[Path]) -> None:
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
            elif suffix in (".sh", ".bash"):
                label = "[yellow bold]SHELL [/yellow bold]"
            else:
                label = "[dim]FILE [/dim]"
            self.console.print(f"  {label}  [cyan]{f}[/cyan]")
        self.console.print()

    def print_help(self) -> None:
        table = Table(
            show_header=True, header_style="bold cyan",
            box=box.SIMPLE, padding=(0, 2), expand=True,
        )
        table.add_column("Command", style="cyan", no_wrap=True)
        table.add_column("Description")

        table.add_row("/new [agent]", "Start a new session (optionally pre-selecting an agent)")
        table.add_row("/resume [id|name]", "Resume a previous session (list resumable or resume by ID/name)")
        table.add_row("/agent <name>", "Switch to a specific agent mid-session")
        table.add_row("/agents", "List all available agents with details")
        table.add_row("/model <id>", "Switch the LLM model")
        table.add_row("/compact", "Manually compact context window (free memory)")
        table.add_row("/debug", "Toggle debug mode (shows tool I/O, subagent flow, token usage)")
        table.add_row("/sessions", "List active and resumable sessions (\u25b6 marks current)")
        table.add_row("/sessions all", "List all sessions including killed ones")
        table.add_row("/sessions <id>", "Show session details and turns")
        table.add_row("/sessions end <id>", "End (kill) an active session")
        table.add_row("/sessions name [id] <nick>", "Set or clear a session nickname")
        table.add_row("/sessions cleanup", "End all orphaned active sessions")
        table.add_row("/usage", "Current session info, context window, and cost")
        table.add_row("/usage all", "Global token usage and cost summary")
        table.add_row("/samples", "Show sample output library")
        table.add_row("/tutorial", "Interactive guided walkthrough")
        table.add_row("/clear", "Clear the screen and redisplay the banner")
        table.add_row("/help", "Show this help")
        table.add_row("/quit", "Exit VBD-Copilot (session remains resumable)")

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
        """Full-screen interactive tutorial with arrow key navigation."""
        from prompt_toolkit import Application
        from prompt_toolkit.layout import Layout
        from prompt_toolkit.layout.containers import Window
        from prompt_toolkit.layout.controls import FormattedTextControl

        pages = self._build_tutorial_pages()
        total = len(pages)
        state = {"current": 0, "done": False}
        self._tutorial_state = {"pages": pages, "current": 0, "total": total}

        def render() -> None:
            self._tutorial_state["current"] = state["current"]
            self._render_tutorial_page(pages, state["current"], total)

        render()

        kb = KeyBindings()

        @kb.add("right")
        @kb.add("l")
        @kb.add(" ")
        @kb.add("enter")
        def _next(event) -> None:
            if state["current"] < total - 1:
                state["current"] += 1
                render()
            else:
                state["done"] = True
                event.app.exit()

        @kb.add("left")
        @kb.add("h")
        @kb.add("backspace")
        def _prev(event) -> None:
            if state["current"] > 0:
                state["current"] -= 1
                render()

        @kb.add("q")
        @kb.add("Q")
        @kb.add("escape")
        @kb.add("c-c")
        def _quit(event) -> None:
            state["done"] = True
            event.app.exit()

        app: Application = Application(
            layout=Layout(Window(FormattedTextControl(""), height=0)),
            key_bindings=kb,
            full_screen=False,
        )
        await app.run_async()

        self._tutorial_state = None

        self.clear()
        self.print_banner()
        if self.session_id:
            self.console.print(
                f"  [dim]Session [cyan]{self.session_id[:12]}...[/cyan] active[/dim]\n"
            )

    def _render_tutorial_page(
        self,
        pages: list,
        idx: int,
        total: int,
    ) -> None:
        self.clear()
        c = self.console
        c.print()
        c.print(pages[idx])
        c.print()

        dots = "  ".join(
            "[bold cyan]\u25cf[/bold cyan]" if i == idx else "[dim]\u25cb[/dim]"
            for i in range(total)
        )
        c.print(f"  {dots}", justify="center")
        c.print()
        c.print("  [dim]\u2190/\u2192  navigate pages   \u00b7   q  quit tutorial[/dim]")

    def _build_tutorial_pages(self) -> list:
        # ── Page 1: Welcome ───────────────────────────────────────────
        p1 = Panel(
            "[bold white]Welcome to VBD-Copilot![/bold white]\n\n"
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
            title="[bold cyan]Welcome[/bold cyan]",
            subtitle="[dim]1 / 6[/dim]",
            border_style="#0055dd",
            padding=(1, 3),
        )

        # ── Page 2: Slide Conductor ───────────────────────────────────
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

        p2 = Panel(
            Group(
                Text.from_markup("[bold white]The Slide Conductor Pipeline[/bold white]\n"),
                pipeline,
                Text.from_markup('\n[dim]Try: "I need a 1-hour L300 deck on Azure Container Apps"[/dim]'),
            ),
            title="[bold cyan]Slide Conductor[/bold cyan]",
            subtitle="[dim]2 / 6[/dim]",
            border_style="#0055dd",
            padding=(1, 3),
        )

        # ── Page 3: Demo Conductor ────────────────────────────────────
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

        p3 = Panel(
            Group(
                Text.from_markup("[bold white]The Demo Conductor Pipeline[/bold white]\n"),
                demo_pipe,
                Text.from_markup('\n[dim]Try: "Create 3 L300 demos on GitHub Copilot for Contoso"[/dim]'),
            ),
            title="[bold cyan]Demo Conductor[/bold cyan]",
            subtitle="[dim]3 / 6[/dim]",
            border_style="#0055dd",
            padding=(1, 3),
        )

        # ── Page 4: Content Levels ────────────────────────────────────
        levels = Table(show_header=True, header_style="bold cyan", box=box.SIMPLE, padding=(0, 2))
        levels.add_column("Level", style="bold white")
        levels.add_column("Audience")
        levels.add_column("Slides (1h)")
        levels.add_column("Demo Style")
        levels.add_row("L100", "Business / Executive", "25-35", "No code, portal clicks")
        levels.add_row("L200", "Technical decision makers", "25-35", "CLI commands, pre-built samples")
        levels.add_row("L300", "Practitioners", "25-35", "Code samples, SDK calls")
        levels.add_row("L400", "Experts", "25-35", "Live coding, internals")

        p4 = Panel(
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
            subtitle="[dim]4 / 6[/dim]",
            border_style="#0055dd",
            padding=(1, 3),
        )

        # ── Page 5: Sessions & Usage ─────────────────────────────────
        p5 = Panel(
            "[bold white]Session Management & Usage Tracking[/bold white]\n\n"
            "VBD-Copilot tracks all sessions, turns, and token usage:\n\n"
            "  [cyan bold]/sessions[/cyan bold]         List active & resumable sessions\n"
            "  [cyan bold]/sessions <id>[/cyan bold]    Inspect a session's turns & details\n"
            "  [cyan bold]/sessions name X[/cyan bold]  Give the current session a nickname\n"
            "  [cyan bold]/resume[/cyan bold]           List or resume previous sessions\n"
            "  [cyan bold]/usage[/cyan bold]            Current session: tokens, cost, context window\n"
            "  [cyan bold]/usage all[/cyan bold]        Global usage summary by agent & model\n"
            "  [cyan bold]/compact[/cyan bold]          Free context window memory\n\n"
            "[bold white]How it works:[/bold white]\n"
            "  - Sessions persist across /new - old sessions remain resumable\n"
            "  - Token usage and costs are tracked per turn in a local DB\n"
            "  - Context window bar shows how full your LLM context is\n"
            "  - /compact removes older messages to free context space",
            title="[bold cyan]Sessions & Usage[/bold cyan]",
            subtitle="[dim]5 / 6[/dim]",
            border_style="#0055dd",
            padding=(1, 3),
        )

        # ── Page 6: Commands & Tips ───────────────────────────────────
        cmds = Table(show_header=False, box=None, padding=(0, 2))
        cmds.add_column(style="cyan bold", width=22)
        cmds.add_column()
        cmds.add_row("/new [agent]", "Start a fresh session")
        cmds.add_row("/resume [id|name]", "Resume a previous session")
        cmds.add_row("/agent <name>", "Switch agent mid-conversation")
        cmds.add_row("/agents", "See all agents")
        cmds.add_row("/model <id>", "Switch LLM model")
        cmds.add_row("/sessions", "Session management")
        cmds.add_row("/usage", "Token usage & costs")
        cmds.add_row("/compact", "Free context memory")
        cmds.add_row("/samples", "View sample output library")
        cmds.add_row("/clear", "Clear screen")
        cmds.add_row("/tutorial", "Re-run this tutorial")
        cmds.add_row("/help", "Quick command reference")
        cmds.add_row("/quit", "Exit")

        p6 = Panel(
            Group(
                Text.from_markup("[bold white]Commands & Tips[/bold white]\n"),
                cmds,
                Text.from_markup(
                    "\n[bold white]Pro tips:[/bold white]\n"
                    "  >> Use [bold]arrow up/down[/bold] for command history\n"
                    "  >> [bold]Tab[/bold] auto-completes commands and agent names\n"
                    "  >> Use [cyan]@slide-conductor[/cyan] or "
                    "[cyan]@demo-conductor[/cyan] to route directly\n"
                    "  >> History persists across sessions (~/.vbd-copilot/)\n"
                    "  >> Set BING_API_KEY env var for reliable web search\n"
                    "  >> Run inside the Dev Container for full functionality\n"
                ),
            ),
            title="[bold cyan]Commands[/bold cyan]",
            subtitle="[dim]6 / 6[/dim]",
            border_style="#0055dd",
            padding=(1, 3),
        )

        return [p1, p2, p3, p4, p5, p6]

    def print_info(self, msg: str) -> None:
        self.console.print(f"  [dim]{msg}[/dim]")
        self._record("info", msg)

    def print_error(self, msg: str) -> None:
        self.console.print(f"  [red bold]X[/red bold] [red]{msg}[/red]")
        self._record("error", msg)

    def print_warning(self, msg: str) -> None:
        self.console.print(f"  [yellow bold]![/yellow bold] [yellow]{msg}[/yellow]")
        self._record("warning", msg)

    def print_success(self, msg: str) -> None:
        self.console.print(f"  [green bold]OK[/green bold] [green]{msg}[/green]")
        self._record("success", msg)

    def clear(self) -> None:
        sys.stdout.write("\033[2J\033[H")
        sys.stdout.flush()
