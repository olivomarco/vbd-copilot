"""Tests for agents/registry.py - AgentCatalog."""

import pytest

from agents.models import AgentConfig
from agents.registry import AgentCatalog, DEFAULT_MODEL, DEFAULT_TIMEOUT


def _make_agent(name, infer=False):
    return AgentConfig(
        name=name,
        display_name=name.title(),
        description=f"Desc for {name}",
        prompt=f"Prompt for {name}",
        infer=infer,
    )


@pytest.fixture
def skill_dirs(tmp_path):
    """Create two skill subdirectories on disk."""
    for skill in ["pptx-generator", "demo-generator"]:
        (tmp_path / "skills" / skill).mkdir(parents=True)
    return tmp_path / "skills"


@pytest.fixture
def catalog(tmp_path, skill_dirs):
    agents = [
        _make_agent("slide-conductor", infer=True),
        _make_agent("demo-conductor", infer=True),
        _make_agent("research-subagent", infer=False),
    ]
    return AgentCatalog(agents, skill_dirs)


class TestCatalogProperties:
    def test_all_agents(self, catalog):
        assert len(catalog.all_agents) == 3
        assert "slide-conductor" in catalog.all_agents
        assert "research-subagent" in catalog.all_agents

    def test_routable_agents(self, catalog):
        routable = catalog.routable_agents
        assert len(routable) == 2
        assert "slide-conductor" in routable
        assert "demo-conductor" in routable
        assert "research-subagent" not in routable

    def test_agent_configs_list(self, catalog):
        configs = catalog.agent_configs_list
        assert len(configs) == 3
        assert all(isinstance(c, AgentConfig) for c in configs)

    def test_default_model(self, catalog):
        assert catalog.default_model == DEFAULT_MODEL

    def test_default_timeout(self, catalog):
        assert catalog.default_timeout == DEFAULT_TIMEOUT

    def test_skill_dirs(self, catalog, skill_dirs):
        dirs = catalog.skill_dirs
        # Should enumerate all subdirs from the skills root
        assert len(dirs) == 2
        assert any("pptx-generator" in d for d in dirs)
        assert any("demo-generator" in d for d in dirs)


class TestCatalogLookups:
    def test_get_agent(self, catalog):
        agent = catalog.get_agent("slide-conductor")
        assert agent is not None
        assert agent.name == "slide-conductor"

    def test_get_agent_not_found(self, catalog):
        assert catalog.get_agent("nonexistent") is None

    def test_get_model_for_any_agent(self, catalog):
        assert catalog.get_model_for("slide-conductor") == DEFAULT_MODEL
        assert catalog.get_model_for("research-subagent") == DEFAULT_MODEL

    def test_get_model_for_unknown_agent(self, catalog):
        assert catalog.get_model_for("doesnt-exist") == DEFAULT_MODEL

    def test_get_timeout_for_any_agent(self, catalog):
        assert catalog.get_timeout_for("slide-conductor") == DEFAULT_TIMEOUT
        assert catalog.get_timeout_for("research-subagent") == DEFAULT_TIMEOUT

    def test_get_timeout_for_unknown_agent(self, catalog):
        assert catalog.get_timeout_for("doesnt-exist") == DEFAULT_TIMEOUT


class TestCatalogCustomDefaults:
    def test_custom_default_model(self, tmp_path):
        agents = [_make_agent("a")]
        cat = AgentCatalog(agents, tmp_path, default_model="custom-model")
        assert cat.default_model == "custom-model"
        assert cat.get_model_for("a") == "custom-model"

    def test_custom_default_timeout(self, tmp_path):
        agents = [_make_agent("a")]
        cat = AgentCatalog(agents, tmp_path, default_timeout=999)
        assert cat.default_timeout == 999
        assert cat.get_timeout_for("a") == 999


class TestCatalogEmpty:
    def test_empty_catalog(self, tmp_path):
        cat = AgentCatalog([], tmp_path)
        assert cat.all_agents == {}
        assert cat.routable_agents == {}
        assert cat.agent_configs_list == []
        assert cat.skill_dirs == []


# ---------------------------------------------------------------------------
# refresh()
# ---------------------------------------------------------------------------


class TestCatalogRefresh:
    def test_refresh_no_change_returns_false(self, catalog, skill_dirs):
        """refresh() with identical agents must return False."""
        same_agents = list(catalog.agent_configs_list)
        assert catalog.refresh(same_agents) is False

    def test_refresh_added_agent_returns_true(self, catalog, skill_dirs):
        agents = list(catalog.agent_configs_list)
        agents.append(_make_agent("new-agent", infer=True))
        changed = catalog.refresh(agents)
        assert changed is True
        assert "new-agent" in catalog.all_agents
        assert "new-agent" in catalog.routable_agents

    def test_refresh_removed_agent_returns_true(self, catalog, skill_dirs):
        agents = [a for a in catalog.agent_configs_list if a.name != "slide-conductor"]
        changed = catalog.refresh(agents)
        assert changed is True
        assert "slide-conductor" not in catalog.all_agents

    def test_refresh_updates_routable_set(self, catalog, skill_dirs):
        # Make research-subagent routable by replacing it with infer=True
        agents = [
            a
            if a.name != "research-subagent"
            else _make_agent("research-subagent", infer=True)
            for a in catalog.agent_configs_list
        ]
        catalog.refresh(agents)
        assert "research-subagent" in catalog.routable_agents

    def test_refresh_picks_up_new_skill_dir(self, catalog, skill_dirs):
        """refresh() must discover a new subdirectory added to skills/."""
        (skill_dirs / "new-skill").mkdir()
        same_agents = list(catalog.agent_configs_list)
        changed = catalog.refresh(same_agents)
        assert changed is True
        assert any("new-skill" in d for d in catalog.skill_dirs)

    def test_refresh_false_when_skill_dir_unchanged(self, catalog, skill_dirs):
        same_agents = list(catalog.agent_configs_list)
        # First call records current state
        catalog.refresh(same_agents)
        # Second call with nothing changed should be False
        assert catalog.refresh(same_agents) is False
