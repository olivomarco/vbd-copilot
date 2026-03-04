# VBD-Copilot - Copilot Instructions

VBD-Copilot is built on the [GitHub Copilot SDK](https://github.com/github/copilot-sdk). It generates PowerPoint (.pptx) presentations and demo guides for Microsoft Cloud Solution Architects.

## Agents

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

## Output Structure

- `outputs/slides/` - final `.pptx` presentations and `generate_*.py` generator scripts
- `outputs/slides/.fragments/` - intermediate code fragments per section
- `outputs/demos/` - demo guide `.md` + companion scripts
- `plans/` - intermediate plan files
- `pptx_utils.py` - shared Python utilities for PPTX generation (do NOT duplicate; do NOT redefine its functions)

## Content Levels

- **L100** - Executive overview, no code
- **L200** - Architecture diagrams, high-level concepts
- **L300** - Deep dive, code samples
- **L400** - Expert, internals, advanced patterns

## Rules

1. Research only from **official sources**: Microsoft Learn, docs.github.com, github.blog, devblogs.microsoft.com
2. Slide generation uses **python-pptx** via the **pptx-generator skill** and the shared `pptx_utils.py` module
3. Speaker notes = full presenter transcripts, never summaries
4. **No emoji** - use Unicode text symbols instead
5. **No invented URLs** - every link must be real and verified
6. **No em-dashes** - use hyphens
7. **No indenting** in `.py` fragments - the conductor indents during assembly
