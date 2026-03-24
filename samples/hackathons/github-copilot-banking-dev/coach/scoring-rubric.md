# Scoring Rubric - GitHub Copilot for Developers (FinCore Bank)

## How to Use This Rubric

Coaches use this rubric during the event to check in on teams and during the final wrap-up to assign a day assessment. It is not meant to be punitive. Use it to identify where a team is strong and where to focus coaching attention.

Each challenge has three tiers: Complete, Partial, Not Started. Stretch indicators mark work beyond the base requirements.

At the end of the day, four overall dimensions are scored independently. These give a more meaningful picture than a single total score.

---

## Per-Challenge Rubric

---

### Challenge 00 - Environment Setup and First Contact

| Tier | Criteria |
|---|---|
| Complete | Copilot status bar icon shows active (no slash, no spinner). VS Code setting `chat.checkpoints.enabled` is true. Participant triggered and accepted at least one inline suggestion. Starter app runs with `uvicorn app.main:app --reload` and returns a 200 on `/health`. |
| Partial | Copilot is authenticated but one of: checkpoints not enabled, app does not start cleanly, no inline suggestion attempted. |
| Not Started | Copilot extension not installed or not authenticated. |

**Verification command:** `curl -s http://localhost:8000/health` returns `{"status": "ok"}` or equivalent.

**Stretch:** Participant explored the FinCore codebase using @workspace and can describe the three main modules (models, services, main) without reading the README.

---

### Challenge 01 - Ghost Text Mastery: Inline Suggestions

| Tier | Criteria |
|---|---|
| Complete | Participant can demonstrate: Alt+] cycling to a second or third suggestion on a non-trivial function. Ctrl+Right to accept one word of a multi-word completion. A comment written above a function that produces a materially better first suggestion than without the comment. |
| Partial | Participant uses Tab correctly but has not demonstrated cycling or partial accepts. |
| Not Started | Participant did not attempt the challenge or is still using only mouse-click acceptance. |

**Verification:** Ask the participant to open `app/services/account_service.py`, position the cursor below a comment they wrote, and cycle through three suggestions using Alt+]. Watch for the keystroke.

**L300 differentiator:** An L200 participant uses Tab on obvious completions. An L300 participant strategically primes context (imports, types, comments) before starting a function and uses partial accepts to steer the completion rather than accepting and deleting.

**Stretch:** Participant can explain why two suggestions for the same function location are different from each other (different context, different temperature, stochastic generation).

---

### Challenge 02 - Copilot Chat: Context and Participants

