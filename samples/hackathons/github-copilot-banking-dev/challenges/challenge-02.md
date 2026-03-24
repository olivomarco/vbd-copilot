# Challenge 02: Copilot Chat: Context and Participants

**Difficulty:** Easy | **Estimated Time:** 35 minutes | **Level:** L300

## Introduction

You just joined the FinCore Bank team mid-sprint. There is no onboarding doc. The previous engineer left comments like "needs work - fix later" and a Slack message that says "the interest service has some issues, not sure what." Your team lead needs a quick rundown in 30 minutes on what the API does, what is broken, and what is missing.

This is not a contrived scenario. It happens on every real project. The question is whether you spend the next two hours chasing down function calls and reading stack traces, or whether you spend 10 minutes asking the right questions in Copilot Chat.

This challenge is about asking better questions. You will learn how @workspace, #file, #selection, and slash commands change the quality of Copilot's answers - and when that matters.

**Prerequisites:** Challenges 00 and 01 completed.

## Description

Work through the four tasks below inside VS Code with the FinCore starter project open. Stay in **Ask mode** for this challenge unless a task explicitly says otherwise. The goal is to understand the codebase and surface real problems, not to rewrite everything at once.

---

### Task 1 - Project orientation with @workspace

Open a new Chat session. First, ask this question exactly as written, without any context prefix:

> "What does the FinCore Bank application do? List all API endpoints, their HTTP methods, and what service methods they call."

Note the answer. Now ask the same question again, this time prefixed with `@workspace`:

> "@workspace What does the FinCore Bank application do? List all API endpoints, their HTTP methods, and what service methods they call."

Compare the two answers. The second should name actual files, actual route paths from `accounts.py` and `transfers.py`, and actual method names from `AccountService`. If both answers look the same, close all editor tabs, reopen only the relevant files, and try again - VS Code's Copilot context is shaped by what you have open.

**What you are learning:** Copilot without context is guessing from its training data. `@workspace` makes it search your actual project. The gap between those two answers is the gap between a generic response and a useful one.

---

### Task 2 - Code explanation with #file and #selection

Open `app/services/interest_service.py`. Find the `calculate_compound_interest` function and select it (highlight the full function body).

Try three variations in Chat:

1. Type `/explain` with the selection active (no other context)
2. Type `#selection /explain`
3. Type `#file:account_service.py #file:interest_service.py How does close_account handle accounts with non-zero balances, and does interest_service interact with that path at all?`

The third query crosses file boundaries and asks a relational question. A good answer will trace the logic across both files. A weak answer will describe one file in isolation. Notice which context approach produces which result.

You do not need to fix anything yet. Read the explanations.

---

### Task 3 - Discovering problems with @workspace

Ask Chat:

> "@workspace Are there any obvious code quality issues or missing features in the FinCore codebase? Focus on the services layer."

Read the full response. Copilot should identify at least some of the following without you pointing to them: use of `float` for monetary values, gaps in error handling, thin or missing test coverage, or missing input validation. If it only gives you vague generalities, follow up with:

> "@workspace Look specifically at interest_service.py. What are the risks with how numeric types and exceptions are handled?"

Write down what it finds. You will fix several of these issues in later challenges.

---

### Task 4 - First fix with /fix

Open `app/api/routers/accounts.py`. Find the `create_account` endpoint. Right now it accepts any value for `initial_balance`, including negative numbers - not something a bank should allow.

Select the route handler function. Use inline chat (Ctrl+I on Windows/Linux, Cmd+I on Mac) or the Chat panel to ask:

> "#selection This endpoint does not validate that initial_balance is positive. Propose a fix using Pydantic v2 validators."

Review what Copilot proposes. A good response will introduce a Pydantic `field_validator` or use `Annotated` with `Field(ge=0)` and will use `Decimal` rather than `float`. If the proposal uses `float`, push back in the same Chat thread before accepting.

Accept the change using the inline diff controls. Confirm the file saves without Python syntax errors.

---

### Task 5 - Terminal context (bonus, attempt if time allows)

From the integrated terminal, run:

```
cd resources/starter && python -m pytest tests/ -v
```

Once the output appears, switch to Chat and ask:

> "@terminal #terminalLastCommand What do these test results tell us about test coverage for the services layer?"

The test run will likely show passing tests that cover very little. Copilot should be able to read the terminal output and comment on what is and is not tested.

---

## Success Criteria

- [ ] You can describe, in one sentence, what changes when you prefix a query with `@workspace` vs. asking with no context
- [ ] You used `#file` with at least one Chat query that referenced two files simultaneously
- [ ] You used `/explain` on a selected block of code and got a meaningful explanation of `calculate_compound_interest`
- [ ] You applied a validation fix to the `create_account` endpoint in `accounts.py` using a Pydantic v2 approach and the file has no syntax errors
- [ ] You can explain, without looking it up, when you would use Ask mode vs. Agent mode

## Tips

<details>
<summary>Tip 1 - @workspace returns vague or generic answers</summary>

VS Code indexes your workspace in the background the first time Copilot Chat runs. If your answers look generic (no file names, no actual function names from your project), check for a spinning indicator in the Chat panel header - indexing may still be running. Give it a minute, then retry. Also check that you opened VS Code at the project root, not a subdirectory.

</details>

<details>
<summary>Tip 2 - #file is not working or not showing a picker</summary>

For `#file` to work, the file must be part of your open VS Code workspace. Type `#file:` in the Chat input and VS Code should show a picker with matching filenames. If nothing appears, verify you opened the workspace at the correct root folder. You can also drag a file from the Explorer panel into the Chat input to attach it.

</details>

<details>
<summary>Tip 3 - /fix is not generating a Pydantic validator</summary>

If the proposed fix does not include a Pydantic validator and just adds an `if` check instead, be more specific in the same Chat thread rather than starting over. Try:

> "#selection Add a Pydantic v2 `field_validator` on `initial_balance` that raises a `ValueError` if the value is less than zero. Use `Decimal` type, not `float`."

The more concrete you are about the library version and type, the more specific the output.

</details>

<details>
<summary>Tip 4 - Ask mode vs. Agent mode - when to switch</summary>

Ask mode answers questions and proposes code for you to review and apply. Agent mode can autonomously make changes across multiple files and run terminal commands on your behalf. For exploring an unfamiliar codebase, Ask mode is safer - you stay in control of every change. Switch to Agent mode when you have a clear, scoped task like "add docstrings to all functions in interest_service.py" and you want Copilot to handle the edits directly. You will use Agent mode in a later challenge.

</details>

## Learning Resources

- [Asking GitHub Copilot questions in your IDE](https://docs.github.com/en/copilot/using-github-copilot/copilot-chat/asking-github-copilot-questions-in-your-ide)
- [GitHub Copilot Chat cheat sheet for VS Code](https://docs.github.com/en/copilot/using-github-copilot/github-copilot-chat-cheat-sheet?tool=vscode)
- [Prompt engineering for GitHub Copilot](https://docs.github.com/en/copilot/using-github-copilot/prompt-engineering-for-github-copilot)
