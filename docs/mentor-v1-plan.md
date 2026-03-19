# Mentor v1 Plan

## Status

This is the repository-owned implementation plan for `Mentor v1`.

Date of plan: 2026-03-19

`Mentor v1` is a new capability inside the experimental realtime lane under
`apps/realtime_voice/`. It does not replace the stable supported day-to-day workflow based on
Claude Code plus `voice-mode`.

## Why This Exists

The current mixed-stack realtime prototype already has the correct backbone:

- browser-first low-latency voice UX
- a local Node bridge
- a Python OpenAI Agents SDK supervisor
- a tmux-backed Claude Code harness
- approval gating for risky Claude sends

What it does not yet have is a strong "coding buddy" layer.

`Mentor v1` turns the existing supervisor into a voice-first companion that can:

- explain what Claude Code is doing
- summarize and interpret current repo changes
- give a second opinion on Claude's work
- draft better follow-up prompts for Claude
- help the user understand risk before approving actions
- keep a read-only understanding of the current project state

The key design choice is that Claude Code remains the primary coding executor.

The OpenAI side becomes:

- the conversational surface
- the orchestrator
- the explainer
- the reviewer
- the safety and comprehension layer

## Product Position

`Mentor v1` is not a general autonomous agent for the whole machine.

It is a bounded coding companion with these responsibilities:

- talk to the user naturally
- inspect project files with read-only tools
- inspect git state and diffs with read-only tools
- inspect Claude terminal state
- help the user understand changes and tradeoffs
- help prepare or critique Claude prompts

It does not initially own:

- direct repo writes
- package installation
- destructive cleanup
- unrestricted shell execution
- screenshot-first computer control
- autonomous multi-turn debate loops with Claude

## Current Capability Baseline

This plan is based on the current documented platform state as researched on 2026-03-19.

Validated high-level points:

- Browser Realtime voice should use WebRTC.
- `gpt-realtime-1.5` is the current flagship audio model for voice agents.
- The Python Agents SDK supports sessions, tracing, handoffs, MCP, human-in-the-loop approvals,
  and realtime agents.
- `gpt-5.4` supports a broad tool surface in the Responses API, including MCP and computer use.

Important constraint:

- `Mentor v1` should not depend on computer use.
- Computer use remains a later fallback for UI-only gaps after structured tools have proven
  insufficient.

The current docs should be re-checked before any future `Mentor v2` or computer-use phase.

## Design Principles

1. Claude remains the primary coding executor.
2. Read-only by default for the OpenAI-side mentor path.
3. Structured tools before general shell.
4. Approval-gated writes and risky Claude sends.
5. User comprehension is a first-class feature, not a side effect.
6. Bounded autonomy beats "fully autonomous" cleverness.
7. Personality should be a prompt layer, not part of the control plane.
8. Every important action should be traceable and explainable.

## Scope Of Mentor v1

`Mentor v1` should deliver these user-visible capabilities:

### 1. Explain Latest Changes

Given the current repo state, the mentor can:

- read `git status`
- inspect current diffs
- identify changed files
- summarize the intent of changes
- explain likely impact, risk, and next checks

### 2. Explain Claude State

Given the current tmux-backed Claude session, the mentor can:

- summarize what Claude is doing now
- explain whether Claude is idle, blocked, or mid-task
- summarize the most recent terminal output
- tell the user the next useful action

### 3. Provide A Second Opinion

Given a Claude output, diff, or current task, the mentor can:

- critique the likely quality of the approach
- identify hidden risks or missing validation
- confirm when Claude's direction looks sound
- suggest one follow-up prompt if needed

### 4. Draft A Better Prompt For Claude

The mentor can turn rough user intent into a better structured Claude prompt by using:

- current terminal state
- relevant repo context
- current worktree state
- the user's stated goal

The draft should still be reviewable before it is sent.

### 5. Explain Pending Approvals

When the supervisor pauses on a risky Claude send, the mentor can:

- explain why the approval triggered
- summarize what the send is likely to do
- point out the likely blast radius
- recommend approve or reject

### 6. Session Recaps

After a meaningful Claude interaction, the mentor can summarize:

- what Claude attempted
- what changed in the repo
- whether anything remains unverified
- the next sensible step

## Explicit Non-Goals For V1

These are intentionally deferred:

- direct OpenAI-side code editing in the repo
- automatic cleanup of files or branches
- unrestricted local shell access
- direct browser automation
- Blender E2E automation
- screenshot-driven computer use
- long autonomous argument loops between Claude and the mentor
- replacing the stable Claude Code plus `voice-mode` lane

