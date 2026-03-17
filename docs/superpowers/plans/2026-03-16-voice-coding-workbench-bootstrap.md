# Voice Coding Workbench Bootstrap Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bootstrap `voice_coding_research` as the new source of truth for the current Claude Code voice workflow while reserving a clean, separate lane for the future realtime voice application.

**Architecture:** Build one standalone repo with two app tracks: `apps/claude_code_voice` for the stable Claude Code + `voice-mode` integration and `apps/realtime_voice` for future experimental work. Keep live machine configuration outside git, store only safe templates and patch files in the repo, migrate the current working docs out of `PlasmaDXR` so the new repo becomes authoritative, and treat `voice-mode==8.5.1` as the pinned stable baseline for the Claude track until deliberately changed.

**Tech Stack:** Markdown, Bash, JSON templates, environment-variable-based config, Claude Code MCP, `voice-mode`, OpenAI STT/TTS, git.

---

## Proposed File Structure

### Repository Root

- `README.md`
  Project overview, architecture summary, and navigation to both app tracks.
- `.gitignore`
  Prevents live secrets, local env files, generated artifacts, and machine-specific state from entering git.
- `docs/architecture.md`
  Repo-level architecture, ownership rules, and the stable-track vs realtime-track split.
- `docs/claude-code-workflow.md`
  Canonical narrative for the currently working Claude Code voice workflow.
- `docs/realtime-roadmap.md`
  Placeholder roadmap for the future immersive voice app.
- `docs/troubleshooting.md`
  Central troubleshooting index for audio stack, MCP registration, updates, and repair steps.
- `docs/migration-notes.md`
  Records what moved from `PlasmaDXR`, what stayed local, and when the new repo became authoritative.
- `templates/claude-mcp.example.json`
  Safe Claude-side MCP example using `OPENAI_API_KEY` via environment variables rather than inline secrets.
- `templates/cursor-mcp.example.json`
  Safe Cursor-side MCP example using environment variables.
- `templates/voicemode.env.example`
  Safe example for `voice-mode` settings with `gpt-4o-mini-tts`, `shimmer`, and comments about Windows/WSL use.
- `templates/asoundrc.example`
  ALSA-to-Pulse bridge template for WSL audio.
- `patches/voice-mode/8.5.1/cli-empty-tts.patch`
  Versioned patch that captures the standalone CLI fix already discovered locally.
- `scripts/install_claude_code_voice.sh`
  Guided setup helper for the stable Claude Code voice track.
- `scripts/verify_audio_stack.sh`
  Verifies the WSL audio prerequisites and basic input/output assumptions.
- `scripts/verify_voicemode.sh`
  Verifies one-shot `voice-mode` speech and the MCP-oriented basics.
- `scripts/apply_voicemode_patch.sh`
  Finds the installed `voice-mode` path and reapplies the tracked patch safely.
- `scripts/sync_local_config.sh`
  Dry-run, fragment-based helper for inspecting or merging safe config fragments into local machine-owned files without replacing them wholesale.

### `apps/claude_code_voice`

- `apps/claude_code_voice/README.md`
  Track-specific overview for the stable integration path.
- `apps/claude_code_voice/prompts/session_start.md`
  Canonical voice work mode prompt for Claude Code sessions.
- `apps/claude_code_voice/docs/local-setup-notes.md`
  Redacted description of the current known-good local setup and assumptions.
- `apps/claude_code_voice/docs/voice-mode-8.5.1.md`
  Notes about the working dependency version, known behavior, and patch applicability.

### `apps/realtime_voice`

- `apps/realtime_voice/README.md`
  Placeholder for the future standalone voice app, including non-goals for Phase 1.
- `apps/realtime_voice/docs/overview.md`
  Early placeholder describing what this track is for and why it is deliberately separate.

## Chunk 1: Repository Bootstrap And Canonical Docs

### Task 1: Initialize The Repo And Create The Skeleton

**Files:**

- Create: `/home/maz3ppa/projects/voice_coding_research/README.md`
- Create: `/home/maz3ppa/projects/voice_coding_research/.gitignore`
- Create: `/home/maz3ppa/projects/voice_coding_research/docs/architecture.md`
- Create: `/home/maz3ppa/projects/voice_coding_research/docs/claude-code-workflow.md`
- Create: `/home/maz3ppa/projects/voice_coding_research/docs/realtime-roadmap.md`
- Create: `/home/maz3ppa/projects/voice_coding_research/docs/troubleshooting.md`
- Create: `/home/maz3ppa/projects/voice_coding_research/docs/migration-notes.md`
- Create: `/home/maz3ppa/projects/voice_coding_research/apps/claude_code_voice/README.md`
- Create: `/home/maz3ppa/projects/voice_coding_research/apps/realtime_voice/README.md`
- Create: `/home/maz3ppa/projects/voice_coding_research/apps/realtime_voice/docs/overview.md`

