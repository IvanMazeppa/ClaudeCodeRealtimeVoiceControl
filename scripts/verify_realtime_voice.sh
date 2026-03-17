#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
APP_DIR="${REPO_ROOT}/apps/realtime_voice"

if ! command -v node >/dev/null 2>&1; then
    printf '[fail] node was not found on PATH\n' >&2
    exit 1
fi

if ! command -v npm >/dev/null 2>&1; then
    printf '[fail] npm was not found on PATH\n' >&2
    exit 1
fi

printf '[pass] node found at %s\n' "$(command -v node)"
printf '[pass] npm found at %s\n' "$(command -v npm)"

if [ -f "${APP_DIR}/package.json" ]; then
    printf '[pass] realtime package manifest exists\n'
else
    printf '[fail] missing %s/package.json\n' "${APP_DIR}" >&2
    exit 1
fi

if [ -f "${APP_DIR}/server.mjs" ]; then
    printf '[pass] realtime server exists\n'
else
    printf '[fail] missing %s/server.mjs\n' "${APP_DIR}" >&2
    exit 1
fi

if [ -f "${APP_DIR}/.env" ]; then
    printf '[pass] local realtime .env exists\n'
elif [ -n "${OPENAI_API_KEY:-}" ]; then
    printf '[pass] OPENAI_API_KEY is set in the current shell\n'
else
    printf '[warn] local realtime .env is missing and OPENAI_API_KEY is not set in the current shell\n'
fi

printf 'realtime-voice-files-ok\n'
