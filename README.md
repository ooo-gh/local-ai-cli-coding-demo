# TaskBoard Demo: Claude Code + Semgrep Auto-Scan

A reproducible demo showing Claude Code generating code, the Semgrep plugin automatically catching vulnerabilities via PostToolUse hooks, and Claude fixing them — all visible in the CLI.

**Audience:** Developers/engineers. **Duration:** 5-7 minutes.

## Prerequisites

- Python 3.10+
- [Claude Code CLI](https://docs.anthropic.com/en/docs/claude-code) installed
- Semgrep Guardian plugin installed (MDM rolls it out as `semgrep@semgrep-marketplace`; check with `claude /plugin`)
- Semgrep 1.x+ installed and logged in (OIDC credentials in `~/.semgrep/guardian.yml`)

**Run the automated check:**

```bash
python3 prereq.py
```

This verifies every prerequisite and shows exactly what's missing and how to fix it.

## Quick Start

### Option A: devcontainer, one command (recommended for presenting)

```bash
./demo.sh
```

Brings up the devcontainer, runs `prereq.py` inside it, starts Claude Code, and
**pre-fills the prompt from `DEMO_PROMPT.md` into the input box without sending
it** — so you can read it aloud off the projector and hit Enter on cue.

The first run builds the image (a few minutes) and asks you to `claude auth
login` inside the container. That is the only first-run step left —
`post_create.py` pre-answers the rest of Claude Code's onboarding (theme, TUI
style, permission-mode confirmation, and trust for `/workspace`). The login
persists in a named volume, so every later run goes straight to the pre-filled
prompt. **Do the first run before you're in front of an audience.** See
[`.devcontainer/`](.devcontainer/) for what the container ships.

The session starts in **`acceptEdits`**, not auto mode — Claude writes `app.py`
without a prompt on every edit, which keeps the write → Semgrep blocks → Claude
fixes cycle uninterrupted, but still asks before anything other than an edit.

```
./demo.sh --rebuild                  force an image rebuild
./demo.sh --no-prefill               start with an empty prompt box
./demo.sh --permission-mode manual   prompt for every tool call
./demo.sh --reset-login              drop the persisted Claude login
./demo.sh --skip-checks              skip the in-container prereq.py run
```

Quitting Claude leaves you in a container shell for `git diff` and
`python3 reset.py`. `C-b d` detaches without stopping the session.

### Option B: straight on the host

```bash
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

| Vuln | What Claude Writes | Semgrep Rule | Severity |
|------|-------------------|--------------|----------|
| SQL Injection | `f"SELECT ... WHERE title LIKE '%{query}%'"` | `tainted-sql-string` | CRITICAL |
| Hardcoded Secret | `app.config['SECRET_KEY'] = '...'` | `avoid_hardcoded_config_SECRET_KEY` | ERROR |
| XSS | `make_response('<html>...' + task['body'])` | `raw-html-format`, `make-response-with-unknown-content` | WARNING |
| Debug Enabled | `app.run(debug=True)` | `debug-enabled` | WARNING |
| Open Redirect | Unvalidated `?next=` param rendered as link href | `open-redirect` | WARNING |

**Total:** 5-10 findings on first write, across up to 5 vuln classes.

### Demo Flow

1. **[0:00] Show the project** — `ls`, `cat app.py` (just a skeleton), `cat CLAUDE.md`
2. **[0:30] Open Claude Code** — SessionStart hook confirms Semgrep is active
3. **[1:00] Paste the prompt** — read it aloud, emphasize it's a normal feature request
4. **[1:30] Claude writes `app.py`** — hook fires and **blocks with findings**. This is the "aha" moment.
5. **[2:30] Claude auto-fixes** — parameterized queries, `os.environ.get()`, `html.escape()` / `render_template()`, `debug=False`. Hook passes.
6. **[3:30] Claude writes templates** — scans pass silently
7. **[4:00] Done** — Claude provides a security summary
8. **[4:30] Talking points** — up to 5 vuln classes caught and fixed, zero human intervention, works on every file write

## How It Works

- **`CLAUDE.md`** — Project conventions that look normal but bias toward insecure patterns (f-string SQL, hardcoded config, raw HTML responses, debug mode, open redirects)
- **`DEMO_PROMPT.md`** — The exact prompt to paste, worded to trigger all three vuln types
- **`app.py`** — Minimal Flask skeleton with a `get_db()` helper that returns a raw sqlite3 connection
- **PostToolUse hook** — From the Semgrep Guardian plugin, runs `scripts/hook.sh claude PostToolUse` after every `Write`, `Edit`, or `Bash` tool call
- **`demo.sh`** — Launcher: `devcontainer up`, then Claude Code under tmux, then a bracketed paste of the prompt so it lands in the input box unsubmitted
- **`.devcontainer/`** — Image with Claude Code, the Guardian plugin and the Semgrep CLI pre-installed. `~/.semgrep` is bind-mounted for the OIDC token; `~/.claude` is a named volume so the login survives between demos; the repo is bind-mounted at `/workspace`, so what Claude writes shows up in `git diff` on the host

## Resetting After a Demo Run

```bash
python3 reset.py
```

This restores the scaffold to its clean state. It uses `git checkout` + `git clean` when a git repo is available, and falls back to regenerating scaffold files from embedded content if git is unavailable. It runs `prereq.py` at the end to verify everything is clean.

> **Commit `demo.sh` and `.devcontainer/` before you reset.** `reset.py` runs
> `git clean -fd`, which deletes untracked files — including these — and they are
> not part of the embedded scaffold that the no-git fallback regenerates.

## Verification

Before presenting, run the prerequisite checker:

```bash
python3 prereq.py
```

It checks: Python version, Claude Code CLI, Semgrep plugin enabled, Semgrep installed, OIDC credentials in `~/.semgrep/guardian.yml`, scaffold integrity, clean app.py, and no leftover demo artifacts. Any failures include fix instructions.

Additionally verify that `claude` starts and shows "Semgrep (compatible)" in the session start output.

## Troubleshooting

**Hook doesn't fire:** Write a test file with `password = "test"` in Claude Code and check if Semgrep blocks it. If not, verify the plugin is enabled in `~/.claude/settings.json`.

**Claude writes secure code anyway:** The `CLAUDE.md` conventions are designed to steer toward insecure patterns, but Claude may still write secure code for some categories (especially SQL injection). This is actually a valid demo outcome ("Semgrep silently confirms secure code"). The hardcoded secret and debug mode are nearly guaranteed since they're in the scaffold already.

**Semgrep misses a vuln:** Multiple vuln classes are targeted so even if one is missed, the others still demonstrate the concept.
