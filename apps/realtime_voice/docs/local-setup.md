# Realtime Voice Local Setup

## Purpose

This document describes the machine-local setup for the browser-based realtime lane.

Unlike the stable Claude Code plus `voice-mode` workflow, this app does not rely on MCP
registration in Claude Code or Cursor.

## Required Local Inputs

- Node.js with `npm`
- a browser with microphone access
- `OPENAI_API_KEY` available in a local `.env` file under `apps/realtime_voice/`

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
- optional `REALTIME_MODEL`
- optional `REALTIME_VOICE`

If your shell already exports `OPENAI_API_KEY`, the app can also start without a local
`.env` file, but the local `.env` remains the cleaner repeatable setup.

## Run Steps

From `apps/realtime_voice/`:

1. `npm install`
2. `npm run dev`
3. Open `http://127.0.0.1:4173`
4. Allow microphone access in the browser
5. Click `Connect`

## Security Boundary

The browser must not receive the long-lived OpenAI API key.

The local Node server uses `OPENAI_API_KEY` only to mint short-lived Realtime client
secrets via the OpenAI REST API. The browser then uses that short-lived secret to open a
WebRTC session directly with OpenAI.

## Relationship To The Stable Lane

Keep the local setup separate from:

- `~/.claude.json`
- `~/.cursor/mcp.json`
- `~/.voicemode/voicemode.env`
- `~/.asoundrc`

Those files belong to the stable Claude Code plus `voice-mode` lane, not this realtime
app.
