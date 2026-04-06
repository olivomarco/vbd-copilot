# Work Routing

How to decide who handles what.

## Routing Table

| Work Type | Route To | Examples |
|-----------|----------|----------|
| Python backend | McManus | app.py, router.py, tools.py, store.py, server.py, SDK integration, FastAPI endpoints |
| Agent loading system | McManus | agents/ package, loader.py, models.py, registry.py |
| CLI commands & terminal UX | McManus | commands/ directory, CLI argument parsing, Rich terminal output, shell integration, SDK CLI interfaces |
| Frontend / Electron / Web UI | Redfoot | frontend/ directory, Electron shell, React components, Vite config, browser-side logic, web styling, IPC |
| Agent definitions | Fenster | agent_defs/*.agent.md, YAML frontmatter, prompt design, workflow orchestration |
| Skills & QA scripts | Fenster | skills/<name>/SKILL.md, QA check scripts, content humanizer |
| Architecture decisions | Keaton | System design, refactoring proposals, routing logic, scope trade-offs |
| Code review | Keaton | Review PRs, check quality, enforce conventions |
| Testing | Hockney | Write tests, coverage enforcement, edge cases, pytest fixtures |
| QA validation | Hockney | Run QA check scripts, verify test thresholds |
| Product ownership & backlog | Kujan | Feature prioritization, acceptance criteria, user value, backlog grooming, requirement analysis |
| Scope & priorities | Keaton | What to build next, trade-offs, decisions |
| Session logging | Scribe | Automatic — never needs routing |
| Work monitoring | Ralph | Backlog tracking, issue triage, keep-alive |

## Issue Routing

| Label | Action | Who |
|-------|--------|-----|
| `squad` | Triage: analyze issue, assign `squad:{member}` label | Lead |
| `squad:{name}` | Pick up issue and complete the work | Named member |

### How Issue Assignment Works

1. When a GitHub issue gets the `squad` label, the **Lead** triages it — analyzing content, assigning the right `squad:{member}` label, and commenting with triage notes.
2. When a `squad:{member}` label is applied, that member picks up the issue in their next session.
3. Members can reassign by removing their label and adding another member's label.
4. The `squad` label is the "inbox" — untriaged issues waiting for Lead review.

## Rules

1. **Eager by default** — spawn all agents who could usefully start work, including anticipatory downstream work.
2. **Scribe always runs** after substantial work, always as `mode: "background"`. Never blocks.
3. **Quick facts → coordinator answers directly.** Don't spawn an agent for "what port does the server run on?"
4. **When two agents could handle it**, pick the one whose domain is the primary concern.
5. **"Team, ..." → fan-out.** Spawn all relevant agents in parallel as `mode: "background"`.
6. **Anticipate downstream work.** If a feature is being built, spawn the tester to write test cases from requirements simultaneously.
7. **Issue-labeled work** — when a `squad:{member}` label is applied to an issue, route to that member. The Lead handles all `squad` (base label) triage.
