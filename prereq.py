#!/usr/bin/env python3
"""Check that the environment has all prerequisites for the TaskBoard demo."""

import json
import os
import re
import subprocess
import sys

DEMO_DIR = os.path.dirname(os.path.abspath(__file__))

# Files that must exist in the clean scaffold
SCAFFOLD_FILES = [
    "app.py",
    "schema.sql",
    "requirements.txt",
    "CLAUDE.md",
    "DEMO_PROMPT.md",
    "README.md",
    "reset.py",
    "prereq.py",
    "templates/base.html",
    ".claude/settings.local.json",
]

# Patterns that indicate app.py has been modified from the scaffold
DEMO_ROUTE_PATTERNS = [
    r"@app\.route\(\"/tasks",
    r"@app\.route\(\"/admin",
]

passed = 0
failed = 0
warnings = 0


def check_pass(name):
    global passed
    passed += 1
    print(f"  \033[32m✓\033[0m {name}")


def check_fail(name, fix):
    global failed
    failed += 1
    print(f"  \033[31m✗\033[0m {name}")
    for line in fix.strip().split("\n"):
        print(f"    \u2192 {line}")
    print()


def check_warn(name, note):
    global warnings
    warnings += 1
    print(f"  \033[33m!\033[0m {name}")
    for line in note.strip().split("\n"):
        print(f"    \u2192 {line}")
    print()


def run_cmd(cmd):
    """Run a command and return (returncode, stdout, stderr)."""
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=15
        )
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except FileNotFoundError:
        return -1, "", "command not found"
    except subprocess.TimeoutExpired:
        return -1, "", "command timed out"


