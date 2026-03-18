# Claude Terminal Supervisor

## Purpose

The recommended integration is now a mixed-stack supervisor workflow:

- Claude Code runs in a normal tmux-backed terminal session
- the browser-based realtime app stays focused on low-latency voice
- a local Python Agents SDK supervisor owns the terminal orchestration layer

This keeps the voice surface fast while moving the fragile parts of terminal control into a
structured backend.

## Architecture

The supervisor flow uses:

- the realtime web app for speech, transcript, approvals, and action logs
- a local Node server as the browser-facing bridge
- a Python Agents SDK supervisor for sessions, traces, and tool orchestration
- a tmux-backed Claude terminal harness

## Main Workflow

The browser panel is built around five primary actions:

- start or verify the Claude session
- send the last heard spoken turn directly to Claude Code
- optionally edit and send a manual prompt draft
- read the current Claude terminal state
- approve or reject risky terminal actions

## Default Config

The editable repo-owned terminal config lives here:

- `apps/realtime_voice/config/claude-bridge.json`

That config defines:

- `sessionName`
- `workingDirectory`
- `command`
- `captureLines`
- `startupPromptFile`
- `startupSettleMs`
- `modePhrases`

## Tool Surface

The Python supervisor exposes a narrow Claude terminal tool surface:

- `attach_or_verify_session`
- `capture_output`
- `is_ready`
- `send_prompt`
- `interrupt_run`

Riskier prompt sends are approval-gated before the tool executes.

## Why This Shift

Trying to drive Claude Code's interactive terminal UI remotely through manual copy and paste
or screenshot loops tends to feel sluggish and awkward. The supervisor model is stronger:

- less manual shuffling between windows
- clearer approval boundaries for risky actions
- durable sessions and traces through the Agents SDK
- Claude Code stays the real coding agent
- the browser stays a thin voice-first client

## Computer-Use Position

`gpt-5.4` computer use is intentionally not the default Claude Code path in this version.

It remains a later fallback for cross-app or visual-state gaps that text capture cannot cover.
