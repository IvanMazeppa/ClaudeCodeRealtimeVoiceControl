from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Any

from agents import Agent, Runner, RunState, SQLiteSession, function_tool, trace
from agents.run_context import RunContextWrapper

from .harness import ClaudeBridgeConfig, ClaudeTerminalHarness


RISKY_PROMPT_MARKERS = (
    "edit ",
    "modify ",
    "change ",
    "write ",
    "create ",
    "apply patch",
    "delete ",
    "remove ",
    "rename ",
    "commit",
    "checkout",
    "reset",
    "rebase",
    "npm install",
    "pip install",
    "cargo add",
    "apt ",
    "git ",
    "start server",
    "launch",
)


def _tool_call_id(item: Any) -> str:
    raw = getattr(item, "raw_item", None)
    if isinstance(raw, dict):
        return str(raw.get("call_id") or "")
    if raw is not None:
        return str(getattr(raw, "call_id", "") or "")
    return ""


def _tool_name(item: Any) -> str:
    name = getattr(item, "tool_name", None)
    if name:
        return str(name)
    name = getattr(item, "name", None)
    return str(name or "unknown_tool")


def _default_context(session_id: str) -> dict[str, Any]:
    return {
        "session_id": session_id,
        "action_log": [],
        "terminal_snapshot": "",
        "terminal_ready": False,
        "claude_session_exists": False,
    }


