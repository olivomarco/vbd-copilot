# Facilitation Guide - GitHub Copilot for Developers (FinCore Bank)

This guide is written for coaches who are running this event for the first time. Read it end to end the night before. The most common problems are predictable and almost all of them are solvable in under five minutes if you know what to look for.

## Event Overview

**Audience:** Banking and financial services developer teams  
**Level:** L300 with a L400 capstone (Challenge 08)  
**Duration:** Full day, approximately 08:30 to 17:30  
**Format:** Individual or pair work through nine progressive challenges on a shared codebase

Participants are not here to learn Copilot basics from a slide deck. The expectation is that they leave with three things: muscle memory for the keyboard shortcuts and chat participants that save them time every day, a working understanding of how to direct Copilot at a real problem rather than a toy, and a concrete demonstration of the Coding Agent capability they can show their own teams.

## The FinCore Bank Application

The starter application is a Python FastAPI service. Participants treat it as a legacy codebase they have just inherited. It has four deliberate problems baked in:

1. Monetary values use Python `float`, which introduces rounding errors in financial calculations.
2. There is no test coverage.
3. Exception handlers use bare `except:` clauses that swallow errors silently.
4. There is no audit logging on account mutations.

Every challenge either exposes one of these problems, fixes it, or adds a feature on top of the fixed foundation. Work accumulates across the day. A participant who skips Challenge 03 will have a harder time in Challenge 06. Make sure participants understand this at the kickoff.

### Application structure

```
app/
  main.py                     - FastAPI app creation and router registration
  config.py                   - Settings (environment variables)
  exceptions.py               - Domain exception hierarchy (BankingError, AccountNotFound, InsufficientFunds)
  models/
    account.py                - Pydantic v2 Account, AccountCreate, AccountUpdate models
    transaction.py            - Pydantic v2 Transaction, TransactionCreate models
    transfer.py               - TransferRequest, TransferResponse models
  services/
    account_service.py        - AccountService: create, update, close account
    transaction_service.py    - TransactionService: create and validate transactions
    interest_service.py       - InterestService: simple and compound interest (has 3 deliberate bugs)
  api/
    routers/
      accounts.py             - FastAPI router for /accounts endpoints
      transactions.py         - FastAPI router for /transactions
      transfers.py            - FastAPI router for /transfers
      auth.py                 - JWT authentication endpoints
  utils/
    logging.py                - structlog setup
    audit.py                  - AuditLogger and @audit_event decorator (added in Challenge 06)
tests/
  conftest.py                 - pytest fixtures
  unit/
    test_account_service.py   - empty at start (filled in Challenge 03)
    test_interest_service.py  - empty at start (filled in Challenges 03 and 04)
  integration/
    test_api.py               - minimal smoke tests
.github/
  copilot-instructions.md     - added in Challenge 05
  instructions/               - path-specific instruction files (added in Challenge 05)
AGENTS.md                     - build and test commands for autonomous agents (added in Challenge 05)
```

## Key Concepts Coaches Must Reinforce

### Agent Mode (VS Code) is not the same as Copilot Coding Agent (GitHub.com)

This is the single most important distinction of the day. Participants will confuse these.

- **Agent Mode** runs inside VS Code. It edits files on your local machine. It does not create pull requests. It has access to the terminal and can run commands. Challenges 06 and 07 use Agent Mode.
- **Copilot Coding Agent** runs on GitHub.com. You assign it to an Issue. It spins up a cloud environment, writes code, pushes a branch, and opens a PR. You review the PR. Challenge 08 uses the Coding Agent.

When a participant says "I used the agent for Challenge 06 and it didn't open a PR", that is correct behavior. When a participant says "I don't see where to assign Copilot to an Issue", that is a Challenge 08 / Coding Agent question.

### Custom instructions do not affect inline completions

`copilot-instructions.md` applies to Chat and Agent Mode only. Ghost text (the gray inline suggestions) is not influenced by it. Participants often write a rule like "always use Decimal for money" in the instructions file and then expect Tab completions to follow it automatically. They do not. The rule only fires when they use a Chat prompt or Agent Mode task. Make this explicit during the Challenge 05 debrief.

### Plan Mode is read-only