| Tier | Criteria |
|---|---|
| Complete | Participant used @workspace to answer a cross-file question (not answerable from a single file). Used #selection to explain a specific code block. Used @terminal or #terminalLastCommand to diagnose a runtime error. Can explain the difference between Ask mode and Agent mode. |
| Partial | Participant used Chat and at least one participant (@workspace or #file) but missed the terminal integration or cannot articulate the Ask vs Agent distinction. |
| Not Started | Participant only used inline suggestions and did not open Chat. |

**Verification:** Ask "Where is the transfer limit defined and which files reference it?" If they reach for @workspace first, that is Complete-tier behavior.

**L300 differentiator:** L200 participants use Chat as a search engine (plain questions). L300 participants use Chat as a scoped reasoning tool - they attach the right context and ask precise questions about specific code paths.

**Stretch:** Participant tried /explain on the legacy bare-except handler and asked a follow-up question to understand the historical context or risks, treating Copilot as a code reviewer rather than just a generator.

---

### Challenge 03 - Test-Driven Development with Copilot

| Tier | Criteria |
|---|---|
| Complete | Participant wrote a failing test first (test exists in git before the implementation). Used Copilot to generate the implementation to make it pass. Used /tests on an existing function and reviewed whether the generated assertions are meaningful. Used /fixTestFailure or a Chat prompt to fix a real test failure. `pytest` passes with at least three new tests added. |
| Partial | Participant wrote tests but did not follow test-first order (implementation came before the test). Tests pass but the assertions are trivial (e.g., asserts that a function returns something rather than asserting correct values). |
| Not Started | No new tests written. |

**Verification command:** `pytest tests/ -v --tb=short` - all tests pass, at least three new test functions appear in the output.

**L300 differentiator:** L200 participants use /tests to generate a test suite after writing code. L300 participants write the assertion first (what the correct result should be), let Copilot generate the test boilerplate, and scrutinize generated assertions for false greens before accepting.

**Stretch:** Participant wrote a test for the float precision bug that fails before the fix and passes after, demonstrating that tests can document bugs.

---

### Challenge 04 - Debugging and Code Quality

| Tier | Criteria |
|---|---|
| Complete | Participant used #terminalLastCommand to bring an error into a Chat prompt without manual copy-paste. Used /fix with a selection that covers the root cause function (not just the error line). Removed at least one bare-except clause and replaced it with a specific exception type and meaningful error handling. |
| Partial | Participant fixed errors but did all context transfer manually (copy-pasted stack traces). Or removed bare-except but replaced with `except Exception: pass` (swapping one bad pattern for another). |
| Not Started | No debugging or code quality work attempted. |

**Verification:** Ask the participant to show you a bare-except in the git diff and explain what exception they replaced it with and why.

**L300 differentiator:** L200 participants use /fix on the error message. L300 participants use /fix on the function that produced the error and read the suggested fix critically before applying - they look for whether Copilot fixed the cause or just suppressed the symptom.

**Stretch:** Participant used /explain on a legacy function to produce a comment block documenting what the function does and what its edge cases are, then committed that as a documentation improvement.

---

### Challenge 05 - Custom Instructions for Banking Standards

| Tier | Criteria |
|---|---|
| Complete | `.github/copilot-instructions.md` exists at the exact path. File contains at least three specific, verifiable rules appropriate for a banking codebase (not vague guidelines). Participant verified that at least one rule is followed in a Chat response (asked Copilot to write a function and the output complied with the rule). Participant can explain that inline completions are not affected by the instructions file. |
| Partial | Instructions file exists and has rules, but participant cannot demonstrate that the rules are applied, or the rules are too vague to be verifiable (e.g., "write clean code"). |
| Not Started | No instructions file created. |

**Verification:** Check `.github/copilot-instructions.md` exists. Ask the participant to prompt Copilot Chat to write a function that handles money and verify the output uses Decimal, not float.

**L300 differentiator:** L200 participants write generic best-practice rules. L300 participants write rules that encode their organization's specific standards: naming conventions, required imports, mandatory fields in audit records, approved libraries vs. banned ones.

**Stretch:** Participant created a path-specific `.instructions.md` in a subdirectory (e.g., `tests/.instructions.md`) with rules specific to test writing conventions, and verified it applies only to files in that directory.

---

### Challenge 06 - Copilot Edits: Multi-File Refactoring

| Tier | Criteria |
|---|---|
| Complete | Participant used Plan Mode before Agent Mode and can describe what the plan said. Refactoring touches at least two files. Chat checkpoints were used to recover from or inspect a specific agent action (participant can point to the checkpoint in the UI). Per-file Discard was used at least once to reject an out-of-scope change. `pytest` passes after the refactoring is complete. |
| Partial | Participant completed the refactoring using Agent Mode but skipped Plan Mode, did not use checkpoints, or did not encounter and handle an out-of-scope change. |
| Not Started | Refactoring was done manually or not attempted. |

**Verification:** `git diff --stat HEAD~1` shows changes across at least two files. Ask the participant what the plan said before execution.

**L300 differentiator:** L200 participants run an agent prompt and accept the output. L300 participants treat the agent like a junior developer: review the plan, approve it, watch the execution, and use checkpoints and per-file Discard to maintain control of what enters the codebase.

**Stretch:** Participant ran two different Plan Mode prompts for the same task, compared the resulting plans, and chose the better one before switching to Agent Mode.

---

### Challenge 07 - End-to-End Feature Development

| Tier | Criteria |
|---|---|
| Complete | A new working endpoint exists in the API. Business logic is in the service layer (not inline in the route handler). Tests for the new feature exist in `tests/` and pass. The feature uses Decimal for monetary values (consistent with Challenge 05 rules). Participant used at least one steering follow-up message to correct an agent output rather than starting over. |
| Partial | Feature exists and runs but: tests are missing or failing, monetary values use float, or business logic is in the wrong layer. |
| Not Started | No new feature attempted. |

**Verification command:** `pytest tests/ -v --tb=short` passes. `curl` the new endpoint with a valid payload and confirm correct behavior.

**L300 differentiator:** L200 participants accept the agent's first complete output. L300 participants review the agent output against their acceptance criteria and write targeted steering messages to close specific gaps rather than re-running the full prompt.

**Stretch:** Participant added OpenAPI documentation (docstring + response model) to the new endpoint and verified it appears in the Swagger UI at `/docs`.

---

### Challenge 08 - Copilot Coding Agent: Autonomous PR (Capstone)

| Tier | Criteria |
|---|---|
| Complete | A GitHub Issue was written with: a background section, specific requirements, constraints referencing AGENTS.md or copilot-instructions.md, and a definition of done. The Issue was assigned to @copilot (or Agent Mode fallback was used with equivalent rigor). A PR was opened with agent-generated code. Participant reviewed the PR diff and posted at least one specific review comment on a code line. The agent responded to the comment with an update. Final PR passes CI or participant can explain what remains to fix. |
| Partial | PR exists and was agent-generated, but Issue was vague (one or two sentences), no line-level review comments were posted, or participant merged without reviewing the diff. |
| Not Started | No Issue created or PR opened. |

**Verification:** GitHub PR URL exists. PR has at least one review comment thread. Ask the participant to show you the Issue and walk you through why they wrote it the way they did.

**L300 differentiator:** L200 participants generate the PR and merge it. L300 participants treat the agent PR like any other code review: they read every changed line, run the tests, and post precise comments to drive the agent toward production-quality code.

**L400 differentiator (this challenge is the L400 capstone):** L400 participants structure the Issue as a complete technical specification, reference AGENTS.md for the task context, and iterate on the PR through multiple rounds of targeted comments - treating the Coding Agent as a capable but junior contributor who needs clear, specific feedback to do excellent work.

**Stretch:** Participant created an AGENTS.md file in the repo root with task-specific context before assigning the Issue, and the PR output reflects that context (e.g., follows the audit logging format specified in AGENTS.md).

---

## Overall Day Assessment Dimensions

Score each dimension independently at the end of the day. Use the three-tier labels.

### Dimension 1 - Prompt Quality

Measures how well participants construct inputs to Copilot across all interaction modes.

| Tier | Description |
|---|---|
| Strong | Prompts are specific, include relevant context, and include constraints or acceptance criteria. Participants iterate with targeted follow-ups rather than re-prompting from scratch. |
| Developing | Prompts are functional but generic. Participant relies on Copilot to infer context that should be stated explicitly. |
| Beginning | Prompts are one-liners or natural language questions without code context. Participant treats Copilot as a search engine. |

### Dimension 2 - Context Management

Measures how well participants use participants, references, and workspace scoping.

| Tier | Description |
|---|---|
| Strong | Participant consistently attaches the right context for the task: @workspace for cross-file questions, #selection for targeted analysis, #terminalLastCommand for error debugging. Rarely asks a question that Copilot cannot answer due to missing context. |
| Developing | Participant uses some context participants but defaults to unscoped prompts for some tasks, leading to less relevant responses. |
| Beginning | Participant uses Chat without attaching context. All questions are unscoped. |

### Dimension 3 - Workflow Integration

Measures how well participants have embedded Copilot into their development process rather than treating it as an external tool.

| Tier | Description |
|---|---|
| Strong | Participant reaches for Copilot as the first tool for test generation, debugging, and documentation. Uses inline suggestions, Chat, and Agent Mode for appropriate tasks without being directed to. Checkpoints and Plan Mode are used proactively. |
| Developing | Participant uses Copilot when directed but reverts to manual approaches for some tasks where Copilot would be faster. |
| Beginning | Participant uses Copilot only for the explicit task described in the challenge, not as a general development tool. |

### Dimension 4 - Domain Application

Measures whether participants apply Copilot to banking-specific problems correctly rather than using generic patterns.

| Tier | Description |
|---|---|
| Strong | Custom instructions encode real banking standards. Monetary values use Decimal throughout. Audit logging is present on mutations. Generated code is reviewed against financial correctness requirements, not just functional correctness. |
| Developing | Participant fixed the float issue when directed but does not apply banking constraints proactively to new code. |
| Beginning | Generated code still uses float for money or lacks audit logging in mutation endpoints. |

---

## Suggested Award Tiers

These are optional recognition categories for events that end with a group showcase.

| Award | Criteria |
|---|---|
| All Challenges Complete | Completed all nine challenges at Complete tier |
| Capstone Excellence | Challenge 08 at L400 differentiator standard with a well-structured Issue and multiple review iterations |
| Best Custom Instructions | Challenge 05 Stretch plus instructions that other participants would actually use on a real banking codebase |
| Steering Champion | Demonstrated the most effective follow-up messaging to correct and improve agent output in Challenges 06 and 07 |
| First PR Merged | First team to have a Coding Agent PR reviewed and merged in Challenge 08 |
