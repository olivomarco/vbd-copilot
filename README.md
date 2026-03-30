# CSA-Copilot

> AI-powered engagement platform for Cloud Solution Architects — from meeting prep to production-ready Azure delivery

![CSA-Copilot](assets/screenshots/csa-copilot.png)

---

## What This Is

Customer meeting on Wednesday, and you need a 45-slide deck on a service you last touched three months ago. The official deck is two releases behind. Your demo scripts live in five different OneNote pages. You'll spend tonight copy-pasting from MS Learn and wrangling PowerPoint.

CSA-Copilot kills that cycle. It's a terminal-based AI platform built on the GitHub Copilot SDK with **four workflows** — each run by a conductor agent that orchestrates specialist subagents, asks for your approval at key stops, and runs QA checks before delivering output. 27 agents behind the scenes; you just type a prompt.

1. **Presentations** — Complete `.pptx` with speaker notes from a single prompt, researched against official sources
2. **Demos** — Step-by-step guides with runnable scripts, troubleshooting tables, and "say this" presenter cues
3. **AI Projects** — Blank page → production-ready Azure project: brainstorm → architecture → Bicep + app code + CI/CD + tests, with a 4-reviewer gate
4. **Hackathons** — What-The-Hack-style packages with progressive challenges, coach materials, and dev containers

> [!IMPORTANT]
> **Deep research, not instant generation.** A slide deck takes **~1 hour**, demos 30-45 min, AI projects 1 hour+. That replaces 4-8 hours of manual work. Kick it off and do something else.
>
> **Accelerator, not autopilot.** Output is a strong first draft with sourced claims and tested code. You own it, refine it, present it.

---

## A Day in the Life

| Situation | Prompt | Result |
|-----------|--------|--------|
| Manager wants a tech update | "Create a 15min L200 briefing on what's new in AKS" | 12-slide deck with speaker notes from MS Learn + devblogs |
| Customer meeting needs deep coverage | "1-hour L300 deck on GitHub Copilot extensions for financial services" | 30 slides with presenter transcripts, plan approval before build |
| You already have research notes | "Build a 30min L200 deck from notes/aks-security-review.md" | Deck built from your material, not web research |
| Demo day for a customer | "Create 3 L300 demos on Azure Container Apps" | Guide + companion scripts + troubleshooting tables + "say this" boxes |
| Pre-sales brainstorm | "@ai-brainstorming AI use cases for a healthcare company" | 10+ ranked ideas with impact scores, Azure services, phased roadmap |
| Architecture engagement | "@ai-solution-architect Design architecture for idea #3" | 5 docs: solution design, diagrams, cost estimation, delivery plan |
| Delivery kickoff | "@ai-implementor Implement the solution" | Bicep + app code + CI/CD + tests (80% coverage gate), 4-reviewer approval |
| Continue yesterday's work | `/resume` | Full context restored — sessions survive across days |
| Partner enablement event | "@hackathon-conductor Full-day L300 hackathon on Container Apps" | Challenges + solutions + dev container + coach materials, repo-ready |

---

## Workflows

### Presentations

The **Slide Conductor** researches official sources, presents a plan for your approval, builds slides with QA checks, and drops the `.pptx` + generator script into `outputs/slides/`. Also handles technical update briefings and slides from your own notes.

### Demos

The **Demo Conductor** produces a Markdown guide with runnable companion scripts → `outputs/demos/`. Each demo includes step-by-step instructions, "say this" presenter cues, a WOW moment, a troubleshooting table, and companion scripts.

### AI Projects — Idea to Production

Three conductor agents, each with mandatory quality gates:

| Stage | Agent | Output |
|-------|-------|--------|
| **Brainstorm** | `@ai-brainstorming` | 10+ ranked ideas with impact scores, Azure mappings, phased roadmap |
| **Architecture** | `@ai-solution-architect` | 5 docs: solution design, draw.io + ASCII diagrams, cost estimation, delivery plan |
| **Implementation** | `@ai-implementor` | Bicep infra + app code + CI/CD + tests (80% coverage gate). 4-reviewer approval required |

### Hackathon Events

The **Hackathon Conductor** creates What-The-Hack-style packages: progressive challenges, coach solutions, dev container for Codespaces, facilitation guide, and scoring rubric.

