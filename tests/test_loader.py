"""Tests for agents/loader.py - agent definition loading."""

import pytest

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
tools:
  - str_replace_editor
  - bash
---
You are a test agent. Follow these instructions carefully.
"""
    path = tmp_path / "test-agent.agent.md"
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
    path = tmp_path / "minimal-agent.agent.md"
    path.write_text(content)
    return path


class TestLoadAgent:
    def test_load_full_agent(self, agent_md):
        agent = load_agent(agent_md)
        assert agent.name == "test-agent"
        assert agent.display_name == "Test Agent"
        assert agent.description == "A test agent for unit tests"
        assert agent.infer is True
        assert "str_replace_editor" in agent.tools
        assert "bash" in agent.tools
        assert "test agent" in agent.prompt.lower()

    def test_load_minimal_agent(self, agent_md_minimal):
        agent = load_agent(agent_md_minimal)
        assert agent.name == "minimal-agent"
        assert agent.infer is False
        assert agent.tools == []

    def test_load_agent_bad_format(self, tmp_path):
        """Agent file without proper frontmatter should raise."""
        bad = tmp_path / "bad.agent.md"
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
            (tmp_path / f"{name}.agent.md").write_text(content)
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
        """Agent source should find .agent.md files in subdirectories."""
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
        (subdir / "nested-agent.agent.md").write_text(content)
        source = FileSystemAgentSource(tmp_path)
        agents = source.load_all()
        assert len(agents) == 1
        assert agents[0].name == "nested-agent"


# ---------------------------------------------------------------------------
# Cache behaviour
# ---------------------------------------------------------------------------


def _write_agent(path, name):
    path.write_text(
        f"---\nname: {name}\ndisplay_name: {name.title()}\ndescription: desc\n---\nPrompt.\n"
    )


def _advance_mtime(path) -> None:
    """Bump a file or directory's mtime by 1 s so it is definitely different
    from a previously cached value — needed in tests that run faster than the
    filesystem clock's granularity."""
    import os

    st = os.stat(path)
    future = st.st_mtime + 1.0
    os.utime(path, (future, future))


class TestFileSystemAgentSourceCache:
    def test_second_call_returns_cache(self, tmp_path):
        """Repeated load_all() with no changes must not re-parse any file."""
        _write_agent(tmp_path / "a.agent.md", "a")
        source = FileSystemAgentSource(tmp_path)

        first = source.load_all()
        second = source.load_all()

        assert [a.name for a in first] == [a.name for a in second]
        # The second call must reuse the cached AgentConfig objects (same id)
        assert first[0] is second[0]

    def test_is_stale_false_when_unchanged(self, tmp_path):
        _write_agent(tmp_path / "a.agent.md", "a")
        source = FileSystemAgentSource(tmp_path)
        source.load_all()
        assert source.is_stale() is False

    def test_detects_file_modification(self, tmp_path):
        p = tmp_path / "a.agent.md"
        _write_agent(p, "a")
        source = FileSystemAgentSource(tmp_path)
        source.load_all()

        # Overwrite and explicitly advance mtime so detection is guaranteed
        # (tests can run faster than filesystem clock granularity)
        _write_agent(p, "a-modified")
        _advance_mtime(p)

        assert source.is_stale() is True
        agents = source.load_all()
        assert len(agents) == 1

    def test_detects_new_file_in_existing_dir(self, tmp_path):
        _write_agent(tmp_path / "a.agent.md", "a")
        source = FileSystemAgentSource(tmp_path)
        source.load_all()
        assert source.is_stale() is False

        # Adding a new file changes the directory mtime
        _write_agent(tmp_path / "b.agent.md", "b")
        _advance_mtime(tmp_path)  # ensure dir mtime differs from cached value

        assert source.is_stale() is True

        agents = source.load_all()
        assert {ag.name for ag in agents} == {"a", "b"}

    def test_detects_new_subdirectory(self, tmp_path):
        _write_agent(tmp_path / "a.agent.md", "a")
        source = FileSystemAgentSource(tmp_path)
        source.load_all()

        # New subdirectory with a new agent file
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        _write_agent(subdir / "c.agent.md", "c")
        _advance_mtime(tmp_path)  # parent dir mtime changes when subdir is added

        assert source.is_stale() is True
        agents = source.load_all()
        assert {ag.name for ag in agents} == {"a", "c"}

    def test_detects_file_removal(self, tmp_path):
        p = tmp_path / "a.agent.md"
        _write_agent(p, "a")
        source = FileSystemAgentSource(tmp_path)
        source.load_all()

        p.unlink()
        _advance_mtime(tmp_path)  # dir mtime changes on deletion; ensure it's seen
        assert source.is_stale() is True
        agents = source.load_all()
        assert agents == []

    def test_unchanged_file_reuses_cached_object(self, tmp_path):
        """When only one of two files changes, the unchanged file must not
        be re-parsed (its AgentConfig object must be identical)."""
        _write_agent(tmp_path / "a.agent.md", "a")
        _write_agent(tmp_path / "b.agent.md", "b")
        source = FileSystemAgentSource(tmp_path)
        first = source.load_all()
        a_before = next(ag for ag in first if ag.name == "a")

        # Modify only "b"
        p_b = tmp_path / "b.agent.md"
        _write_agent(p_b, "b")
        p_b.touch()

        second = source.load_all()
        a_after = next(ag for ag in second if ag.name == "a")
        assert a_before is a_after  # same object — not re-parsed


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
