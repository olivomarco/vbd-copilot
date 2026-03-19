---
applyTo: "cli/**"
---

# GitHub Copilot SDK — Deep-Dive Research Report

## Executive Summary

The [GitHub Copilot SDK](https://github.com/github/copilot-sdk) is an open-source (MIT-licensed), multi-language SDK that exposes the same agentic engine behind the Copilot CLI as a **programmable runtime** for TypeScript/Node.js, Python, Go, and .NET. Currently in **Technical Preview** (v0.1.x), it communicates with the Copilot CLI in server mode via **JSON-RPC** (protocol v3), enabling applications to programmatically drive Copilot's planning, tool invocation, file editing, and multi-turn conversation capabilities[^1]. The SDK supports GitHub Copilot authentication, OAuth app tokens, environment variables, and BYOK (Bring Your Own Key) for providers like OpenAI, Azure AI Foundry, Anthropic, and Ollama[^2]. Key features include custom tool definition, hooks for intercepting agent behavior, MCP server integration, custom sub-agent orchestration, streaming events (40+ event types), session persistence, and OpenTelemetry instrumentation[^3].

---

## Architecture Overview

```text
┌─────────────────────────────────────────────────────┐
│                  Your Application                    │
│  ┌───────────┐  ┌───────────┐  ┌──────────────────┐│
│  │Custom Tools│  │   Hooks   │  │ Custom Agents    ││
│  └─────┬─────┘  └─────┬─────┘  └───────┬──────────┘│
│        │               │                │            │
│  ┌─────▼───────────────▼────────────────▼──────────┐│
│  │              SDK Client (CopilotClient)          ││
│  │  • Session management    • Tool registration     ││
│  │  • Permission handling   • Event streaming       ││
│  │  • Telemetry config      • Model selection       ││
│  └──────────────────────┬───────────────────────────┘│
└─────────────────────────┼────────────────────────────┘
                          │ JSON-RPC (stdio or TCP)
                          │ Protocol v3
┌─────────────────────────▼────────────────────────────┐
│            Copilot CLI (Server Mode)                  │
│  • Agent runtime & planning                          │
│  • Built-in tools (grep, edit_file, read_file, etc.) │
│  • MCP server management                            │
│  • Model routing                                     │
│  ┌───────────────────────────────────────────────────┐│
│  │  ☁️ GitHub Copilot API / BYOK Model Provider      ││
│  └───────────────────────────────────────────────────┘│
└───────────────────────────────────────────────────────┘
```

The SDK follows a **client → server** architecture where the SDK client (in your app process) communicates with the Copilot CLI via JSON-RPC[^1]. Two connection modes are supported:

1. **Auto-managed (stdio):** The SDK spawns the CLI as a child process, communicating over stdin/stdout. This is the default for local development[^4].
2. **External server (TCP):** The CLI runs independently in headless mode (`copilot --headless --port 4321`), and the SDK connects via `cliUrl`. This is the recommended pattern for backend services, enabling multiple SDK clients to share one CLI server[^5].

The current SDK protocol version is **v3**, stored in `/sdk-protocol-version.json`[^6]. The SDK also supports backward compatibility with v2 CLI servers as of v0.1.32[^7].

---

## SDK Implementations

### Repository Structure

| Directory          | Purpose                       | Key Files                                                                         |
| ------------------ | ----------------------------- | --------------------------------------------------------------------------------- |
| `nodejs/`          | TypeScript/Node.js SDK        | `src/client.ts`, `src/session.ts`, `src/types.ts`, `src/index.ts`                 |
| `python/`          | Python SDK                    | `copilot/client.py`, `copilot/session.py`, `copilot/tools.py`, `copilot/types.py` |
| `go/`              | Go SDK                        | `client.go`, `session.go`, `definetool.go`, `types.go`                            |
| `dotnet/`          | .NET SDK                      | `src/Client.cs`, `src/Session.cs`, `src/Types.cs`                                 |
| `docs/`            | Cross-language documentation  | Getting started, auth, features, hooks, troubleshooting                           |
| `scripts/codegen/` | Code generation tooling       | Shared schema → language-specific type generation                                 |
| `test/`            | Cross-language test scenarios | Integration/E2E scenario tests                                                    |

### Package Distribution

| SDK                | Package Name                       | Install Command                           | Current Version |
| ------------------ | ---------------------------------- | ----------------------------------------- | --------------- |
| Node.js/TypeScript | `@github/copilot-sdk`              | `npm install @github/copilot-sdk`         | 0.1.8[^8]       |
| Python             | `github-copilot-sdk`               | `pip install github-copilot-sdk`          | 0.1.0[^9]       |
| Go                 | `github.com/github/copilot-sdk/go` | `go get github.com/github/copilot-sdk/go` | module v0[^10]  |
| .NET               | `GitHub.Copilot.SDK`               | `dotnet add package GitHub.Copilot.SDK`   | (NuGet)[^1]     |

---

## Node.js / TypeScript SDK

### Public API Surface

The Node.js SDK exports from `nodejs/src/index.ts`[^11]:

- **`CopilotClient`** — Main client class; manages CLI process lifecycle, session creation/resumption, and global configuration.
- **`CopilotSession`** — Represents a conversation session; handles sending messages, streaming events, tool registration, and permission handling.
- **`defineTool()`** — Helper to define custom tools with Zod schema validation.
- **`approveAll`** — A convenience permission handler that auto-approves all tool calls.

Key exported types include `SessionConfig`, `ResumeSessionConfig`, `SessionEvent`, `PermissionHandler`, `PermissionRequest`, `Tool`, `ToolHandler`, `MCPServerConfig`, `CustomAgentConfig`, `TelemetryConfig`, and many more[^11].

### Dependencies

The Node.js SDK has minimal runtime dependencies[^8]:

- `@github/copilot` (v1.0.4+) — Copilot CLI integration
- `vscode-jsonrpc` (v8.2.1+) — JSON-RPC protocol implementation
- `zod` (v4.3.6+) — Runtime type validation for tool parameters

### Source Architecture

The implementation is split across:

- **`client.ts`** (~60KB) — Client lifecycle, CLI process management, session CRUD, auth handling[^12]
- **`session.ts`** (~28KB) — Session state machine, event dispatching, message sending, hook execution[^13]
- **`types.ts`** (~32KB) — All type definitions, `defineTool()` implementation, schema helpers[^14]
- **`generated/`** — Auto-generated types from the codegen pipeline[^15]
- **`extension.ts`** — Extension module for integrating with VS Code-like hosts[^16]

### Usage Example

```typescript
import { CopilotClient, defineTool, approveAll } from "@github/copilot-sdk";

const client = new CopilotClient();
const session = await client.createSession({
  tools: [
    defineTool("get_weather", {
      description: "Get weather for a city",
      schema: z.object({ city: z.string() }),
      handler: async (params) => `Weather in ${params.city}: 22°C`,
    }),
  ],
  onPermissionRequest: approveAll,
});

session.on("assistant.message", (event) => {
  console.log(event.data.content);
});

await session.sendAndWait({ prompt: "What's the weather in Seattle?" });
await client.stop();
```

---

## Python SDK

### Public API Surface

The Python SDK exports from `python/copilot/__init__.py`[^17]:

- **`CopilotClient`** — Async client for managing CLI process and sessions.
- **`CopilotSession`** — Session management with event-driven API.
- **`define_tool()`** — Decorator/function-based tool definition with Pydantic model schema generation.

### Dependencies

Minimal runtime dependencies (from `pyproject.toml`)[^9]:

- `python-dateutil` (v2.9.0+)
- `pydantic` (v2.0+)
- Optional: `opentelemetry-api` (v1.0+) for telemetry

Requires Python 3.11+[^9].

### Tool Definition System

The Python SDK has a particularly elegant tool definition API using decorators and Pydantic models (`python/copilot/tools.py`)[^18]:

```python
from pydantic import BaseModel, Field
from copilot import define_tool

class LookupIssueParams(BaseModel):
    id: str = Field(description="Issue identifier")

@define_tool(description="Fetch issue details")
def lookup_issue(params: LookupIssueParams) -> str:
    return fetch_issue(params.id).summary
```

The decorator inspects function signatures via `inspect` and `get_type_hints()` to automatically detect whether the handler takes params, a `ToolInvocation`, both, or neither[^18]. Schema is auto-generated from Pydantic models via `model_json_schema()`[^18]. Error handling wraps exceptions into a `ToolResult` with `result_type="failure"`, deliberately hiding detailed error info from the LLM for security[^18].

### Source Architecture

- **`client.py`** (~64KB) — Full client implementation with async subprocess management[^19]
- **`session.py`** (~29KB) — Session lifecycle, event streaming, message handling[^20]
- **`jsonrpc.py`** (~14KB) — Custom JSON-RPC implementation over stdio/TCP[^21]
- **`tools.py`** (~7KB) — Tool definition with Pydantic schema generation[^18]
- **`types.py`** (~38KB) — Type definitions using Pydantic and dataclasses[^22]
- **`generated/`** — Auto-generated types[^23]

---

## Go SDK

### Public API Surface

The Go SDK is a single package `copilot` under `go/`[^24]:

- **`NewClient(opts)`** / **`Client.Start(ctx)`** / **`Client.Stop()`** — Client lifecycle[^24]
- **`Client.CreateSession(ctx, config)`** / **`Client.ResumeSession(ctx, id, config)`** — Session management[^25]
- **`Session.Send(ctx, opts)`** / **`Session.SendAndWait(ctx, opts)`** — Message sending[^25]
- **`DefineTool[T, U](name, desc, handler)`** — Generic typed tool definition[^26]

### Tool Definition with Generics

The Go SDK uses Go generics for type-safe tool definitions (`go/definetool.go`)[^26]:

```go
type GetWeatherParams struct {
    City string `json:"city" jsonschema:"city name"`
    Unit string `json:"unit" jsonschema:"temperature unit"`
}

tool := copilot.DefineTool("get_weather", "Get weather for a city",
    func(params GetWeatherParams, inv copilot.ToolInvocation) (any, error) {
        return fmt.Sprintf("Weather in %s: 22°%s", params.City, params.Unit), nil
    })
```

The generic `DefineTool[T, U]` function uses `google/jsonschema-go` for automatic JSON schema generation from Go struct tags and the `jsonschema` tag[^26]. The handler receives typed params (automatically unmarshaled via JSON round-trip) and returns any value—strings pass through directly, other types are JSON-serialized[^26].

### Dependencies

From `go/go.mod`[^10]:

- `google/jsonschema-go` (v0.4.2) — JSON Schema generation
- `klauspost/compress` (v1.18.3) — Compression
- `google/uuid` (v1.6.0) — UUID generation
- `go.opentelemetry.io/otel` (v1.35.0) — OpenTelemetry tracing

### Source Architecture

- **`client.go`** (~48KB) — Client lifecycle, CLI process management, JSON-RPC transport[^24]
- **`session.go`** (~26KB) — Session state, event dispatch, message sending[^25]
- **`types.go`** (~39KB) — All type definitions[^27]
- **`definetool.go`** (~4KB) — Generic tool definition with schema generation[^26]
- **`generated_session_events.go`** (~61KB) — Auto-generated event types[^28]
- **`permissions.go`** — Permission handler types[^29]
- **`telemetry.go`** — OpenTelemetry integration[^30]
- **`rpc/`** — RPC method definitions[^31]
- **`internal/`** — Internal JSON-RPC implementation[^32]
- **`embeddedcli/`** — Embedded CLI binary support[^33]

---

## .NET SDK

### Public API Surface

The .NET SDK namespace is `GitHub.Copilot.SDK`[^34]:

- **`CopilotClient`** — Implements `IAsyncDisposable`; manages CLI and sessions[^35]
- **`Session`** — Session with event-based API using C# events (`OnEvent`, `OnPermissionRequest`, etc.)[^36]
- **`PermissionHandlers`** — Static helper class with `ApproveAll` and other pre-built handlers[^37]
- Integrates with **Microsoft.Extensions.AI** `AIFunctionFactory` for tool definition[^38]

### Dependencies

From `GitHub.Copilot.SDK.csproj`[^34]:

- Targets `net8.0` and `net9.0`
- Uses `System.Text.Json` for serialization
- `Microsoft.Extensions.AI.Abstractions` for AI function integration

### Source Architecture

- **`Client.cs`** (~70KB) — Full client implementation[^35]
- **`Session.cs`** (~36KB) — Session lifecycle with C# event delegates[^36]
- **`Types.cs`** (~70KB) — All type definitions[^38]
- **`PermissionHandlers.cs`** — Pre-built permission handlers[^37]
- **`Telemetry.cs`** — OpenTelemetry integration[^39]
- **`Generated/`** — Auto-generated types from codegen[^40]

---

## Code Generation Pipeline

All four SDKs share a **common code generation pipeline** located in `scripts/codegen/`[^41]. The pipeline generates:

- Session event types (e.g., `generated_session_events.go`, `nodejs/src/generated/`, `python/copilot/generated/`, `dotnet/src/Generated/`)
- RPC method stubs
- Type definitions from a shared schema

This ensures cross-language parity for the 40+ streaming event types and RPC interfaces. The SDK protocol version is centralized in `/sdk-protocol-version.json` (currently v3)[^6] and propagated to each SDK via language-specific version files[^42].

---

## Key Features

### 1. Custom Tools

All SDKs support defining custom tools that the Copilot agent can invoke during conversations. Each SDK provides an idiomatic API:

| SDK        | API                                                    | Schema Source                       |
| ---------- | ------------------------------------------------------ | ----------------------------------- |
| TypeScript | `defineTool(name, { schema: z.object(...), handler })` | Zod schemas[^14]                    |
| Python     | `@define_tool(description=...)` decorator              | Pydantic models[^18]                |
| Go         | `DefineTool[T, U](name, desc, handler)` generics       | Go struct tags + jsonschema-go[^26] |
| .NET       | `AIFunctionFactory.Create(handler, name, desc)`        | Microsoft.Extensions.AI[^38]        |

Tools can override built-in tools (v0.1.30+) by setting `overridesBuiltInTool: true`[^43].

### 2. Hooks System

Hooks intercept and customize session behavior at every stage[^44]:

| Hook                      | Purpose                                              |
| ------------------------- | ---------------------------------------------------- |
| **Pre-Tool Use**          | Approve, deny, or modify tool calls before execution |
| **Post-Tool Use**         | Transform tool results before returning to the LLM   |
| **User Prompt Submitted** | Modify or filter user messages                       |
| **Session Lifecycle**     | React to session start/end                           |
| **Error Handling**        | Custom error recovery                                |

### 3. Custom Agents / Sub-Agent Orchestration

Define specialized sub-agents with scoped tools and system prompts. The Copilot runtime automatically routes requests to the appropriate agent based on expertise[^45]:

```typescript
const session = await client.createSession({
  customAgents: [
    { name: "researcher", prompt: "You are a research assistant.", tools: [searchTool] },
    { name: "editor", prompt: "You are a code editor.", tools: [editTool] },
  ],
  agent: "researcher", // Pre-select active agent (v0.1.33+)
});
```

### 4. MCP Server Integration

The SDK integrates with Model Context Protocol servers for external tool access[^46]:

- **Local/Stdio servers** — Runs as subprocess, communicates via stdin/stdout
- **HTTP/SSE servers** — Remote servers accessed via HTTP

Supports the official MCP ecosystem including `@modelcontextprotocol/server-filesystem`, `@modelcontextprotocol/server-github`, etc.[^46]

### 5. Streaming Events

With `streaming: true`, the SDK emits 40+ real-time event types including[^47]:

- `assistant.message` — Model-generated text
- `tool.call` / `tool.result` — Tool execution lifecycle
- `permission.requested` / `permission.completed` — Permission flow
- `session.idle` — Session ready for next input
- `system.notification` — System-level notifications (v0.1.33+)

### 6. Session Persistence & Lifecycle

Sessions can be resumed across client reconnections using `client.resume_session(session_id)`[^48].

**`session.destroy()` vs detaching:**

- **`session.destroy()`** sends `session.destroy` RPC to the CLI server, which **permanently deletes** server-side session state (conversation history, context). After this, `client.resume_session(session_id)` will fail with "Session not found".
- **To keep a session resumable**, do NOT call `destroy()`. Instead, just clear the local event handlers (`session._event_handlers.clear()`) and stop referencing the session object. The server retains the session state until `client.stop()` shuts down the CLI process.
- **Server-side sessions do not survive CLI process restarts** (stdio mode). When the CLI process exits (via `client.stop()` or crash), all sessions are lost. Only the application's own persistence (e.g. SQLite) survives.
- **Use `destroy()` only when** you want to permanently kill a session (e.g. explicit user action like `/sessions end`).

| Action | Server-side state | Can resume? |
|--------|------------------|-------------|
| Detach handlers only | Preserved | Yes |
| `session.destroy()` | Deleted | No |
| CLI process restart | Lost | No |

### 7. BYOK (Bring Your Own Key)

Bypass GitHub Copilot authentication entirely by providing your own API keys[^2]:

| Provider                  | Type Value              |
| ------------------------- | ----------------------- |
| OpenAI                    | `"openai"`              |
| Azure OpenAI / AI Foundry | `"azure"`               |
| Anthropic                 | `"anthropic"`           |
| Ollama                    | `"openai"` (compatible) |
| Microsoft Foundry Local   | `"openai"` (compatible) |

BYOK supports `wireApi` configuration for choosing between Chat Completions API and the newer Responses API format[^2].

### 8. OpenTelemetry Instrumentation

Built-in support for configuring OpenTelemetry on the CLI process with W3C Trace Context propagation between SDK and CLI[^49]. All four SDKs support `TelemetryConfig` in client options.

### 9. Multi-Client Tool Broadcasting (Protocol v3)

As of v0.1.31, the SDK uses protocol v3 where the runtime broadcasts `external_tool.requested` and `permission.requested` as session events to all connected clients. This enables architectures where different clients contribute different tools to the same session[^50].

---

## Authentication

The SDK supports a priority-ordered authentication chain[^51]:

1. **Explicit `githubToken`** — Token passed directly to SDK constructor
2. **HMAC key** — `CAPI_HMAC_KEY` or `COPILOT_HMAC_KEY` env vars
3. **Direct API token** — `GITHUB_COPILOT_API_TOKEN` with `COPILOT_API_URL`
4. **Environment variable tokens** — `COPILOT_GITHUB_TOKEN` → `GH_TOKEN` → `GITHUB_TOKEN`
5. **Stored OAuth credentials** — From previous `copilot` CLI login
6. **GitHub CLI** — `gh auth` credentials
7. **BYOK** — No GitHub auth required

Supported token types: `gho_` (OAuth), `ghu_` (GitHub App), `github_pat_` (fine-grained PAT). Classic PATs (`ghp_`) are not supported[^51].

---

## Deployment Patterns

### Local Development (Auto-Managed CLI)

```text
SDK Client ──(stdio)──▶ CLI Process (child)
```

The SDK spawns the CLI automatically. Simplest setup[^4].

### Backend Services (External CLI Server)

```text
┌─────────────┐         ┌──────────────────┐
│ API Server  │──TCP──▶ │ Copilot CLI      │
│ (SDK Client)│  :4321  │ (--headless mode)│
└─────────────┘         └──────────────────┘
```

CLI runs as a persistent server. Multiple SDK clients can share one CLI. Docker Compose and systemd deployment examples are documented[^5].

### Scaling / Multi-Tenancy

Multiple API instances can connect to the same CLI server. Per-user tokens can be passed at session creation time for multi-tenant scenarios[^5].

---

## Development & Testing

The repository uses **`just`** (justfile) as the task runner across all languages[^52]:

| Command               | Description                               |
| --------------------- | ----------------------------------------- |
| `just test`           | Run tests for all languages               |
| `just lint`           | Lint all code                             |
| `just format`         | Format all code                           |
| `just install`        | Install all dependencies                  |
| `just validate-docs`  | Validate documentation code examples      |
| `just scenario-build` | Build all cross-language scenario samples |

Each SDK has its own test suite:

- **Node.js:** Vitest (`npm test`)[^8]
- **Python:** pytest with pytest-asyncio[^9]
- **Go:** `go test ./...`[^52]
- **.NET:** `dotnet test`[^52]

Documentation code examples are **automatically validated** via `scripts/docs-validation/` which extracts code blocks and compiles/checks them[^52].

---

## Release History (Recent)

| Version           | Date       | Highlights                                                                                            |
| ----------------- | ---------- | ----------------------------------------------------------------------------------------------------- |
| v0.1.33-preview.0 | 2026-03-12 | Pre-select custom agent at session creation; custom model listing for BYOK; system notifications[^53] |
| v0.1.32           | 2026-03-07 | Backward compatibility with v2 CLI servers[^7]                                                        |
| v0.1.31           | 2026-03-07 | Protocol v3 multi-client tool broadcasts; typed `PermissionRequestResultKind`[^50]                    |
| v0.1.30           | 2026-03-03 | Override built-in tools; `session.setModel()` convenience API[^43]                                    |
| v0.1.29           | 2026-02-27 | Python `CopilotClient.stop()` raises `ExceptionGroup`[^54]                                            |

---

## Community SDKs

Unofficial, community-maintained SDKs exist for additional languages[^1]:

| SDK     | Repository                                                                                                |
| ------- | --------------------------------------------------------------------------------------------------------- |
| Java    | [copilot-community-sdk/copilot-sdk-java](https://github.com/copilot-community-sdk/copilot-sdk-java)       |
| Rust    | [copilot-community-sdk/copilot-sdk-rust](https://github.com/copilot-community-sdk/copilot-sdk-rust)       |
| Clojure | [copilot-community-sdk/copilot-sdk-clojure](https://github.com/copilot-community-sdk/copilot-sdk-clojure) |
| C++     | [0xeb/copilot-sdk-cpp](https://github.com/0xeb/copilot-sdk-cpp)                                           |

---

## Key Repositories Summary

| Repository                                                          | Purpose                                      | Key Files                                              |
| ------------------------------------------------------------------- | -------------------------------------------- | ------------------------------------------------------ |
| [github/copilot-sdk](https://github.com/github/copilot-sdk)         | Main SDK mono-repo (4 languages)             | `nodejs/src/`, `python/copilot/`, `go/`, `dotnet/src/` |
| [github/awesome-copilot](https://github.com/github/awesome-copilot) | Cookbooks, instructions, community resources | `cookbook/copilot-sdk/`, `instructions/`               |

---

## Confidence Assessment

| Aspect                                    | Confidence | Notes                                                            |
| ----------------------------------------- | ---------- | ---------------------------------------------------------------- |
| Architecture (JSON-RPC, CLI server mode)  | **High**   | Verified from README, docs, and source code                      |
| Public API surface (all 4 SDKs)           | **High**   | Verified from `index.ts`, `__init__.py`, Go exports, .NET source |
| Tool definition patterns                  | **High**   | Source code for `defineTool` verified in all languages           |
| Authentication methods                    | **High**   | Comprehensive auth docs verified                                 |
| BYOK provider support                     | **High**   | Detailed BYOK docs with code examples verified                   |
| Feature completeness (hooks, MCP, agents) | **High**   | Feature docs and source verified                                 |
| Internal CLI implementation               | **Medium** | CLI is a separate closed-source binary; SDK wraps it             |
| Production readiness                      | **Medium** | Explicitly labeled "Technical Preview"                           |
| Performance characteristics               | **Low**    | No benchmarks or performance docs found in repo                  |

---

## Footnotes

[^1]: [github/copilot-sdk `README.md`](https://github.com/github/copilot-sdk/blob/main/README.md)

[^2]: [github/copilot-sdk `docs/auth/byok.md`](https://github.com/github/copilot-sdk/blob/main/docs/auth/byok.md)

[^3]: [github/copilot-sdk `docs/features/index.md`](https://github.com/github/copilot-sdk/blob/main/docs/features/index.md)

[^4]: [github/copilot-sdk `docs/getting-started.md`](https://github.com/github/copilot-sdk/blob/main/docs/getting-started.md)

[^5]: [github/copilot-sdk `docs/setup/backend-services.md`](https://github.com/github/copilot-sdk/blob/main/docs/setup/backend-services.md)

[^6]: `sdk-protocol-version.json` — `{"version": 3}`

[^7]: [github/copilot-sdk release v0.1.32](https://github.com/github/copilot-sdk/releases/tag/v0.1.32) — PR [#706](https://github.com/github/copilot-sdk/pull/706)

[^8]: `nodejs/package.json` — `@github/copilot-sdk` v0.1.8

[^9]: `python/pyproject.toml` — `github-copilot-sdk` v0.1.0, Python 3.11+

[^10]: `go/go.mod` — `github.com/github/copilot-sdk/go`, Go 1.24

[^11]: `nodejs/src/index.ts`

[^12]: `nodejs/src/client.ts` (~60KB)

[^13]: `nodejs/src/session.ts` (~28KB)

[^14]: `nodejs/src/types.ts` (~32KB)

[^15]: `nodejs/src/generated/`

[^16]: `nodejs/src/extension.ts`

[^17]: `python/copilot/__init__.py`

[^18]: `python/copilot/tools.py`

[^19]: `python/copilot/client.py` (~64KB)

[^20]: `python/copilot/session.py` (~29KB)

[^21]: `python/copilot/jsonrpc.py` (~14KB)

[^22]: `python/copilot/types.py` (~38KB)

[^23]: `python/copilot/generated/`

[^24]: `go/client.go` (~48KB)

[^25]: `go/session.go` (~26KB)

[^26]: `go/definetool.go`

[^27]: `go/types.go` (~39KB)

[^28]: `go/generated_session_events.go` (~61KB)

[^29]: `go/permissions.go`

[^30]: `go/telemetry.go`

[^31]: `go/rpc/`

[^32]: `go/internal/`

[^33]: `go/embeddedcli/`

[^34]: `dotnet/src/GitHub.Copilot.SDK.csproj`

[^35]: `dotnet/src/Client.cs` (~70KB)

[^36]: `dotnet/src/Session.cs` (~36KB)

[^37]: `dotnet/src/PermissionHandlers.cs`

[^38]: `dotnet/src/Types.cs` (~70KB)

[^39]: `dotnet/src/Telemetry.cs`

[^40]: `dotnet/src/Generated/`

[^41]: `scripts/codegen/`

[^42]: `nodejs/src/sdkProtocolVersion.ts`, `python/copilot/sdk_protocol_version.py`, `go/sdk_protocol_version.go`, `dotnet/src/SdkProtocolVersion.cs`

[^43]: [github/copilot-sdk release v0.1.30](https://github.com/github/copilot-sdk/releases/tag/v0.1.30) — PR [#636](https://github.com/github/copilot-sdk/pull/636)

[^44]: [github/copilot-sdk `docs/features/hooks.md`](https://github.com/github/copilot-sdk/blob/main/docs/features/hooks.md)

[^45]: [github/copilot-sdk `docs/features/custom-agents.md`](https://github.com/github/copilot-sdk/blob/main/docs/features/custom-agents.md)

[^46]: [github/copilot-sdk `docs/features/mcp.md`](https://github.com/github/copilot-sdk/blob/main/docs/features/mcp.md)

[^47]: [github/copilot-sdk `docs/features/streaming-events.md`](https://github.com/github/copilot-sdk/blob/main/docs/features/streaming-events.md)

[^48]: [github/copilot-sdk `docs/features/session-persistence.md`](https://github.com/github/copilot-sdk/blob/main/docs/features/session-persistence.md)

[^49]: [github/copilot-sdk `docs/observability/opentelemetry.md`](https://github.com/github/copilot-sdk/blob/main/docs/observability/opentelemetry.md)

[^50]: [github/copilot-sdk `CHANGELOG.md` — v0.1.31](https://github.com/github/copilot-sdk/blob/main/CHANGELOG.md) — PR [#686](https://github.com/github/copilot-sdk/pull/686)

[^51]: [github/copilot-sdk `docs/auth/index.md`](https://github.com/github/copilot-sdk/blob/main/docs/auth/index.md)

[^52]: `justfile` — cross-language task runner

[^53]: [github/copilot-sdk release v0.1.33-preview.0](https://github.com/github/copilot-sdk/releases/tag/v0.1.33-preview.0)

[^54]: [github/copilot-sdk release v0.1.29](https://github.com/github/copilot-sdk/releases/tag/v0.1.29) — PR [#603](https://github.com/github/copilot-sdk/pull/603)
