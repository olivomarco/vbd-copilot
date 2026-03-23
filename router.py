"""
Agent router - selects the best top-level agent for a given user prompt
and switches the session model to match the agent's preferred model.

Only routable agents (infer=True) can be selected here. Subagents
are activated by the conductors via delegation tools.

Routing strategy:
1. Explicit prefix:  "@slide-conductor ...", "@demo-conductor ..."
2. LLM-based intent classification via a dedicated Copilot SDK
   classifier session (uses GPT-4.1 through the CLI runtime).
3. Fallback: no agent is selected (uses the default Copilot agent).
"""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Any

from copilot import CopilotClient, CopilotSession
from copilot.generated.session_events import SessionEventType
from copilot.types import PermissionRequest, PermissionRequestResult

from agents import AGENT_MODELS, DEFAULT_MODEL, ROUTABLE_AGENTS

logger = logging.getLogger(__name__)

# ── Classifier session state ──────────────────────────────────────────────────

_ROUTING_MODEL = "gpt-4.1"

_copilot_client: CopilotClient | None = None
_classifier_session: CopilotSession | None = None
_classifier_lock = asyncio.Lock()


def _build_system_prompt() -> str:
    """Build the classification system prompt from the routable agent catalog."""
    lines = [
        "You are an intent classifier. Given a user message, decide which "
        "agent should handle it. Reply with ONLY the agent name (lowercase, "
        "exactly as listed) or the word none if no agent is a good fit.",
        "",
        "Available agents:",
    ]
    for name, cfg in ROUTABLE_AGENTS.items():
        desc = cfg.get("description", "")
        lines.append(f"- {name}: {desc}")

    lines.extend([
        "",
        "Rules:",
        "- Pick the single best-matching agent.",
        "- If the message is general conversation, a greeting, or does not "
        "clearly match any agent, reply none.",
        "- Reply with the agent name only, no extra text.",
    ])
    return "\n".join(lines)


async def init_router(client: CopilotClient) -> None:
    """Store the CopilotClient reference for classifier session creation."""
    global _copilot_client
    _copilot_client = client


async def _auto_approve(
    request: PermissionRequest, invocation: dict[str, str]
) -> PermissionRequestResult:
    return PermissionRequestResult(kind="approved")


async def _ensure_classifier() -> CopilotSession:
    """Lazily create (or recreate) a lightweight classifier session."""
    global _classifier_session
    async with _classifier_lock:
        if _classifier_session is not None:
            return _classifier_session

        if _copilot_client is None:
            raise RuntimeError("Router not initialised - call init_router() first")

        _classifier_session = await _copilot_client.create_session(
            {
                "model": _ROUTING_MODEL,
                "streaming": True,
                "system_message": {
                    "mode": "replace",
                    "content": _build_system_prompt(),
                },
                "on_permission_request": _auto_approve,
            }
        )
        return _classifier_session


async def _classify_intent(prompt: str) -> str | None:
    """Use the Copilot SDK classifier session to pick the right agent."""
    try:
        session = await _ensure_classifier()

        # Collect streamed deltas for this turn
        response_parts: list[str] = []

        def _on_event(event: Any) -> None:
            if event.type in (
                SessionEventType.ASSISTANT_MESSAGE_DELTA,
                SessionEventType.ASSISTANT_STREAMING_DELTA,
            ):
                delta = getattr(event.data, "delta_content", None) or ""
                if delta:
                    response_parts.append(delta)

        unsubscribe = session.on(_on_event)
        try:
            reply = await session.send_and_wait(
                {"prompt": prompt}, timeout=15
            )
        finally:
            unsubscribe()

        # Prefer streamed text; fall back to reply content
        answer = "".join(response_parts).strip().lower()
        if not answer and reply:
            content = getattr(reply.data, "content", None)
            if content:
                answer = content.strip().lower()

        if answer in ROUTABLE_AGENTS:
            return answer
        return None

    except Exception:
        # On any failure, discard the session so a fresh one is created next time
        global _classifier_session
        _classifier_session = None
        logger.warning(
            "LLM routing via Copilot SDK failed, falling back to no agent",
            exc_info=True,
        )
        return None


async def detect_agent(prompt: str) -> str | None:
    """
    Determine which top-level agent should handle the prompt.
    Returns the agent name, or None to use the default Copilot agent.
    """
    # 1. Explicit @mention
    mention = re.match(r"^@([\w-]+)\s", prompt)
    if mention:
        name = mention.group(1).lower()
        if name in ROUTABLE_AGENTS:
            return name

    # 2. LLM-based intent classification via Copilot SDK
    return await _classify_intent(prompt)


async def route_to_agent(session: CopilotSession, prompt: str) -> str | None:
    """
    Detect which agent to use, select it, and switch the model.
    Returns the agent name that is active, or None if using the default.
    """
    agent_name = await detect_agent(prompt)

    if agent_name:
        from copilot.generated.rpc import (
            SessionAgentSelectParams,
            SessionModelSwitchToParams,
        )

        await session.rpc.agent.select(SessionAgentSelectParams(name=agent_name))
        model = AGENT_MODELS.get(agent_name, DEFAULT_MODEL)
        await session.rpc.model.switch_to(SessionModelSwitchToParams(model_id=model))
        return agent_name
    else:
        current = await session.rpc.agent.get_current()
        if current.agent is not None:
            return current.agent.name
        return None
