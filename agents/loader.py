"""Agent loading - parse agent definitions from the filesystem.

The primary source is ``*.md`` files with YAML frontmatter in a
directory.  The ``AgentSource`` protocol allows plugging in alternative
backends (database, HTTP, etc.) in the future.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

import yaml

from agents.models import AgentConfig


@runtime_checkable
class AgentSource(Protocol):
    """Protocol for anything that can supply agent definitions."""

    def load_all(self) -> list[AgentConfig]:
        """Return every available agent definition."""
        ...


class FileSystemAgentSource:
    """Load agents from ``*.md`` files in a directory.

    File format::

        ---
        name: agent-id
        display_name: Human Label
        description: Short description for the router
        infer: true
        model: claude-sonnet-4.6
        timeout: 900
        tools: [str_replace_editor, task]
        skills: [pptx-generator]
        ---
        Markdown system prompt / instructions
    """

    def __init__(self, defs_dir: Path) -> None:
        self._defs_dir = defs_dir

    def load_all(self) -> list[AgentConfig]:
        agents: list[AgentConfig] = []
        for md_file in sorted(self._defs_dir.glob("*.md")):
            agents.append(load_agent(md_file))
        return agents


def load_agent(path: Path) -> AgentConfig:
    """Parse a single ``*.md`` agent definition file."""
    text = path.read_text()
    _, fm_block, prompt = text.split("---", 2)
    raw = yaml.safe_load(fm_block)
    prompt = prompt.strip()

    return AgentConfig(
        name=raw["name"],
        display_name=raw["display_name"],
        description=raw["description"],
        prompt=prompt,
        tools=raw.get("tools", []),
        infer=raw.get("infer", False),
        model=raw.get("model", ""),
        timeout=raw.get("timeout", 0),
        skills=raw.get("skills", []),
    )
