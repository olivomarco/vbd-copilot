# Challenge 00: Environment Setup and First Contact

## Introduction

You have just joined the engineering team at FinCore Bank. Before diving into the sprint
backlog, you need to verify that your development environment is ready and that GitHub
Copilot is active and aware of the FinCore Bank codebase.

This challenge takes approximately 25 minutes. There is no banking logic to implement
here - the goal is to confirm your tooling works and get a first feel for inline
suggestions and Chat before the challenges that follow.

## Description

### Part 1: Verify Your GitHub Copilot Subscription

In a browser, go to https://github.com/settings/copilot and confirm that you have an
active Copilot subscription. If your organisation has assigned you a seat through
GitHub Copilot Business or Enterprise, you should see a status of "Active". If you see
a prompt to start a trial, contact your hackathon facilitator before continuing.

### Part 2: Open the Repository

**Recommended path - GitHub Codespaces**

On the repository landing page, click the green "Code" button, select the "Codespaces"
tab, then click "Create codespace on main". The dev container will build automatically
and install Python 3.11, Node.js 22, the GitHub CLI, and all Python dependencies from
`resources/starter/requirements.txt`. The first build takes three to five minutes.
Subsequent opens use the cached image and start in under thirty seconds.

**Alternative path - Local VS Code**

If you are working locally, confirm you have the following before cloning:

- VS Code 1.90 or later (Help > About)
- Python 3.11 or later (`python --version`)
- Node.js 22 or later (`node --version`)
- GitHub CLI (`gh --version`)
- The "GitHub Copilot" and "GitHub Copilot Chat" extensions installed in VS Code

Clone the repository, open it in VS Code, and run the following from the repository
root:

```
pip install -r resources/starter/requirements.txt
```

### Part 3: Verify GitHub Copilot is Active

Look at the bottom status bar in VS Code. You should see the GitHub Copilot icon - a
small circle with two dots. If the icon is grey or has a line through it, click it and
sign in with your GitHub account.

Open the Command Palette (Ctrl+Shift+P on Windows/Linux, Cmd+Shift+P on macOS) and
type "GitHub Copilot: Check Status". The Output panel should report "Connected" or
similar.

If Copilot does not connect, check that your GitHub account is the same one with an
active subscription. You can also try signing out and back in via the Accounts menu
in the bottom-left corner of VS Code.

### Part 4: Explore the FinCore Bank Starter Application

Open `resources/starter/` in the VS Code Explorer panel. Spend a few minutes
navigating the structure:

- `README.md` - the team onboarding narrative and known issues list
- `app/main.py` - the FastAPI application entry point and exception handling
- `app/models/account.py` - the Account Pydantic schemas
- `app/services/interest_service.py` - interest calculations with known gaps

Notice the improvement markers and bug markers scattered through the codebase. These are the
deliberate gaps you will be filling throughout the day with Copilot.

Do not fix anything yet. Just read and orient yourself.

### Part 5: First Inline Suggestion

Open `resources/starter/app/models/account.py`. Scroll to the `AccountCreate` class.
Find the line that reads:

```python
    # Validate that account_number matches IBAN format
```

This comment is already in the file. Position your cursor on the blank line immediately
after it and press Enter to begin a new line. Wait one to two seconds. Copilot should
display ghost text suggesting a `@field_validator` implementation.

Review the suggestion before accepting it. If Copilot suggests importing
`field_validator` from `pydantic`, that is the correct pattern. Accept the suggestion
with Tab.

You do not need to keep this validator for the rest of the day - the goal is simply to
confirm that inline suggestions are working in Python files.

If no suggestion appears after three seconds, try the following:
- Press Alt+\ (Windows/Linux) or Option+\ (macOS) to manually trigger a suggestion
- Check that the file is saved (inline suggestions do not appear in unsaved files with
  syntax errors)

### Part 6: First Chat Interaction

Open the GitHub Copilot Chat panel by clicking the chat icon in the left Activity Bar,
or press Ctrl+Alt+I. In the chat input box, type the following exactly as written:

```
@workspace What does the FinCore Bank application do? List all API endpoints.
```

Wait for the response. Copilot Chat should describe the application and enumerate the
routes from the router files. A good response will mention `/auth/token`,
`/accounts/`, `/transactions/`, and `/transfers/` with a brief description of each.

If the response is generic and does not reference specific files from the repository,
try closing and reopening the Codespace or VS Code window to let the extension finish
indexing the workspace. The `@workspace` participant requires the workspace index to be
built before it can reference file contents.

### Part 7: Start the Application

From the `resources/starter/` directory, run:

```
uvicorn app.main:app --reload
```

Open http://localhost:8000/health in a browser. You should see:

```json
{"status": "ok", "service": "fincore-bank-api", "version": "1.0.0"}
```

In Codespaces, the port will be automatically forwarded and a notification will appear.
The interactive Swagger docs are at http://localhost:8000/docs.

## Success Criteria

- The GitHub Copilot icon appears in the VS Code status bar without an error indicator
- Typing a comment in a Python file produces ghost text inline suggestions
- Copilot Chat responds to the `@workspace` query and references `/accounts`,
  `/transactions`, `/transfers`, and `/auth` endpoints
- The FinCore Bank API starts and http://localhost:8000/health returns a 200 response
- You can describe to a neighbour what the three service classes do and where the known
  bugs are located

## Tips

- If inline suggestions do not appear in Python files, open VS Code Settings and search
  for "github.copilot.enable". Confirm that it is set to `true` for all language
  identifiers, not just `*`.
- The `uvicorn` command must be run from inside `resources/starter/`, not from the
  repository root. If you get a `ModuleNotFoundError: No module named 'app'`, you are
  in the wrong directory.
- If `pip install` fails with permission errors in a local setup, use
  `pip install --user -r requirements.txt` or activate a virtual environment first.
- The demo credentials for the API are `developer@fincore.bank` / `hackathon2024`.

## Learning Resources

- GitHub Copilot documentation: https://docs.github.com/en/copilot
- Getting started with GitHub Copilot in VS Code: https://code.visualstudio.com/docs/copilot/getting-started
- GitHub Copilot Chat overview: https://docs.github.com/en/copilot/github-copilot-chat/about-github-copilot-chat
- Pydantic v2 field validators: https://docs.pydantic.dev/latest/concepts/validators/
- FastAPI documentation: https://fastapi.tiangolo.com
