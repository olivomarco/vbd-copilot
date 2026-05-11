"""
Agent definitions for CSA-Copilot.

Loads agents from ``agent_defs/*.agent.md`` files via the ``agents`` package
and re-exports backward-compatible module-level constants so that
``app.py``, ``router.py``, and ``tools.py`` continue to work unchanged.

Hot-reload
----------
Call ``refresh_catalog()`` at any time to pick up changes made to agent
definition files while the process is running.  It uses only ``stat()``
calls on the hot path (no file I/O when nothing changed) and mutates the
module-level dicts/lists in-place, so callers that already did
``from agents import AGENTS`` will automatically see the updated values.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from agents.loader import AgentSource, FileSystemAgentSource, load_agent
from agents.models import AgentConfig
from agents.registry import AgentCatalog

# -- Resolve paths -------------------------------------------------------------

_PKG_DIR = Path(__file__).resolve().parent  # agents/
_APP_DIR = _PKG_DIR.parent  # project root
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
ALL_SKILL_DIRS: list[str] = CATALOG.skill_dirs


# -- Hot-reload ----------------------------------------------------------------


def refresh_catalog() -> bool:
    """Check the filesystem for changes and rebuild the catalog if needed.

    Uses only ``stat()`` syscalls on the hot path — cheap when nothing has
    changed.  When a change is detected only the modified agent files are
    re-parsed; everything else is served from the in-memory file cache.

    Module-level collections (``AGENTS``, ``ROUTABLE_AGENTS``,
    ``ALL_AGENT_CONFIGS``, ``ALL_SKILL_DIRS``) are mutated **in-place** so
    callers that imported them directly still see the updated values.

    Returns ``True`` if anything changed, ``False`` otherwise.
    """
    new_agents = _source.load_all()  # hits cache if nothing changed on disk
    changed = CATALOG.refresh(new_agents)
    if changed:
        AGENTS.clear()
        AGENTS.update({n: _build_sdk_config(a) for n, a in CATALOG.all_agents.items()})
        ROUTABLE_AGENTS.clear()
        ROUTABLE_AGENTS.update(
            {n: _build_sdk_config(a) for n, a in CATALOG.routable_agents.items()}
        )
        ALL_AGENT_CONFIGS[:] = [
            _build_sdk_config(a) for a in CATALOG.agent_configs_list
        ]
        ALL_SKILL_DIRS[:] = CATALOG.skill_dirs
    return changed


__all__ = [
    "AgentCatalog",
    "AgentConfig",
    "AgentSource",
    "AGENTS",
    "ALL_AGENT_CONFIGS",
    "ALL_SKILL_DIRS",
    "CATALOG",
    "DEFAULT_MODEL",
    "DEFAULT_TIMEOUT",
    "FileSystemAgentSource",
    "ROUTABLE_AGENTS",
    "load_agent",
    "refresh_catalog",
]
