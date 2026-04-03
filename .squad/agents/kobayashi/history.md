# Project Context

- **Owner:** Marco Olivo
- **Project:** CSA-Copilot — AI-powered engagement platform for Cloud Solution Architects. Built on GitHub Copilot SDK with 4 workflows: presentations, demos, AI projects, hackathons. 27 agent definitions orchestrated by conductor agents.
- **Stack:** Python 3.11+, GitHub Copilot SDK (0.1.29), FastAPI, Rich, python-pptx, Electron/TypeScript frontend, YAML agent definitions
- **Key files:** app.py (CLI entry), commands/ (CLI subcommands), ui.py (Rich terminal UI), router.py (agent routing), tools.py (custom tools)
- **CLI layer:** app.py is the main entry point. commands/sessions.py and commands/usage.py are existing subcommands. Rich library handles terminal formatting. prompt-toolkit for interactive input.
- **Dependencies:** pyproject.toml — github-copilot-sdk, mcp, pydantic, fastapi, rich, python-pptx, prompt-toolkit
- **Created:** 2026-04-03

## Learnings

<!-- Append new learnings below. Each entry is something lasting about the project. -->
