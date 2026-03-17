#!/usr/bin/env bash

set -u

PINNED_VERSION="8.5.1"
SMOKE_MESSAGE="Voice check."
TIMEOUT_SECONDS=45

usage() {
    cat <<'EOF'
Usage: scripts/verify_voicemode.sh [--timeout SECONDS]

Verifies that the pinned stable voice-mode command can launch and then runs the
one-shot no-wait smoke command:

  uvx --from voice-mode==8.5.1 voice-mode converse --message "Voice check." --no-wait
EOF
}

pass() {
    printf '[pass] %s\n' "$1"
}

warn() {
    printf '[warn] %s\n' "$1"
}

fail() {
    printf '[fail] %s\n' "$1" >&2
    exit 1
}

run_timed() {
    if command -v timeout >/dev/null 2>&1; then
        timeout "${TIMEOUT_SECONDS}s" "$@"
    else
        "$@"
    fi
}

while [ $# -gt 0 ]; do
    case "$1" in
        --timeout)
            shift
            if [ $# -eq 0 ]; then
                fail "Missing value after --timeout"
            fi
            TIMEOUT_SECONDS="$1"
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            usage
            fail "Unknown argument: $1"
            ;;
    esac
    shift
done

launch_cmd=(
    uvx
    --from
    "voice-mode==${PINNED_VERSION}"
    voice-mode
    converse
    --help
)

smoke_cmd=(
    uvx
    --from
    "voice-mode==${PINNED_VERSION}"
    voice-mode
    converse
    --message
    "${SMOKE_MESSAGE}"
    --no-wait
)

printf 'Verifying pinned stable voice-mode command: voice-mode==%s\n' "$PINNED_VERSION"

if ! command -v uvx >/dev/null 2>&1; then
    fail "uvx was not found on PATH"
fi
pass "Found uvx at $(command -v uvx)"

if [ -n "${OPENAI_API_KEY:-}" ]; then
    pass "OPENAI_API_KEY is set in the current shell"
elif [ -f "$HOME/.voicemode/voicemode.env" ]; then
    warn "OPENAI_API_KEY is not set in the current shell. voice-mode may rely on ~/.voicemode/voicemode.env or other env injection."
else
    warn "OPENAI_API_KEY is not set and ~/.voicemode/voicemode.env is missing. The smoke test may fail for auth reasons."
fi

printf 'Launch check: %s\n' "${launch_cmd[*]}"
if run_timed "${launch_cmd[@]}" >/dev/null 2>&1; then
    pass "Pinned stable voice-mode command launched successfully"
else
    status=$?
    if [ "$status" -eq 124 ]; then
        fail "Pinned stable voice-mode launch check timed out after ${TIMEOUT_SECONDS}s"
    fi
    fail "Pinned stable voice-mode command could not launch"
fi

printf 'Smoke check: %s\n' "${smoke_cmd[*]}"
if run_timed "${smoke_cmd[@]}"; then
    pass "Pinned stable one-shot speech smoke test completed"
    printf 'voicemode-ok\n'
    exit 0
else
    status=$?
fi
if [ "$status" -eq 124 ]; then
    fail "Pinned stable voice-mode smoke test timed out after ${TIMEOUT_SECONDS}s"
fi

fail "Pinned stable voice-mode smoke test failed"
