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
- OpenAI Realtime speech-to-speech interaction over WebRTC
- brief spoken replies suitable for coding sessions
- on-screen transcript and diagnostics visibility

## Current Scope

`realtime v1` includes:

- a local Node server that mints short-lived Realtime client secrets
- a browser UI that manages mic permissions, connection state, and audio playback
- live transcript and event visibility for debugging
- local `.env` configuration that stays outside git

## Explicit Non-Goals

`realtime v1` does not try to:

- replace the stable Claude Code plus MCP workflow
- share runtime code with `apps/claude_code_voice/`
- expose long-lived secrets to the browser
- add tool-calling or code-edit automation inside the realtime app yet

## Decision Rule

Keep using the stable Claude Code lane for normal repository work.

Use the realtime lane when you want to evaluate a more immersive browser-based voice
assistant without changing the supported stable workflow contract.
