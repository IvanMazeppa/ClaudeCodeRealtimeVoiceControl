# Codex Handover

## Purpose

This document is the comprehensive handover for continuing `voice_coding_research` work in
another coding environment with minimal loss of context.

It is intentionally more detailed than `docs/session-handoff.md`.

Use this document when a new assistant needs to understand:

- what this repository is for
- why the architecture evolved the way it did
- what has already been built
- what is still incomplete or unverified
- which files are authoritative
- which local-machine details must be treated carefully

## Mandatory Research Rule

Before making architectural claims, model recommendations, or Agents SDK implementation
decisions, the next assistant should do an explicit documentation research pass.

This is critical because OpenAI platform capabilities are moving quickly and model memory alone
is not reliable enough for current-state decisions.

Required rule:

- do not rely on prior training or recollection alone for Agents SDK capabilities, current
  Realtime model availability, or current API behavior
- treat current official docs as the source of truth
- re-check the OpenAI API docs library and the OpenAI Agents SDK docs/repo docs before deciding - https://github.com/openai/openai-agents-python/tree/main
  what is or is not possible

Research priority:

1. official OpenAI API docs
2. official OpenAI Agents SDK docs and repo documentation
3. if direct access is blocked, use `Context7` MCP to retrieve the relevant docs
4. only after that, use general web fallback and restrict it to official OpenAI domains when
   possible

The next assistant should specifically research:

- current Realtime API capabilities and current recommended browser transport
- current `gpt-realtime-1.5` support and any newer relevant voice models
- current OpenAI Agents SDK support for sessions, tracing, handoffs, approvals, Realtime,
  tools-as-agents, and MCP
- whether any newer SDK or API surfaces materially improve this project's design

## Repo Mission

This repository contains two distinct voice-control lanes in one workspace:

1. the stable supported lane for real work: Claude Code plus the `voice-mode` MCP server
2. the experimental lane: browser-first realtime voice under `apps/realtime_voice/`

The goal is not just personal accessibility support. The broader product goal is to explore a
general-purpose, low-friction, high-quality voice-driven coding workflow that could become
genuinely product-worthy.

## Stable Lane vs Experimental Lane

### Stable Lane

Use `apps/claude_code_voice/` and repo docs around it when the task is day-to-day real coding.

Key facts:

- supported path: Claude Code plus `voice-mode` MCP
- pinned baseline: `voice-mode==8.5.1`
- machine-owned config matters a lot here
- this remains the authoritative workflow for normal repo work

Canonical stable files:

- `docs/claude-code-workflow.md`
- `apps/claude_code_voice/prompts/session_start.md`
- `apps/claude_code_voice/docs/local-setup-notes.md`
- `apps/claude_code_voice/docs/voice-mode-8.5.1.md`

### Experimental Realtime Lane

Use `apps/realtime_voice/` when working on the browser/WebRTC voice prototype.

Original goals:

- direct browser microphone capture
- low-latency OpenAI realtime speech-to-speech
- on-screen transcript and diagnostics
- a way to work effectively with Claude Code without relying on the stable `voice-mode` lane

Current architectural direction:

- browser stays optimized for voice UX
- a local Node server mints Realtime client secrets and serves the UI
- a local Python backend based on the OpenAI Agents SDK becomes the orchestration layer
- Claude Code interaction is modeled as structured terminal tools, not screenshot-first control

Canonical realtime files:

- `apps/realtime_voice/README.md`
- `apps/realtime_voice/docs/overview.md`
- `apps/realtime_voice/docs/design.md`
- `apps/realtime_voice/docs/local-setup.md`
- `apps/realtime_voice/docs/claude-bridge.md`
- `apps/realtime_voice/server.mjs`
- `apps/realtime_voice/public/index.html`
- `apps/realtime_voice/public/app.js`
- `apps/realtime_voice/public/styles.css`

## Why The Design Shift Happened

The main design pivot is important.

### What Was Tried First

An earlier design used a lighter "Claude companion" model:

- browser voice assistant as a sidekick
- draft prompts for Claude Code
- copy prompt into Claude manually
- paste Claude output back for summaries or next-prompt suggestions

That version worked, but the user found it too clunky and sluggish for the desired experience.

### Why The Companion Model Was Not Enough

The problem was not only model quality. The bigger issue was orchestration shape:

- too much manual copy/paste in the happy path
- too much context shifting between windows
- terminal control felt indirect and brittle
- the system did not feel like a real integrated voice workflow

### Why The New Mixed-Stack Plan Was Chosen

After researching the OpenAI Realtime API, `gpt-realtime-1.5`, `gpt-5.4`, computer use, and
the OpenAI Agents SDK, the recommended direction became:

