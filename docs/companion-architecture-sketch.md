# Companion Architecture Sketch

## Problem

The current system splits the AI companion across two models:

- `gpt-realtime-1.5` in the browser: voice I/O only, no tools, no memory, stateless
- `gpt-5.4` in the Python supervisor: tools, memory, reasoning, but only reachable via
  subprocess-per-request through the Node server

The user talks to the voice model, but the voice model cannot inspect the terminal, read
the repo, or remember what happened last turn. The supervisor can do all that, but it
never speaks. The result feels like two agents instead of one collaborator.

## Target

One voice. One identity. The companion hears the user, thinks with tools, and speaks the
answer — all in a single conversational turn.

## How the Agents SDK enables this

`RealtimeAgent` supports `function_tool` directly. When the voice model decides it needs
to call a tool, the `RealtimeSession` executes the tool and feeds the result back inline.
The model then speaks a response that incorporates the tool output. No subprocess hop, no
separate conversation thread.

## Proposed stack

```
Browser (mic + speaker + UI)
  │
  │  WebRTC (audio) ←→ OpenAI Realtime API
  │
  │  WebSocket ←→ Python companion server
  │                  │
  │                  ├── RealtimeSession (manages the Realtime API connection)
  │                  │     └── CompanionAgent (RealtimeAgent with tools)
  │                  │           ├── terminal tools (capture, send, interrupt)
  │                  │           ├── git tools (branch, status, diff, commits)
  │                  │           ├── repo tools (search, read, list)
  │                  │           └── mentor tools (deep analysis via Runner.run)
  │                  │
  │                  ├── session memory (SQLite + JSON profile files)
  │                  └── approval gate (risky-prompt detection)
  │
  Node server (static files + token minting only)
```

### What changes

1. **Python becomes a long-running server** (FastAPI or plain asyncio WebSocket server),
   not a subprocess. It holds the `RealtimeSession` for the lifetime of the voice
   connection.

2. **The Realtime API connection moves to Python.** The browser still does WebRTC for
   audio, but the Python server is the one creating the session and managing tool calls.
   The browser connects to the Realtime API for audio transport and to the Python server
   via WebSocket for UI state (transcripts, approvals, terminal output, memory).

3. **The Node server thins out.** It serves static files, mints ephemeral tokens, and
   proxies the WebSocket connection to Python. The `/api/supervisor/*` routes disappear
   because the Python server handles everything directly.

4. **The voice model gets tools.** Instead of being a dumb prompt-reader, the
   `RealtimeAgent` can call `capture_terminal`, `git_status`, `send_prompt_to_claude`,
   etc. The model decides when to use them based on the conversation.

## Concrete module layout

```
python_supervisor/src/realtime_voice_supervisor/
├── __init__.py
├── companion.py          # NEW: RealtimeAgent + tool definitions
├── companion_server.py   # NEW: WebSocket server, RealtimeSession lifecycle
├── deep_analysis.py      # RENAMED from mentor.py: gpt-5.4 agents for heavy tasks
├── git_tools.py          # UNCHANGED
├── harness.py            # UNCHANGED
├── memory.py             # NEW: extracted from SupervisorService memory methods
├── models.py             # UNCHANGED
├── prompts.py            # EXTENDED: add companion base instructions
├── repo_tools.py         # UNCHANGED
├── supervisor.py          # KEEP for now as fallback / migration bridge
├── cli.py                 # KEEP for now, add `serve` command
```

## companion.py — the core