- [ ] **Step 1: Verify whether the new folder is already a git repo**

Run: `git -C /home/maz3ppa/projects/voice_coding_research rev-parse --is-inside-work-tree`
Expected:

- Either `true`, or
- a non-zero exit showing the folder still needs `git init`

- [ ] **Step 2: Initialize git if needed**

Run: `git -C /home/maz3ppa/projects/voice_coding_research init`
Expected: Git initializes the repo and creates `.git/`

- [ ] **Step 3: Create the base directory tree**

Run:

```bash
mkdir -p \
  /home/maz3ppa/projects/voice_coding_research/docs \
  /home/maz3ppa/projects/voice_coding_research/templates \
  /home/maz3ppa/projects/voice_coding_research/scripts \
  /home/maz3ppa/projects/voice_coding_research/patches/voice-mode/8.5.1 \
  /home/maz3ppa/projects/voice_coding_research/apps/claude_code_voice/prompts \
  /home/maz3ppa/projects/voice_coding_research/apps/claude_code_voice/docs \
  /home/maz3ppa/projects/voice_coding_research/apps/realtime_voice/docs
```

Expected: directories exist with no errors

- [ ] **Step 4: Write the initial root docs and placeholders**

Minimum content expectations:

```markdown
# voice_coding_research

Two-track voice coding workspace:
- `apps/claude_code_voice`: stable Claude Code + voice-mode integration
- `apps/realtime_voice`: future experimental realtime voice app
```

```gitignore
.env
.env.*
*.local.json
*.local.md
*.secrets
__pycache__/
.DS_Store
```

- [ ] **Step 5: Verify the scaffold exists**

Run:

```bash
test -f /home/maz3ppa/projects/voice_coding_research/README.md && \
test -f /home/maz3ppa/projects/voice_coding_research/.gitignore && \
test -f /home/maz3ppa/projects/voice_coding_research/docs/architecture.md && \
test -f /home/maz3ppa/projects/voice_coding_research/apps/claude_code_voice/README.md && \
test -f /home/maz3ppa/projects/voice_coding_research/apps/realtime_voice/README.md && \
echo "bootstrap-ok"
```

Expected: `bootstrap-ok`

- [ ] **Step 6: Commit the bootstrap**

```bash
git -C /home/maz3ppa/projects/voice_coding_research add \
  README.md .gitignore docs apps
git -C /home/maz3ppa/projects/voice_coding_research commit -m "chore: bootstrap voice coding research repo"
```

### Task 2: Migrate The Current Working Claude Code Voice Docs

**Files:**

- Modify: `/home/maz3ppa/projects/voice_coding_research/docs/claude-code-workflow.md`
- Create: `/home/maz3ppa/projects/voice_coding_research/apps/claude_code_voice/prompts/session_start.md`
- Create: `/home/maz3ppa/projects/voice_coding_research/apps/claude_code_voice/docs/local-setup-notes.md`
- Create: `/home/maz3ppa/projects/voice_coding_research/apps/claude_code_voice/docs/voice-mode-8.5.1.md`
- Source reference: `/home/maz3ppa/projects/PlasmaDXR/docs/CLAUDE_CODE_VOICE_MODE_GUIDE.md`
- Source reference: `/home/maz3ppa/projects/PlasmaDXR/docs/CLAUDE_CODE_VOICE_WORK_MODE_PROMPT.md`

- [ ] **Step 1: Copy and adapt the canonical workflow guide**

Use the content from the existing `PlasmaDXR` guide as the starting point, but rewrite it so it no longer implies `PlasmaDXR` is the authoritative home.

Key required additions:

- this repo is now the source of truth
- `OPENAI_API_KEY` should be supported via environment variable in both Windows and WSL
- the stable track is Claude Code + MCP, not the standalone CLI

- [ ] **Step 2: Move the session-start prompt into the stable track**

Write `/home/maz3ppa/projects/voice_coding_research/apps/claude_code_voice/prompts/session_start.md` using the approved voice work mode prompt as the canonical version.

Expected starter content:

