# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Repo Is

A voice-coding research workspace with two independent lanes:

- **Stable lane** (`apps/claude_code_voice/`): Claude Code + `voice-mode` MCP integration for daily workflow. Contains canonical session-start prompt, setup notes, and version-pinned support materials.
- **Experimental lane** (`apps/realtime_voice/`): Browser-first OpenAI Realtime prototype with a Python supervisor and Mentor v1 assistant layer.

The two lanes share no runtime, prompts, transport, or launch processes. Do not create shared abstractions between them unless both lanes prove a real shared need.

## Common Commands

### Realtime voice app (experimental lane)

```bash
# Full launch (installs deps, creates venv, starts server)
scripts/start_realtime_voice.sh

# Manual start (if deps already installed)
node apps/realtime_voice/server.mjs

# Install Node deps only
npm install --prefix apps/realtime_voice

# Install Python supervisor into its venv
python3 -m venv apps/realtime_voice/python_supervisor/.venv
apps/realtime_voice/python_supervisor/.venv/bin/python -m pip install -e apps/realtime_voice/python_supervisor
```

### Companion server (persistent WebSocket mode)

```bash
# Start the persistent Python companion server (port 4174)
scripts/start_companion_server.sh

# Or manually:
apps/realtime_voice/python_supervisor/.venv/bin/python -m realtime_voice_supervisor.cli serve \
    --app-root apps/realtime_voice --repo-root . --host 127.0.0.1 --port 4174
```

### Stable lane verification scripts

```bash
scripts/verify_voicemode.sh        # smoke-test pinned voice-mode
scripts/verify_audio_stack.sh      # verify audio path
scripts/verify_realtime_voice.sh   # verify realtime voice setup
scripts/install_claude_code_voice.sh  # guided stable-track installer
```

## Architecture

### Realtime Voice App (`apps/realtime_voice/`)

Three-layer stack:

1. **Browser UI** (`public/`): Static HTML/CSS/JS. Owns mic capture, WebRTC to OpenAI, audio playback, transcript display, preset selection, and Prompt Studio editing. Single-page app served by Express.

2. **Node server** (`server.mjs`): Express on port 4173. Mints ephemeral OpenAI Realtime client secrets, serves the static UI, loads prompt presets from `prompts/presets/`, and proxies requests into the Python supervisor via `child_process.execFile`.

3. **Python supervisor** (`python_supervisor/`): OpenAI Agents SDK package (`realtime-voice-supervisor`). Two runtime modes:

   **Companion mode (new, persistent WebSocket server on port 4174):**
   - `companion.py` — single `RealtimeAgent` with terminal, git, repo, and deep-analysis tools plus `WebSearchTool`
   - `companion_server.py` — WebSocket server managing companion lifecycle, browser state sync, and approval flow
   - `memory.py` — extracted two-lane memory store (shared project lane + per-profile lane)

   **Legacy subprocess mode (existing, invoked per-request from Node):**
   - `supervisor.py` — main Agent with approval-gated terminal actions and SQLite session persistence
   - `mentor.py` — five specialized read-only agents (mentor, change-explainer, second-opinion, prompt-drafter, approval-explainer)

   **Shared modules:**
   - `harness.py` — tmux-backed Claude terminal harness for capturing terminal snapshots
   - `git_tools.py` / `repo_tools.py` — function tools for git-aware context and repo inspection
   - `models.py` — Pydantic response models for structured mentor outputs
   - `prompts.py` — instruction templates for all agents

### Stable Lane (`apps/claude_code_voice/`)

Prompt and docs only — no runtime code. The canonical session-start prompt is at `prompts/session_start.md`.

## Key Conventions

- **Environment**: Requires `OPENAI_API_KEY` in `apps/realtime_voice/.env` or shell environment. See `.env.example` for all config vars.
- **Python**: Requires >=3.10. The supervisor uses its own venv at `python_supervisor/.venv/`. Dependencies: `openai-agents`, `pydantic>=2`.
- **Node**: ESM (`"type": "module"`). Dependencies: `express`, `dotenv`.
- **WSL context**: This repo runs in WSL2. The browser UI is accessed from Windows (localhost or WSL IP). Audio routing goes through the Windows/Android browser, not WSL audio.
- **Lane boundary**: Never mix stable-lane and realtime-lane files, imports, or runtime assumptions. App-specific prompts, docs, and config stay under their respective `apps/` directory.
- **Prompt presets**: Live in `apps/realtime_voice/prompts/presets/`. The Node server serves them via API; the browser UI displays them for selection.
