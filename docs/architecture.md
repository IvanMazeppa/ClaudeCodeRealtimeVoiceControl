# Architecture

## Purpose

This repository separates near-term workflow stabilization from longer-term realtime voice exploration.

## Top-Level Shape

- `apps/claude_code_voice/` is the stable track for Claude Code plus voice-mode integration work.
- `apps/realtime_voice/` is the experimental track for future realtime voice research.
- `docs/` holds shared documentation that applies across both tracks.
- `patches/voice-mode/8.5.1/` holds version-scoped patch materials for the current stable voice-mode target.
- `templates/` and `scripts/` are reserved for reusable support assets and automation.

## Boundary Rules

1. Keep the stable Claude Code workflow independent from speculative realtime work.
2. Do not force shared abstractions before both tracks need them.
3. Store version-pinned assets where the version is visible in the path.
4. Treat experimental realtime materials as research until a later task defines implementation details.

## Current State

This document captures the initial scaffold only. Deeper architecture decisions will be added in later tasks after the stable workflow and realtime roadmap are expanded.
