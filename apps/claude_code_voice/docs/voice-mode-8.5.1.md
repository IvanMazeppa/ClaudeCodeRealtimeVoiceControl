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

If the standalone continuous CLI regresses later, that does not automatically mean the Claude Code MCP path is broken. The Claude Code MCP path works without depending on the standalone continuous loop.

## Historical Patch Support For Unfixed CLI Copies

For `voice-mode==8.5.1`, standalone `uvx --from voice-mode==8.5.1 voice-mode converse --continuous` may still need the canonical patch artifact in this repository if the targeted installed copy does not already include the effective empty-TTS follow-up logic:

`patches/voice-mode/8.5.1/cli-empty-tts.patch`

That patch artifact captures the historical minimal delta for unfixed standalone continuous-loop copies:

- empty follow-up turn
- forced listen-only behavior on that follow-up turn
- no empty-string TTS call

Important nuance:

- current shipped `uvx --from voice-mode==8.5.1` installs may already include equivalent logic in `voice_mode/cli.py`
- that means patch dry-run may fail even though the target copy is already effectively fixed
- `scripts/apply_voicemode_patch.sh` should detect that already-fixed code path and exit successfully without trying to apply the historical patch

Important separation:

- the historical patch artifact only matters for standalone `uvx --from voice-mode==8.5.1 voice-mode converse --continuous` copies that are still unfixed
- the stable Claude Code plus MCP workflow does not depend on the standalone continuous loop
- the canonical patch artifact now lives in this repository at `patches/voice-mode/8.5.1/cli-empty-tts.patch`

## Durable Takeaway

For version `8.5.1`, the stable track is Claude Code plus MCP.

Treat the standalone CLI as a troubleshooting or experimental path, not as the source of truth for the supported workflow. If standalone `--continuous` behavior matters on `8.5.1`, use `scripts/apply_voicemode_patch.sh` against the specific install you care about; it should either detect the effective shipped fix or confirm that the historical patch is needed.
