"""Agent catalog - the central registry of loaded agents.

Provides convenient accessors for agent lookups, routable agent lists,
model/timeout resolution, and skill directory collection.
"""

from __future__ import annotations

from pathlib import Path

from agents.models import AgentConfig

DEFAULT_MODEL = "claude-sonnet-4.6"
DEFAULT_TIMEOUT = 1800  # 30 min


class AgentCatalog:
    """Immutable catalog built from a list of ``AgentConfig`` objects.

    Typical usage::

        source = FileSystemAgentSource(defs_dir)
        catalog = AgentCatalog(source.load_all(), skills_dir)
    """

    def __init__(
        self,
        agents: list[AgentConfig],
        skills_dir: Path,
        default_model: str = DEFAULT_MODEL,
        default_timeout: int = DEFAULT_TIMEOUT,
    ) -> None:
        self._default_model = default_model
        self._default_timeout = default_timeout
        self._agents: dict[str, AgentConfig] = {}
        self._routable: dict[str, AgentConfig] = {}
        self._skill_dirs: list[str] = []

        all_skill_names: set[str] = set()

        for agent in agents:
            self._agents[agent.name] = agent
            if agent.infer:
                self._routable[agent.name] = agent
            all_skill_names.update(agent.skills)

        self._skill_dirs = sorted(str(skills_dir / s) for s in all_skill_names)

    # -- Lookups ---------------------------------------------------------------

    @property
    def all_agents(self) -> dict[str, AgentConfig]:
        return dict(self._agents)

    @property
    def routable_agents(self) -> dict[str, AgentConfig]:
        return dict(self._routable)

    @property
    def agent_configs_list(self) -> list[AgentConfig]:
        return list(self._agents.values())

    @property
    def skill_dirs(self) -> list[str]:
        return list(self._skill_dirs)

    @property
    def default_model(self) -> str:
        return self._default_model

    @property
    def default_timeout(self) -> int:
        return self._default_timeout

    def get_agent(self, name: str) -> AgentConfig | None:
        return self._agents.get(name)

    def get_model_for(self, agent_name: str) -> str:
        agent = self._agents.get(agent_name)
        if agent and agent.model:
            return agent.model
        return self._default_model

    def get_timeout_for(self, agent_name: str) -> int:
        agent = self._agents.get(agent_name)
        if agent and agent.timeout:
            return agent.timeout
        return self._default_timeout
