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

if ! command -v npm >/dev/null 2>&1; then
    printf '[fail] npm was not found on PATH\n' >&2
    exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
    printf '[fail] python3 was not found on PATH\n' >&2
    exit 1
fi

if ! command -v tmux >/dev/null 2>&1; then
    printf '[fail] tmux was not found on PATH\n' >&2
    exit 1
fi

if ! command -v claude >/dev/null 2>&1; then
    printf '[fail] claude was not found on PATH\n' >&2
    exit 1
fi

printf '[pass] node found at %s\n' "$(command -v node)"
printf '[pass] npm found at %s\n' "$(command -v npm)"
printf '[pass] python3 found at %s\n' "$(command -v python3)"
printf '[pass] tmux found at %s\n' "$(command -v tmux)"
printf '[pass] claude found at %s\n' "$(command -v claude)"

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

if [ -f "${APP_DIR}/public/app.js" ]; then
    printf '[pass] browser app exists\n'
else
    printf '[fail] missing %s/public/app.js\n' "${APP_DIR}" >&2
    exit 1
fi

if [ -f "${SUPERVISOR_DIR}/pyproject.toml" ]; then
    printf '[pass] Python supervisor manifest exists\n'
else
    printf '[fail] missing %s/pyproject.toml\n' "${SUPERVISOR_DIR}" >&2
    exit 1
fi

for required_file in \
    "${SUPERVISOR_DIR}/src/realtime_voice_supervisor/cli.py" \
    "${SUPERVISOR_DIR}/src/realtime_voice_supervisor/supervisor.py" \
    "${SUPERVISOR_DIR}/src/realtime_voice_supervisor/models.py" \
    "${SUPERVISOR_DIR}/src/realtime_voice_supervisor/prompts.py" \
    "${SUPERVISOR_DIR}/src/realtime_voice_supervisor/repo_tools.py" \
    "${SUPERVISOR_DIR}/src/realtime_voice_supervisor/git_tools.py" \
    "${SUPERVISOR_DIR}/src/realtime_voice_supervisor/mentor.py"
do
    if [ -f "${required_file}" ]; then
        printf '[pass] supervisor source exists: %s\n' "${required_file#${REPO_ROOT}/}"
    else
        printf '[fail] missing %s\n' "${required_file}" >&2
        exit 1
    fi
done

for mentor_route in \
    "/api/supervisor/explain-latest" \
    "/api/supervisor/second-opinion" \
    "/api/supervisor/draft-claude-prompt" \
    "/api/supervisor/explain-approval"
do
    if rg -Fq "app.post(\"${mentor_route}\"" "${APP_DIR}/server.mjs"; then
        printf '[pass] mentor endpoint exists in server.mjs: %s\n' "${mentor_route}"
    else
        printf '[fail] missing mentor endpoint in server.mjs: %s\n' "${mentor_route}" >&2
        exit 1
    fi
done

for mentor_command in \
    "explain-latest" \
    "second-opinion" \
    "draft-claude-prompt" \
    "explain-approval"
do
    if rg -Fq "\"${mentor_command}\"" "${SUPERVISOR_DIR}/src/realtime_voice_supervisor/cli.py"; then
        printf '[pass] mentor CLI command exists: %s\n' "${mentor_command}"
    else
        printf '[fail] missing mentor CLI command: %s\n' "${mentor_command}" >&2
        exit 1
    fi
done

if [ -f "${APP_DIR}/config/claude-bridge.json" ]; then
    printf '[pass] Claude bridge config exists\n'
else
    printf '[fail] missing %s/config/claude-bridge.json\n' "${APP_DIR}" >&2
    exit 1
fi

if [ -f "${APP_DIR}/.env" ]; then
    printf '[pass] local realtime .env exists\n'
elif [ -n "${OPENAI_API_KEY:-}" ]; then
    printf '[pass] OPENAI_API_KEY is set in the current shell\n'
else
    printf '[warn] local realtime .env is missing and OPENAI_API_KEY is not set in the current shell\n'
fi

if [ -x "${SUPERVISOR_PYTHON}" ]; then
    if "${SUPERVISOR_PYTHON}" -c '
import realtime_voice_supervisor, agents
from realtime_voice_supervisor.mentor import build_change_explainer_agent
from realtime_voice_supervisor.supervisor import SupervisorService
' >/dev/null 2>&1; then
        printf '[pass] Python supervisor virtual environment is ready\n'
    else
        printf '[warn] Python supervisor virtual environment exists but imports failed\n'
    fi
else
    printf '[warn] Python supervisor virtual environment is missing; run scripts/start_realtime_voice.sh once to create it\n'
fi

if node --check "${APP_DIR}/server.mjs" >/dev/null 2>&1; then
    printf '[pass] server.mjs passed node --check\n'
else
    printf '[fail] server.mjs has a syntax error\n' >&2
    exit 1
fi

if node --check "${APP_DIR}/public/app.js" >/dev/null 2>&1; then
    printf '[pass] public/app.js passed node --check\n'
else
    printf '[fail] public/app.js has a syntax error\n' >&2
    exit 1
fi

if python3 -m py_compile "${SUPERVISOR_DIR}"/src/realtime_voice_supervisor/*.py >/dev/null 2>&1; then
    printf '[pass] supervisor package passed py_compile\n'
else
    printf '[fail] supervisor package failed py_compile\n' >&2
    exit 1
fi

printf 'realtime-voice-files-ok\n'
