# Troubleshooting

## Stable Lane

If the stable Claude Code plus `voice-mode` workflow fails:

- audio or transcription issue: start with `bash scripts/verify_audio_stack.sh`
- `voice-mode` issue: run `bash scripts/verify_voicemode.sh`
- missing MCP tool: inspect the `voice-mode` fragment in `~/.claude.json` and
  `~/.cursor/mcp.json`

## Realtime Lane

If the browser-based realtime app fails:

- confirm `apps/realtime_voice/.env` exists and contains `OPENAI_API_KEY`
- restart the local server with `bash scripts/start_realtime_voice.sh`
- open the browser devtools console and the in-app event log
- confirm the browser has microphone permission
- hit `http://127.0.0.1:4173/health` and confirm the local server reports `ok: true`
- if Windows says `127.0.0.1 refused to connect`, try the current WSL IP instead, such
  as `http://172.31.221.77:4173`

## Boundary Reminder

Do not debug the wrong lane first:

- stable lane problems usually live in WSL audio, `voice-mode`, or MCP registration
- realtime lane problems usually live in browser mic permissions, local `.env`, token
  minting, or WebRTC session setup
