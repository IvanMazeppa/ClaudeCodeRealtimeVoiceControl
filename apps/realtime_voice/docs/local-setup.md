# Realtime Voice Local Setup

## Purpose

This document describes the machine-local setup for the browser-based realtime lane.

Unlike the stable Claude Code plus `voice-mode` workflow, this app does not rely on MCP
registration in Claude Code or Cursor.

## Required Local Inputs

- Node.js with `npm`
- a browser with microphone access
- `OPENAI_API_KEY` available in a local `.env` file under `apps/realtime_voice/`
- `tmux`
- `claude` on PATH for the Claude bridge

## Safe Local File Shape

Create a local file here and keep it out of git:

- `apps/realtime_voice/.env`

Start from:

- `apps/realtime_voice/.env.example`

## Default Local Variables

The local `.env` file should define:

- `OPENAI_API_KEY`
- optional `REALTIME_PORT`
- optional `REALTIME_HOST`
- optional `REALTIME_MODEL` defaulting to `gpt-realtime-1.5`
- optional `REALTIME_VOICE`
- optional `REALTIME_SUPERVISOR_MODEL`

If your shell already exports `OPENAI_API_KEY`, the app can also start without a local
`.env` file, but the local `.env` remains the cleaner repeatable setup.

## Run Steps

From the repository root:

1. `scripts/start_realtime_voice.sh`
2. Open `http://127.0.0.1:4173`
3. If Windows cannot reach WSL localhost, use the current WSL IP such as
   `http://172.31.221.77:4173`
4. Allow microphone access in the browser
5. Pick a preset prompt and optionally add custom system instructions
6. Click `Save prompt` if you want those custom instructions stored locally in the browser
7. Click `Connect`
8. Use the Python Supervisor panel to start or verify the dedicated Claude session
9. Send the last heard turn or a manual draft to Claude Code from the browser
10. Review approvals when the supervisor flags risky terminal actions
11. Use `Read Claude state` when you want a fresh terminal capture and short spoken summary

## Security Boundary

The browser must not receive the long-lived OpenAI API key.

The local Node server uses `OPENAI_API_KEY` only to mint short-lived Realtime client
secrets via the OpenAI REST API. The browser then uses that short-lived secret to open a
WebRTC session directly with OpenAI.

Custom prompt text is stored locally in the browser, not in repo-tracked files.

The Python supervisor runs locally and uses the browser-facing Node server as its only entry
point. The browser still never receives the long-lived OpenAI API key.

## Relationship To The Stable Lane

Keep the local setup separate from:

- `~/.claude.json`
- `~/.cursor/mcp.json`
- `~/.voicemode/voicemode.env`
- `~/.asoundrc`

Those files belong to the stable Claude Code plus `voice-mode` lane, not this realtime
app.
