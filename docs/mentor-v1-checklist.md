# Mentor v1 Implementation Checklist

## Purpose

This document turns `docs/mentor-v1-plan.md` into a buildable execution checklist.

It is intentionally operational:

- exact files to touch
- exact modules to add
- exact endpoints to add
- exact UI controls to add
- exact acceptance checks to run

Use this as the implementation order for `Mentor v1`.

## Ground Rules

- Keep the stable Claude Code plus `voice-mode` lane untouched.
- Keep `Mentor v1` inside the experimental realtime lane.
- Do not introduce repo-write tools for the mentor path in v1.
- Do not introduce general shell passthrough tools in v1.
- Do not depend on computer use in v1.
- Keep Claude Code as the primary coding executor.
- Keep mentor responses concise enough for spoken delivery, with detail on screen.

## Success Criteria

`Mentor v1` is done when all of these are true:

- the user can ask what changed and get a useful git-aware explanation
- the user can ask what Claude is doing and get a useful summary
- the user can ask for a second opinion on Claude's current direction
- the user can ask the mentor to draft a better prompt for Claude
- the user can ask why an approval is required and get a clear explanation
- all mentor tooling is read-only
- the current session attach/send/approval/interrupt flows still work

## Delivery Strategy

Implement `Mentor v1` in three slices:

1. backend read-only mentor core
2. Node bridge and browser UI wiring
3. verification, polish, and docs

Do not try to add automation, browser control, or computer use in the same implementation pass.

## Slice 1: Backend Read-Only Mentor Core

### 1.1 Add typed response models

Create:

- `apps/realtime_voice/python_supervisor/src/realtime_voice_supervisor/models.py`

Add models for:

- `MentorSummary`
- `ChangeExplanation`
- `SecondOpinion`
- `ClaudePromptDraft`
- `ApprovalExplanation`

Each model should include:

- `spoken_response`
- `screen_summary`
- `bullets`
- optional structured fields such as `changed_files`, `risks`, `recommended_next_step`

Definition of done:

- models import cleanly
- all response objects can be serialized to plain JSON

### 1.2 Add prompt builders

Create:

- `apps/realtime_voice/python_supervisor/src/realtime_voice_supervisor/prompts.py`

Add functions that return instruction strings for:

- mentor summary mode
- change explanation mode
- second-opinion mode
- Claude prompt drafting mode
- approval explanation mode

Important rule:

- keep personality separate from tool policy and safety rules

Definition of done:

- no prompt strings are embedded inline in `supervisor.py` except thin wiring

### 1.3 Add read-only repo tools

Create:

- `apps/realtime_voice/python_supervisor/src/realtime_voice_supervisor/repo_tools.py`

Add fixed wrappers for:

- `repo_search(pattern, limit=50)`
- `read_file(path, start_line=1, max_lines=220)`
- `list_directory(path, depth=2)`
- `find_related_files(query, limit=20)`

Implementation rules:

- constrain all paths to repo root
- reject absolute paths outside repo root
- cap line counts and result counts
- use `rg` for searches
- use direct subprocess calls with fixed arguments
- return compact structured output, not giant raw dumps

Definition of done:

- searching and file reads work on repo files
- path traversal outside repo root is rejected
- tool output is small enough to feed into an agent loop safely

### 1.4 Add read-only git tools

Create:

- `apps/realtime_voice/python_supervisor/src/realtime_voice_supervisor/git_tools.py`

Add fixed wrappers for:

- `git_current_branch()`
- `git_status_summary()`
- `git_diff_summary(ref="HEAD")`
- `git_diff_for_file(path, ref="HEAD")`
- `git_recent_commits(limit=5)`

Implementation rules:

- use non-interactive git commands only
- do not mutate git state
- return structured compact summaries where possible

Recommended commands:

- `git branch --show-current`
- `git status --short --branch`
- `git diff --stat`
- `git diff -- path`
- `git log --oneline -n <limit>`

Definition of done:

- all commands work in a dirty repo without mutating anything
- output is concise and safe for agent consumption

### 1.5 Add mentor specialist

Create:

- `apps/realtime_voice/python_supervisor/src/realtime_voice_supervisor/mentor.py`

Implement a `build_mentor_agent(...)` helper that returns the mentor specialist.

Its tools should include:

