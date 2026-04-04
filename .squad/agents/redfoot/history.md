# Project Context

- **Owner:** Marco Olivo
- **Project:** CSA-Copilot — AI-powered engagement platform for Cloud Solution Architects. Built on GitHub Copilot SDK with 4 workflows: presentations, demos, AI projects, hackathons. 27 agent definitions orchestrated by conductor agents.
- **Stack:** Python 3.11+, GitHub Copilot SDK (0.1.29), FastAPI, Rich, python-pptx, Electron/TypeScript frontend, YAML agent definitions
- **Key files:** frontend/ (Electron + React app), frontend/src/components/ (React components), frontend/src/pages/ (page views), vite.config.ts (build config), server.py (backend API)
- **Frontend:** React + TypeScript + Vite. Fluent UI icons (no emoji in UI). AgentIcon component for agent rendering. WebSocket for real-time backend communication.
- **Dependencies:** package.json in frontend/ — React, Fluent UI, Vite, TypeScript
- **Created:** 2026-04-03

## Learnings

<!-- Append new learnings below. Each entry is something lasting about the project. -->

## Deep Frontend Study — 2026-04-04

### Project Setup

- **Stack:** React 19 + TypeScript + Vite + Zustand (state) + Fluent UI (components) + Electron (desktop shell)
- **Build:** Vite dev server + Electron main process. Scripts in frontend/package.json.
- **Dependencies:** @fluentui/react-components, @fluentui/react-icons, zustand, react-router-dom, @microsoft/fetch-event-source, react-markdown, remark-gfm

### Component Architecture

- **Shell:** Layout wrapper with Sidebar + main content area
- **Sidebar:** Navigation, session list, agent status indicators
- **Pages:** 8 routes — Home, AgentWorkspace (live monitoring), OutputLibrary (file browser), SlideViewer (PPTX preview), Settings, Sessions, Usage, NewJob
- **BriefForm:** Modal for job creation — agent selection, topic input, content level, duration
- **AgentWorkspace:** Real-time job monitoring — event feed, tool calls, subagent spawns, phase indicators
- **OutputLibrary:** File browser for outputs/ directory — grouped by type, download support
- **SlideViewer:** PPTX preview with keyboard navigation through slides
- **AgentIcon:** Canonical icon renderer — maps 6 agent types to Fluent UI icons with branded colors. NEVER use emoji.

### State Management (Zustand)

- **jobStore:** Main store — persisted to localStorage with cross-tab sync via BroadcastChannel. Caps events at 2000. Tracks jobs, current job, events, phases.
- **settingsStore:** Theme preference (light/dark) + sidebar collapse state
- **outputStore:** Downloaded files cache for output previews

### API Layer

- Backend communicates via FastAPI (server.py) + WebSocket
- WebSocket in useWebSocket hook — streams job events (turn_started, tool_started/completed, phase_changed, waiting_for_input, user_response)
- REST: /sessions (CRUD), /usage, /outputs, /file (path-validated)
- Events flow: WebSocket → jobStore → component re-renders

### Electron Shell

- frontend/electron/ — main process, preload script, IPC channels
- Window management, native menus, app lifecycle
- Wraps the Vite dev server / built web app

### Key Conventions

- **NEVER use emoji in the UI** — always @fluentui/react-icons components
- AgentIcon component is the CANONICAL icon renderer for agents
- AGENT_META emoji field is legacy metadata only — never rendered
- Follow existing component patterns before introducing new ones
- Keep desktop app responsive — agent workflows can run for an hour
- WebSocket reconnection on disconnect
