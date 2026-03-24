# Challenge 06: Copilot Edits: Multi-File Refactoring with Plan Mode

**Difficulty:** Hard | **Estimated Time:** 55 minutes | **Level:** L300

## Introduction

FinCore Bank's regulator has issued a compliance finding: there is no structured audit trail for financial operations. By end of quarter, every service-layer method that modifies account state or processes transactions must write a structured audit event capturing who did what, to which entity, and what changed. Fail this review and the bank misses its ISO 20022 certification window.

The scope is five methods across three files: `AccountService.create_account`, `AccountService.update_balance`, `AccountService.close_account`, `TransactionService.create_transaction`, and `TransactionService.validate_transaction`. Each one needs before-and-after state capture without duplicating the same logging boilerplate in every method body.

This is exactly the situation where reaching for Copilot Agent Mode makes sense over manual editing - not because the individual changes are hard, but because the pattern is repetitive, the surface area is wide, and getting the design wrong in file one means fixing it in files two and three. The right move is to design first, implement second, and keep a rollback option ready throughout.

## Prerequisites

- Challenges 00 through 05 completed
- Challenge 05 must be done: `.github/copilot-instructions.md` must exist in your repo with the FinCore Bank coding standards

## Description

This challenge has three parts. Work through them in order - Part A produces the design that Part B implements, and Part C gives you hands-on experience with the safety net you will want in every future multi-file Agent session.

### Part A - Design with Plan Mode

Before writing a single line of code, open the Chat view in VS Code and switch the agents dropdown from Ask to **Plan**. Plan Mode is read-only: the agent will read your codebase, reason about the requirements, and output a structured plan. It will not modify any files.

Give it this prompt to start:

> "Design an audit logging system for the FinCore Bank API services. Every service method that modifies financial data must log a structured audit event. Consider: (a) where audit log entries should be written and what the log schema should look like, (b) how to capture before-and-after state without duplicating code across every method, (c) whether a Python decorator or context manager better fits this codebase, and (d) what happens if the audit log write fails after the financial operation has already succeeded."

Read the plan carefully. If it proposes a context manager approach rather than a decorator, push back:

> "The team prefers Python decorators over context managers for audit logging because the decorator is visible at the call site. Revise the plan to use a `@audit_event` decorator."

Then ask the follow-up question about the failure case:

> "How would you handle the situation where the audit log write fails after the financial operation completes - is that a rollback scenario or a best-effort scenario? What are the tradeoffs?"

Once you are satisfied with the plan, choose **Open in Editor** (not Start Implementation). This saves the plan as a Markdown file. Read it. If the plan references fields not in the required schema below, note the gap before you proceed to Part B.

The audit event schema that compliance requires:

```
timestamp   - ISO 8601 UTC
user_id     - string identifier of the actor
action      - name of the operation (e.g. "create_account")
entity_id   - ID of the account or transaction being modified
before_state - dict or null (null for creation operations)
after_state  - dict (the resulting state, or a failure marker)
```

### Part B - Implement with Agent Mode

Before sending any prompt in this part, open VS Code Settings and confirm `chat.checkpoints.enabled` is set to `true`. Do this now, not after you have started editing.

Switch the agents dropdown to **Agent**. Provide a single, scoped implementation prompt. Be explicit about which files are in scope and which are off-limits:

> "Implement the audit logging system from the plan. Create `app/utils/audit.py` with an `AuditLogger` class and an `@audit_event` decorator. Apply `@audit_event` to: `AccountService.create_account`, `AccountService.update_balance`, `AccountService.close_account`, `TransactionService.create_transaction`, and `TransactionService.validate_transaction`. The decorator must capture before-state before calling the wrapped function, and log the audit event whether the operation succeeds or raises an exception - use a failure indicator in after_state for the exception case. Add a pytest fixture in `tests/conftest.py` for capturing audit log output in tests. Write at least two unit tests in `tests/unit/test_audit.py`: one covering a successful audit entry and one covering a failed operation. Only modify files under `app/utils/`, `app/services/account_service.py`, `app/services/transaction_service.py`, and `tests/`. Do not touch any migration files, `.env` files, or `interest_service.py`."

When Agent Mode produces its working set, do the following before accepting anything:

1. Open the Chat view's list of modified files. Every file listed should be one of the files you named above. If `interest_service.py`, a migration file, or any other out-of-scope file appears, use the per-file Discard button on those entries - do not Discard All.
2. Open each changed file. The inline diff shows what Agent is proposing. Use the overlay navigation arrows to step through individual hunks. Accept or reject each change on its own merits.
3. If Agent proposes terminal commands (such as `pip install` or `pytest`), read the command before approving it. Do not approve commands that reference migrations or database operations.

After accepting the implementation, run the test suite:

```
pytest tests/unit/test_audit.py -v
```

Both tests must pass. If they fail because the decorator is swallowing exceptions rather than logging them, see Hint 3.

### Part C - Checkpoint Practice

With the implementation accepted and tests passing, you now have a known-good state. This part is deliberate practice with the rollback mechanism.

Ask Agent to make a change you would not actually keep:

