"""Tests for agents/loader.py - agent definition loading."""

import pytest
from pathlib import Path

from agents.loader import load_agent, FileSystemAgentSource


@pytest.fixture
def agent_md(tmp_path):
    """Create a sample agent definition file."""
    content = """\
---
name: test-agent
display_name: Test Agent
description: A test agent for unit tests
infer: true
model: gpt-4o
timeout: 600
tools:
  - str_replace_editor
  - bash
skills:
  - pptx-generator
---
You are a test agent. Follow these instructions carefully.
"""
    path = tmp_path / "test-agent.md"
    path.write_text(content)
    return path


@pytest.fixture
def agent_md_minimal(tmp_path):
    """Create a minimal agent definition (only required fields)."""
    content = """\
---
name: minimal-agent
display_name: Minimal
description: Minimal agent
---
Do minimal things.
"""
    path = tmp_path / "minimal-agent.md"
    path.write_text(content)
    return path


class TestLoadAgent:

    def test_load_full_agent(self, agent_md):
        agent = load_agent(agent_md)
        assert agent.name == "test-agent"
        assert agent.display_name == "Test Agent"
        assert agent.description == "A test agent for unit tests"
        assert agent.infer is True
        assert agent.model == "gpt-4o"
        assert agent.timeout == 600
        assert "str_replace_editor" in agent.tools
        assert "bash" in agent.tools
        assert "pptx-generator" in agent.skills
        assert "test agent" in agent.prompt.lower()

    def test_load_minimal_agent(self, agent_md_minimal):
        agent = load_agent(agent_md_minimal)
        assert agent.name == "minimal-agent"
        assert agent.infer is False
        assert agent.model == ""
        assert agent.timeout == 0
        assert agent.tools == []
        assert agent.skills == []

    def test_load_agent_bad_format(self, tmp_path):
        """Agent file without proper frontmatter should raise."""
        bad = tmp_path / "bad.md"
        bad.write_text("No frontmatter here.")
        with pytest.raises(ValueError):
            load_agent(bad)


class TestFileSystemAgentSource:

    def test_load_all(self, tmp_path):
        # Create two agent files
        for name in ["agent-a", "agent-b"]:
            content = f"""\
---
name: {name}
display_name: {name.title()}
description: desc
---
Prompt for {name}.
"""
            (tmp_path / f"{name}.md").write_text(content)
        source = FileSystemAgentSource(tmp_path)
        agents = source.load_all()
        assert len(agents) == 2
        names = {a.name for a in agents}
        assert "agent-a" in names
        assert "agent-b" in names

    def test_load_all_empty(self, tmp_path):
        source = FileSystemAgentSource(tmp_path)
        agents = source.load_all()
        assert agents == []

    def test_load_all_recursive(self, tmp_path):
        """Agent source should find .md files in subdirectories."""
        subdir = tmp_path / "workflow"
        subdir.mkdir()
        content = """\
---
name: nested-agent
display_name: Nested
description: desc
---
Nested prompt.
"""
        (subdir / "nested-agent.md").write_text(content)
        source = FileSystemAgentSource(tmp_path)
        agents = source.load_all()
        assert len(agents) == 1
        assert agents[0].name == "nested-agent"


class TestHackathonAgentLoading:
    """Verify hackathon agents are discovered from agent_defs/hackathons/."""

    def test_hackathon_conductor_is_routable(self):
        """hackathon-conductor must have infer=True and be in ROUTABLE_AGENTS."""
        from agents import ROUTABLE_AGENTS
        assert "hackathon-conductor" in ROUTABLE_AGENTS

    def test_hackathon_subagents_not_routable(self):
        """Hackathon subagents must have infer=False and NOT be in ROUTABLE_AGENTS."""
        from agents import ROUTABLE_AGENTS
        subagent_names = [
            "hackathon-research-subagent",
            "hackathon-challenge-builder-subagent",
            "hackathon-coach-builder-subagent",
            "hackathon-reviewer-subagent",
        ]
        for name in subagent_names:
            assert name not in ROUTABLE_AGENTS

    def test_all_hackathon_agents_loaded(self):
        """All 5 hackathon agents must be discovered by the loader."""
        from agents import AGENTS
        expected = [
            "hackathon-conductor",
            "hackathon-research-subagent",
            "hackathon-challenge-builder-subagent",
            "hackathon-coach-builder-subagent",
            "hackathon-reviewer-subagent",
        ]
        for name in expected:
            assert name in AGENTS, f"Agent '{name}' not found in AGENTS"
