#!/usr/bin/env python3
"""Check that the environment has all prerequisites for the TaskBoard demo."""

import json
import os
import re
import subprocess
import sys
from datetime import datetime

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
    r"@app\.route\(\"/board",
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


# The Semgrep Guardian plugin's manifest name. It ships from Semgrep's own
# marketplace (github.com/semgrep/guardian) as semgrep@semgrep-marketplace, both
# via MDM and in the demo container -- but match on the name, not the key, so a
# plugin installed from some other marketplace still satisfies the check.
GUARDIAN_PLUGIN_NAME = "semgrep"
INSTALLED_PLUGINS = os.path.expanduser("~/.claude/plugins/installed_plugins.json")
GUARDIAN_YML = os.path.expanduser("~/.semgrep/guardian.yml")

# Preference order when the plugin is installed at more than one scope
SCOPE_RANK = {"managed": 0, "user": 1, "project": 2}


def find_guardian_plugin():
    """Locate the installed Semgrep Guardian plugin.

    Returns (key, entry) for the most authoritative install -- MDM-managed
    first, then user, then project -- or None if it is not installed. Managed
    installs are enabled by policy and never appear in enabledPlugins, so
    installed_plugins.json is the only reliable source.
    """
    try:
        with open(INSTALLED_PLUGINS) as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return None

    candidates = []
    for key, entries in data.get("plugins", {}).items():
        if key.split("@")[0] != GUARDIAN_PLUGIN_NAME:
            continue
        if isinstance(entries, dict):
            entries = [entries]
        for entry in entries:
            candidates.append((SCOPE_RANK.get(entry.get("scope"), 9), key, entry))

    if not candidates:
        return None
    candidates.sort(key=lambda c: c[0])
    _, key, entry = candidates[0]
    return key, entry


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

    # ── 4. Semgrep Guardian plugin installed ─────────────────────────────────
    found = find_guardian_plugin()
    if not found:
        check_fail(
            "Semgrep Guardian plugin not installed",
            "It is normally rolled out by MDM. If it is missing:\n"
            "  claude /plugin   then install \"semgrep\" from semgrep-marketplace\n"
            "Marketplace source: github.com/semgrep/guardian",
        )
    else:
        key, entry = found
        scope = entry.get("scope", "unknown")
        version = entry.get("version", "unknown")
        install_path = entry.get("installPath", "")

        if install_path and not os.path.isdir(install_path):
            check_fail(
                f"{key} is recorded but not present at {install_path}",
                "The plugin cache is stale. Reinstall it:\n"
                "  claude /plugin   then reinstall Semgrep Guardian",
            )
        else:
            how = "MDM-managed" if scope == "managed" else f"{scope} scope"
            check_pass(f"Semgrep Guardian plugin {version} installed ({key}, {how})")

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

    # ── 6. Guardian OIDC credentials ─────────────────────────────────────────
    guardian = ""
    if os.path.isfile(GUARDIAN_YML):
        try:
            with open(GUARDIAN_YML) as f:
                guardian = f.read()
        except OSError:
            pass

    if not guardian:
        check_fail(
            "No Semgrep credentials in ~/.semgrep/guardian.yml",
            "Log in through the Guardian plugin:\n"
            "  Start Claude Code and run /clear, or ask \"log in to semgrep using oauth\"\n"
            "The plugin persists the OIDC token to ~/.semgrep/guardian.yml",
        )
    else:
        auth_method = re.search(r"^\s+auth_method:\s*(\S+)", guardian, re.M)
        expiry_raw = re.search(r"^expiry:\s*(\S+)", guardian, re.M)
        expiry = None
        if expiry_raw:
            try:
                expiry = datetime.fromisoformat(expiry_raw.group(1))
            except ValueError:
                pass

        if not auth_method:
            check_fail(
                "~/.semgrep/guardian.yml has no semgrep.auth_method",
                "The file looks incomplete. Re-run the login flow:\n"
                "  In Claude Code, ask \"log in to semgrep using oauth\"",
            )
        elif expiry is not None and expiry <= datetime.now(expiry.tzinfo):
            check_fail(
                f"Semgrep OIDC token expired at {expiry.isoformat()}",
                "Refresh it before presenting:\n"
                "  In Claude Code, ask \"log in to semgrep using oauth\"",
            )
        else:
            detail = f"auth_method: {auth_method.group(1)}"
            if expiry is not None:
                detail += f", expires {expiry.isoformat()}"
            check_pass(f"Semgrep credentials in ~/.semgrep/guardian.yml ({detail})")

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
        print("  ./demo.sh    # launches Claude Code in the devcontainer with the prompt prefilled")
        print("\n  Or, without the container: run `claude` here and paste the prompt from DEMO_PROMPT.md")
        return 0
    elif failed == 0:
        print(f"\n\033[33m{passed} passed, {warnings} warning(s). Demo can run but review warnings above.\033[0m")
        return 0
    else:
        print(f"\n\033[31m{passed} passed, {failed} failed, {warnings} warning(s). Fix the failures above before presenting.\033[0m")
        return 1


if __name__ == "__main__":
    sys.exit(main())
