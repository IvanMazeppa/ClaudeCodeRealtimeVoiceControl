# Voice Coding Research

This repository is the working home for voice-coding research and workflow hardening.

It is bootstrapped, not scaffold-only. The stable Claude Code plus `voice-mode` track now has canonical docs, a canonical session-start prompt, redacted setup notes, pinned version notes, support scripts, templates, and a versioned patch artifact.

## Tracks

### `apps/claude_code_voice`

Stable Claude Code plus `voice-mode` integration work. This track preserves and improves the current reproducible workflow, including the canonical prompt, stable-track docs, setup notes, and version-pinned support materials.

### `apps/realtime_voice`

Future experimental realtime voice app work. This track remains placeholder-only until the research direction is approved and implementation details are ready to be written down.

## Repository Layout

- `apps/claude_code_voice/`: stable-track prompt and app-specific support docs
- `apps/realtime_voice/`: future experimental app materials
- `docs/`: canonical stable-track workflow docs plus shared architecture, migration, roadmap, and troubleshooting docs
- `templates/`: reusable example config files for MCP, audio bridging, and `voice-mode` setup
- `scripts/`: installer, sync, verification, and patch-helper scripts for the stable track
- `patches/voice-mode/8.5.1/`: version-pinned patch artifact for the standalone `voice-mode` CLI path on `8.5.1`

## Current Status

The repository bootstrap is in place and the stable track now includes the canonical materials for the current supported workflow:

- `docs/claude-code-workflow.md`
- `apps/claude_code_voice/prompts/session_start.md`
- `apps/claude_code_voice/docs/local-setup-notes.md`
- `apps/claude_code_voice/docs/voice-mode-8.5.1.md`
- repo-owned templates, support scripts, and the `patches/voice-mode/8.5.1/cli-empty-tts.patch` artifact

The stable Claude Code plus MCP workflow is the supported day-to-day path. The realtime track remains research-only.
