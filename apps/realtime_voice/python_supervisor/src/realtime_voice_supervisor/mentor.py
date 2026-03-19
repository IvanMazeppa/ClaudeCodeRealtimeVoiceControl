from __future__ import annotations

from pathlib import Path
from typing import Any

from agents import Agent, function_tool
from agents.run_context import RunContextWrapper

from .git_tools import GitToolbox
from .harness import ClaudeTerminalHarness
from .models import ApprovalExplanation, ChangeExplanation, ClaudePromptDraft, MentorSummary, SecondOpinion
from .prompts import (
    approval_explainer_instructions,
    change_explainer_instructions,
    mentor_base_instructions,
    prompt_drafter_instructions,
    second_opinion_instructions,
)
from .repo_tools import RepoToolbox


def _remember(ctx: RunContextWrapper[dict[str, Any]], key: str, value: Any) -> None:
    ctx.context[key] = value


def _log_action(ctx: RunContextWrapper[dict[str, Any]], action_type: str, detail: str) -> None:
    action_log = ctx.context.setdefault("action_log", [])
    action_log.append({"type": action_type, "detail": detail})


def build_mentor_agent(
    supervisor_model: str,
    repo_root: Path,
    harness: ClaudeTerminalHarness,
) -> Agent[dict[str, Any]]:
    tools = _build_shared_tools(repo_root, harness)
    return Agent(
        name="MentorAgent",
        model=supervisor_model,
        instructions=(
            f"{mentor_base_instructions()} "
            "Handle general mentor requests such as explaining the current repo state, summarizing "
            "Claude state, or suggesting the next practical action. "
            "Use git and repo tools before speculating."
        ),
        tools=tools,
    )


def build_change_explainer_agent(
    supervisor_model: str,
    repo_root: Path,
    harness: ClaudeTerminalHarness,
) -> Agent[dict[str, Any]]:
    return Agent(
        name="ChangeExplainerAgent",
        model=supervisor_model,
        instructions=change_explainer_instructions(),
        tools=_build_shared_tools(repo_root, harness),
        output_type=ChangeExplanation,
    )


def build_second_opinion_agent(
    supervisor_model: str,
    repo_root: Path,
    harness: ClaudeTerminalHarness,
) -> Agent[dict[str, Any]]:
    return Agent(
        name="SecondOpinionAgent",
        model=supervisor_model,
        instructions=second_opinion_instructions(),
        tools=_build_shared_tools(repo_root, harness),
        output_type=SecondOpinion,
    )


def build_prompt_drafter_agent(
    supervisor_model: str,
    repo_root: Path,
    harness: ClaudeTerminalHarness,
) -> Agent[dict[str, Any]]:
    return Agent(
        name="ClaudePromptDrafterAgent",
        model=supervisor_model,
        instructions=prompt_drafter_instructions(),
        tools=_build_shared_tools(repo_root, harness),
        output_type=ClaudePromptDraft,
    )


def build_approval_explainer_agent(
    supervisor_model: str,
    repo_root: Path,
    harness: ClaudeTerminalHarness,
) -> Agent[dict[str, Any]]:
    return Agent(
        name="ApprovalExplainerAgent",
        model=supervisor_model,
        instructions=approval_explainer_instructions(),
        tools=_build_shared_tools(repo_root, harness),
        output_type=ApprovalExplanation,
    )


def build_claude_state_agent(
    supervisor_model: str,
    repo_root: Path,
    harness: ClaudeTerminalHarness,
) -> Agent[dict[str, Any]]:
    return Agent(
        name="ClaudeStateMentorAgent",
        model=supervisor_model,
        instructions=(
            f"{mentor_base_instructions()} "
            "Summarize what Claude Code is doing right now. "
            "Use the terminal state tool first. "
            "Explain whether Claude is idle, busy, blocked, or waiting for user input."
        ),
        tools=_build_shared_tools(repo_root, harness),
        output_type=MentorSummary,
    )


