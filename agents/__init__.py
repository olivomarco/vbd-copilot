"""
Agent definitions for VBD-Copilot.

Loads agents from ``agent_defs/*.md`` files via the ``agents`` package
and re-exports backward-compatible module-level constants so that
``app.py``, ``router.py``, and ``tools.py`` continue to work unchanged.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from agents.loader import AgentSource, FileSystemAgentSource, load_agent
from agents.models import AgentConfig
from agents.registry import AgentCatalog

# -- Resolve paths -------------------------------------------------------------

_PKG_DIR = Path(__file__).resolve().parent          # agents/
_APP_DIR = _PKG_DIR.parent                          # project root
_DEFS_DIR = _APP_DIR / "agent_defs"
_SKILLS_DIR = _APP_DIR / "skills"

# -- Build catalog -------------------------------------------------------------

_source = FileSystemAgentSource(_DEFS_DIR)
CATALOG = AgentCatalog(_source.load_all(), _SKILLS_DIR)


# -- SDK config converter ------------------------------------------------------

def _build_sdk_config(agent: AgentConfig) -> dict[str, Any]:
    """Convert a core AgentConfig to the dict shape expected by the SDK."""
    return {
        "name": agent.name,
        "display_name": agent.display_name,
        "description": agent.description,
        "prompt": agent.prompt,
        "tools": agent.tools,
        "infer": agent.infer,
    }


# -- Backward-compatible module-level constants --------------------------------

DEFAULT_MODEL = CATALOG.default_model
DEFAULT_TIMEOUT = CATALOG.default_timeout

AGENTS: dict[str, dict[str, Any]] = {
    name: _build_sdk_config(a) for name, a in CATALOG.all_agents.items()
}
ROUTABLE_AGENTS: dict[str, dict[str, Any]] = {
    name: _build_sdk_config(a) for name, a in CATALOG.routable_agents.items()
}
ALL_AGENT_CONFIGS: list[dict[str, Any]] = [
    _build_sdk_config(a) for a in CATALOG.agent_configs_list
]
AGENT_MODELS: dict[str, str] = {
    name: CATALOG.get_model_for(name) for name in CATALOG.all_agents
}
AGENT_TIMEOUTS: dict[str, int] = {
    name: CATALOG.get_timeout_for(name) for name in CATALOG.all_agents
}
ALL_SKILL_DIRS: list[str] = CATALOG.skill_dirs

__all__ = [
    "AgentCatalog",
    "AgentConfig",
    "AgentSource",
    "AGENTS",
    "AGENT_MODELS",
    "AGENT_TIMEOUTS",
    "ALL_AGENT_CONFIGS",
    "ALL_SKILL_DIRS",
    "CATALOG",
    "DEFAULT_MODEL",
    "DEFAULT_TIMEOUT",
    "FileSystemAgentSource",
    "ROUTABLE_AGENTS",
    "load_agent",
]
