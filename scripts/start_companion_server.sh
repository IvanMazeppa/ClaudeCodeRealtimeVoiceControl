#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
APP_DIR="${REPO_ROOT}/apps/realtime_voice"
SUPERVISOR_DIR="${APP_DIR}/python_supervisor"
SUPERVISOR_VENV="${SUPERVISOR_DIR}/.venv"
SUPERVISOR_PYTHON="${SUPERVISOR_VENV}/bin/python"

HOST="${COMPANION_HOST:-127.0.0.1}"
PORT="${COMPANION_PORT:-4174}"

if ! command -v python3 >/dev/null 2>&1; then
    printf '[fail] python3 was not found on PATH\n' >&2
    exit 1
fi

if [ -z "${OPENAI_API_KEY:-}" ] && [ ! -f "${APP_DIR}/.env" ]; then
    printf '[fail] Missing %s/.env and OPENAI_API_KEY is not set\n' "${APP_DIR}" >&2
    exit 1
fi

if [ ! -x "${SUPERVISOR_PYTHON}" ]; then
    printf '[info] Creating Python supervisor virtual environment\n'
    python3 -m venv "${SUPERVISOR_VENV}"
fi

if ! "${SUPERVISOR_PYTHON}" -c 'import realtime_voice_supervisor, agents, websockets' >/dev/null 2>&1; then
    printf '[info] Installing Python supervisor dependencies\n'
    "${SUPERVISOR_PYTHON}" -m pip install --upgrade pip >/dev/null
    "${SUPERVISOR_PYTHON}" -m pip install -e "${SUPERVISOR_DIR}"
fi

# Source .env if it exists (for OPENAI_API_KEY)
if [ -f "${APP_DIR}/.env" ]; then
    set -a
    # shellcheck source=/dev/null
    . "${APP_DIR}/.env"
    set +a
fi

printf '[info] Starting companion WebSocket server on ws://%s:%s\n' "${HOST}" "${PORT}"
exec "${SUPERVISOR_PYTHON}" -m realtime_voice_supervisor.cli serve \
    --app-root "${APP_DIR}" \
    --repo-root "${REPO_ROOT}" \
    --host "${HOST}" \
    --port "${PORT}"
