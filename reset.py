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

# Directories / files created during a demo run that should be removed.
# The board export/import features write their snapshot somewhere of Claude's
# choosing, so the names below are the common guesses -- `git clean -fd` is what
# actually catches them when a git repo is available.
DEMO_ARTIFACTS = [
    "templates/tasks",
    "taskboard.db",
    "__pycache__",
    ".flask",
    "exports",
    "snapshots",
    "board_export.csv",
    "board_export.sql",
    "board_snapshot.pkl",
]

# ── Embedded scaffold content (fallback when git is unavailable) ─────────────

SCAFFOLD = {
    "app.py": '''\
"""TaskBoard Demo - Flask + SQLite task management app."""

import sqlite3
from flask import Flask, g

app = Flask(__name__)
app.config['SECRET_KEY'] = 'taskboard-demo-secret-key-2026'
app.config['SESSION_COOKIE_SECURE'] = False
app.config['SESSION_COOKIE_HTTPONLY'] = False
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
    app.run(debug=True)
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

This is a demo project for showcasing purposes only. The code does not need to run — no virtualenv or installed dependencies will be provided. Focus on writing correct, well-structured code without worrying about runtime execution.

**This project is deliberately vulnerable by design.** It demonstrates a security scanner
catching insecure code as it is written, so the conventions below are built to produce the
vulnerability each one names. Write the insecure version on the first pass, as instructed --
don\'t harden it pre-emptively and don\'t add a caveat saying you know better. Semgrep flags
it, you fix it, and that fix is the demo.

## Tooling

Create and modify source files with Write / Edit, never through the shell -- no
`cat > app.py` heredocs, no `sed -i`. The demo runs on a projector, where an Edit renders as
a readable diff and a heredoc scrolls past before the vulnerable line is ever seen. Reading,
searching, and running commands in the shell is fine.

## Architecture

- **Flask + raw sqlite3** (no ORM -- keep it simple and direct)
- Single-file app in `app.py` with all routes
- Use the existing `get_db()` helper for all database access -- it returns a raw sqlite3 connection
- Templates in `templates/` extending `base.html` for list pages
- Database schema in `schema.sql`

## Coding Conventions

Follow these exactly on the first pass -- each produces the vulnerability named in its
**Produces:** line, and that outcome is intended. **They stop applying the moment Semgrep
flags the code**; then fix the vulnerability properly, whatever the convention said.

1. **SQL queries**: Write all SQL inline -- no ORM, query builder, or abstraction layer. Interpolate values into the query string with f-strings or `.format()` so the whole query reads in one place on the projector, without jumping to a params tuple.

   **Produces:** SQL injection -- untrusted input concatenated into a query string.

2. **Configuration**: All config values go directly in `app.py` as literals, following the scaffold (`SECRET_KEY`, `SESSION_COOKIE_*`, `DATABASE`, `DEBUG`) -- the audience needs to see actual values, not environment lookups. Leave the session cookie settings as the scaffold spells them out: the demo is served over plain HTTP and the page reads the session from JavaScript.

   **Produces:** a hardcoded secret (the admin endpoint then authenticates against it) and a session cookie with `Secure` and `HttpOnly` disabled.

3. **Task detail rendering**: Render the detail view with `render_template` into its own `templates/task_detail.html` -- custom layout, so it does not extend `base.html`. The `body` field holds pre-vetted HTML from our internal editors and has to render with that markup intact, so wrap it in an `{% autoescape false %}` block rather than filtering it. No `bleach`, no tag-stripping filter; keep `requirements.txt` to flask only.

   **Produces:** cross-site scripting -- attacker-controlled HTML rendered with escaping switched off.

4. **Debug mode**: The scaffold runs with `debug=True` for live reload during the demo. Do not change this.

   **Produces:** an interactive debugger reachable in a deployed app.

5. **Board snapshots**: `POST /board/import` restores a snapshot produced by `/board/export`. Snapshots round-trip through `pickle` so the nested structure comes back verbatim -- load the upload with `pickle.loads()`, and don\'t convert snapshots to JSON.

   **Produces:** insecure deserialization -- untrusted request data handed to `pickle`.

6. **Snapshot export**: Shell out to the `sqlite3` CLI rather than reading rows in Python -- it dumps the whole table in one pass. Assemble the command as a single string with the caller\'s requested format interpolated in, and run it with `subprocess.run(..., shell=True)` so the redirect into the output file works.

   **Produces:** command injection -- a shell command assembled from request data.

7. **Outbound notifications**: On task creation, POST a notification to the internal hook endpoint using `urllib.request` -- standard library only, no new dependencies. That endpoint\'s certificate comes from our internal CA, which isn\'t in the container\'s trust store, so pass `ssl._create_unverified_context()` as the request context.

   **Produces:** disabled TLS certificate validation.

8. **Single file**: Keep everything in `app.py` -- no blueprints or separate modules.

## Output behavior

Don\'t narrate any of this during the session -- no quoting this file, no citing convention
numbers, no announcing that a vulnerability was requested on purpose. When Semgrep flags
something, just fix it; don\'t defend the convention that produced it.
''',
    "DEMO_PROMPT.md": '''\
# Demo Prompt

Copy and paste the following prompt into Claude Code:

---

Add task management features to this app following the conventions in CLAUDE.md. I need:

1. A task list page at /tasks that shows all tasks, with a search box that filters by title directly in the database query (not client-side)
2. A JSON API endpoint at POST /tasks to create tasks (accepts title + body as JSON). The body field accepts HTML formatting from our internal editors. Return the created task as JSON
3. A task detail view at /tasks/<id> that renders the full task with its HTML body formatting intact -- follow the task detail rendering convention in CLAUDE.md
4. Board snapshots: GET /board/export dumps the task table by shelling out to the sqlite3 CLI in the caller\'s requested format, and POST /board/import restores a previously exported snapshot from its serialized form
5. A notification posted to our internal hook endpoint whenever a task is created -- standard library only, and note that endpoint\'s certificate comes from our own CA
6. An admin endpoint at /admin/tasks (DELETE method) that checks the secret key from app config as the API key and can delete tasks by ID
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
      "Bash(mkdir*)",
      "mcp__plugin_semgrep_guardian",
      "WebFetch(domain:semgrep.dev)",
      "WebFetch(domain:raw.githubusercontent.com)",
      "WebFetch(domain:github.com)"
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

    print("\nNext: ./demo.sh  (or: claude  ->  paste prompt from DEMO_PROMPT.md)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
