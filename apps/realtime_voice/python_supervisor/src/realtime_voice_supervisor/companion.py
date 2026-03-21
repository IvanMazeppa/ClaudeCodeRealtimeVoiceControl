"""Single-voice companion agent built on RealtimeAgent.

The companion hears the user, thinks with tools, and speaks the answer —
all within one conversational turn. Heavy reasoning tasks delegate to
gpt-5.4 agents via Runner.run, but the conversational identity stays
continuous.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from agents import Agent, Runner, WebSearchTool, function_tool
from agents.realtime import RealtimeAgent
from agents.run_context import RunContextWrapper

from .git_tools import GitToolbox
from .harness import ClaudeTerminalHarness
from .memory import MemoryStore
from .models import ChangeExplanation, ClaudePromptDraft, SecondOpinion
from .prompts import (
    change_explainer_instructions,
    companion_base_instructions,
    prompt_drafter_instructions,
    second_opinion_instructions,
)
from .repo_tools import RepoToolbox


RISKY_PROMPT_MARKERS = (
    "edit ", "modify ", "change ", "write ", "create ", "apply patch",
    "delete ", "remove ", "rename ", "commit", "checkout", "reset",
    "rebase", "npm install", "pip install", "cargo add", "apt ",
    "git ", "start server", "launch",
)


def _prompt_needs_approval(prompt: str) -> bool:
    normalized = prompt.lower()
    return any(marker in normalized for marker in RISKY_PROMPT_MARKERS)


def build_companion(
    repo_root: Path,
    harness: ClaudeTerminalHarness,
    memory_store: MemoryStore,
    deep_analysis_model: str | None = None,
) -> RealtimeAgent[dict[str, Any]]:
    """Build the single voice companion RealtimeAgent with all tools."""

    deep_model = deep_analysis_model or os.environ.get("REALTIME_SUPERVISOR_MODEL", "gpt-5.4")
    git = GitToolbox(repo_root)
    repo = RepoToolbox(repo_root)

    # ── Terminal tools ───────────────────────────────────────────────

    @function_tool
    async def check_claude_status(ctx: RunContextWrapper[dict[str, Any]]) -> str:
        """Check whether the Claude Code terminal session exists and is idle."""
        state = await harness.get_terminal_state()
        return json.dumps({"session_exists": state["session_exists"], "ready": state["ready"]})

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
        label = "Started a new Claude session." if created else "Claude session already running."
        return f"{label}\n{state.get('output', '')}"

    @function_tool
    async def send_to_claude(ctx: RunContextWrapper[dict[str, Any]], prompt: str) -> str:
        """Send a prompt to Claude Code. Describe what you are sending and why
        before calling this tool. If the prompt modifies the project it will be
        queued for user approval instead of sent immediately."""
        if _prompt_needs_approval(prompt):
            session_id = ctx.context.get("session_id", "default")
            approval_id = memory_store.queue_approval(session_id, prompt, source="companion")
            return (
                f"That prompt looks like it could modify the project. "
                f"I have queued it for your approval (id: {approval_id}). "
                f"Say 'approve' or 'reject' to proceed."
            )
        output = await harness.send_prompt(prompt, settle_ms=1200)
        return output or "(prompt sent, waiting for Claude to respond)"

    @function_tool
    async def approve_pending_prompt(ctx: RunContextWrapper[dict[str, Any]]) -> str:
        """Approve the most recent pending prompt and send it to Claude."""
        session_id = ctx.context.get("session_id", "default")
        approval = memory_store.pop_latest_approval(session_id)
        if approval is None:
            return "No pending approval to approve."
        prompt = str(approval.get("prompt") or "")
        if not prompt:
            return "The pending approval had no prompt content."
        output = await harness.send_prompt(prompt, settle_ms=1200)
        return f"Approved and sent to Claude.\n{output or '(waiting for response)'}"

    @function_tool
    async def reject_pending_prompt(ctx: RunContextWrapper[dict[str, Any]]) -> str:
        """Reject the most recent pending prompt without sending it."""
        session_id = ctx.context.get("session_id", "default")
        approval = memory_store.pop_latest_approval(session_id)
        if approval is None:
            return "No pending approval to reject."
        return "Rejected. Nothing was sent to Claude."

    @function_tool
    async def interrupt_claude(ctx: RunContextWrapper[dict[str, Any]]) -> str:
        """Send Ctrl+C to interrupt Claude Code's current work."""
        output = await harness.interrupt()
        return output or "(interrupt sent)"

    # ── Git tools ────────────────────────────────────────────────────

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
        """Show a diff stat summary against the given git ref."""
        return await git.git_diff_summary(ref=ref)

    @function_tool
    async def git_log(ctx: RunContextWrapper[dict[str, Any]], limit: int = 5) -> str:
        """Show recent commits in short form."""
        return await git.git_recent_commits(limit=limit)

    @function_tool
    async def git_file_diff(ctx: RunContextWrapper[dict[str, Any]], path: str, ref: str = "HEAD") -> str:
        """Show the full diff for one file against a git ref."""
        return await git.git_diff_for_file(path=path, ref=ref)

    # ── Repo tools ───────────────────────────────────────────────────

    @function_tool
    async def search_repo(ctx: RunContextWrapper[dict[str, Any]], pattern: str) -> str:
        """Search the repository for files containing text matching a pattern."""
        return await repo.repo_search(pattern)

    @function_tool
    async def read_file(ctx: RunContextWrapper[dict[str, Any]], path: str, start_line: int = 1) -> str:
        """Read a bounded excerpt from a file in the repository."""
        return await repo.read_file(path, start_line=start_line)

    @function_tool
    async def list_dir(ctx: RunContextWrapper[dict[str, Any]], path: str = ".") -> str:
        """List files and folders in a repository directory."""
        return await repo.list_directory(path=path)

    @function_tool
    async def find_related_files(ctx: RunContextWrapper[dict[str, Any]], query: str) -> str:
        """Find files with paths matching the query terms."""
        return await repo.find_related_files(query)

    # ── Deep analysis tools (delegate to gpt-5.4) ───────────────────

    @function_tool
    async def draft_claude_prompt(ctx: RunContextWrapper[dict[str, Any]], goal: str) -> str:
        """Draft a strong, well-formed prompt for Claude Code. Use when the user
        asks for help writing a prompt, or when their request needs refinement
        before sending to Claude."""
        drafter = Agent(
            name="PromptDrafter",
            model=deep_model,
            instructions=prompt_drafter_instructions(),
            tools=_build_readonly_tools(git, repo, harness),
            output_type=ClaudePromptDraft,
        )
        result = await Runner.run(drafter, f"Draft a Claude Code prompt for this goal:\n{goal}", context=ctx.context)
        output = result.final_output
        if hasattr(output, "drafted_prompt"):
            return f"{output.spoken_response}\n\nDrafted prompt:\n{output.drafted_prompt}"
        return str(output)

    @function_tool
    async def explain_changes(ctx: RunContextWrapper[dict[str, Any]]) -> str:
        """Explain the latest repository changes in plain language. Use when the
        user asks what changed or wants a summary of recent work."""
        explainer = Agent(
            name="ChangeExplainer",
            model=deep_model,
            instructions=change_explainer_instructions(),
            tools=_build_readonly_tools(git, repo, harness),
            output_type=ChangeExplanation,
        )
        result = await Runner.run(
            explainer,
            "Explain the latest repository changes for the user. "
            "Always call git_current_branch, git_status_summary, and git_diff_summary first.",
            context=ctx.context,
        )
        output = result.final_output
        if hasattr(output, "screen_summary"):
            return output.screen_summary
        return str(output)

    @function_tool
    async def second_opinion(ctx: RunContextWrapper[dict[str, Any]], concern: str = "") -> str:
        """Give a second opinion on Claude Code's current direction. Use when the
        user wants a sanity check or is unsure about what Claude is doing."""
        reviewer = Agent(
            name="SecondOpinion",
            model=deep_model,
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

    # ── Dynamic instructions ─────────────────────────────────────────

    async def build_instructions(
        ctx: RunContextWrapper[dict[str, Any]],
        agent: RealtimeAgent,
    ) -> str:
        session_id = ctx.context.get("session_id", "default")
        profile_id = ctx.context.get("profile_session_id")
        memory = memory_store.get_session_memory(session_id, profile_id)

        base = companion_base_instructions()
        context_block = memory_store.build_agent_context_block(memory)

        parts = [base]
        if context_block:
            parts.append(context_block)
        return "\n\n".join(parts)

    # ── Assemble ─────────────────────────────────────────────────────

    tools = [
        # Terminal
        check_claude_status,
        see_claude_terminal,
        start_claude_session,
        send_to_claude,
        approve_pending_prompt,
        reject_pending_prompt,
        interrupt_claude,
        # Git
        git_branch,
        git_status,
        git_diff,
        git_log,
        git_file_diff,
        # Repo
        search_repo,
        read_file,
        list_dir,
        find_related_files,
        # Deep analysis
        draft_claude_prompt,
        explain_changes,
        second_opinion,
        # Hosted
        WebSearchTool(),
    ]

    return RealtimeAgent(
        name="Companion",
        instructions=build_instructions,
        tools=tools,
    )


def _build_readonly_tools(git: GitToolbox, repo: RepoToolbox, harness: ClaudeTerminalHarness):
    """Read-only tool set for deep-analysis sub-agents (gpt-5.4)."""

    @function_tool
    async def capture_claude_terminal_state(ctx: RunContextWrapper[dict[str, Any]]) -> str:
        """Capture the current Claude terminal state without sending input."""
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
        """Read a bounded file excerpt."""
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
