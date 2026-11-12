#!/usr/bin/env bash
#
# Malware Firewall demo, on the host (not the devcontainer).
#
# The firewall gates package installs through a local proxy + daemon that only
# run on your machine, so this demo runs Claude Code on the host, in a shell
# where mfw's proxy env is active. The container cannot block installs.
#
#   ./mfw.sh                      launch Claude on the host, prompt on the clipboard
#   ./mfw.sh --no-prefill         don't touch the clipboard
#   ./mfw.sh --permission-mode X  Claude permission mode (default: Claude's own)
#   ./mfw.sh --model <id>         model to launch with (default: claude-opus-5-5)
#   ./mfw.sh --skip-checks        skip the mfw readiness check
#
# Read the prompt aloud off the projector, paste it (Cmd-V), and hit Enter.

set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROMPT_FILE="$REPO/MFW_PROMPT.md"
MODEL="${DEMO_MODEL:-claude-opus-5-5}"
PERMISSION_MODE="${DEMO_PERMISSION_MODE:-}"
PREFILL=1
SKIP_CHECKS=0

die()  { printf '\033[31merror:\033[0m %s\n' "$*" >&2; exit 1; }
info() { printf '\033[36m==>\033[0m %s\n' "$*" >&2; }
warn() { printf '\033[33mwarn:\033[0m %s\n' "$*" >&2; }

while [[ $# -gt 0 ]]; do
  case "$1" in
    --no-prefill)      PREFILL=0; shift ;;
    --skip-checks)     SKIP_CHECKS=1; shift ;;
    --permission-mode) PERMISSION_MODE="${2:?--permission-mode needs a value}"; shift 2 ;;
    --model)           MODEL="${2:?--model needs a value}"; shift 2 ;;
    -h|--help)         awk 'NR>2 && /^#/ {sub(/^# ?/, ""); print; next} NR>2 {exit}' \
                         "${BASH_SOURCE[0]}"; exit 0 ;;
    *)                 die "unknown option: $1 (try --help)" ;;
  esac
done

command -v claude >/dev/null || die "claude not found on PATH"
[[ -f "$PROMPT_FILE" ]] || die "missing $PROMPT_FILE"

# Make sure this shell has mfw's PATH shims and proxy env, even if the launcher
# was started from a shell that never sourced them.
if [[ -f "$HOME/.semgrep/mfw/rc-setup.sh" ]]; then
  # shellcheck disable=SC1091
  source "$HOME/.semgrep/mfw/rc-setup.sh"
fi

# ── Firewall readiness ───────────────────────────────────────────────────────
# Without this the install just succeeds and there is nothing to show. The two
# common reasons are mfw not installed, and a deployment not in the firewall beta.

if (( ! SKIP_CHECKS )); then
  if ! command -v mfw >/dev/null; then
    warn "mfw is not installed on this machine -- run /install-mfw (or the docs installer) first."
    warn "without it the install will NOT be blocked. Continuing anyway."
  else
    doctor="$(mfw doctor 2>&1 || true)"
    if printf '%s' "$doctor" | grep -q "protecting this machine"; then
      info "mfw doctor: machine protected"
    else
      warn "mfw doctor does not report this machine protected. The install will not be blocked until this is fixed:"
      printf '%s\n' "$doctor" | grep -E '✗|isn.t enabled|not .*enabled|deployment' | sed 's/^/    /' >&2 || true
      warn "if the deployment isn't in the Malware Firewall beta, ask your Semgrep admin to enable it."
    fi
  fi
fi

# ── Prompt onto the clipboard ────────────────────────────────────────────────

prompt="$(awk 'f{print} /^---$/{f=1}' "$PROMPT_FILE" | sed '/./,$!d')"
[[ -n "$prompt" ]] || die "no prompt body after the '---' separator in $PROMPT_FILE"

if (( PREFILL )) && command -v pbcopy >/dev/null; then
  printf '%s' "$prompt" | pbcopy
  info "prompt copied to the clipboard -- paste it into Claude (Cmd-V) and press Enter"
else
  info "prompt (paste into Claude, then press Enter):"
fi
printf '\n%s\n\n' "$prompt" >&2

# ── Launch Claude Code on the host ───────────────────────────────────────────

cd "$REPO"
claude_args=(--model "$MODEL")
[[ -n "$PERMISSION_MODE" ]] && claude_args+=(--permission-mode "$PERMISSION_MODE")
info "starting Claude Code on the host in $REPO"
exec claude "${claude_args[@]}"
