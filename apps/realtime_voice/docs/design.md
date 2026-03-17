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
3. The browser opens a WebRTC peer connection to the Realtime API.
4. The browser sends a `session.update` event over the data channel to apply voice,
   transcript, and turn-detection preferences.
5. The browser renders live status, transcripts, and diagnostics while audio flows over
   WebRTC.

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

## Future Upgrades

These belong after `realtime v1` proves stable:

- tool use
- explicit push-to-talk UX
- richer transcript persistence
- repo-aware coding helpers
- publishable packaging beyond local prototype use