- keep browser/WebRTC for the low-latency voice surface
- use `gpt-realtime-1.5` for the live browser voice session
- move orchestration into a Python Agents SDK backend
- represent Claude Code as a custom tmux/PTY-backed terminal tool surface
- add human approval before risky actions
- keep `gpt-5.4` computer use as a fallback later, not the default path

This choice was based on the following reasoning:

- browser voice wants WebRTC and direct browser media access
- the Python Agents SDK is strong for sessions, tracing, approvals, handoffs, and tool orchestration
- Claude Code is a long-lived interactive terminal UI, not a one-shot shell command
- tmux or PTY-backed terminal tools fit Claude Code better than screenshot loops as a first path

Even so, the next assistant should re-validate this reasoning against current docs before
cementing it further. The mixed-stack plan is the current best conclusion, not a permanent
axiom.

## Latest Model Decisions

### Browser Voice Model

The realtime lane has been moved toward `gpt-realtime-1.5`.

This was chosen as the current flagship browser-oriented realtime model and was the explicit
"Phase 0" immediate upgrade before deeper architecture work.

### Supervisor / Reasoning Model

The new Python supervisor is currently wired to default to `gpt-5.4` via
`REALTIME_SUPERVISOR_MODEL`, because that backend is intended for:

- orchestration
- reasoning about terminal state
- deciding when to act
- deciding when approval is required

### Computer Use

`gpt-5.4` computer use is not the default integration path in v1.

It is reserved as a later fallback for cases where text-native terminal capture is
insufficient, such as:

- non-textual app or window state
- cross-application workflows
- screenshot validation for ambiguous visual state

## Plan That Guided The Work

The plan file is:

- `/.cursor/plans/mixed_stack_voice_supervisor_17d074cb.plan.md`

The plan phases are:

1. upgrade the current realtime app to `gpt-realtime-1.5`
2. add a Python Agents SDK backend supervisor
3. build structured Claude terminal tools
4. add human approval and safety policies
5. rework the browser UI around the backend supervisor
6. evaluate optional computer-use fallback later

Important constraint from the user:

- do not edit the plan file itself

## What Has Been Implemented In Recent Sessions

The following implementation work has now been completed or materially advanced.

### 1. Realtime Model Upgrade

The realtime lane defaults were updated toward `gpt-realtime-1.5`.

Changed files:

- `apps/realtime_voice/server.mjs`
- `apps/realtime_voice/.env.example`
- `apps/realtime_voice/public/index.html`
- `apps/realtime_voice/public/app.js`
- realtime docs that mention the current model

### 2. New Python Supervisor Package

A new local Python backend package was added under:

- `apps/realtime_voice/python_supervisor/`

Key files:

- `apps/realtime_voice/python_supervisor/pyproject.toml`
- `apps/realtime_voice/python_supervisor/src/realtime_voice_supervisor/__init__.py`
- `apps/realtime_voice/python_supervisor/src/realtime_voice_supervisor/harness.py`
- `apps/realtime_voice/python_supervisor/src/realtime_voice_supervisor/supervisor.py`
- `apps/realtime_voice/python_supervisor/src/realtime_voice_supervisor/cli.py`

### 3. Claude Terminal Harness

The new Python harness is intended to own the structured Claude terminal interaction layer.

It currently includes logic for:

- loading `apps/realtime_voice/config/claude-bridge.json`
- merging optional `claude-bridge.local.json`
- checking whether a tmux session exists
- creating or attaching to the Claude session
- capturing visible terminal output
- sending prompts to Claude
- interrupting Claude
- reading the startup prompt file
- inferring prompt-ready state from captured output

### 4. Agents SDK Supervisor Layer

The new supervisor is designed around:

- a top-level `VoiceSupervisorAgent`
- a specialist `ClaudeTerminalAgent`
- SQLite-backed session persistence
- durable `RunState` approval flow for risky tool calls
- action logging and terminal snapshots stored in context payloads

The tool surface currently intended for Claude terminal work is:

- `attach_or_verify_session`
- `capture_output`
- `is_ready`
- `send_prompt`
- `interrupt_run`

### 5. Approval-Gated Prompt Sends

The supervisor includes a simple risk heuristic for prompt sends.

Prompts containing edit-like or destructive intent markers such as:

- `edit`
- `modify`
- `change`
- `write`
- `delete`
- `git`
- `commit`
- `reset`
- `rebase`
- package install commands

are intended to trigger Agents SDK human-in-the-loop approval before the tool actually sends
the prompt to Claude.

### 6. Browser UI Refactor

The browser UI was refactored away from the old companion copy/paste panel and toward a thin
client for the Python supervisor.

The current UI direction includes:

- start/verify Claude session
- send last heard turn
- send a manual prompt draft
- read Claude state
- interrupt Claude
- view pending approvals
- approve or reject actions
- see supervisor action logs
- see a live terminal snapshot
- explain latest changes
- ask for a second opinion on Claude's current direction
- draft a stronger Claude prompt through the mentor panel
- explain why a pending approval was flagged

