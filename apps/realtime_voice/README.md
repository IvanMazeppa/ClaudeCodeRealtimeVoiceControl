# Realtime Voice

## Status

`apps/realtime_voice/` is now the experimental `realtime v1` lane in this repository.

It is intentionally separate from the stable Claude Code plus `voice-mode` workflow in
`apps/claude_code_voice/`.

## What This App Is

This app is a browser-first OpenAI Realtime prototype for hands-free coding sessions.

The browser owns:

- microphone capture
- WebRTC connection setup
- remote audio playback
- live transcript and diagnostics UI
- preset character selection
- local custom system-instruction editing

The local Node server owns:

- reading `OPENAI_API_KEY` from the local environment
- minting short-lived Realtime client secrets
- serving the static browser UI
- loading repo-owned prompt presets from `apps/realtime_voice/prompts/presets/`
- brokering requests into the Python supervisor

The local Python supervisor owns:

- Agents SDK sessions and tracing
- the tmux-backed Claude terminal harness
- approval-gated terminal actions
- action logs and readable Claude terminal snapshots

## Why Browser-First

This path fits the current machine setup better than a WSL-local WebSocket client:

- the browser can use the Windows and Android microphone path directly
- the browser can play remote model audio without extra WSL audio routing
- the repo still owns the source, docs, and launch commands

## Boundary From The Stable Lane

Keep these lanes separate:

- stable lane: Claude Code plus `voice-mode` MCP for day-to-day work sessions
- realtime lane: standalone browser/WebRTC prototype under `apps/realtime_voice/`

Do not assume shared runtime code, shared prompts, shared transport, or shared launch
processes between the two lanes.

## Quick Start

1. Copy `apps/realtime_voice/.env.example` to a local `.env` file in the same directory.
2. Set `OPENAI_API_KEY` in that local `.env` file.
3. Start the app with `scripts/start_realtime_voice.sh`.
4. Open `http://127.0.0.1:4173`.
5. If Windows cannot reach WSL localhost directly, use the current WSL IP instead,
   such as `http://172.31.221.77:4173`.
6. Pick a preset character or enter your own custom instructions in Prompt Studio.
7. Click `Save prompt` if you want those custom instructions persisted locally.
8. Click `Connect` and allow microphone access in the browser.
9. Use the Python Supervisor panel to start or verify the Claude session, send the last
    heard turn, review approval prompts, and read the captured Claude terminal snapshot.

## Canonical Realtime Docs

- overview: `apps/realtime_voice/docs/overview.md`
- local setup: `apps/realtime_voice/docs/local-setup.md`
- design notes: `apps/realtime_voice/docs/design.md`
- Claude terminal supervisor: `apps/realtime_voice/docs/claude-bridge.md`
- base prompt: `apps/realtime_voice/prompts/system_prompt.txt`
- preset prompts: `apps/realtime_voice/prompts/presets/`
