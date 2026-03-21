"""Session and profile memory store, extracted from SupervisorService."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _utc_now_label() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _clean_text(value: Any, limit: int = 0) -> str:
    if not isinstance(value, str):
        return ""
    normalized = " ".join(value.strip().split())
    if limit and len(normalized) > limit:
        return f"{normalized[: max(0, limit - 3)].rstrip()}..."
    return normalized


def _normalize_text_list(raw_value: Any, *, limit: int = 6, item_limit: int = 220) -> list[str]:
    if not isinstance(raw_value, list):
        return []
    cleaned: list[str] = []
    for item in raw_value[:limit]:
        text = _clean_text(item, item_limit)
        if text:
            cleaned.append(text)
    return cleaned


class MemoryStore:
    """File-backed session and profile memory.

    Two-lane model:
    - session memory: shared project-lane state (Claude session, realtime connection)
    - profile memory: per-character state (goal, custom instructions, transcript)

    Both are persisted as JSON files under the runtime directory.
    """

    def __init__(self, runtime_dir: Path):
        self.session_memory_dir = runtime_dir / "session_memory"
        self.session_memory_dir.mkdir(parents=True, exist_ok=True)
        self.profile_memory_dir = runtime_dir / "profile_memory"
        self.profile_memory_dir.mkdir(parents=True, exist_ok=True)
        self.pending_approval_dir = runtime_dir / "pending_approvals"
        self.pending_approval_dir.mkdir(parents=True, exist_ok=True)

    # ── Public API ───────────────────────────────────────────────────

    def get_session_memory(
        self,
        session_id: str,
        profile_session_id: str | None = None,
    ) -> dict[str, Any]:
        shared = self._empty_shared() | self._read_json(self._session_path(session_id))
        profile = self._empty_profile()
        stored = self._read_json(self._profile_path(profile_session_id)) if profile_session_id else {}
        if stored:
            profile |= stored
        else:
            profile |= self._legacy_profile(shared)

        memory = shared | profile
        memory["projectSessionId"] = session_id
        memory["profileSessionId"] = profile_session_id or str(shared.get("profileSessionId") or session_id)
        memory["updatedAt"] = profile.get("updatedAt") or shared.get("updatedAt")
        memory["interfaceSummary"] = memory.get("interfaceSummary") or self._build_interface_summary(memory)
        if not isinstance(memory.get("transcriptPreview"), list):
            memory["transcriptPreview"] = []
        return memory

    def merge_browser_state(
        self,
        session_id: str,
        profile_session_id: str | None,
        browser_state: dict[str, Any] | None,
    ) -> dict[str, Any]:
        normalized = self._normalize_browser_state(browser_state)
        shared = self._empty_shared() | self._read_json(self._session_path(session_id))
        profile = self._empty_profile()
        existing = self._read_json(self._profile_path(profile_session_id)) if profile_session_id else {}
        if existing:
            profile |= existing
        else:
            profile |= self._legacy_profile(shared)

        if not normalized:
            return self.get_session_memory(session_id, profile_session_id)

        shared.update({
            "projectSessionId": session_id,
            "profileSessionId": profile_session_id or shared.get("profileSessionId") or session_id,
            "voice": normalized.get("voice") or "marin",
            "turnDetection": normalized.get("turnDetection") or "semantic_vad",
            "realtimeStatus": normalized.get("realtimeStatus") or "Idle",
            "supervisorStatus": normalized.get("supervisorStatus") or "Loading supervisor state",
            "realtimeConnected": bool(normalized.get("realtimeConnected")),
            "liveTerminalEnabled": bool(normalized.get("liveTerminalEnabled", True)),
            "pendingApprovalCount": int(normalized.get("pendingApprovalCount") or 0),
            "updatedAt": _utc_now_label(),
        })
        self._write_json(self._session_path(session_id), shared)

        if profile_session_id:
            profile.update({
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
                "updatedAt": shared["updatedAt"],
            })
            self._write_json(self._profile_path(profile_session_id), profile)

        return self.get_session_memory(session_id, profile_session_id)

    def build_agent_context_block(self, memory: dict[str, Any]) -> str:
        """Format memory into a text block suitable for agent instructions."""
        if not memory:
            return ""

        lines = []
        profile = memory.get("profileLabel")
        if profile:
            lines.append(f"Active profile: {profile}")
        goal = _clean_text(memory.get("currentGoal"), 320)
        if goal:
            lines.append(f"Current user goal: {goal}")
        last_turn = _clean_text(memory.get("lastUserTurn"), 320)
        if last_turn:
            lines.append(f"Last spoken turn: {last_turn}")
        draft = _clean_text(memory.get("manualPromptDraft"), 320)
        if draft:
            lines.append(f"Current Claude prompt draft: {draft}")
        custom = _clean_text(memory.get("customInstructions"), 500)
        if custom:
            lines.append(f"Custom instructions: {custom}")
        summary = memory.get("interfaceSummary")
        if summary:
            lines.append(f"Interface state: {summary}")

        if not lines:
            return ""

        return "Current session context:\n" + "\n".join(f"- {line}" for line in lines)

    # ── Approval helpers ─────────────────────────────────────────────

    def read_pending_approvals(self, session_id: str) -> list[dict[str, Any]]:
        raw = self._read_json(self._approval_path(session_id))
        return raw if isinstance(raw, list) else []

    def queue_approval(self, session_id: str, prompt: str, source: str = "voice") -> str:
        from uuid import uuid4

        approval_id = f"direct_{uuid4().hex}"
        approval = {
            "callId": approval_id,
            "toolName": "send_prompt",
            "arguments": {"prompt": prompt, "source": source},
            "prompt": prompt,
            "source": source,
        }
        pending = self.read_pending_approvals(session_id)
        pending.append(approval)
        self._write_json(self._approval_path(session_id), pending)
        return approval_id

    def pop_approval(self, session_id: str, call_id: str) -> dict[str, Any] | None:
        pending = self.read_pending_approvals(session_id)
        match = next((item for item in pending if str(item.get("callId") or "") == call_id), None)
        if match is None:
            return None
        remaining = [item for item in pending if item is not match]
        if remaining:
            self._write_json(self._approval_path(session_id), remaining)
        else:
            self._approval_path(session_id).unlink(missing_ok=True)
        return match

    def pop_latest_approval(self, session_id: str) -> dict[str, Any] | None:
        pending = self.read_pending_approvals(session_id)
        if not pending:
            return None
        return self.pop_approval(session_id, str(pending[-1].get("callId") or ""))

    # ── Internal ─────────────────────────────────────────────────────

    def _safe_key(self, session_id: str) -> str:
        return "".join(c if c.isalnum() or c in {"-", "_"} else "_" for c in session_id)

    def _session_path(self, session_id: str) -> Path:
        return self.session_memory_dir / f"{self._safe_key(session_id)}.json"

    def _profile_path(self, profile_session_id: str | None) -> Path | None:
        if not profile_session_id:
            return None
        return self.profile_memory_dir / f"{self._safe_key(profile_session_id)}.json"

    def _approval_path(self, session_id: str) -> Path:
        return self.pending_approval_dir / f"{self._safe_key(session_id)}.json"

    def _read_json(self, path: Path | None) -> dict[str, Any] | list:
        if path is None:
            return {}
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}

    def _write_json(self, path: Path | None, data: Any) -> None:
        if path is None:
            return
        path.write_text(json.dumps(data), encoding="utf-8")

    def _empty_shared(self) -> dict[str, Any]:
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

    def _empty_profile(self) -> dict[str, Any]:
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

    def _legacy_profile(self, shared: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(shared, dict):
            return {}
        return {
            "profileLabel": _clean_text(shared.get("profileLabel"), 120),
            "presetId": _clean_text(shared.get("presetId"), 80),
            "presetTitle": _clean_text(shared.get("presetTitle"), 120),
            "assistantStyle": _clean_text(shared.get("assistantStyle"), 40),
            "customInstructions": _clean_text(shared.get("customInstructions"), 1200),
            "currentGoal": _clean_text(shared.get("currentGoal"), 320),
            "lastUserTurn": _clean_text(shared.get("lastUserTurn"), 500),
            "manualPromptDraft": _clean_text(shared.get("manualPromptDraft"), 700),
            "transcriptPreview": shared.get("transcriptPreview") if isinstance(shared.get("transcriptPreview"), list) else [],
            "updatedAt": shared.get("updatedAt"),
        }

    def _build_interface_summary(self, memory: dict[str, Any]) -> str:
        realtime_label = "Realtime connected" if memory.get("realtimeConnected") else "Realtime idle"
        profile_label = str(memory.get("profileLabel") or "Base coding voice mode / brief")
        project_session = str(memory.get("projectSessionId") or "shared Claude lane")
        supervisor_status = str(memory.get("supervisorStatus") or "Supervisor ready")
        live_terminal = "Live terminal active" if memory.get("liveTerminalEnabled") else "Live terminal paused"
        pending = int(memory.get("pendingApprovalCount") or 0)
        approval_label = (
            "No approvals pending."
            if pending == 0
            else f"{pending} approval{'s' if pending != 1 else ''} pending."
        )
        return (
            f"{realtime_label}. Shared Claude lane {project_session}. "
            f"Current character lane {profile_label}. "
            f"{supervisor_status}. {live_terminal}. {approval_label}"
        )

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
            "mentorBullets": _normalize_text_list(browser_state.get("mentorBullets"), item_limit=220),
            "mentorRisks": _normalize_text_list(browser_state.get("mentorRisks"), item_limit=220),
            "mentorFiles": _normalize_text_list(browser_state.get("mentorFiles"), item_limit=220),
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