def _build_shared_tools(repo_root: Path, harness: ClaudeTerminalHarness):
    repo_toolbox = RepoToolbox(repo_root)
    git_toolbox = GitToolbox(repo_root)

    @function_tool
    async def repo_search(ctx: RunContextWrapper[dict[str, Any]], pattern: str, limit: int = 50) -> str:
        """Search the repository for files containing text that matches the pattern."""
        result = await repo_toolbox.repo_search(pattern, limit=limit)
        _remember(ctx, "latest_repo_search", result)
        _log_action(ctx, "repo_search", f'Searched the repository for "{pattern}".')
        return result

    @function_tool
    async def read_file(
        ctx: RunContextWrapper[dict[str, Any]],
        path: str,
        start_line: int = 1,
        max_lines: int = 220,
    ) -> str:
        """Read a bounded excerpt from a file inside the repository."""
        result = await repo_toolbox.read_file(path, start_line=start_line, max_lines=max_lines)
        _remember(ctx, "latest_file_read", {"path": path, "start_line": start_line})
        _log_action(ctx, "read_file", f"Read {path} starting at line {start_line}.")
        return result

    @function_tool
    async def list_directory(ctx: RunContextWrapper[dict[str, Any]], path: str = ".", depth: int = 2) -> str:
        """List files and folders inside a directory within the repository."""
        result = await repo_toolbox.list_directory(path=path, depth=depth)
        _remember(ctx, "latest_directory_listing", {"path": path, "depth": depth})
        _log_action(ctx, "list_directory", f"Listed {path} with depth {depth}.")
        return result

    @function_tool
    async def find_related_files(ctx: RunContextWrapper[dict[str, Any]], query: str, limit: int = 20) -> str:
        """Find likely related files by matching path names against the query."""
        result = await repo_toolbox.find_related_files(query, limit=limit)
        _remember(ctx, "latest_related_files_query", query)
        _log_action(ctx, "find_related_files", f'Looked for files related to "{query}".')
        return result

    @function_tool
    async def git_current_branch(ctx: RunContextWrapper[dict[str, Any]]) -> str:
        """Show the current git branch."""
        result = await git_toolbox.git_current_branch()
        _remember(ctx, "latest_git_branch", result)
        _log_action(ctx, "git_current_branch", "Read the current git branch.")
        return result

    @function_tool
    async def git_status_summary(ctx: RunContextWrapper[dict[str, Any]]) -> str:
        """Show a concise git status summary for the working tree."""
        result = await git_toolbox.git_status_summary()
        _remember(ctx, "latest_git_status", result)
        _log_action(ctx, "git_status_summary", "Read the current git status.")
        return result

    @function_tool
    async def git_diff_summary(ctx: RunContextWrapper[dict[str, Any]], ref: str = "HEAD") -> str:
        """Show a concise diff summary against the given git reference."""
        result = await git_toolbox.git_diff_summary(ref=ref)
        _remember(ctx, "latest_git_diff_summary", result)
        _log_action(ctx, "git_diff_summary", f"Read the git diff summary against {ref}.")
        return result

    @function_tool
    async def git_diff_for_file(ctx: RunContextWrapper[dict[str, Any]], path: str, ref: str = "HEAD") -> str:
        """Show a bounded diff for one file against the given git reference."""
        result = await git_toolbox.git_diff_for_file(path=path, ref=ref)
        _remember(ctx, "latest_git_diff_file", {"path": path, "ref": ref})
        _log_action(ctx, "git_diff_for_file", f"Read the diff for {path} against {ref}.")
        return result

    @function_tool
    async def git_recent_commits(ctx: RunContextWrapper[dict[str, Any]], limit: int = 5) -> str:
        """Show recent git commits in short form."""
        result = await git_toolbox.git_recent_commits(limit=limit)
        _remember(ctx, "latest_git_recent_commits", result)
        _log_action(ctx, "git_recent_commits", f"Read the last {limit} git commits.")
        return result

    @function_tool
    async def capture_claude_terminal_state(ctx: RunContextWrapper[dict[str, Any]]) -> str:
        """Capture the current Claude terminal state without sending any input."""
        state = await harness.get_terminal_state()
        _remember(ctx, "terminal_snapshot", state.get("output", ""))
        _remember(ctx, "terminal_ready", bool(state.get("ready")))
        _remember(ctx, "claude_session_exists", bool(state.get("session_exists")))
        _remember(ctx, "latest_terminal_snapshot", state.get("output", ""))
        _remember(ctx, "latest_terminal_ready", bool(state.get("ready")))
        _remember(ctx, "latest_claude_session_exists", bool(state.get("session_exists")))
        _log_action(ctx, "capture_claude_terminal_state", "Captured the latest Claude terminal state.")
        return (
            f"session_exists: {state['session_exists']}\n"
            f"ready: {state['ready']}\n\n"
            f"{state['output']}"
        ).strip()

    return [
        repo_search,
        read_file,
        list_directory,
        find_related_files,
        git_current_branch,
        git_status_summary,
        git_diff_summary,
        git_diff_for_file,
        git_recent_commits,
        capture_claude_terminal_state,
    ]
