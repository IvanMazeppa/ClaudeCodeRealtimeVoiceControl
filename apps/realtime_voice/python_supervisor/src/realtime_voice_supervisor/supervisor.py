from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from agents import Agent, Runner, RunState, SQLiteSession, function_tool, trace
from agents.run_context import RunContextWrapper
from pydantic import BaseModel

from .harness import ClaudeTerminalHarness
from .mentor import (
    build_approval_explainer_agent,
    build_change_explainer_agent,
    build_mentor_agent,
    build_prompt_drafter_agent,
    build_second_opinion_agent,
)


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
        "latest_git_branch": "",
        "latest_git_status": "",
        "latest_git_diff_summary": "",
        "latest_repo_search": "",
        "last_mentor_mode": "",
        "last_mentor_summary": "",
    }


def _clean_text(value: Any, limit: int = 0) -> str:
    if not isinstance(value, str):
        return ""

    normalized = " ".join(value.strip().split())
    if limit and len(normalized) > limit:
        return f"{normalized[: max(0, limit - 3)].rstrip()}..."
    return normalized


def _utc_now_label() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


class SupervisorService:
    def __init__(self, repo_root: Path, app_root: Path):
        self.repo_root = repo_root
        self.app_root = app_root
        self.runtime_dir = app_root / "python_supervisor" / ".runtime"
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        self.session_db_path = self.runtime_dir / "sessions.sqlite3"
        self.run_state_dir = self.runtime_dir / "run_state"
        self.run_state_dir.mkdir(parents=True, exist_ok=True)
        self.pending_approval_dir = self.runtime_dir / "pending_approvals"
        self.pending_approval_dir.mkdir(parents=True, exist_ok=True)
        self.session_memory_dir = self.runtime_dir / "session_memory"
        self.session_memory_dir.mkdir(parents=True, exist_ok=True)
        self.profile_memory_dir = self.runtime_dir / "profile_memory"
        self.profile_memory_dir.mkdir(parents=True, exist_ok=True)
        self.bridge_config_path = app_root / "config" / "claude-bridge.json"
        self.harness = ClaudeTerminalHarness(repo_root=repo_root, config_path=self.bridge_config_path)
        self.supervisor_model = os.environ.get("REALTIME_SUPERVISOR_MODEL", "gpt-5.4")
        self.mentor_agent = build_mentor_agent(self.supervisor_model, self.repo_root, self.harness)
        self.change_explainer_agent = build_change_explainer_agent(
            self.supervisor_model,
            self.repo_root,
            self.harness,
        )
        self.second_opinion_agent = build_second_opinion_agent(
            self.supervisor_model,
            self.repo_root,
            self.harness,
        )
        self.prompt_drafter_agent = build_prompt_drafter_agent(
            self.supervisor_model,
            self.repo_root,
            self.harness,
        )
        self.approval_explainer_agent = build_approval_explainer_agent(
            self.supervisor_model,
            self.repo_root,
            self.harness,
        )
        self.voice_supervisor_agent = self._build_agent_graph()

    async def health(
        self,
        session_id: str | None = None,
        profile_session_id: str | None = None,
    ) -> dict[str, Any]:
        bridge = self.harness.load_config()
        terminal = await self.harness.get_terminal_state(bridge)
        return {
            "ok": True,
            "sessionId": session_id,
            "supervisorModel": self.supervisor_model,
            "bridge": {
                "sessionName": bridge.session_name,
                "workingDirectory": str(bridge.working_directory),
                "command": bridge.command,
            },
            "terminal": terminal,
            "pendingApprovals": await self._load_pending_approvals(session_id) if session_id else [],
            "sessionMemory": self._session_memory_payload(session_id, profile_session_id)
            if session_id
            else self._empty_session_memory(),
        }

    async def state(self, session_id: str, profile_session_id: str | None = None) -> dict[str, Any]:
        bridge = self.harness.load_config()
        terminal = await self.harness.get_terminal_state(bridge)
        pending_approvals = await self._load_pending_approvals(session_id)
        return self._build_direct_response(
            session_id,
            profile_session_id=profile_session_id,
            spoken_response="",
            terminal=terminal,
            action_log=[],
            pending_approvals=pending_approvals,
        )

    async def sync_browser_state(
        self,
        session_id: str,
        profile_session_id: str | None,
        browser_state: dict[str, Any] | None,
    ) -> dict[str, Any]:
        self._merge_browser_state(session_id, profile_session_id, browser_state)
        bridge = self.harness.load_config()
        terminal = await self.harness.get_terminal_state(bridge)
        return self._build_direct_response(
            session_id,
            profile_session_id=profile_session_id,
            spoken_response="",
            terminal=terminal,
            action_log=[],
            pending_approvals=await self._load_pending_approvals(session_id),
        )

    async def ensure_claude_session(
        self,
        session_id: str,
        profile_session_id: str | None = None,
    ) -> dict[str, Any]:
        bridge = self.harness.load_config()
        created = await self.harness.ensure_session(bridge)
        terminal = await self.harness.get_terminal_state(bridge)
        result = self._build_direct_response(
            session_id,
            profile_session_id=profile_session_id,
            spoken_response=(
                "Claude Code is ready."
                if terminal["session_exists"]
                else "I could not find or start the Claude session."
            ),
            terminal=terminal,
            action_log=[
                {
                    "type": "attach_or_verify_session",
                    "detail": "Started a new Claude session." if created else "Verified the existing Claude session.",
                }
            ],
            pending_approvals=await self._load_pending_approvals(session_id),
        )
        result["created"] = created
        return result

    async def interrupt_claude(
        self,
        session_id: str,
        profile_session_id: str | None = None,
    ) -> dict[str, Any]:
        output = await self.harness.interrupt()
        state = await self.harness.get_terminal_state()
        if output:
            state["output"] = output
        return self._build_direct_response(
            session_id,
            profile_session_id=profile_session_id,
            spoken_response="Sent an interrupt to Claude.",
            terminal=state,
            action_log=[{"type": "interrupt_run", "detail": "Sent Ctrl+C to the Claude session."}],
            pending_approvals=await self._load_pending_approvals(session_id),
        )

    async def observe(
        self,
        session_id: str,
        profile_session_id: str | None = None,
    ) -> dict[str, Any]:
        bridge = self.harness.load_config()
        terminal = await self.harness.get_terminal_state(bridge)
        pending_approvals = await self._load_pending_approvals(session_id)
        return self._build_direct_response(
            session_id,
            profile_session_id=profile_session_id,
            spoken_response=self._summarize_terminal_state(terminal, pending_approvals),
            terminal=terminal,
            action_log=[{"type": "capture_output", "detail": "Captured the visible Claude terminal output."}],
            pending_approvals=pending_approvals,
        )

    async def send_manual_prompt(
        self,
        session_id: str,
        profile_session_id: str | None,
        prompt: str,
    ) -> dict[str, Any]:
        return await self._dispatch_prompt(session_id, profile_session_id, prompt, source="manual")

    async def handle_turn(
        self,
        session_id: str,
        profile_session_id: str | None,
        user_text: str,
    ) -> dict[str, Any]:
        return await self._dispatch_prompt(session_id, profile_session_id, user_text, source="spoken")

    async def explain_latest_changes(
        self,
        session_id: str,
        profile_session_id: str | None = None,
    ) -> dict[str, Any]:
        return await self._run_agent(
            self.change_explainer_agent,
            session_id,
            profile_session_id,
            (
                "Explain the latest repository changes for the user. "
                "Always call git_current_branch, git_status_summary, and git_diff_summary first. "
                "Read files only when needed to clarify intent. "
                "Keep the spoken response to one or two short sentences."
            ),
            trace_name="realtime-voice-mentor",
        )

    async def second_opinion(
        self,
        session_id: str,
        profile_session_id: str | None,
        goal: str,
    ) -> dict[str, Any]:
        return await self._run_agent(
            self.second_opinion_agent,
            session_id,
            profile_session_id,
            (
                "Give a second opinion on Claude Code's current direction. "
                "Start by capturing Claude terminal state. "
                "Use git status and diff context when relevant.\n\n"
                f"User goal or concern:\n{goal.strip() or 'Please review the current direction.'}"
            ),
            trace_name="realtime-voice-mentor",
        )

    async def draft_claude_prompt(
        self,
        session_id: str,
        profile_session_id: str | None,
        goal: str,
    ) -> dict[str, Any]:
        return await self._run_agent(
            self.prompt_drafter_agent,
            session_id,
            profile_session_id,
            (
                "Draft a strong prompt for Claude Code based on the user's goal. "
                "Capture Claude terminal state first when it is relevant. "
                "Use repo context only when it materially improves the prompt.\n\n"
                f"User goal:\n{goal.strip() or 'Help me continue the current task.'}"
            ),
            trace_name="realtime-voice-mentor",
        )

    async def explain_approval(
        self,
        session_id: str,
        profile_session_id: str | None,
        call_id: str,
    ) -> dict[str, Any]:
        pending = await self._load_pending_approval(session_id, call_id)
        if not pending:
            return {
                "ok": False,
                "error": "No matching pending approval was found for explanation.",
            }

        result = await self._run_agent(
            self.approval_explainer_agent,
            session_id,
            profile_session_id,
            (
                "Explain this pending supervisor approval for the user.\n\n"
                f"Tool name: {pending['toolName']}\n"
                f"Arguments: {pending['arguments']}\n"
                "Explain why it was likely flagged, what it is likely to do, and whether approval or "
                "rejection is safer."
            ),
            trace_name="realtime-voice-mentor",
        )

        terminal = await self.harness.get_terminal_state(self.harness.load_config())
        result["terminalSnapshot"] = terminal.get("output", "")
        result["terminalReady"] = bool(terminal.get("ready"))
        result["claudeSessionExists"] = bool(terminal.get("session_exists"))
        result["pendingApprovals"] = await self._load_pending_approvals(session_id)
        return result

    async def resolve_approval(
        self,
        session_id: str,
        profile_session_id: str | None,
        call_id: str,
        *,
        approve: bool,
        always: bool = False,
        rejection_message: str | None = None,
    ) -> dict[str, Any]:
        direct_match = await self._load_direct_pending_approval(session_id, call_id)
        if direct_match is not None:
            bridge = self.harness.load_config()
            if approve:
                output = await self.harness.send_prompt(
                    str(direct_match.get("prompt") or ""),
                    config=bridge,
                    settle_ms=bridge.startup_settle_ms,
                )
                terminal = await self.harness.get_terminal_state(bridge)
                if output:
                    terminal["output"] = output
                await self._remove_direct_pending_approval(session_id, call_id)
                return self._build_direct_response(
                    session_id,
                    profile_session_id=profile_session_id,
                    spoken_response="Approved and sent that prompt to Claude.",
                    terminal=terminal,
                    action_log=[
                        {
                            "type": "send_prompt",
                            "detail": f"Sent an approved Claude prompt: {str(direct_match.get('prompt') or '')[:120]}",
                        }
                    ],
                    pending_approvals=await self._load_pending_approvals(session_id),
                )

            await self._remove_direct_pending_approval(session_id, call_id)
            terminal = await self.harness.get_terminal_state(bridge)
            return self._build_direct_response(
                session_id,
                profile_session_id=profile_session_id,
                spoken_response="Rejected that prompt. Nothing was sent to Claude.",
                terminal=terminal,
                action_log=[
                    {
                        "type": "reject_prompt",
                        "detail": rejection_message or "The user rejected a queued Claude prompt.",
                    }
                ],
                pending_approvals=await self._load_pending_approvals(session_id),
            )

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

        return await self._build_result_payload(
            result,
            session_id,
            profile_session_id=profile_session_id,
            update_approval_state=True,
        )

    async def _run_agent(
        self,
        agent: Agent[dict[str, Any]],
        session_id: str,
        profile_session_id: str | None,
        user_text: str,
        *,
        trace_name: str,
        update_approval_state: bool = False,
    ) -> dict[str, Any]:
        agent_session_id = profile_session_id or session_id
        session = SQLiteSession(agent_session_id, str(self.session_db_path))
        context = _default_context(session_id)
        context["profile_session_id"] = agent_session_id
        memory = self._session_memory_payload(session_id, profile_session_id)
        context["session_memory"] = memory
        input_text = self._build_agent_input(user_text, memory)

        with trace(trace_name, group_id=agent_session_id):
            result = await Runner.run(
                agent,
                input_text,
                session=session,
                context=context,
            )

        return await self._build_result_payload(
            result,
            session_id,
            profile_session_id=profile_session_id,
            update_approval_state=update_approval_state,
        )

    async def _dispatch_prompt(
        self,
        session_id: str,
        profile_session_id: str | None,
        prompt: str,
        *,
        source: str,
    ) -> dict[str, Any]:
        normalized_prompt = prompt.strip()
        if not normalized_prompt:
            return self._build_direct_response(
                session_id,
                profile_session_id=profile_session_id,
                spoken_response="There is no prompt to send yet.",
                terminal=await self.harness.get_terminal_state(self.harness.load_config()),
                action_log=[],
                pending_approvals=await self._load_pending_approvals(session_id),
            )

        bridge = self.harness.load_config()
        created = await self.harness.ensure_session(bridge)

        if self._prompt_needs_approval(normalized_prompt):
            approval = {
                "callId": f"direct_{uuid4().hex}",
                "toolName": "send_prompt",
                "arguments": {
                    "prompt": normalized_prompt,
                    "source": source,
                },
                "prompt": normalized_prompt,
                "source": source,
            }
            approvals = await self._append_direct_pending_approval(session_id, approval)
            terminal = await self.harness.get_terminal_state(bridge)
            detail = "Queued a prompt for approval before sending it to Claude."
            if created:
                detail = f"Started Claude and {detail[0].lower()}{detail[1:]}"
            return self._build_direct_response(
                session_id,
                profile_session_id=profile_session_id,
                spoken_response="Approval is required before I send that prompt to Claude.",
                terminal=terminal,
                action_log=[{"type": "prompt_approval_required", "detail": detail}],
                pending_approvals=approvals,
            )

        output = await self.harness.send_prompt(
            normalized_prompt,
            config=bridge,
            settle_ms=bridge.startup_settle_ms,
        )
        terminal = await self.harness.get_terminal_state(bridge)
        if output:
            terminal["output"] = output

        detail = (
            "Sent the last heard turn to Claude."
            if source == "spoken"
            else "Sent the manual draft to Claude."
        )
        if created:
            detail = f"Started Claude and {detail[0].lower()}{detail[1:]}"
        return self._build_direct_response(
            session_id,
            profile_session_id=profile_session_id,
            spoken_response="Sent that prompt to Claude. The terminal view will keep updating below.",
            terminal=terminal,
            action_log=[{"type": "send_prompt", "detail": detail}],
            pending_approvals=await self._load_pending_approvals(session_id),
        )

    async def _build_result_payload(
        self,
        result: Any,
        session_id: str,
        *,
        profile_session_id: str | None = None,
        update_approval_state: bool = False,
    ) -> dict[str, Any]:
        state = result.to_state()
        serialized = state.to_json()
        context = serialized.get("context", {}).get("context", {}) or {}
        interruptions = state.get_interruptions()

        if update_approval_state:
            if interruptions:
                self._state_path(session_id).write_text(state.to_string(), encoding="utf-8")
            else:
                self._state_path(session_id).unlink(missing_ok=True)

        if update_approval_state:
            pending_approvals = [self._serialize_interruption(item) for item in interruptions]
        else:
            pending_approvals = await self._load_pending_approvals(session_id)

        spoken_response, mentor_payload = self._mentor_payload_from_output(result.final_output)
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
            "pendingApprovals": pending_approvals,
            "mentor": mentor_payload,
            "sessionMemory": self._session_memory_payload(session_id, profile_session_id),
        }

    def _build_direct_response(
        self,
        session_id: str,
        *,
        profile_session_id: str | None = None,
        spoken_response: str,
        terminal: dict[str, Any],
        action_log: list[dict[str, Any]],
        pending_approvals: list[dict[str, Any]],
    ) -> dict[str, Any]:
        return {
            "ok": True,
            "sessionId": session_id,
            "supervisorModel": self.supervisor_model,
            "spokenResponse": spoken_response,
            "terminalSnapshot": terminal.get("output", ""),
            "terminalReady": bool(terminal.get("ready")),
            "claudeSessionExists": bool(terminal.get("session_exists")),
            "actionLog": action_log,
            "pendingApprovals": pending_approvals,
            "mentor": self._empty_mentor_payload(),
            "sessionMemory": self._session_memory_payload(session_id, profile_session_id),
        }

    def _serialize_interruption(self, item: Any) -> dict[str, Any]:
        return {
            "callId": _tool_call_id(item),
            "toolName": _tool_name(item),
            "arguments": getattr(item, "arguments", None),
        }

    async def _load_pending_approval(self, session_id: str, call_id: str) -> dict[str, Any] | None:
        direct_match = await self._load_direct_pending_approval(session_id, call_id)
        if direct_match is not None:
            return self._serialize_direct_pending_approval(direct_match)

        state_path = self._state_path(session_id)
        if not state_path.exists():
            return None

        state = await RunState.from_string(
            self.voice_supervisor_agent,
            state_path.read_text(encoding="utf-8"),
        )
        interruptions = state.get_interruptions()
        if call_id:
            match = next((item for item in interruptions if _tool_call_id(item) == call_id), None)
            return self._serialize_interruption(match) if match else None
        if len(interruptions) == 1:
            return self._serialize_interruption(interruptions[0])
        return None

    async def _load_pending_approvals(self, session_id: str) -> list[dict[str, Any]]:
        direct = [
            self._serialize_direct_pending_approval(item)
            for item in self._read_direct_pending_approvals(session_id)
        ]
        state_path = self._state_path(session_id)
        if not state_path.exists():
            return direct

        state = await RunState.from_string(
            self.voice_supervisor_agent,
            state_path.read_text(encoding="utf-8"),
        )
        return direct + [self._serialize_interruption(item) for item in state.get_interruptions()]

    def _serialize_direct_pending_approval(self, item: dict[str, Any]) -> dict[str, Any]:
        return {
            "callId": str(item.get("callId") or ""),
            "toolName": str(item.get("toolName") or "send_prompt"),
            "arguments": item.get("arguments") or {},
        }

    async def _append_direct_pending_approval(
        self,
        session_id: str,
        approval: dict[str, Any],
    ) -> list[dict[str, Any]]:
        pending = self._read_direct_pending_approvals(session_id)
        pending.append(approval)
        self._write_direct_pending_approvals(session_id, pending)
        return await self._load_pending_approvals(session_id)

    async def _load_direct_pending_approval(
        self,
        session_id: str,
        call_id: str,
    ) -> dict[str, Any] | None:
        pending = self._read_direct_pending_approvals(session_id)
        if call_id:
            return next((item for item in pending if str(item.get("callId") or "") == call_id), None)
        if len(pending) == 1:
            return pending[0]
        return None

    async def _remove_direct_pending_approval(self, session_id: str, call_id: str) -> None:
        pending = self._read_direct_pending_approvals(session_id)
        remaining = [item for item in pending if str(item.get("callId") or "") != call_id]
        self._write_direct_pending_approvals(session_id, remaining)

    def _mentor_payload_from_output(self, final_output: Any) -> tuple[str, dict[str, Any]]:
        empty = self._empty_mentor_payload()
        if isinstance(final_output, BaseModel):
            data = final_output.model_dump()
            spoken_response = str(data.pop("spoken_response", "")).strip()
            return spoken_response, {
                "screenSummary": data.get("screen_summary", ""),
                "bullets": list(data.get("bullets") or []),
                "risks": list(data.get("risks") or []),
                "recommendedNextStep": data.get("recommended_next_step"),
                "changedFiles": list(data.get("changed_files") or []),
                "verdict": data.get("verdict"),
                "draftedFollowUpPrompt": data.get("drafted_follow_up_prompt"),
                "draftedPrompt": data.get("drafted_prompt"),
                "approvalRecommendation": data.get("approval_recommendation"),
                "approvalReason": data.get("approval_reason"),
            }
        return str(final_output or "").strip(), empty

    def _empty_mentor_payload(self) -> dict[str, Any]:
        return {
            "screenSummary": "",
            "bullets": [],
            "risks": [],
            "recommendedNextStep": None,
            "changedFiles": [],
            "verdict": None,
            "draftedFollowUpPrompt": None,
            "draftedPrompt": None,
            "approvalRecommendation": None,
            "approvalReason": None,
        }

    def _safe_session_key(self, session_id: str) -> str:
        return "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in session_id)

    def _state_path(self, session_id: str) -> Path:
        return self.run_state_dir / f"{self._safe_session_key(session_id)}.json"

    def _session_memory_path(self, session_id: str) -> Path:
        return self.session_memory_dir / f"{self._safe_session_key(session_id)}.json"

    def _profile_memory_path(self, profile_session_id: str) -> Path:
        return self.profile_memory_dir / f"{self._safe_session_key(profile_session_id)}.json"

    def _direct_approval_path(self, session_id: str) -> Path:
        return self.pending_approval_dir / f"{self._safe_session_key(session_id)}.json"

    def _read_direct_pending_approvals(self, session_id: str) -> list[dict[str, Any]]:
        path = self._direct_approval_path(session_id)
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        return raw if isinstance(raw, list) else []

    def _write_direct_pending_approvals(
        self,
        session_id: str,
        approvals: list[dict[str, Any]],
    ) -> None:
        path = self._direct_approval_path(session_id)
        if approvals:
            path.write_text(json.dumps(approvals), encoding="utf-8")
        else:
            path.unlink(missing_ok=True)

    def _prompt_needs_approval(self, prompt: str) -> bool:
        normalized = prompt.lower()
        return any(marker in normalized for marker in RISKY_PROMPT_MARKERS)

    def _empty_shared_memory(self) -> dict[str, Any]:
        return {
            "projectSessionId": "",
            "profileSessionId": "",
            "voice": "marin",
            "turnDetection": "semantic_vad",
            "realtimeStatus": "Idle",
            "supervisorStatus": "Loading supervisor state",
            "realtimeConnected": False,
            "liveTerminalEnabled": True,
            "pendingApprovalCount": 0,
            "updatedAt": None,
        }

    def _empty_profile_memory(self) -> dict[str, Any]:
        return {
            "profileLabel": "Base coding voice mode / brief",
            "presetId": "",
            "presetTitle": "",
            "assistantStyle": "brief",
            "customInstructions": "",
            "currentGoal": "",
            "lastUserTurn": "",
            "manualPromptDraft": "",
            "latestMentorDraft": "",
            "mentorSummary": "",
            "mentorBullets": [],
            "mentorRisks": [],
            "mentorFiles": [],
            "transcriptPreview": [],
            "updatedAt": None,
        }

    def _empty_session_memory(self) -> dict[str, Any]:
        memory = self._empty_shared_memory() | self._empty_profile_memory()
        memory["interfaceSummary"] = "The supervisor has not received browser context yet."
        return memory

    def _read_session_memory(self, session_id: str) -> dict[str, Any]:
        path = self._session_memory_path(session_id)
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return raw if isinstance(raw, dict) else {}

    def _write_session_memory(self, session_id: str, memory: dict[str, Any]) -> None:
        self._session_memory_path(session_id).write_text(json.dumps(memory), encoding="utf-8")

    def _read_profile_memory(self, profile_session_id: str | None) -> dict[str, Any]:
        if not profile_session_id:
            return {}

        path = self._profile_memory_path(profile_session_id)
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return raw if isinstance(raw, dict) else {}

    def _write_profile_memory(self, profile_session_id: str, memory: dict[str, Any]) -> None:
        self._profile_memory_path(profile_session_id).write_text(json.dumps(memory), encoding="utf-8")

    def _normalize_text_list(
        self,
        raw_value: Any,
        *,
        limit: int = 6,
        item_limit: int = 220,
    ) -> list[str]:
        if not isinstance(raw_value, list):
            return []

        cleaned: list[str] = []
        for item in raw_value[:limit]:
            text = _clean_text(item, item_limit)
            if text:
                cleaned.append(text)
        return cleaned

    def _legacy_profile_memory(self, shared_memory: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(shared_memory, dict):
            return {}

        return {
            "profileLabel": _clean_text(shared_memory.get("profileLabel"), 120),
            "presetId": _clean_text(shared_memory.get("presetId"), 80),
            "presetTitle": _clean_text(shared_memory.get("presetTitle"), 120),
            "assistantStyle": _clean_text(shared_memory.get("assistantStyle"), 40),
            "customInstructions": _clean_text(shared_memory.get("customInstructions"), 1200),
            "currentGoal": _clean_text(shared_memory.get("currentGoal"), 320),
            "lastUserTurn": _clean_text(shared_memory.get("lastUserTurn"), 500),
            "manualPromptDraft": _clean_text(shared_memory.get("manualPromptDraft"), 700),
            "transcriptPreview": shared_memory.get("transcriptPreview") if isinstance(shared_memory.get("transcriptPreview"), list) else [],
            "updatedAt": shared_memory.get("updatedAt"),
        }

    def _normalize_browser_state(self, browser_state: dict[str, Any] | None) -> dict[str, Any]:
        if not isinstance(browser_state, dict):
            return {}

        transcript_preview: list[dict[str, str]] = []
        raw_transcript = browser_state.get("transcriptPreview")
        if isinstance(raw_transcript, list):
            for item in raw_transcript[:6]:
                if not isinstance(item, dict):
                    continue
                role = _clean_text(item.get("role"), 24).lower() or "unknown"
                text = _clean_text(item.get("text"), 320)
                if text:
                    transcript_preview.append({"role": role, "text": text})

        normalized = {
            "projectSessionId": _clean_text(browser_state.get("sessionId"), 120),
            "profileSessionId": _clean_text(browser_state.get("profileSessionId"), 180),
            "profileLabel": _clean_text(browser_state.get("profileLabel"), 120),
            "presetId": _clean_text(browser_state.get("selectedPresetId"), 80),
            "presetTitle": _clean_text(browser_state.get("selectedPresetTitle"), 120),
            "assistantStyle": _clean_text(browser_state.get("assistantStyle"), 40),
            "voice": _clean_text(browser_state.get("voice"), 40),
            "turnDetection": _clean_text(browser_state.get("turnDetection"), 40),
            "customInstructions": _clean_text(browser_state.get("customInstructions"), 1200),
            "currentGoal": _clean_text(browser_state.get("mentorGoal"), 320),
            "realtimeStatus": _clean_text(browser_state.get("realtimeStatus"), 80),
            "supervisorStatus": _clean_text(browser_state.get("supervisorStatus"), 80),
            "lastUserTurn": _clean_text(browser_state.get("lastUserTurn"), 500),
            "manualPromptDraft": _clean_text(browser_state.get("manualPromptDraft"), 700),
            "latestMentorDraft": _clean_text(browser_state.get("latestMentorDraft"), 700),
            "mentorSummary": _clean_text(browser_state.get("mentorSummary"), 700),
            "mentorBullets": self._normalize_text_list(browser_state.get("mentorBullets"), item_limit=220),
            "mentorRisks": self._normalize_text_list(browser_state.get("mentorRisks"), item_limit=220),
            "mentorFiles": self._normalize_text_list(browser_state.get("mentorFiles"), item_limit=220),
            "realtimeConnected": bool(browser_state.get("realtimeConnected")),
            "liveTerminalEnabled": bool(browser_state.get("liveTerminalEnabled", True)),
            "pendingApprovalCount": int(browser_state.get("pendingApprovalCount") or 0),
            "transcriptPreview": transcript_preview,
        }

        if not normalized["profileLabel"]:
            preset_title = normalized["presetTitle"] or "Base coding voice mode"
            style = normalized["assistantStyle"] or "brief"
            normalized["profileLabel"] = f"{preset_title} / {style}"

        return normalized

    def _build_interface_summary(self, memory: dict[str, Any]) -> str:
        realtime_label = "Realtime connected" if memory.get("realtimeConnected") else "Realtime idle"
        profile_label = str(memory.get("profileLabel") or "Base coding voice mode / brief")
        project_session = str(memory.get("projectSessionId") or "shared Claude lane")
        supervisor_status = str(memory.get("supervisorStatus") or "Supervisor ready")
        live_terminal = "Live terminal active" if memory.get("liveTerminalEnabled") else "Live terminal paused"
        pending_approvals = int(memory.get("pendingApprovalCount") or 0)
        approval_label = (
            "No approvals pending."
            if pending_approvals == 0
            else f"{pending_approvals} approval{'s' if pending_approvals != 1 else ''} pending."
        )
        return (
            f"{realtime_label}. Shared Claude lane {project_session}. "
            f"Current character lane {profile_label}. "
            f"{supervisor_status}. {live_terminal}. {approval_label}"
        )

    def _merge_browser_state(
        self,
        session_id: str,
        profile_session_id: str | None,
        browser_state: dict[str, Any] | None,
    ) -> dict[str, Any]:
        normalized = self._normalize_browser_state(browser_state)
        shared_memory = self._empty_shared_memory() | self._read_session_memory(session_id)
        profile_memory = self._empty_profile_memory()
        existing_profile = self._read_profile_memory(profile_session_id)
        if existing_profile:
            profile_memory |= existing_profile
        else:
            profile_memory |= self._legacy_profile_memory(shared_memory)

        if not normalized:
            return self._session_memory_payload(session_id, profile_session_id)

        shared_memory.update(
            {
                "projectSessionId": session_id,
                "profileSessionId": profile_session_id or shared_memory.get("profileSessionId") or session_id,
                "voice": normalized.get("voice") or "marin",
                "turnDetection": normalized.get("turnDetection") or "semantic_vad",
                "realtimeStatus": normalized.get("realtimeStatus") or "Idle",
                "supervisorStatus": normalized.get("supervisorStatus") or "Loading supervisor state",
                "realtimeConnected": bool(normalized.get("realtimeConnected")),
                "liveTerminalEnabled": bool(normalized.get("liveTerminalEnabled", True)),
                "pendingApprovalCount": int(normalized.get("pendingApprovalCount") or 0),
                "updatedAt": _utc_now_label(),
            }
        )
        self._write_session_memory(session_id, shared_memory)

        if profile_session_id:
            profile_memory.update(
                {
                    "profileLabel": normalized.get("profileLabel") or "Base coding voice mode / brief",
                    "presetId": normalized.get("presetId") or "",
                    "presetTitle": normalized.get("presetTitle") or "",
                    "assistantStyle": normalized.get("assistantStyle") or "brief",
                    "customInstructions": normalized.get("customInstructions") or "",
                    "currentGoal": normalized.get("currentGoal") or "",
                    "lastUserTurn": normalized.get("lastUserTurn") or "",
                    "manualPromptDraft": normalized.get("manualPromptDraft") or "",
                    "latestMentorDraft": normalized.get("latestMentorDraft") or "",
                    "mentorSummary": normalized.get("mentorSummary") or "",
                    "mentorBullets": list(normalized.get("mentorBullets") or []),
                    "mentorRisks": list(normalized.get("mentorRisks") or []),
                    "mentorFiles": list(normalized.get("mentorFiles") or []),
                    "transcriptPreview": list(normalized.get("transcriptPreview") or []),
                    "updatedAt": shared_memory["updatedAt"],
                }
            )
            self._write_profile_memory(profile_session_id, profile_memory)

        return self._session_memory_payload(session_id, profile_session_id)

    def _session_memory_payload(
        self,
        session_id: str,
        profile_session_id: str | None = None,
    ) -> dict[str, Any]:
        shared_memory = self._empty_shared_memory() | self._read_session_memory(session_id)
        profile_memory = self._empty_profile_memory()
        stored_profile = self._read_profile_memory(profile_session_id)
        if stored_profile:
            profile_memory |= stored_profile
        else:
            profile_memory |= self._legacy_profile_memory(shared_memory)

        memory = shared_memory | profile_memory
        memory["projectSessionId"] = session_id
        memory["profileSessionId"] = profile_session_id or str(shared_memory.get("profileSessionId") or session_id)
        memory["updatedAt"] = profile_memory.get("updatedAt") or shared_memory.get("updatedAt")
        memory["interfaceSummary"] = memory.get("interfaceSummary") or self._build_interface_summary(memory)
        transcript_preview = memory.get("transcriptPreview")
        if not isinstance(transcript_preview, list):
            memory["transcriptPreview"] = []
        return memory

    def _build_agent_input(self, user_text: str, memory: dict[str, Any]) -> str:
        lines = [
            f"- shared Claude lane: {memory.get('projectSessionId')}",
            f"- active character lane: {memory.get('profileLabel')}",
            f"- interface summary: {memory.get('interfaceSummary')}",
        ]
        current_goal = _clean_text(memory.get("currentGoal"), 320)
        if current_goal:
            lines.append(f"- current user goal: {current_goal}")
        last_user_turn = _clean_text(memory.get("lastUserTurn"), 320)
        if last_user_turn:
            lines.append(f"- latest spoken turn: {last_user_turn}")
        manual_prompt = _clean_text(memory.get("manualPromptDraft"), 320)
        if manual_prompt:
            lines.append(f"- current manual Claude draft: {manual_prompt}")
        custom_instructions = _clean_text(memory.get("customInstructions"), 500)
        if custom_instructions:
            lines.append(f"- local custom instructions: {custom_instructions}")
        latest_mentor_draft = _clean_text(memory.get("latestMentorDraft"), 320)
        if latest_mentor_draft:
            lines.append(f"- latest mentor draft: {latest_mentor_draft}")

        transcript_preview = memory.get("transcriptPreview") or []
        if isinstance(transcript_preview, list) and transcript_preview:
            preview_parts = []
            for item in transcript_preview[:4]:
                if not isinstance(item, dict):
                    continue
                role = _clean_text(item.get("role"), 24) or "unknown"
                text = _clean_text(item.get("text"), 160)
                if text:
                    preview_parts.append(f"{role}: {text}")
            if preview_parts:
                lines.append(f"- recent transcript: {' | '.join(preview_parts)}")

        memory_block = "\n".join(lines)
        request = user_text.strip()
        return (
            "Active browser session memory and interface context:\n"
            f"{memory_block}\n\n"
            "Current request:\n"
            f"{request}"
        )

    def _summarize_terminal_state(
        self,
        terminal: dict[str, Any],
        pending_approvals: list[dict[str, Any]],
    ) -> str:
        if pending_approvals:
            count = len(pending_approvals)
            noun = "approval" if count == 1 else "approvals"
            return f"{count} {noun} {'is' if count == 1 else 'are'} waiting. Review the approval cards before Claude continues."

        if not terminal.get("session_exists"):
            return "Claude is not attached yet. Start or verify the Claude session first."

        if terminal.get("ready"):
            output = str(terminal.get("output") or "")
            if "Welcome back!" in output:
                return "Claude is idle at the welcome screen. You can send a prompt now."
            return "Claude is idle and ready for another prompt."

        return "Claude is still working. The terminal view below will keep updating while it runs."

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
                "Use the mentor specialist whenever the user wants explanations, repo summaries, or a second opinion. "
                "If a request does not require a specialist, answer directly and briefly. "
                "Keep spoken-style responses short, calm, and actionable."
            ),
            tools=[
                claude_terminal_agent.as_tool(
                    tool_name="work_with_claude_terminal",
                    tool_description="Read, summarize, interrupt, or send prompts to the Claude Code terminal.",
                ),
                self.mentor_agent.as_tool(
                    tool_name="work_with_mentor",
                    tool_description="Explain repo changes, summarize Claude state, and provide second-opinion guidance.",
                ),
            ],
        )

        return supervisor_agent