def main():
    print("\nTaskBoard Demo \u2014 Prerequisite Check\n")
    print("=" * 50)

    # ── 1. Python version ────────────────────────────────────────────────────
    print("\n[Runtime]\n")

    v = sys.version_info
    if v >= (3, 10):
        check_pass(f"Python {v.major}.{v.minor}.{v.micro}")
    else:
        check_fail(
            f"Python {v.major}.{v.minor}.{v.micro} (need 3.10+)",
            "Install Python 3.10 or newer:\n"
            "  brew install python@3.12   # macOS\n"
            "  sudo apt install python3.12 # Ubuntu/Debian",
        )

    # ── 2. Claude Code CLI ───────────────────────────────────────────────────
    print("\n[Claude Code]\n")

    rc, out, err = run_cmd(["claude", "--version"])
    if rc == 0 and out:
        check_pass(f"Claude Code CLI ({out.splitlines()[0]})")
    else:
        check_fail(
            "Claude Code CLI not found",
            "Install Claude Code:\n"
            "  npm install -g @anthropic-ai/claude-code\n"
            "See: https://docs.anthropic.com/en/docs/claude-code",
        )

    # ── 4. Semgrep plugin enabled ────────────────────────────────────────────
    settings_path = os.path.expanduser("~/.claude/settings.json")
    plugin_enabled = False
    if os.path.isfile(settings_path):
        try:
            with open(settings_path) as f:
                settings = json.load(f)
            plugins = settings.get("enabledPlugins", {})
            plugin_enabled = plugins.get("semgrep@claude-plugins-official", False)
        except (json.JSONDecodeError, OSError):
            pass

    if plugin_enabled:
        check_pass("semgrep@claude-plugins-official plugin enabled")
    else:
        check_fail(
            "semgrep@claude-plugins-official plugin not enabled",
            "Enable the plugin in ~/.claude/settings.json:\n"
            '  Add "semgrep@claude-plugins-official": true to "enabledPlugins"\n'
            "Or run: claude /plugins  and enable it interactively",
        )

    # ── 5. Semgrep installed ─────────────────────────────────────────────────
    print("\n[Semgrep]\n")

    rc, out, err = run_cmd(["semgrep", "--version"])
    if rc == 0 and out:
        version_str = out.strip().splitlines()[0]
        match = re.match(r"(\d+)\.", version_str)
        major = int(match.group(1)) if match else 0
        if major >= 1:
            check_pass(f"Semgrep {version_str}")
        else:
            check_fail(
                f"Semgrep {version_str} (need 1.x+)",
                "Upgrade Semgrep:\n"
                "  pip install --upgrade semgrep\n"
                "  # or: brew upgrade semgrep",
            )
    else:
        check_fail(
            "Semgrep not installed",
            "Install Semgrep:\n"
            "  pip install semgrep\n"
            "  # or: brew install semgrep\n"
            "See: https://semgrep.dev/docs/getting-started/",
        )

    # ── 6. SEMGREP_APP_TOKEN ─────────────────────────────────────────────────
    token = os.environ.get("SEMGREP_APP_TOKEN", "")
    token_in_settings = False
    if token:
        check_pass("SEMGREP_APP_TOKEN is set")
    else:
        if os.path.isfile(settings_path):
            try:
                with open(settings_path) as f:
                    settings = json.load(f)
                env = settings.get("env", {})
                token_in_settings = bool(env.get("SEMGREP_APP_TOKEN", ""))
            except (json.JSONDecodeError, OSError):
                pass

        if token_in_settings:
            check_pass("SEMGREP_APP_TOKEN set in ~/.claude/settings.json (available to Claude Code)")
        else:
            check_fail(
                "SEMGREP_APP_TOKEN not set",
                "Get a token from https://semgrep.dev/orgs/-/settings/tokens\n"
                "Then either:\n"
                "  export SEMGREP_APP_TOKEN=<your-token>  # shell\n"
                '  Or add to ~/.claude/settings.json under "env"',
            )

    # ── 7. Scaffold state ────────────────────────────────────────────────────
    print("\n[Demo Scaffold]\n")

    missing = []
    for f in SCAFFOLD_FILES:
        if not os.path.isfile(os.path.join(DEMO_DIR, f)):
            missing.append(f)

    if missing:
        check_fail(
            f"Missing scaffold files: {', '.join(missing)}",
            "Restore the scaffold:\n"
            "  python3 reset.py",
        )
    else:
        check_pass(f"All {len(SCAFFOLD_FILES)} scaffold files present")

    # ── 8. app.py is clean (not already modified from a demo run) ────────────
    app_path = os.path.join(DEMO_DIR, "app.py")
    if os.path.isfile(app_path):
        with open(app_path) as f:
            app_content = f.read()

        modified = False
        for pattern in DEMO_ROUTE_PATTERNS:
            if re.search(pattern, app_content):
                modified = True
                break

        if modified:
            check_fail(
                "app.py has demo routes (not clean scaffold)",
                "Reset to scaffold state before presenting:\n"
                "  python3 reset.py",
            )
        else:
            check_pass("app.py is clean scaffold (no demo routes)")

    # ── 9. No leftover demo artifacts ────────────────────────────────────────
    artifacts_found = []
    for artifact in ["templates/tasks", "taskboard.db"]:
        if os.path.exists(os.path.join(DEMO_DIR, artifact)):
            artifacts_found.append(artifact)

    if artifacts_found:
        check_fail(
            f"Leftover demo artifacts: {', '.join(artifacts_found)}",
            "Reset to scaffold state before presenting:\n"
            "  python3 reset.py",
        )
    else:
        check_pass("No leftover demo artifacts")

    # ── Summary ──────────────────────────────────────────────────────────────
    print("\n" + "=" * 50)
    total = passed + failed + warnings
    if failed == 0 and warnings == 0:
        print(f"\n\033[32mAll {total} checks passed. Demo is ready!\033[0m")
        print("\nNext steps:")
        print(f"  cd {DEMO_DIR}")
        print("  claude")
        print("  # Paste the prompt from DEMO_PROMPT.md")
        return 0
    elif failed == 0:
        print(f"\n\033[33m{passed} passed, {warnings} warning(s). Demo can run but review warnings above.\033[0m")
        return 0
    else:
        print(f"\n\033[31m{passed} passed, {failed} failed, {warnings} warning(s). Fix the failures above before presenting.\033[0m")
        return 1


if __name__ == "__main__":
    sys.exit(main())
