# Project Context

- **Owner:** Marco Olivo
- **Project:** CSA-Copilot — AI-powered engagement platform for Cloud Solution Architects. 27 agent definitions across 4 workflows, each with conductor→subagent orchestration patterns.
- **Stack:** Agent defs in agent_defs/ as Markdown + YAML frontmatter, loaded by agents/ package. 28 skills in skills/.
- **Workflows:** Slides (slide-conductor → research, builder, QA subagents), Demos (demo-conductor → research, builder, editor, reviewer), AI Projects (brainstorming → solution-architect → implementor, with 4-reviewer gate), Hackathons (hackathon-conductor → research, challenge-builder, coach-builder, reviewer)
- **Key skills:** pptx-generator (pptx_utils.py shared contract, pptx_qa_checks.py), demo-generator (demo_qa_checks.py), architecture-design (architecture_qa_checks.py), code-project (infra/pipeline/docs QA), hackathon-generator (hackathon_qa_checks.py), content-humanizer (humanizer_scorer.py)
- **Created:** 2026-04-02

## Learnings

<!-- Append new learnings below. Each entry is something lasting about the project. -->

## Deep Agent & Skill Study — 2026-04-04

### Agent Inventory (27 agents)

**Conductors (routable, infer=true):**
- slide-conductor — Orchestrates: pre-research → clarify (ask_user) → deep research (parallel shards) → plan → build (parallel sections) → QA → deliver. Output: .pptx
- demo-conductor — Orchestrates: research → plan → build → validate → review → deliver. Output: demo-guide.md + scripts
- hackathon-conductor — Orchestrates: research → plan challenges → build setup → build challenges → coach materials → QA → deliver. Output: WTH-style event package
- ai-brainstorming — Single agent: discover → research → ideate 10+ ideas → prioritize → roadmap
- ai-solution-architect — Orchestrates: discover → plan → build 5 docs → QA → review → deliver
- ai-implementor — Orchestrates: plan 8 work packages → build (parallel) → 4 specialist reviews → deliver

**Subagents (infer=false) — Slides workflow:**
- research-subagent, slide-builder-subagent, pptx-qa-subagent, slide-editor-subagent

**Subagents — Demos workflow:**
- demo-research-subagent, demo-builder-subagent, demo-editor-subagent, demo-reviewer-subagent

**Subagents — Hackathons workflow:**
- hackathon-research-subagent, hackathon-challenge-builder, hackathon-coach-builder, hackathon-reviewer

**Subagents — AI Projects workflow:**
- ai-researcher, ai-architect-builder, ai-architect-reviewer, ai-infra-builder, ai-code-builder, ai-test-builder, ai-docs-builder, ai-security-reviewer, ai-pipeline-reviewer, ai-docs-reviewer, ai-integration-reviewer

### Conductor Patterns

1. **Parallel dispatch:** Conductors use task tool to spawn up to 5 subagents per batch
2. **Phase gates:** User approval MANDATORY between major phases (ask_user tool)
3. **Fragment assembly:** Subagents write unindented fragments; conductors assemble with proper indentation
4. **QA validation:** QA subagent runs programmatic checks (pptx_qa_checks.py etc.) + visual/content review
5. **Content levels:** L100 (executive, no code) → L200 (architecture) → L300 (deep dive, code) → L400 (expert, internals)
6. **Conductor non-invocation:** NEVER wrap a conductor in another task call

### Skill Inventory (28 skills)

**Content generation skills (7):**
- pptx-generator — SKILL.md + pptx_utils.py (shared contract, DO NOT REFACTOR) + pptx_qa_checks.py + office/soffice.py + references/
- demo-generator — SKILL.md + demo_qa_checks.py
- architecture-design — SKILL.md + architecture_qa_checks.py
- code-project — SKILL.md + infra_qa_checks.py + pipeline_qa_checks.py + docs_qa_checks.py
- hackathon-generator — SKILL.md + hackathon_qa_checks.py
- content-humanizer — SKILL.md + humanizer_scorer.py + references/ (banned AI vocabulary, natural voice patterns)
- microsoft-foundry — SKILL.md (Foundry agent deployment)

**Azure service skills (21):**
- azure-ai, azure-aigateway, azure-cloud-migrate, azure-compliance, azure-compute, azure-cost-optimization, azure-deploy, azure-diagnostics, azure-hosted-copilot-sdk, azure-kusto, azure-messaging, azure-prepare, azure-quotas, azure-rbac, azure-resource-lookup, azure-resource-visualizer, azure-storage, azure-upgrade, azure-validate, appinsights-instrumentation, entra-app-registration
- From microsoft/azure-skills repo — DO NOT modify directly

### QA Check Scripts (8 scripts)

All return: {"status", "summary", "issues"} JSON. Exit codes: 0=CLEAN, 1=ISSUES_FOUND, 2=ERROR.
- pptx_qa_checks.py — slide count, shape overflow (0.15" tolerance), font sanity (8-48pt), placeholder detection, overlaps
- demo_qa_checks.py — guide existence, demo count (## Demo N), placeholder/emoji/em-dash/URL validation
- architecture_qa_checks.py — 7 required .md files + architecture-diagram.drawio (XML validation)
- hackathon_qa_checks.py — challenge-NN.md numbering (00-based), coach/*, .devcontainer/*, solution-revealing detection
- infra_qa_checks.py — Bicep hardcoded secrets, security patterns (KeyVault/ManagedIdentity), network checks
- pipeline_qa_checks.py — GitHub Actions + ADO workflows, deploy/validate scripts, secret detection
- docs_qa_checks.py — README required sections, env vars, hardcoded secrets
- humanizer_scorer.py — AI vocabulary detection, natural voice scoring

### Key Prompt Patterns

- Tool allowlists vary by agent type: conductors get [task, ask_user], builders get [str_replace_editor, bash, web_fetch]
- Skills referenced in YAML frontmatter: `skills: [pptx-generator, demo-generator]`
- Content humanizer: banned vocabulary list (leverage, delve, robust, encompass...), natural voice rubric
- Fragment convention: .fragments/ files are raw (unindented), conductors handle assembly
- Azure mandate: all infrastructure proposed must use Azure services

### Conventions & Landmines

- Agent defs: YAML frontmatter with exactly 3-dash delimiters, NO extra `---` in prompt body
- Agent defs organized in subfolders (slides/, demos/, ai-project/, hackathons/) — loader scans recursively
- Challenge files use challenge-{NN} numbering (00-based) — do not renumber or skip
- Plan files in plans/ are intermediate — do not treat as ground truth
- Content level specified in user prompt determines scope/depth of all outputs
