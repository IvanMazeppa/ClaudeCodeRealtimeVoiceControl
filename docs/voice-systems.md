# Voice Systems

## Purpose

This repository now contains two separate voice-control systems in one workspace.

The goal is convenience without collapsing the architectural boundary between the stable
lane and the experimental lane.

## Use The Stable Lane When

Use `apps/claude_code_voice/` when you want the supported day-to-day workflow:

- Claude Code plus the `voice-mode` MCP server
- existing WSL audio path
- spoken summaries with detailed output on screen
- repo-supported setup and verification scripts

Canonical files:

- `docs/claude-code-workflow.md`
- `apps/claude_code_voice/prompts/session_start.md`
- `apps/claude_code_voice/docs/local-setup-notes.md`
- `apps/claude_code_voice/docs/voice-mode-8.5.1.md`

## Use The Realtime Lane When

Use `apps/realtime_voice/` when you want the experimental browser-based voice prototype:

- direct browser microphone capture
- OpenAI Realtime speech-to-speech over WebRTC
- a separate local Node launcher
- on-screen transcript and event diagnostics

Canonical files:

- `apps/realtime_voice/README.md`
- `apps/realtime_voice/docs/overview.md`
- `apps/realtime_voice/docs/design.md`
- `apps/realtime_voice/docs/local-setup.md`

## Quick Start Commands

Stable lane:

1. `bash scripts/verify_audio_stack.sh`
2. `bash scripts/verify_voicemode.sh`
3. start Claude Code and use `apps/claude_code_voice/prompts/session_start.md`

Realtime lane:

1. `bash scripts/start_realtime_voice.sh`
2. open `http://127.0.0.1:4173`
3. click `Connect`

## Boundary Reminder

Do not mix these layers:

- stable lane machine-local config lives in `~/.claude.json`, `~/.cursor/mcp.json`,
  `~/.voicemode/voicemode.env`, and `~/.asoundrc`
- realtime lane local config lives in `apps/realtime_voice/.env`

The stable lane remains the supported workflow. The realtime lane remains experimental.
