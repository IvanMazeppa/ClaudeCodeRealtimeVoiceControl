# Realtime Voice Overview

## Status

This track now authorizes a concrete `realtime v1` prototype under
`apps/realtime_voice/`.

It remains experimental, but it is no longer placeholder-only.

## Goal

Provide a second voice-control system in the same workspace that is distinct from the
stable Claude Code plus `voice-mode` path.

The `realtime v1` goal is:

- direct browser microphone capture
- OpenAI Realtime speech-to-speech interaction over WebRTC using `gpt-realtime-1.5`
- brief spoken replies suitable for coding sessions
- on-screen transcript and diagnostics visibility
- a browser-visible mentor layer that can explain Claude work without taking over execution

## Current Scope

`realtime v1` includes:

- a local Node server that mints short-lived Realtime client secrets
- a browser UI that manages mic permissions, connection state, and audio playback
- live transcript and event visibility for debugging
- repo-owned preset personalities
- local custom system instructions stored in the browser
- a Python Agents SDK supervisor for Claude Code terminal orchestration
- approval-gated terminal actions with visible action logs
- a live Claude terminal snapshot inside the browser UI
- a Mentor panel for:
  - explain latest changes
  - second opinion on Claude's direction
  - prompt drafting for Claude
  - approval explanation
- local `.env` configuration that stays outside git

## Explicit Non-Goals

`realtime v1` does not try to:

- replace the stable Claude Code plus MCP workflow
- share runtime code with `apps/claude_code_voice/`
- expose long-lived secrets to the browser
- give the mentor direct repo-write or shell-passthrough powers
- default to screenshot-first computer-use control

## Mentor Boundary

`Mentor v1` is intentionally read-only.

It may read:

- git state
- repo files
- Claude terminal state
- pending approval metadata

It may summarize or draft follow-up prompts, but it does not execute repo mutations on its
own. Claude Code remains the primary coding executor, and risky Claude actions still go
through the existing approval path.

## Decision Rule

Keep using the stable Claude Code lane for normal repository work.

Use the realtime lane when you want to evaluate a more immersive browser-based voice
assistant without changing the supported stable workflow contract.

Keep `gpt-5.4` computer use as an explicit fallback for later phases when text-native
terminal capture is insufficient.
