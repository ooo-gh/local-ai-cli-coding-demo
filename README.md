# TaskBoard Demo: Claude Code + Semgrep Auto-Scan

A reproducible demo showing Claude Code generating code, the Semgrep plugin automatically catching vulnerabilities via PostToolUse hooks, and Claude fixing them — all visible in the CLI.

**Audience:** Developers/engineers. **Duration:** 5-7 minutes.

## Prerequisites

- [Claude Code CLI](https://docs.anthropic.com/en/docs/claude-code) installed
- `semgrep@claude-plugins-official` plugin enabled in `~/.claude/settings.json`
- Semgrep installed and authenticated (`semgrep --version`, `SEMGREP_APP_TOKEN` set)
- Python 3.10+

## Quick Start

```bash
cd taskboard-demo
claude
# Paste the prompt below into Claude Code
```

### The Prompt

```
Add a task management feature to this app. I need:

1. A page that lists all tasks and lets you search them by title
2. A form to create new tasks (title + body), where the body supports basic HTML formatting
3. A task detail view at /tasks/<id> that renders the task body with its HTML formatting preserved -- build the response directly in Python with make_response() so we have full control over the HTML output
4. An admin endpoint at /admin/tasks that requires the app's secret key as an API key and can delete tasks by ID

Make sure search actually filters from the database, not client-side.
```

## What Happens

The `CLAUDE.md` file contains project conventions that naturally steer Claude toward three insecure patterns. The Semgrep PostToolUse hook fires on every file write and blocks when it finds vulnerabilities. Claude then auto-fixes and rewrites until the scan passes.

### Expected Vulnerability Cycle

| Vuln | What Claude Writes | Semgrep Rule | Severity |
|------|-------------------|--------------|----------|
| SQL Injection (3 locations) | `"SELECT ... %s" % query` | `generic-sql-flask` + others | CRITICAL |
| Hardcoded Secret | `app.config['SECRET_KEY'] = "..."` | `avoid_hardcoded_config_SECRET_KEY` | ERROR |
| XSS | `make_response("<html>..." % user_data)` | `raw-html-format`, `make-response-with-unknown-content` | WARNING |

**Total:** ~21 findings on first write, across all 3 vuln classes.

### Demo Flow

1. **[0:00] Show the project** — `ls`, `cat app.py` (just a skeleton), `cat CLAUDE.md`
2. **[0:30] Open Claude Code** — SessionStart hook confirms Semgrep is active
3. **[1:00] Paste the prompt** — read it aloud, emphasize it's a normal feature request
4. **[1:30] Claude writes `app.py`** — hook fires and **blocks with findings**. This is the "aha" moment.
5. **[2:30] Claude auto-fixes** — parameterized queries, `os.environ.get()`, `render_template()`. Hook passes.
6. **[3:30] Claude writes templates** — scans pass silently
7. **[4:00] Done** — Claude provides a security summary
8. **[4:30] Talking points** — 3 vuln classes caught and fixed, zero human intervention, works on every file write

## How It Works

- **`CLAUDE.md`** — Project conventions that look normal but bias toward insecure patterns (string-formatted SQL, hardcoded config, raw HTML responses)
- **`DEMO_PROMPT.md`** — The exact prompt to paste, worded to trigger all three vuln types
- **`app.py`** — Minimal Flask skeleton with a `get_db()` helper that returns a raw sqlite3 connection
- **PostToolUse hook** — From the `semgrep@claude-plugins-official` plugin, runs `semgrep mcp -k post-tool-cli-scan` after every `Write` or `Edit` tool call

## Recreating From Scratch

To set up a fresh copy (e.g., after running the demo):

```bash
# From the parent directory
./setup-demo.sh my-fresh-demo
cd my-fresh-demo
claude
```

Or reset the current repo:

```bash
python3 reset.py
```

## Verification Checklist

Before presenting:

- [ ] `semgrep --version` works and shows 1.x+
- [ ] `echo $SEMGREP_APP_TOKEN` is set
- [ ] `claude` starts and shows "Semgrep (compatible)" in session start
- [ ] `app.py` is the clean skeleton (no feature routes)
- [ ] No `templates/tasks/` directory exists yet

## Troubleshooting

**Hook doesn't fire:** Write a test file with `password = "test"` in Claude Code and check if Semgrep blocks it. If not, verify the plugin is enabled in `~/.claude/settings.json`.

**Claude writes secure code anyway:** The `CLAUDE.md` conventions are designed to steer toward insecure patterns, but Claude may still write secure code. This is actually a valid demo outcome ("Semgrep silently confirms secure code"). If needed, make the CLAUDE.md conventions more directive.

**Semgrep misses a vuln:** SQL injection rules are very mature and reliably fire. If one vuln type is missed, the others still demonstrate the concept.