```text
You are in voice work mode for this session.
Use the `voice-mode` MCP `converse` tool for spoken interaction whenever a spoken reply is helpful.
...
Start by speaking: "Voice work mode active. What would you like to do?"
```

- [ ] **Step 3: Add a redacted local setup note**

Write `/home/maz3ppa/projects/voice_coding_research/apps/claude_code_voice/docs/local-setup-notes.md` documenting:

- Android mic to Windows path
- WSL audio bridge
- Claude Code MCP registration
- `voice-mode` config location
- no live secrets

- [ ] **Step 4: Add a working dependency version note**

Write `/home/maz3ppa/projects/voice_coding_research/apps/claude_code_voice/docs/voice-mode-8.5.1.md` with:

- the tested version
- what worked
- the standalone CLI limitation
- the local patch requirement for the CLI path

- [ ] **Step 5: Run a repo-wide redaction scrub before committing docs**

Manually review the new files from this task and scrub:

- live API keys
- email addresses
- unnecessary machine-specific usernames
- unnecessary device names
- local-only details that do not belong in public-facing docs

Then run:

```bash
if rg -n "sk-[A-Za-z0-9_-]+|ctx7sk-|gmail\\.com" /home/maz3ppa/projects/voice_coding_research; then
  echo "redaction-failed"
else
  echo "redaction-clean"
fi
```

Expected: `redaction-clean`

- [ ] **Step 6: Verify that the new repo now contains the canonical docs**

Run:

```bash
rg -n "Voice work mode active|gpt-4o-mini-tts|OPENAI_API_KEY" \
  /home/maz3ppa/projects/voice_coding_research
```

Expected:

- matches in the new repo docs and prompt files
- no dependency on the old `PlasmaDXR` docs for canonical wording

- [ ] **Step 7: Commit the documentation migration**

```bash
git -C /home/maz3ppa/projects/voice_coding_research add docs apps/claude_code_voice
git -C /home/maz3ppa/projects/voice_coding_research commit -m "docs: migrate claude code voice workflow"
```

### Task 3: Add Migration Pointers To The Old `PlasmaDXR` Docs

**Files:**

- Modify: `/home/maz3ppa/projects/PlasmaDXR/docs/CLAUDE_CODE_VOICE_MODE_GUIDE.md`
- Modify: `/home/maz3ppa/projects/PlasmaDXR/docs/CLAUDE_CODE_VOICE_WORK_MODE_PROMPT.md`
- Modify: `/home/maz3ppa/projects/voice_coding_research/docs/migration-notes.md`

- [ ] **Step 1: Add a short note to the old guide**

Add a brief note near the top of the `PlasmaDXR` guide saying the canonical copy now lives in:

`/home/maz3ppa/projects/voice_coding_research/docs/claude-code-workflow.md`

- [ ] **Step 2: Add a short note to the old prompt**

Add a brief note near the top of the `PlasmaDXR` prompt saying the canonical copy now lives in:

`/home/maz3ppa/projects/voice_coding_research/apps/claude_code_voice/prompts/session_start.md`

- [ ] **Step 3: Record the migration in `docs/migration-notes.md`**

Include:

- what was migrated
- what remained machine-local
- the date the new repo became authoritative

- [ ] **Step 4: Verify the old docs now point forward**

Run:

```bash
rg -n "canonical copy now lives" \
  /home/maz3ppa/projects/PlasmaDXR/docs/CLAUDE_CODE_VOICE_MODE_GUIDE.md \
  /home/maz3ppa/projects/PlasmaDXR/docs/CLAUDE_CODE_VOICE_WORK_MODE_PROMPT.md
```

Expected: both files contain pointer text

- [ ] **Step 5: Commit the migration note in the new repo first**

```bash
git -C /home/maz3ppa/projects/voice_coding_research add docs/migration-notes.md
git -C /home/maz3ppa/projects/voice_coding_research commit -m "docs: record voice docs migration"
```

- [ ] **Step 6: Commit the historical pointer notes in `PlasmaDXR`**

```bash
git -C /home/maz3ppa/projects/PlasmaDXR add \
  docs/CLAUDE_CODE_VOICE_MODE_GUIDE.md \
  docs/CLAUDE_CODE_VOICE_WORK_MODE_PROMPT.md
git -C /home/maz3ppa/projects/PlasmaDXR commit -m "docs: point voice docs to new canonical repo"
```

## Chunk 2: Reproducibility, Safe Templates, And Repair Tooling

### Task 4: Create Safe Templates For Local Config

**Files:**

