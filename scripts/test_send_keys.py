#!/usr/bin/env python3
"""Verification script for harness.send_keys against interactive TUI menus.

Creates a tmux session running a simple Python select menu, then exercises
both named-key and raw-byte modes to confirm keys reach the application.

Usage:
    python scripts/test_send_keys.py

Requires: tmux, python3 (the system Python that runs the inline menu script).
"""

import asyncio
import json
import subprocess
import sys
import textwrap
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
HARNESS_CONFIG_DIR = REPO_ROOT / "apps" / "realtime_voice" / "config"

# Inline Python script that renders a simple interactive menu via raw stdin.
# This simulates how Ink-based TUI apps handle input: raw mode, byte-level
# reads, arrow-key navigation, Enter to select, Ctrl-C to cancel.
MENU_SCRIPT = textwrap.dedent(r'''
import sys, os, tty, termios

options = ["alpha", "beta", "gamma"]
selected = 0

def render():
    # Move cursor up by len(options) lines to overwrite (first render just prints)
    for i, opt in enumerate(options):
        marker = "> " if i == selected else "  "
        print(f"\r{marker}{opt}    ")
    # Move cursor back up
    sys.stdout.write(f"\033[{len(options)}A")
    sys.stdout.flush()

fd = sys.stdin.fileno()
old_settings = termios.tcgetattr(fd)
try:
    tty.setraw(fd)
    render()
    while True:
        ch = os.read(fd, 16)
        if ch == b'\x03':  # Ctrl-C
            # Move below menu before printing
            sys.stdout.write(f"\033[{len(options)}B\r\n")
            sys.stdout.flush()
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
            print("RESULT:cancelled")
            sys.exit(0)
        elif ch == b'\r' or ch == b'\n':  # Enter
            sys.stdout.write(f"\033[{len(options)}B\r\n")
            sys.stdout.flush()
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
            print(f"RESULT:selected:{options[selected]}")
            sys.exit(0)
        elif ch == b'\x1b[A':  # Up arrow
            selected = max(0, selected - 1)
            render()
        elif ch == b'\x1b[B':  # Down arrow
            selected = min(len(options) - 1, selected + 1)
            render()
        elif ch == b'\x01':  # Ctrl-A
            sys.stdout.write(f"\033[{len(options)}B\r\n")
            sys.stdout.flush()
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
            print("RESULT:ctrl-a-received")
            sys.exit(0)
finally:
    termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
''')


TEST_SESSION = "test-send-keys"


def tmux(*args: str) -> str:
    result = subprocess.run(
        ["tmux", *args],
        capture_output=True, text=True, timeout=5,
    )
    return result.stdout


def kill_test_session():
    try:
        subprocess.run(
            ["tmux", "kill-session", "-t", TEST_SESSION],
            capture_output=True, timeout=5,
        )
    except Exception:
        pass


def start_menu_session():
    """Start a tmux session running the inline menu script."""
    kill_test_session()
    # Write the menu script to a temp file
    script_path = Path("/tmp/test_tui_menu.py")
    script_path.write_text(MENU_SCRIPT)
    subprocess.run(
        ["tmux", "new-session", "-d", "-s", TEST_SESSION, "-x", "120", "-y", "40",
         sys.executable, str(script_path)],
        check=True, timeout=5,
    )
    # Keep the pane alive after the script exits so we can capture output
    subprocess.run(
        ["tmux", "set-option", "-t", TEST_SESSION, "remain-on-exit", "on"],
        capture_output=True, timeout=5,
    )
    time.sleep(0.5)  # let menu render


def capture() -> str:
    return tmux("capture-pane", "-p", "-t", f"{TEST_SESSION}:0.0")


def send_keys_named(*keys: str):
    """Send keys using tmux named-key mode (how the harness works by default)."""
    for key in keys:
        tmux("send-keys", "-t", f"{TEST_SESSION}:0.0", key)
        time.sleep(0.06)


def send_keys_raw_hex(*hex_args: str | list[str]):
    """Send keys using tmux -H raw hex mode (how the harness works in raw=True).

    Each argument can be a single hex byte ("0d") or a list of hex bytes
    for multi-byte sequences (["1b", "5b", "42"] for Down arrow).
    """
    for arg in hex_args:
        if isinstance(arg, list):
            # Multi-byte: pass each byte as separate tmux arg
            tmux("send-keys", "-t", f"{TEST_SESSION}:0.0", "-H", *arg)
        else:
            tmux("send-keys", "-t", f"{TEST_SESSION}:0.0", "-H", arg)
        time.sleep(0.06)


