"""
Agent router - selects the best top-level agent for a given user prompt
and switches the session model to match the agent's preferred model.

Only routable agents (infer=True) can be selected here. Subagents
are activated by the conductors via delegation tools.

Routing strategy:
1. Explicit prefix:  "@slide-conductor ...", "@demo-conductor ..."
2. Keyword heuristics: looks for signal words in the prompt.
3. Fallback: no agent is selected (uses the default Copilot agent).
"""

from __future__ import annotations

import re

from copilot import CopilotSession

from agents import AGENT_MODELS, DEFAULT_MODEL, ROUTABLE_AGENTS

# ── Keyword patterns per routable agent ───────────────────────────────────────

_PATTERNS: dict[str, re.Pattern[str]] = {
    "slide-conductor": re.compile(
        r"\b(slide|presentation|pptx|powerpoint|deck|create\s+(a\s+)?deck"
        r"|generate\s+(a\s+)?(pptx|presentation|slide)|build\s+(a\s+)?deck"
        r"|make\s+(a\s+)?(presentation|slide|pptx))\b",
        re.IGNORECASE,
    ),
    "demo-conductor": re.compile(
        r"\b(demos?\b|walkthrough|hands[- ]?on|live\s+demo|demo\s+guide"
        r"|create\s+(a\s+)?demos?|build\s+(a\s+)?demos?|generate\s+(a\s+)?demos?"
        r"|demo\s+script|companion\s+script|demo\s+package)",
        re.IGNORECASE,
    ),
}


def detect_agent(prompt: str) -> str | None:
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

    # 2. Keyword scoring
    scores: dict[str, int] = {}
    for agent_name, pattern in _PATTERNS.items():
        matches = pattern.findall(prompt)
        if matches:
            scores[agent_name] = len(matches)

    if scores:
        best = max(scores, key=lambda k: scores[k])
        if scores[best] >= 1:
            return best

    # 3. No clear match - fallback
    return None


async def route_to_agent(session: CopilotSession, prompt: str) -> str | None:
    """
    Detect which agent to use, select it, and switch the model.
    Returns the agent name that is active, or None if using the default.
    """
    agent_name = detect_agent(prompt)

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
