# GitHub Copilot SDK: Common pitfalls and gotchas

You are using [GitHub Copilot SDK](https://github.com/github/copilot-sdk) to build a Python app, multi-agent.
These are common pitfalls, gotchas, and non-obvious behaviors to be aware of.

## Permission handler errors are silently swallowed

If your `on_permission_request` handler throws (bad import, DB timeout, typo), the SDK catches it with a bare `except Exception` and returns a **silent denial**. No log, no warning. The model just sees every action denied. You'll spend hours debugging "why won't it use tools" when the real issue is a crashed handler.

## `on_permission_request` is mandatory

`create_session` raises `ValueError` if you don't provide it. The error message suggests `approve_all`, which approves **all** shell commands, file writes, and URL fetches. Never use `approve_all` in production.

## Tool handler errors are hidden from the LLM

When your tool handler throws, the SDK sends the model: _"Invoking this tool produced an error. Detailed information is not available."_ The actual error goes to `result.error` for your logs, but the model **cannot self-correct**. If you want intelligent retries, catch errors inside the handler and return a descriptive failure string instead of raising.

## `TypedDict` configs silently ignore typos

`SessionConfig`, `CopilotClientOptions`, etc. are `TypedDict` with `total=False`. If you write `on_permision_request` (missing 's'), Python won't warn you — the key is silently ignored and you get a `ValueError` about the missing required handler.

## Synchronous tool handlers block the entire event loop

`@define_tool` wraps your function in async, but if the function is synchronous and does blocking I/O (e.g., `urllib.request.urlopen`), it freezes **every session on that client**. Use `asyncio.to_thread()` for blocking work, or use `aiohttp`/`httpx` for async network calls.

## `stop()` raises `ExceptionGroup`, not a single exception

A bare `except Exception` won't catch it. You need `except*` syntax (Python 3.11+) or the `exceptiongroup` backport to handle individual `StopError`s from `client.stop()`.

## `destroy()` does not delete session data from disk

`destroy()` removes in-memory state only. The session remains at `~/.copilot/session-state/{sessionId}` and can be resumed. To permanently delete, call `delete_session()`. Calling `destroy()` for cleanup accumulates disk state forever.

## Infinite sessions are on by default

Context compaction triggers automatically at 80% context utilization (blocking at 95%). Session state persists to disk. Disable with `infinite_session={"enabled": False}`.

## `send_and_wait` timeout doesn't abort server-side work

The 60-second default controls how long the SDK waits. It does **not** cancel the agent's work on the server. The agent keeps running and burning tokens after your timeout fires. For multi-step tasks (research → write → review), 60s is almost certainly too short. Pass `timeout=` explicitly.

## `available_tools` silently overrides `excluded_tools`

If you set both, `excluded_tools` is completely ignored — no warning, no error. Only set one.

## `system_message` replace mode removes ALL security guardrails

Setting `mode: "replace"` replaces the **entire** system prompt, including security restrictions. No warning. Prefer `mode: "append"`.

## Hook errors are silently swallowed

If `on_pre_tool_use`, `on_post_tool_use`, or `on_error_occurred` throws, the session continues as if no hook existed. The exception is caught and discarded. A crashed security-policy hook silently downgrades to "no policy."

## Event handler errors are printed and discarded

If a callback registered via `session.on()` throws, the SDK catches it, prints with `print()`, and continues. Remaining handlers still execute. Don't rely on handler crashes to halt your program.

## `@define_tool` auto-detects handler signature — wrong type hints silently change behavior

- First param is a Pydantic `BaseModel` subclass → SDK parses and validates args into that model.
- First param is `ToolInvocation` → SDK assumes no params and passes the invocation object.
- Anything else → you get a raw `dict`.

Wrong type hints silently change which calling convention is used. No error, just different behavior.

## Returning `None` from `@define_tool` is an empty string success

A handler that forgets to return a value silently succeeds with `ToolResult(content="")`. The model sees a "successful" tool call with no output and moves on.

## Raw `Tool` handler receives a `TypedDict`, not a dataclass

The `ToolHandler` type takes a `ToolInvocation` which is a `TypedDict`. You access fields with `invocation["session_id"]`, not `invocation.session_id`. Inconsistent with `@define_tool` ergonomics.

## Custom agents: `tools=None` vs `tools=[]` is critical

- `tools=None` (or omitted) = agent has access to **all** tools.
- `tools=[]` = agent has access to **no** tools.

An empty list is not "default" — it's "nothing."

## MCP `tools=[]` silently disables the server

An empty tools list in MCP server config includes no tools from that server. No error, no warning. Use `tools=["*"]` to include all tools.

## `resume_session` creates a new object — old reference is orphaned

If you hold a reference to the previous session, its handlers are stale. The old object still sends RPC calls, but its event handlers, tool handlers, and permission handler are disconnected. Always replace your reference.

## BYOK credentials are never persisted

API keys for custom providers are never written to disk. You **must** re-provide `provider` config on every `resume_session` call. The session "resumes" successfully but can't call the model without re-providing the key.

## Skills on `resume_session` don't work yet

Adding `skill_directories` to a resumed session has no effect. Known bug. Set skills at session creation time only.

## Concurrent `create_session` can spawn duplicate CLI processes

Known race condition: concurrent `create_session` calls with `auto_start=True` may spawn multiple CLI child processes. Fix: call `await client.start()` once before creating any sessions, or serialize session creation.

## JSON-RPC uses daemon threads under the async interface

Reader/writer threads are daemon threads that may not be cleaned up on exit. `stop()` has a 1-second join timeout — after that, threads are abandoned. In long-running services, this leaks threads.

## `session.on()` callbacks must be synchronous

`session.on()` accepts `Callable[[SessionEvent], None]` — synchronous only. For async work, use `asyncio.create_task()` inside the handler. But be aware the handler may not run in the main event loop context.

## TCP mode: `SocketWrapper` pretends to be `subprocess.Popen`

When connecting via `cli_url`, the SDK wraps the socket in a `SocketWrapper` that duck-types as `Popen`. `terminate()` and `kill()` close the socket — they don't kill a process. Don't assume `client._process` is a real process.

## `asyncio.run()` at entry point precludes library use

If your entry point uses `asyncio.run(main())`, your app can't be imported from another async context — you'll get `RuntimeError: asyncio.run() cannot be called from a running event loop`. Put `asyncio.run()` only at the `if __name__ == "__main__"` guard and keep `main()` as an importable coroutine.

## Streaming deltas are ephemeral

`assistant.message_delta` events exist only during streaming. After `send_and_wait` returns, `get_messages()` only has the final `assistant.message`. You must accumulate `delta_content` yourself if you need the incremental text.

## `auto_start` and `auto_restart` default to `True`

If the CLI process crashes, the SDK silently restarts it. Session state may be lost during restart — all sessions are destroyed on reconnect. Set `auto_restart=False` if you need crash visibility.

## `_sessions_lock` is `threading.Lock`, not `asyncio.Lock`

Session tracking uses a threading lock. During `stop()`, this lock is held while iterating and destroying sessions. If `destroy()` awaits a long RPC call while the lock is held, other threads accessing `_sessions` are blocked. In apps with parallel sessions, this can cause contention.

## `pre_tool_use` hooks can silently bypass permission checks

A `PreToolUseHookOutput` with `permission_decision="allow"` bypasses the normal permission handler entirely. Combined with `modified_args`, a hook can silently alter what a tool does with no audit trail.

## Unknown event types become `UNKNOWN` — not errors

Events from future server versions with unrecognized types map to `SessionEventType.UNKNOWN` and are silently ignored. Good for compatibility, but you'll miss important new events if you only handle known types.

## Malformed events from the CLI crash the event processing loop

While unknown event types are graceful, malformed UUIDs or timestamps in events raise `ValueError` during parsing. This happens **before** dispatch, so `_dispatch_event`'s error handling doesn't catch it. A corrupted event kills event processing.
