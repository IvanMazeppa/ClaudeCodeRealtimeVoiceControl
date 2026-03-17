# Migration Notes

## Authoritative Since

`voice_coding_research` became the authoritative home for the stable Claude Code plus `voice-mode` workflow docs on `2026-03-17`.

## What Was Migrated

- The canonical stable-track workflow guide now lives in `docs/claude-code-workflow.md`.
- The canonical session-start prompt now lives in `apps/claude_code_voice/prompts/session_start.md`.
- The redacted stable local setup reference now lives in `apps/claude_code_voice/docs/local-setup-notes.md`.
- The pinned stable version note for `voice-mode==8.5.1` now lives in `apps/claude_code_voice/docs/voice-mode-8.5.1.md`.
- Repo-owned stable-track workflow wording, prompts, version notes, and redacted setup guidance should now be maintained in this repository.
- The older `PlasmaDXR` docs were retained only as historical pointer docs that send readers back to the canonical files in this repository.

## What Remained Machine-Local

- User-specific values and live entries in user-scoped config files, including Claude Code MCP registration and `voice-mode` runtime settings.
- Per-machine audio routing values and identifiers, including concrete Windows and WSL bridge details, usernames, hostnames, device labels, and local paths.
- Live secrets and environment-variable values such as `OPENAI_API_KEY`.
