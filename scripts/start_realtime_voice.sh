#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
APP_DIR="${REPO_ROOT}/apps/realtime_voice"
SUPERVISOR_DIR="${APP_DIR}/python_supervisor"
SUPERVISOR_VENV="${SUPERVISOR_DIR}/.venv"
SUPERVISOR_PYTHON="${SUPERVISOR_VENV}/bin/python"

if ! command -v node >/dev/null 2>&1; then
    printf '[fail] node was not found on PATH\n' >&2
    exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
    printf '[fail] python3 was not found on PATH\n' >&2
    exit 1
fi

if [ ! -f "${APP_DIR}/.env" ] && [ -z "${OPENAI_API_KEY:-}" ]; then
    printf '[fail] Missing %s/.env and OPENAI_API_KEY is not set in the current shell\n' "${APP_DIR}" >&2
    printf '[info] Start from %s/.env.example or export OPENAI_API_KEY before launching\n' "${APP_DIR}" >&2
    exit 1
fi

if [ ! -d "${APP_DIR}/node_modules" ]; then
    printf '[info] Installing realtime voice dependencies\n'
    npm install --prefix "${APP_DIR}"
fi

if [ ! -x "${SUPERVISOR_PYTHON}" ]; then
    printf '[info] Creating Python supervisor virtual environment\n'
    python3 -m venv "${SUPERVISOR_VENV}"
fi

if ! "${SUPERVISOR_PYTHON}" -c 'import realtime_voice_supervisor, agents' >/dev/null 2>&1; then
    printf '[info] Installing Python supervisor dependencies\n'
    "${SUPERVISOR_PYTHON}" -m pip install --upgrade pip >/dev/null
    "${SUPERVISOR_PYTHON}" -m pip install -e "${SUPERVISOR_DIR}"
fi

export REALTIME_SUPERVISOR_PYTHON="${SUPERVISOR_PYTHON}"

printf '[info] Starting realtime voice app from %s\n' "${APP_DIR}"
exec node "${APP_DIR}/server.mjs"
