# Project Context

- **Owner:** Marco Olivo
- **Project:** CSA-Copilot — AI-powered engagement platform for Cloud Solution Architects. 27 agent definitions across 4 workflows, each with conductor→subagent orchestration patterns.
- **Stack:** Agent defs in agent_defs/ as Markdown + YAML frontmatter, loaded by agents/ package. 28 skills in skills/.
- **Workflows:** Slides (slide-conductor → research, builder, QA subagents), Demos (demo-conductor → research, builder, editor, reviewer), AI Projects (brainstorming → solution-architect → implementor, with 4-reviewer gate), Hackathons (hackathon-conductor → research, challenge-builder, coach-builder, reviewer)
- **Key skills:** pptx-generator (pptx_utils.py shared contract, pptx_qa_checks.py), demo-generator (demo_qa_checks.py), architecture-design (architecture_qa_checks.py), code-project (infra/pipeline/docs QA), hackathon-generator (hackathon_qa_checks.py), content-humanizer (humanizer_scorer.py)
- **Created:** 2026-04-02

## Learnings

<!-- Append new learnings below. Each entry is something lasting about the project. -->