class SupervisorService:
    def __init__(self, repo_root: Path, app_root: Path):
        self.repo_root = repo_root
        self.app_root = app_root
        self.runtime_dir = app_root / "python_supervisor" / ".runtime"
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        self.session_db_path = self.runtime_dir / "sessions.sqlite3"
        self.run_state_dir = self.runtime_dir / "run_state"
        self.run_state_dir.mkdir(parents=True, exist_ok=True)
        self.bridge_config_path = app_root / "config" / "claude-bridge.json"
        self.harness = ClaudeTerminalHarness(repo_root=repo_root, config_path=self.bridge_config_path)
        self.supervisor_model = os.environ.get("REALTIME_SUPERVISOR_MODEL", "gpt-5.4")
        self.voice_supervisor_agent = self._build_agent_graph()

    async def health(self) -> dict[str, Any]:
        bridge = self.harness.load_config()
        terminal = await self.harness.get_terminal_state(bridge)
        return {
            "ok": True,
            "supervisorModel": self.supervisor_model,
            "bridge": {
                "sessionName": bridge.session_name,
                "workingDirectory": str(bridge.working_directory),
                "command": bridge.command,
            },
            "terminal": terminal,
        }

    async def ensure_claude_session(self, session_id: str) -> dict[str, Any]:
        bridge = self.harness.load_config()
        created = await self.harness.ensure_session(bridge)
        terminal = await self.harness.get_terminal_state(bridge)
        return {
            "ok": True,
            "sessionId": session_id,
            "created": created,
            "spokenResponse": (
                "Claude Code is ready."
                if terminal["session_exists"]
                else "I could not find or start the Claude session."
            ),
            "terminalSnapshot": terminal["output"],
            "terminalReady": terminal["ready"],
            "claudeSessionExists": terminal["session_exists"],
            "actionLog": [
                {
                    "type": "attach_or_verify_session",
                    "detail": "Started a new Claude session." if created else "Verified the existing Claude session.",
                }
            ],
            "pendingApprovals": [],
        }

    async def interrupt_claude(self, session_id: str) -> dict[str, Any]:
        output = await self.harness.interrupt()
        state = await self.harness.get_terminal_state()
        return {
            "ok": True,
            "sessionId": session_id,
            "spokenResponse": "Sent an interrupt to Claude.",
            "terminalSnapshot": output or state["output"],
            "terminalReady": state["ready"],
            "claudeSessionExists": state["session_exists"],
            "actionLog": [{"type": "interrupt_run", "detail": "Sent Ctrl+C to the Claude session."}],
            "pendingApprovals": [],
        }

    async def observe(self, session_id: str) -> dict[str, Any]:
        return await self.handle_turn(
            session_id,
            "Read the latest Claude Code terminal output, summarize it briefly, and tell me the next useful action.",
        )

    async def send_manual_prompt(self, session_id: str, prompt: str) -> dict[str, Any]:
        return await self.handle_turn(
            session_id,
            f"Send this exact prompt to Claude Code without rewriting it:\n\n{prompt}",
        )

    async def handle_turn(self, session_id: str, user_text: str) -> dict[str, Any]:
        session = SQLiteSession(session_id, str(self.session_db_path))
        context = _default_context(session_id)

        with trace("realtime-voice-supervisor", group_id=session_id):
            result = await Runner.run(
                self.voice_supervisor_agent,
                user_text,
                session=session,
                context=context,
            )

        return await self._build_result_payload(result, session_id)

    async def resolve_approval(
        self,
        session_id: str,
        call_id: str,
        *,
        approve: bool,
        always: bool = False,
        rejection_message: str | None = None,
    ) -> dict[str, Any]:
        state_path = self._state_path(session_id)
        if not state_path.exists():
            return {
                "ok": False,
                "error": "No pending approval state was found for this supervisor session.",
            }

        state = await RunState.from_string(
            self.voice_supervisor_agent,
            state_path.read_text(encoding="utf-8"),
        )
        interruptions = state.get_interruptions()
        match = next((item for item in interruptions if _tool_call_id(item) == call_id), None)
        if match is None:
            return {
                "ok": False,
                "error": "The requested approval item is no longer pending.",
            }

        if approve:
            state.approve(match, always_approve=always)
        else:
            state.reject(match, always_reject=always, rejection_message=rejection_message)

        session = SQLiteSession(session_id, str(self.session_db_path))
        with trace("realtime-voice-supervisor", group_id=session_id):
            result = await Runner.run(
                self.voice_supervisor_agent,
                state,
                session=session,
            )

        return await self._build_result_payload(result, session_id)

    async def _build_result_payload(self, result: Any, session_id: str) -> dict[str, Any]:
        state = result.to_state()
        serialized = state.to_json()
        context = serialized.get("context", {}).get("context", {}) or {}
        interruptions = state.get_interruptions()

        if interruptions:
            self._state_path(session_id).write_text(state.to_string(), encoding="utf-8")
        else:
            self._state_path(session_id).unlink(missing_ok=True)

        spoken_response = str(result.final_output or "").strip()
        if interruptions and not spoken_response:
            spoken_response = "Approval is required before I can continue working with Claude."

        return {
            "ok": True,
            "sessionId": session_id,
            "spokenResponse": spoken_response,
            "terminalSnapshot": context.get("terminal_snapshot", ""),
            "terminalReady": bool(context.get("terminal_ready")),
            "claudeSessionExists": bool(context.get("claude_session_exists")),
            "actionLog": list(context.get("action_log", [])),
            "pendingApprovals": [self._serialize_interruption(item) for item in interruptions],
        }

    def _serialize_interruption(self, item: Any) -> dict[str, Any]:
        return {
            "callId": _tool_call_id(item),
            "toolName": _tool_name(item),
            "arguments": getattr(item, "arguments", None),
        }

    def _state_path(self, session_id: str) -> Path:
        safe_session = "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in session_id)
        return self.run_state_dir / f"{safe_session}.json"

    def _build_agent_graph(self) -> Agent:
        bridge = self.harness.load_config()

        def _log_action(ctx: RunContextWrapper[dict[str, Any]], action_type: str, detail: str) -> None:
            action_log = ctx.context.setdefault("action_log", [])
            action_log.append({"type": action_type, "detail": detail})

        def _store_terminal_state(ctx: RunContextWrapper[dict[str, Any]], state: dict[str, Any]) -> None:
            ctx.context["terminal_snapshot"] = state.get("output", "")
            ctx.context["terminal_ready"] = bool(state.get("ready"))
            ctx.context["claude_session_exists"] = bool(state.get("session_exists"))

        async def _needs_prompt_approval(
            _ctx: RunContextWrapper[dict[str, Any]],
            params: dict[str, Any],
            _call_id: str,
        ) -> bool:
            prompt = str(params.get("prompt") or "").lower()
            return any(marker in prompt for marker in RISKY_PROMPT_MARKERS)

        @function_tool
        async def attach_or_verify_session(ctx: RunContextWrapper[dict[str, Any]]) -> str:
            """Ensure the dedicated Claude Code session exists and report its state."""
            created = await self.harness.ensure_session(bridge)
            state = await self.harness.get_terminal_state(bridge)
            _store_terminal_state(ctx, state)
            detail = "Started a new Claude session." if created else "Verified the existing Claude session."
            _log_action(ctx, "attach_or_verify_session", detail)
            return json.dumps(state)

        @function_tool
        async def capture_output(ctx: RunContextWrapper[dict[str, Any]]) -> str:
            """Capture the visible Claude terminal output as text."""
            state = await self.harness.get_terminal_state(bridge)
            _store_terminal_state(ctx, state)
            _log_action(ctx, "capture_output", "Captured the visible Claude terminal output.")
            return json.dumps(state)

        @function_tool
        async def is_ready(ctx: RunContextWrapper[dict[str, Any]]) -> str:
            """Check whether Claude Code appears ready for another prompt."""
            state = await self.harness.get_terminal_state(bridge)
            _store_terminal_state(ctx, state)
            detail = "Claude looks ready for another prompt." if state["ready"] else "Claude does not look ready yet."
            _log_action(ctx, "is_ready", detail)
            return json.dumps(
                {
                    "session_exists": state["session_exists"],
                    "ready": state["ready"],
                }
            )

        @function_tool(needs_approval=_needs_prompt_approval)
        async def send_prompt(ctx: RunContextWrapper[dict[str, Any]], prompt: str) -> str:
            """Send a prompt to Claude Code and capture the visible terminal output."""
            output = await self.harness.send_prompt(prompt, config=bridge, settle_ms=bridge.startup_settle_ms)
            state = await self.harness.get_terminal_state(bridge)
            if output:
                state["output"] = output
            _store_terminal_state(ctx, state)
            _log_action(ctx, "send_prompt", f"Sent a prompt to Claude Code: {prompt[:120]}")
            return json.dumps(state)

        @function_tool
        async def interrupt_run(ctx: RunContextWrapper[dict[str, Any]]) -> str:
            """Interrupt the current Claude Code run and capture the new terminal state."""
            output = await self.harness.interrupt(bridge)
            state = await self.harness.get_terminal_state(bridge)
            if output:
                state["output"] = output
            _store_terminal_state(ctx, state)
            _log_action(ctx, "interrupt_run", "Sent Ctrl+C to the Claude session.")
            return json.dumps(state)

        claude_terminal_agent = Agent(
            name="ClaudeTerminalAgent",
            model=self.supervisor_model,
            instructions=(
                "You specialize in interacting with Claude Code running in a real tmux-backed terminal. "
                "Use attach_or_verify_session before trying to send prompts if you are not sure the session exists. "
                "Use capture_output and is_ready whenever you need to inspect state before acting. "
                "When the user wants Claude Code to do something, use send_prompt with the exact useful prompt to send. "
                "When the user wants a status summary, inspect the terminal and summarize it briefly. "
                "Keep your final answer concise and practical."
            ),
            tools=[attach_or_verify_session, capture_output, is_ready, send_prompt, interrupt_run],
        )

        supervisor_agent = Agent(
            name="VoiceSupervisorAgent",
            model=self.supervisor_model,
            instructions=(
                "You are the backend supervisor for a voice-driven Claude Code workflow. "
                "Help the user interact with Claude Code in a hands-free, low-friction way. "
                "Use the Claude terminal specialist whenever the request involves Claude Code state, sending work, or interrupting a run. "
                "If a request does not require terminal interaction, answer directly and briefly. "
                "Keep spoken-style responses short, calm, and actionable."
            ),
            tools=[
                claude_terminal_agent.as_tool(
                    tool_name="work_with_claude_terminal",
                    tool_description="Read, summarize, interrupt, or send prompts to the Claude Code terminal.",
                )
            ],
        )

        return supervisor_agent
