# Claude Code Workflow

## Source Of Truth

This repository is now the source of truth for the stable Claude Code plus `voice-mode` workflow.

The older documents in `PlasmaDXR` were the migration source material. Keep new workflow wording, prompts, and version notes here.

## Stable Track

The stable track is Claude Code plus the `voice-mode` MCP server.

Treat the Claude Code plus MCP path as the day-to-day supported workflow. Do not treat the standalone `uvx voice-mode converse --continuous` command as the stable assistant path.

Responsibility boundary:

- `voice-mode` owns local audio capture, local audio playback, speech-to-text, and text-to-speech.
- Claude Code invokes `voice-mode` over MCP and provides the decision layer for when to listen, when to speak, and what should stay on screen.

## Current Working Path

The known-good flow is:

1. An Android microphone is routed into Windows through an audio input bridge.
2. WSL audio bridging exposes that path to Linux applications in WSL.
3. `voice-mode` runs locally with access to that audio path and to `OPENAI_API_KEY`.
4. Claude Code runs inside WSL and can see the registered `voice-mode` MCP server.
5. Claude Code calls the `voice-mode` `converse` tool for spoken turns.
6. `voice-mode` captures microphone audio, performs STT and TTS work, and plays spoken output locally.
7. Claude Code receives the result from `voice-mode` and decides the next action, including what to say and what detail should remain on screen.

## Required Local Assumptions

- `OPENAI_API_KEY` should be supported through an environment variable in both Windows and WSL.
- Do not store live API keys in repo-tracked files.
- Claude Code MCP registration should stay in user-level config, not in committed project files.
- `voice-mode` runtime configuration should stay in user-level config, not in committed project files.

See `apps/claude_code_voice/docs/local-setup-notes.md` for the redacted local setup summary.

## Troubleshooting Direction

Use the owner boundary to decide where to debug first:

- If the problem is microphone input, speaker output, transcription, or speech playback, start with the Android to Windows path, the WSL audio bridge, and `voice-mode` configuration.
- If the problem is that Claude Code cannot see or call `voice-mode`, start with Claude Code MCP registration.
- If the problem is conversational behavior, prompt behavior, or how much detail is spoken versus left on screen, start with Claude Code session setup and the session-start prompt.

## Session Start

1. Confirm the microphone path is still available from Android to Windows and through WSL audio.
2. Confirm that `voice-mode` still has access to the local audio path and the required environment variables.
3. Start Claude Code inside WSL.
4. Confirm the `voice-mode` MCP server is visible and healthy in Claude Code.
5. Paste the prompt from `apps/claude_code_voice/prompts/session_start.md`.
6. Let Claude speak the opening line: `Voice work mode active. What would you like to do?`
7. Continue as a spoken work session while detailed output stays on screen.

## Spoken Output Rules

The stable workflow assumes:

- spoken output should be brief
- full technical detail should stay on screen
- code blocks, diffs, logs, stack traces, and long file paths should not be read aloud unless explicitly requested
- Claude should ask one short spoken question at a time when user input is needed

The canonical wording for these rules lives in `apps/claude_code_voice/prompts/session_start.md`.

## Useful Voice Phrases

These in-session phrases are part of the stable workflow:

- `details`
- `summarize`
- `next step`
- `read code`
- `voice brief mode`
- `voice detail mode`
- `voice coding mode`

## Stable Versus Diagnostic Paths

### Stable

Use Claude Code plus MCP for real work sessions. Claude Code supplies the decision layer, decides when to call `converse`, and decides what should be spoken versus left on screen. `voice-mode` handles the local audio and STT/TTS work for those turns.

### Diagnostic

Use the standalone CLI only for smoke tests or local troubleshooting. A one-shot check is still useful:

```bash
uvx --from voice-mode==8.5.1 voice-mode converse --message "Voice check." --no-wait
```

The standalone continuous CLI is not the stable workflow and should not be treated as the source of truth for overall voice-session behavior.

See `apps/claude_code_voice/docs/voice-mode-8.5.1.md` for version-specific notes.

## Canonical Files

- Workflow guide: `docs/claude-code-workflow.md`
- Session-start prompt: `apps/claude_code_voice/prompts/session_start.md`
- Local setup notes: `apps/claude_code_voice/docs/local-setup-notes.md`
- Version note: `apps/claude_code_voice/docs/voice-mode-8.5.1.md`

Keep the stable Claude Code plus MCP track centered on these files.
