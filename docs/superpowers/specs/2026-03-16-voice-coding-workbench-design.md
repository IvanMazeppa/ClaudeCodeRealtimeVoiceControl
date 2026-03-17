# Voice Coding Workbench Design

## Status

Approved design draft for the initial `voice_coding_research` project.

This document captures the agreed architecture for:

- the current Claude Code + `voice-mode` workflow
- the future OpenAI realtime voice variant
- the migration path from scattered local state to a reusable project

## Goals

The project should:

- preserve the currently working Claude Code voice workflow
- make the current setup reproducible across future machines and sessions
- keep local secrets and machine-specific runtime state out of git
- create a clean lane for a future immersive realtime voice application
- avoid tangling the current Claude Code integration with the future realtime architecture

The project should not:

- turn the current Claude Code workflow into a standalone assistant product
- depend on `PlasmaDXR` as its long-term home
- store live API keys or live user config in the repository

## Project Positioning

`voice_coding_research` should be a standalone repo beside `PlasmaDXR`, not a subproject inside it.

During migration, both folders can remain open in the same Cursor workspace to reduce friction and preserve easy cross-reference. Once the new repo is self-contained, it should also get its own dedicated workspace.

## Core Product Split

The repo will contain two sibling application tracks.

### 1. `apps/claude_code_voice`

This is the stable, practical, current-use track.

Purpose:

- preserve and package the working Claude Code voice workflow
- document setup and usage
- provide install, verify, repair, and patch utilities
- keep the spoken-summary workflow easy to start and maintain

This track owns:

- session prompts
- user instructions
- troubleshooting notes
- app-specific helper logic
- wrapper or launcher helpers if needed

This track does not try to become its own standalone assistant. Claude Code remains the decision-making layer, and `voice-mode` remains the speech transport layer.

### 2. `apps/realtime_voice`

This is the experimental, future-facing track.

Purpose:

- explore a richer and more immersive standalone voice experience
- use advanced OpenAI realtime models
- support lower-latency conversational interaction
- eventually own its own runtime and interaction model

This track is allowed to diverge from the Claude Code track in:

- APIs
- event loop design
- interaction model
- state management
- release and testing strategy

## Repo Structure

Recommended top-level structure:

```text
voice_coding_research/
  README.md
  .gitignore
  docs/
    architecture.md
    claude-code-workflow.md
    realtime-roadmap.md
    troubleshooting.md
    migration-notes.md
    superpowers/
      specs/
        2026-03-16-voice-coding-workbench-design.md
  apps/
    claude_code_voice/
      README.md
      prompts/
      docs/
      helpers/
    realtime_voice/
      README.md
      docs/
      src/
      configs/
  templates/
    claude-mcp.example.json
    cursor-mcp.example.json
    voicemode.env.example
    asoundrc.example
  scripts/
    install_claude_code_voice.sh
    verify_audio_stack.sh
    verify_voicemode.sh
    apply_voicemode_patch.sh
    sync_local_config.sh
  patches/
    voice-mode/
      8.5.1/
        cli-empty-tts.patch
```

## Ownership Rules For Shared vs App-Specific Assets

To avoid confusion later, the repository root is reserved for assets that are
shared across tracks or intentionally project-wide.

### Repository Root Owns

- cross-track documentation
- global install and verification scripts
- shared config templates
- versioned patch files for external dependencies
- migration notes and release notes

### `apps/claude_code_voice` Owns

- session prompts
- app-specific usage docs
- Claude-track helper logic
- anything that only makes sense for the Claude Code integration

### `apps/realtime_voice` Owns

- realtime app code
- realtime-only configs
- realtime app docs
- anything specific to the standalone immersive runtime

Rule of thumb:

- if an asset exists only for one app, keep it under that app
- if an asset may be shared by both tracks, keep it at the repository root

## Source of Truth Rules

### Repository-Owned

These become the source of truth in git:

- docs
- prompts
- setup scripts
- verification scripts
- repair scripts
- config templates
- versioned patch files
- future realtime app code

### Machine-Owned

These remain local runtime state and must not be committed:

- `~/.claude.json`
- `~/.cursor/mcp.json`
- `~/.voicemode/voicemode.env`
- `~/.asoundrc`
- API keys
- machine-specific audio device names
- ad hoc cache paths

The repo should contain examples and sync/install helpers, not the live files themselves.

For secrets, prefer standard environment variables over inline config values.
In particular, `OPENAI_API_KEY` should be supported as an environment variable
in both Windows and WSL so the same high-level setup works across both
environments without committing secrets into project files.

## Global Config Safety Rules

Global user config files are the highest-risk operational area in this project.

That means any automation touching these files must follow strict rules:

- never overwrite `~/.claude.json` wholesale
- never overwrite `~/.cursor/mcp.json` wholesale
- never rewrite `~/.voicemode/voicemode.env` unless the user explicitly asks for it
- never copy secrets from live local config into tracked files
- always support dry-run output before applying changes

The purpose of `sync_local_config.sh` is therefore narrowly defined:

- read local machine state
- compare it against safe repo templates or fragments
- print the proposed delta
- optionally merge known-safe fragments

`sync_local_config.sh` must be merge-only and fragment-based. It is not allowed
to replace an entire global config file.

## Current Working System Layout

At design time, the working voice system is spread across:

- `~/.cursor/mcp.json`
- `~/.claude.json`
- `~/.voicemode/voicemode.env`
- `~/.voicemode/soundfonts/.version`
- `~/.cache/uv/archive-v0/.../site-packages/voice_mode/...`
- `~/.asoundrc`
- documentation currently stored in `PlasmaDXR/docs/`

This arrangement is functional but operationally scattered. The repo exists to centralize the reproducible pieces without trying to relocate the live files that existing tools already expect.