- Create: `/home/maz3ppa/projects/voice_coding_research/templates/claude-mcp.example.json`
- Create: `/home/maz3ppa/projects/voice_coding_research/templates/cursor-mcp.example.json`
- Create: `/home/maz3ppa/projects/voice_coding_research/templates/voicemode.env.example`
- Create: `/home/maz3ppa/projects/voice_coding_research/templates/asoundrc.example`

- [ ] **Step 1: Write safe MCP examples**

Use example structure only. Do not inline any real API key.

Expected JSON pattern:

```json
{
  "mcpServers": {
    "voice-mode": {
      "type": "stdio",
      "command": "uvx",
      "args": ["--from", "voice-mode==8.5.1", "voice-mode"],
      "env": {
        "OPENAI_API_KEY": "${OPENAI_API_KEY}"
      }
    }
  }
}
```

- [ ] **Step 2: Write `voicemode.env.example`**

Required example entries:

```dotenv
VOICEMODE_TTS_BASE_URLS=https://api.openai.com/v1
VOICEMODE_STT_BASE_URLS=https://api.openai.com/v1
VOICEMODE_VOICES=shimmer,nova,af_sky
VOICEMODE_TTS_MODELS=gpt-4o-mini-tts,tts-1-hd,tts-1
```

Also add comments explaining that `OPENAI_API_KEY` should be available in both Windows and WSL environments.

- [ ] **Step 3: Write `asoundrc.example`**

Expected minimal content:

```text
pcm.!default {
  type pulse
}
ctl.!default {
  type pulse
}
```

- [ ] **Step 4: Verify there are no live secrets in templates**

Run:

```bash
if rg -n "sk-[A-Za-z0-9_-]+" /home/maz3ppa/projects/voice_coding_research/templates; then
  echo "secret-leak"
else
  echo "templates-clean"
fi
```

Expected: `templates-clean`

- [ ] **Step 5: Commit the templates**

```bash
git -C /home/maz3ppa/projects/voice_coding_research add templates
git -C /home/maz3ppa/projects/voice_coding_research commit -m "chore: add safe voice config templates"
```

### Task 5: Capture The `voice-mode` Patch As A Real Artifact

**Files:**

- Create: `/home/maz3ppa/projects/voice_coding_research/patches/voice-mode/8.5.1/cli-empty-tts.patch`
- Modify: `/home/maz3ppa/projects/voice_coding_research/apps/claude_code_voice/docs/voice-mode-8.5.1.md`

- [ ] **Step 1: Reconstruct the exact CLI fix as a patch file**

The patch must describe the follow-up change in the standalone continuous loop:

- empty follow-up turn
- forced listen-only behavior
- no empty-string TTS call

- [ ] **Step 2: Document when the patch is required**

In `voice-mode-8.5.1.md`, clearly say:

- Claude Code MCP path works without depending on the standalone continuous loop
- standalone `uvx voice-mode converse --continuous` may require this patch for version `8.5.1`

- [ ] **Step 3: Verify the patch file and docs are linked**

Run:

```bash
rg -n "cli-empty-tts.patch|standalone|continuous" \
  /home/maz3ppa/projects/voice_coding_research/patches \
  /home/maz3ppa/projects/voice_coding_research/apps/claude_code_voice/docs/voice-mode-8.5.1.md
```

Expected:

- patch filename appears
- docs mention the standalone loop limitation

- [ ] **Step 4: Commit the patch capture**

```bash
git -C /home/maz3ppa/projects/voice_coding_research add \
  patches/voice-mode/8.5.1/cli-empty-tts.patch \
  apps/claude_code_voice/docs/voice-mode-8.5.1.md
git -C /home/maz3ppa/projects/voice_coding_research commit -m "fix: capture standalone voice-mode patch"
```

### Task 6: Add Verification And Repair Scripts

**Files:**

- Create: `/home/maz3ppa/projects/voice_coding_research/scripts/verify_audio_stack.sh`
- Create: `/home/maz3ppa/projects/voice_coding_research/scripts/verify_voicemode.sh`
- Create: `/home/maz3ppa/projects/voice_coding_research/scripts/apply_voicemode_patch.sh`
- Create: `/home/maz3ppa/projects/voice_coding_research/scripts/install_claude_code_voice.sh`
- Create: `/home/maz3ppa/projects/voice_coding_research/scripts/sync_local_config.sh`

- [ ] **Step 1: Define the safety contract for `install_claude_code_voice.sh`**

The installer must:

