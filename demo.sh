#!/usr/bin/env bash
#
# Launch the TaskBoard demo inside its devcontainer, with the demo prompt
# already sitting in Claude Code's input box waiting for you to hit Enter.
#
#   ./demo.sh                      launch (build on first run, reuse after)
#   ./demo.sh --rebuild            force an image rebuild
#   ./demo.sh --no-prefill         start Claude with an empty prompt box
#   ./demo.sh --permission-mode manual   prompt for every tool call
#                                  (default: bypassPermissions -- no prompts,
#                                  so the container is the only boundary)
#   ./demo.sh --reset-login        drop the persisted Claude login volume
#   ./demo.sh --skip-checks        skip the in-container prereq.py run
#
# What it does, in order: brings the devcontainer up, runs prereq.py inside it,
# starts Claude Code in a tmux session, pastes the prompt from DEMO_PROMPT.md
# (everything after the `---`) as a bracketed paste so it lands unsubmitted,
# then attaches your terminal to that session.
#
# Quitting Claude drops you into a shell in the container, where `git diff` and
# `python3 reset.py` operate on the bind-mounted host repo. Detach without
# killing the session with C-b d.

set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SESSION="demo"
CLAUDE_VOLUME="taskboard-demo-claude"
PROMPT_FILE="$REPO/DEMO_PROMPT.md"
# Generous on purpose: on a fresh ~/.claude volume this has to outlast an OAuth
# login before the input box exists. (post_create.py pre-answers the theme, TUI
# and trust dialogs, so the login is all that is left.) The poller exits the
# moment it pastes, so a high ceiling costs nothing.
READY_TIMEOUT="${DEMO_READY_TIMEOUT:-600}"

PERMISSION_MODE="${DEMO_PERMISSION_MODE:-bypassPermissions}"
PREFILL=1
REBUILD=0
RESET_LOGIN=0
SKIP_CHECKS=0

die()  { printf '\033[31merror:\033[0m %s\n' "$*" >&2; exit 1; }
info() { printf '\033[36m==>\033[0m %s\n' "$*" >&2; }
warn() { printf '\033[33mwarn:\033[0m %s\n' "$*" >&2; }

while [[ $# -gt 0 ]]; do
  case "$1" in
    --rebuild)          REBUILD=1; shift ;;
    --no-prefill)       PREFILL=0; shift ;;
    --reset-login)      RESET_LOGIN=1; shift ;;
    --skip-checks)      SKIP_CHECKS=1; shift ;;
    --permission-mode)  PERMISSION_MODE="${2:?--permission-mode needs a value}"; shift 2 ;;
    # Print the header comment block, minus the shebang, as the usage text.
    -h|--help)          awk 'NR>2 && /^#/ {sub(/^# ?/, ""); print; next} NR>2 {exit}' \
                          "${BASH_SOURCE[0]}"; exit 0 ;;
    *)                  die "unknown option: $1 (try --help)" ;;
  esac
done

# ── Host preflight ──────────────────────────────────────────────────────────

command -v docker >/dev/null || die "docker not found on PATH"
docker info >/dev/null 2>&1 || die "docker is not responding -- is Colima running? (colima start)"

