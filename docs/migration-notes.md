# Migration Notes

## Authoritative Since

`voice_coding_research` became the authoritative home for the migrated Claude Code voice workflow docs on `2026-03-17`.

## What Was Migrated

- The canonical workflow guide moved from `PlasmaDXR/docs/CLAUDE_CODE_VOICE_MODE_GUIDE.md` to `docs/claude-code-workflow.md`.
- The canonical session-start prompt moved from `PlasmaDXR/docs/CLAUDE_CODE_VOICE_WORK_MODE_PROMPT.md` to `apps/claude_code_voice/prompts/session_start.md`.
- The historical `PlasmaDXR` documents were retained only as pointer docs that send readers to the canonical copies in this repository.

## What Remained Machine-Local

- User-level Claude Code MCP registration for the `voice-mode` server.
- User-level `voice-mode` runtime configuration.
- Per-machine Windows and WSL audio routing details, including the phone-to-Windows and Windows-to-WSL bridge path.
- Secrets and environment-specific values such as `OPENAI_API_KEY`.
- OS-level voice control setup outside the repo-tracked workflow docs.
