# Challenge 08: Copilot Coding Agent: Autonomous Pull Request (Capstone)

**Difficulty:** Expert (L400) | **Estimated Time:** 70 minutes

## Introduction

Every challenge so far has kept a developer in the loop for every edit. Inline suggestions, Chat, Agent Mode in VS Code - all of them put you at the keyboard, steering. This capstone asks a different question: what happens when you step back and let GitHub Copilot open a pull request on its own?

FinCore Bank's security team has escalated a high-priority finding. The `POST /transfers` endpoint has two gaps that would fail a PCI-DSS audit: there is no rate limiting (an attacker could script rapid transfers and drain an account before the fraud system catches it), and there is no idempotency key validation (a network retry on a slow connection could submit the same transfer twice, causing a double charge). The team wants to fix both issues - but for this task, you will write a GitHub Issue and let the Copilot Coding Agent implement it.

For a banking team, that choice has a concrete upside that goes beyond convenience. The Copilot Coding Agent runs in a GitHub Actions ephemeral environment where every file it reads, every command it runs, and every test result it produces is committed to history in the pull request session log. That is the same kind of change-management audit trail that a compliance team asks for when they want to know what touched production code and when. You get that automatically, without writing a deployment runbook.

This is also the first time the team has delegated implementation to an AI agent entirely. By the end of this challenge, you will know when that is a good trade-off and when it is not.

## Description

This challenge has four parts. Work through them in order - the agent cannot start until the repository and issue are ready.

### Part A - Prepare the repository (10 minutes)

The Copilot Coding Agent needs three things to do useful work: a repository it can push to, Copilot Business or Enterprise enabled on the organization, and an `AGENTS.md` that tells it how to build and test the project.

Confirm the following before moving on:

- The FinCore Bank repository has been pushed to GitHub.com
- `.github/copilot-instructions.md` exists (created in earlier challenges)
- `AGENTS.md` exists at the repository root and contains the exact commands to install dependencies, run the test suite, and run the linter
- The organization has Copilot Business or Enterprise enabled

Check the repository settings at Settings -> Copilot -> Policies. There is a toggle that must be on before the agent can open pull requests: "Allow Copilot to submit pull requests." If you do not see that setting or cannot change it, read the first hint before proceeding.

### Part B - Write the GitHub Issue (15 minutes)

Create a new GitHub Issue. The title and body of this issue are the agent's only briefing. It has never seen your codebase, it does not know what your team discussed last week, and it will not ask clarifying questions before starting. Write the issue as if you were handing it to a contractor on their first day.

The issue must cover the following requirements for the `POST /transfers` endpoint in `app/api/routers/transfers.py`:

1. Rate limiting: maximum 5 requests per minute per `account_id`. Use the `slowapi` library or a custom middleware approach. Requests that exceed the limit must return HTTP 429 with a clear error message.
2. Idempotency key validation: the `X-Idempotency-Key` header is required on every transfer request. If the same key is received within 24 hours, return the cached response instead of processing the transfer again. Use a Redis cache if available; fall back to an in-memory TTL cache for development.
3. Amount validation: transfer amount must be a positive `Decimal` and must not exceed $100,000 per single transfer.
4. Logging: all validation failures must log the `account_id`, `failure_reason`, and timestamp at INFO level. Do not log transfer amounts or account numbers - reference the custom instructions in `.github/copilot-instructions.md` for the PCI-DSS sensitive field rules.
5. Tests: at least 3 new tests covering rate limit exceeded, idempotency key replay, and amount over limit.

Include references to existing patterns in the codebase (for example, the validation approach in `app/api/routers/accounts.py`) so the agent has a concrete model to follow. Add an explicit "Out of scope" section so the agent does not modify unrelated endpoints.

A well-written issue is the single biggest factor in whether the agent produces useful output. Spend the full 15 minutes on it.

### Part C - Invoke the agent and track the session (30 minutes)

With the issue saved, invoke the Copilot Coding Agent using one of the following:

- Assign the issue to `@copilot` using the Assignees panel on the GitHub.com issue page
- Comment `@copilot implement this` on the issue

The agent session starts within a few minutes. A link to the session appears on the issue page once the agent picks it up. Open that session view and watch what the agent does.

The session view shows each step in sequence: which files the agent read, which edits it made, which test commands it ran, whether tests passed or failed, and what it did when they failed. Each logical step is a commit on the `copilot/issue-N` branch, so the full history is auditable after the fact.

While the agent is running, discuss with your teammates:

- Did the agent read `AGENTS.md` before anything else?
- Did it read `.github/copilot-instructions.md`?
- Which files did it read before writing any code?
- Did any test fail on the first run? How did the agent handle it?
- How long did the install phase take versus the implementation phase?

The agent opens a pull request when all checks pass. If the agent session fails without opening a PR, read the second and fourth hints before re-invoking.

### Part D - Review and iterate on the PR (15 minutes)

Treat the agent's pull request the same way you would treat a pull request from a junior developer. Read the diff carefully. Ask:

