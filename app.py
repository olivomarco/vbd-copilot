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
import signal
import time
from pathlib import Path

from copilot import CopilotClient
from copilot.types import (
    PermissionRequest,
    PermissionRequestResult,
    UserInputRequest,
    UserInputResponse,
)

from agents import AGENT_MODELS, AGENT_TIMEOUTS, ALL_AGENT_CONFIGS, DEFAULT_MODEL, DEFAULT_TIMEOUT
from router import route_to_agent
from tools import ALL_CUSTOM_TOOLS
from ui import CopilotUI

# ── Resolve paths ─────────────────────────────────────────────────────────────
APP_DIR = Path(__file__).resolve().parent
SKILLS_DIR = str(APP_DIR / "skills")
OUTPUTS_DIR = APP_DIR / "outputs"
PLANS_DIR = APP_DIR / "plans"


# ── Output file detection ─────────────────────────────────────────────────────

_INTERESTING_SUFFIXES = {".pptx", ".md", ".py"}
_SKIP_DIRS = {".fragments"}


def _find_new_outputs(since: float) -> list[Path]:
    """Return output files created/modified after `since` (epoch seconds)."""
    found: list[Path] = []
    grace = 3.0  # seconds of slack for file-system timestamp resolution
    for p in OUTPUTS_DIR.rglob("*"):
        if not p.is_file():
            continue
        if any(part in _SKIP_DIRS for part in p.parts):
            continue
        if p.suffix.lower() not in _INTERESTING_SUFFIXES:
            continue
        # Exclude intermediate plan files from plans/ directory
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

    # ── Initialise UI ─────────────────────────────────────────────────────────
    ui = CopilotUI()
    ui.print_banner()

    # Register terminal resize handler (Unix only)
    if hasattr(signal, "SIGWINCH"):
        loop = asyncio.get_running_loop()
        loop.add_signal_handler(signal.SIGWINCH, ui.handle_resize)

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

    client = CopilotClient()
    await client.start()

    session = None

    async def create_session(agent_hint: str | None = None) -> None:
        nonlocal session
        if session:
            try:
                await session.destroy()
            except Exception:
                pass

        session = await client.create_session(
            {
                "model": DEFAULT_MODEL,
                "streaming": True,
                "custom_agents": ALL_AGENT_CONFIGS,
                "tools": ALL_CUSTOM_TOOLS,
                "skill_directories": [SKILLS_DIR],
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
                        ui.print_success(f"Switched to model: {arg}")
                    except Exception as exc:
                        ui.print_error(f"Failed to switch model: {exc}")
                    continue

                elif cmd == "/samples":
                    ui.print_samples()
                    continue

                elif cmd == "/clear":
                    ui.clear()
                    ui.print_banner()
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
            agent_name = await route_to_agent(session, user_input)
            if agent_name:
                model = AGENT_MODELS.get(agent_name, DEFAULT_MODEL)
                ui.current_agent = agent_name
                ui.current_model = model

            # ── Strip @mention prefix ─────────────────────────────────────
            clean_prompt = user_input
            if user_input.startswith("@"):
                clean_prompt = (
                    user_input.split(" ", 1)[1]
                    if " " in user_input
                    else user_input
                )

            # ── Start tracking agent run ──────────────────────────────────
            ui.start_agent_display()
            before_time = time.time()

            ui.print_routing(agent_name, ui.current_model)
            ui.print_assistant_prefix()
            ui.reset_deltas()

            effective_timeout = AGENT_TIMEOUTS.get(
                ui.current_agent or "", DEFAULT_TIMEOUT
            )

            try:
                reply = await session.send_and_wait(
                    {"prompt": clean_prompt}, timeout=effective_timeout
                )
            except TimeoutError:
                ui.print_response_end()
                ui.stop_agent_display()
                mins = effective_timeout // 60
                ui.console.print(
                    f"  [yellow bold]Timeout[/yellow bold] [yellow]after {mins} min - "
                    f"the agent is still running on the server.\n"
                    f"  You can keep chatting; it may deliver results on the next turn.\n"
                    f"  Use [cyan]/new[/cyan] to start a fresh session.[/yellow]"
                )
                continue

            if not ui.received_deltas and reply:
                content = getattr(reply.data, "content", None)
                if content:
                    print(content, end="")

            ui.print_response_end()

            # ── Notify about any newly generated output files ─────────────
            new_files = _find_new_outputs(before_time)
            ui.print_output_files(new_files)

            ui.stop_agent_display()

    except KeyboardInterrupt:
        ui.stop_agent_display()
        ui.console.print("\n  [dim]Interrupted.[/dim]")

    # ── Clean up ──────────────────────────────────────────────────────────────
    ui.print_info("Cleaning up...")
    try:
        if session:
            await session.destroy()
        await client.stop()
    except Exception:
        pass
    ui.print_success("Done! Goodbye.")


# =============================================================================
# Entry point
# =============================================================================

def main_entry() -> None:
    """Synchronous entry point (for pyproject.toml console_scripts)."""
    asyncio.run(main())


if __name__ == "__main__":
    main_entry()
