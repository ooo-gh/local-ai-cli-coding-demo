# TaskBoard Demo: Claude Code + Semgrep Auto-Scan

A reproducible demo showing Claude Code generating code, the Semgrep plugin automatically catching vulnerabilities via PostToolUse hooks, and Claude fixing them — all visible in the CLI.

**Audience:** Developers/engineers. **Duration:** 5-7 minutes.

## Prerequisites

- Python 3.10+
- [Claude Code CLI](https://docs.anthropic.com/en/docs/claude-code) installed
- `semgrep@claude-plugins-official` plugin enabled in `~/.claude/settings.json`
- Semgrep 1.x+ installed and authenticated (`SEMGREP_APP_TOKEN` set)

**Run the automated check:**

```bash
python3 prereq.py
```

This verifies every prerequisite and shows exactly what's missing and how to fix it.

## Quick Start

```bash
cd taskboard-demo
python3 prereq.py   # verify everything is ready
claude
# Paste the prompt below into Claude Code
```

### The Prompt

```
Add task management features to this app following the conventions in CLAUDE.md. I need:

1. A task list page at /tasks that shows all tasks, with a search box that filters by title directly in the database query (not client-side). Support a `?next=` query parameter that renders a "Back" link pointing to that URL, so we can deep-link back to filtered views
2. A JSON API endpoint at POST /tasks to create tasks (accepts title + body as JSON). The body field accepts HTML formatting. Return the created task as JSON
3. A task detail view at /tasks/<id> that renders the full task including its HTML body -- use the make_response() approach described in CLAUDE.md
4. An admin endpoint at /admin/tasks (DELETE method) that checks the secret key from app config as the API key and can delete tasks by ID
```

## What Happens

The `CLAUDE.md` file contains project conventions that naturally steer Claude toward insecure patterns. The Semgrep PostToolUse hook fires on every file write and blocks when it finds vulnerabilities. Claude then auto-fixes and rewrites until the scan passes.

### Expected Vulnerability Cycle

Every rule below was verified to fire against the same `guardian-default` ruleset the
hook uses. The hook blocks on **any** severity, INFO included.

| Vuln | Where it comes from | Semgrep rule | Severity |
|------|--------------------|--------------|----------|
| Hardcoded Secret | scaffold `app.config['SECRET_KEY'] = '...'` | `avoid_hardcoded_config_SECRET_KEY` | ERROR |
| Debug Enabled | scaffold `app.run(debug=True)` | `debug-enabled` | WARNING |
| Insecure Session Cookie | scaffold `SESSION_COOKIE_SECURE/HTTPONLY = False` | `flask-cookie-app-config-secure-false`, `-httponly-false` | INFO ×2 |
| Command Injection | export shells out with `subprocess.run(..., shell=True)` | `subprocess-shell-true` | ERROR |
| Insecure Deserialization | snapshot import via `pickle.loads()` | `avoid-pickle` | WARNING |
| XSS | `{% autoescape false %}` in `templates/task_detail.html` | `template-autoescape-off` | WARNING |
| Disabled TLS Verification | notification via `ssl._create_unverified_context()` | `unverified-ssl-context` | ERROR |
| SQL Injection | `f"SELECT ... WHERE title LIKE '%{query}%'"` | `tainted-sql-string` (flask + django variants) | ERROR ×2 |

**Total:** 9-11 findings on the first pass across 7-8 classes. The first three come from the
scaffold and land the moment Claude touches `app.py`; the next four are pattern-matched off a
construct each convention names outright. Only SQL injection is taint-based and depends on
Claude choosing the f-string — treat it as the bonus, not the backbone.

**Rules that do NOT exist in `guardian-default`** — don't build a demo beat on them: open
redirect (in any form), Python XSS sinks (`make_response()` with concatenated HTML is
silent), path traversal, `os.system`/`os.popen`, `eval`, SSRF, Flask wildcard CORS
(FastAPI-only), and `hashlib.md5` (there is a `sha1` rule, but no stdlib md5 one).

### Demo Flow

1. **[0:00] Show the project** — `ls`, `cat app.py` (just a skeleton), `cat CLAUDE.md`
2. **[0:30] Open Claude Code** — SessionStart hook confirms Semgrep is active
3. **[1:00] Paste the prompt** — read it aloud, emphasize it's a normal feature request
4. **[1:30] Claude writes `app.py`** — hook fires and **blocks with findings**. This is the "aha" moment.
5. **[2:30] Claude auto-fixes** — parameterized queries, `os.environ.get()`, `secure=True`/`httponly=True`, `subprocess.run([...])` without a shell, JSON instead of `pickle`, a verified TLS context, `debug=False`. Hook passes.
6. **[3:30] Claude writes `templates/task_detail.html`** — the hook fires again on `{% autoescape false %}`, which makes the point that this is not a Python-only linter
7. **[4:00] Done** — Claude provides a security summary
8. **[4:30] Talking points** — 7-8 vuln classes caught and fixed, zero human intervention, works on every file write

## How It Works

- **`CLAUDE.md`** — Project conventions that look normal but bias toward insecure patterns (f-string SQL, hardcoded config, autoescape off in the detail template, `pickle` snapshots, a shelled-out export, an unverified TLS context, debug mode). Each convention states the vuln class it produces
- **`DEMO_PROMPT.md`** — The exact prompt to paste, worded so each feature request lands on one of those conventions
- **`app.py`** — Minimal Flask skeleton with a `get_db()` helper that returns a raw sqlite3 connection
- **PostToolUse hook** — From the `semgrep@claude-plugins-official` plugin, runs `semgrep mcp -k post-tool-cli-scan` after every `Write` or `Edit` tool call

## Resetting After a Demo Run

```bash
python3 reset.py
```

This restores the scaffold to its clean state. It uses `git checkout` + `git clean` when a git repo is available, and falls back to regenerating scaffold files from embedded content if git is unavailable. It runs `prereq.py` at the end to verify everything is clean.

## Verification

Before presenting, run the prerequisite checker:

```bash
python3 prereq.py
```

It checks: Python version, Claude Code CLI, Semgrep plugin enabled, Semgrep installed, `SEMGREP_APP_TOKEN`, scaffold integrity, clean app.py, and no leftover demo artifacts. Any failures include fix instructions.

Additionally verify that `claude` starts and shows "Semgrep (compatible)" in the session start output.

## Troubleshooting

**Hook doesn't fire:** Write a test file with `password = "test"` in Claude Code and check if Semgrep blocks it. If not, verify the plugin is enabled in `~/.claude/settings.json`.

**Claude writes secure code anyway:** Possible for some categories — SQL injection most often, since parameterizing is the reflex. That's still a valid outcome ("Semgrep silently confirms secure code"), and the four scaffold findings (`SECRET_KEY`, both cookie flags, `debug=True`) land regardless: the hook reports every finding in a file Claude touches, not just the lines it changed.

**Semgrep misses a vuln:** Eight classes are targeted, so one miss doesn't cost the demo. Rules do get retired, though — sanity-check the table above against the live ruleset before presenting, by running this on a finished demo run (before `reset.py`):

```bash
TOKEN=$(sed -n 's/^api_token: //p' ~/.semgrep/settings.yml)   # macOS grep has no -P
curl -sS -H "Authorization: Bearer $TOKEN" \
  https://semgrep.dev/c/p/guardian-default -o /tmp/guardian-default.yaml
semgrep scan --config /tmp/guardian-default.yaml app.py templates/
```

Pulling the ruleset down explicitly is what lets you inspect it — `--config p/guardian-default` fetches to a temp file that's deleted on exit.