```python
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agents import Agent, Runner, SQLiteSession, function_tool, trace
from agents.realtime import RealtimeAgent
from agents.run_context import RunContextWrapper

from .git_tools import GitToolbox
from .harness import ClaudeTerminalHarness
from .memory import MemoryStore
from .models import ChangeExplanation, ClaudePromptDraft, SecondOpinion
from .prompts import companion_instructions, prompt_drafter_instructions
from .repo_tools import RepoToolbox


RISKY_PROMPT_MARKERS = (
    "edit ", "modify ", "change ", "write ", "create ", "apply patch",
    "delete ", "remove ", "rename ", "commit", "checkout", "reset",
    "rebase", "npm install", "pip install", "cargo add", "apt ",
    "git ", "start server", "launch",
)


def build_companion(
    repo_root: Path,
    harness: ClaudeTerminalHarness,
    memory_store: MemoryStore,
    deep_analysis_model: str = "gpt-5.4",
) -> RealtimeAgent[dict[str, Any]]:
    """Build the single voice companion agent with all tools."""

    git = GitToolbox(repo_root)
    repo = RepoToolbox(repo_root)

    # ── Terminal tools (the companion can see and drive Claude) ───────

    @function_tool
    async def check_claude_status(ctx: RunContextWrapper[dict[str, Any]]) -> str:
        """Check whether the Claude Code terminal session exists and is ready."""
        state = await harness.get_terminal_state()
        return json.dumps({
            "session_exists": state["session_exists"],
            "ready": state["ready"],
        })

    @function_tool
    async def see_claude_terminal(ctx: RunContextWrapper[dict[str, Any]]) -> str:
        """Read the visible output from the Claude Code terminal."""
        state = await harness.get_terminal_state()
        return state.get("output", "(no output)")

    @function_tool
    async def start_claude_session(ctx: RunContextWrapper[dict[str, Any]]) -> str:
        """Ensure the Claude Code tmux session is running."""
        created = await harness.ensure_session()
        state = await harness.get_terminal_state()
        if created:
            return "Started a new Claude session. " + state.get("output", "")
        return "Claude session already running. " + state.get("output", "")

    @function_tool
    async def send_to_claude(ctx: RunContextWrapper[dict[str, Any]], prompt: str) -> str:
        """Send a prompt to Claude Code. The companion must describe what it is
        sending and why before calling this tool."""
        output = await harness.send_prompt(prompt, settle_ms=1200)
        return output or "(prompt sent, waiting for Claude to respond)"

    @function_tool
    async def interrupt_claude(ctx: RunContextWrapper[dict[str, Any]]) -> str:
        """Send Ctrl+C to interrupt Claude Code's current work."""
        output = await harness.interrupt()
        return output or "(interrupt sent)"

    # ── Git tools (the companion can see repo state) ─────────────────

    @function_tool
    async def git_branch(ctx: RunContextWrapper[dict[str, Any]]) -> str:
        """Show the current git branch."""
        return await git.git_current_branch()

    @function_tool
    async def git_status(ctx: RunContextWrapper[dict[str, Any]]) -> str:
        """Show a concise git status summary."""
        return await git.git_status_summary()

    @function_tool
    async def git_diff(ctx: RunContextWrapper[dict[str, Any]], ref: str = "HEAD") -> str:
        """Show a diff summary against the given git ref."""
        return await git.git_diff_summary(ref=ref)

    @function_tool
    async def git_log(ctx: RunContextWrapper[dict[str, Any]], limit: int = 5) -> str:
        """Show recent commits."""
        return await git.git_recent_commits(limit=limit)

    # ── Repo tools (the companion can read the project) ──────────────

    @function_tool
    async def search_repo(ctx: RunContextWrapper[dict[str, Any]], pattern: str) -> str:
        """Search the repository for files matching a text pattern."""
        return await repo.repo_search(pattern)

    @function_tool
    async def read_file(ctx: RunContextWrapper[dict[str, Any]], path: str, start_line: int = 1) -> str:
        """Read a bounded excerpt from a file in the repository."""
        return await repo.read_file(path, start_line=start_line)

    @function_tool
    async def list_dir(ctx: RunContextWrapper[dict[str, Any]], path: str = ".") -> str:
        """List files and folders in a directory."""
        return await repo.list_directory(path=path)

    # ── Deep analysis tools (delegate to gpt-5.4 for heavy reasoning) ─

    @function_tool
    async def draft_claude_prompt(
        ctx: RunContextWrapper[dict[str, Any]],
        goal: str,
    ) -> str:
        """Draft a strong, well-formed prompt for Claude Code based on the
        user's goal. Use this when the user asks you to help them write or
        improve a prompt, or when you think the user's request needs
        refinement before sending to Claude."""
        drafter = Agent(
            name="PromptDrafter",
            model=deep_analysis_model,
            instructions=prompt_drafter_instructions(),
            tools=_build_readonly_tools(git, repo, harness),
            output_type=ClaudePromptDraft,
        )
        session_id = ctx.context.get("session_id", "default")
        result = await Runner.run(
            drafter,
            f"Draft a Claude Code prompt for this goal:\n{goal}",
            context=ctx.context,
        )
        output = result.final_output
        if hasattr(output, "drafted_prompt"):
            return output.drafted_prompt
        return str(output)

    @function_tool
    async def explain_changes(ctx: RunContextWrapper[dict[str, Any]]) -> str:
        """Explain the latest repository changes in plain language. Use this
        when the user asks what changed, what Claude did, or wants a summary
        of recent work."""
        from .prompts import change_explainer_instructions

        explainer = Agent(
            name="ChangeExplainer",
            model=deep_analysis_model,
            instructions=change_explainer_instructions(),
            tools=_build_readonly_tools(git, repo, harness),
            output_type=ChangeExplanation,
        )
        result = await Runner.run(
            explainer,
            "Explain the latest repository changes.",
            context=ctx.context,
        )
        output = result.final_output
        if hasattr(output, "screen_summary"):
            return output.screen_summary
        return str(output)

    @function_tool
    async def second_opinion(
        ctx: RunContextWrapper[dict[str, Any]],
        concern: str = "",
    ) -> str:
        """Give a second opinion on Claude Code's current direction. Use this
        when the user wants a sanity check or is unsure about what Claude is
        doing."""
        from .prompts import second_opinion_instructions

        reviewer = Agent(
            name="SecondOpinion",
            model=deep_analysis_model,
            instructions=second_opinion_instructions(),
            tools=_build_readonly_tools(git, repo, harness),
            output_type=SecondOpinion,
        )
        result = await Runner.run(
            reviewer,
            f"Give a second opinion on Claude's direction.\n{concern}".strip(),
            context=ctx.context,
        )
        output = result.final_output
        parts = []
        if hasattr(output, "screen_summary") and output.screen_summary:
            parts.append(output.screen_summary)
        if hasattr(output, "verdict") and output.verdict:
            parts.append(f"Verdict: {output.verdict}")
        if hasattr(output, "drafted_follow_up_prompt") and output.drafted_follow_up_prompt:
            parts.append(f"Suggested prompt: {output.drafted_follow_up_prompt}")
        return "\n".join(parts) or str(output)

    # ── Memory-aware dynamic instructions ────────────────────────────

    async def build_instructions(
        ctx: RunContextWrapper[dict[str, Any]],
        agent: RealtimeAgent,
    ) -> str:
        session_id = ctx.context.get("session_id", "default")
        profile_id = ctx.context.get("profile_session_id")
        memory = memory_store.get_session_memory(session_id, profile_id)

        base = companion_instructions()
        memory_block = _format_memory_context(memory)

        return f"{base}\n\n{memory_block}" if memory_block else base

    # ── Assemble the companion ───────────────────────────────────────

    return RealtimeAgent(
        name="Companion",
        instructions=build_instructions,
        tools=[
            # Terminal
            check_claude_status,
            see_claude_terminal,
            start_claude_session,
            send_to_claude,
            interrupt_claude,
            # Git
            git_branch,
            git_status,
            git_diff,
            git_log,
            # Repo
            search_repo,
            read_file,
            list_dir,
            # Deep analysis (delegates to gpt-5.4)
            draft_claude_prompt,
            explain_changes,
            second_opinion,
        ],
    )


def _build_readonly_tools(git, repo, harness):
    """Lightweight read-only tool set for deep-analysis sub-agents."""

    @function_tool
    async def capture_claude_terminal_state(ctx: RunContextWrapper[dict[str, Any]]) -> str:
        """Capture the current Claude terminal state."""
        state = await harness.get_terminal_state()
        return f"session_exists: {state['session_exists']}\nready: {state['ready']}\n\n{state['output']}"

    @function_tool
    async def git_status_summary(ctx: RunContextWrapper[dict[str, Any]]) -> str:
        """Concise git status."""
        return await git.git_status_summary()

    @function_tool
    async def git_diff_summary(ctx: RunContextWrapper[dict[str, Any]], ref: str = "HEAD") -> str:
        """Diff summary against a ref."""
        return await git.git_diff_summary(ref=ref)

    @function_tool
    async def git_current_branch(ctx: RunContextWrapper[dict[str, Any]]) -> str:
        """Current git branch."""
        return await git.git_current_branch()

    @function_tool
    async def git_recent_commits(ctx: RunContextWrapper[dict[str, Any]], limit: int = 5) -> str:
        """Recent commits."""
        return await git.git_recent_commits(limit=limit)

    @function_tool
    async def repo_search(ctx: RunContextWrapper[dict[str, Any]], pattern: str) -> str:
        """Search for files matching a pattern."""
        return await repo.repo_search(pattern)

    @function_tool
    async def read_file_excerpt(ctx: RunContextWrapper[dict[str, Any]], path: str, start_line: int = 1) -> str:
        """Read a file excerpt."""
        return await repo.read_file(path, start_line=start_line)

    return [
        capture_claude_terminal_state,
        git_status_summary,
        git_diff_summary,
        git_current_branch,
        git_recent_commits,
        repo_search,
        read_file_excerpt,
    ]


def _format_memory_context(memory: dict[str, Any]) -> str:
    """Format session memory into a context block for the companion's
    system prompt. This is injected via the dynamic instructions callable."""
    if not memory:
        return ""

    lines = []
    profile = memory.get("profileLabel")
    if profile:
        lines.append(f"Active profile: {profile}")
    goal = memory.get("currentGoal")
    if goal:
        lines.append(f"Current user goal: {goal}")
    last_turn = memory.get("lastUserTurn")
    if last_turn:
        lines.append(f"Last spoken turn: {last_turn}")
    draft = memory.get("manualPromptDraft")
    if draft:
        lines.append(f"Current Claude prompt draft: {draft}")
    custom = memory.get("customInstructions")
    if custom:
        lines.append(f"Custom instructions: {custom}")

    if not lines:
        return ""

    return "Current session context:\n" + "\n".join(f"- {line}" for line in lines)
```

