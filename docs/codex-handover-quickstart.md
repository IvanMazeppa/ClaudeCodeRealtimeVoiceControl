# Codex Handover Quickstart

Use this document when starting a fresh Codex session and you want the shortest possible
high-signal handover.

## Paste-First Prompt

```text
Start by reading these files in order:
1. `docs/codex-handover-quickstart.md`
2. `docs/codex-handover.md`
3. `docs/session-handoff.md`
4. `docs/voice-systems.md`
5. `apps/realtime_voice/README.md`
6. `apps/realtime_voice/docs/overview.md`
7. `apps/realtime_voice/docs/design.md`
8. `apps/realtime_voice/docs/local-setup.md`
9. `apps/realtime_voice/docs/claude-bridge.md`

Project context:
- This repo has two lanes:
  - stable supported lane: Claude Code + `voice-mode` MCP, pinned around `voice-mode==8.5.1`
  - experimental lane: `apps/realtime_voice/`
- The stable lane remains the supported day-to-day workflow.
- The experimental lane is being upgraded into a mixed-stack architecture.

Mandatory instruction:
- do not rely on memory alone for current OpenAI model availability or Agents SDK capabilities
- before making architecture decisions, research the latest official OpenAI API docs and the
  latest official OpenAI Agents SDK docs/repo docs
- if direct docs access is blocked, use `Context7` MCP to fetch the relevant documentation

Current experimental architecture:
- browser remains the low-latency voice client
- browser voice transport is WebRTC
- realtime model is moving to `gpt-realtime-1.5`
- Node server mints Realtime client secrets and bridges browser requests
- Python backend uses the OpenAI Agents SDK for orchestration
- Claude Code should be controlled through structured tmux/PTY-backed terminal tools
- risky terminal actions should be approval-gated
- `gpt-5.4` computer use is a later fallback only, not the default v1 path

What has already been changed:
- `apps/realtime_voice/server.mjs`
- `apps/realtime_voice/public/index.html`
- `apps/realtime_voice/public/app.js`
- `apps/realtime_voice/public/styles.css`
- `apps/realtime_voice/python_supervisor/src/realtime_voice_supervisor/`
- `scripts/start_realtime_voice.sh`
- `scripts/verify_realtime_voice.sh`
- realtime docs and handoff docs

Current confidence level:
- syntax has been checked
- IDE lints were clean on edited files
- full runtime verification of the mixed stack is still pending

What to do first:
1. inspect `git status`
2. research the latest OpenAI API docs and Agents SDK docs before making capability claims
3. if blocked, use `Context7` MCP for the docs retrieval
4. run `bash scripts/verify_realtime_voice.sh`
5. run `bash scripts/start_realtime_voice.sh`
6. fix any Python supervisor bootstrap or dependency issues
7. verify browser connection with `gpt-realtime-1.5`
8. verify one real Claude session attach/send flow
9. verify one approval flow
10. verify one interrupt flow

Important constraints:
- do not casually edit machine-owned files:
  - `~/.claude.json`
  - `~/.cursor/mcp.json`
  - `~/.voicemode/voicemode.env`
  - `~/.asoundrc`
- ask before changing local machine audio or secret configuration
- do not treat old exported transcripts as the primary source if repo docs already answer the question
```

## One-Paragraph Summary

This repository is exploring a product-worthy voice coding workflow with two lanes: a stable
Claude Code + `voice-mode` path for real work, and an experimental browser-first realtime lane
under `apps/realtime_voice/`. The experimental lane has shifted away from a manual copy/paste
companion model toward a mixed-stack architecture where the browser handles voice UX, a local
Node server handles Realtime token minting and API bridging, and a Python OpenAI Agents SDK
supervisor manages tmux-backed Claude terminal tools, approvals, and orchestration. The browser
side is moving to `gpt-realtime-1.5`, the backend supervisor currently targets `gpt-5.4`, and
computer use is explicitly deferred as a later fallback rather than the main control path. The
next assistant must verify this design against the latest official OpenAI API and Agents SDK
docs (https://github.com/openai/openai-agents-python/tree/main) before making strong claims, using `Context7` MCP if direct doc access is blocked.

## If Time Is Extremely Tight

At minimum, a new Codex session should read:

1. `docs/codex-handover.md`
2. `apps/realtime_voice/server.mjs`
3. `apps/realtime_voice/public/app.js`
4. `apps/realtime_voice/python_supervisor/src/realtime_voice_supervisor/supervisor.py`
5. `scripts/start_realtime_voice.sh`
