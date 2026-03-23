#!/usr/bin/env python3
"""
VBD-Copilot - AI-Powered Presentation & Demo Builder
======================================================

A beautiful interactive terminal app built on the GitHub Copilot SDK
that produces customer-ready technical content on any topic:

  - Slide Conductor: generates .pptx presentations with speaker notes
  - Demo Conductor: generates demo guides with companion scripts

Both agents research official docs first, plan with your input, build,
and run automated quality review before delivering output.
"""

from __future__ import annotations

import asyncio
import contextlib
import os
import time
from pathlib import Path

from copilot import CopilotClient
from copilot.jsonrpc import JsonRpcError
from copilot.types import (
    PermissionRequest,
    PermissionRequestResult,
    UserInputRequest,
    UserInputResponse,
)

from agents import AGENT_MODELS, AGENT_TIMEOUTS, ALL_AGENT_CONFIGS, ALL_SKILL_DIRS, DEFAULT_MODEL, DEFAULT_TIMEOUT
from collector import EventCollector
from router import route_to_agent
from store import EventStore
from tools import ALL_CUSTOM_TOOLS
from ui import CopilotUI

# ── Resolve paths ─────────────────────────────────────────────────────────────
APP_DIR = Path(__file__).resolve().parent
OUTPUTS_DIR = APP_DIR / "outputs"
PLANS_DIR = APP_DIR / "plans"
DB_DIR = Path.home() / ".vbd-copilot"


# ── Output file detection ─────────────────────────────────────────────────────

_INTERESTING_SUFFIXES = {".pptx", ".md", ".py"}
_SKIP_DIRS = {".fragments"}


def _find_new_outputs(since: float) -> list[Path]:
    """Return output files created/modified after `since` (epoch seconds)."""
    found: list[Path] = []
    grace = 3.0
    for p in OUTPUTS_DIR.rglob("*"):
        if not p.is_file():
            continue
        if any(part in _SKIP_DIRS for part in p.parts):
            continue
        if p.suffix.lower() not in _INTERESTING_SUFFIXES:
            continue
        if "-plan.md" in p.name:
            continue
        try:
            if p.stat().st_mtime >= since - grace:
                found.append(p)
        except OSError:
            pass
    return found


# =============================================================================
# Main application
# =============================================================================