## Migration Matrix

Each current artifact needs an explicit ownership decision.

| Current artifact | Future status | New authority |
| ---------------- | ------------- | ------------- |
| `PlasmaDXR/docs/CLAUDE_CODE_VOICE_MODE_GUIDE.md` | Migrate/copy | `voice_coding_research` |
| `PlasmaDXR/docs/CLAUDE_CODE_VOICE_WORK_MODE_PROMPT.md` | Migrate/copy | `voice_coding_research` |
| `~/.claude.json` | Stays machine-owned | local machine |
| `~/.cursor/mcp.json` | Stays machine-owned | local machine |
| `~/.voicemode/voicemode.env` | Stays machine-owned | local machine |
| `~/.asoundrc` | Stays machine-owned | local machine |
| `~/.cache/uv/archive-v0/.../voice_mode/...` live edits | External dependency only | repo patch files |
| `voice-mode` version note | Migrate/copy | `voice_coding_research` |

Authority-transfer rule:

- once a migrated doc exists in `voice_coding_research`, the new repo copy becomes authoritative
- the old `PlasmaDXR` copy becomes historical reference only until it is removed or replaced with a pointer
- live home-directory config never becomes repo-authoritative

## Migration Plan

### Phase 1: Bootstrap the New Repo

Create the repo structure and establish the top-level documents:

- `README.md`
- `docs/architecture.md`
- `docs/claude-code-workflow.md`
- `docs/realtime-roadmap.md`
- `docs/troubleshooting.md`

### Phase 2: Migrate the Current Working Claude Code Workflow

Move or adapt the following into the new repo:

- the current Claude Code voice guide
- the current session-start prompt
- a version note for the working `voice-mode` release
- a redacted description of the current local setup

At this point, the new repo becomes the authoritative home for the current voice workflow documentation.

As part of this phase:

- add a short pointer note in the old `PlasmaDXR` docs if needed
- do not continue editing both copies in parallel
- treat the new repo copy as canonical immediately after migration

### Phase 3: Capture Reproducibility

Add:

- `voicemode.env.example`
- `claude-mcp.example.json`
- `cursor-mcp.example.json`
- `asoundrc.example`
- verification scripts
- patch files and a patch-application script

This phase is what converts the setup from "working on one machine" to "repeatable on future machines."

### Phase 4: Freeze the Stable Track

Treat `apps/claude_code_voice` as the stable integration track:

- do not make it a dumping ground for speculative realtime work
- keep it focused on the Claude Code + `voice-mode` integration
- optimize for durability, repairability, and publishability

### Phase 5: Open the Realtime Track

Only after the stable track is documented and reproducible:

- begin `apps/realtime_voice`
- keep its architecture separate
- document intentional divergence rather than mixing the two approaches

## Anti-Tangle Rules

These rules keep `PlasmaDXR` and `voice_coding_research` from drifting into confusion while both remain in the same workspace.

### Boundary Rules

- All new voice-system work belongs in `voice_coding_research`.
- `PlasmaDXR` stops being the long-term home for voice docs and voice scripts.
- No new voice-specific logic should be added to `PlasmaDXR` unless it is directly required for `PlasmaDXR` itself.
- `voice_coding_research` should not import code from `PlasmaDXR`.
- Do not rely on symlinks between the repos for source files.
- If a file is migrated, copy it once, then treat the new repo copy as authoritative.

### Workspace Rules

- Keep both folders in the same Cursor workspace during migration.
- Use `PlasmaDXR` as reference material only.
- Once the new repo has its own docs, templates, scripts, and patch logic, create a dedicated workspace for it.
- Keep the combined workspace available only for cross-reference and migration work.

## Update and Durability Strategy

### Likely Durable

The following should usually survive Claude Code updates:

- MCP registration patterns
- local voice-mode configuration in home-directory files
- the general Claude Code + MCP + `voice-mode` architecture
- repo-owned prompts, docs, and templates

### Fragile Pieces

The current local `voice-mode` CLI hotfix is fragile because it lives inside an installed package cache under `uv`.

That means:

- a `voice-mode` reinstall
- a cache refresh
- a package update

could remove the live patch.

The design answer is not to keep editing cache files by hand forever. The design answer is to:

- store the patch in the repo
- record the target upstream version
- provide a script that reapplies the patch when needed

### Important Nuance

The working Claude Code MCP workflow and the patched standalone `voice-mode` CLI are related but not identical.

If the standalone `uvx voice-mode converse --continuous` command regresses later, that does not automatically imply that the Claude Code MCP workflow is broken.

## Publishing Strategy

The project is currently optimized for personal use, but the structure should assume future publication.

Recommended approach:

- keep one repo now
- keep two app tracks inside that repo
- publish only after secrets are fully removed from tracked material
- split into separate repos later only if the realtime app becomes a genuinely separate product

### Criteria for a Future Split

Split into separate repos only if one or more of these becomes true:

- the realtime app uses a substantially different tech stack
- the release cadence diverges strongly
- the target audience diverges strongly
- the shared docs/scripts/templates become minimal

Until then, one repo with two sibling apps is the correct level of separation.

## Immediate Next Actions

1. Initialize the repo structure in `voice_coding_research`.
2. Migrate the two existing voice docs from `PlasmaDXR` into the new repo.
3. Add safe local-config templates.
4. Capture the known `voice-mode` fix as a patch file.
5. Add verification and repair scripts.
6. Treat `apps/claude_code_voice` as the stable track.
7. Leave `apps/realtime_voice` as a documented future lane until the stable track is reproducible.

## Approval Record

The user approved:

- one repo rather than separate repos for now
- two app tracks inside the repo
- keeping the new repo beside `PlasmaDXR`
- shared workspace during migration
- saving this design to disk as the project blueprint
