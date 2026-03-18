# Realtime Voice Design

## Transport Choice

`realtime v1` uses browser WebRTC, not a WSL-local WebSocket client.

Why:

- the browser can capture the working Windows and Android microphone path directly
- the browser can play model audio directly
- WebRTC is the recommended low-latency browser transport for OpenAI Realtime voice apps

## Session Lifecycle

1. The browser requests a short-lived client secret from the local Node server.
2. The local Node server calls the OpenAI Realtime client-secret endpoint using
   `OPENAI_API_KEY`.
3. The browser opens a WebRTC peer connection to the Realtime API using
   `gpt-realtime-1.5`.
4. The browser sends a `session.update` event over the data channel to apply voice,
   transcript, prompt, and turn-detection preferences.
5. The browser renders live status, transcripts, and diagnostics while audio flows over
   WebRTC.
6. When the user wants Claude Code interaction, the browser calls a local Python Agents SDK
   supervisor through the Node server.

## Prompt Composition

The final system instructions are composed from four layers:

1. the repo-owned base prompt in `apps/realtime_voice/prompts/system_prompt.txt`
2. an optional repo-owned preset under `apps/realtime_voice/prompts/presets/`
3. the currently selected spoken style
4. optional user-authored custom instructions stored locally in the browser

This keeps shared defaults in editable repo files while letting the user personalize the
assistant without committing machine-local preferences into git.

## Turn Handling

The default is VAD-driven turn handling.

Supported options in the UI:

- `semantic_vad`
- `server_vad`
- manual mode placeholder through `turn_detection: null`

## Spoken Behavior

The realtime prompt should mirror the stable lane's spoken style without sharing runtime:

- brief spoken replies
- detailed information stays on screen
- one short follow-up question at a time
- no reading long code or logs aloud unless explicitly asked

## Transcript Strategy

The browser UI listens for:

- `conversation.item.input_audio_transcription.delta`
- `conversation.item.input_audio_transcription.completed`
- `response.output_audio_transcript.delta`
- `response.output_audio_transcript.done`

That keeps user and assistant turns visible on screen even when audio already played.

## Python Supervisor

The browser is no longer responsible for Claude orchestration.

That responsibility now lives in a Python supervisor that uses the OpenAI Agents SDK for:

- persistent sessions across turns
- traceable agent runs
- a specialized Claude terminal agent exposed as a tool
- approval-gated terminal actions
- resumable run state for pending approvals

The Claude terminal surface is text-native and tmux-backed, not screenshot-first. The core
tool set is:

- `attach_or_verify_session`
- `capture_output`
- `is_ready`
- `send_prompt`
- `interrupt_run`

## Computer-Use Fallback

`gpt-5.4` computer use remains a later fallback, not the default path.

Current evaluation:

- terminal text capture is cheaper and easier to trace
- approval gating is clearer when actions are tool calls rather than UI gestures
- Claude Code is fundamentally a long-lived text UI, so a tmux harness is the right first fit

Use computer use only when we hit real visual-state gaps that plain terminal capture cannot
cover.

## Future Upgrades

These belong after `realtime v1` proves stable:

- explicit push-to-talk UX
- richer transcript persistence
- richer supervisor behaviors and handoffs
- publishable packaging beyond local prototype use
