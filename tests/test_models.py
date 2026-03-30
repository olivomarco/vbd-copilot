"""Tests for agents/models.py - AgentConfig dataclass."""

from agents.models import AgentConfig


class TestAgentConfig:

    def test_defaults(self):
        agent = AgentConfig(
            name="test-agent",
            display_name="Test Agent",
            description="A test agent",
            prompt="You are a test agent.",
        )
        assert agent.name == "test-agent"
        assert agent.tools == []
        assert agent.infer is False

    def test_full_config(self):
        agent = AgentConfig(
            name="my-agent",
            display_name="My Agent",
            description="Desc",
            prompt="Prompt",
            tools=["tool1", "tool2"],
            infer=True,
        )
        assert agent.infer is True
        assert len(agent.tools) == 2
