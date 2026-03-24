# Challenge 03: Test-Driven Development with Copilot

**Difficulty:** Medium | **Estimated Time:** 45 minutes | **Level:** L300

---

## Introduction

The FinCore Bank QA lead sent a message this morning: `account_service.py` has zero test coverage, and the interest calculation service has three known bugs with nothing to catch them. The compliance team has a hard rule - any service that touches money must have tests before the release branch is locked. If those interest calculations are off by even a cent at banking scale, the audit fails.

This challenge covers two distinct workflows. The first is TDD: you write the tests before the implementation exists, let Copilot fill in both sides, and watch the loop turn red then green. The second is test generation for code that already exists but was written without tests - use `/tests` to build a suite, find the gaps, and then let `/fixTestFailure` trace and repair the bugs that the tests expose.

Both workflows are useful. Knowing when to apply each one is the skill.

---

## Prerequisites

- Challenge 00 completed (environment setup, first inline suggestion)
- Challenge 01 completed (ghost text mastery, inline suggestions, Alt+[ cycling)
- Challenge 02 completed (Copilot Chat, @workspace, #file, /explain, /fix)

---

## Description

Your working area is the `tests/unit/` directory. Both test files there are empty - they exist but contain no tests yet. Your goal across the three parts below is to fill them with meaningful, passing tests - and to surface and fix the deliberate bugs in `interest_service.py` along the way.

**Before starting any part:** open `tests/conftest.py` in a side-by-side tab. Copilot will pick up the existing fixture names, import paths, and naming patterns from that open file and use them in generated tests automatically. Do not skip this step - the tests will be harder to integrate if they do not match the conventions already established there.

---

### Part A - TDD for AccountService (20 minutes)

Open `tests/unit/test_account_service.py` and `app/services/account_service.py` side by side.

Do NOT use the `/tests` slash command for this part. That command generates tests for existing implementations - here, the implementation is incomplete and you are driving it with tests first.

In Copilot Chat (Ask mode), describe the test requirements for `create_account` in natural language. Ask Copilot to write failing tests first - tests that reference the correct exception types from `app.exceptions`, use `Decimal` for all monetary values, and follow the naming pattern `test_<method>_<scenario>_<expected_outcome>`. Once Copilot proposes the tests, accept them and run `pytest tests/unit/test_account_service.py`. They should fail - that is the point. Red is the correct state here.

Once you have confirmed the failures, ask Copilot in Chat to implement the missing logic in `AccountService` to make those specific tests pass. Run pytest again. Your target is GREEN for at minimum four tests: creating an account with a valid positive balance, creating with a negative balance (should raise `ValidationError`), creating with zero balance (should succeed), and at least one `update_balance` or `close_account` scenario.

---

### Part B - /tests and coverage gap analysis (10 minutes)

Open `app/services/interest_service.py`. This file has a working-looking implementation with three deliberate bugs embedded in it. There are currently no tests to catch any of them.

Switch to Copilot Chat and use `/tests` - or write a prompt that asks Copilot to generate a thorough pytest suite for `InterestService`. The prompt should name specific scenarios you want covered: positive rates, a zero rate, a negative rate, boundary values, a one-day calculation, and the exception handling path. Accept the generated tests into `tests/unit/test_interest_service.py`.

Run the full suite. Some tests will fail. That outcome is correct and expected - the bugs are real, and a test suite that passes against a buggy implementation is not helping anyone. Before moving to Part C, ask Copilot in Chat: "What additional tests should be included to improve coverage of `InterestService`?" Review the suggestions and add any that target scenarios not already covered.

---

### Part C - /fixTestFailure in action (15 minutes)

Pick one of the failing tests from Part B - the one for simple interest with a one-year term is a good starting point.

Switch to Agent mode in Copilot Chat. Reference the failing test and `interest_service.py` using `#file`, then ask Copilot to use `/fixTestFailure` to trace the failure. Copilot should read the test output and step through the calculation in `calculate_simple_interest` to identify where the result diverges from the expected value.

Your goal in this part is to identify the bugs, understand why they exist, and use Copilot to diagnose the root cause. Note the off-by-one in the days calculation and any float precision issues, but do not apply the full fix yet - Challenge 04 builds a proper debugging workflow around these same bugs using `@terminal` and `#terminalLastCommand`. Confirming that the bugs exist is sufficient here.

The `bare except` block is a third issue. Once you have located the first two, look at the exception handling path and ask Copilot to explain what `except:` catches and why that is a problem.

---

## Success Criteria

- [ ] `tests/unit/test_account_service.py` contains at least 4 pytest tests that all pass, covering at minimum: valid account creation, negative initial balance rejection, zero balance creation, and one balance update or close scenario
- [ ] `tests/unit/test_interest_service.py` contains tests that fail on the current `interest_service.py` implementation (the failures confirm the bugs exist)
- [ ] The off-by-one bug in `interest_service.py` has been identified and you can explain to a teammate what causes it (the fix is applied in Challenge 04)
- [ ] All monetary assertions in both test files use exact `Decimal` comparison - no `assertAlmostEqual` or float tolerance
- [ ] You can describe to a teammate the difference between the TDD workflow in Part A (test-first, no `/tests`) and the code-first workflow in Part B (using `/tests` on existing code)

---

## Tips

<details>
<summary>Tip 1: Prompting for TDD in Part A</summary>

A prompt that gives Copilot enough structure to produce useful test stubs looks something like this:

"Write failing pytest tests for `AccountService.create_account`. The tests should cover: creating an account with a valid `Decimal` balance returns an `Account` object with the correct balance, creating with a negative initial balance raises `ValidationError` imported from `app.exceptions`, and creating with zero balance succeeds and returns an account. Use the fixture names and import style already present in `conftest.py`."

The specificity matters. If you ask for "some tests for `create_account`" without naming the scenarios, Copilot will generate something that compiles but probably misses the exception cases you actually need.

</details>

<details>
<summary>Tip 2: When /fixTestFailure does not find the bug on its own</summary>

If Copilot traces the failure but does not identify the root cause, switch to Agent mode and add more explicit context:

"#file:app/services/interest_service.py The test `test_simple_interest_one_year` is failing with an assertion error. Walk through the `calculate_simple_interest` method step by step for a principal of 10000, rate of 0.05, and days of 365. Show each intermediate value and identify where the result diverges from the expected $500.00."

This forces Copilot to reason through the arithmetic rather than just scan for obvious syntax problems. The off-by-one becomes visible when the intermediate values are printed out.

</details>

<details>
<summary>Tip 3: Understanding the off-by-one</summary>

The bug in `calculate_simple_interest` adds 1 to the days parameter before computing. Think about what that means concretely: a loan for exactly 365 days gets calculated as if it ran for 366 days. For a $10,000 principal at 5%, that is roughly $1.37 extra interest per loan. Across a portfolio of thousands of accounts, that adds up fast.

The fix is a one-line change, but the test is what forces you to notice it at all. That is the point of the exercise - the bug was always there; the test made it visible.

If you are unsure whether the `+ 1` was intentional, ask Copilot: "Is there a banking convention for day-count that would justify adding 1 to the actual number of days in a simple interest calculation?" The answer will help you decide whether the fix is correct.

</details>

<details>
<summary>Tip 4: Float vs Decimal in monetary assertions</summary>

If your tests use `assert result == 500.0` with float arithmetic in the implementation, you may see failures like `AssertionError: 499.99999999997 != 500.0`. This is not the off-by-one bug - it is Python float precision, and it is a separate problem worth fixing.

The right fix is to change the assertion to compare `Decimal` values: convert the result to `Decimal` before asserting, or change the implementation to use `Decimal` arithmetic throughout. Ask Copilot: "Rewrite this assertion to use `Decimal` exact comparison" and it will show you the pattern. Once you have it for one test, apply it consistently across all monetary assertions in the file.

</details>

---

## Learning Resources

- [Asking Copilot questions in your IDE](https://docs.github.com/en/copilot/using-github-copilot/copilot-chat/asking-github-copilot-questions-in-your-ide)
- [GitHub Copilot Chat cheat sheet for VS Code](https://docs.github.com/en/copilot/using-github-copilot/github-copilot-chat-cheat-sheet?tool=vscode)
- [Best practices for using GitHub Copilot](https://docs.github.com/en/copilot/using-github-copilot/best-practices-for-using-github-copilot)

---

## Advanced Challenge

After all tests pass, open `app/models/account.py`. The `Account` model uses `float` for the `balance` field. Ask Copilot in Agent mode: "Migrate the `Account`, `AccountCreate`, and `AccountUpdate` models to use `Decimal` instead of `float` for the `balance` field. Update `account_service.py` and all test files to match. Run the full test suite and fix any failures that result."

This is a cross-file refactor. Watch how Copilot handles the propagation of the type change across multiple files and whether it correctly identifies every place where the type assumption was baked in.