In Agent Mode, participants can toggle between Plan Mode and Agent Mode. Plan Mode produces a written plan. It does not create or edit files. Participants must review the plan and then switch to Agent Mode to execute it. Some participants will wait several minutes expecting code to appear after Plan Mode produces its output. Check on them.

### Chat checkpoints must be enabled manually

`chat.checkpoints.enabled` is off by default in VS Code. Challenge 06 depends on it. Verify this is set for every participant during Challenge 00 or at the latest during Challenge 05. The setting is in VS Code Settings under "Chat > Checkpoints". If a participant gets deep into Challenge 06 without checkpoints and an agent run goes wrong, their only recovery is git.

## Pre-Event Checklist

Complete this at least one business day before the event. Do not leave license verification until the morning of.

### License verification (do this first)

- Confirm every participant has a GitHub account with an active Copilot subscription (Individual, Business, or Enterprise).
- If the event uses Copilot Business or Enterprise through an organization, confirm the org admin has enabled Copilot and that the Coding Agent is authorized for Challenge 08.
- Ask participants to open VS Code, install the GitHub Copilot extension, and confirm the Copilot icon in the status bar shows as active. Have them do this before they arrive.

### VS Code settings to verify at setup

These should be set for every participant. Challenge 00 walks through them, but coaches should know what to check:

```
github.copilot.enable: true
chat.checkpoints.enabled: true
github.copilot.chat.agent.enabled: true (may be on by default in recent versions)
```

### Network requirements

Copilot requires outbound HTTPS to `api.github.com`, `copilot-proxy.githubusercontent.com`, and `githubcopilot.com`. If participants are on a corporate network or VPN, verify these are not blocked before the event starts. A quick check: if the Copilot status bar icon shows a spinner that never resolves, it is almost always a network or auth issue.

### Python environment

Participants need:
- Python 3.11 or newer (`python --version`)
- pip or uv to install dependencies
- The starter app should run: `uvicorn app.main:app --reload` with no errors

### Challenge 08 prerequisites (Coding Agent)

Challenge 08 has additional requirements that go beyond a standard Copilot subscription:

- The GitHub organization must have Copilot Business or Enterprise.
- The Copilot Coding Agent must be enabled in org settings (Settings > Copilot > Coding agent).
- Participants must be members of the org with write access to the repository.
- Node.js 22 or newer must be installed.

If any of this is not in place by 14:00, start the fallback plan described in the Challenge 08 section below.

## Day-of Schedule and Agenda

| Time | Activity | Duration |
|---|---|---|
| 08:30 | Coach welcome and Copilot overview | 30 min |
| 09:00 | Challenge 00: Environment Setup | 25 min |
| 09:25 | Challenge 01: Inline Suggestions | 30 min |
| 09:55 | Challenge 02: Copilot Chat | 35 min |
| 10:30 | Break | 15 min |
| 10:45 | Challenge 03: TDD | 45 min |
| 11:30 | Challenge 04: Debugging | 40 min |
| 12:10 | Lunch | 50 min |
| 13:00 | Challenge 05: Custom Instructions | 45 min |
| 13:45 | Challenge 06: Multi-File Refactoring | 55 min |
| 14:40 | Break | 15 min |
| 14:55 | Challenge 07: End-to-End Feature | 55 min |
| 15:50 | Challenge 08: Copilot Coding Agent | 70 min |
| 17:00 | Debrief and wrap-up | 30 min |
| 17:30 | End | |

### Pacing notes

The schedule assumes average progress. Fast teams will finish each challenge with 5-10 minutes to spare and move to stretch tasks. Slow teams need coaching intervention, not time extensions. If a team is more than 15 minutes behind at the end of Challenge 02, check whether they are getting stuck on Copilot mechanics (authentication, indexing lag) vs. getting stuck on the tasks. Mechanical issues need a coach fix. Task difficulty issues resolve faster if you point them to a specific prompt pattern rather than explaining the concept at length.

The lunch break is a good reset point. If teams are significantly behind by 12:10, use the minimum path below.

### Minimum path (teams falling significantly behind)

If a team is at risk of not reaching Challenge 08, suggest they skip the stretch tasks in Challenges 01 and 02, treat Challenge 04 as optional review (Coach 03 and 04 address overlapping skills), and spend the time saved on Challenge 05 because custom instructions directly affect the quality of Challenges 06 and 07. Challenge 08 is the capstone - do not skip it entirely. A 40-minute abbreviated version of Challenge 08 is better than finishing Challenge 07 with ten minutes left.

