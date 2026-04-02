# Project Context

- **Owner:** Marco Olivo
- **Project:** CSA-Copilot — AI-powered engagement platform for Cloud Solution Architects. Built on GitHub Copilot SDK with 4 workflows: presentations, demos, AI projects, hackathons. 27 agent definitions orchestrated by conductor agents.
- **Stack:** Python 3.11+, GitHub Copilot SDK (0.1.29), FastAPI, Rich, python-pptx, Electron/TypeScript frontend, YAML agent definitions
- **Key files:** app.py (CLI entry), router.py (agent routing), tools.py (custom tools), store.py (SQLite event store), collector.py (event collector), server.py (FastAPI desktop server), ui.py (Rich terminal UI)
- **Agent defs:** agent_defs/{slides,demos,ai-project,hackathons}/ — Markdown with YAML frontmatter, loaded by agents/ package
- **Skills:** 28 skills in skills/ — pptx-generator, demo-generator, hackathon-generator, architecture-design, code-project, content-humanizer, 22 Azure skills
- **Tests:** 13 test files in tests/, 80% coverage gate (pytest --cov)
- **Created:** 2026-04-02

## Learnings

<!-- Append new learnings below. Each entry is something lasting about the project. -->
