# TaskBoard Demo: Claude Code + Semgrep Auto-Scan

A reproducible demo showing Claude Code generating code, the Semgrep plugin automatically catching vulnerabilities when Claude's turn ends, and Claude fixing them — all visible in the CLI.

**Audience:** Developers/engineers. **Duration:** 5-7 minutes.

## Prerequisites

- Python 3.10+
- [Claude Code CLI](https://docs.anthropic.com/en/docs/claude-code) installed
- Semgrep Guardian plugin installed from Semgrep's marketplace, [github.com/semgrep/guardian](https://github.com/semgrep/guardian)
  — MDM rolls it out as `semgrep@semgrep-marketplace`; check with `claude /plugin`, or add it by hand with
  `claude plugin marketplace add semgrep/guardian && claude plugin install semgrep@semgrep-marketplace`
- Semgrep 1.x+ installed and logged in (OIDC credentials in `~/.semgrep/guardian.yml`)
- For `./demoplus.sh` only: your deployment is on the `guardian.shadow_review_enabled` feature flag. Sign-in alone does not turn Shadow on. Add the deployment to that flag before presenting, or Shadow stays silent while the five rule findings still appear. `./demo.sh` does not need the flag.
- For `./mfw.sh` only: this one runs on the host, not in the devcontainer — the firewall's proxy and daemon only run on your machine, so the container can't block installs. The deployment must be in the Malware Firewall private beta (ask your Semgrep admin; sign-in alone doesn't enable it), `mfw` must be installed (`/install-mfw` or the docs installer), and `mfw doctor` must report "protecting this machine". The prompt installs Semgrep's demo fixture `semgrep-malware-demo-aws-cred-read`, which the firewall then blocks.

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
./demo.sh --model <id>               model to launch with (default: claude-opus-5-5)
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

The prompt lives in [`DEMO_PROMPT.md`](DEMO_PROMPT.md) (everything after the `---`). It asks
for five features: a task list page, a create-task API that sends a notification, board
snapshot export/import, task ownership from the SSO bearer token, and task attachment
downloads.

## What Happens

The `CLAUDE.md` file contains project conventions that naturally steer Claude toward insecure
patterns. Claude writes the whole feature, then ends its turn. Guardian's Stop hook scans what
was written and hands the findings back, and Claude fixes them.

### Expected Vulnerability Cycle

Every rule below fires against the `guardian-default` ruleset on a representative first pass,
all in `app.py`. Each one is pattern-matched off a construct a convention names outright,
so the count doesn't depend on Claude's style.

| Vuln | Where it comes from | Semgrep rule | Severity |
|------|--------------------|--------------|----------|
| Command Injection | export shells out with `subprocess.run(..., shell=True)` | `subprocess-shell-true` | ERROR |
| Command Injection | request data interpolated into that command | `subprocess-injection` | ERROR |
| Insecure Deserialization | snapshot import via `pickle.loads()` | `avoid-pickle` | WARNING |
| Insecure Deserialization | `pickle.loads()` on request data in a Flask route | `insecure-deserialization` | ERROR |
| Disabled TLS Verification | notification via `ssl._create_unverified_context()` | `unverified-ssl-context` | ERROR |
| Authentication Bypass | task owner read from `jwt.decode(..., options={"verify_signature": False})` | `unverified-jwt-decode` | ERROR |
| Path Traversal | attachment read via `open(os.path.join(ATTACHMENT_DIR, name), "rb")` with `name` from `request.args` | `path-traversal-open` | ERROR |

**Total:** 7 findings on the first pass.

The path-traversal rule is a plain pattern match that follows at most one assignment from
`request` to `open()`. `name = request.args.get(...)` followed by `open(os.path.join(DIR, name))`
fires; adding a second hop (`path = os.path.join(DIR, name)`, then `open(path)`) or using
`send_file(...)` instead of `open()` goes silent. That is why the attachments convention
spells out the inline `open(os.path.join(...))` call.

**Deliberately left out:**
- **SQL injection.** One f-string query sets off four rules (`tainted-sql-string` ×2,
  `formatted-sql-query`, `sqlalchemy-execute-raw-query`), and whether it appears at all
  depends on whether Claude writes the f-string.
- **Template XSS (`{% autoescape false %}`).** The rule fires locally, but the Stop hook
  didn't report it on a real run.
- **Session cookie flags.** Neither cookie-flag rule fired on the scaffold.
- **Hardcoded `SECRET_KEY` and `debug=True`.** These lived in the scaffold, which the prompt
  never touches, so whether they were reported varied from run to run.

**Other candidate beats, checked against `guardian-default` with Flask routes and `request.args` input:**
- **Fire:** `os.system()` on request data (`os-system-injection`), `eval()` on request data
  (`eval-injection` plus `eval-detected`), `requests.get()` on a request-supplied URL
  (`ssrf-requests`), and `make_response()` with HTML concatenated from request data
  (`raw-html-format`, reported twice). Path traversal fires too, but only in the shape
  described above.
- **Silent:** SSRF through `urllib.request.urlopen()` (the SSRF rule only knows `requests`),
  a Flask open redirect (`redirect(request.args.get(...))`; the redirect rule in the set
  is FastAPI-only), Flask-CORS with `origins="*"` (the wildcard-CORS rule is FastAPI-only),
  and `hashlib.md5()` (the md5 rules cover the `cryptography` and `pycryptodome` libraries,
  not `hashlib`).

### Demo Flow

1. **[0:00] Show the project** — `ls`, `cat app.py` (just a skeleton), `cat CLAUDE.md`
2. **[0:30] Open Claude Code** — SessionStart hook confirms Semgrep is active
3. **[1:00] Paste the prompt** — read it aloud, emphasize it's a normal feature request
4. **[1:30] Claude writes the features** — edits to `app.py` and `templates/tasks.html`, then a short summary
5. **[2:30] Turn ends, Guardian reports** — the Stop hook comes back with the findings. This is the "aha" moment.
6. **[3:00] Claude fixes them** — `subprocess.run([...])` without a shell, JSON instead of `pickle`, a verified TLS context, the bearer token verified against the gateway's public keys (`jwt.PyJWKClient` plus `algorithms=["RS256"]`), and the attachment path resolved and rejected if it falls outside `ATTACHMENT_DIR` (or served with `send_from_directory`). The next scan comes back clean.
7. **[4:00] Talking points** — seven issues across five vulnerability classes, caught and fixed with no human intervention

## How It Works

- **`CLAUDE.md`** — Project conventions that look normal but bias toward insecure patterns (`pickle` snapshots, a shelled-out export, an unverified TLS context, an unverified JWT, a request-supplied filename handed to `open()`). Each convention states the vuln class it produces
- **`DEMO_PROMPT.md`** — The exact prompt to paste, worded so each feature request lands on one of those conventions
- **`app.py`** — Minimal Flask skeleton with a `get_db()` helper that returns a raw sqlite3 connection
- **Stop hook** — From the Semgrep Guardian plugin; scans the files Claude changed when the turn ends and feeds the findings back to Claude
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

**Hook doesn't fire:** Have Claude write a test file with `password = "test"` and end its turn; the Stop hook should report it. If not, verify the plugin is enabled in `~/.claude/settings.json`.

**Claude writes secure code anyway:** Each convention names the exact insecure call, so this is rare. If it happens, that's still a valid outcome ("Semgrep silently confirms secure code").

**Semgrep misses a vuln:** Rules do get retired. Rules do get retired, though — sanity-check the table above against the live ruleset before presenting, by running this on a finished demo run (before `reset.py`):

```bash
TOKEN=$(sed -n 's/^api_token: //p' ~/.semgrep/settings.yml)   # macOS grep has no -P
curl -sS -H "Authorization: Bearer $TOKEN" \
  https://semgrep.dev/c/p/guardian-default -o /tmp/guardian-default.yaml
semgrep scan --config /tmp/guardian-default.yaml app.py templates/
```

Pulling the ruleset down explicitly is what lets you inspect it — `--config p/guardian-default` fetches to a temp file that's deleted on exit.
