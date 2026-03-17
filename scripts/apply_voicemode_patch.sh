#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
PATCH_FILE="${REPO_ROOT}/patches/voice-mode/8.5.1/cli-empty-tts.patch"
EXPECTED_VERSION="8.5.1"

MODE="dry-run"
TARGET_PATH=""
FORCE=0

usage() {
    cat <<'EOF'
Usage: scripts/apply_voicemode_patch.sh [--apply] [--target PATH] [--force]

Locates one installed voice_mode/cli.py, confirms the 8.5.1 version assumption as
best as possible, performs a patch dry-run first, and only applies the patch when
--apply is explicitly requested.

This script refuses to silently patch multiple installs.
EOF
}

note() {
    printf '[info] %s\n' "$1"
}

warn() {
    printf '[warn] %s\n' "$1"
}

die() {
    printf '[fail] %s\n' "$1" >&2
    exit 1
}

while [ $# -gt 0 ]; do
    case "$1" in
        --apply)
            MODE="apply"
            ;;
        --target)
            shift
            if [ $# -eq 0 ]; then
                die "Missing value after --target"
            fi
            TARGET_PATH="$1"
            ;;
        --force)
            FORCE=1
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            usage
            die "Unknown argument: $1"
            ;;
    esac
    shift
done

if ! command -v patch >/dev/null 2>&1; then
    die "The patch command is required"
fi

if ! command -v python3 >/dev/null 2>&1; then
    die "python3 is required to locate installed voice-mode files"
fi

if [ ! -f "${PATCH_FILE}" ]; then
    die "Patch artifact not found: ${PATCH_FILE}"
fi

mapfile -t candidates < <(
    python3 - "${TARGET_PATH}" "${HOME}" <<'PY'
import pathlib
import sys

target = sys.argv[1]
home = pathlib.Path(sys.argv[2]).expanduser()


def read_version(site_packages: pathlib.Path) -> str:
    for metadata in sorted(site_packages.glob("*.dist-info/METADATA")):
        try:
            text = metadata.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError:
            continue
        name = None
        version = None
        for line in text:
            if line.startswith("Name: "):
                name = line[6:].strip().lower()
            elif line.startswith("Version: "):
                version = line[9:].strip()
            if name is not None and version is not None:
                break
        if name in {"voice-mode", "voice_mode"} and version:
            return version
    return ""


def emit(cli_path: pathlib.Path) -> None:
    cli_path = cli_path.resolve()
    site_packages = cli_path.parent.parent
    version = read_version(site_packages)
    print(f"{cli_path}\t{site_packages}\t{version}")


def emit_target(path_text: str) -> int:
    candidate = pathlib.Path(path_text).expanduser()
    if candidate.is_dir():
        if (candidate / "voice_mode" / "cli.py").is_file():
            emit(candidate / "voice_mode" / "cli.py")
            return 0
        if candidate.name == "voice_mode" and (candidate / "cli.py").is_file():
            emit(candidate / "cli.py")
            return 0
        return 2
    if candidate.is_file():
        emit(candidate)
        return 0
    return 2


if target:
    sys.exit(emit_target(target))

seen = set()
roots = [
    home / ".cache" / "uv",
    home / ".local" / "share" / "uv",
    home / ".local" / "lib",
]

for root in roots:
    if not root.exists():
        continue
    for cli_path in root.rglob("voice_mode/cli.py"):
        resolved = cli_path.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        emit(resolved)
PY
) || die "Could not inspect installed voice-mode locations"

candidate_count="${#candidates[@]}"

if [ "${candidate_count}" -eq 0 ]; then
    die "No installed voice_mode/cli.py files were found. Run the stable uvx command once or pass --target."
fi

if [ "${candidate_count}" -gt 1 ] && [ -z "${TARGET_PATH}" ]; then
    warn "Multiple voice_mode/cli.py files were found. Refusing to choose one automatically."
    for candidate in "${candidates[@]}"; do
        IFS=$'\t' read -r cli_path site_packages version <<<"${candidate}"
        if [ -n "${version}" ]; then
            printf '  - %s (site-packages: %s, version: %s)\n' "${cli_path}" "${site_packages}" "${version}"
        else
            printf '  - %s (site-packages: %s, version: unknown)\n' "${cli_path}" "${site_packages}"
        fi
    done
    die "Pass --target with the specific install you want to inspect"
fi

IFS=$'\t' read -r CLI_PATH SITE_PACKAGES_DIR DETECTED_VERSION <<<"${candidates[0]}"

if [ ! -f "${CLI_PATH}" ]; then
    die "Resolved cli.py does not exist: ${CLI_PATH}"
fi

if [ ! -d "${SITE_PACKAGES_DIR}" ]; then
    die "Resolved site-packages directory does not exist: ${SITE_PACKAGES_DIR}"
fi

note "Resolved target: ${CLI_PATH}"
note "Resolved site-packages root: ${SITE_PACKAGES_DIR}"
note "Patch artifact: ${PATCH_FILE}"
note "Mode: ${MODE}"

if [ -n "${DETECTED_VERSION}" ]; then
    note "Detected installed version: ${DETECTED_VERSION}"
    if [ "${DETECTED_VERSION}" != "${EXPECTED_VERSION}" ] && [ "${FORCE}" -ne 1 ]; then
        die "Detected version ${DETECTED_VERSION} does not match expected ${EXPECTED_VERSION}. Re-run with --force only if you have verified the target."
    fi
else
    warn "Could not confirm the installed voice-mode version from METADATA"
    if [ "${FORCE}" -ne 1 ]; then
        die "Refusing to patch an install with unknown version. Re-run with --force only after manual review."
    fi
fi

if patch --dry-run -R -p1 -d "${SITE_PACKAGES_DIR}" < "${PATCH_FILE}" >/dev/null 2>&1; then
    note "Patch already appears to be applied at ${CLI_PATH}"
    exit 0
fi

if patch --dry-run -p1 -d "${SITE_PACKAGES_DIR}" < "${PATCH_FILE}" >/dev/null 2>&1; then
    note "Patch dry-run succeeded"
else
    die "Patch dry-run failed. Refusing to touch the install."
fi

if [ "${MODE}" != "apply" ]; then
    note "Dry-run only. Re-run with --apply to patch this single confirmed install."
    exit 0
fi

patch -p1 -d "${SITE_PACKAGES_DIR}" < "${PATCH_FILE}"
note "Patch applied successfully"
