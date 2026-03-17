#!/usr/bin/env bash

set -u

failures=0
warnings=0

pass() {
    printf '[pass] %s\n' "$1"
}

warn() {
    printf '[warn] %s\n' "$1"
    warnings=$((warnings + 1))
}

fail() {
    printf '[fail] %s\n' "$1"
    failures=$((failures + 1))
}

is_wsl() {
    if [ -n "${WSL_DISTRO_NAME:-}" ] || [ -n "${WSL_INTEROP:-}" ]; then
        return 0
    fi

    case "$(uname -r 2>/dev/null)" in
        *[Mm]icrosoft*|*[Ww][Ss][Ll]*)
            return 0
            ;;
    esac

    return 1
}

check_command() {
    local command_name="$1"
    local requirement="$2"

    if command -v "$command_name" >/dev/null 2>&1; then
        pass "Found command: $command_name ($(command -v "$command_name"))"
        return 0
    fi

    if [ "$requirement" = "required" ]; then
        fail "Missing required command: $command_name"
    else
        warn "Optional command not found: $command_name"
    fi
}

printf 'Verifying local audio stack for voice-mode in WSL.\n'
printf 'This verifier checks the known-good WSL assumptions without changing your machine.\n\n'

if [ -f "$HOME/.asoundrc" ]; then
    pass "Found ALSA bridge file: $HOME/.asoundrc"

    if grep -Eq 'type[[:space:]]+(pulse|pipewire)' "$HOME/.asoundrc"; then
        pass "~/.asoundrc references a PulseAudio or PipeWire bridge"
    else
        warn "~/.asoundrc exists but does not mention pulse or pipewire"
    fi
else
    fail "Missing ~/.asoundrc. The known-good WSL setup used a user-level ALSA bridge."
fi

check_command arecord required
check_command aplay optional
check_command pactl optional

if command -v arecord >/dev/null 2>&1; then
    if arecord --version >/dev/null 2>&1; then
        pass "arecord responds"
    else
        fail "arecord is installed but did not respond to --version"
    fi

    if arecord -L >/dev/null 2>&1; then
        pass "ALSA PCM enumeration works"
    else
        warn "arecord -L failed. ALSA device discovery may be incomplete."
    fi
fi

if is_wsl; then
    pass "WSL environment detected"

    pulse_bridge_found=0

    if [ -n "${PULSE_SERVER:-}" ]; then
        pass "PULSE_SERVER is set"
        pulse_bridge_found=1
    fi

    if [ -d /mnt/wslg ]; then
        pass "WSLg runtime directory exists at /mnt/wslg"
        pulse_bridge_found=1
    fi

    if [ -n "${XDG_RUNTIME_DIR:-}" ] && [ -S "${XDG_RUNTIME_DIR}/pulse/native" ]; then
        pass "Pulse socket exists at ${XDG_RUNTIME_DIR}/pulse/native"
        pulse_bridge_found=1
    fi

    if [ "$pulse_bridge_found" -eq 0 ]; then
        fail "No WSL audio bridge clues detected. Expected PULSE_SERVER, /mnt/wslg, or a Pulse socket."
    fi
else
    warn "WSL was not detected. WSL-specific audio assumptions were skipped."
fi

if command -v pactl >/dev/null 2>&1; then
    if pactl info >/dev/null 2>&1; then
        pass "pactl can talk to a PulseAudio or PipeWire server"
    else
        warn "pactl exists but could not talk to a PulseAudio or PipeWire server"
    fi
fi

printf '\nSummary: %s failure(s), %s warning(s).\n' "$failures" "$warnings"

if [ "$failures" -eq 0 ]; then
    printf 'audio-stack-ok\n'
    exit 0
fi

exit 1