- repo tools
- git tools
- existing Claude terminal tool surface as needed through a narrow helper or specialist tool

The mentor agent should support these intents:

- explain latest changes
- explain Claude state
- second opinion
- draft Claude prompt
- explain approval

Definition of done:

- mentor agent can be imported and instantiated cleanly
- mentor agent does not require any write-capable tools

### 1.6 Extend supervisor service

Modify:

- `apps/realtime_voice/python_supervisor/src/realtime_voice_supervisor/supervisor.py`

Add:

- mentor specialist wiring into the top-level agent graph
- service methods:
  - `explain_latest_changes(session_id)`
  - `second_opinion(session_id, prompt_or_goal)`
  - `draft_claude_prompt(session_id, goal)`
  - `explain_approval(session_id, call_id)`

Recommended implementation shape:

- keep `ClaudeTerminalAgent` as-is
- add `MentorAgent`
- let `VoiceSupervisorAgent` route between them
- keep payload building centralized in `_build_result_payload`

State additions to `context`:

- `latest_git_status`
- `latest_git_diff_summary`
- `latest_changed_files`
- `last_mentor_mode`
- `last_mentor_summary`

Definition of done:

- current session attach/send/observe/interrupt behavior still works
- mentor-specific service methods return usable payloads

### 1.7 Extend CLI commands

Modify:

- `apps/realtime_voice/python_supervisor/src/realtime_voice_supervisor/cli.py`

Add commands:

- `explain-latest`
- `second-opinion`
- `draft-claude-prompt`
- `explain-approval`

Payload conventions:

- `second-opinion` takes `goal` or `userText`
- `draft-claude-prompt` takes `goal`
- `explain-approval` takes `callId`

Definition of done:

- each command runs from `python -m realtime_voice_supervisor.cli ...`
- failures return structured JSON and non-zero exit codes

## Slice 2: Node Bridge And Browser UI

### 2.1 Add Node bridge endpoints

Modify:

- `apps/realtime_voice/server.mjs`

Add endpoints:

- `POST /api/supervisor/explain-latest`
- `POST /api/supervisor/second-opinion`
- `POST /api/supervisor/draft-claude-prompt`
- `POST /api/supervisor/explain-approval`

Each endpoint should:

- pass session id through
- validate required payload fields
- return structured JSON from the Python CLI
- preserve existing error-shape conventions

Definition of done:

- each endpoint returns a stable payload shape
- existing supervisor endpoints still work unchanged

### 2.2 Add mentor UI section

Modify:

- `apps/realtime_voice/public/index.html`

Add a new panel under the existing supervisor section or directly after it.

Required controls:

- `Explain latest changes`
- `Second opinion`
- `Draft prompt for Claude`
- `Explain approval`

Required displays:

- mentor spoken summary
- mentor detail summary
- changed file list
- risk list
- drafted Claude prompt preview

Recommended element ids:

- `mentor-explain-btn`
- `mentor-second-opinion-btn`
- `mentor-draft-prompt-btn`
- `mentor-explain-approval-btn`
- `mentor-goal-input`
- `mentor-summary`
- `mentor-detail`
- `mentor-risks`
- `mentor-files`
- `mentor-draft-output`

Definition of done:

- new panel exists without breaking the current layout
- no current controls disappear or regress

### 2.3 Add mentor client logic

Modify:

- `apps/realtime_voice/public/app.js`

Add:

- DOM bindings for mentor controls
- helper request functions for new mentor endpoints
- rendering functions for mentor results
- a way to copy or load a drafted Claude prompt into `supervisor-prompt-input`

Recommended helper functions:

- `callMentorEndpoint(path, payload)`
- `renderMentorSummary(data)`
- `renderMentorFiles(files)`
- `renderMentorRisks(risks)`
- `applyDraftToSupervisorPrompt(text)`

Behavior rules:

- keep mentor errors visible in the UI
- do not overwrite existing terminal snapshot rendering
- do not collapse mentor output into the existing supervisor notes field

Definition of done:

- each mentor button calls the correct endpoint
- results render clearly on screen
- drafted prompts can be pushed into the supervisor draft box

### 2.4 Add mentor styles

Modify:

- `apps/realtime_voice/public/styles.css`

Add styles for:

- mentor panel
- mentor summary cards
- risk list
- changed-files list
- drafted prompt preview