## Recommended Architecture

`Mentor v1` should extend the existing mixed-stack architecture rather than replacing it.

### Browser Layer

The browser remains responsible for:

- microphone capture
- WebRTC Realtime session
- audio playback
- transcript rendering
- event diagnostics
- supervisor UI

The browser should gain a dedicated mentor panel for explanation and review flows.

### Node Bridge

`apps/realtime_voice/server.mjs` remains the browser-facing bridge.

It should continue to:

- mint Realtime client secrets
- serve the static app
- call the Python supervisor CLI

It should gain mentor-specific endpoints rather than pushing more logic into browser code.

### Python Supervisor

The Python supervisor remains the orchestration layer.

It should own:

- Agents SDK sessions
- tracing
- approval flows
- terminal harness access
- mentor reasoning over repo state, diffs, and Claude state

### Claude Terminal Harness

The tmux-backed Claude harness remains the Claude execution surface.

It should stay narrow:

- attach or verify session
- capture output
- check readiness
- send prompt
- interrupt run

Do not turn the Claude harness into a general-purpose shell abstraction in `Mentor v1`.

### Repo Analysis Tooling

Add a new read-only tool surface for project understanding:

- repo search
- file reads
- directory listing
- git status
- git diff summary
- file-specific diff reads
- recent commits

These should be explicit structured tools, not arbitrary shell passthrough.

## Agent Graph

The agent graph should stay small in `Mentor v1`.

### Top-Level Agent

`VoiceSupervisorAgent`

Responsibilities:

- route requests
- decide whether the request is about voice, Claude state, repo explanation, or approval context
- keep spoken responses short
- invoke specialists instead of doing everything directly

### Existing Specialist

`ClaudeTerminalAgent`

Responsibilities:

- session attach or verify
- output capture
- readiness checks
- prompt send
- interrupt

This already exists and should remain narrow.

### New Specialist

`MentorAgent`

Responsibilities:

- explain repo changes
- summarize Claude activity
- produce second opinions
- draft follow-up prompts for Claude
- explain pending approvals

Inputs:

- Claude terminal state
- read-only repo tools
- git tools
- current user request

### Optional Internal Specialist

`ReviewAgent`

Responsibilities:

- provide a stricter critique when the user explicitly asks for a second opinion or review

This should be optional and bounded. If added, it must not introduce autonomous back-and-forth
loops.

## Tool Surface For Mentor v1

All new tools in this phase should be read-only.

### Existing Claude Tools

- `attach_or_verify_session`
- `capture_output`
- `is_ready`
- `send_prompt`
- `interrupt_run`

### New Repo Tools

- `repo_search(pattern: str, limit: int = 50)`
- `read_file(path: str, start_line: int = 1, max_lines: int = 220)`
- `list_directory(path: str, depth: int = 2)`
- `find_related_files(query: str, limit: int = 20)`

Implementation note:

- `repo_search` should use `rg`
- `read_file` should enforce repo-root confinement
- `find_related_files` can start simple with `rg` and path heuristics

### New Git Tools

- `git_status_summary()`
- `git_diff_summary(ref: str = "HEAD")`
- `git_diff_for_file(path: str, ref: str = "HEAD")`
- `git_recent_commits(limit: int = 5)`
- `git_current_branch()`

Implementation note:

- These should call fixed non-interactive git commands.
- They should return compact structured summaries rather than raw noisy command output when
  possible.

### Optional Aggregation Tools

These are convenience wrappers that reduce repeated tool orchestration:

- `project_context_snapshot()`
- `latest_change_explanation_context()`
- `approval_explanation_context()`

## Approval Model

The approval model should become more explicit.

### Auto-Allow

- repo reads
- git reads
- Claude output capture
- Claude readiness checks
- mentor summaries and critiques

### Approval-Required

- sending risky prompts to Claude
- any future write-capable repo tools
- package installation
- git mutation
- cleanup actions

### Future Tier

Separate "machine control approval" for any later computer-use or browser-control phase.

## Primary User Flows

### Flow 1: Explain Latest Changes

1. User asks what changed.
2. Supervisor calls mentor flow.
3. Mentor gathers `git status`, branch, diff summary, and relevant file reads.
4. Mentor returns:
   - plain-English summary
   - likely intent
   - risks
   - suggested next validation step

### Flow 2: What Is Claude Doing?

