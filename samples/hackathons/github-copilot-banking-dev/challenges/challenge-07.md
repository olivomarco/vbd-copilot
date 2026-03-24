# Challenge 07: End-to-End Feature Development with Agent Mode

**Difficulty:** Hard | **Estimated Time:** 55 minutes | **Level:** L300

## Introduction

FinCore Bank's product team has a Sprint Review tomorrow morning. The credit risk score feature was scoped for this sprint, demoed in a slide deck three weeks ago, and then... nothing happened. The backend team hit a blocker on another service, and now the feature has zero lines of code.

That feature is yours to build. The spec is clear: a `GET /accounts/{account_id}/risk-score` endpoint that calculates a credit risk score from 0 to 100 based on an account's transaction history. A score of 0 means the account is high risk; 100 means it is low risk. The risk management dashboard team is already wiring up their frontend to this contract.

In 55 minutes you need a working model, a working service, a registered FastAPI route with JWT auth, and a passing test suite - all conforming to the FinCore coding standards already defined in your custom instructions from Challenge 05. GitHub Copilot Agent Mode is the tool. Your job is to direct it, review what it produces, correct it when it drifts, and ship a feature that actually passes `pytest`.

This is what real AI-assisted development looks like. No pre-built skeleton. No guided steps. Just a spec, a codebase, and Copilot.

## Prerequisites

- Challenges 00 through 06 completed
- The FinCore Bank starter project is running locally (`uvicorn app.main:app --reload`)
- The `@audit_event` decorator from Challenge 06 is present in `app/utils/audit.py`
- The custom instructions file `.github/copilot-instructions.md` from Challenge 05 is in place

## Description

This challenge has three parts. Work through them in order - skipping Part A will make Part B harder.

---

### Part A - Plan before you build (10 minutes)

Open a new Copilot Chat panel and switch to **Plan Mode** (not Agent Mode yet). Ask Copilot to design the full implementation:

> "FinCore Bank needs a GET /accounts/{account_id}/risk-score endpoint. The risk score is an integer from 0 to 100 where 0 is the highest risk and 100 is the lowest risk. It is calculated from four factors in the account's transaction history: overdraft frequency (how often the balance went below zero), average account balance, transaction regularity (consistent patterns mean lower risk), and recent failed transactions. Design a complete implementation plan covering which files to create, the Pydantic v2 RiskScoreResponse model schema, the RiskScoreEngine service class design, the FastAPI route definition, and a test plan."

After the plan comes back, ask at least one follow-up question about edge cases - for example, what should happen when an account has no transaction history at all, or when the account ID does not exist. Review the plan critically before moving on. The goal is to catch design gaps now, not halfway through Agent Mode.

---

### Part B - Build with Agent Mode (35 minutes)

Take a checkpoint in VS Code before you start (Command Palette - "Create Checkpoint"). Then switch to **Agent Mode**.

Write a single scoped prompt that references the plan you just reviewed. Be explicit about the file list - Agent Mode performs better when it knows exactly what it is supposed to touch:

> "Implement the risk score feature based on the plan we just designed. Create: (1) `app/models/risk_score.py` with a Pydantic v2 RiskScoreResponse model where risk_score is an int between 0 and 100 and risk_level is one of LOW, MEDIUM, HIGH, or CRITICAL, (2) `app/services/risk_service.py` with a RiskScoreEngine class that computes the score from the four factors, (3) a new route GET /accounts/{account_id}/risk-score in `app/api/routers/` with JWT auth that returns RiskScoreResponse and raises AccountNotFound for unknown accounts, (4) `tests/unit/test_risk_service.py` with at least 4 tests - one per risk factor plus a boundary test. Apply the @audit_event decorator from app.utils.audit. Follow all rules in .github/copilot-instructions.md."

Use `#file:app/utils/audit.py` and `#file:app/exceptions.py` as references in your prompt so Agent can read the existing patterns before generating code.

**While Agent is running:** watch the working set panel. Before approving each generated file, scan it briefly. You are looking specifically for three things:

- Does `risk_service.py` use `Decimal` for any monetary calculation, or did Copilot default to `float`?
- Is the `@audit_event` decorator applied to the scoring method, not just mentioned in a comment?
- Does any log call pass `account_number` or a raw balance value as a structured field?

If Agent violates one of these, **do not stop the session and discard everything**. That is the wrong move. Instead, let Agent finish the current working set, then send a targeted follow-up message in the same session window. For example:

> "The risk_service.py uses float for monetary values. Update all monetary calculations in risk_service.py to use Python Decimal instead of float. Keep all other logic exactly as written."

This is the core skill of Part B: steering a live Agent session with follow-up corrections rather than discarding context and starting over. A restart loses the planning context, the file structure decisions, and the test scaffolding. A follow-up message fixes the specific issue and keeps everything else intact.

