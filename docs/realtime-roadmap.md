# Realtime Roadmap

## North Star

Build a browser-first voice coding workbench where the user can talk to a persistent
supervisor that feels like an active collaborator, not a stateless assistant.

The target experience is:

- low-latency voice in the browser
- a two-lane memory model with one shared Claude/project lane plus separate character-profile conversations
- live visibility into Claude's terminal work
- targeted use of hosted tools such as web search when fresh information is needed
- controlled access to project files and safe execution paths
- optional computer-use fallback for visual workflows that cannot be covered by structured state and terminal capture alone

This is a research lane for a new interaction model, not a replacement for the stable Claude
Code lane today.

## Product Direction

The realtime app is no longer just a voice transport experiment.

It is now explicitly a local-first coding companion research track centered on three roles the
same supervisor can inhabit depending on the chosen profile:

- programmer: helps plan, inspect, review, and drive coding work
- teacher: explains what is happening and why in plain language
- companion: keeps the session warm, persistent, and less mentally taxing

The interface should make it feel like the user is sitting beside a capable collaborator who can:

- hear the user naturally
- see enough of the current interface state to stay oriented
- watch Claude's live terminal output
- inspect the repository with bounded tools
- research the web when the task needs fresh information
- ask for approval before crossing risky boundaries

## Current Status

`realtime v1` is running under `apps/realtime_voice/` and currently includes:

- browser microphone capture over WebRTC
- local short-lived token minting
- live transcript and diagnostics UI
- a Python supervisor using the OpenAI Agents SDK
- a tmux-backed Claude terminal harness
- a read-only mentor layer for repo explanation and prompt drafting
- approval-gated prompt sending for risky Claude actions
- live read-only terminal monitoring in the browser

This is enough to validate the interaction loop, but it is not yet the intended product shape.

## What We Are Building Next

The next phase is about making the supervisor feel present, persistent, and grounded in the
actual session.

### Phase 1: Persistent Context And Interface Awareness

Goal:
Give the supervisor durable awareness of the active browser session so it stops feeling like a
fresh agent on every turn.

Deliverables:

- structured browser-state sync from the UI to the Python supervisor
- persistent profile memory for active character, style, goal, and recent conversation state
- a shared project lane that stays stable while the user switches between teacher, programmer, or companion profiles
- visible confirmation in the UI that the supervisor has the right profile and context
- mentor and supervisor runs that can use this memory instead of relying only on the latest request

Out of scope:

- arbitrary file writes
- arbitrary shell execution
- screenshot-driven control as a default path

### Phase 2: Research And Knowledge Tools

Goal:
Let the supervisor pull in fresh information when the task actually depends on current external
state.

Deliverables:

- a dedicated research specialist with hosted web search
- explicit tool-routing rules so local repo tools, web search, and mentor tools do not overlap blindly
- citations or source summaries for research-heavy answers

Out of scope:

- general-purpose browsing everywhere by default
- replacing local repo inspection with web tools

### Phase 2.5: Interactive Terminal In The Browser

Goal:
Give the user direct keyboard access to the Claude Code terminal session from the
browser so menus, confirmations, and interactive prompts are usable without the
voice agent narrating every keystroke.

Deliverables:

- xterm.js terminal widget embedded in the browser UI
- WebSocket bridge (Node server) that attaches to the existing tmux session
- bidirectional I/O: user types in the browser, output streams back live
- voice agent and browser terminal share the same tmux session — the agent can
  still read and send keys alongside the user
- the existing terminal snapshot panel remains as a read-only summary view

Out of scope:

- replacing tmux with node-pty for the primary session
- giving the voice agent pixel-level screen understanding through the browser terminal

### Phase 3: Workspace Interaction

Goal:
Let the supervisor act on the local project in a controlled, reviewable way.

Deliverables:

- bounded workspace tools for reading, searching, and selected writes
- narrow execution tools for approved commands only
- stronger approval categories for edits, installs, server starts, and destructive actions
- traces and action summaries that make supervisor behavior legible

Out of scope:

- unrestricted shell access
- silent autonomous edits without a clear approval model

### Phase 4: Visual Supervision And Computer Use

Goal:
Fill the remaining visibility gaps for browser and UI workflows that structured state cannot
cover.

Deliverables:

- optional screenshot feeds or isolated browser harnesses
- a separate computer-use specialist rather than making all supervisor turns screenshot-first
- approval-gated UI actions for high-impact interactions

Out of scope:

- replacing the tmux Claude harness with computer use
- running visual automation on the host machine without isolation

### Phase 5: Polished Role Profiles

Goal:
Make the same underlying system feel intentionally different across programmer, teacher, and
companion modes.

Deliverables:

- profile-specific prompts and memory shaping
- profile-aware response behavior in both voice and on-screen summaries
- clearer UX for switching roles without losing session continuity

## Immediate Working Plan

The current implementation priority order is:

1. persistent context and interface awareness
2. research specialist with hosted web search
3. bounded workspace interaction
4. computer-use fallback
5. profile polish and evaluation

That order is intentional:

- persistent context makes the whole system feel coherent
- research is useful early and relatively safe
- workspace power should come after context and approval boundaries are clearer
- computer use is valuable, but only after we know exactly what structured state still misses

## Architecture Principles

The roadmap assumes these principles stay in place:

- browser-first voice remains the transport layer
- the Python supervisor remains the reasoning and orchestration layer
- Claude terminal interaction stays text-native and tmux-backed by default
- specialized agents are preferred over a single monolithic supervisor
- approvals stay explicit around risky actions
- traces and local state should make the system debuggable

## What Must Remain Separate

The following still must remain separate from `apps/claude_code_voice/` unless a real shared
need is proven later:

- runtime processes and entrypoints
- transport assumptions
- prompts and presets specific to the realtime experience
- browser UI implementation details
- supervisor-specific orchestration and memory state

The stable Claude Code lane remains the supported day-to-day path.

## Success Criteria For This Track

This roadmap is working if the user can honestly say:

- "The supervisor remembers what we are doing."
- "It understands the interface it is sitting inside."
- "It can see Claude's work without me narrating everything."
- "It only asks for approval when the boundary actually matters."
- "It feels more like collaborating with a programmer, teacher, or companion than operating a demo."

## Near-Term Milestone

The next milestone for `realtime v1` is:

- supervisor session memory for profile and goal state
- structured browser-state sync into the supervisor
- visible supervisor memory summary in the interface
- the first research-specialist design pass queued up behind that work