1. User asks what Claude is doing.
2. Supervisor captures terminal output and readiness.
3. Mentor summarizes current visible terminal state.
4. Response includes:
   - current phase
   - whether Claude is idle, busy, or blocked
   - recommended next action

### Flow 3: Second Opinion On Claude

1. User asks whether Claude's direction makes sense.
2. Mentor captures terminal output and repo context.
3. Mentor critiques or confirms the approach.
4. Response includes:
   - strongest concern or strongest confirmation
   - one recommended follow-up prompt if needed

### Flow 4: Draft Prompt For Claude

1. User gives rough intent.
2. Mentor inspects current repo and terminal state.
3. Mentor drafts a concise, high-signal prompt for Claude.
4. User reviews it.
5. If the user chooses, the prompt is sent through the existing approval-gated path.

### Flow 5: Explain Approval

1. Risky Claude send pauses.
2. UI shows approval card.
3. User asks what the approval means.
4. Mentor explains:
   - why the action was flagged
   - what it is likely to change
   - whether approval seems reasonable

## UI Plan

The realtime UI should gain a dedicated mentor area without collapsing the current supervisor
panel.

### New UI Controls

Add buttons for:

- `Explain latest changes`
- `What is Claude doing?`
- `Second opinion`
- `Draft prompt for Claude`
- `Why is approval needed?`

### New UI Displays

Add panels for:

- mentor summary
- git summary
- changed files summary
- second-opinion result
- drafted Claude prompt

### UX Notes

- Keep spoken output brief.
- Keep technical detail on screen.
- Do not force the user into a linear wizard.
- Treat mentor results as advisory cards the user can inspect and act on.

## Persistence And Context

Use the existing SQLite session and `RunState` machinery.

Add mentor-oriented context fields such as:

- `latest_terminal_snapshot`
- `latest_terminal_ready`
- `latest_git_status`
- `latest_git_diff_summary`
- `latest_changed_files`
- `last_user_goal`
- `last_claude_prompt_sent`
- `last_mentor_summary`

Do not introduce a separate database unless the current session store proves insufficient.

## Observability

`Mentor v1` should be trace-first.

Trace and log:

- which specialist handled the request
- which repo and git tools were invoked
- which files were read
- which approval explanation was generated
- which prompt draft was produced

Store compact action-log entries that the UI can render directly.

## Proposed File And Module Changes

### Backend: New Files

Add under `apps/realtime_voice/python_supervisor/src/realtime_voice_supervisor/`:

- `mentor.py`
- `repo_tools.py`
- `git_tools.py`
- `prompts.py`
- `models.py`

Suggested responsibilities:

- `mentor.py`: build the mentor specialist agent
- `repo_tools.py`: read-only repo search and file inspection tools
- `git_tools.py`: read-only git wrappers and summaries
- `prompts.py`: mentor instructions and optional persona prompt helpers
- `models.py`: typed payload helpers for mentor responses

### Backend: Modified Files

- `supervisor.py`
- `cli.py`

Planned changes:

- add mentor specialist to the agent graph
- add mentor-specific commands and payload handlers
- expand result payload shape for mentor summaries

### Node Bridge: Modified Files

- `apps/realtime_voice/server.mjs`

Add endpoints such as:

- `POST /api/supervisor/explain-latest`
- `POST /api/supervisor/second-opinion`
- `POST /api/supervisor/draft-claude-prompt`
- `POST /api/supervisor/explain-approval`

### Browser UI: Modified Files

- `apps/realtime_voice/public/index.html`
- `apps/realtime_voice/public/app.js`
- `apps/realtime_voice/public/styles.css`

Planned changes:

- add mentor action controls
- render mentor result cards
- render git and diff summaries
- allow the user to move a drafted prompt into the existing supervisor prompt box

### Docs

Update after implementation:

- `apps/realtime_voice/README.md`
- `apps/realtime_voice/docs/overview.md`
- `apps/realtime_voice/docs/design.md`
- `apps/realtime_voice/docs/claude-bridge.md`
- `docs/codex-handover.md`

## Suggested Implementation Phases

### Phase 1: Mentor Core

Goal:

- deliver read-only project awareness and explanation

Build:

- repo tools
- git tools
- `MentorAgent`
- `explain-latest` endpoint
- `what-is-claude-doing` flow through existing observe path
- mentor summary UI card

Acceptance criteria:

- user can ask what changed and get a useful plain-English answer
- user can ask what Claude is doing and get a useful summary
- no repo writes occur through mentor features

