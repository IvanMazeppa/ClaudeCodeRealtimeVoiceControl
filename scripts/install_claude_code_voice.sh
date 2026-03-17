#!/usr/bin/env bash

set -euo pipefail

# Safety contract for this installer:
# - Default behavior is non-destructive.
# - Never overwrite ~/.claude.json wholesale.
# - Never overwrite ~/.cursor/mcp.json wholesale.
# - Never overwrite ~/.voicemode/voicemode.env unless explicitly asked.
# - Prefer next steps and merge-only suggestions over silent mutation.
# - Treat voice-mode==8.5.1 as the pinned stable dependency unless the caller
#   explicitly opts into experimentation.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

PINNED_STABLE_VERSION="8.5.1"
SELECTED_VERSION="${PINNED_STABLE_VERSION}"
SKIP_SYNC=0
RUN_AUDIO_CHECK=0
RUN_VOICE_SMOKE=0
RUN_PATCH_DRY_RUN=0
APPLY_CLI_PATCH=0
PATCH_TARGET=""
OVERWRITE_VOICEMODE_ENV=0
failures=0

usage() {
    cat <<'EOF'
Usage: scripts/install_claude_code_voice.sh [options]

Guided installer for the stable Claude Code plus voice-mode workflow.
Default behavior is read-only except for the optional --overwrite-voicemode-env
and --apply-cli-patch flags.

Options:
  --experimental-version VERSION  Opt into experimentation instead of 8.5.1.
  --skip-sync                     Skip merge-only config suggestions.
  --run-audio-check               Run scripts/verify_audio_stack.sh.
  --run-voice-smoke               Run scripts/verify_voicemode.sh for 8.5.1.
  --dry-run-cli-patch             Run the patch locator in dry-run mode.
  --apply-cli-patch               Apply the 8.5.1 CLI patch after a dry-run.
  --patch-target PATH             Pass a specific install path through to
                                  scripts/apply_voicemode_patch.sh.
  --overwrite-voicemode-env       Replace ~/.voicemode/voicemode.env from the repo template.
  -h, --help                      Show this help text.

Patch targeting:
  Use --patch-target when multiple installed voice-mode copies exist and you
  want the installer to target one specific site-packages, voice_mode, or
  voice_mode/cli.py path for the CLI patch dry-run or apply step.
EOF
}

note() {
    printf '[info] %s\n' "$1"
}

warn() {
    printf '[warn] %s\n' "$1"
}

record_failure() {
    printf '[fail] %s\n' "$1" >&2
    failures=$((failures + 1))
}

run_step() {
    local label="$1"
    shift

    printf '\n[%s]\n' "$label"
    if "$@"; then
        note "${label} completed"
    else
        record_failure "${label} failed"
    fi
}

write_voicemode_env() {
    local target_dir="${HOME}/.voicemode"
    local target_file="${target_dir}/voicemode.env"
    local template_file="${REPO_ROOT}/templates/voicemode.env.example"

    mkdir -p "${target_dir}"

    if [ -f "${target_file}" ]; then
        local backup_file
        backup_file="${target_file}.bak.$(date +%Y%m%d%H%M%S)"
        cp "${target_file}" "${backup_file}"
        note "Backed up existing ${target_file} to ${backup_file}"
    fi

    cp "${template_file}" "${target_file}"
    note "Overwrote ${target_file} because --overwrite-voicemode-env was explicitly requested"
}

while [ $# -gt 0 ]; do
    case "$1" in
        --experimental-version)
            shift
            if [ $# -eq 0 ]; then
                record_failure "Missing value after --experimental-version"
                exit 1
            fi
            SELECTED_VERSION="$1"
            ;;
        --skip-sync)
            SKIP_SYNC=1
            ;;
        --run-audio-check)
            RUN_AUDIO_CHECK=1
            ;;
        --run-voice-smoke)
            RUN_VOICE_SMOKE=1
            ;;
        --dry-run-cli-patch)
            RUN_PATCH_DRY_RUN=1
            ;;
        --apply-cli-patch)
            APPLY_CLI_PATCH=1
            ;;
        --patch-target)
            shift
            if [ $# -eq 0 ]; then
                record_failure "Missing value after --patch-target"
                exit 1
            fi
            PATCH_TARGET="$1"
            ;;
        --overwrite-voicemode-env)
            OVERWRITE_VOICEMODE_ENV=1
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            usage
            record_failure "Unknown argument: $1"
            exit 1
            ;;
    esac
    shift
done

required_paths=(
    "${REPO_ROOT}/templates/claude-mcp.example.json"
    "${REPO_ROOT}/templates/cursor-mcp.example.json"
    "${REPO_ROOT}/templates/voicemode.env.example"
    "${REPO_ROOT}/patches/voice-mode/8.5.1/cli-empty-tts.patch"
    "${SCRIPT_DIR}/sync_local_config.sh"
    "${SCRIPT_DIR}/verify_audio_stack.sh"
    "${SCRIPT_DIR}/verify_voicemode.sh"
    "${SCRIPT_DIR}/apply_voicemode_patch.sh"
)

