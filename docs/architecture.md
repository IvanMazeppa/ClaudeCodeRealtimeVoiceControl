# Architecture

## Purpose

This repository separates a stable integration lane from an experimental realtime lane so current workflow materials do not get tangled with future research.

## Named Lanes

- Stable integration lane: `apps/claude_code_voice/` for Claude Code plus voice-mode integration work that supports the current reproducible workflow.
- Experimental realtime lane: `apps/realtime_voice/` for future realtime voice research. This lane is placeholder-only and not implemented yet.

## Shared vs Track-Specific Assets

- Root-level assets are shared when they apply to the repository as a whole, such as `docs/`, `scripts/`, `templates/`, and version-scoped materials under `patches/`.
- App-level assets are track-specific. Files under `apps/claude_code_voice/` belong to the stable integration lane, and files under `apps/realtime_voice/` belong to the experimental realtime lane.
- Do not move app-level prompts, setup notes, runtime code, or track-specific docs into a shared location unless both lanes later prove a real shared need.

## Boundary Rules

1. Keep the stable integration lane independent from speculative realtime work.
2. Keep the experimental realtime lane independent from the Claude Code integration runtime.
3. No shared runtime should be assumed between the two lanes.
4. Do not force shared abstractions before both lanes need them.
5. Store version-pinned assets where the version is visible in the path.
6. Treat experimental realtime materials as research until a later task defines implementation details.

## Current State

The stable integration lane can hold concrete workflow materials. The experimental realtime lane remains placeholder-only until a later task explicitly authorizes prototypes.
