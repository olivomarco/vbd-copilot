# CSA-Copilot - Copilot Instructions

## Agents

Agents are defined as Markdown files with YAML frontmatter in `agent_defs/` subdirectories. Each file specifies the agent's name, tools, skills, model, timeout, and whether it is routable (`infer: true`). The `agents/` package discovers and loads them recursively at startup.

## Output Structure

- `outputs/slides/` - final `.pptx` presentations and `generate_*.py` generator scripts
- `outputs/slides/.fragments/` - intermediate code fragments per section
- `outputs/demos/` - demo guide `.md` + companion scripts
- `outputs/hackathons/<event-slug>/` - hackathon packages (one subfolder per event):
  - `challenges/` - challenge-00.md through challenge-{N}.md
  - `coach/` - facilitation-guide.md, scoring-rubric.md
  - `resources/` - reference-architecture.md, starter files
  - `.devcontainer/` - Codespaces-ready environment
  - `README.md` - event landing page
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
| `hackathon-generator` | `SKILL.md`, `hackathon_qa_checks.py` |
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

1. **No indenting** in `.py` fragments - the conductor indents during assembly
2. All AI project artifacts go under `outputs/ai-projects/<project-slug>/` - never in the repo root
3. All hackathon artifacts go under `outputs/hackathons/<event-slug>/` - never in the repo root
4. **Test coverage must be at least 80%** - run `pytest --cov` and verify the `fail_under = 80` threshold passes before merging
4. When you write text, always ensure that is sounds human through the skill that you have for that

## Landmines

- Use `uv` instead of `pip` for all Python dependency operations
- Do not refactor `skills/pptx-generator/pptx_utils.py` - it is a shared contract across all subagents
- Fragment files in `outputs/slides/.fragments/` are unindented by design - do not auto-format them
- Plan files in `plans/` are intermediate and may be incomplete - do not treat them as ground truth
- Agent definitions in `agent_defs/` use YAML frontmatter - do not add extra `---` delimiters in the prompt body
- Agent definitions are organized in subfolders (`slides/`, `demos/`, `ai-project/`, `hackathons/`) - the loader scans recursively
- Challenge files in `outputs/hackathons/` use `challenge-{NN}` numbering - do not renumber or skip
- Azure service skills in `skills/azure-*` are from the `microsoft/azure-skills` repo - do not modify them directly
