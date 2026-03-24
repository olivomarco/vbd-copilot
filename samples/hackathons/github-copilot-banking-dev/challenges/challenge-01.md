# Challenge 01: Ghost Text Mastery - Inline Suggestions

**Difficulty:** Easy
**Estimated Time:** 30 minutes
**Content Level:** L300

## Introduction

You are working through the FinCore Bank backlog and someone has flagged a comment left
by a previous developer:

```python
# NOTE: consider using Decimal for monetary precision - float arithmetic can
# introduce rounding errors on fractional cent calculations
```

It shows up in `account.py`, in `transaction.py`, and in `transaction_service.py`. The
team agreed weeks ago to fix it. Nobody did.

Before you start changing types, your tech lead wants you to spend time understanding
how Copilot's inline suggestions actually work - specifically how the content of the
file you are editing shapes what Copilot offers. This is not a detour. Once you
understand how context priming, import signals, and comment contracts affect suggestion
quality, every subsequent challenge goes faster.

The keyboard shortcuts you practice here are ones you will use all day.

## Description

### Part 1 - Context Priming Experiment

Open `app/models/account.py` in VS Code. At line 9, the import block ends with:

```python
from pydantic import BaseModel, ConfigDict, Field
```

Also open `app/models/transaction.py` in an adjacent tab - leave it visible. The two
files together give Copilot more signal about the codebase conventions.

In `account.py`, the `Account` class has `balance: float`. Your goal is to observe what
Copilot suggests before and after you change the import context.

Without adding any imports, delete the `balance: float` field annotation line from the
`Account` class and retype `balance:` from scratch. Note what type Copilot proposes.
Accept nothing yet.

Now add `from decimal import Decimal` to the imports at the top of the file (after the
existing imports), save the file, then delete the `balance: float` line again and retype
`balance:`. Compare the suggestion to what you saw before.

Use Alt+] and Alt+[ to cycle through the alternatives Copilot has generated. Open the
full multi-suggestion panel with Ctrl+Enter to see all available options side by side.
Pick the suggestion that uses `Decimal` and accept it with Tab.

Repeat the same experiment in `AccountCreate` for the `initial_balance` field and in
`AccountSummary` for its `balance` field. The pattern should be consistent across all
three - if it is not, check whether the file has been saved and the import is at the
top.

### Part 2 - Comment Contract

Open `app/services/transaction_service.py`. The `validate_transaction` method has two
`# BUG` comments inside it, but the docstring only describes what the method does at
a high level. Copilot is generating suggestions shaped by that vague context.

Replace the existing docstring with a detailed comment block that specifies:

- The types of each parameter (account_id is an int, amount should be Decimal, not
  float, transaction_type is a string matching one of the known type literals)
- All the things that must be true for a transaction to be valid: the amount must be
  positive and non-zero, the account must be active, and for debit-type transactions
  the account balance minus the amount must be zero or positive
- What the method returns on success (nothing - it either passes or raises)
- Which exception is raised for each failure condition

After adding that comment, delete the body of `validate_transaction` (keep the
signature and your new comment) and let Copilot regenerate it. Cycle through
alternatives. Compare the suggestion quality to what you would have gotten with the
original one-liner docstring.

The goal here is not necessarily to accept Copilot's suggestion verbatim - it is to
observe how the comment changes what you are offered.

### Part 3 - Partial Accept Practice

Copilot often suggests a block of code where the first two lines are exactly right and
the third line is wrong, or where it picks the correct approach but uses a float literal
instead of a Decimal. Pressing Tab accepts the whole thing; pressing Esc rejects all of
it. Neither is what you want.

In `validate_transaction`, position your cursor and trigger a suggestion that mixes
correct Decimal comparisons with any float-style arithmetic or hardcoded float literals.
If the first suggestion does not mix approaches, cycle with Alt+] until you find one
that does, or manually write a partial line that Copilot wants to complete with a float.

Use Ctrl+Right to accept the suggestion one word at a time. Accept the part of the
suggestion that is correct and stop before the part that is wrong. Then continue typing
the corrected version yourself.