## companion_server.py — WebSocket lifecycle

```python
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from agents.realtime import RealtimeSession

from .companion import build_companion
from .harness import ClaudeTerminalHarness
from .memory import MemoryStore


class CompanionServer:
    """Manages the lifecycle of a RealtimeSession per voice connection.

    The Node server proxies a WebSocket from the browser to this server.
    On connect, we create a RealtimeSession with the CompanionAgent.
    Tool calls are handled inline by the SDK. UI events (transcripts,
    terminal updates, approvals) are forwarded to the browser via the
    same WebSocket.
    """

    def __init__(self, repo_root: Path, app_root: Path):
        self.repo_root = repo_root
        self.app_root = app_root
        self.runtime_dir = app_root / "python_supervisor" / ".runtime"
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        self.harness = ClaudeTerminalHarness(
            repo_root=repo_root,
            config_path=app_root / "config" / "claude-bridge.json",
        )
        self.memory_store = MemoryStore(self.runtime_dir)
        self.companion = build_companion(
            repo_root=repo_root,
            harness=self.harness,
            memory_store=self.memory_store,
        )
        self.active_sessions: dict[str, RealtimeSession] = {}

    async def handle_connection(self, websocket, session_id: str, profile_id: str | None = None):
        """Handle a single voice connection lifecycle."""

        context: dict[str, Any] = {
            "session_id": session_id,
            "profile_session_id": profile_id,
        }

        session = RealtimeSession(
            agent=self.companion,
            context=context,
        )

        self.active_sessions[session_id] = session

        try:
            # The RealtimeSession connects to the Realtime API and manages
            # the audio stream. We forward events to the browser WebSocket
            # for UI updates.
            async for event in session:
                await self._forward_event(websocket, event)
        finally:
            del self.active_sessions[session_id]

    async def handle_browser_state(self, session_id: str, profile_id: str | None, state: dict):
        """Receive browser state sync (profile, goal, transcript preview)."""
        self.memory_store.merge_browser_state(session_id, profile_id, state)

    async def _forward_event(self, websocket, event):
        """Forward relevant RealtimeSession events to the browser for UI."""
        # Event types include: transcript updates, tool call starts/ends,
        # handoff events, errors, audio events, etc.
        # The browser uses these to update the transcript, show tool
        # activity indicators, and display terminal snapshots.
        pass  # Wire to websocket.send(json.dumps(serialized_event))
```