### 7. Node-to-Python Bridge Endpoints

`apps/realtime_voice/server.mjs` was extended with browser-facing endpoints for the Python
supervisor:

- `GET /api/supervisor/health`
- `POST /api/supervisor/session`
- `POST /api/supervisor/observe`
- `POST /api/supervisor/turn`
- `POST /api/supervisor/manual-prompt`
- `POST /api/supervisor/interrupt`
- `POST /api/supervisor/decision`
- `POST /api/supervisor/explain-latest`
- `POST /api/supervisor/second-opinion`
- `POST /api/supervisor/draft-claude-prompt`
- `POST /api/supervisor/explain-approval`

### 10. Mentor v1 Backend

Mentor v1 has now been added to the Python supervisor as a read-only specialist.

Key files:

- `apps/realtime_voice/python_supervisor/src/realtime_voice_supervisor/models.py`
- `apps/realtime_voice/python_supervisor/src/realtime_voice_supervisor/prompts.py`
- `apps/realtime_voice/python_supervisor/src/realtime_voice_supervisor/repo_tools.py`
- `apps/realtime_voice/python_supervisor/src/realtime_voice_supervisor/git_tools.py`
- `apps/realtime_voice/python_supervisor/src/realtime_voice_supervisor/mentor.py`

The mentor currently supports:

- explain latest changes
- second opinion
- draft Claude prompt
- explain approval

Important boundary:

- mentor tooling is read-only
- mentor can inspect git state, repo files, Claude terminal state, and pending approvals
- mentor does not perform repo writes directly

### 11. Mentor v1 Browser UI

The browser UI and Node bridge now expose Mentor v1 directly.

Changed files:

- `apps/realtime_voice/public/index.html`
- `apps/realtime_voice/public/app.js`
- `apps/realtime_voice/public/styles.css`
- `apps/realtime_voice/server.mjs`

The Mentor panel now includes:

- a goal input
- `Explain latest changes`
- `Second opinion`
- `Draft prompt for Claude`
- `Explain approval`
- on-screen summary, bullets, risks, changed files, and drafted prompt output

The drafted prompt can be pushed into the existing supervisor draft box and then sent
through the normal approval-aware Claude flow.

### 8. Startup / Verification Script Changes

These scripts were updated:

- `scripts/start_realtime_voice.sh`
- `scripts/verify_realtime_voice.sh`

The startup script now intends to:

- ensure Node deps exist
- create a local Python virtualenv for the supervisor if needed
- install the supervisor package into that local venv if needed
- export `REALTIME_SUPERVISOR_PYTHON`
- then launch the Node server

### 9. Ignore Rules

`.gitignore` was updated to ignore `.runtime/` state so local supervisor state does not end up
as repo noise.

## Current State Of Validation

This distinction matters a lot for the next environment.

### Completed Validation

These checks were run successfully:

- `node --check apps/realtime_voice/server.mjs`
- `node --check apps/realtime_voice/public/app.js`
- `python3 -m py_compile` against the new Python supervisor modules
- `bash scripts/verify_realtime_voice.sh`
- local mixed-stack startup through `scripts/start_realtime_voice.sh`
- `/health` and `/api/supervisor/health`
- mentor endpoint smoke checks for:
  - `explain-latest`
  - `second-opinion`
  - `draft-claude-prompt`
  - `explain-approval`
- one real Claude tmux attach/send flow
- one approval flow
- one interrupt flow

An important integration fix was also made after runtime testing:

- mentor explanation flows now preserve pending approvals instead of accidentally clearing
  them

### Not Yet Fully Verified End To End

The following still need explicit runtime verification:

- real browser microphone/WebRTC connection using `gpt-realtime-1.5` in a live browser session
- browser rendering of Mentor panel actions in real click-through usage after cold start
- correctness of readiness detection against a broader range of real Claude terminal states

So the current implementation is best described as:

- architecturally substantial
- runtime-validated for the local supervisor and Claude terminal flows
- still awaiting a final browser-driven smoke pass for the live mic/WebRTC path

## Important Constraints And Cautions

### Do Not Change These Casually

These are machine-owned and should not be changed without asking:

- `~/.claude.json`
- `~/.cursor/mcp.json`
- `~/.voicemode/voicemode.env`
- `~/.asoundrc`
- live secrets such as `OPENAI_API_KEY`

### Runtime Assumptions

The new supervisor path assumes:

- `tmux` exists
- `claude` exists on `PATH`
- Python 3 exists
- Node exists
- browser microphone access works
- the current machine still has a valid OpenAI API key for the realtime lane

### Existing Claude Config Reuse

The new supervisor reuses:

- `apps/realtime_voice/config/claude-bridge.json`

