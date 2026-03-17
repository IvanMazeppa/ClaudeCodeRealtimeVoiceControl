# Session Handoff

## Purpose

Use this file to start a new session in the `voice_coding_research` workspace
without reloading the full migration and setup chat history.

This file is the short handoff. The exported transcript is backup reference only.

## Current State

- This repository is the source of truth for the stable Claude Code plus
  `voice-mode` workflow.
- The stable supported path is Claude Code plus the `voice-mode` MCP server.
- The stable baseline is `voice-mode==8.5.1`.
- A separate experimental browser/WebRTC realtime prototype now lives under
  `apps/realtime_voice/`.
- The stable supported day-to-day path is still Claude Code plus `voice-mode` MCP.
- The repository has been pushed to GitHub.
- The initial verification path has already been exercised successfully on the
  current machine:
  - repo scripts pass syntax checks
  - the audio verification path showed passes
  - the `voice-mode` smoke path showed passes
  - an audible `Voice check` was heard

## Canonical Files

Treat these files as the first place to read before using any large transcript:

- `README.md`
- `docs/claude-code-workflow.md`
- `docs/migration-notes.md`
- `docs/session-handoff.md`
- `docs/realtime-roadmap.md`
- `docs/voice-systems.md`
- `apps/claude_code_voice/prompts/session_start.md`
- `apps/claude_code_voice/docs/local-setup-notes.md`
- `apps/claude_code_voice/docs/voice-mode-8.5.1.md`
- `apps/realtime_voice/README.md`
- `apps/realtime_voice/docs/overview.md`

## Machine-Owned State

These remain outside git and should not be changed casually:

- `~/.claude.json`
- `~/.cursor/mcp.json`
- `~/.voicemode/voicemode.env`
- `~/.asoundrc`
- live secrets such as `OPENAI_API_KEY`
- per-machine audio routing details and device labels

Ask before changing any of those files.

## Responsibility Boundary

Keep these layers distinct:

- `voice-mode` owns local audio capture, local audio playback, STT, and TTS
- Claude Code owns MCP invocation, session logic, and spoken-vs-on-screen
  behavior
- Windows and WSL audio layers only provide the local audio path that
  `voice-mode` depends on

## Stable Workflow Reminder

- Use Claude Code plus MCP for real work sessions.
- Do not treat `uvx voice-mode converse --continuous` as the supported daily
  workflow.
- The standalone CLI is diagnostic or experimental only.
- If standalone `8.5.1` CLI behavior matters, use
  `scripts/apply_voicemode_patch.sh` against the specific install you care
  about.

## New Session Start

When starting a fresh session in the new workspace:

1. Read the canonical files above.
2. Assume the repo docs are authoritative and the old `PlasmaDXR` voice docs are
   historical pointers only.
3. Assume machine-owned config remains local unless explicitly discussed.
4. Use the session-start prompt in
   `apps/claude_code_voice/prompts/session_start.md` for spoken Claude sessions.

## Suggested Handoff Prompt

Paste this at the start of a new workspace chat if needed:

```text
This workspace is for `voice_coding_research`, the standalone repo for the stable Claude Code plus `voice-mode` workflow and future realtime voice experiments.

Use these files as the primary source of truth:
- `README.md`
- `docs/claude-code-workflow.md`
- `docs/migration-notes.md`
- `docs/session-handoff.md`
- `docs/realtime-roadmap.md`
- `docs/voice-systems.md`
- `apps/claude_code_voice/prompts/session_start.md`
- `apps/claude_code_voice/docs/local-setup-notes.md`
- `apps/claude_code_voice/docs/voice-mode-8.5.1.md`
- `apps/realtime_voice/README.md`
- `apps/realtime_voice/docs/overview.md`

Important assumptions:
- stable supported path: Claude Code plus `voice-mode` MCP
- pinned stable baseline: `voice-mode==8.5.1`
- separate experimental realtime prototype under `apps/realtime_voice/`
- machine-owned files stay outside git unless explicitly discussed
- ask before changing `~/.claude.json`, `~/.cursor/mcp.json`, `~/.voicemode/voicemode.env`, or `~/.asoundrc`

Use the exported transcript only as fallback reference if the canonical docs do not answer something.
```

## Transcript Fallback

If deeper history is needed, use the exported transcript here:

- `cursor_exports/cursor_voice_access_setup_using_android.md`

Do not use it as the primary context source unless the canonical docs are
missing something specific.

## Next Good Targets

Natural next tasks in this repo are:

- validate one real end-to-end Claude Code voice session from the new workspace
- validate one local browser-based realtime session under `apps/realtime_voice/`
- tighten any machine-local drift discovered during real use
