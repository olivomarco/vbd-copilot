# VBD-Copilot - Copilot Instructions

## Agents

Agents are defined as Markdown files with YAML frontmatter in `agent_defs/` subdirectories. Each file specifies the agent's name, tools, skills, model, timeout, and whether it is routable (`infer: true`). The `agents/` package discovers and loads them recursively at startup.

Agent definitions are organized by workflow in subfolders:
- `agent_defs/slides/` - slide generation workflow
- `agent_defs/demos/` - demo generation workflow
- `agent_defs/ai-project/` - AI project lifecycle workflow

### Slide Workflow

| Agent | Role |
|-------|------|
| `slide-conductor` | Orchestrates full slide lifecycle via subagents |
| `research-subagent` | Fetches official docs (MS Learn, GitHub, devblogs) |
| `slide-builder-subagent` | Writes python-pptx code fragments using pptx_utils |
| `pptx-qa-subagent` | Layout + content QA on generated .pptx; returns CLEAN or ISSUES_FOUND |

### Demo Workflow

| Agent | Role |
|-------|------|
| `demo-conductor` | Orchestrates full demo lifecycle via subagents |
| `demo-research-subagent` | Researches existing demos and sample repos for a topic |
| `demo-builder-subagent` | Builds demo guide + companion scripts |
| `demo-reviewer-subagent` | Reviews demos; returns APPROVED or NEEDS_REVISION |
| `demo-editor-subagent` | Edits demos based on reviewer feedback |

### AI Project Workflow

| Agent | Role |
|-------|------|
| `ai-brainstorming` | Researches customer context and generates prioritized AI project ideas |
| `ai-solution-architect` | Conductor that orchestrates architecture design and mandatory review cycles |
| `ai-implementor` | Conductor that orchestrates build and 4-specialist review cycles |
| `architecture-builder-subagent` | Builds architecture documents and diagrams |
| `architecture-reviewer-subagent` | Reviews architecture outputs; returns CLEAN or ISSUES_FOUND |
| `code-builder-subagent` | Implements one work package slice (infra, app, tests, scripts) |
| `code-reviewer-subagent` | Reviews src/ and tests/ for correctness and quality |
| `infra-reviewer-subagent` | Reviews Bicep/ARM for security and Azure best practices |
| `pipeline-reviewer-subagent` | Reviews CI/CD workflows and deploy/validate scripts |
| `docs-reviewer-subagent` | Reviews README.md for completeness and accuracy |

To add a new agent, create `agent_defs/<workflow>/<agent-name>.md` with the standard frontmatter and restart the CLI.

## Output Structure

- `outputs/slides/` - final `.pptx` presentations and `generate_*.py` generator scripts
- `outputs/slides/.fragments/` - intermediate code fragments per section
- `outputs/demos/` - demo guide `.md` + companion scripts
- `outputs/ai-projects/<project-slug>/` - AI project artifacts (one subfolder per project):
  - `docs/` - architecture documents, brainstorming output
  - `infra/` - Bicep/ARM infrastructure-as-code
  - `src/` - application source code
  - `tests/` - unit and smoke tests, validate.sh
  - `scripts/` - deploy.sh and automation scripts
  - `.github/` - CI/CD workflows
  - `slides/` - project-scoped presentations
  - `demos/` - project-scoped demo guides
  - `README.md` - project entry point
- `plans/` - intermediate plan files

## Skills

Skills live in `skills/<skill-name>/` directories. Each skill has a `SKILL.md` and may contain utility scripts used by agents. Agents reference skills by directory name in their `skills:` frontmatter field.

| Skill | Contents |
|-------|----------|
| `pptx-generator` | `SKILL.md`, `pptx_utils.py`, `pptx_qa_checks.py`, `office/soffice.py`, `references/` |
| `demo-generator` | `SKILL.md`, `demo_qa_checks.py` |
| `architecture-design` | `SKILL.md`, `architecture_qa_checks.py` |
| `code-project` | `SKILL.md`, `infra_qa_checks.py`, `pipeline_qa_checks.py`, `docs_qa_checks.py` |
| `content-humanizer` | `SKILL.md`, `humanizer_scorer.py`, `references/` |
| `azure-*` | Azure service skills from microsoft/azure-skills (22 skills) |

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
8. AI project agents (`ai-brainstorming`, `ai-solution-architect`, `ai-implementor`) enforce **Azure-only** solutions - this mandate does NOT apply to slide/demo conductors
9. All AI project artifacts go under `outputs/ai-projects/<project-slug>/` - never in the repo root
10. The `ai-implementor` requires ALL 4 specialist reviewers to return APPROVED before delivery11. **Test coverage must be at least 80%** - run `pytest --cov` and verify the `fail_under = 80` threshold passes before merging
## Landmines

- Use `uv` instead of `pip` for all Python dependency operations
- Do not refactor `skills/pptx-generator/pptx_utils.py` - it is a shared contract across all subagents
- Fragment files in `outputs/slides/.fragments/` are unindented by design - do not auto-format them
- Plan files in `plans/` are intermediate and may be incomplete - do not treat them as ground truth
- Agent definitions in `agent_defs/` use YAML frontmatter - do not add extra `---` delimiters in the prompt body
- Agent definitions are organized in subfolders (`slides/`, `demos/`, `ai-project/`) - the loader scans recursively
- Azure service skills in `skills/azure-*` are from the `microsoft/azure-skills` repo - do not modify them directly