> "Change the audit log format to use camelCase field names instead of snake_case - so `userId` instead of `user_id`, `entityId` instead of `entity_id`, and so on."

Let Agent apply the changes. Look at the diff. Then, without accepting or discarding through the normal diff controls, open the Chat history panel and hover over the message you just sent. A clock icon appears. Click **Restore Checkpoint**. Observe how every file Agent touched reverts to its pre-camelCase state.

Next, from that same checkpoint, use **Fork Conversation** to open a new branch of the chat. In this fork, ask Copilot whether the camelCase change would break any downstream consumers of the audit log, and whether the compliance schema specifies field name casing. Explore the question without committing to either answer. This is the workflow for evaluating a design choice without permanently changing your codebase.

## Success Criteria

- [ ] `app/utils/audit.py` exists and contains an `AuditLogger` class and an `@audit_event` decorator
- [ ] The `@audit_event` decorator is applied to all five service methods named in the description
- [ ] The decorator captures before-state prior to calling the wrapped function, and logs an audit event on both success and exception
- [ ] `tests/unit/test_audit.py` exists with at least two tests, both passing via `pytest`
- [ ] A plan Markdown file was saved from Plan Mode before any code was written, and you can describe the key design decisions it covered
- [ ] `chat.checkpoints.enabled` was turned on before Part B, and you used Restore Checkpoint at least once during Part C
- [ ] The Agent working set was reviewed per-file before changes were accepted - no out-of-scope files were kept
- [ ] Terminal commands proposed by Agent were read before approval - no migration or `.env` commands were run
- [ ] The implementation follows `.github/copilot-instructions.md`: structlog is used, no PII appears in log fields, domain exceptions from `app/exceptions.py` are not caught and swallowed

## Tips

<details>
<summary>Hint 1 - Agent touched files it should not have</summary>

Open the working set list in the Chat view. Every file Agent modified is shown there. Find the out-of-scope entries and click the per-file Discard button on each one individually. Do not click Discard All - that throws away the valid changes too. Once you have discarded the unwanted files, add a scope constraint to your next prompt: "Only modify files under `app/utils/` and the two service files I specified. Do not change any other files."

</details>

<details>
<summary>Hint 2 - Plan Mode keeps suggesting a context manager instead of a decorator</summary>

Steer the plan directly. Tell it: "The team prefers the decorator pattern because it keeps the audit annotation visible at the function definition rather than inside the function body. A context manager would require every developer to remember to add the `with` block in every new method. Revise the plan to use a `@audit_event` decorator." Plan Mode responds well to this kind of constraint because it is still in reasoning mode rather than code-generation mode - you can change the design before a single line is written.

</details>

<details>
<summary>Hint 3 - Audit tests fail because the decorator does not handle exceptions correctly</summary>

The decorator needs to call the wrapped function inside a try-except block. Capture before-state before entering the try block. If the function raises, catch the exception, log the audit event with a failure indicator in `after_state` (for example `{"status": "failed", "error": str(exc)}`), and then re-raise the original exception. The test for the failed-operation case should assert both that the domain exception propagates to the caller AND that the audit log captured an entry for that failed attempt.

</details>

<details>
<summary>Hint 4 - Cannot find the Restore Checkpoint button</summary>

Restore Checkpoint lives in the Chat history panel, not in the editor diff controls. Hover your cursor over any previous chat turn in the panel - a small clock icon appears to the left of the message. Click that icon to restore all files to the state they were in before that specific prompt ran. The clock only appears on hover, so it is easy to miss. If you have not enabled `chat.checkpoints.enabled` in Settings, the icon will not appear at all - go to Settings, search for "checkpoints", and toggle it on before trying again.

</details>

<details>
<summary>Hint 5 - Agent loop is producing increasingly wrong output</summary>

If each Agent iteration makes the code worse rather than better - adding noise, breaking unrelated methods, or spiraling into a pattern that does not match the codebase - stop the loop using the Stop button in Chat. Then hover over the last good chat turn and use Restore Checkpoint to get back to a clean state. Break your original prompt into two smaller tasks: first ask Agent to create only `app/utils/audit.py` with no changes to service files, review that single file in full, accept it, then send a second prompt to apply the decorator to the service files. Smaller working sets are easier to review and easier to roll back.

</details>

## Learning Resources

- [Asking GitHub Copilot questions in your IDE](https://docs.github.com/en/copilot/using-github-copilot/copilot-chat/asking-github-copilot-questions-in-your-ide)
- [Chat checkpoints in VS Code](https://code.visualstudio.com/docs/copilot/chat/chat-checkpoints)
- [Copilot local agents in VS Code](https://code.visualstudio.com/docs/copilot/agents/local-agents)

## Advanced Challenge

The current `@audit_event` decorator captures state by calling a `_get_state` method on `self`. This means every service class needs to implement `_get_state`, which is repetitive. Design an `Auditable` base class or mixin that service classes can inherit from, where `_get_state` is defined once using the entity ID argument to look up current state. Update `AccountService` and `TransactionService` to inherit from this base, remove the duplicated `_get_state` implementations, and write a test that confirms the base class state capture works correctly when a subclass does not override it. Use Plan Mode to design the refactoring before implementing.
