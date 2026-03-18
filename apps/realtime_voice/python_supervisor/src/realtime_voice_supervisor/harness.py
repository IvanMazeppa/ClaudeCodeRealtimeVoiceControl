from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ANSI_PATTERN = re.compile(
    # Strip common ANSI escape sequences from captured tmux output.
    r"\u001b\[[0-9;?]*[ -/]*[@-~]|\u001b[@-_]"
)
BUSY_MARKERS = (
    "Thinking",
    "Hatching",
    "Slithering",
    "Frolicking",
    "Compacting",
    "Searching",
    "Applying",
    "Generating",
    "Inspecting",
)


@dataclass(slots=True)
class ClaudeBridgeConfig:
    session_name: str
    working_directory: Path
    command: str
    capture_lines: int
    startup_prompt_file: Path
    startup_settle_ms: int
    mode_phrases: dict[str, str]


class ClaudeTerminalHarness:
    def __init__(self, repo_root: Path, config_path: Path):
        self.repo_root = repo_root
        self.config_path = config_path
        self.local_config_path = config_path.with_name("claude-bridge.local.json")

    def load_config(self) -> ClaudeBridgeConfig:
        base = self._read_json(self.config_path)
        local = self._read_json(self.local_config_path)
        merged: dict[str, Any] = {
            **base,
            **local,
            "modePhrases": {
                **base.get("modePhrases", {}),
                **local.get("modePhrases", {}),
            },
        }

        return ClaudeBridgeConfig(
            session_name=str(merged.get("sessionName") or "voice-coding-claude"),
            working_directory=(self.repo_root / str(merged.get("workingDirectory") or ".")).resolve(),
            command=str(merged.get("command") or "claude"),
            capture_lines=int(merged.get("captureLines") or 160),
            startup_prompt_file=(
                self.repo_root
                / str(merged.get("startupPromptFile") or "apps/claude_code_voice/prompts/session_start.md")
            ).resolve(),
            startup_settle_ms=int(merged.get("startupSettleMs") or 1200),
            mode_phrases=dict(merged.get("modePhrases") or {}),
        )

    async def claude_session_exists(self, config: ClaudeBridgeConfig | None = None) -> bool:
        cfg = config or self.load_config()
        try:
            await self._run_tmux("has-session", "-t", cfg.session_name)
            return True
        except RuntimeError:
            return False

    async def ensure_session(self, config: ClaudeBridgeConfig | None = None) -> bool:
        cfg = config or self.load_config()
        exists = await self.claude_session_exists(cfg)
        if exists:
            return False

        await self._run_tmux(
            "new-session",
            "-d",
            "-s",
            cfg.session_name,
            "-c",
            str(cfg.working_directory),
            cfg.command,
        )
        await asyncio.sleep(1.2)
        return True

    async def capture_output(self, config: ClaudeBridgeConfig | None = None) -> str:
        cfg = config or self.load_config()
        output = await self._run_tmux(
            "capture-pane",
            "-p",
            "-t",
            self._target(cfg),
            "-S",
            f"-{cfg.capture_lines}",
        )
        return self._strip_ansi(output).strip()

    async def send_prompt(
        self,
        prompt: str,
        *,
        config: ClaudeBridgeConfig | None = None,
        submit: bool = True,
        settle_ms: int | None = None,
    ) -> str:
        cfg = config or self.load_config()
        await self.ensure_session(cfg)
        buffer_name = f"voice-supervisor-{asyncio.get_running_loop().time():.6f}".replace(".", "-")
        await self._run_tmux("set-buffer", "-b", buffer_name, prompt)
        try:
            await self._run_tmux("paste-buffer", "-b", buffer_name, "-t", self._target(cfg))
            if submit:
                await self._run_tmux("send-keys", "-t", self._target(cfg), "C-m")
        finally:
            await self._delete_buffer(buffer_name)

        if settle_ms:
            await asyncio.sleep(settle_ms / 1000)

        return await self.capture_output(cfg)

    async def interrupt(self, config: ClaudeBridgeConfig | None = None) -> str:
        cfg = config or self.load_config()
        if not await self.claude_session_exists(cfg):
            return ""
        await self._run_tmux("send-keys", "-t", self._target(cfg), "C-c")
        await asyncio.sleep(0.4)
        return await self.capture_output(cfg)

    async def read_startup_prompt(self, config: ClaudeBridgeConfig | None = None) -> str:
        cfg = config or self.load_config()
        try:
            contents = cfg.startup_prompt_file.read_text(encoding="utf-8").strip()
        except OSError:
            return ""

        match = re.search(r"```(?:text)?\n([\s\S]*?)```", contents)
        return match.group(1).strip() if match else contents

    async def get_terminal_state(self, config: ClaudeBridgeConfig | None = None) -> dict[str, Any]:
        cfg = config or self.load_config()
        exists = await self.claude_session_exists(cfg)
        output = await self.capture_output(cfg) if exists else ""
        ready = self._is_ready_from_output(output)
        return {
            "session_exists": exists,
            "session_name": cfg.session_name,
            "working_directory": str(cfg.working_directory),
            "command": cfg.command,
            "ready": ready,
            "output": output,
        }

    def _is_ready_from_output(self, output: str) -> bool:
        if not output:
            return False

        tail = output.splitlines()[-20:]
        if any(marker in line for line in tail for marker in BUSY_MARKERS):
            return False

        return any(line.strip().startswith("❯") for line in tail)

    def _target(self, config: ClaudeBridgeConfig) -> str:
        return f"{config.session_name}:0.0"

    async def _run_tmux(self, *args: str) -> str:
        process = await asyncio.create_subprocess_exec(
            "tmux",
            *args,
            cwd=str(self.repo_root),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()
        if process.returncode != 0:
            raise RuntimeError(stderr.decode("utf-8", errors="ignore").strip() or "tmux command failed")
        return stdout.decode("utf-8", errors="ignore")

    async def _delete_buffer(self, buffer_name: str) -> None:
        try:
            await self._run_tmux("delete-buffer", "-b", buffer_name)
        except RuntimeError:
            pass

    def _read_json(self, file_path: Path) -> dict[str, Any]:
        try:
            return json.loads(file_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}

    def _strip_ansi(self, text: str) -> str:
        return ANSI_PATTERN.sub("", text)