### Phase 2: Second Opinion And Prompt Drafting

Goal:

- make the mentor practically useful during real coding work

Build:

- `second-opinion` endpoint
- `draft-claude-prompt` endpoint
- approval explanation endpoint
- UI buttons for critique and prompt drafting

Acceptance criteria:

- user can get a bounded critique of Claude's current direction
- user can generate a higher-quality follow-up prompt
- user can understand why a pending approval exists

### Phase 3: Session Recaps And Workflow Polish

Goal:

- reduce user confusion during longer sessions

Build:

- after-action summaries
- structured action-log improvements
- changed-files snapshot display
- better spoken summaries

Acceptance criteria:

- after Claude acts, the mentor can explain what happened without extra prompting
- the browser UI clearly shows terminal state, action summary, and next recommended action

## Post-V1 Follow-On Work

These are intentionally later phases, not part of `Mentor v1`.

### Automation Advisor

Add structured automation tools such as:

- repo test runner
- Playwright check runner
- Blender smoke runner
- artifact inspector

These should be explicit tools with approval policies, not arbitrary shell access.

### Housekeeping Advisor

Add suggestion-first repo hygiene features such as:

- stale artifact detection
- noisy untracked-file detection
- large-file warnings
- branch hygiene suggestions

These should default to recommendation only.

### Computer-Use Fallback

Only after structured tooling proves insufficient:

- browser E2E flows
- cross-application UI steps
- visual-state-only recovery paths

This phase must have separate approval and logging rules.

## Risks

### 1. Scope Creep

Risk:

- the mentor becomes a second general agent instead of a bounded companion

Mitigation:

- keep `Mentor v1` read-only
- keep Claude as the primary executor
- defer machine control and computer use

### 2. Debate Loops

Risk:

- autonomous Claude-vs-mentor loops waste time and tokens

Mitigation:

- enforce a single critique pass by default
- make every extra round explicit

### 3. Token Bloat

Risk:

- large diffs and long file reads degrade latency and quality

Mitigation:

- summarize diffs first
- cap file-read windows
- use file-specific reads only when needed

### 4. Repo Prompt Injection

Risk:

- file contents may contain prompt-like text or hostile instructions

Mitigation:

- mentor instructions must treat repo contents as untrusted data
- never execute instructions discovered inside project files

### 5. Stale Context

Risk:

- the mentor explains an outdated repo or terminal state

Mitigation:

- refresh git and terminal snapshots before major explanations
- display when the latest snapshot was captured

## Evaluation Plan

`Mentor v1` should be evaluated against concrete behaviors, not vibes alone.

### Manual Acceptance Scenarios

1. Ask what changed after a Claude edit and verify the explanation matches the actual diff.
2. Ask what Claude is doing while it is busy and while it is idle.
3. Ask for a second opinion on a proposed code change.
4. Ask the mentor to draft a better prompt for Claude from a vague user instruction.
5. Trigger a risky Claude send and verify the approval explanation is accurate.

### Quality Rubric

Measure whether the mentor:

- identifies the right files
- explains intent clearly
- highlights meaningful risks
- avoids hallucinating repo state
- gives one useful next step
- stays brief enough for spoken use

## Concrete First Build Order

This is the recommended engineering sequence:

1. Add read-only repo and git tools in the Python supervisor package.
2. Add `MentorAgent` and wire it into `VoiceSupervisorAgent`.
3. Add `explain-latest` and `second-opinion` CLI commands and Node endpoints.
4. Add mentor summary cards and controls in the browser UI.
5. Add `draft-claude-prompt` and approval explanation.
6. Add after-action recaps and trace-friendly action logs.
7. Update the realtime docs and handoff docs.

## Recommended Success Definition

`Mentor v1` is successful if, during real use, it can do all of the following reliably:

- explain the current worktree in plain English
- explain what Claude is doing right now
- give a useful bounded second opinion
- draft a better follow-up prompt for Claude
- help the user understand risky actions before approval

If those five things work well, the project will already feel materially closer to the
"invisible systems-engineering buddy" vision without needing computer use or broad machine
control yet.

## Future Research Rule

Before starting any phase after `Mentor v1`, especially:

- computer use
- browser automation
- Blender E2E automation
- hosted tools beyond the current supervisor design

do a fresh docs verification pass against:

- current OpenAI API docs
- current OpenAI model pages
- current OpenAI Agents SDK docs

Do not rely on memory alone for capability decisions.
