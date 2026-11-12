#!/usr/bin/env bash
#
# Same launch as ./demo.sh, with the Malware Firewall prompt pre-filled.
#
#   ./mfw.sh
#   ./mfw.sh --rebuild
#   ./mfw.sh --no-prefill
#   ./mfw.sh --permission-mode manual
#   ./mfw.sh --model <id>
#   ./mfw.sh --reset-login
#   ./mfw.sh --skip-checks

set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export DEMO_PROMPT_FILE="$REPO/MFW_PROMPT.md"

if ! command -v mfw >/dev/null 2>&1; then
  printf '\033[33mwarn:\033[0m mfw is not on PATH. Install it and sign in before sending the prompt, or the package install will not be blocked.\n' >&2
elif ! mfw doctor 2>&1 | grep -q "protecting this machine"; then
  printf '\033[33mwarn:\033[0m mfw doctor does not report this machine protected. Fix that before sending the prompt.\n' >&2
fi
printf '\033[33mwarn:\033[0m Claude runs inside the devcontainer. The host firewall does not see installs there. Run /install-mfw in that session, restart the shell it starts, and confirm mfw doctor before sending the prompt.\n' >&2

exec "$REPO/demo.sh" "$@"
