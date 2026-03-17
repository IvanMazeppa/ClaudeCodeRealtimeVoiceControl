# Realtime Roadmap

## Why This Track Exists

The realtime track exists to preserve a separate research lane for future low-latency voice experiments that may require different transport, session, and runtime assumptions than the stable Claude Code integration lane.

Keeping that work separate prevents speculative architecture from leaking into the reproducible workflow under `apps/claude_code_voice/`.

## Current Status

The realtime track now authorizes a browser-based `realtime v1` prototype under
`apps/realtime_voice/`.

The prototype is experimental. The stable supported day-to-day workflow remains Claude
Code plus the `voice-mode` MCP server.

## `realtime v1` Scope

The current prototype scope is:

- browser microphone capture
- WebRTC connection to the OpenAI Realtime API
- a local Node server that mints short-lived Realtime client secrets
- brief spoken coding-assistant behavior
- live transcript and diagnostics UI

See:

- `apps/realtime_voice/README.md`
- `apps/realtime_voice/docs/overview.md`
- `apps/realtime_voice/docs/design.md`
- `apps/realtime_voice/docs/local-setup.md`

## What Is Still Deferred

- tool use inside the realtime assistant
- shared abstractions with `apps/claude_code_voice/`
- publishable packaging or deployment beyond local prototype use
- any decision to replace the stable lane

## What Must Remain Separate

The following must remain separate from `apps/claude_code_voice/` until both tracks prove a real shared need:

- runtime processes and entrypoints
- transport and session assumptions
- prompts, patches, and setup materials that belong to the stable integration lane
- app-level assets and implementation details

## Current Constraint

Do not let the existence of the prototype blur the repo contract:

- the stable Claude Code lane is still the supported path
- the realtime lane is still experimental
- no shared runtime should be assumed between them