- default to non-destructive behavior
- never overwrite `~/.claude.json` wholesale
- never overwrite `~/.cursor/mcp.json` wholesale
- never overwrite `~/.voicemode/voicemode.env` unless explicitly asked
- prefer printing next steps and merge suggestions over silent mutation
- treat `voice-mode==8.5.1` as the pinned stable dependency unless the user explicitly opts into experimentation

Write these rules into the installer comments and user-facing output.

- [ ] **Step 2: Write `verify_audio_stack.sh`**

It should check for:

- `~/.asoundrc`
- ALSA/Pulse packages or commands
- basic WSL audio assumptions

Minimum script shape:

```bash
#!/usr/bin/env bash
set -euo pipefail

test -f "$HOME/.asoundrc"
command -v arecord >/dev/null
command -v pactl >/dev/null || true
echo "audio-stack-ok"
```

- [ ] **Step 3: Write `verify_voicemode.sh`**

It should:

- confirm `uvx` exists
- confirm the pinned stable command can launch
- perform a one-shot no-wait speech test

Expected smoke command:

```bash
uvx --from voice-mode==8.5.1 voice-mode converse --message "Voice check." --no-wait
```

- [ ] **Step 4: Write `apply_voicemode_patch.sh`**

It should:

- locate the installed `voice_mode/cli.py`
- confirm target version assumptions
- dry-run first if possible
- apply `patches/voice-mode/8.5.1/cli-empty-tts.patch`
- never silently patch multiple installs

- [ ] **Step 5: Write `sync_local_config.sh` safely**

This script must:

- default to dry-run
- work with fragments only
- never overwrite `~/.claude.json` or `~/.cursor/mcp.json` wholesale
- print a clear warning if a live file already contains unrelated settings

Expected top-of-file warning:

```bash
echo "This script performs merge-only config suggestions. It never replaces whole config files."
```

- [ ] **Step 6: Verify script syntax**

Run:

```bash
set -e
bash -n /home/maz3ppa/projects/voice_coding_research/scripts/verify_audio_stack.sh
bash -n /home/maz3ppa/projects/voice_coding_research/scripts/verify_voicemode.sh
bash -n /home/maz3ppa/projects/voice_coding_research/scripts/apply_voicemode_patch.sh
bash -n /home/maz3ppa/projects/voice_coding_research/scripts/install_claude_code_voice.sh
bash -n /home/maz3ppa/projects/voice_coding_research/scripts/sync_local_config.sh
echo "scripts-ok"
```

Expected: `scripts-ok`

- [ ] **Step 7: Commit the operational tooling**

```bash
git -C /home/maz3ppa/projects/voice_coding_research add scripts
git -C /home/maz3ppa/projects/voice_coding_research commit -m "chore: add voice verification and repair scripts"
```

### Task 7: Reserve The Realtime Track Without Building It Yet

**Files:**

- Modify: `/home/maz3ppa/projects/voice_coding_research/apps/realtime_voice/README.md`
- Modify: `/home/maz3ppa/projects/voice_coding_research/docs/realtime-roadmap.md`
- Modify: `/home/maz3ppa/projects/voice_coding_research/docs/architecture.md`

- [ ] **Step 1: Write a non-goals-first README for `apps/realtime_voice`**

It must explicitly say:

- this track is not implemented yet
- it is intentionally separate from the Claude Code integration track
- no shared runtime should be assumed

- [ ] **Step 2: Write `docs/realtime-roadmap.md`**

Include:

- why the realtime track exists
- what is deferred
- what must remain separate from `apps/claude_code_voice`

- [ ] **Step 3: Cross-link the architecture docs**

`docs/architecture.md` should name:

- the stable integration lane
- the experimental realtime lane
- the rule that root-level assets are shared and app-level assets are track-specific

- [ ] **Step 4: Verify no code was added to the realtime track yet**

Run:

```bash
if rg -n "responses.create|realtime|websocket|audio stream" \
  /home/maz3ppa/projects/voice_coding_research/apps/realtime_voice/src; then
  echo "unexpected-runtime-code"
else
  echo "realtime-placeholder-only"
fi
```

Expected:

- if `src/` does not exist yet, adapt the check to confirm placeholder-only structure
- final result should effectively confirm no real runtime implementation was added

- [ ] **Step 5: Commit the realtime placeholder lane**

```bash
git -C /home/maz3ppa/projects/voice_coding_research add \
  apps/realtime_voice docs/realtime-roadmap.md docs/architecture.md
git -C /home/maz3ppa/projects/voice_coding_research commit -m "docs: reserve realtime voice track"
```
