"""Tests for agents/registry.py - AgentCatalog."""

import pytest
from pathlib import Path

from agents.models import AgentConfig
from agents.registry import AgentCatalog, DEFAULT_MODEL, DEFAULT_TIMEOUT


def _make_agent(name, infer=False, model="", timeout=0, skills=None):
    return AgentConfig(
        name=name,
        display_name=name.title(),
        description=f"Desc for {name}",
        prompt=f"Prompt for {name}",
        infer=infer,
        model=model,
        timeout=timeout,
        skills=skills or [],
    )


@pytest.fixture
def catalog(tmp_path):
    agents = [
        _make_agent("slide-conductor", infer=True, model="gpt-4o", timeout=900, skills=["pptx-generator"]),
        _make_agent("demo-conductor", infer=True, model="claude-sonnet-4.6", timeout=1200, skills=["demo-generator"]),
        _make_agent("research-subagent", infer=False, skills=["pptx-generator"]),
    ]
    return AgentCatalog(agents, tmp_path / "skills")


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

    def test_skill_dirs(self, catalog, tmp_path):
        dirs = catalog.skill_dirs
        # Should have unique skill names: pptx-generator, demo-generator
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

    def test_get_model_for_with_override(self, catalog):
        assert catalog.get_model_for("slide-conductor") == "gpt-4o"

    def test_get_model_for_without_override(self, catalog):
        assert catalog.get_model_for("research-subagent") == DEFAULT_MODEL

    def test_get_model_for_unknown_agent(self, catalog):
        assert catalog.get_model_for("doesnt-exist") == DEFAULT_MODEL

    def test_get_timeout_for_with_override(self, catalog):
        assert catalog.get_timeout_for("slide-conductor") == 900

    def test_get_timeout_for_without_override(self, catalog):
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
