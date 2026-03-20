---
name: demo-generator
description: Build demo guides with companion scripts for live technical demonstrations. Use this skill when the user asks to create demos, walkthroughs, hands-on labs, or demo packages for customer sessions. Also use when the user says "create a demo", "build a walkthrough", "demo guide", or "companion scripts".
---

# Demo Generator

Build professional demo guides with companion scripts for live technical demonstrations targeting Microsoft Cloud Solution Architects and Solution Engineers.

## When to Use This Skill

Use this skill when the user:
- Says "create a demo", "build a walkthrough", "demo guide", or "hands-on lab"
- Wants to create demo packages with guides and companion scripts
- Needs structured demo content for customer sessions

## Demo Package Structure

A complete demo package consists of:
1. **Main demo guide** (`.md`) - the presenter's script with step-by-step instructions
2. **Companion scripts** - runnable scripts (`.sh`, `.py`, `.ps1`, etc.) that accompany the demo

## Guide Fragment Structure

Each demo section in the guide must include:
- `## Demo {N}: {title}` heading
- WOW moment callout (the "aha" moment for the audience)
- Prerequisites specific to this demo
- Numbered steps with 'Say this' boxes (presenter narrative)
- Troubleshooting table (at least 3 known issues)
- Transition bridge sentence (connection to the next demo)

## Writing Principles

- Write the narrative first - every step has a 'Say this' box
- Customer-centric language - connect steps to business outcomes
- WOW moment emphasis - mark highlights with a star
- No emoji - use Unicode text symbols
- No invented URLs - every link must be real and verified
- No em-dashes - use hyphens

## Companion File Rules

- Always include header comments with usage and prerequisites
- Parameterize environment-specific values with env vars
- Add echo statements readable at font size 18+
- Include error handling and cleanup commands (commented out)
- Scripts must be fully self-contained and runnable

## Content Levels

| Level | Time per Demo | Complexity |
|-------|--------------|------------|
| L200  | ~10 min      | CLI commands, clicks, pre-built samples, no code editing |
| L300  | ~15 min      | Code mods, SDK calls, workflow configs, moderate setup |
| L400  | ~20-30 min   | Live coding, internals, custom extensions, advanced configs |

## QA Checks

The `demo_qa_checks.py` script validates demo packages for:
- Placeholder text (TODO, FIXME, xxx, TBD)
- Emoji usage (prohibited)
- Em-dash usage (prohibited)
- Script syntax (bash -n / py_compile)
- File cross-references (scripts referenced in guide must exist)
- Guide structure (required sections present)
- Demo count vs. expected
