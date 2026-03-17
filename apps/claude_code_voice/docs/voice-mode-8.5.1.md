# voice-mode 8.5.1

## Tested Version

The stable Claude Code voice track in this repository was validated against `voice-mode==8.5.1`.

## What Worked

The known-good results for this version were:

- Claude Code could see the registered `voice-mode` MCP server
- Claude Code could call the `converse` tool for spoken turns
- the WSL audio bridge path was good enough for listen and speak cycles
- OpenAI STT worked for transcription in the MCP workflow
- `gpt-4o-mini-tts` worked for spoken output in the MCP workflow

A useful smoke test for local audio output remained:

```bash
uvx --from voice-mode==8.5.1 voice-mode converse --message "Voice check." --no-wait
```

That one-shot command is a diagnostic check. It is not the full stable workflow.

## Standalone CLI Limitation

The standalone continuous command:

```bash
uvx --from voice-mode==8.5.1 voice-mode converse --continuous
```

is not the stable assistant path.

Why:

- it does not provide Claude Code's decision layer
- it does not decide what should be spoken versus left on screen
- it is not equivalent to the Claude Code plus MCP conversation loop

If the standalone continuous CLI regresses later, that does not automatically mean the Claude Code MCP path is broken.

## Local Patch Requirement For The CLI Path

On the known-good local setup, the standalone CLI path used a local patch to the installed `voice-mode` CLI code path.

That local patch was needed to stop the continuous standalone path from sending empty strings to TTS.

Important separation:

- the patch requirement applied to the standalone CLI path
- the stable Claude Code plus MCP workflow did not depend on that standalone continuous loop

Current repo state:

- this repository does not yet contain a tracked patch artifact for that local CLI fix
- this document records the existence of the local workaround, but the workaround is not yet repo-owned
- until a tracked patch artifact is added, any reapplication remains a manual local concern outside this repository

## Durable Takeaway

For version `8.5.1`, the stable track is Claude Code plus MCP.

Treat the standalone CLI as a troubleshooting or experimental path, not as the source of truth for the supported workflow.
