#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
HOME_DIR="${HOME}"

usage() {
    cat <<'EOF'
Usage: scripts/sync_local_config.sh [--home-dir PATH]

This script is dry-run by default. It only prints merge-only config fragments and
warnings for:
  - ~/.claude.json
  - ~/.cursor/mcp.json
  - ~/.voicemode/voicemode.env

It never replaces whole config files.
EOF
}

while [ $# -gt 0 ]; do
    case "$1" in
        --home-dir)
            shift
            if [ $# -eq 0 ]; then
                printf '[fail] Missing value after --home-dir\n' >&2
                exit 1
            fi
            HOME_DIR="$1"
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            usage
            printf '[fail] Unknown argument: %s\n' "$1" >&2
            exit 1
            ;;
    esac
    shift
done

printf 'This script performs merge-only config suggestions. It never replaces whole config files.\n'

python3 - "${REPO_ROOT}" "${HOME_DIR}" <<'PY'
import json
import pathlib
import sys

repo_root = pathlib.Path(sys.argv[1]).resolve()
home_dir = pathlib.Path(sys.argv[2]).expanduser()


def print_header(label: str, path: pathlib.Path) -> None:
    print()
    print(f"[{label}] Target: {path}")


def load_json(path: pathlib.Path):
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"[warn] {path} contains invalid JSON: {exc}")
        return "INVALID"


def print_fragment(label: str, fragment: dict) -> None:
    print(f"[{label}] Suggested fragment to merge:")
    print(json.dumps(fragment, indent=2, sort_keys=True))


def print_full_file_example(label: str, template: dict) -> None:
    print(f"[{label}] Suggested full-file example for a fresh setup:")
    print(json.dumps(template, indent=2, sort_keys=True))


def analyze_json_target(label: str, live_path: pathlib.Path, template: dict, fragment: dict) -> None:
    print_header(label, live_path)

    current = load_json(live_path)
    if current is None:
        print(f"[{label}] Live file is missing. Create it manually from the full-file example below.")
        print_full_file_example(label, template)
        return

    if current == "INVALID":
        print(f"[{label}] Refusing to suggest an automatic merge into invalid JSON.")
        print_fragment(label, fragment)
        return

    if not isinstance(current, dict):
        print(f"[warn] {live_path} is not a JSON object. Merge manually.")
        print_fragment(label, fragment)
        return

    extra_root_keys = sorted(key for key in current.keys() if key != "mcpServers")
    current_servers = current.get("mcpServers", {})

    if "mcpServers" in current and not isinstance(current_servers, dict):
        print(f"[warn] {live_path} has a non-object mcpServers value. Merge manually.")
        print_fragment(label, fragment)
        return

    extra_servers = sorted(key for key in current_servers.keys() if key != "voice-mode")

    if extra_root_keys or extra_servers:
        print("[warn] Live file already contains unrelated settings. Merge manually and do not replace the whole file.")
        if extra_root_keys:
            print(f"[warn] Unrelated root keys: {', '.join(extra_root_keys)}")
        if extra_servers:
            print(f"[warn] Other MCP servers: {', '.join(extra_servers)}")

    current_fragment = current_servers.get("voice-mode")
    desired_fragment = fragment["voice-mode"]

    if current_fragment is None:
        print(f"[{label}] voice-mode fragment is missing.")
    elif current_fragment == desired_fragment:
        print(f"[{label}] voice-mode fragment already matches the repo template.")
    else:
        print(f"[{label}] voice-mode fragment exists but differs from the repo template.")

    print_fragment(label, fragment)


def parse_env(path: pathlib.Path):
    parsed = {}
    if not path.exists():
        return None
    for raw_line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        parsed[key] = value
    return parsed


claude_template = json.loads((repo_root / "templates" / "claude-mcp.example.json").read_text(encoding="utf-8"))
cursor_template = json.loads((repo_root / "templates" / "cursor-mcp.example.json").read_text(encoding="utf-8"))
voicemode_template_path = repo_root / "templates" / "voicemode.env.example"
voicemode_template_text = voicemode_template_path.read_text(encoding="utf-8")
voicemode_template_map = parse_env(voicemode_template_path) or {}
voicemode_template_lines = [
    line
    for line in voicemode_template_text.splitlines()
    if line and not line.lstrip().startswith("#")
]

analyze_json_target(
    "claude",
    home_dir / ".claude.json",
    claude_template,
    {"voice-mode": claude_template["mcpServers"]["voice-mode"]},
)

analyze_json_target(
    "cursor",
    home_dir / ".cursor" / "mcp.json",
    cursor_template,
    {"voice-mode": cursor_template["mcpServers"]["voice-mode"]},
)

voicemode_live_path = home_dir / ".voicemode" / "voicemode.env"
print_header("voicemode-env", voicemode_live_path)

live_env = parse_env(voicemode_live_path)
if live_env is None:
    print("[voicemode-env] Live file is missing. Create it manually and copy only the lines you need.")
else:
    extra_env_keys = sorted(key for key in live_env.keys() if key not in voicemode_template_map)
    if extra_env_keys:
        print("[warn] Live file already contains unrelated settings. Review manually before adding template lines.")
        print(f"[warn] Unrelated env keys: {', '.join(extra_env_keys)}")

    missing_keys = sorted(key for key in voicemode_template_map.keys() if key not in live_env)
    differing_keys = sorted(
        key
        for key, value in voicemode_template_map.items()
        if key in live_env and live_env[key] != value
    )

    if not missing_keys and not differing_keys:
        print("[voicemode-env] Template keys are already present with the same values.")
    else:
        if missing_keys:
            print(f"[voicemode-env] Missing template keys: {', '.join(missing_keys)}")
        if differing_keys:
            print(f"[voicemode-env] Template keys with different values: {', '.join(differing_keys)}")

print("[voicemode-env] Suggested lines to merge or create:")
for line in voicemode_template_lines:
    print(line)
PY
