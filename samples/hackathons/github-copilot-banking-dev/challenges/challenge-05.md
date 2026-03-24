# Challenge 05: Custom Instructions for Banking Standards

**Difficulty:** Medium | **Estimated Time:** 45 minutes | **Level:** L300

---

## Introduction

After finishing the Decimal fixes and exception work in earlier challenges, the FinCore Bank tech lead ran a short retrospective. The pattern was clear: every developer working with Copilot was hitting the same walls. Float for money. Logging account numbers. `raise Exception("something went wrong")`. Not because anyone was careless - Copilot simply had no idea what FinCore's standards were, so it made reasonable-but-wrong choices for a generic Python project.

The fix is not to keep correcting Copilot after the fact. The fix is to write the rules down once in a place Copilot will always read them.

This challenge walks you through building out that instruction layer: a repo-wide `copilot-instructions.md` that captures FinCore's non-negotiable coding standards, path-specific instruction files that add tighter rules for routers and tests, and an `AGENTS.md` that tells autonomous agents how to build and test the project. By the end, the same prompt that previously produced `float` and `raise Exception` will produce `Decimal` and `raise InsufficientFundsError` - without you saying a word about it.

---

## Description

### Part A - Create and verify copilot-instructions.md (20 minutes)

The repo already has a `.github/` directory. Create `.github/copilot-instructions.md` - exactly that path, no subdirectory, at the repository root.

Write instructions that give Copilot the context it is missing. Your file should cover at minimum:

- **Project identity:** Python 3.11, FastAPI, REST API serving banking operations. The app runs with uvicorn; tests run with pytest.
- **Directory layout:** what lives in `app/services/`, `app/api/routers/`, `app/models/`, `tests/unit/`, and `tests/integration/` - a brief sentence each so Copilot generates files in the right place.
- **Monetary types:** Python's `Decimal` from the `decimal` module for every monetary value. Never `float`. Never `int` used as a money surrogate without explicit conversion.
- **Sensitive field logging:** never log the value of any field named `password`, `pin`, `cvv`, `card_number`, `account_number`, `routing_number`, `token`, or `secret`. Log that the field was present, not its content.
- **Exception handling:** raise from the `app.exceptions` hierarchy. `BankingError`, `InsufficientFundsError`, `AccountNotFoundError` are already defined there. Never raise bare `Exception` or `ValueError` for domain conditions.
- **Testing:** use `pytest`, `pytest-asyncio`, and `pytest-mock`. All assertions on monetary values use exact `Decimal` comparison, not `assertAlmostEqual`.

Once the file is saved, run a before/after comparison. The cleanest way to do this: rename the file to `copilot-instructions.md.bak`, open Chat, and ask:

> "Create a savings account service with an `apply_interest` method that takes an annual rate."

Note what types and exceptions appear in the response. Rename the file back, open a new Chat window, ask the same question. Compare the two responses - specifically what type is used for `balance` and `rate`, and what gets raised on an invalid rate.

Verify the instructions are applied: after sending any Chat message with the file in place, expand the References panel at the top of the Chat response. The `copilot-instructions.md` entry should appear there. If it does not appear, the file is not being read - see the hints.

One thing to confirm before moving on: test the security guardrail specifically. Ask Chat to "add debug logging that prints all request parameters." With your instructions in place, Copilot should either refuse the specific fields or mask them. If it logs `account_number` in plain text, your sensitive field rule needs to be more explicit.

### Part B - Path-specific instructions (15 minutes)

Repo-wide instructions handle the universal rules. But routers have security requirements that do not apply to model files, and test files have naming conventions that would be noise in production code. Path-specific instruction files let you layer additional rules on top.

Create `.github/instructions/security.instructions.md`. This file needs YAML frontmatter at the very top that tells Copilot which files it applies to - the router layer in this case. Add rules specific to the API surface:

- All endpoints require JWT authentication via the shared dependency, unless explicitly listed in an exempt public routes list
- All amount fields must be validated as positive values before processing
- Account number fields require IBAN format validation

Create `.github/instructions/tests.instructions.md` with an `applyTo` that targets the test tree. Add:

- Test function naming follows the pattern `test_<method>_<scenario>_<expected>` - for example, `test_apply_interest_negative_rate_raises_banking_error`
- Every service method must have at least one negative test case (invalid input, boundary condition, or expected exception)
- Monetary comparisons use exact `Decimal` values, never floats or `assertAlmostEqual`

Now test that layering works. Open one of the router files in the editor and ask Chat to "add an endpoint that transfers funds between two accounts." Expand the References panel - you should see two entries: the repo-wide `copilot-instructions.md` and the `security.instructions.md` file. Both apply simultaneously, so the generated endpoint should have JWT auth AND use Decimal AND raise from `app.exceptions`.

Open a test file and ask for new tests for the savings account service you sketched in Part A. The References panel should show `copilot-instructions.md` and `tests.instructions.md`.

### Part C - Create AGENTS.md (10 minutes)

`AGENTS.md` is a different kind of file from `copilot-instructions.md`. The instructions file tells Copilot how to write code for this project. `AGENTS.md` tells an autonomous agent how to operate the project - how to set up the environment, run the linter, execute the test suite, and interpret results.

Create `AGENTS.md` at the repo root (not inside `.github/`). Include:

