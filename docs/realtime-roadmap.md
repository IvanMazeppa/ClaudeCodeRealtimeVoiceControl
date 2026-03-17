# Realtime Roadmap

## Why This Track Exists

The realtime track exists to preserve a separate research lane for future low-latency voice experiments that may require different transport, session, and runtime assumptions than the stable Claude Code integration lane.

Keeping that work separate prevents speculative architecture from leaking into the reproducible workflow under `apps/claude_code_voice/`.

## Current Status

The realtime track is not implemented yet. Task 7 keeps `apps/realtime_voice/` placeholder-only and uses this document to define boundaries, not a build plan.

## What Is Deferred

- runtime code under `apps/realtime_voice/`
- stack and SDK selection
- audio pipeline and session model
- packaging, deployment, and local setup steps
- any cross-track abstraction work

## What Must Remain Separate

The following must remain separate from `apps/claude_code_voice/` until both tracks prove a real shared need:

- runtime processes and entrypoints
- transport and session assumptions
- prompts, patches, and setup materials that belong to the stable integration lane
- app-level assets and implementation details

## Current Constraint

Do not add implementation details here yet. The realtime track remains intentionally placeholder-only until a later task explicitly authorizes prototypes.