## Approval gate — where it fits

The current approval system works by detecting risky prompts *before* they reach Claude.
In the new architecture, this lives inside `send_to_claude`:

```python
@function_tool
async def send_to_claude(ctx: RunContextWrapper[dict[str, Any]], prompt: str) -> str:
    """Send a prompt to Claude Code."""
    if _prompt_needs_approval(prompt):
        # Store as pending, return a message asking the user to approve
        approval_id = memory_store.queue_approval(ctx.context["session_id"], prompt)
        return (
            f"That prompt looks like it could modify the project. "
            f"I've queued it for your approval (id: {approval_id}). "
            f"Say 'approve' or 'reject' to proceed."
        )
    output = await harness.send_prompt(prompt, settle_ms=1200)
    return output or "(prompt sent, waiting for Claude)"
```

The companion hears "approve" in the next turn, matches it to the pending approval, and
calls `send_to_claude` again with the stored prompt. This keeps the approval conversation
entirely within the voice flow — no separate UI buttons needed (though buttons can still
work as a parallel path via the WebSocket).

## Dynamic instructions — how personality works

The `RealtimeAgent.instructions` is a callable. It runs on every turn. This is where
profile, memory, and character all compose:

```python
async def build_instructions(ctx, agent):
    memory = memory_store.get_session_memory(session_id, profile_id)

    # Base personality
    base = """You are a coding companion in a voice session. You help the user
    work with Claude Code by inspecting the terminal, reading the repo, drafting
    prompts, and explaining what's happening.

    Keep spoken responses to 1-2 sentences. Put detail on screen via tool results.
    Be calm, direct, and practical. Ask one follow-up at a time."""

    # Profile overlay (from preset selection)
    profile = memory.get("customInstructions", "")

    # Session context
    context = _format_memory_context(memory)

    parts = [base]
    if profile:
        parts.append(f"Character instructions:\n{profile}")
    if context:
        parts.append(context)
    return "\n\n".join(parts)
```