## Per-Challenge Coaching Notes

---

### Challenge 00 - Environment Setup and First Contact (25 min)

**Goal:** Every participant has Copilot running, authenticated, and has seen their first inline suggestion.

**Coach talking points at kickoff:**
- Frame the FinCore Bank scenario. This is a real codebase with real problems. The code you write today stays with you.
- Copilot is a tool, not a magic box. The quality of its output is proportional to the quality of the context you give it. That is the theme of the day.
- The extension is already installed for Codespaces users. Local users: install GitHub Copilot from the VS Code extension marketplace and sign in.

**What to watch for:**
- The Copilot icon in the status bar is the first diagnostic. A slash through it means auth failed. A spinner that never resolves means network. A check mark means ready.
- Some participants will already have Copilot and will race ahead to Challenge 01. That is fine.

**Common stuck points:**
- SSO organizations require a one-time "authorize" step in the browser after signing in. Participants often miss the browser prompt. Ask them to check for a browser popup.
- `chat.checkpoints.enabled` is the most commonly forgotten setting. Do a quick show-of-hands check before you close the challenge: "Who has checkpoints enabled?" Walk to anyone who hesitates.

---

### Challenge 01 - Ghost Text Mastery: Inline Suggestions (30 min)

**Goal:** Participants move beyond Tab and discover cycling, partial accepts, and context priming.

**Coach talking points:**
- Most developers already know Tab. The gap between a Copilot beginner and an intermediate user is knowing three more keystrokes: Alt+] cycles to the next suggestion, Alt+[ cycles back, Ctrl+Right accepts a single word of the ghost text without accepting the whole line.
- Context priming: Copilot reads what is above the cursor. If you write a detailed comment and a relevant import before you start typing a function, the first suggestion is almost always better than if you start cold.

**What to watch for:**
- Participants who do not see Alt+] produce a different suggestion may have only one suggestion in the queue. This is normal for short, unambiguous completions. Tell them to try it on a more complex function body.
- On macOS, Alt is the Option key. Some keyboards label it differently. Worth mentioning at the start.

**Common stuck points:**
- Participants who are only using Tab and accepting full suggestions as-is. Interrupt them: "Have you tried cycling through alternatives?" If they say no, walk through it with them.
- Context priming feels unnatural. The task asks them to write a comment before the function. Some participants skip the comment and wonder why the suggestion is generic. Point them back to the task description.

**Unblocking hint for partial accepts:** If they cannot get Ctrl+Right to work, ask them to check VS Code keybindings. On some setups it conflicts with word navigation. The setting is `editor.action.inlineSuggest.acceptNextWord`.

---

### Challenge 02 - Copilot Chat: Context and Participants (35 min)

**Goal:** Participants use @workspace, @terminal, #file, #selection, and understand Ask vs Agent modes.

**Coach talking points:**
- Chat participants are scoping mechanisms. @workspace tells Copilot to search the whole repo before answering. #file pins a specific file. #selection sends exactly what you have highlighted. Without these, Copilot answers from its training data, not your code.
- Ask mode is read-only: it answers, explains, and suggests. Agent mode can run commands and edit files. They are different tools for different jobs. Do not use Agent mode to answer a question. Do not use Ask mode to make a change.

**What to watch for:**
- @workspace answers that reference code which does not exist in the repo. This is the hallucination tell. Ask the participant: "Does that function actually exist? Let's check." It teaches them to verify.
- Participants who skip @workspace and use /explain on a single file and get confused why Copilot does not understand a dependency defined in a different file.

**Common stuck points:**
- Weak @workspace responses early in the morning. The workspace indexing spinner (bottom status bar) needs to finish before @workspace is reliable. Tell participants to wait for it. It takes 1-3 minutes for the FinCore repo.
- @terminal not capturing the right output. @terminal reads the active terminal's recent output. If a participant has multiple terminals open, it reads the one that was most recently focused. Tell them to run the failing command, immediately switch to chat, and use @terminal before doing anything else.

**Unblocking hint for Ask vs Agent confusion:** A reliable rule of thumb: if you want to change a file, use Agent mode. If you want to understand something, use Ask mode. If you are not sure, use Ask mode first.

---

### Challenge 03 - Test-Driven Development with Copilot (45 min)

