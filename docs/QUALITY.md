# Quality and Trust

The whole point of this tool is producing content you can put in front of a customer without embarrassment. Several mechanisms work together to make that happen.

## Research from official sources only

Every research subagent is restricted to MS Learn, docs.github.com, github.blog, devblogs.microsoft.com, and techcommunity.microsoft.com. No random blog posts, no Stack Overflow guesses, no made-up URLs. Every link in the output is real and was fetched during generation.

## Human approval stops

Every conductor pauses after the research phase and presents a plan. You approve, modify, or reject it before any content gets built. You also review the final output before it's considered done.

## Automated QA checks

Each workflow runs programmatic validation before delivery:

- **PPTX QA** - shape overflow detection, placeholder text scanning, speaker notes presence, font size validation, slide count verification
- **Architecture QA** - document completeness, Azure mandate compliance, placeholder-free content, diagram accuracy
- **Infrastructure QA** - Bicep syntax, module decomposition, Key Vault usage, managed identity for secrets, RBAC configuration
- **Pipeline QA** - YAML syntax, job dependencies, secrets via environment variables, deploy script safety
- **Documentation QA** - section completeness, path accuracy, command correctness, environment variable documentation
- **Hackathon QA** - sequential challenge numbering, required sections per challenge, matching solutions, coach materials, dev container validity, cross-reference consistency

## Content humanization

Generated text goes through AI-tell detection that flags filler words, hedging phrases, uniform sentence structure, and a blacklist of overused AI vocabulary. A humanity scoring system rates the output and triggers rewrites if the score is too low. The goal is content that reads like a person wrote it, not a chatbot.

## 4-reviewer gate for AI projects

The implementor cannot deliver until four independent specialist reviewers (code, infra, pipeline, docs) each return APPROVED. If any one of them flags an issue, targeted fixes are applied and that reviewer runs again. No shortcuts.

## 80% test coverage

Code projects must pass a `pytest --cov` threshold of 80% before the code reviewer will approve.
