# GitHub Copilot for Developers - FinCore Bank

You are joining the engineering team at FinCore Bank, a fictional retail bank running a Python FastAPI service that handles accounts, transfers, and transactions. The codebase has real problems: monetary values stored as floats, no test coverage, no audit logging, and exception handlers that swallow errors silently. Over the course of this day you will use GitHub Copilot to fix those problems, build new features, write tests, and ship a full change through the Copilot Coding Agent - all without leaving the tools you already use.

This is not a step-by-step tutorial. Each challenge gives you a goal, some context, and enough constraints to make it interesting. Copilot is your pair programmer. How well you direct it determines how far you get.

## Prerequisites

| Requirement | Details |
|---|---|
| GitHub account | With Copilot Individual, Business, or Enterprise subscription active |
| VS Code | Latest stable release (1.99 or newer recommended) |
| GitHub Copilot extension | Installed and signed in before the event |
| Python | 3.11 or newer |
| Node.js | 22 or newer (required for Challenge 08) |
| Git | 2.40 or newer |
| GitHub organization membership | Required for Challenge 08 Coding Agent (your coach will confirm) |

## Challenges

| # | Title | Difficulty | Time | Key Skills |
|---|---|---|---|---|
| 00 | Environment Setup and First Contact | Setup | 25 min | Copilot install, first inline suggestion, workspace orientation |
| 01 | Ghost Text Mastery: Inline Suggestions | Easy | 30 min | Alt+] / Alt+[ cycling, Ctrl+Right partial accepts, context priming |
| 02 | Copilot Chat: Context and Participants | Easy | 35 min | @workspace, @terminal, #file, #selection, /explain, /fix, Ask vs Agent modes |
| 03 | Test-Driven Development with Copilot | Medium | 45 min | TDD loop, test-first prompting, /fixTestFailure |
| 04 | Debugging and Code Quality | Medium | 40 min | @terminal, #terminalLastCommand, /fix for root causes, /explain for legacy code |
| 05 | Custom Instructions for Banking Standards | Medium | 45 min | .github/copilot-instructions.md, path-specific instructions, AGENTS.md |
| 06 | Copilot Edits: Multi-File Refactoring | Hard | 55 min | Plan Mode, Agent Mode, chat checkpoints, working set review |
| 07 | End-to-End Feature Development | Hard | 55 min | Full feature scaffold in Agent Mode, steering with follow-up messages |
| 08 | Copilot Coding Agent: Autonomous PR (Capstone) | Expert | 70 min | GitHub Issue writing, Copilot Coding Agent, PR review and iteration |
| | Total | | ~6h 40min | |

## Getting Started

### Option 1 - GitHub Codespaces (recommended)

1. Open this repository on GitHub.
2. Click Code, then the Codespaces tab, then "Create codespace on main".
3. Wait for the container to build and the postCreate script to finish.
4. Sign in to GitHub Copilot inside the Codespace when prompted.
5. Open `challenges/challenge-00.md` and follow the verification steps.

### Option 2 - Local setup

```bash
git clone <repo-url>
cd github-copilot-banking-dev
code .
```

Then follow `challenges/challenge-00.md` for local tool verification and first-run checks.

## Challenge Format

Challenges are scenario-driven. You will see a situation description, a set of tasks, and acceptance criteria. There are no screenshots showing you exactly which button to click. Read the criteria, decide how to use Copilot to meet them, and verify your own work. Coaches are available to unblock you - not to give you the answer.

Work accumulates: code you write in Challenge 01 is the same code you debug in Challenge 04 and refactor in Challenge 06. Keep your changes.

## Reference Architecture

See [resources/reference-architecture.md](resources/reference-architecture.md) for an overview of the FinCore Bank service and how the challenges build toward the target architecture.