| Duration | Challenges | Spread |
|----------|-----------|--------|
| 2 hours | 3-4 | setup → easy → medium |
| 4 hours | 5-6 | setup → easy → medium → hard |
| 8 hours | 8-10 | setup → easy → medium → hard → expert |

---

## Sample Outputs

Raw, un-edited output — straight from the agents, so you know what to expect.

| | | | |
|:---:|:---:|:---:|:---:|
| ![Title slide](assets/screenshots/sample-slide-01.jpg) | ![Section slide](assets/screenshots/sample-slide-11.jpg) | ![Deep dive slide](assets/screenshots/sample-slide-12.jpg) | ![Architecture slide](assets/screenshots/sample-slide-22.jpg) |
| Title slide | Section | Technical deep dive | Architecture pattern |

*From: Microsoft Fabric - Trustworthy Data (L300, 2h)*

Browse the full output library: [slides](samples/slides/README.md) · [demos](samples/demos/README.md) · [hackathons](samples/hackathons/README.md) · [AI projects](samples/ai-projects/README.md)

---

## Architecture

**Routing.** `@agent-name` goes directly to that agent. Otherwise, a GPT-4.1 classifier picks the best match from all routable agent descriptions. No match → default Copilot agent handles it.

**Model selection.** Each agent has a preferred model (claude-sonnet-4.6 for slides/demos/implementation, claude-opus-4.6 for brainstorming/architecture). Override anytime with `/model`.

---

## Quality and Trust

Every output goes through multiple quality layers before delivery. See [docs/QUALITY.md](docs/QUALITY.md) for full details.

- **Official sources only** — research restricted to MS Learn, docs.github.com, github.blog, devblogs.microsoft.com, techcommunity.microsoft.com
- **Human approval stops** — plan approval before builds, output review before delivery
- **Automated QA checks** — PPTX, architecture, infra, pipeline, docs, and hackathon validators
- **Content humanization** — AI-tell detection with humanity scoring and automatic rewrites
- **4-reviewer gate** — code, infra, pipeline, docs reviewers must all APPROVE before AI project delivery
- **80% test coverage** — enforced via `pytest --cov` threshold

---

## Reference Tables

### Content Levels

| Level | Audience | Description |
|-------|----------|-------------|
| **L100** | Business / Executive | Value propositions, no code |
| **L200** | Technical decision makers | Architecture, key concepts |
| **L300** | Practitioners | Implementation, code samples, best practices |
| **L400** | Experts | Internals, performance, advanced patterns |

### Slide Durations

| Duration | Approx. slides |
|----------|---------------|
| 15 min | 10-14 |
| 30 min | 15-20 |
| 1 hour | 25-35 |
| 2 hours | 40-55 |
| 4 hours | 70-90 |

---

## Getting Started

### Prerequisites

- A **GitHub Copilot** subscription (Individual, Business, or Enterprise) with CLI access
- The [**GitHub CLI** (`gh`)](https://cli.github.com/) installed and authenticated (`gh auth login`)

### Quickstart (Docker)

```bash
git clone https://github.com/olivomarco/vbd-copilot.git
cd vbd-copilot
docker build -t csa-copilot .
docker run -it --rm \
  -e GITHUB_TOKEN=$(gh auth token) \
  -v "$(pwd)/outputs:/app/outputs" \
  csa-copilot
```

Other installation options (Copilot plugin, Codespaces, native): [docs/INSTALLATION.md](docs/INSTALLATION.md)

---

## Key Commands

| Command | Description |
|---------|-------------|
| `/new [agent]` | Start a new session |
| `/resume [id\|name]` | Resume a previous session |
| `/agent <name>` | Switch agent mid-session |
| `/agents` | List all available agents |
| `/model <id>` | Switch the LLM model |
| `/usage` | Token counts, cost, context window |
| `/sessions` | List and inspect sessions |
| `/debug` | Toggle debug mode |
| `/help` | Full command reference |

Full command reference and usage examples: [docs/USAGE.md](docs/USAGE.md)

---

## Responsible AI

Human-in-the-loop approval, official-sources-only research, no sensitive data in prompts, transparent first-draft output. Full policy: [docs/RESPONSIBLE-AI.md](docs/RESPONSIBLE-AI.md)
