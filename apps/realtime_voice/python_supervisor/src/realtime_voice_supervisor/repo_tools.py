from __future__ import annotations

import asyncio
from pathlib import Path


class RepoToolbox:
    def __init__(self, repo_root: Path):
        self.repo_root = repo_root.resolve()

    async def repo_search(self, pattern: str, limit: int = 50) -> str:
        normalized_limit = max(1, min(limit, 200))
        query = pattern.strip()
        if not query:
            return "No search pattern was provided."

        process = await asyncio.create_subprocess_exec(
            "rg",
            "--files-with-matches",
            "--glob",
            "!apps/realtime_voice/node_modules/**",
            "--glob",
            "!**/.git/**",
            "--glob",
            "!**/.venv/**",
            "--glob",
            "!**/.runtime/**",
            query,
            str(self.repo_root),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()
        if process.returncode not in {0, 1}:
            return stderr.decode("utf-8", errors="ignore").strip() or "Repository search failed."

        matches = [
            self._display_path(Path(line.strip()))
            for line in stdout.decode("utf-8", errors="ignore").splitlines()
            if line.strip()
        ][:normalized_limit]

        if not matches:
            return f'No files matched the search pattern "{query}".'

        return "\n".join(matches)

    async def read_file(self, path: str, start_line: int = 1, max_lines: int = 220) -> str:
        try:
            target = self._resolve_repo_path(path)
        except ValueError as error:
            return str(error)
        if not target.exists():
            return f"File not found: {path}"
        if not target.is_file():
            return f"Not a file: {path}"

        normalized_start = max(1, start_line)
        normalized_max = max(1, min(max_lines, 400))

        lines = target.read_text(encoding="utf-8", errors="ignore").splitlines()
        start_index = normalized_start - 1
        end_index = min(len(lines), start_index + normalized_max)
        excerpt = "\n".join(lines[start_index:end_index])

        return (
            f"Path: {self._display_path(target)}\n"
            f"Lines: {normalized_start}-{end_index}\n\n"
            f"{excerpt}"
        ).strip()

    async def list_directory(self, path: str = ".", depth: int = 2) -> str:
        try:
            target = self._resolve_repo_path(path)
        except ValueError as error:
            return str(error)
        if not target.exists():
            return f"Directory not found: {path}"
        if not target.is_dir():
            return f"Not a directory: {path}"

        normalized_depth = max(0, min(depth, 4))
        entries: list[str] = []
        self._walk_directory(target, normalized_depth, target, entries)

        if not entries:
            return f"Directory is empty: {self._display_path(target)}"

        return "\n".join(entries[:200])

    async def find_related_files(self, query: str, limit: int = 20) -> str:
        normalized_limit = max(1, min(limit, 100))
        tokens = [token.lower() for token in query.replace("/", " ").replace("_", " ").split() if token]
        if not tokens:
            return "No related-file query was provided."

        matches: list[str] = []
        for file_path in sorted(self.repo_root.rglob("*")):
            if not file_path.is_file():
                continue
            if self._is_ignored(file_path):
                continue

            haystack = str(file_path.relative_to(self.repo_root)).lower()
            score = sum(token in haystack for token in tokens)
            if score:
                matches.append(self._display_path(file_path))
            if len(matches) >= normalized_limit:
                break

        if not matches:
            return f'No related files found for "{query}".'

        return "\n".join(matches)

    def _walk_directory(self, target: Path, depth: int, root: Path, entries: list[str]) -> None:
        if depth < 0:
            return

        for child in sorted(target.iterdir(), key=lambda item: (item.is_file(), item.name.lower())):
            if self._is_ignored(child):
                continue
            relative = child.relative_to(root)
            prefix = "dir" if child.is_dir() else "file"
            entries.append(f"{prefix}: {relative}")
            if child.is_dir():
                self._walk_directory(child, depth - 1, root, entries)

    def _resolve_repo_path(self, path: str) -> Path:
        candidate = (self.repo_root / path).resolve()
        if self.repo_root == candidate or self.repo_root in candidate.parents:
            return candidate
        raise ValueError(f"Path escapes repo root: {path}")

    def _display_path(self, path: Path) -> str:
        return str(path.resolve().relative_to(self.repo_root))

    def _is_ignored(self, path: Path) -> bool:
        parts = path.parts
        return any(
            part in {"node_modules", ".git", ".venv", ".runtime", "__pycache__"}
            for part in parts
        )
