"""
Agent router - selects the best top-level agent for a given user prompt
and switches the session model to match the agent's preferred model.

Only routable agents (infer=True) can be selected here. Subagents
are activated by the conductors via delegation tools.

Routing strategy:
1. Explicit prefix:  "@slide-conductor ...", "@demo-conductor ..."
2. Keyword-based intent classification scored against agent names + descriptions.
3. Fallback: no agent is selected (uses the default Copilot agent).
"""

from __future__ import annotations

import logging
import re

from copilot import CopilotClient, CopilotSession

from agents import DEFAULT_MODEL, ROUTABLE_AGENTS

# Stop-words to ignore when scoring keyword overlap
_STOP_WORDS = {
    "a",
    "an",
    "the",
    "and",
    "or",
    "of",
    "to",
    "in",
    "for",
    "on",
    "with",
    "is",
    "it",
    "this",
    "that",
    "any",
    "all",
    "how",
    "what",
    "can",
    "i",
    "me",
    "my",
    "do",
    "you",
    "please",
    "create",
    "make",
    "build",
    "generate",
    "new",
    "some",
    "want",
    "need",
    "get",
    "give",
    "show",
    "using",
    "use",
}

logger = logging.getLogger(__name__)

# ── Keyword-based intent classifier ──────────────────────────────────────────
#
# The Copilot SDK uses a local CLI subprocess on non-Codespaces environments,
# which cannot multiplex concurrent sessions.  Creating a second session for
# LLM-based routing blocks indefinitely because the subprocess is already
# occupied by the main conversation session.
#
# Instead we score the prompt against each routable agent's name tokens and
# description tokens.  For a small, well-named agent catalog this is accurate
# enough and adds zero latency.


def _tokenize(text: str) -> set[str]:
    """Lower-case word tokens, stop-words removed."""
    return {
        w
        for w in re.findall(r"[a-z]+", text.lower())
        if w not in _STOP_WORDS and len(w) > 2
    }


def _build_agent_tokens() -> dict[str, set[str]]:
    """Pre-compute a token set for every routable agent (name + description)."""
    result: dict[str, set[str]] = {}
    for name, cfg in ROUTABLE_AGENTS.items():
        tokens = _tokenize(name) | _tokenize(cfg.get("description", ""))
        result[name] = tokens
    return result


_AGENT_TOKENS: dict[str, set[str]] = {}


async def init_router(client: CopilotClient) -> None:  # noqa: ARG001
    """Pre-compute routing token sets (client kept for API compatibility)."""
    global _AGENT_TOKENS
    _AGENT_TOKENS = _build_agent_tokens()


def _maybe_refresh() -> None:
    """Check for agent file changes and rebuild routing tokens if anything changed.

    Called once per turn.  The hot path is just a few ``stat()`` syscalls —
    file content is never re-read unless an mtime actually changed.
    """
    global _AGENT_TOKENS
    from agents import refresh_catalog

    if refresh_catalog():
        _AGENT_TOKENS = _build_agent_tokens()


def _classify_intent(prompt: str) -> str | None:
    """Return the best-matching routable agent name, or None."""
    if not _AGENT_TOKENS:
        return None

    prompt_tokens = _tokenize(prompt)
    if not prompt_tokens:
        return None

    best_agent: str | None = None
    best_score = 0

    for name, agent_tokens in _AGENT_TOKENS.items():
        overlap = len(prompt_tokens & agent_tokens)
        if overlap > best_score:
            best_score = overlap
            best_agent = name

    # Require at least one meaningful keyword match
    return best_agent if best_score >= 1 else None


async def detect_agent(prompt: str) -> str | None:
    """
    Determine which top-level agent should handle the prompt.
    Returns the agent name, or None to use the default Copilot agent.
    """
    _maybe_refresh()

    # 1. Explicit @mention
    mention = re.match(r"^@([\w-]+)\s", prompt)
    if mention:
        name = mention.group(1).lower()
        if name in ROUTABLE_AGENTS:
            return name

    # 2. Keyword-based intent classification
    return _classify_intent(prompt)


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
        await session.rpc.model.switch_to(
            SessionModelSwitchToParams(model_id=DEFAULT_MODEL)
        )
        return agent_name
    else:
        # Do NOT call session.rpc.agent.get_current() here — it blocks indefinitely
        # on the CLI subprocess in WSL (and other non-Codespaces environments) when
        # no agent-switch RPC is pending.  The caller (app.py) already tracks the
        # active agent in ui.current_agent and preserves it across turns.
        return None