That file still matters even though the browser UI has shifted away from the older companion
workflow, because it now effectively acts as the terminal harness config surface.

## Recommended Reading Order For Codex

A fresh Codex session should read these in roughly this order:

1. `docs/codex-handover.md`
2. `docs/session-handoff.md`
3. `docs/voice-systems.md`
4. `apps/realtime_voice/README.md`
5. `apps/realtime_voice/docs/overview.md`
6. `apps/realtime_voice/docs/design.md`
7. `apps/realtime_voice/docs/local-setup.md`
8. `apps/realtime_voice/docs/claude-bridge.md`
9. `apps/realtime_voice/server.mjs`
10. `apps/realtime_voice/public/index.html`
11. `apps/realtime_voice/public/app.js`
12. `apps/realtime_voice/python_supervisor/src/realtime_voice_supervisor/supervisor.py`
13. `apps/realtime_voice/python_supervisor/src/realtime_voice_supervisor/harness.py`
14. `scripts/start_realtime_voice.sh`
15. `scripts/verify_realtime_voice.sh`

## Suggested Next Actions For Codex

The next assistant should probably do the following in order:

1. inspect `git status` and review the modified files before changing anything else
2. do a fresh research pass against the current OpenAI API docs and Agents SDK docs
3. if blocked from direct docs access, use `Context7` MCP to retrieve those docs
4. compare the current implementation and plan against the latest documented SDK capabilities
5. run `scripts/verify_realtime_voice.sh`
6. run `scripts/start_realtime_voice.sh`
7. fix any dependency or import issues in the Python supervisor bootstrap path
8. verify the browser launches and connects with `gpt-realtime-1.5`
9. verify the supervisor endpoints work locally
10. test a real Claude tmux session attach/start flow
11. test approval pause/resume for a risky prompt
12. test interrupt behavior
13. verify the browser mic/WebRTC flow after any machine reboot or environment change
14. tighten docs to match any runtime or architecture changes discovered during validation

## Known Likely Follow-Up Issues

These are the most likely places for problems when the next environment resumes:

- Python package import path or editable install behavior
- exact Agents SDK runtime API differences from the researched examples
- `RunState` serialization/resume edge cases
- tmux prompt-ready detection being too naive
- browser UI assumptions about the shape of mentor and approval payloads
- Node-to-Python subprocess JSON bridging details
- the Claude terminal's actual visible prompt markers differing from the current readiness heuristic

## Transcript / Deep History Fallback

Use repo docs first.

If a later assistant needs deeper conversational history, the relevant prior session can be
consulted here:

- [Mixed stack voice supervisor](a8b66c77-4abb-4310-93df-38c05a860ba2)

The large exported markdown transcript also exists as fallback history:

- `cursor_exports/cursor_voice_access_setup_using_android.md`

Do not start with the full transcript unless the repo docs and this handover are missing
something specific.

## Compact Prompt For The Next Codex Session

```text
Read `docs/codex-handover.md` first, then treat the repo docs as authoritative.

Before making architectural or model-capability decisions, do an explicit docs research pass:
- check the current official OpenAI API docs
- check the current official OpenAI Agents SDK docs/repo docs
- if direct access is blocked, use `Context7` MCP to retrieve the relevant docs
- do not rely on memory alone for what the Agents SDK or current models can do

This repository has two lanes:
- stable supported lane: Claude Code + `voice-mode` MCP, pinned around `voice-mode==8.5.1`
- experimental lane: `apps/realtime_voice/`, now being upgraded into a mixed-stack architecture

Important current direction:
- browser voice stays WebRTC/browser-first
- realtime model is moving to `gpt-realtime-1.5`
- orchestration is shifting into a Python OpenAI Agents SDK supervisor
- Claude Code interaction should use structured tmux/PTY-backed terminal tools
- risky actions should be approval-gated
- `gpt-5.4` computer use is only a later fallback, not the default v1 path

Implementation work has already started in:
- `apps/realtime_voice/server.mjs`
- `apps/realtime_voice/public/index.html`
- `apps/realtime_voice/public/app.js`
- `apps/realtime_voice/python_supervisor/src/realtime_voice_supervisor/`
- `scripts/start_realtime_voice.sh`
- `scripts/verify_realtime_voice.sh`

The current implementation is runtime-validated for local supervisor and Claude terminal
flows, but still needs a final live browser mic/WebRTC smoke pass.

Before making further architectural changes:
1. inspect git state
2. research the latest OpenAI API + Agents SDK docs
3. verify startup and dependency installation
4. run the mixed stack locally
5. validate one real Claude terminal flow, one approval flow, and one interrupt flow

Do not edit machine-owned files like `~/.claude.json`, `~/.cursor/mcp.json`, `~/.voicemode/voicemode.env`, or `~/.asoundrc` without asking.
```
