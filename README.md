# TaskBoard Demo: Claude Code + Semgrep Auto-Scan

A reproducible demo showing Claude Code generating code, the Semgrep plugin automatically catching vulnerabilities via PostToolUse hooks, and Claude fixing them — all visible in the CLI.

**Audience:** Developers/engineers. **Duration:** 5-7 minutes.

## Prerequisites

- Python 3.10+
- [Claude Code CLI](https://docs.anthropic.com/en/docs/claude-code) installed
- Semgrep Guardian plugin installed from Semgrep's marketplace, [github.com/semgrep/guardian](https://github.com/semgrep/guardian)
  — MDM rolls it out as `semgrep@semgrep-marketplace`; check with `claude /plugin`, or add it by hand with
  `claude plugin marketplace add semgrep/guardian && claude plugin install semgrep@semgrep-marketplace`
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

**Claude writes secure code anyway:** Possible for some categories — SQL injection most often, since parameterizing is the reflex. That's still a valid outcome ("Semgrep silently confirms secure code"), and the four scaffold findings (`SECRET_KEY`, both cookie flags, `debug=True`) land regardless: the hook reports every finding in a file Claude touches, not just the lines it changed.

**Semgrep misses a vuln:** Eight classes are targeted, so one miss doesn't cost the demo. Rules do get retired, though — sanity-check the table above against the live ruleset before presenting, by running this on a finished demo run (before `reset.py`):

```bash
TOKEN=$(sed -n 's/^api_token: //p' ~/.semgrep/settings.yml)   # macOS grep has no -P
curl -sS -H "Authorization: Bearer $TOKEN" \
  https://semgrep.dev/c/p/guardian-default -o /tmp/guardian-default.yaml
semgrep scan --config /tmp/guardian-default.yaml app.py templates/
```

Pulling the ruleset down explicitly is what lets you inspect it — `--config p/guardian-default` fetches to a temp file that's deleted on exit.