**Goal:** Participants write a failing test first, then use Copilot to make it pass. They also use /tests on existing code and /fixTestFailure.

**Coach talking points:**
- TDD with Copilot is different from TDD without it. The loop is: write a plain-language description of the behavior you want as a comment or chat prompt, have Copilot generate the test skeleton, adjust the assertion to match the exact failure case, run the test, use /fixTestFailure or a chat prompt to fix the implementation. The key is that you drive the test intent - Copilot handles the boilerplate.
- /tests is a shortcut for generating tests for existing code, not for TDD. If participants are doing TDD and they reach for /tests, they are going in the wrong direction.

**What to watch for:**
- Participants who use /tests to generate the test and then write the implementation themselves. They are doing it backwards. This is the most common mistake in this challenge.
- Participants who accept the first test Copilot generates for /tests without reading it. Some of the generated tests for the float-money code will pass because the assertion rounds the value. That is a false green. Ask them: "Does that test actually catch the float precision bug?"

**Common stuck points:**
- /fixTestFailure requires the test output to be visible in the terminal. If participants ran the test from the test explorer GUI and the output is not in a terminal, /fixTestFailure will not have enough context. Tell them to run `pytest -v` in the terminal.
- Participants who are new to pytest may spend time on test discovery config. The starter app has a `pytest.ini` that handles this. If tests are not discovered, check that they ran `pip install -r requirements.txt` first.

**Unblocking hint for the TDD loop:** If a participant is stuck, ask them to write one sentence describing what the function should do, paste that sentence as a comment above an empty test function, and then press Tab. That single priming step usually unblocks them.

---

### Challenge 04 - Debugging and Code Quality (40 min)

**Goal:** Participants use @terminal and #terminalLastCommand to give Copilot error context, use /fix to address root causes rather than symptoms, and use /explain on the legacy bare-except handlers.

**Coach talking points:**
- #terminalLastCommand is the fastest way to get Copilot looking at an error. You run a command, it fails, you open Chat and type "#terminalLastCommand /fix". No copy-pasting a stack trace. This is a habit worth building.
- /fix applied to a symptom gives you a band-aid. /fix applied to the right file with the right selection gives you a real fix. Coach participants to select the function or block that contains the root cause before invoking /fix, not just the error line.

**What to watch for:**
- Participants fixing exceptions by adding a try/except instead of fixing the logic. If you see `except Exception: pass` added to passing tests, intervene. That is exactly the bad pattern they are supposed to be finding and removing.
- /explain used on a single line instead of the full function. The results are much better when the selection includes the full context.

**Common stuck points:**
- #terminalLastCommand does not pick up output from terminals that are external to VS Code (Windows Terminal, iTerm, etc.). Participants who run their app outside VS Code will not get useful context. Tell them to run everything in the VS Code integrated terminal for this challenge.
- Participants on Windows may see different stack trace formats. The challenge tasks are written for standard Python traceback format. This is rarely a blocking issue but worth knowing.

**Unblocking hint for bare-except:** If a participant cannot find the bare-except clauses, ask them to use @workspace: "Find all bare except clauses in the services layer." This also demonstrates the @workspace search capability as a practical tool.

---

### Challenge 05 - Custom Instructions for Banking Standards (45 min)

**Goal:** Participants create `.github/copilot-instructions.md`, add at least three banking-specific rules, verify the rules apply in Chat, and understand the scope limitations.

**Coach talking points:**
- The instructions file is a way to encode your team's standards so you do not have to repeat them in every prompt. For a banking codebase, the obvious candidates are: always use Decimal for money, always add audit logging to account mutations, never use bare except, follow PEP 8. Write these once and Copilot will apply them in every Chat and Agent Mode interaction.
- This file does not affect inline completions. If participants add a rule and test it by pressing Tab, the rule will appear to have no effect. That is correct. Test rules by asking a Chat question or running an Agent Mode task.
- Path-specific instructions (`.instructions.md` files in subdirectories) are for when different parts of the codebase have different standards - for example, stricter PII handling in the customer data module.

**What to watch for:**
- The file path must be exactly `.github/copilot-instructions.md`. Any variation (`.copilot-instructions.md`, `copilot-instructions.md`, a different directory) and the file is silently ignored. Check this first if a participant says their instructions are not working.
- Participants who write vague instructions like "write good code" and then wonder why behavior has not changed. Push them toward specific, verifiable rules: "All monetary values must use Python's Decimal type from the decimal module."

