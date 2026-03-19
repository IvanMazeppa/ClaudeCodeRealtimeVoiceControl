from __future__ import annotations

import asyncio
import os
from pathlib import Path


class GitToolbox:
    def __init__(self, repo_root: Path):
        self.repo_root = repo_root.resolve()

    async def git_current_branch(self) -> str:
        output = await self._run_git("branch", "--show-current")
        return output or "(detached HEAD or unknown branch)"

    async def git_status_summary(self) -> str:
        output = await self._run_git("status", "--short", "--branch")
        return output or "Working tree is clean."

    async def git_diff_summary(self, ref: str = "HEAD") -> str:
        output = await self._run_git("diff", "--stat", ref)
        return output or f"No diff summary against {ref}."

    async def git_diff_for_file(self, path: str, ref: str = "HEAD") -> str:
        try:
            candidate = (self.repo_root / path).resolve()
            if self.repo_root != candidate and self.repo_root not in candidate.parents:
                return f"Path escapes repo root: {path}"
        except OSError as error:
            return str(error)
        relative = candidate.relative_to(self.repo_root)
        output = await self._run_git("diff", "--no-ext-diff", ref, "--", str(relative))
        if not output:
            return f"No diff for {relative} against {ref}."
        return self._truncate(output, max_lines=320)

    async def git_recent_commits(self, limit: int = 5) -> str:
        normalized_limit = max(1, min(limit, 20))
        output = await self._run_git("log", "--oneline", f"-n{normalized_limit}")
        return output or "No recent commits available."

    async def _run_git(self, *args: str) -> str:
        process = await asyncio.create_subprocess_exec(
            "git",
            *args,
            cwd=str(self.repo_root),
            env={**os.environ, "GIT_PAGER": "cat"},
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()
        if process.returncode != 0:
            return stderr.decode("utf-8", errors="ignore").strip() or "git command failed"
        return stdout.decode("utf-8", errors="ignore").strip()

    def _truncate(self, text: str, *, max_lines: int) -> str:
        lines = text.splitlines()
        if len(lines) <= max_lines:
            return text
        truncated = "\n".join(lines[:max_lines])
        return f"{truncated}\n...\n[diff truncated]"