# Colima only shares $HOME into the VM. A bind mount from anywhere else comes up
# silently empty, so refuse to launch from outside the home tree rather than
# hand the presenter an empty /workspace mid-demo.
case "$REPO/" in
  "$HOME"/*) ;;
  *) die "repo lives outside \$HOME ($REPO); Colima cannot bind-mount it" ;;
esac

[[ -f "$PROMPT_FILE" ]] || die "missing $PROMPT_FILE"

if [[ ! -s "$HOME/.semgrep/guardian.yml" ]]; then
  warn "no Semgrep credentials at ~/.semgrep/guardian.yml"
  warn "the Guardian hook will not scan -- ask \"log in to semgrep using oauth\" in the session"
fi

# ── devcontainer CLI ────────────────────────────────────────────────────────

if command -v devcontainer >/dev/null; then
  DEVCONTAINER=(devcontainer)
elif command -v npx >/dev/null; then
  # Pin via DEVCONTAINER_CLI_SPEC to avoid pulling a fresh release mid-demo.
  info "devcontainer CLI not installed; using npx ${DEVCONTAINER_CLI_SPEC:-@devcontainers/cli}"
  DEVCONTAINER=(npx --yes "${DEVCONTAINER_CLI_SPEC:-@devcontainers/cli}")
else
  die "need the devcontainer CLI: npm install -g @devcontainers/cli"
fi

# ── Bring the container up ──────────────────────────────────────────────────

if (( RESET_LOGIN )); then
  # Order matters, and so does not hiding the error. `docker volume rm` refuses
  # while any container -- running or merely stopped -- still has the volume
  # mounted, so removing it before `devcontainer up` tears the old container down
  # fails on every re-run. Swallowed, that silently keeps the previous login and
  # --reset-login becomes a no-op: the exact opposite of what it promises.
  holders="$(docker ps -aq --filter "volume=$CLAUDE_VOLUME")"
  if [[ -n "$holders" ]]; then
    info "removing containers holding $CLAUDE_VOLUME"
    # Unquoted on purpose: one id per line, and `set -u` is covered by the -n test.
    # shellcheck disable=SC2086
    docker rm -f $holders >/dev/null || die "could not remove containers using $CLAUDE_VOLUME"
  fi

  if docker volume inspect "$CLAUDE_VOLUME" >/dev/null 2>&1; then
    warn "removing volume $CLAUDE_VOLUME -- you will have to log in to Claude again"
    docker volume rm "$CLAUDE_VOLUME" >/dev/null \
      || die "could not remove $CLAUDE_VOLUME -- something still has it mounted"
  else
    info "volume $CLAUDE_VOLUME is already gone -- nothing to reset"
  fi
fi

# Always recreate the container, never reuse. It costs a few seconds (the image
# is cached), and it guarantees exactly one container carries the devcontainer
# label -- reusing left stale containers behind, and a second labelled container
# makes `devcontainer up` ambiguous about which one you get. It also reruns
# postStartCommand, which is what reconciles the plugin into ~/.claude.
up_args=(up --workspace-folder "$REPO" --remove-existing-container)
if (( REBUILD )); then
  up_args+=(--build-no-cache)
fi

info "bringing up devcontainer (first run builds the image; expect a few minutes)"
up_output="$("${DEVCONTAINER[@]}" "${up_args[@]}" 2>&1 | tee /dev/stderr)"

# `devcontainer up` reports its result as a JSON object on the last matching
# line. Take the container id from there rather than guessing at names.
CID="$(printf '%s\n' "$up_output" \
  | grep -o '{"outcome".*}' \
  | tail -1 \
  | python3 -c 'import json,sys; print(json.load(sys.stdin).get("containerId",""))' 2>/dev/null || true)"

[[ -n "$CID" ]] || die "could not determine container id from 'devcontainer up' output"
info "container: ${CID:0:12}"

cexec()  { docker exec -u vscode -w /workspace "$CID" "$@"; }
cexec_i(){ docker exec -i -u vscode -w /workspace "$CID" "$@"; }

# ── Prerequisite check, inside the container ─────────────────────────────────

if (( ! SKIP_CHECKS )); then
  info "running prereq.py inside the container"
  if ! cexec python3 prereq.py; then
    die "prereq.py failed -- fix the above, or re-run with --skip-checks"
  fi
fi

# ── Start Claude Code under tmux ────────────────────────────────────────────

cols="$( (tput cols  2>/dev/null) || echo 120 )"
lines="$( (tput lines 2>/dev/null) || echo 40  )"

# Always start from a clean session so each launch is a fresh conversation.
cexec tmux kill-session -t "$SESSION" >/dev/null 2>&1 || true

claude_cmd="claude --permission-mode $(printf '%q' "$PERMISSION_MODE")"
wrapped="${claude_cmd}; printf '\n[demo] Claude exited. Container shell -- git diff, python3 reset.py, exit.\n'; exec bash -l"

info "starting Claude Code (permission mode: $PERMISSION_MODE)"
# -u forces UTF-8 output even if tmux's own locale check comes up short; the
# image sets LANG for the same reason, and either alone is sufficient.
cexec tmux -u new-session -d -s "$SESSION" -x "$cols" -y "$lines" "$wrapped"

# ── Pre-fill the prompt ─────────────────────────────────────────────────────

if (( PREFILL )); then
  # Everything after the first `---` line in DEMO_PROMPT.md, whitespace-trimmed.
  prompt="$(python3 - "$PROMPT_FILE" <<'PY'
import sys

with open(sys.argv[1], encoding="utf-8") as fh:
    lines = fh.read().splitlines()

for i, line in enumerate(lines):
    if line.strip() == "---":
        body = "\n".join(lines[i + 1:]).strip()
        break
else:
    body = "\n".join(lines).strip()

if not body:
    sys.exit("DEMO_PROMPT.md has no prompt body after the '---' separator")

sys.stdout.write(body)
PY
)" || die "could not extract the prompt from DEMO_PROMPT.md"

  printf '%s' "$prompt" | cexec_i tmux load-buffer -b demo-prompt -

  # The pre-fill runs from a detached poller inside the container rather than
  # inline, because the input box may not be up yet -- on the very first launch
  # against a fresh ~/.claude volume there is an OAuth login in the way. Polling
  # past the attach lets you log in yourself and still get the prompt filled in
  # the moment the box appears.
  #
  # Three details learned the hard way:
  #   - capture-pane needs -S - : Claude Code draws into scrollback, so the
  #     visible-screen-only capture comes back blank.
  #   - paste twice : the first bracketed paste collapses to a
  #     "[Pasted text #1 +5 lines]" placeholder, the second expands it to the
  #     full text. Same content both times, so nothing is duplicated -- and an
  #     expanded prompt is the point when it is going up on a projector.
  #   - match on the input box, not on a hint : this waited for "for shortcuts",
  #     but that hint shares its slot with others ("install gh for PR status",
  #     ...), so on a launch that drew a different one the poller spun out its
  #     whole timeout and the box stayed empty. The prompt char and the
  #     permission-mode line are structural, so match either of those, and say
  #     so on the way out if neither ever shows up.
  poller=$(printf '
    for _ in $(seq %d); do
      if tmux capture-pane -p -S - -t %s 2>/dev/null \
           | grep -q -e "shift+tab to cycle" -e "❯"; then
        tmux paste-buffer -b demo-prompt -t %s -p
        sleep 1
        tmux paste-buffer -b demo-prompt -t %s -p -d
        exit 0
      fi
      sleep 1
    done
    tmux display-message -t %s "[demo] prompt pre-fill timed out -- paste it with: tmux paste-buffer -b demo-prompt -p"
  ' "$READY_TIMEOUT" "$SESSION" "$SESSION" "$SESSION" "$SESSION")

  docker exec -d -u vscode "$CID" bash -c "$poller"
  info "prompt will appear in the input box shortly -- press Enter to send it"
  info "first launch only: run 'claude auth login' first -- the prompt fills"
  info "  itself in as soon as the input box appears"
fi

# ── Hand over the terminal ──────────────────────────────────────────────────

info "attaching (C-b d to detach without stopping the session)"
exec docker exec -it -u vscode -e TERM="${TERM:-xterm-256color}" "$CID" \
  tmux -u attach -t "$SESSION"
