"""Agent configuration data model."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class AgentConfig:
    """Parsed representation of an agent definition.

    This is the SDK-agnostic equivalent of the dict that the old
    ``agents.py`` used to build for ``CustomAgentConfig``.
    """

    name: str
    display_name: str
    description: str
    prompt: str
    tools: list[str] = field(default_factory=list)
    infer: bool = False
    """Whether this agent is routable from the main loop."""

    model: str = ""
    """Override model for this agent. Empty string = use default."""

    timeout: int = 0
    """Override timeout (seconds). 0 = use default."""

    skills: list[str] = field(default_factory=list)
    """Skill directory names referenced by this agent."""
