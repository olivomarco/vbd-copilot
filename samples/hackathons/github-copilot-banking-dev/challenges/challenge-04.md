# Challenge 04: Debugging and Code Quality

**Difficulty:** Medium | **Estimated Time:** 40 minutes | **Level:** L300

## Introduction

It is 11:15 PM at FinCore Bank. The reconciliation team just opened an incident ticket: end-of-day settlement is failing because interest calculations are returning values that differ from expected by fractions of a cent. On millions of accounts, fractions of a cent become thousands of dollars of discrepancy. The ticket is marked P1.

Your job is to find the bugs in `app/services/interest_service.py`, fix them, and get the test suite green before the reconciliation job runs at midnight. A separate security audit report also flagged that the service layer contains silent exception handling - the kind that swallows errors and makes production incidents nearly impossible to diagnose. That needs to go too.

You have Copilot, a terminal, and 40 minutes. This is not a theoretical exercise.

## Prerequisites

- Challenge 00 completed (environment setup and basic inline suggestions)
- Challenge 01 completed (ghost text mastery, inline suggestions)
- Challenge 02 completed (Copilot Chat, @workspace, #file, /explain, /fix)
- Challenge 03 is helpful for the test suite but not required

## Description

The investigation has three distinct parts. Work through them in order.

### Part A - Reproduce and Diagnose (15 minutes)

Start by running the existing test suite for `interest_service.py` from the VS Code integrated terminal:

```
pytest tests/unit/test_interest_service.py -v
```

If Challenge 03 tests do not yet exist in that file, ask Copilot Chat to generate basic smoke tests for `calculate_simple_interest` and `calculate_compound_interest` before proceeding. Tell it the file context with `#file` so it understands the function signatures.

Once you have failing tests, do not just read the stack trace yourself. Instead, open Copilot Chat and type:

```
@terminal #terminalLastCommand What caused this test failure and which line in interest_service.py is the root cause?
```

The `#terminalLastCommand` variable pulls the full terminal output - including the assertion error, the diff between expected and actual values, and the traceback - directly into Chat. Use this pattern for each failing test. Your goal in Part A is to identify all three categories of bugs before writing a single line of fix.

For any logic you do not immediately understand, select the relevant lines in the editor and ask `/explain` before touching anything. Changing code you do not understand is how one-bug incidents become three-bug incidents.

### Part B - Fix the Bugs with Copilot Assistance (20 minutes)

There are three distinct bugs to fix. Treat them as separate units of work.

**Bug 1 - Floating-point arithmetic in monetary calculations**

The service uses Python `float` for interest calculations. Float is the wrong type for money: `0.1 + 0.2` does not equal `0.3` in float arithmetic, and that error compounds across thousands of transactions. Select the affected calculation code and open Chat. Give Copilot the full context it needs:

> "This is a PCI-DSS compliant banking service. All monetary calculations must use Python `Decimal` with `ROUND_HALF_UP` rounding, never `float`. Fix the selected code to use `from decimal import Decimal, ROUND_HALF_UP` throughout."

The more specific you are about the constraint, the more accurate the fix will be. After applying the fix, check that the `account.py` model is also not passing raw floats into the service - a fix in the service is undermined if callers feed it `float` values.

**Bug 2 - Off-by-one in the simple interest formula**

The standard simple interest formula is `I = P * r * t` where `t` is time in days divided by 365. The current implementation has an arithmetic deviation from this formula. Use `/explain` on the specific calculation line and ask:

> "/explain What does this formula calculate for a 365-day loan, and how does it compare to the standard simple interest formula I = P * r * t?"

Let Copilot identify the discrepancy. Then use `/fix` or a targeted Chat prompt to correct it. The fix is a single character removal once you know where to look.

**Bug 3 - Bare except swallowing errors silently**

The `calculate_compound_interest` function contains a bare `except:` clause that catches every possible exception - including `SystemExit` and `KeyboardInterrupt` - and returns `Decimal('0.0')` without logging anything. This is why the production incident team had no error trail to follow.

Before fixing it, select the entire `try/except` block and use `/explain` to understand what the original developer was attempting to catch. Then prompt Copilot explicitly:

> "The bare `except:` in this function is an anti-pattern that catches system-level exceptions. Replace it with `except (ValueError, ArithmeticError) as e:` and re-raise as `BankingError` imported from `app.exceptions`. Preserve the original exception chain using `raise BankingError(...) from e`."

The `from e` part is not optional - it keeps the original traceback attached to the new exception, which is what incident responders need at 11 PM.

### Part C - Security-Oriented Code Review (5 minutes)

With all three bugs fixed, select the entire contents of `interest_service.py`. In Chat, ask:

> "#selection Review this code for exception handling anti-patterns and any inputs that could cause unexpected behavior if the caller passes negative values, zero values, or extremely large Decimal numbers."

This is the kind of review that a code reviewer with financial domain knowledge would do. Act on anything Copilot surfaces. Edge cases with zero or negative principal are not theoretical - they show up when other services have bugs upstream.

## Success Criteria

- [ ] All three bugs in `interest_service.py` have been identified and corrected
- [ ] `interest_service.py` uses `Decimal` throughout - no `float` type used for any monetary value
- [ ] The simple interest formula matches the standard `I = P * r * t` with no off-by-one deviation
- [ ] The bare `except:` clause has been replaced with specific exception handling that re-raises as `BankingError` with `from e` exception chaining
- [ ] `pytest tests/unit/test_interest_service.py -v` passes all tests with no failures or errors
- [ ] You can describe which Copilot feature you used to diagnose each bug: `@terminal #terminalLastCommand`, `/explain`, and `/fix`

## Tips

<details>
<summary>Tip 1 - Finding float usage across the file</summary>

Rather than reading the entire file manually, ask Copilot Chat directly:

> "@workspace Find all places in `app/services/interest_service.py` where `float` literals or `float()` conversions are used instead of `Decimal`. List the line numbers."

This surfaces every instance at once rather than finding them one by one as tests fail.
</details>

<details>
<summary>Tip 2 - Diagnosing the off-by-one with /explain</summary>

Select just the calculation line that contains `days + 1` and run:

> "/explain What does (days + 1) mean in this interest formula and is it mathematically correct for a 365-day loan at an annual rate?"

Copilot will walk through the arithmetic. A 365-day loan should accrue exactly one year of interest. With `days + 1`, a 365-day loan accrues 366/365 of a year of interest instead - a consistent overcharge that compounds across every account.
</details>

<details>
<summary>Tip 3 - Getting the bare except fix exactly right</summary>

Copilot needs explicit direction to produce exception handling that meets the re-raise requirement. Use this prompt verbatim as a starting point:

> "The bare `except:` in this function is an anti-pattern. It catches `SystemExit` and `KeyboardInterrupt` in addition to calculation errors. Replace it with a specific `except (ValueError, ArithmeticError) as e:` clause, and re-raise as `BankingError` imported from `app.exceptions`, preserving the original exception chain with `raise BankingError(f'Compound interest calculation failed: {e}') from e`."

If `BankingError` is not yet imported at the top of the file, Copilot will typically add the import - check that it has done so.
</details>

<details>
<summary>Tip 4 - #terminalLastCommand not picking up output</summary>

`#terminalLastCommand` captures the output of the last command run in the VS Code integrated terminal - not an external terminal window. Make sure you are running `pytest` inside VS Code (Terminal menu > New Terminal) rather than in a separate application. If the output is truncated, run `pytest` with `-v` to get full assertion diffs, which gives Copilot more to work with.
</details>

## Learning Resources

- [Asking Copilot questions in your IDE](https://docs.github.com/en/copilot/using-github-copilot/copilot-chat/asking-github-copilot-questions-in-your-ide)
- [GitHub Copilot Chat cheat sheet for VS Code](https://docs.github.com/en/copilot/using-github-copilot/github-copilot-chat-cheat-sheet?tool=vscode)
- [Prompt engineering for GitHub Copilot](https://docs.github.com/en/copilot/using-github-copilot/prompt-engineering-for-github-copilot)

## Advanced Challenge

The reconciliation team wants a regression guard: a test that runs `calculate_simple_interest` with a known principal of `Decimal('10000.00')`, a rate of `Decimal('0.05')`, and exactly 365 days, and asserts that the result equals `Decimal('500.00')` to the cent. Ask Copilot to generate this parametrized test, then extend it to cover the compound interest function with monthly compounding over 12 months. Pin the expected output values yourself by first calculating them manually or with Python's `decimal` module in a REPL session - do not let Copilot guess the expected values, because that just tests that Copilot agrees with itself.