async def main() -> None:
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUTS_DIR / "slides").mkdir(exist_ok=True)
    (OUTPUTS_DIR / "demos").mkdir(exist_ok=True)
    PLANS_DIR.mkdir(parents=True, exist_ok=True)

    # ── Event store (SQLite) ──────────────────────────────────────────────────
    db_path = DB_DIR / "vbd-copilot.db"
    event_store = EventStore(db_path, retention_days=90)
    collector = EventCollector(event_store)

    # ── Initialise UI ─────────────────────────────────────────────────────────
    ui = CopilotUI(collector=collector)
    ui.print_banner()

    # Start background resize watcher
    ui.start_resize_watcher()

    # ── Callbacks ─────────────────────────────────────────────────────────────

    async def handle_permission(
        request: PermissionRequest, invocation: dict[str, str]
    ) -> PermissionRequestResult:
        kind = request.get("kind", "unknown")
        if ui.debug_mode:
            ui.print_info(f"[permission] {kind} -> approved")
        return PermissionRequestResult(kind="approved")

    async def handle_user_input(
        request: UserInputRequest, invocation: dict[str, str]
    ) -> UserInputResponse:
        question = request.get("question", "The agent has a question for you:")
        choices = request.get("choices")
        allow_freeform = request.get("allowFreeform", True)
        answer, was_freeform = await ui.ask_user_prompt(
            question, choices, allow_freeform
        )
        return UserInputResponse(answer=answer, wasFreeform=was_freeform)

    async def on_prompt_submitted(
        input_data: dict, invocation: dict
    ) -> dict | None:
        return None

    # ── Client & session ──────────────────────────────────────────────────────

    client_opts = {}
    github_token = os.environ.get("GITHUB_TOKEN")
    if github_token:
        client_opts["github_token"] = github_token
    elif Path("/.dockerenv").exists() or os.environ.get("container"):
        ui.console.print(
            "\n  [red bold]ERROR: GITHUB_TOKEN not set.[/red bold]\n\n"
            "  Docker containers cannot access the host credential store\n"
            "  (macOS Keychain / Windows Credential Manager).\n\n"
            "  [bold]Fix:[/bold] pass your GitHub token when starting the container:\n\n"
            "    [cyan]docker run -it --rm \\\\\n"
            "      -e GITHUB_TOKEN=$(gh auth token) \\\\\n"
            "      -v \"$(pwd)/outputs:/app/outputs\" \\\\\n"
            "      vbd-copilot[/cyan]\n\n"
            "  If [cyan]gh auth token[/cyan] fails, run [cyan]gh auth login[/cyan] first.\n"
        )
        return

    client = CopilotClient(client_opts or None)
    await client.start()

    # ── Cache model context-window limits ─────────────────────────────────────
    model_limits: dict[str, int] = {}
    try:
        models_result = await client.rpc.models.list()
        for m in models_result.models:
            ctx = int(m.capabilities.limits.max_context_window_tokens or 0)
            if ctx:
                model_limits[m.id] = ctx
    except Exception:
        pass

    # Inject CLI health check so UI can detect dead processes
    def _check_cli_health() -> tuple[bool, str]:
        proc = getattr(client, "_process", None)
        if proc is None:
            return False, "no CLI process found"
        rc = proc.poll()
        if rc is not None:
            stderr = ""
            rpc_client = getattr(client, "_client", None)
            if rpc_client and hasattr(rpc_client, "get_stderr_output"):
                stderr = rpc_client.get_stderr_output() or ""
            return False, f"exited with code {rc}" + (f"\n  stderr: {stderr}" if stderr else "")
        return True, f"pid={proc.pid}"

    ui._cli_health_check = _check_cli_health

    session = None

    async def create_session(agent_hint: str | None = None) -> None:
        nonlocal session
        if session:
            with contextlib.suppress(Exception):
                collector.on_session_ended(session.session_id, resumable=True)
                # Do NOT destroy - keep server-side state so /resume works.
                session._event_handlers.clear()

        # If the CLI subprocess died, restart it before creating a session.
        try:
            session = await client.create_session(
                {
                    "model": DEFAULT_MODEL,
                    "streaming": True,
                    "custom_agents": ALL_AGENT_CONFIGS,
                    "tools": ALL_CUSTOM_TOOLS,
                    "skill_directories": ALL_SKILL_DIRS,
                    "on_permission_request": handle_permission,
                    "on_user_input_request": handle_user_input,
                    "working_directory": str(APP_DIR),
                    "hooks": {
                        "on_user_prompt_submitted": on_prompt_submitted,
                    },
                }
            )
        except (BrokenPipeError, OSError):
            # Subprocess is dead - restart client and retry once.
            with contextlib.suppress(Exception):
                await client.stop()
            await client.start()
            session = await client.create_session(
                {
                    "model": DEFAULT_MODEL,
                    "streaming": True,
                    "custom_agents": ALL_AGENT_CONFIGS,
                    "tools": ALL_CUSTOM_TOOLS,
                    "skill_directories": ALL_SKILL_DIRS,
                    "on_permission_request": handle_permission,
                    "on_user_input_request": handle_user_input,
                    "working_directory": str(APP_DIR),
                    "hooks": {
                        "on_user_prompt_submitted": on_prompt_submitted,
                    },
                }
            )
        session.on(ui.handle_event)
        ui.current_agent = None
        ui.current_model = DEFAULT_MODEL
        ui.print_session_created(session.session_id)
        collector.on_session_created(
            session.session_id,
            agent="copilot",
            model=DEFAULT_MODEL,
            frontend="cli",
            server_mode="stdio",
        )

        # Pre-select agent if requested
        if agent_hint:
            from copilot.generated.rpc import (
                SessionAgentSelectParams,
                SessionModelSwitchToParams,
            )

            try:
                await session.rpc.agent.select(
                    SessionAgentSelectParams(name=agent_hint)
                )
                model = AGENT_MODELS.get(agent_hint, DEFAULT_MODEL)
                await session.rpc.model.switch_to(
                    SessionModelSwitchToParams(model_id=model)
                )
                ui.current_agent = agent_hint
                ui.current_model = model
                event_store.update_session_agent(session.session_id, agent_hint)
                event_store.update_session_model(session.session_id, model)
            except Exception as exc:
                ui.print_error(f"Could not pre-select agent '{agent_hint}': {exc}")

    await create_session()

    # ── Interactive loop ──────────────────────────────────────────────────────

    try:
        while True:
            user_input = await ui.prompt()

            if user_input is None:
                break

            user_input = user_input.strip()
            if not user_input:
                continue

            # ── Slash commands ────────────────────────────────────────────
            if user_input.startswith("/"):
                parts = user_input.split(None, 1)
                cmd = parts[0].lower()
                arg = parts[1].strip() if len(parts) > 1 else ""

                if cmd in ("/quit", "/exit"):
                    break

                elif cmd == "/new":
                    ui.clear_history()
                    ui.print_info("Creating new session...")
                    await create_session(arg if arg else None)
                    ui.clear()
                    ui.print_banner()
                    ui.print_session_created(session.session_id)
                    continue

                elif cmd == "/help":
                    ui.print_help()
                    continue

                elif cmd == "/tutorial":
                    await ui.print_tutorial()
                    continue

                elif cmd == "/agents":
                    ui.print_agents_list()
                    continue

                elif cmd == "/agent":
                    if not arg:
                        ui.print_error("Usage: /agent <name>")
                        continue
                    from copilot.generated.rpc import (
                        SessionAgentSelectParams,
                        SessionModelSwitchToParams,
                    )

                    try:
                        await session.rpc.agent.select(
                            SessionAgentSelectParams(name=arg)
                        )
                        model = AGENT_MODELS.get(arg, DEFAULT_MODEL)
                        await session.rpc.model.switch_to(
                            SessionModelSwitchToParams(model_id=model)
                        )
                        ui.current_agent = arg
                        ui.current_model = model
                        event_store.update_session_agent(session.session_id, arg)
                        event_store.update_session_model(session.session_id, model)
                        ui.print_success(f"Switched to {arg} (model: {model})")
                    except Exception as exc:
                        ui.print_error(f"Failed to switch agent: {exc}")
                    continue

                elif cmd == "/debug":
                    new_state = ui.toggle_debug()
                    if new_state:
                        ui.print_success("Debug mode ON  -  tool I/O, subagent flow, token usage visible")
                    else:
                        ui.print_success("Debug mode OFF")
                    continue

                elif cmd == "/model":
                    if not arg:
                        ui.print_error("Usage: /model <model_id>")
                        continue
                    from copilot.generated.rpc import SessionModelSwitchToParams

                    try:
                        await session.rpc.model.switch_to(
                            SessionModelSwitchToParams(model_id=arg)
                        )
                        ui.current_model = arg
                        event_store.update_session_model(session.session_id, arg)
                        ui.print_success(f"Switched to model: {arg}")
                    except Exception as exc:
                        ui.print_error(f"Failed to switch model: {exc}")
                    continue

                elif cmd == "/samples":
                    ui.print_samples()
                    continue

                elif cmd == "/clear":
                    ui.clear_history()
                    ui.clear()
                    ui.print_banner()
                    continue

                elif cmd == "/sessions":
                    from commands.sessions import (
                        _CURRENT_SESSION_ENDED,
                        handle_sessions,
                    )

                    result = handle_sessions(
                        arg, event_store, ui.console,
                        current_session_id=session.session_id if session else None,
                    )
                    if result == _CURRENT_SESSION_ENDED:
                        await create_session()
                    continue

                elif cmd == "/usage":
                    from commands.usage import handle_usage

                    handle_usage(
                        arg, event_store, ui.console,
                        session_id=session.session_id if session else None,
                        current_agent=ui.current_agent,
                        current_model=ui.current_model,
                        last_input_tokens=ui._last_input_tokens,
                        model_limits=model_limits,
                    )
                    continue

                elif cmd == "/resume":
                    if not arg:
                        from queries import get_resumable_sessions

                        resumable = get_resumable_sessions(event_store)
                        if not resumable:
                            ui.print_info("No resumable sessions found.")
                        else:
                            ui.console.print()
                            ui.console.print("  [bold]Resumable Sessions[/bold]")
                            for rs in resumable[:10]:
                                sid = rs["id"][:12] + "..."
                                nick = rs.get("nickname") or ""
                                started = rs.get("started_at", "")[:19]
                                turns = rs.get("turn_count", 0)
                                label = (
                                    f"    [#58a6ff]{nick}[/#58a6ff] "
                                    f"[cyan]({sid})[/cyan] "
                                    if nick
                                    else f"    [cyan]{sid}[/cyan] "
                                )
                                ui.console.print(
                                    f"{label}"
                                    f"[#00d4ff]{rs.get('agent', '')}[/#00d4ff] "
                                    f"[dim]{started} ({turns} turns)[/dim]"
                                )
                            ui.console.print()
                            ui.console.print(
                                "  [dim]Use [cyan]/resume <id|name>[/cyan] to continue a session.[/dim]"
                            )
                            ui.console.print()
                    else:
                        full_id = event_store.resolve_prefix("sessions", arg)
                        if not full_id:
                            ui.print_error(f"Session '{arg}' not found.")
                            continue
                        s_detail = event_store.get_session(full_id)
                        if not s_detail or not s_detail.get("resumable"):
                            ui.print_error(
                                f"Session '{arg}' is not resumable "
                                "(ended with /sessions end or not yet ended)."
                            )
                            continue
                        ui.print_info(f"Resuming session {full_id[:12]}...")
                        try:
                            new_session = await client.resume_session(
                                full_id,
                                {
                                    "streaming": True,
                                    "custom_agents": ALL_AGENT_CONFIGS,
                                    "tools": ALL_CUSTOM_TOOLS,
                                    "skill_directories": ALL_SKILL_DIRS,
                                    "on_permission_request": handle_permission,
                                    "on_user_input_request": handle_user_input,
                                    "working_directory": str(APP_DIR),
                                    "hooks": {
                                        "on_user_prompt_submitted": on_prompt_submitted,
                                    },
                                },
                            )
                        except Exception as exc:
                            msg = str(exc)
                            if "Session not found" in msg:
                                event_store.end_session(full_id, resumable=False)
                                ui.print_error(
                                    f"Session {full_id[:12]}... is no longer available "
                                    "(server was restarted). Marked as non-resumable."
                                )
                            else:
                                ui.print_error(f"Failed to resume session: {exc}")
                            continue
                        # Success - detach old session
                        if session:
                            collector.on_session_ended(session.session_id, resumable=True)
                            with contextlib.suppress(Exception):
                                session._event_handlers.clear()
                        session = new_session
                        session.on(ui.handle_event)
                        event_store.reactivate_session(full_id)
                        turns = event_store.get_turns(full_id)
                        if turns:
                            last_turn = turns[-1]
                            raw_agent = last_turn.get("agent") or s_detail.get("agent", "")
                            ui.current_model = last_turn.get("model") or s_detail.get("model", DEFAULT_MODEL)
                        else:
                            raw_agent = s_detail.get("agent", "") or ""
                            ui.current_model = s_detail.get("model", DEFAULT_MODEL)
                        ui.current_agent = raw_agent if raw_agent in AGENT_MODELS else None
                        ui.session_id = full_id
                        ui._last_input_tokens = 0
                        ui.print_success(
                            f"Resumed session [cyan]{full_id[:12]}...[/cyan] "
                            f"({s_detail.get('turn_count', 0)} turns)"
                        )
                        if turns:
                            ui.console.print()
                            ui.console.print("  [bold]Conversation History[/bold]")
                            for t in turns:
                                num = t.get("turn_number", "?")
                                agent = t.get("agent", "")
                                prompt = t.get("user_prompt", "")
                                response = t.get("assistant_response", "")
                                ui.console.print(
                                    f"\n  [dim]Turn {num}[/dim] "
                                    f"[#00d4ff]{agent}[/#00d4ff]"
                                )
                                if prompt:
                                    ui.console.print(
                                        f"  [bold white]You:[/bold white] {prompt[:500]}"
                                    )
                                if response:
                                    preview = response[:1000]
                                    if len(response) > 1000:
                                        preview += "..."
                                    ui.console.print(
                                        f"  [dim]Assistant:[/dim] {preview}"
                                    )
                            ui.console.print()
                    continue

                elif cmd == "/compact":
                    if not session:
                        ui.print_error("No active session.")
                        continue
                    ui.print_info("Compacting context...")
                    try:
                        result = await session.rpc.compaction.compact()
                        if result.success:
                            freed = int(result.tokens_removed)
                            removed = int(result.messages_removed)
                            ui._last_input_tokens = max(
                                ui._last_input_tokens - freed, 0
                            )
                            ui.print_success(
                                f"Compaction done: {removed} messages removed, "
                                f"{freed:,} tokens freed"
                            )
                        else:
                            ui.print_warning("Compaction completed but reported no success.")
                    except Exception as exc:
                        msg = str(exc)
                        if "Nothing to compact" in msg:
                            ui.print_info("Nothing to compact - context is already minimal.")
                        else:
                            ui.print_error(f"Compaction failed: {exc}")
                    continue

                else:
                    ui.print_error(
                        f"Unknown command: {cmd}. Type /help for available commands."
                    )
                    continue

            # ── Legacy quit/exit ──────────────────────────────────────────
            if user_input.lower() in ("quit", "exit"):
                break

            # ── Route to the appropriate agent ────────────────────────────
            try:
                agent_name = await route_to_agent(session, user_input)
            except JsonRpcError as exc:
                if "Session not found" in str(exc):
                    ui.print_warning(
                        "Session expired. Use /new to start a fresh session or quit."
                    )
                else:
                    ui.print_warning(
                        f"Session error: {exc}. Use /new to start a fresh session or quit."
                    )
                continue
            except (BrokenPipeError, OSError):
                ui.print_warning(
                    "Session disconnected. Use /new to start a fresh session or quit."
                )
                continue
            if agent_name:
                model = AGENT_MODELS.get(agent_name, DEFAULT_MODEL)
                ui.current_agent = agent_name
                ui.current_model = model
                event_store.update_session_agent(session.session_id, agent_name)
                event_store.update_session_model(session.session_id, model)

            # ── Strip @mention prefix ─────────────────────────────────────
            clean_prompt = user_input
            if user_input.startswith("@"):
                clean_prompt = (
                    user_input.split(" ", 1)[1]
                    if " " in user_input
                    else user_input
                )

            # ── Record user input for history replay ──────────────────────
            ui.record_user_input(user_input)

            # ── Start tracking agent run ──────────────────────────────────
            ui.start_agent_display()
            before_time = time.time()

            ui.print_routing(agent_name, ui.current_model)
            ui.print_assistant_prefix()
            ui.print_input_lock_state(True)
            ui.reset_deltas()

            effective_timeout = AGENT_TIMEOUTS.get(
                ui.current_agent or "", DEFAULT_TIMEOUT
            )

            # ── Turn tracking ─────────────────────────────────────────────
            turn_id = collector.on_turn_start(
                session.session_id,
                agent=ui.current_agent or "copilot",
                model=ui.current_model,
                user_prompt=clean_prompt,
            )

            turn_status = "success"
            try:
                reply = await session.send_and_wait(
                    {"prompt": clean_prompt}, timeout=effective_timeout
                )
            except TimeoutError:
                turn_status = "timeout"
                ui.print_response_end()
                ui.stop_agent_display()
                ui.print_input_lock_state(False)
                mins = effective_timeout // 60
                ui.console.print(
                    f"  [yellow bold]Timeout[/yellow bold] [yellow]after {mins} min - "
                    f"the agent is still running on the server.\n"
                    f"  You can keep chatting; it may deliver results on the next turn.\n"
                    f"  Use [cyan]/new[/cyan] to start a fresh session.[/yellow]"
                )
                collector.on_turn_end(
                    turn_id,
                    assistant_response="".join(ui._current_response),
                    model=ui.current_model,
                    status="timeout",
                )
                continue
            except (BrokenPipeError, OSError):
                turn_status = "error"
                ui.print_response_end()
                ui.stop_agent_display()
                ui.print_input_lock_state(False)
                ui.print_warning(
                    "Session disconnected. Use /new to start a fresh session or quit."
                )
                collector.on_turn_end(
                    turn_id,
                    assistant_response="".join(ui._current_response),
                    model=ui.current_model,
                    status="error",
                )
                continue
            except JsonRpcError as exc:
                turn_status = "error"
                ui.print_response_end()
                ui.stop_agent_display()
                ui.print_input_lock_state(False)
                if "Session not found" in str(exc):
                    ui.print_warning(
                        "Session expired. Use /new to start a fresh session or quit."
                    )
                else:
                    ui.print_warning(
                        f"Session error: {exc}. Use /new to start a fresh session or quit."
                    )
                collector.on_turn_end(
                    turn_id,
                    assistant_response="".join(ui._current_response),
                    model=ui.current_model,
                    status="error",
                )
                continue
            except (KeyboardInterrupt, asyncio.CancelledError):
                turn_status = "cancelled"
                ui.print_response_end()
                ui.stop_agent_display()
                ui.print_input_lock_state(False)
                ui.console.print(
                    "\n  [yellow]Cancelled.[/yellow] [dim]The agent was interrupted. "
                    "You can keep chatting or use [cyan]/new[/cyan] for a fresh session.[/dim]"
                )
                collector.on_turn_end(
                    turn_id,
                    assistant_response="".join(ui._current_response),
                    model=ui.current_model,
                    status="cancelled",
                )
                continue

            if not ui.received_deltas and reply:
                content = getattr(reply.data, "content", None)
                if content:
                    ui._write_indented(content)
                    ui._current_response.append(content)

            ui.print_response_end()

            # ── Notify about any newly generated output files ─────────────
            new_files = _find_new_outputs(before_time)
            ui.print_output_files(new_files)

            ui.stop_agent_display()
            ui.print_input_lock_state(False)

            # ── End turn tracking ─────────────────────────────────────────
            collector.on_turn_end(
                turn_id,
                assistant_response="".join(ui._current_response),
                model=ui.current_model,
                status=turn_status,
            )

    except KeyboardInterrupt:
        ui.stop_agent_display()
        ui.console.print("\n  [dim]Interrupted.[/dim]")
    except asyncio.CancelledError:
        ui.stop_agent_display()
        ui.console.print("\n  [dim]Cancelled.[/dim]")
    finally:
        # ── Clean up ─────────────────────────────────────────────────────
        ui.stop_resize_watcher()
        ui.print_info("Cleaning up...")
        try:
            if session:
                collector.on_session_ended(session.session_id, resumable=True)
                session._event_handlers.clear()
            await client.stop()
        except Exception:
            pass
        event_store.close()
        ui.print_success("Done! Goodbye.")


# =============================================================================
# Entry point
# =============================================================================

def main_entry() -> None:
    """Synchronous entry point (for pyproject.toml console_scripts)."""
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main_entry()