**Common stuck points:**
- VS Code may not reload instructions immediately after the file is created. If rules do not seem to apply, close and reopen the Chat panel.
- AGENTS.md is a related but separate feature. It provides task-specific context to the Coding Agent (Challenge 08). Some participants will conflate the two. Instructions in `copilot-instructions.md` = persistent rules for Chat. Instructions in `AGENTS.md` = task brief for a specific agent run.

**Unblocking hint:** Have participants verify their instructions by asking Copilot Chat: "What rules are you following for this codebase?" With a well-formed instructions file, Copilot will surface the rules in its response.

---

### Challenge 06 - Copilot Edits: Multi-File Refactoring (55 min)

**Goal:** Participants use Plan Mode to generate a refactoring plan, review it, switch to Agent Mode to execute it, use chat checkpoints to recover from a bad run, and use per-file Discard to roll back out-of-scope changes.

**Coach talking points:**
- Plan Mode is research. Agent Mode is execution. Never switch directly to Agent Mode without reviewing the plan. The plan tells you exactly what the agent intends to change. If you would not approve a PR with those changes, do not execute the plan.
- Chat checkpoints are your undo button for agent runs. They snapshot the state of the working set before each agent action. If the agent does something unexpected, click the checkpoint to restore. But they only work if `chat.checkpoints.enabled` is set to true. Verify this before participants start.
- When the agent touches files that are not in scope, use per-file Discard in the Chat diff view. Do not use Discard All - that throws away the good changes too.

**What to watch for:**
- Participants who skip Plan Mode and go straight to Agent Mode. They will often end up with a mess that is hard to untangle. Interrupt them after their first agent run and ask: "Did you read the plan first?"
- Agents that pull in too many files. If the working set grows beyond what was agreed in the plan, that is a signal to stop, discard the extras, and re-prompt with a narrower scope.

**Common stuck points:**
- Chat checkpoints not available. If a participant cannot find the checkpoint icon in the Chat panel, `chat.checkpoints.enabled` is false. They need to enable it in settings and start a new chat session.
- Agent mode making circular edits (writes a change, runs a test, fails, tries to fix the same thing in a loop). This is the classic agent thrash pattern. Tell the participant to cancel the run, read the last few agent steps, and add a constraint to their next prompt: "Do not edit database.py. Only modify services.py."

**Unblocking hint for Discard All panic:** If a participant used Discard All and lost their work, check git. If they committed before starting Challenge 06 (which Challenge 05 asks them to do), `git checkout .` will restore the Challenge 05 state and they can retry.

---

### Challenge 07 - End-to-End Feature Development (55 min)

**Goal:** Participants scaffold a full feature (new endpoint, service logic, tests) using Agent Mode with follow-up steering messages, and deliver working, tested code.

**Coach talking points:**
- A good first Agent Mode prompt for a feature has four parts: what the feature does, which files to create or modify, what the acceptance criteria are, and which rules to follow (or reference the instructions file). Write this as a paragraph, not bullet points - the agent produces better plans from prose.
- Steering is not re-prompting from scratch. If the agent produces code that is 80% right but uses float instead of Decimal, the follow-up message is: "The transfer amount in services.py on line 42 uses float. Fix that to use Decimal." Target the specific issue. Do not say "try again."

**What to watch for:**
- Participants who accept agent output without running the tests. The task requires passing tests. Remind them that generated code is a starting point, not a finished product.
- Agents that ignore the custom instructions from Challenge 05 and use float for money. This is a steering opportunity: show participants how to reference the instructions explicitly in the follow-up prompt. "According to the rules in .github/copilot-instructions.md, monetary values must use Decimal. Update the new transfer endpoint to comply."

**Common stuck points:**
- The agent creating a new file for the feature instead of modifying the existing structure. This is usually because the first prompt did not specify existing file paths. Have the participant add #file references to anchor the agent to the right files.
- Feature works but tests are not in the tests/ directory. Check where the agent put them.

**Unblocking hint for steering:** If a participant is frustrated that the agent keeps making the same mistake, ask them to describe the rule in their follow-up as a constraint rather than a correction: "Do not use float anywhere in this feature" rather than "You used float, fix it." Constraints outperform corrections.