The exact scoring formula inside RiskScoreEngine is yours to define (with Copilot's help). What matters is that the formula is deterministic and that the final score is clamped to the range [0, 100] before being placed in the response.

---

### Part C - Verify and fix (10 minutes)

Run the new test file:

```
pytest tests/unit/test_risk_service.py -v
```

If tests fail, use `/fixTestFailure` in Agent Mode - paste the failure output and let Copilot fix it. Do not hand-edit the tests to pass around broken logic; fix the logic.

Then do a manual compliance check against the FinCore custom instructions:

- Open `app/services/risk_service.py` and search for `float`. There should be none in monetary calculations.
- Open the router file and confirm `@audit_event` appears above the route handler.
- Search the service for `structlog` - it should be the logger, not the standard library `logging`.
- Confirm that the new router is registered in `app/main.py` with the correct prefix.

If any of these checks fail, fix them with a follow-up steering message in Agent Mode, not by hand.

---

### File map for reference

```
app/
  models/
    risk_score.py          <- create this
  services/
    risk_service.py        <- create this
  api/
    routers/
      accounts.py          <- add the new route here (or create risk.py)
  utils/
    audit.py               <- existing - use @audit_event from here
  exceptions.py            <- existing - use AccountNotFound from here
tests/
  unit/
    test_risk_service.py   <- create this
.github/
  copilot-instructions.md  <- existing - Copilot should follow this automatically
```

## Success Criteria

- [ ] `app/models/risk_score.py` exists and defines a valid Pydantic v2 `RiskScoreResponse` model with `account_id` (str), `risk_score` (int), `risk_level` (str), `contributing_factors` (list[str]), and `calculated_at` (datetime)
- [ ] `app/services/risk_service.py` exists and defines a `RiskScoreEngine` class with a method that computes a score from transaction history
- [ ] The `GET /accounts/{account_id}/risk-score` route is registered and accessible in the running FastAPI app (verify at `/docs`)
- [ ] The route returns HTTP 404 when the account ID does not exist, using `AccountNotFound` from `app.exceptions` (not a bare `HTTPException`)
- [ ] `tests/unit/test_risk_service.py` contains at least 4 tests and all pass with `pytest tests/unit/test_risk_service.py`
- [ ] `risk_service.py` has no `float` usage for monetary values - monetary calculations use `Decimal`
- [ ] The `@audit_event` decorator from `app.utils.audit` is applied to the route handler or the service method
- [ ] The participant used at least one follow-up steering message during the Agent session to correct a drift (not a full session discard and restart)

## Tips

<details>
<summary>Tip 1: Agent created the router file but the endpoint is not showing up in /docs</summary>

Agent probably created `app/api/routers/risk.py` but forgot to register it. Add a follow-up in the same Agent session:

> "The risk router was created but not registered in the app. Update `app/main.py` to include the new router with prefix `/accounts` and tag `accounts`."

Check `app/main.py` afterward to confirm the `include_router` call is there.

</details>

<details>
<summary>Tip 2: The risk score is occasionally returning values above 100 or below 0</summary>

The scoring formula Copilot wrote probably does not clamp the output. Add a follow-up:

> "The final risk score in risk_service.py is not clamped. Before constructing the RiskScoreResponse, clamp the computed score using `max(0, min(100, score))` so it can never go outside the 0-100 range."

Then add a boundary test: create an account fixture with extreme values (100 overdrafts, zero balance, many recent failures) and assert the returned score is still >= 0 and <= 100.

</details>

<details>
<summary>Tip 3: Writing the boundary test - how to ask Copilot to reason about its own algorithm</summary>

Agent Mode wrote the scoring formula, but you need to test its extremes. In a follow-up ask:

> "#file:app/services/risk_service.py What are the minimum and maximum possible values this scoring algorithm can produce before clamping? Write a test in tests/unit/test_risk_service.py that constructs an account with those extreme values and asserts the returned risk_score is always between 0 and 100 inclusive."

This forces Copilot to read its own output and reason about it rather than writing a generic range test.

</details>

<details>
<summary>Tip 4: Copilot used float in the service despite custom instructions - how to fix without discarding</summary>

If you see `float` in `risk_service.py`, send a targeted correction in the active Agent session:

> "risk_service.py uses float for monetary calculations, which violates the FinCore custom instructions. Update all monetary values and arithmetic in risk_service.py to use Python Decimal from the decimal module. Import Decimal at the top of the file. Keep all other logic, structure, and comments exactly as they are."

This is a surgical patch. Agent should produce a diff that touches only the type declarations and arithmetic, not the whole file. If it tries to rewrite everything, use "Restore Checkpoint" from before Part B and refine the original prompt to be more explicit about Decimal upfront.

</details>

<details>
<summary>Tip 5: AccountNotFound is not being raised - the route returns a generic 500 instead</summary>

This usually means the service raises a plain `ValueError` or `KeyError` for unknown IDs, and the FastAPI exception handler does not know how to handle it. Add a follow-up:

> "In risk_service.py, when the account ID is not found in the data store, raise AccountNotFound from app.exceptions instead of ValueError or KeyError. Import AccountNotFound at the top of the file."

Then verify that `app/exceptions.py` has the `AccountNotFound` class and that a corresponding exception handler is registered in `app/main.py`.

</details>

## Learning Resources

- [Asking GitHub Copilot questions in your IDE](https://docs.github.com/en/copilot/using-github-copilot/copilot-chat/asking-github-copilot-questions-in-your-ide)
- [Copilot Agents and local agents in VS Code](https://code.visualstudio.com/docs/copilot/agents/local-agents)
- [Prompt engineering for GitHub Copilot](https://docs.github.com/en/copilot/using-github-copilot/prompt-engineering-for-github-copilot)
- [Pydantic v2 model configuration](https://docs.pydantic.dev/latest/concepts/config/)
- [FastAPI dependency injection for security](https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/)

## Advanced Challenge

The product team liked the risk score feature and wants a second endpoint: `POST /accounts/{account_id}/risk-score/explain` that returns a plain-English explanation of why the account received its score, written by Azure OpenAI using the `contributing_factors` list as input context. The explanation should be cached in Azure Cache for Redis with a TTL of 10 minutes so repeated calls for the same account do not hit the OpenAI API. Use Copilot Agent Mode to design and build this extension - and apply the same steering technique if the generated code hardcodes the OpenAI API key rather than reading it from environment variables.
