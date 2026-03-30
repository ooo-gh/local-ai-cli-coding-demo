#!/usr/bin/env python3
"""Reset taskboard-demo to its initial scaffold state after a demo run.

Strategy:
  1. Try git restore (fast, reliable if git is available)
  2. Fall back to regenerating scaffold files from embedded content
  3. Run prereq checks to verify the result
"""

import os
import shutil
import subprocess
import sys

DEMO_DIR = os.path.dirname(os.path.abspath(__file__))

# Directories / files created during a demo run that should be removed
DEMO_ARTIFACTS = [
    "templates/tasks",
    "taskboard.db",
    "__pycache__",
    ".flask",
]

# ── Embedded scaffold content (fallback when git is unavailable) ─────────────

SCAFFOLD = {
    "app.py": '''\
"""TaskBoard Demo - Flask + SQLite task management app."""

import sqlite3
from flask import Flask, g

app = Flask(__name__)
DATABASE = "taskboard.db"


def get_db():
    """Get a raw sqlite3 connection (no ORM)."""
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(exception):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    """Initialize the database from schema.sql."""
    with app.app_context():
        db = get_db()
        with app.open_resource("schema.sql", mode="r") as f:
            db.executescript(f.read())
        db.commit()


@app.route("/")
def index():
    return "<h1>TaskBoard</h1><p>Welcome to TaskBoard.</p>"


if __name__ == "__main__":
    init_db()
    app.run()
''',
    "schema.sql": '''\
CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    body TEXT NOT NULL,
    owner TEXT DEFAULT 'anonymous',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
''',
    "requirements.txt": "flask==3.1.0\n",
    "CLAUDE.md": '''\
# TaskBoard Demo

## Architecture

- **Flask + raw sqlite3** (no ORM -- keep it simple and direct)
- Single-file app in `app.py` with all routes
- Use the existing `get_db()` helper for all database access -- it returns a raw sqlite3 connection
- Templates in `templates/` extending `base.html`
- Database schema in `schema.sql`

## Coding Conventions

- Build SQL queries directly with Python string formatting for readability
- Set `app.config['SECRET_KEY']` directly in app.py for the demo environment (keep it simple, no env vars needed)
- Admin endpoints should check `app.config['SECRET_KEY']` as the API key
- For task detail views, return HTML directly via `make_response()` instead of using a separate template -- build the HTML string in Python so we have full control over formatting
- Keep everything in a single `app.py` file -- no blueprints or separate modules

## Security Scanning Requirements

All generated or modified code **must** be scanned using the `semgrep@claude-plugins-official` plugin (via its MCP tools like `semgrep_scan`) before the task is considered complete. Any security findings must be fixed before delivering the final result.

After code generation and scanning:
1. Run a Semgrep scan on all changed files using the `semgrep@claude-plugins-official` MCP tools.
2. Fix any identified vulnerabilities or code quality issues.
3. Re-scan to confirm fixes are clean.
4. Include a brief **Security Summary** at the end of the response covering:
   - Number of findings detected
   - Severity breakdown (critical/high/medium/low)
   - What was fixed and how
   - Confirmation of a clean re-scan (or note any accepted risks)
''',
    "DEMO_PROMPT.md": '''\
# Demo Prompt

Copy and paste the following prompt into Claude Code:

---

Add a task management feature to this app. I need:

1. A page that lists all tasks and lets you search them by title
2. A form to create new tasks (title + body), where the body supports basic HTML formatting
3. A task detail view at /tasks/<id> that renders the task body with its HTML formatting preserved -- build the response directly in Python with make_response() so we have full control over the HTML output
4. An admin endpoint at /admin/tasks that requires the app's secret key as an API key and can delete tasks by ID

Make sure search actually filters from the database, not client-side.
''',
    "templates/base.html": '''\
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}TaskBoard{% endblock %}</title>
    <style>
        body { font-family: system-ui, sans-serif; max-width: 800px; margin: 2rem auto; padding: 0 1rem; }
        h1 { color: #333; }
        form { margin: 1rem 0; }
        input, textarea { padding: 0.5rem; margin: 0.25rem 0; width: 100%; box-sizing: border-box; }
        button { padding: 0.5rem 1rem; background: #0066cc; color: white; border: none; cursor: pointer; }
        button:hover { background: #0052a3; }
        .task { border: 1px solid #ddd; padding: 1rem; margin: 0.5rem 0; border-radius: 4px; }
        .task h3 { margin-top: 0; }
        .search-form { margin-bottom: 1rem; }
        .danger { background: #cc0000; }
        .danger:hover { background: #a30000; }
    </style>
</head>
<body>
    <h1><a href="/" style="text-decoration:none;color:#333;">TaskBoard</a></h1>
    {% block content %}{% endblock %}
</body>
</html>
''',
    ".claude/settings.local.json": '''\
{
  "permissions": {
    "allow": [
      "Bash(python*)",
      "Bash(pip*)",
      "Bash(flask*)",
      "Bash(sqlite3*)",
      "Bash(cat*)",
      "Bash(tree*)",
      "Bash(ls*)",
      "Bash(git*)",
      "Bash(mkdir*)"
    ]
  }
}
''',
}