class TestResult:
    def __init__(self):
        self.passed = 0
        self.failed = 0

    def check(self, label: str, condition: bool, detail: str = ""):
        if condition:
            self.passed += 1
            print(f"  PASS: {label}")
        else:
            self.failed += 1
            print(f"  FAIL: {label} — {detail}")


def test_named_enter(results: TestResult):
    """Test: named Enter key selects the default (first) item."""
    print("\n[Test 1] Named key: Enter selects default item")
    start_menu_session()
    output_before = capture()
    results.check("Menu rendered", "> alpha" in output_before, f"got: {output_before!r}")

    send_keys_named("Enter")
    time.sleep(0.3)
    output_after = capture()
    results.check(
        "Enter selected 'alpha'",
        "RESULT:selected:alpha" in output_after,
        f"got: {output_after!r}",
    )
    kill_test_session()


def test_named_arrows_and_enter(results: TestResult):
    """Test: Down arrow + Enter selects second item."""
    print("\n[Test 2] Named keys: Down + Enter selects second item")
    start_menu_session()
    send_keys_named("Down")
    time.sleep(0.1)
    send_keys_named("Enter")
    time.sleep(0.3)
    output = capture()
    results.check(
        "Down+Enter selected 'beta'",
        "RESULT:selected:beta" in output,
        f"got: {output!r}",
    )
    kill_test_session()


def test_named_ctrl_c(results: TestResult):
    """Test: Ctrl-C cancels."""
    print("\n[Test 3] Named key: C-c cancels")
    start_menu_session()
    send_keys_named("C-c")
    time.sleep(0.3)
    output = capture()
    results.check(
        "C-c cancelled",
        "RESULT:cancelled" in output,
        f"got: {output!r}",
    )
    kill_test_session()


def test_named_ctrl_a(results: TestResult):
    """Test: Ctrl-A is received."""
    print("\n[Test 4] Named key: C-a received")
    start_menu_session()
    send_keys_named("C-a")
    time.sleep(0.3)
    output = capture()
    results.check(
        "C-a received",
        "RESULT:ctrl-a-received" in output,
        f"got: {output!r}",
    )
    kill_test_session()


def test_raw_enter(results: TestResult):
    """Test: Raw hex 0d (Enter) selects."""
    print("\n[Test 5] Raw hex: 0d (Enter) selects default item")
    start_menu_session()
    send_keys_raw_hex("0d")
    time.sleep(0.3)
    output = capture()
    results.check(
        "Raw 0d selected 'alpha'",
        "RESULT:selected:alpha" in output,
        f"got: {output!r}",
    )
    kill_test_session()


def test_raw_arrows_and_enter(results: TestResult):
    """Test: Raw hex arrow down + enter."""
    print("\n[Test 6] Raw hex: Down(1b 5b 42) + Down + Enter(0d)")
    start_menu_session()
    send_keys_raw_hex(["1b", "5b", "42"])  # Down
    time.sleep(0.1)
    send_keys_raw_hex(["1b", "5b", "42"])  # Down
    time.sleep(0.1)
    send_keys_raw_hex("0d")                # Enter
    time.sleep(0.3)
    output = capture()
    results.check(
        "Raw arrows+enter selected 'gamma'",
        "RESULT:selected:gamma" in output,
        f"got: {output!r}",
    )
    kill_test_session()


def test_raw_ctrl_c(results: TestResult):
    """Test: Raw hex 03 (Ctrl-C) cancels."""
    print("\n[Test 7] Raw hex: 03 (Ctrl-C) cancels")
    start_menu_session()
    send_keys_raw_hex("03")
    time.sleep(0.3)
    output = capture()
    results.check(
        "Raw 03 cancelled",
        "RESULT:cancelled" in output,
        f"got: {output!r}",
    )
    kill_test_session()


def main():
    # Check tmux is available
    try:
        subprocess.run(["tmux", "-V"], capture_output=True, check=True, timeout=5)
    except (FileNotFoundError, subprocess.CalledProcessError):
        print("ERROR: tmux is required but not found.")
        sys.exit(1)

    print("=== send_keys verification tests ===")
    print("Testing both named-key and raw-hex modes against a TUI menu.")

    results = TestResult()

    try:
        test_named_enter(results)
        test_named_arrows_and_enter(results)
        test_named_ctrl_c(results)
        test_named_ctrl_a(results)
        test_raw_enter(results)
        test_raw_arrows_and_enter(results)
        test_raw_ctrl_c(results)
    finally:
        kill_test_session()
        # Clean up temp script
        Path("/tmp/test_tui_menu.py").unlink(missing_ok=True)

    print(f"\n=== Results: {results.passed} passed, {results.failed} failed ===")
    sys.exit(0 if results.failed == 0 else 1)


if __name__ == "__main__":
    main()