- Does the rate limiting apply per `account_id` as specified, or did the agent default to a per-IP limit?
- Are the tests meaningful, or do they only test the happy path?
- Does any log line accidentally include a transfer amount or account number?
- Is the idempotency cache TTL hardcoded, or is it configurable?
- What happens if a client sends a malformed `X-Idempotency-Key` value - an empty string, a very long string, a value with special characters?

Leave at least two review comments on specific lines in the diff. One should request a substantive code change - for example, "The idempotency TTL is hardcoded to 86400 seconds. Move this to an environment variable with a documented default." One should request a test improvement - for example, adding a test case for a malformed idempotency key.

Watch whether the agent picks up your comments and addresses them in a new commit on the same branch. The agent monitors the PR for new review comments and will respond without you re-invoking it.

Once the agent has addressed your comments, compare the original PR diff against the updated one. Note which changes came from your review feedback and which were the agent's own choices.

## Success Criteria

- [ ] A GitHub Issue exists with a clear title, detailed description of the security requirements, and numbered acceptance criteria
- [ ] The Copilot Coding Agent was invoked and opened a pull request on a `copilot/issue-N` branch
- [ ] The PR session log has been examined and you can describe at least 3 distinct steps the agent took (file reads, test runs, lint passes, or fixes)
- [ ] The PR diff includes rate limiting on `POST /transfers`
- [ ] The PR diff includes `X-Idempotency-Key` header validation
- [ ] At least 2 review comments were left on the PR and the agent addressed them in a follow-up commit
- [ ] You can explain the difference between the Copilot Coding Agent (GitHub.com) and Agent Mode (VS Code) in terms of where each runs, how output is produced, and what audit trail each leaves

## Tips

<details>
<summary>Hint 1: @copilot does not appear in the Assignees panel</summary>

If `@copilot` does not show up when you search the Assignees panel, the Copilot Coding Agent has not been enabled for the organization. A GitHub organization admin must go to Organization Settings -> Copilot -> Access and turn on "Allow Copilot to submit pull requests." Without that setting, the coding agent cannot run.

If you are at a hackathon and cannot change organization settings, there is a fallback path: open VS Code, start a Copilot Chat in Agent Mode, and ask Copilot to "create a pull request implementing the changes described in issue #N." Agent Mode in VS Code will make the edits locally and you can push and open the PR manually. This path skips the autonomous agent session on GitHub.com, but you can still complete the review and iteration steps in Part D. Note in your success criteria discussion what is different about this path - the audit trail argument does not apply in the same way.

</details>

<details>
<summary>Hint 2: The agent opened a PR but tests are failing in CI</summary>

A failing CI check does not mean the agent is done. Add a comment on the PR with the text `@copilot The test test_rate_limit_exceeded is failing. Review the CI log output and fix the failing test.` (replace the test name with whichever test is failing). The agent will read the CI log, identify the failure, and commit a fix on the same branch.

If the agent keeps failing on the same test across multiple iterations, the issue is likely that the test fixture or the dependency is missing from the test environment. Check whether `slowapi` or the idempotency cache library is listed in `requirements.txt`. If not, add it and push the change directly - then re-invoke the agent.

</details>

<details>
<summary>Hint 3: How to write an issue the agent can act on</summary>

A useful structure for a Coding Agent issue has five sections:

1. Background - what the problem is and why it matters (one short paragraph)
2. Location - exact file paths where changes are needed (`app/api/routers/transfers.py`, `tests/unit/test_transfers.py`)
3. Requirements - numbered list, each item specific enough to test (not "add security" but "return HTTP 429 when more than 5 requests per minute are received for the same account_id")
4. Constraints - which libraries to use, which existing patterns to follow, which environment variables to respect
5. Out of scope - what the agent must not change (other endpoints, the database schema, authentication middleware)

An issue that says "please fix our security problems" gives the agent nothing to work with. The agent reads the issue text the same way a build script reads a config file - the more precise the input, the more predictable the output.

</details>

<details>
<summary>Hint 4: The agent is failing before it writes any code</summary>

The Copilot Coding Agent reads `AGENTS.md` before anything else in the repository. If the agent keeps failing at the install or test step, the commands in `AGENTS.md` are likely wrong for the project layout. Common problems:

- The test command is `pytest` but the project needs `pytest tests/unit/ -v`
- The install command does not install dev dependencies (`pip install -e ".[dev]"` is different from `pip install -e .`)
- `AGENTS.md` refers to a virtual environment activation step that does not apply in the GitHub Actions environment

Update `AGENTS.md` with the exact commands that work in a clean environment (you can verify this locally by creating a new virtualenv and running the commands from scratch), commit and push, then add a comment on the issue to re-invoke the agent.

</details>

## Learning Resources

- [About the Copilot Coding Agent](https://docs.github.com/en/copilot/concepts/agents/coding-agent/about-coding-agent)
- [Create a pull request with the Copilot Coding Agent](https://docs.github.com/en/copilot/how-tos/use-copilot-agents/coding-agent/create-a-pr)
- [Track Copilot agent sessions](https://docs.github.com/en/copilot/how-tos/use-copilot-agents/coding-agent/track-copilot-sessions)
