# Local Setup Notes

## Purpose

This file records the redacted shape of a known-good local setup for the stable Claude Code plus `voice-mode` MCP workflow.

These notes intentionally omit live secrets, email addresses, usernames, hostnames, device labels, and other machine-specific details that do not belong in public-facing docs.

## Known-Good Audio Path

The working microphone path was:

1. An Android microphone fed audio into Windows through a desktop audio input bridge.
2. Windows exposed that input to the local desktop audio stack.
3. WSL audio integration made the Windows-side audio path available to Linux applications.
4. A user-level ALSA bridge forwarded Linux audio clients to the WSL PulseAudio or PipeWire path.
5. Claude Code in WSL used that audio path indirectly through the `voice-mode` MCP workflow.

In short: Android mic to Windows, then Windows audio into WSL, then Claude Code plus MCP inside WSL.

## WSL Audio Bridge

The known-good WSL layer relied on:

- WSLg audio support
- a user-level ALSA bridge file at `~/.asoundrc`
- a working PulseAudio or PipeWire path visible to Linux applications

If speech stops working after an update, recheck the WSL audio path before assuming the MCP workflow is broken.

## Claude Code MCP Registration

The stable path depends on registering `voice-mode` as an MCP server in Claude Code user config.

The known-good registration location was:

- `~/.claude.json`

Keep the registration user-scoped. Do not commit machine-local MCP registration files into this repository.

## voice-mode Config Location

The known-good `voice-mode` config location was:

- `~/.voicemode/voicemode.env`

The tested local config favored:

- TTS model: `gpt-4o-mini-tts`
- preferred voice order starting with `shimmer`

Keep repo docs limited to safe, redacted configuration guidance rather than copying full live config files.

## Secret Handling

No live secrets belong in this repository.

Use environment variables instead of inline values:

- `OPENAI_API_KEY` should be available in Windows
- `OPENAI_API_KEY` should also be available in WSL

That keeps both Windows-side tooling and WSL-side Claude sessions compatible without checking secrets into git.

## Durable Takeaway

The stable setup is not "one magic machine." It is a small chain of layers:

- Android microphone path into Windows
- WSL audio bridge
- Claude Code MCP registration
- `voice-mode` user config
- environment-variable-based secret handling

If those layers remain intact, the stable Claude Code plus MCP workflow is the path to preserve.
