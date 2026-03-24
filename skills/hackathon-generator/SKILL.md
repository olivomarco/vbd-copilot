---
name: hackathon-generator
description: Build What-The-Hack-style hackathon events with progressively harder challenges, coach materials, and dev containers. Use this skill when the user asks to create hackathons, challenge-based labs, or hands-on workshops for customers and partners.
---

# Hackathon Generator

Build professional What-The-Hack-style hackathon events for Microsoft Cloud Solution Architects and Solution Engineers to use with customers and partners.

## When to Use This Skill

Use this skill when the user:

- Says "create a hackathon", "build a hack", "hands-on workshop", or "challenge-based lab"
- Wants progressive challenge sets for customer or partner enablement
- Needs structured hackathon content with coach materials and participant guides

## Hackathon Package Structure

A complete hackathon package is a self-contained folder ready to be pushed as a Git repository:

```text
outputs/hackathons/{event-slug}/
  README.md                          # Landing page: topic, audience, prereqs, challenge table
  .devcontainer/
    devcontainer.json                # Codespaces-ready config
    Dockerfile                       # Topic-appropriate toolchain
  challenges/
    challenge-00.md                  # Setup and prerequisites (always present)
    challenge-01.md                  # First challenge (easiest)
    challenge-02.md                  # Progressive difficulty
    ...challenge-{N}.md
  coach/
    facilitation-guide.md            # Timing, pacing, tips per challenge
    scoring-rubric.md                # Evaluation criteria per challenge
  resources/
    reference-architecture.md        # Architecture overview for coaches
    starter/                         # Shared starter files (templates, data, configs)
```

## Challenge File Template

Each `challenges/challenge-{NN}.md` must follow this structure:

```markdown
# Challenge {NN}: {Title}

**Estimated Time:** {time} minutes
**Difficulty:** {Easy|Medium|Hard|Expert}

## Introduction

{Scenario-driven context. Set the scene. Explain WHY this matters
in a real-world context. Do NOT give step-by-step instructions here.}

## Prerequisites

- Challenge {NN-1} completed successfully
- {Any additional prerequisites}

## Description

{What the participant needs to accomplish. Describe the GOAL and the
CONSTRAINTS, not the exact steps. Students figure out the HOW.
Be specific about the expected end-state.}

## Success Criteria

- [ ] {Objectively verifiable check 1 - something a coach can confirm}
- [ ] {Objectively verifiable check 2}
- [ ] {Objectively verifiable check 3}

## Hints

<details>
<summary>Hint 1 (broad)</summary>
{General direction without giving away the answer}
</details>

<details>
<summary>Hint 2 (more specific)</summary>
{Narrower guidance pointing to the right service/command/concept}
</details>

<details>
<summary>Hint 3 (almost there)</summary>
{Very specific guidance, nearly the answer}
</details>

## Learning Resources

- [{Resource title}]({official MS Learn or docs URL})
- [{Resource title}]({official MS Learn or docs URL})

## Advanced Challenge (Optional)

{Stretch goal for teams that finish early. Open-ended, requires
deeper understanding or creative problem-solving.}
```

## Difficulty Curve Model

Challenges must follow a progressive difficulty curve:

- **Challenge 00**: Always setup and prerequisites (15-30 min). Install tools, configure access, verify environment.
- **Easy**: Guided, single-service, foundational concepts (20-30 min). One clear goal, one service, basic operations.
- **Medium**: Multi-step, configuration plus validation (30-45 min). Multiple operations, some decision-making, cross-service awareness.
- **Hard**: Multi-service integration, debugging, design choices (45-60 min). Connect services together, handle edge cases, troubleshoot.
- **Expert**: Open-ended design, optimization, advanced patterns (60-90 min). No single right answer, requires deep understanding, creative problem-solving.

## Duration to Challenge Count Mapping

| Duration | Challenges | Spread |
|----------|-----------|--------|
| 2 hours | 3-4 | setup + 2 easy + 1 medium |
| 4 hours | 5-6 | setup + 2 easy + 2 medium + 1 hard |
| 8 hours (full day) | 8-10 | setup + 2 easy + 3 medium + 2 hard + 1 expert |
| 16 hours (2 days) | 12-15 | setup + 3 easy + 4 medium + 3 hard + 2 expert |

## Content Levels

Content levels define the complexity ceiling of the challenge set:

| Level | Challenge Style | Tools and Techniques |
|-------|----------------|----------------------|
| L200 | Portal-guided, CLI commands, pre-built templates | Azure Portal, Azure CLI, ARM/Bicep templates provided, no code editing |
| L300 | Code modifications, SDK integration, multi-service wiring | SDK calls, configuration files, workflow definitions, moderate setup |
| L400 | Live coding, service internals, custom extensions | Custom code, performance tuning, advanced patterns, deep configuration |

## Writing Rules

- **Scenario-driven challenges**: Describe the GOAL, not the steps. Challenges are NOT tutorials. Students must figure out the approach. That is the learning.
- **Objectively verifiable success criteria**: Every criterion must be something a coach can check in under 2 minutes. "Deploy a container app" is verifiable. "Understand the concept" is not.
- **Progressive hints**: Start broad, get specific. Three hints per challenge minimum. Use collapsible sections.
- **No placeholder text**: No TODO, TBD, FIXME, INSERT, PLACEHOLDER, or lorem ipsum anywhere.
- **No emoji**: Use Unicode text symbols if decoration is needed.
- **No em-dashes**: Use hyphens.
- **Microsoft Azure mandate**: All services, tools, and patterns must use Azure/Microsoft technology.
- **Real URLs only**: Every link must point to an actual MS Learn, GitHub, or official Microsoft documentation page.
- **Challenge numbering**: Always use zero-padded two-digit numbers: challenge-00, challenge-01, ..., challenge-15. Never skip numbers.

## Dev Container Requirements

Every hackathon must include a `.devcontainer/` directory:

- `devcontainer.json` must specify: base image, VS Code extensions, post-create commands, forwarded ports
- `Dockerfile` must install all tools needed for the hackathon (Azure CLI, language SDKs, framework CLIs)
- The dev container must work with GitHub Codespaces out of the box
- Include a `postCreateCommand` that installs dependencies and verifies the environment

## Coach Materials

### Facilitation Guide (`coach/facilitation-guide.md`)

- Event overview and agenda with timing
- Per-challenge section: recommended time, coaching tips, what to watch for, common stuck points, pivot strategies
- Suggested break schedule
- How to handle teams that are ahead or behind

### Scoring Rubric (`coach/scoring-rubric.md`)

- Per-challenge evaluation: Done / Partially Done / Not Done
- Specific verification commands or checks for each criterion
- Bonus points for advanced challenges
- Overall scoring scale

## QA Checks

The `hackathon_qa_checks.py` script validates hackathon packages for:

- Sequential challenge numbering from 00
- Required sections in each challenge (Introduction, Description, Success Criteria, Learning Resources)
- Coach materials exist and have required sections
- Dev container configuration is valid JSON
- Top-level README.md has required sections
- No placeholder text, emoji, or em-dashes
- Internal cross-references between challenges are valid
