#!/usr/bin/env python3
"""Reset taskboard-demo to its initial scaffold state after a demo run."""

import os
import shutil
import subprocess
import sys

DEMO_DIR = os.path.dirname(os.path.abspath(__file__))

# Files that should exist in the clean scaffold
SCAFFOLD_FILES = {
    "app.py",
    "schema.sql",
    "requirements.txt",
    "CLAUDE.md",
    "DEMO_PROMPT.md",
    "README.md",
    "setup-demo.sh",
    "reset.py",
    "templates/base.html",
    ".claude/settings.local.json",
}

# Directories created during a demo run that should be removed
DEMO_ARTIFACTS = [
    "templates/tasks",
    "taskboard.db",
    "__pycache__",
    ".flask",
]


def run_git(*args):
    result = subprocess.run(
        ["git", *args],
        cwd=DEMO_DIR,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"  git {' '.join(args)} failed: {result.stderr.strip()}")
        sys.exit(1)
    return result.stdout.strip()


def main():
    print("Resetting taskboard-demo to scaffold state...\n")

    # 1. Restore all tracked files to their committed state
    print("  Restoring tracked files from git...")
    run_git("checkout", "--", ".")

    # 2. Remove untracked files and directories (demo artifacts)
    print("  Removing untracked files...")
    run_git("clean", "-fd")

    # 3. Remove known demo artifacts that might be gitignored
    for artifact in DEMO_ARTIFACTS:
        path = os.path.join(DEMO_DIR, artifact)
        if os.path.isdir(path):
            shutil.rmtree(path)
            print(f"  Removed directory: {artifact}")
        elif os.path.isfile(path):
            os.remove(path)
            print(f"  Removed file: {artifact}")

    # 4. Verify scaffold is intact
    print("\n  Verifying scaffold...")
    missing = []
    for f in SCAFFOLD_FILES:
        if not os.path.exists(os.path.join(DEMO_DIR, f)):
            missing.append(f)

    if missing:
        print(f"\n  WARNING: Missing scaffold files: {', '.join(missing)}")
        sys.exit(1)

    # 5. Confirm clean git status
    status = run_git("status", "--porcelain")
    if status:
        print(f"\n  WARNING: Unexpected changes remain:\n{status}")
        sys.exit(1)

    print("\n  Done. Demo is ready to run again.")
    print("  Next: claude  →  paste prompt from DEMO_PROMPT.md")


if __name__ == "__main__":
    main()