---

### Challenge 08 - Copilot Coding Agent: Autonomous PR (Capstone) (70 min)

**Goal:** Participants write a well-structured GitHub Issue, assign it to Copilot, review the resulting PR, iterate via PR comments, and merge a working change.

**Coach talking points:**
- The Coding Agent's output quality is directly proportional to the Issue quality. An Issue that says "add audit logging" will produce something. An Issue that says "add audit logging to the account transfer endpoint, log to the audit_log table with columns: timestamp, user_id, action, amount, status - see the Decimal and logging rules in AGENTS.md" will produce something much better.
- Reviewing an agent PR is the same discipline as reviewing a human PR. Read the diff. Run the tests in the PR. Post comments on specific lines. The agent picks up line comments and iterates. This is the feature that banking teams most often want to demo to their leadership.
- AGENTS.md in the repo root provides context to the Coding Agent's cloud environment. It is separate from `copilot-instructions.md`. Think of it as the README for the agent's workspace.

**What to watch for:**
- The @copilot assignee not appearing in the Issue assignee dropdown. This means the Coding Agent is not enabled at the org level. See the fallback below.
- Participants who post a vague review comment like "this is wrong" and expect the agent to know what to fix. Show them how to post a specific, actionable comment on the diff line.
- PR opened but CI is failing. The agent often produces code that needs a nudge to pass tests. A comment on the PR saying "CI is failing because of X, fix the test setup" is usually enough.

**Common stuck points and fallback for missing org settings:**

If @copilot is not available as an assignee, it means the org-level Coding Agent authorization was not completed. Do not spend more than five minutes debugging org settings during the event.

Fallback: Have the participant complete the challenge in VS Code Agent Mode instead. The Issue they wrote becomes the Agent Mode prompt. The working set becomes the PR diff. They can open a real PR from the branch using `gh pr create`. This is not the same experience as the full Coding Agent flow, but it covers 80% of the learning objective and produces a PR they can actually review.

**Unblocking hint for Issue writing:** Ask participants to structure their Issue like a senior engineer writing a spec: background, requirements, constraints (reference AGENTS.md), and definition of done. The three-sentence "add feature X" Issue and the ten-line structured Issue produce dramatically different PRs. Have them compare outputs if time allows.

---

## Technical Escalation Path

Use this in order. Do not jump to step 3 before trying step 1.

1. **Copilot not responding or slow:** Check the status bar icon. If it shows an error, sign out and sign back in (Accounts menu in VS Code, then re-authorize). If on a corporate network, verify the Copilot proxy endpoints are reachable.

2. **Auth is fine but suggestions are not appearing:** Check `github.copilot.enable` in settings. Confirm the file type is not in the exclusion list (`github.copilot.enable` can be set per-language). Try disabling and re-enabling the extension.

3. **@workspace returns irrelevant results:** Force workspace re-indexing by running the command palette option "GitHub Copilot: Rebuild Workspace Index" (exact name may vary by version). This takes 1-3 minutes.

4. **Agent Mode not available:** This requires a Copilot Business or Enterprise subscription and VS Code 1.99 or newer. If a participant has Individual but not Business, Agent Mode may be limited or unavailable in their plan.

5. **Coding Agent not available (Challenge 08):** Fall back to VS Code Agent Mode as described in the Challenge 08 section. Do not let this block the team from completing the capstone objectives.

6. **Everything is broken:** Have the participant create a new Codespace from scratch. Most environment issues resolve in under five minutes with a fresh container.

## Suggested Debrief Questions (17:00 - 17:30)

Run these as an open group discussion, not a quiz. Pick three or four based on the day's conversations.

- What changed about how you approach writing a function comment now that you know Copilot reads it?
- When did you catch Copilot producing something wrong today? How did you catch it?
- What is the difference between Agent Mode and the Coding Agent? When would you use each?
- If you were writing a custom instructions file for your real codebase tomorrow, what would the first three rules be?
- Where in your current development workflow would Copilot save the most time - and where do you think it would create more work if you relied on it too heavily?
- What would you need to show or explain to a skeptical colleague on your team to get them to try this?

Close the debrief by asking each team or individual to name one thing they will try in their actual work within the next week. A concrete commitment to a specific, small change has much better follow-through than a general "I'll use Copilot more."
