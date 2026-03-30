# Usage Guide

## Usage Examples

### Generate a presentation

```text
>>> I need a 1-hour L300 deck on GitHub Copilot agent extensions for financial services
  >> routed -> slide-conductor | model: claude-sonnet-4.6

  ? Agent asks: I found these sub-areas from official docs...
  ...
  [Phase 0-4 proceeds automatically with approval stops]
  ...
  OK: Saved outputs/slides/gh-copilot-extensions-l300-1h.pptx (30 slides)
```

### Generate demo guides

```text
>>> Create 3 L300 demos on Azure Container Apps for Contoso
  >> routed -> demo-conductor | model: claude-sonnet-4.6

  ? Agent asks: What specific aspects should the demos cover?
  ...
  [Phase 0-5 proceeds automatically with approval stops]
  ...
  OK: Saved outputs/demos/contoso-aca-demos.md + 3 companion files
```

### Generate from your own notes

```text
>>> Build a 30min L200 deck from my notes in notes/aks-security-review.md
  >> routed -> slide-conductor | model: claude-sonnet-4.6

  ? Agent reads your notes file, identifies key topics...
  ...
  [Phase 2-4 proceeds - planning from your content, then build + QA]
  ...
  OK: Saved outputs/slides/aks-security-review-l200-30m.pptx (18 slides)
```

### Generate a technical update briefing

```text
>>> Create a 15min L200 briefing on what's new in Azure Kubernetes Service this quarter
  >> routed -> slide-conductor | model: claude-sonnet-4.6

  ? Agent researches recent AKS announcements and changelog...
  ...
  [Phase 0-4 proceeds automatically with approval stops]
  ...
  OK: Saved outputs/slides/aks-quarterly-update-l200.pptx (12 slides)
```

### Run the full AI project lifecycle

```text
>>> @ai-brainstorming Brainstorm AI use cases for a healthcare company
  >> routed -> ai-brainstorming | model: claude-opus-4.6
  ...
  OK: Saved outputs/ai-projects/healthcare-ai/docs/brainstorming.md (10+ ranked ideas)

>>> @ai-solution-architect Design the architecture for idea #3
  >> routed -> ai-solution-architect | model: claude-opus-4.6
  ...
  OK: Saved 5 architecture documents to outputs/ai-projects/healthcare-ai/docs/

>>> @ai-implementor Implement the solution
  >> routed -> ai-implementor | model: claude-sonnet-4.6
  ...
  OK: Saved infra + src + tests + scripts to outputs/ai-projects/healthcare-ai/
```

### Direct @mentions

You can always skip the router and go straight to a specific agent:

```text
>>> @slide-conductor Make a 30min L200 deck on Microsoft Fabric
>>> @demo-conductor Build 2 demos on GitHub Actions for Zava Industries
>>> @ai-brainstorming Brainstorm AI use cases for a retail company improving CX
>>> @ai-solution-architect Design the architecture for a customer service chatbot on Azure
>>> @ai-implementor Implement the infrastructure and app code for the chatbot solution
```

---

## Slash Commands

| Command | Description |
|---------|-------------|
| `/new [agent]` | Start a new session (optionally pre-selecting an agent) |
| `/resume [id\|name]` | Resume a previous session |
| `/agent <name>` | Switch to a specific agent mid-session |
| `/agents` | List all available agents with details |
| `/model <id>` | Switch the LLM model |
| `/compact` | Manually compact context window (free memory) |
| `/debug` | Toggle debug mode (shows tool I/O, subagent flow, token usage) |
| `/sessions` | List active and resumable sessions |
| `/sessions all` | All sessions including ended ones |
| `/sessions <id>` | Detail view of a specific session |
| `/sessions <id> turn <N>` | Show a specific turn within a session |
| `/sessions <id> invocations` | Tool call and subagent trace for a session |
| `/sessions name <id> <nick>` | Set a session nickname |
| `/sessions end <id>` | End a specific session |
| `/sessions cleanup` | Purge old sessions |
| `/usage` | Current session: tokens, cost, context window |
| `/usage all` | Global usage aggregates by agent, model, period |
| `/usage today\|week\|month` | Usage filtered by time period |
| `/usage --agent <name>` | Usage filtered to a specific agent |
| `/usage --model <name>` | Usage filtered to a specific model |
| `/samples` | Show sample output library |
| `/tutorial` | Interactive guided walkthrough |
| `/clear` | Clear the screen and redisplay the banner |
| `/help` | Show quick command reference |
| `/quit` | Exit CSA-Copilot (session remains resumable) |

---

## Observability and Cost Tracking

CSA-Copilot tracks token usage, timing, and estimated costs in a local SQLite database at `~/.csa-copilot/csa-copilot.db`. Nothing leaves your machine.

**What gets tracked:**

- Input and output tokens per turn, including cache reads and writes
- Estimated USD cost per turn (based on published model pricing)
- Tool call and subagent invocation counts
- Session duration, turn count, and agent/model per session

**Usage commands:**

| Command | What it shows |
|---------|--------------|
| `/usage` | Current session: token counts, estimated cost, context window capacity |
| `/usage all` | Global aggregates: total tokens and cost broken down by agent, model, and time period |
| `/usage today` | Today's usage across all sessions |
| `/usage week` | This week's usage |
| `/usage month` | This month's usage |
| `/usage --agent slide-conductor` | Usage filtered to a specific agent |
| `/usage --model claude-opus-4.6` | Usage filtered to a specific model |

**Session inspection:**

| Command | What it shows |
|---------|--------------|
| `/sessions` | Active and resumable sessions |
| `/sessions all` | All sessions, including ended ones |
| `/sessions <id>` | Detail view of a specific session |
| `/sessions <id> turn 3` | Content of a specific turn within a session |
| `/sessions <id> invocations` | Full trace of tool calls and subagent dispatches for that session |
| `/sessions name <id> <nick>` | Give a session a nickname for easy reference |
| `/sessions end <id>` | End a specific session |
| `/sessions cleanup` | Purge old sessions |

Sessions are **resumable by default**. Start a generation on Monday, come back Thursday, type `/resume`, and pick up with full context.
