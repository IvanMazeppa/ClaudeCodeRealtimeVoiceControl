"""WebSocket server for the companion agent.

Runs as a persistent asyncio process. The browser connects via WebSocket
for tool execution and state sync. Audio flows directly between the
browser and OpenAI via WebRTC — this server never touches audio.

When the Realtime model decides to call a tool, the browser receives the
function_call event on its data channel, forwards it here for execution,
and sends the result back to OpenAI. This keeps the voice loop continuous
while giving the model access to terminal, git, repo, and web tools.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Any

from agents import FunctionTool
from agents.run_context import RunContextWrapper
from agents.tool import ToolContext

from .companion import build_companion
from .harness import ClaudeTerminalHarness
from .memory import MemoryStore

logger = logging.getLogger(__name__)


class CompanionServer:
    """Manages companion agent state and executes tools on behalf of the
    browser's Realtime session.

    Architecture:
    - Browser ↔ OpenAI Realtime API: WebRTC for audio + data channel for events
    - Browser ↔ This server: WebSocket for tool execution + state sync
    - When OpenAI calls a function, browser forwards it here, we execute,
      browser sends result back to OpenAI via data channel
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
        self.deep_analysis_model = os.environ.get("REALTIME_SUPERVISOR_MODEL", "gpt-5.4")
        self.companion = build_companion(
            repo_root=repo_root,
            harness=self.harness,
            memory_store=self.memory_store,
            deep_analysis_model=self.deep_analysis_model,
        )
        self._tool_map: dict[str, FunctionTool] = {}
        self._build_tool_map()
        self.active_connections: dict[str, Any] = {}

    def _build_tool_map(self) -> None:
        """Index companion tools by name for fast lookup during execution."""
        for tool in self.companion.tools:
            if isinstance(tool, FunctionTool):
                self._tool_map[tool.name] = tool

    def get_tool_definitions(self) -> list[dict[str, Any]]:
        """Export tool definitions in OpenAI Realtime session.update format.

        The browser includes these in its session.update so the Realtime
        model knows which tools it can call.
        """
        definitions = []
        for tool in self.companion.tools:
            if isinstance(tool, FunctionTool):
                definitions.append({
                    "type": "function",
                    "name": tool.name,
                    "description": tool.description or "",
                    "parameters": tool.params_json_schema,
                })
        return definitions

    async def get_companion_instructions(
        self,
        session_id: str,
        profile_session_id: str | None,
    ) -> str:
        """Build the dynamic instructions for the companion.

        The browser uses this as the Realtime session system prompt so the
        voice model has the same personality, memory, and tool guidance as
        the companion agent definition.
        """
        if callable(self.companion.instructions):
            # Build a minimal context wrapper for the instructions callable
            context: dict[str, Any] = {
                "session_id": session_id,
                "profile_session_id": profile_session_id,
            }
            wrapper = RunContextWrapper(context=context)
            return await self.companion.instructions(wrapper, self.companion)
        return str(self.companion.instructions or "")

    async def execute_tool(
        self,
        session_id: str,
        profile_session_id: str | None,
        tool_name: str,
        call_id: str,
        arguments: str,
    ) -> dict[str, Any]:
        """Execute a tool call forwarded from the browser's Realtime session.

        Returns {"ok": True, "result": "..."} or {"ok": False, "error": "..."}.
        """
        tool = self._tool_map.get(tool_name)
        if tool is None:
            return {"ok": False, "error": f"Unknown tool: {tool_name}"}

        context: dict[str, Any] = {
            "session_id": session_id,
            "profile_session_id": profile_session_id,
        }
        tool_context = ToolContext(
            context=context,
            usage=None,
            tool_name=tool_name,
            tool_call_id=call_id,
            tool_arguments=arguments,
        )
        try:
            result = await tool.on_invoke_tool(tool_context, arguments)
            return {"ok": True, "result": str(result)}
        except Exception as exc:
            logger.exception("Tool %s failed", tool_name)
            return {"ok": False, "error": str(exc)}

    async def handle_websocket(self, websocket: Any, path: str = "/") -> None:
        """Handle one browser WebSocket connection.

        Protocol — browser sends:
            {"type": "init", "sessionId": "...", "profileSessionId": "..."}
            {"type": "browser_state", "state": {...}}
            {"type": "tool_call", "name": "...", "callId": "...", "arguments": "..."}
            {"type": "approve", "callId": "..."}
            {"type": "reject", "callId": "..."}
            {"type": "terminal_refresh"}
            {"type": "ping"}

        Server responds:
            {"type": "ready", "sessionId": "...", "tools": [...], "instructions": "..."}
            {"type": "memory", "memory": {...}}
            {"type": "tool_result", "callId": "...", "result": "...", "ok": true}
            {"type": "approvals", "pending": [...]}
            {"type": "terminal", "state": {...}}
            {"type": "error", "message": "..."}
            {"type": "pong"}
        """
        session_id = "default"
        profile_session_id: str | None = None

        try:
            async for raw_message in websocket:
                try:
                    message = json.loads(raw_message)
                except (json.JSONDecodeError, TypeError):
                    await self._send(websocket, {"type": "error", "message": "Invalid JSON"})
                    continue

                msg_type = message.get("type", "")

                if msg_type == "init":
                    session_id = str(message.get("sessionId") or "default")
                    profile_session_id = message.get("profileSessionId") or None
                    self.active_connections[session_id] = websocket
                    memory = self.memory_store.get_session_memory(session_id, profile_session_id)
                    approvals = self.memory_store.read_pending_approvals(session_id)
                    terminal = await self.harness.get_terminal_state()
                    instructions = await self.get_companion_instructions(session_id, profile_session_id)
                    await self._send(websocket, {
                        "type": "ready",
                        "sessionId": session_id,
                        "tools": self.get_tool_definitions(),
                        "instructions": instructions,
                    })
                    await self._send(websocket, {"type": "memory", "memory": memory})
                    await self._send(websocket, {"type": "approvals", "pending": approvals})
                    await self._send(websocket, {
                        "type": "terminal",
                        "state": self._terminal_payload(terminal),
                    })

                elif msg_type == "browser_state":
                    state = message.get("state") or {}
                    memory = self.memory_store.merge_browser_state(session_id, profile_session_id, state)
                    await self._send(websocket, {"type": "memory", "memory": memory})

                elif msg_type == "tool_call":
                    tool_name = str(message.get("name") or "")
                    call_id = str(message.get("callId") or "")
                    arguments = str(message.get("arguments") or "{}")
                    result = await self.execute_tool(
                        session_id, profile_session_id,
                        tool_name, call_id, arguments,
                    )
                    await self._send(websocket, {
                        "type": "tool_result",
                        "callId": call_id,
                        "name": tool_name,
                        "ok": result["ok"],
                        "result": result.get("result", result.get("error", "")),
                    })
                    # After tool execution, refresh terminal and approvals
                    if tool_name in {
                        "send_to_claude", "start_claude_session", "interrupt_claude",
                        "approve_pending_prompt", "reject_pending_prompt",
                    }:
                        terminal = await self.harness.get_terminal_state()
                        await self._send(websocket, {
                            "type": "terminal",
                            "state": self._terminal_payload(terminal),
                        })
                        approvals = self.memory_store.read_pending_approvals(session_id)
                        await self._send(websocket, {"type": "approvals", "pending": approvals})

                elif msg_type == "approve":
                    call_id = str(message.get("callId") or "")
                    if call_id:
                        approval = self.memory_store.pop_approval(session_id, call_id)
                    else:
                        approval = self.memory_store.pop_latest_approval(session_id)

                    if approval:
                        prompt = str(approval.get("prompt") or "")
                        if prompt:
                            output = await self.harness.send_prompt(prompt, settle_ms=1200)
                            terminal = await self.harness.get_terminal_state()
                            await self._send(websocket, {
                                "type": "terminal",
                                "state": self._terminal_payload(terminal, output),
                            })
                    approvals = self.memory_store.read_pending_approvals(session_id)
                    await self._send(websocket, {"type": "approvals", "pending": approvals})

                elif msg_type == "reject":
                    call_id = str(message.get("callId") or "")
                    if call_id:
                        self.memory_store.pop_approval(session_id, call_id)
                    else:
                        self.memory_store.pop_latest_approval(session_id)
                    approvals = self.memory_store.read_pending_approvals(session_id)
                    await self._send(websocket, {"type": "approvals", "pending": approvals})

                elif msg_type == "terminal_refresh":
                    terminal = await self.harness.get_terminal_state()
                    await self._send(websocket, {
                        "type": "terminal",
                        "state": self._terminal_payload(terminal),
                    })

                elif msg_type == "ping":
                    await self._send(websocket, {"type": "pong"})

                else:
                    await self._send(websocket, {"type": "error", "message": f"Unknown message type: {msg_type}"})

        except Exception as exc:
            logger.warning("WebSocket connection closed: %s", exc)
        finally:
            self.active_connections.pop(session_id, None)

    def _terminal_payload(self, terminal: dict[str, Any], output_override: str | None = None) -> dict[str, Any]:
        return {
            "output": output_override or terminal.get("output", ""),
            "ready": terminal.get("ready", False),
            "session_exists": terminal.get("session_exists", False),
        }

    async def _send(self, websocket: Any, payload: dict[str, Any]) -> None:
        try:
            await websocket.send(json.dumps(payload))
        except Exception:
            pass


async def serve(
    repo_root: Path,
    app_root: Path,
    host: str = "127.0.0.1",
    port: int = 4174,
) -> None:
    """Start the companion WebSocket server."""
    try:
        import websockets
    except ImportError:
        logger.error(
            "The 'websockets' package is required for the companion server. "
            "Install it with: pip install websockets"
        )
        raise SystemExit(1)

    server = CompanionServer(repo_root=repo_root, app_root=app_root)
    logger.info("Companion server starting on ws://%s:%d", host, port)

    async with websockets.serve(server.handle_websocket, host, port):
        logger.info("Companion server ready on ws://%s:%d", host, port)
        await asyncio.Future()  # run forever
