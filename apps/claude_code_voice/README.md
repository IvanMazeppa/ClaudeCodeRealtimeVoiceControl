# Claude Code Voice

This app directory is the stable track for Claude Code plus `voice-mode` MCP integration.

It is not scaffold-only. This directory now contains the canonical session-start prompt and the app-owned support material for the current reproducible workflow.

## Purpose

Use this area for stable-track materials that support day-to-day voice sessions with Claude Code, including:

- the canonical session-start prompt
- stable-track workflow support docs
- redacted setup notes
- pinned version notes
- repair and verification support referenced from the repo-level scripts and patch artifact

## Current Contents

- `prompts/session_start.md`: canonical session-start prompt for the stable voice workflow
- `docs/local-setup-notes.md`: redacted known-good local setup summary
- `docs/voice-mode-8.5.1.md`: pinned stable version note for `voice-mode==8.5.1`

Related stable-track support also lives at repo scope:

- `docs/claude-code-workflow.md`: canonical workflow guide
- `scripts/install_claude_code_voice.sh`: guided installer for the stable track
- `scripts/verify_audio_stack.sh`: audio-path verification support
- `scripts/verify_voicemode.sh`: pinned stable `voice-mode` smoke test
- `scripts/apply_voicemode_patch.sh`: repair helper for the standalone `8.5.1` CLI path
- `patches/voice-mode/8.5.1/cli-empty-tts.patch`: version-pinned standalone CLI patch artifact

## Current Status

The stable Claude Code plus MCP track is bootstrapped and documented here. Treat these files as the maintained source for the current supported workflow. The standalone `uvx ... converse --continuous` path remains diagnostic-only and, on `8.5.1`, may rely on the version-pinned patch support in this repository.
