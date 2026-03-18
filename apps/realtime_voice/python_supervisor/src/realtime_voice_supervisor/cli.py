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
            "ensure-session",
            "observe",
            "handle-turn",
            "manual-prompt",
            "interrupt",
            "decision",
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

    if args.command == "health":
        result = await service.health()
    elif args.command == "ensure-session":
        result = await service.ensure_claude_session(str(payload.get("sessionId") or "default"))
    elif args.command == "observe":
        result = await service.observe(str(payload.get("sessionId") or "default"))
    elif args.command == "handle-turn":
        result = await service.handle_turn(
            str(payload.get("sessionId") or "default"),
            str(payload.get("userText") or ""),
        )
    elif args.command == "manual-prompt":
        result = await service.send_manual_prompt(
            str(payload.get("sessionId") or "default"),
            str(payload.get("prompt") or ""),
        )
    elif args.command == "interrupt":
        result = await service.interrupt_claude(str(payload.get("sessionId") or "default"))
    else:
        result = await service.resolve_approval(
            str(payload.get("sessionId") or "default"),
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
