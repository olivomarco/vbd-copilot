# VBD-Copilot - Copilot Instructions

## Agents

Agents are defined as Markdown files with YAML frontmatter in `agent_defs/`. Each file specifies the agent's name, tools, skills, model, timeout, and whether it is routable (`infer: true`). The `agents/` package discovers and loads them at startup.

| Agent | Role |
|-------|------|
| `slide-conductor` | Orchestrates full slide lifecycle via subagents |
| `demo-conductor` | Orchestrates full demo lifecycle via subagents |
| `research-subagent` | Fetches official docs (MS Learn, GitHub, devblogs) |
| `demo-research-subagent` | Researches existing demos and sample repos for a topic |
| `slide-builder-subagent` | Writes python-pptx code fragments using pptx_utils |
| `pptx-qa-subagent` | Layout + content QA on generated .pptx; returns CLEAN or ISSUES_FOUND |
| `demo-builder-subagent` | Builds demo guide + companion scripts |
| `demo-reviewer-subagent` | Reviews demos; returns APPROVED or NEEDS_REVISION |
| `demo-editor-subagent` | Edits demos based on reviewer feedback |

To add a new agent, create `agent_defs/<agent-name>.md` with the standard frontmatter and restart the CLI.

## Output Structure

- `outputs/slides/` - final `.pptx` presentations and `generate_*.py` generator scripts
- `outputs/slides/.fragments/` - intermediate code fragments per section
- `outputs/demos/` - demo guide `.md` + companion scripts
- `plans/` - intermediate plan files

## Skills

Skills live in `skills/<skill-name>/` directories. Each skill has a `SKILL.md` and may contain utility scripts used by agents. Agents reference skills by directory name in their `skills:` frontmatter field.

| Skill | Contents |
|-------|----------|
| `pptx-generator` | `SKILL.md`, `pptx_utils.py`, `pptx_qa_checks.py`, `office/soffice.py`, `references/` |
| `demo-generator` | `SKILL.md`, `demo_qa_checks.py` |

- Do NOT duplicate or redefine functions from `skills/pptx-generator/pptx_utils.py` - it is a shared contract across all slide-related subagents
- Per-skill utilities belong inside their skill directory, not at the project root

## Content Levels

- **L100** - Executive overview, no code
- **L200** - Architecture diagrams, high-level concepts
- **L300** - Deep dive, code samples
- **L400** - Expert, internals, advanced patterns

## Rules

1. Research only from **official sources**: Microsoft Learn, docs.github.com, github.blog, devblogs.microsoft.com
2. Slide generation uses **python-pptx** via the **pptx-generator skill** and `skills/pptx-generator/pptx_utils.py`
3. Speaker notes = full presenter transcripts, never summaries
4. **No emoji** - use Unicode text symbols instead
5. **No invented URLs** - every link must be real and verified
6. **No em-dashes** - use hyphens
7. **No indenting** in `.py` fragments - the conductor indents during assembly

## Landmines

- Use `uv` instead of `pip` for all Python dependency operations
- Do not refactor `skills/pptx-generator/pptx_utils.py` - it is a shared contract across all subagents
- Fragment files in `outputs/slides/.fragments/` are unindented by design - do not auto-format them
- Plan files in `plans/` are intermediate and may be incomplete - do not treat them as ground truth
- Agent definitions in `agent_defs/` use YAML frontmatter - do not add extra `---` delimiters in the prompt body