for required_path in "${required_paths[@]}"; do
    if [ ! -e "${required_path}" ]; then
        record_failure "Required repo path is missing: ${required_path}"
    fi
done

printf 'Claude Code voice installer\n\n'
printf 'Safety contract:\n'
printf '%s\n' '- Default behavior is non-destructive.'
printf '%s\n' '- This script never overwrites ~/.claude.json wholesale.'
printf '%s\n' '- This script never overwrites ~/.cursor/mcp.json wholesale.'
printf '%s\n' '- This script never overwrites ~/.voicemode/voicemode.env unless you explicitly request it.'
printf '%s\n' '- This script prefers next steps and merge-only suggestions over silent mutation.'
printf '%s\n' "- Pinned stable dependency: voice-mode==${PINNED_STABLE_VERSION}"

if [ "${SELECTED_VERSION}" = "${PINNED_STABLE_VERSION}" ]; then
    note "Using the pinned stable voice-mode track"
else
    warn "Experimental version requested: voice-mode==${SELECTED_VERSION}"
    warn "The stable verifier and patch artifact in this repo target voice-mode==${PINNED_STABLE_VERSION}"
fi

if [ -n "${PATCH_TARGET}" ]; then
    note "CLI patch target override requested: ${PATCH_TARGET}"
fi

if [ "${failures}" -ne 0 ]; then
    exit 1
fi

if [ "${SKIP_SYNC}" -eq 0 ]; then
    run_step "merge-only config suggestions" "${SCRIPT_DIR}/sync_local_config.sh"
else
    note "Skipped merge-only config suggestions"
fi

if [ "${RUN_AUDIO_CHECK}" -eq 1 ]; then
    run_step "audio verifier" "${SCRIPT_DIR}/verify_audio_stack.sh"
else
    note "Audio verifier not run. Suggested next step: ${SCRIPT_DIR}/verify_audio_stack.sh"
fi

if [ "${RUN_VOICE_SMOKE}" -eq 1 ]; then
    if [ "${SELECTED_VERSION}" = "${PINNED_STABLE_VERSION}" ]; then
        run_step "voice-mode smoke test" "${SCRIPT_DIR}/verify_voicemode.sh"
    else
        warn "Skipping scripts/verify_voicemode.sh because it is pinned to voice-mode==${PINNED_STABLE_VERSION}"
        printf 'Manual experimental smoke command:\n'
        printf '  uvx --from voice-mode==%s voice-mode converse --message "Voice check." --no-wait\n' "${SELECTED_VERSION}"
    fi
else
    note "Voice smoke test not run. Suggested next step: ${SCRIPT_DIR}/verify_voicemode.sh"
fi

if [ "${APPLY_CLI_PATCH}" -eq 1 ] || [ "${RUN_PATCH_DRY_RUN}" -eq 1 ]; then
    patch_cmd=("${SCRIPT_DIR}/apply_voicemode_patch.sh")
    if [ -n "${PATCH_TARGET}" ]; then
        patch_cmd+=("--target" "${PATCH_TARGET}")
    fi

    if [ "${SELECTED_VERSION}" != "${PINNED_STABLE_VERSION}" ]; then
        warn "Skipping CLI patch step because the repo patch artifact only targets voice-mode==${PINNED_STABLE_VERSION}"
    elif [ "${APPLY_CLI_PATCH}" -eq 1 ]; then
        patch_cmd+=("--apply")
        run_step "voice-mode CLI patch apply" "${patch_cmd[@]}"
    else
        run_step "voice-mode CLI patch dry-run" "${patch_cmd[@]}"
    fi
else
    note "CLI patch step not run. Suggested next step: ${SCRIPT_DIR}/apply_voicemode_patch.sh"
    if [ -n "${PATCH_TARGET}" ]; then
        note "No CLI patch step ran on this invocation. Re-pass --patch-target PATH together with --dry-run-cli-patch or --apply-cli-patch when you want the installer to use that target."
    else
        note "If multiple installed voice-mode copies exist, rerun the CLI patch step with --patch-target PATH"
    fi
fi

if [ "${OVERWRITE_VOICEMODE_ENV}" -eq 1 ]; then
    printf '\n[voicemode env]\n'
    write_voicemode_env
else
    note "Repo template available at ${REPO_ROOT}/templates/voicemode.env.example"
    note "Manual merge is preferred over replacing ~/.voicemode/voicemode.env"
fi

printf '\nRecommended next steps:\n'
printf '  1. If you want to re-run the merge-only config suggestions, run: bash "%s"\n' "${SCRIPT_DIR}/sync_local_config.sh"
printf '  2. Run: bash "%s"\n' "${SCRIPT_DIR}/verify_audio_stack.sh"
printf '  3. Run: bash "%s" for the pinned stable smoke test.\n' "${SCRIPT_DIR}/verify_voicemode.sh"
printf '  4. Only if you need the standalone continuous CLI path on 8.5.1, run: bash "%s" [--target PATH] --apply\n' "${SCRIPT_DIR}/apply_voicemode_patch.sh"
printf '     Use --patch-target PATH with this installer when multiple installed voice-mode copies exist.\n'

if [ "${failures}" -ne 0 ]; then
    exit 1
fi

exit 0
