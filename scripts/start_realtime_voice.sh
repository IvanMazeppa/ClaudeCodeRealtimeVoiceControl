#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
APP_DIR="${REPO_ROOT}/apps/realtime_voice"

if ! command -v npm >/dev/null 2>&1; then
    printf '[fail] npm was not found on PATH\n' >&2
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

printf '[info] Starting realtime voice app from %s\n' "${APP_DIR}"
npm run dev --prefix "${APP_DIR}"
