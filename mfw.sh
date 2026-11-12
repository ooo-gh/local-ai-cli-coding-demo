#!/usr/bin/env bash
#
# Malware Firewall demo — runs the exact "Test the firewall" steps from
# https://docs.semgrep.dev/semgrep-supply-chain/malware-firewall#test-the-firewall
#
# It runs on the host (the firewall's proxy + daemon only run on your machine),
# in a throwaway project, so the audience watches a real install get blocked.
# No Claude, no container.
#
#   ./mfw.sh              uv init + uv add the demo package (expected: blocked)
#   ./mfw.sh --pip        also repeat the test with pip
#   ./mfw.sh --keep       keep the temp project instead of deleting it
#   ./mfw.sh --skip-checks  skip the mfw doctor readiness check
#
# Demo package: semgrep-malware-demo-aws-cred-read — Semgrep's published, harmless
# fixture. It does not read credentials or run anything; it only trips the firewall.

set -euo pipefail

PKG="semgrep-malware-demo-aws-cred-read"
RUN_PIP=0
KEEP=0
SKIP_CHECKS=0

die()  { printf '\033[31merror:\033[0m %s\n' "$*" >&2; exit 1; }
info() { printf '\033[36m==>\033[0m %s\n' "$*" >&2; }
warn() { printf '\033[33mwarn:\033[0m %s\n' "$*" >&2; }
step() { printf '\n\033[1;36m$ %s\033[0m\n' "$*" >&2; }

while [[ $# -gt 0 ]]; do
  case "$1" in
    --pip)         RUN_PIP=1; shift ;;
    --keep)        KEEP=1; shift ;;
    --skip-checks) SKIP_CHECKS=1; shift ;;
    -h|--help)     awk 'NR>2 && /^#/ {sub(/^# ?/, ""); print; next} NR>2 {exit}' \
                     "${BASH_SOURCE[0]}"; exit 0 ;;
    *)             die "unknown option: $1 (try --help)" ;;
  esac
done

# Give this shell mfw's PATH shims and proxy env even if it never sourced them.
if [[ -f "$HOME/.semgrep/mfw/rc-setup.sh" ]]; then
  # shellcheck disable=SC1091
  source "$HOME/.semgrep/mfw/rc-setup.sh"
fi

command -v uv >/dev/null || die "uv not found on PATH -- install uv first (https://docs.astral.sh/uv/)"

# ── Verify the firewall is active (docs: Install and verify) ──────────────────
if (( ! SKIP_CHECKS )); then
  command -v mfw >/dev/null || die "mfw not installed -- run /install-mfw or the docs installer, then restart your shell"
  step "mfw doctor"
  doctor="$(mfw doctor 2>&1 || true)"
  printf '%s\n' "$doctor" >&2
  if ! printf '%s' "$doctor" | grep -q "protecting this machine"; then
    warn "mfw doctor does not report \"protecting this machine\"."
    warn "If your deployment isn't in the Malware Firewall beta, the install will NOT be blocked."
    warn "Ask your Semgrep admin to enable it, then re-run. (Use --skip-checks to proceed anyway.)"
    die "firewall not ready"
  fi
fi

# ── Test the firewall (docs: Test the firewall) ───────────────────────────────
WORKDIR="$(mktemp -d "${TMPDIR:-/tmp}/mfw-demo.XXXXXX")"
cleanup() { (( KEEP )) || rm -rf "$WORKDIR"; }
trap cleanup EXIT
info "test project: $WORKDIR"
cd "$WORKDIR"

# Step 1 — initialize a project
step "uv init"
uv init

# Step 2 — attempt to install the demo malware package (expected: blocked)
step "uv add --no-cache $PKG"
if uv add --no-cache "$PKG"; then
  warn "The install was NOT blocked. The firewall isn't intercepting this install."
  warn "Check 'mfw doctor' and that the deployment is in the firewall beta."
  blocked=0
else
  info "Install blocked by the Malware Firewall — this is the expected result."
  blocked=1
fi

# Optional — repeat with pip
if (( RUN_PIP )); then
  step "pip install --no-cache $PKG"
  if pip install --no-cache "$PKG"; then
    warn "pip install was NOT blocked."
  else
    info "pip install blocked by the Malware Firewall — expected."
  fi
fi

if (( ! KEEP )); then
  info "cleaning up $WORKDIR"
fi

(( ${blocked:-0} == 1 )) && exit 0 || exit 1