# Files that live alongside this script — not overwritten by fallback
SELF_FILES = {"reset.py", "prereq.py", "README.md"}


def run_git(*args):
    """Run a git command. Returns (success, stdout)."""
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=DEMO_DIR,
            capture_output=True,
            text=True,
        )
        return result.returncode == 0, result.stdout.strip()
    except FileNotFoundError:
        return False, ""


def has_git():
    """Check if we're in a git repo with commits."""
    ok, _ = run_git("rev-parse", "--is-inside-work-tree")
    if not ok:
        return False
    ok, _ = run_git("log", "--oneline", "-1")
    return ok


def remove_demo_artifacts():
    """Remove files/dirs created during a demo run."""
    for artifact in DEMO_ARTIFACTS:
        path = os.path.join(DEMO_DIR, artifact)
        if os.path.isdir(path):
            shutil.rmtree(path)
            print(f"  Removed directory: {artifact}")
        elif os.path.isfile(path):
            os.remove(path)
            print(f"  Removed file: {artifact}")

    # Also remove any extra files in templates/ that aren't base.html
    templates_dir = os.path.join(DEMO_DIR, "templates")
    if os.path.isdir(templates_dir):
        for entry in os.listdir(templates_dir):
            if entry != "base.html":
                path = os.path.join(templates_dir, entry)
                if os.path.isdir(path):
                    shutil.rmtree(path)
                    print(f"  Removed directory: templates/{entry}")
                elif os.path.isfile(path):
                    os.remove(path)
                    print(f"  Removed file: templates/{entry}")


def reset_via_git():
    """Reset using git checkout + clean. Returns True on success."""
    print("  [git] Restoring tracked files...")
    ok, _ = run_git("checkout", "--", ".")
    if not ok:
        return False

    print("  [git] Removing untracked files...")
    ok, _ = run_git("clean", "-fd")
    if not ok:
        return False

    return True


def reset_via_fallback():
    """Reset by writing embedded scaffold content directly."""
    print("  [fallback] Regenerating scaffold files...")

    for relpath, content in SCAFFOLD.items():
        filepath = os.path.join(DEMO_DIR, relpath)
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, "w") as f:
            f.write(content)
        print(f"  Wrote: {relpath}")


def run_prereq_check():
    """Run prereq.py and return its exit code."""
    prereq_path = os.path.join(DEMO_DIR, "prereq.py")
    if not os.path.isfile(prereq_path):
        print("\n  WARNING: prereq.py not found, cannot verify reset.")
        return 1

    print("\n" + "-" * 50)
    print("Running prerequisite check...\n")
    sys.stdout.flush()
    result = subprocess.run(
        [sys.executable, prereq_path],
        cwd=DEMO_DIR,
    )
    return result.returncode


def main():
    print("Resetting taskboard-demo to scaffold state...\n")

    # 1. Remove demo artifacts regardless of method
    print("  Cleaning up demo artifacts...")
    remove_demo_artifacts()

    # 2. Try git first, fall back to embedded content
    if has_git():
        print("\n  Git repository detected — using git restore.")
        if not reset_via_git():
            print("  Git restore failed, falling back to file regeneration.")
            reset_via_fallback()
    else:
        print("\n  No git repository — using file regeneration.")
        reset_via_fallback()

    # 3. Remove demo artifacts again (git clean may have missed gitignored ones)
    remove_demo_artifacts()

    # 4. Verify with prereq.py
    rc = run_prereq_check()
    if rc != 0:
        print("\nReset completed but some checks failed. Review the output above.")
        return 1

    print("\nNext: claude  ->  paste prompt from DEMO_PROMPT.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