When you have finished, `validate_transaction` should:

- Accept `amount` as a `Decimal` parameter (update the type annotation in the
  signature)
- Compare amounts using `Decimal` arithmetic, not float
- Raise `ValidationError` if amount is not positive
- Raise `AccountClosedError` if the account is inactive
- Raise `InsufficientFundsError` if the debit would produce a negative balance

## Success Criteria

- [ ] `app/models/account.py` imports `Decimal` from the `decimal` module and the
      `balance` field in the `Account`, `AccountCreate`, and `AccountSummary` classes
      uses `Decimal` as the type annotation, not `float`
- [ ] You have used Alt+] or Alt+[ to cycle through inline suggestion alternatives at
      least once during the session and can describe what you saw
- [ ] You have opened the multi-suggestion panel with Ctrl+Enter and compared at least
      two alternatives side by side
- [ ] You have used Ctrl+Right to accept part of a suggestion and then continued typing
      manually, rather than accepting the full suggestion with Tab
- [ ] `validate_transaction` in `transaction_service.py` has a detailed comment block
      above the body describing parameter types, validation rules, return value, and
      exceptions
- [ ] The `amount` parameter in `validate_transaction` has a `Decimal` type annotation
      and the comparison logic inside uses `Decimal` arithmetic
- [ ] You can explain to a fellow participant, in one or two sentences, why `float` is
      wrong for monetary values in Python

## Tips

<details>
<summary>Hint 1 - Suggestions still showing float after import change</summary>

Copilot reads the file as it is saved on disk, not the unsaved buffer state. After
adding `from decimal import Decimal`, press Ctrl+S to save the file before deleting the
field and retyping it. If suggestions still show `float`, close the file and reopen it.
Also confirm the import line is at the top of the file and not inside a function or
class body - imports buried lower in the file do not prime suggestions the same way.

</details>

<details>
<summary>Hint 2 - Not seeing alternatives when cycling with Alt+] / Alt+[</summary>

Copilot generates multiple completions in the background. If Alt+] shows only one
option, it may mean the model has high confidence in that suggestion - which is worth
noting as its own observation. To force a wider spread of alternatives, open the
multi-suggestion panel with Ctrl+Enter. This shows all completions at once in a
read-only tab labelled "GitHub Copilot". Scroll through them. Each one is a separate
candidate you can click to accept.

</details>

<details>
<summary>Hint 3 - Comment contract is not improving suggestions</summary>

Specificity of types in the comment matters more than length. A comment that says
"validates the amount" gives Copilot nothing it does not already know from the method
name. A comment that says:

```python
# amount: Decimal - must be > Decimal('0') and < Decimal('1000000')
# raises ValidationError if amount is zero or negative
# raises AccountClosedError if account.is_active is False
# raises InsufficientFundsError if account.balance - amount < Decimal('0') for debits
```

gives Copilot a concrete spec to work from. The type name `Decimal` in the comment
is especially important - it tells the model which numeric type the implementation
should use throughout.

</details>

<details>
<summary>Hint 4 - Ctrl+Right is accepting too much or too little</summary>

Ctrl+Right in VS Code accepts one "word token" of the suggestion at a time. A token
boundary is usually a space, a dot, an opening parenthesis, or a colon. In Python
code, `Decimal('0')` would accept as: `Decimal`, then `(`, then `'0'`, then `)`. If
the suggestion blends good and bad code in the middle of an expression, accept up to
the last good token, then press Esc to dismiss the remainder and continue typing
manually from there.

</details>

## Learning Resources

- Getting inline code suggestions in VS Code: https://docs.github.com/en/copilot/using-github-copilot/getting-code-suggestions-in-your-ide-with-github-copilot
- Best practices for getting useful completions: https://docs.github.com/en/copilot/using-github-copilot/best-practices-for-using-github-copilot
- How code completions work in VS Code: https://docs.github.com/en/copilot/concepts/completions/code-suggestions?tool=vscode