This means:
- The companion adapts to preset selection (teacher, programmer, companion) via the
  profile overlay
- It knows the current goal, last turn, and draft prompt via session context
- The base personality stays consistent across profiles
- No separate "mentor" identity — it's all one agent with different depth levels

## What the browser changes look like

The browser still does WebRTC audio directly with the Realtime API. But instead of the
browser managing the entire session and the supervisor being a separate HTTP-request loop,
the flow becomes:

1. Browser requests an ephemeral token from Node (unchanged)
2. Browser connects WebRTC for audio (unchanged)
3. Browser opens a WebSocket to the Python companion server
4. The companion server creates a `RealtimeSession` tied to the same Realtime session
5. Tool calls are handled by the Python server — the browser sees events via WebSocket
6. Browser sends UI state (profile changes, goal edits, approval decisions) via WebSocket
7. Browser receives terminal snapshots, approval queues, mentor summaries via WebSocket

The transcript, terminal monitor, and approval UI all wire to WebSocket events instead of
HTTP polling.

## Migration path

### Phase 0: Make the supervisor persistent
- Add a `serve` command to `cli.py` that starts a WebSocket server
- Keep all existing HTTP routes working in parallel
- The Node server gains a WebSocket proxy route to Python

### Phase 1: Build the CompanionAgent
- Create `companion.py` with the `RealtimeAgent` and tools (this sketch)
- Wire it into a `RealtimeSession` in `companion_server.py`
- Test with a simple WebSocket client before touching the browser

### Phase 2: Connect browser to companion
- Add WebSocket connection logic in `app.js`
- Forward Realtime API events through the companion server
- Keep HTTP fallback routes until the WebSocket path is solid

### Phase 3: Remove the split
- Remove the separate mentor UI panel (mentor actions become voice-native)
- Remove HTTP supervisor routes from Node
- Remove `subprocess` invocation of Python from Node
- The supervisor panel in the browser becomes a "companion status" panel

## What stays the same

- `ClaudeTerminalHarness` — unchanged, still tmux-backed
- `GitToolbox` / `RepoToolbox` — unchanged, same tool implementations
- `SQLiteSession` for deep-analysis agent memory — unchanged
- JSON file-based session and profile memory — unchanged, extracted to `MemoryStore`
- Approval detection logic — unchanged, just called from a different place
- Prompt presets and Prompt Studio — unchanged, browser-side feature
- The Node server still serves static files and mints tokens