- **Environment setup:** Python 3.11 required, create and activate a virtual environment, install with `pip install -r requirements.txt` to get all dependencies
- **Lint:** `ruff check .` - any lint error is a blocker before committing
- **Type checking:** `mypy app/ --strict` - note that SQLAlchemy models need the `sqlalchemy-stubs` plugin configured in `mypy.ini`
- **Unit tests:** `pytest tests/unit/ -v` with the expected pattern for test IDs
- **Integration tests:** `pytest tests/integration/ -v` - note these require a running PostgreSQL instance, so they should not run in a basic CI check without the service

This file will matter in challenge 08 when a Copilot Coding Agent takes on a task autonomously. The agent reads `AGENTS.md` to understand the project before writing a single line of code. Getting this right now saves time later.

---

## Success Criteria

- [ ] `.github/copilot-instructions.md` exists and contains at least 6 distinct rules covering project identity, monetary types, sensitive field logging, exception hierarchy, and test tooling
- [ ] A before/after comparison shows measurably different Chat responses - specifically, the "with instructions" response uses `Decimal` and raises a named domain exception
- [ ] The References panel on a Chat response confirms `copilot-instructions.md` is being applied (it appears as a reference entry)
- [ ] `.github/instructions/security.instructions.md` exists with an `applyTo` frontmatter pattern targeting router files, and contains at least the JWT and IBAN validation rules
- [ ] `.github/instructions/tests.instructions.md` exists with an `applyTo` frontmatter pattern targeting the test tree, and contains the naming convention and Decimal comparison rules
- [ ] Opening a router file and asking Chat for a new endpoint shows BOTH the repo-wide and security instructions in the References panel
- [ ] `AGENTS.md` exists at the repo root with environment setup, lint, type check, and test commands
- [ ] You can explain why custom instructions do NOT improve inline ghost-text completions (only Chat and agent modes are affected)

---

## Tips

<details>
<summary>Hint 1 - Instructions file not appearing in References panel</summary>

Check these things in order. First, the file must be at exactly `.github/copilot-instructions.md` - not `.github/instructions/copilot-instructions.md`, not `copilot-instructions.md` at the repo root. Second, the file must be saved - unsaved changes do not apply. Third, try opening a new Chat window rather than continuing an existing conversation; instructions are injected at the start of a new session. If you are on an older VS Code with the Copilot extension, check that you are on a version that supports repository custom instructions (released mid-2024). The References panel is the small expandable section at the top of a Chat response, labeled something like "2 references" - click it to expand and see the list.

</details>

<details>
<summary>Hint 2 - Making the before/after comparison meaningful</summary>

For the comparison to be worth anything, you need to test with a prompt that would produce wrong output without instructions. A good test prompt is one where a generic Python developer would reach for float naturally: "Create a `LoanCalculator` class with methods for monthly payment and total interest, given principal and annual rate." Without instructions, expect `float` everywhere. With instructions, expect `Decimal` and the `decimal` import.

When renaming the file for the "before" test, also open a brand-new Chat window - do not reuse a session where the file was previously loaded. Then for the "after" test, rename it back and open another new Chat window. Using two separate chat sessions removes any chance that the previous context is bleeding through.

</details>

<details>
<summary>Hint 3 - Path-specific file frontmatter not working</summary>

The frontmatter block must be the very first thing in the file - no blank lines before it, no title heading before it. It looks like this:

```
---
applyTo: "app/api/**/*.py"
---
```

The value is a glob pattern relative to the repo root. If you are not sure whether your glob matches, test with `"**/*.py"` first, which matches every Python file, confirm the file appears in References, then narrow it to the specific path. For test files the pattern `"tests/**/*.py"` is straightforward. The path-specific file must live under `.github/instructions/` and the filename must end in `.instructions.md` - both conditions are required for VS Code to pick it up.

</details>

<details>
<summary>Hint 4 - Writing rules that actually change Copilot's output</summary>

The official guidance is clear about what works and what does not. Rules that work are specific factual statements: "Use Python's `Decimal` type from the `decimal` module for all monetary fields. Never use `float`." Rules that tend not to work are vague or directive: "Always use best practices for financial applications." Vague instructions get interpreted generously by Copilot and often have no measurable effect.

Avoid referencing external documents ("follow the style guide at docs/style.md") - Copilot cannot read those files from your instructions file. Avoid character-count constraints ("keep responses under 500 words") - those do not work. Keep each rule to one or two sentences, be specific about the type name, module path, or pattern you want. If a rule is not changing behavior, rewrite it to be more concrete.

</details>

---

## Learning Resources

- [Adding repository custom instructions for GitHub Copilot](https://docs.github.com/en/copilot/customizing-copilot/adding-repository-custom-instructions-for-github-copilot)
- [Copilot response customization concepts](https://docs.github.com/en/copilot/concepts/prompting/response-customization)
- [Copilot customization in VS Code](https://code.visualstudio.com/docs/copilot/copilot-customization)

---

## Advanced Challenge

Your `copilot-instructions.md` currently applies to the whole repo. Some rules only make sense in production code - for example, the sensitive field logging rule should never be relaxed in `app/`, but in `tests/` it is acceptable to use stub values like `"test-token-123"` in fixtures.

Add a `.github/instructions/test-fixtures.instructions.md` that explicitly scopes the relaxed rule to test fixtures only, while the stricter production rule remains in the repo-wide file. Then test the conflict: open a production service file and ask for a method that handles auth tokens - it should apply the strict rule. Open a test fixture file and ask for a fixture that creates a test user with a token - it should accept stub test values. Document in a comment at the top of each instructions file which rules it overrides and why, so future developers understand the intentional layering.