Design rules:

- preserve current visual language
- do not create a second unrelated theme
- keep mobile stacking usable

Definition of done:

- mentor UI reads clearly on desktop and mobile
- existing supervisor grid still behaves correctly

## Slice 3: Verification, Polish, And Docs

### 3.1 Add backend sanity checks

Run:

- `python3 -m py_compile` on the supervisor package
- import checks for new modules
- direct CLI smoke calls with mock or real repo state

At minimum verify:

- `health`
- `explain-latest`
- `second-opinion`
- `draft-claude-prompt`
- `explain-approval`

Definition of done:

- backend commands succeed without runtime import errors

### 3.2 Add Node and browser syntax checks

Run:

- `node --check apps/realtime_voice/server.mjs`
- `node --check apps/realtime_voice/public/app.js`

Definition of done:

- no syntax failures

### 3.3 Extend verification script

Modify:

- `scripts/verify_realtime_voice.sh`

Add checks for:

- new Python modules exist
- mentor commands import cleanly
- mentor endpoints are represented in the server source

Keep this script lightweight.

Do not turn it into a full runtime browser test.

Definition of done:

- the script catches obvious mentor-module regressions

### 3.4 Add manual smoke checklist

Manual smoke sequence after startup:

1. `Start / verify Claude`
2. `Explain latest changes`
3. `Read Claude state`
4. `Second opinion`
5. `Draft prompt for Claude`
6. push drafted prompt into Claude draft box
7. send the draft through the existing supervisor send path
8. trigger a risky send
9. use `Explain approval`
10. approve or reject

Definition of done:

- every mentor feature can be exercised from the browser without copy-paste hacks

### 3.5 Update docs

Update:

- `apps/realtime_voice/README.md`
- `apps/realtime_voice/docs/overview.md`
- `apps/realtime_voice/docs/design.md`
- `apps/realtime_voice/docs/claude-bridge.md`
- `docs/codex-handover.md`

Add:

- what mentor does
- what mentor does not do
- new endpoints
- new UI controls
- read-only guarantee

Definition of done:

- docs match implementation rather than future intent

## Recommended PR Or Commit Breakdown

### PR 1

Backend mentor core:

- models
- prompts
- repo tools
- git tools
- mentor specialist
- CLI command extensions

### PR 2

Bridge and UI:

- Node endpoints
- mentor panel
- mentor rendering
- styles

### PR 3

Verification and docs:

- verification script updates
- manual smoke pass
- doc updates

## Exact Acceptance Checks

These are the minimum checks to declare `Mentor v1` ready.

### Check 1: Explain Latest Changes

- create or use an existing dirty worktree
- click `Explain latest changes`
- verify the mentor identifies changed files and gives a sensible summary

### Check 2: Explain Claude State

- start or attach Claude
- click `Read Claude state`
- verify the mentor can describe idle and busy states

### Check 3: Second Opinion

- give Claude a task or use an existing recent output
- ask for `Second opinion`
- verify the response references real repo or terminal context

### Check 4: Draft Prompt

- enter a vague goal
- use `Draft prompt for Claude`
- verify the draft is more concrete than the original goal
- load it into the supervisor draft box and send it successfully

### Check 5: Approval Explanation

- trigger a risky send
- use `Explain approval`
- verify the explanation matches the pending approval arguments

### Check 6: Regression Guard

- existing session attach/send/approval/interrupt flows still work

## Recommended Cut Line

If scope pressure appears, keep these items in v1:

- explain latest changes
- explain Claude state
- second opinion
- draft prompt for Claude

If something must slip, slip this first:

- explain approval

If something else must slip after that, slip this next:

- rich changed-files rendering polish

Do not cut the read-only rule.

## Explicit Deferred Work

Do not add these during `Mentor v1`:

- browser automation
- Playwright integration
- Blender smoke execution
- computer use
- repo-writing tools
- cleanup execution
- multi-round autonomous debate loops

These belong to later phases after mentor usefulness is proven.

## Immediate Next Step

Start with PR 1.

The first implementation actions should be:

1. add `models.py`
2. add `prompts.py`
3. add `repo_tools.py`
4. add `git_tools.py`
5. add `mentor.py`
6. wire the mentor specialist into `supervisor.py`
7. extend `cli.py`

Once those are working locally, move to the bridge and UI.
