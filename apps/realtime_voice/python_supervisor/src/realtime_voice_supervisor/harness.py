from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


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
        target = self._target(cfg)
        logger.info("send_prompt: target=%s submit=%s prompt=%r", target, submit, prompt[:100])
        buffer_name = f"voice-supervisor-{asyncio.get_running_loop().time():.6f}".replace(".", "-")
        await self._run_tmux("set-buffer", "-b", buffer_name, prompt)
        try:
            await self._run_tmux("paste-buffer", "-b", buffer_name, "-t", target)
            if submit:
                # Small delay so Ink processes the pasted text before Enter
                await asyncio.sleep(0.15)
                await self._run_tmux("send-keys", "-t", target, "Enter")
                logger.info("send_prompt: Enter sent to %s", target)
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

    # Mapping from human-friendly key names to tmux send-keys literals.
    NAMED_KEYS: dict[str, str] = {
        "escape": "Escape",
        "esc": "Escape",
        "enter": "Enter",
        "return": "Enter",
        "tab": "Tab",
        "backspace": "BSpace",
        "delete": "DC",
        "up": "Up",
        "down": "Down",
        "left": "Left",
        "right": "Right",
        "home": "Home",
        "end": "End",
        "pageup": "PPage",
        "pagedown": "NPage",
        "space": "Space",
        "ctrl-c": "C-c",
        "ctrl-d": "C-d",
        "ctrl-a": "C-a",
        "ctrl-e": "C-e",
        "ctrl-l": "C-l",
        "ctrl-z": "C-z",
        "ctrl-r": "C-r",
    }

    # Raw hex bytes for keys that TUI frameworks (Ink) may handle
    # differently when received as tmux key-names vs raw PTY input.
    # tmux send-keys -H sends raw hex directly to the PTY master fd.
    RAW_HEX: dict[str, str] = {
        "enter": "0d",
        "return": "0d",
        "ctrl-c": "03",
        "ctrl-a": "01",
        "ctrl-d": "04",
        "ctrl-e": "05",
        "ctrl-l": "0c",
        "ctrl-z": "1a",
        "ctrl-r": "12",
        "escape": "1b",
        "esc": "1b",
        "tab": "09",
        "backspace": "7f",
        "space": "20",
    }

    async def send_keys(
        self,
        keys: str | list[str],
        *,
        config: ClaudeBridgeConfig | None = None,
        settle_ms: int = 200,
        inter_key_delay_ms: int = 50,
        raw: bool = False,
    ) -> str:
        """Send one or more key presses to the terminal.

        *keys* can be a single key name (``"Escape"``) or a list
        (``["Up", "Up", "Enter"]``).  Human-friendly names like
        ``"escape"``, ``"backspace"``, ``"ctrl-c"`` are translated
        automatically; anything else is forwarded to ``tmux send-keys``
        as-is (e.g. literal characters).

        When *raw* is True, keys are sent as raw hex bytes via
        ``tmux send-keys -H``, bypassing tmux's key-name interpretation.
        This can help with TUI frameworks (like Ink) that may treat
        named-key input differently from raw PTY bytes.

        *inter_key_delay_ms* adds a pause between each key to give the
        TUI time to process one key before receiving the next.
        """
        cfg = config or self.load_config()
        await self.ensure_session(cfg)

        if isinstance(keys, str):
            keys = [keys]

        target = self._target(cfg)
        logger.info("send_keys: target=%s keys=%r raw=%s", target, keys, raw)
        for i, key in enumerate(keys):
            if raw:
                await self._send_key_raw(target, key)
            else:
                tmux_key = self.NAMED_KEYS.get(key.lower(), key)
                await self._run_tmux("send-keys", "-t", target, tmux_key)
            if inter_key_delay_ms and i < len(keys) - 1:
                await asyncio.sleep(inter_key_delay_ms / 1000)

        if settle_ms:
            await asyncio.sleep(settle_ms / 1000)

        return await self.capture_output(cfg)

    async def _send_key_raw(self, target: str, key: str) -> None:
        """Send a key as raw hex bytes via ``tmux send-keys -H``.

        Multi-byte escape sequences (arrow keys etc.) are passed as
        separate hex arguments in a single tmux call so the PTY
        receives the full sequence atomically.
        """
        lower = key.lower()

        # Single-byte control characters and printable keys
        hex_code = self.RAW_HEX.get(lower)
        if hex_code:
            await self._run_tmux("send-keys", "-t", target, "-H", hex_code)
            return

        # Multi-byte escape sequences: each hex byte as a separate arg
        # so tmux writes them all in one write() call to the PTY master.
        raw_sequences: dict[str, list[str]] = {
            "up":       ["1b", "5b", "41"],       # ESC [ A
            "down":     ["1b", "5b", "42"],       # ESC [ B
            "right":    ["1b", "5b", "43"],       # ESC [ C
            "left":     ["1b", "5b", "44"],       # ESC [ D
            "home":     ["1b", "5b", "48"],       # ESC [ H
            "end":      ["1b", "5b", "46"],       # ESC [ F
            "delete":   ["1b", "5b", "33", "7e"], # ESC [ 3 ~
            "pageup":   ["1b", "5b", "35", "7e"], # ESC [ 5 ~
            "pagedown": ["1b", "5b", "36", "7e"], # ESC [ 6 ~
        }
        seq = raw_sequences.get(lower)
        if seq:
            await self._run_tmux("send-keys", "-t", target, "-H", *seq)
            return

        # Single printable character — send its hex code
        if len(key) == 1:
            await self._run_tmux("send-keys", "-t", target, "-H", f"{ord(key):02x}")
        else:
            # Fall back to named key
            tmux_key = self.NAMED_KEYS.get(lower, key)
            await self._run_tmux("send-keys", "-t", target, tmux_key)

    async def wait_for_content(
        self,
        pattern: str,
        *,
        config: ClaudeBridgeConfig | None = None,
        timeout_ms: int = 10000,
        poll_ms: int = 250,
    ) -> str | None:
        """Poll the terminal until *pattern* (regex) matches captured output.

        Returns the captured output when the pattern matches, or None on
        timeout. Use this to wait for a menu or prompt to render before
        sending keys.
        """
        cfg = config or self.load_config()
        deadline = asyncio.get_event_loop().time() + timeout_ms / 1000
        compiled = re.compile(pattern)
        while asyncio.get_event_loop().time() < deadline:
            output = await self.capture_output(cfg)
            if compiled.search(output):
                return output
            await asyncio.sleep(poll_ms / 1000)
        return None

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
        interactive = self._detect_interactive_menu(output) if exists else False
        # An interactive menu uses ❯ as a selection cursor, not a prompt.
        # Override ready to False so callers don't mistake it for a prompt.
        ready = False if interactive else self._is_ready_from_output(output)
        return {
            "session_exists": exists,
            "session_name": cfg.session_name,
            "working_directory": str(cfg.working_directory),
            "command": cfg.command,
            "ready": ready,
            "interactive_menu": interactive,
            "output": output,
        }

    # Markers that indicate Claude is showing an interactive menu/dialog
    # (not the normal ❯ prompt or a busy spinner).
    INTERACTIVE_MARKERS = (
        "↑/↓",
        "navigate",
        "Select",
        "Choose",
        "Press enter",
        "/ to search",
        "(y/n)",
        "(Y/n)",
        "[y/N]",
        "Esc to cancel",
        "Type to search",
        "Resume Session",
        "⌕ Search",
        "Ctrl+A to show all",
        "↓ ",  # down-arrow overflow indicator in Claude menus
    )

    def _is_ready_from_output(self, output: str) -> bool:
        if not output:
            return False

        tail = output.splitlines()[-20:]
        if any(marker in line for line in tail for marker in BUSY_MARKERS):
            return False

        return any(line.strip().startswith("❯") for line in tail)

    def _detect_interactive_menu(self, output: str) -> bool:
        """Detect if the terminal is showing an interactive menu/dialog."""
        if not output:
            return False
        tail = "\n".join(output.splitlines()[-30:])
        return any(marker in tail for marker in self.INTERACTIVE_MARKERS)

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
