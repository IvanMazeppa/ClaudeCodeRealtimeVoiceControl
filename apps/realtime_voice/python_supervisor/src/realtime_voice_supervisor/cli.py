from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from .supervisor import SupervisorService


def _read_payload(raw_payload: str | None) -> dict:
    if raw_payload:
        return json.loads(raw_payload)

    raw = sys.stdin.read().strip()
    if not raw:
        return {}
    return json.loads(raw)


async def _run() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "command",
        choices=[
            "health",
            "state",
            "sync-browser-state",
            "ensure-session",
            "observe",
            "handle-turn",
            "manual-prompt",
            "interrupt",
            "decision",
            "explain-latest",
            "second-opinion",
            "draft-claude-prompt",
            "explain-approval",
        ],
    )
    parser.add_argument(
        "--app-root",
        default=str(Path(__file__).resolve().parents[3]),
        help="Absolute path to apps/realtime_voice.",
    )
    parser.add_argument(
        "--repo-root",
        default=str(Path(__file__).resolve().parents[5]),
        help="Absolute path to repository root.",
    )
    parser.add_argument(
        "--payload-json",
        default=None,
        help="JSON payload passed from the Node bridge.",
    )
    args = parser.parse_args()

    app_root = Path(args.app_root).resolve()
    repo_root = Path(args.repo_root).resolve()
    service = SupervisorService(repo_root=repo_root, app_root=app_root)
    payload = _read_payload(args.payload_json)
    session_id = str(payload.get("sessionId") or "default")
    profile_session_id = str(payload.get("profileSessionId") or "").strip() or None
    browser_state = payload.get("browserState")

    if browser_state is not None and args.command not in {"health", "sync-browser-state"}:
        await service.sync_browser_state(session_id, profile_session_id, browser_state)

    if args.command == "health":
        result = await service.health(str(payload.get("sessionId") or "") or None, profile_session_id)
    elif args.command == "state":
        result = await service.state(session_id, profile_session_id)
    elif args.command == "sync-browser-state":
        result = await service.sync_browser_state(
            session_id,
            profile_session_id,
            browser_state if isinstance(browser_state, dict) else {},
        )
    elif args.command == "ensure-session":
        result = await service.ensure_claude_session(session_id, profile_session_id)
    elif args.command == "observe":
        result = await service.observe(session_id, profile_session_id)
    elif args.command == "handle-turn":
        result = await service.handle_turn(
            session_id,
            profile_session_id,
            str(payload.get("userText") or ""),
        )
    elif args.command == "manual-prompt":
        result = await service.send_manual_prompt(
            session_id,
            profile_session_id,
            str(payload.get("prompt") or ""),
        )
    elif args.command == "interrupt":
        result = await service.interrupt_claude(session_id, profile_session_id)
    elif args.command == "explain-latest":
        result = await service.explain_latest_changes(session_id, profile_session_id)
    elif args.command == "second-opinion":
        result = await service.second_opinion(
            session_id,
            profile_session_id,
            str(payload.get("goal") or payload.get("userText") or ""),
        )
    elif args.command == "draft-claude-prompt":
        result = await service.draft_claude_prompt(
            session_id,
            profile_session_id,
            str(payload.get("goal") or payload.get("userText") or ""),
        )
    elif args.command == "explain-approval":
        result = await service.explain_approval(
            session_id,
            profile_session_id,
            str(payload.get("callId") or ""),
        )
    else:
        result = await service.resolve_approval(
            session_id,
            profile_session_id,
            str(payload.get("callId") or ""),
            approve=bool(payload.get("approve")),
            always=bool(payload.get("always", False)),
            rejection_message=payload.get("rejectionMessage"),
        )

    print(json.dumps(result))
    return 0 if result.get("ok") else 1


def main() -> None:
    raise SystemExit(asyncio.run(_run()))


if __name__ == "__main__":
    main()
