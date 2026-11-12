#!/usr/bin/env bash
#
# Same launch as ./demo.sh, with the plus prompt pre-filled.
# Jamie's five findings stay in CLAUDE.md. The extra case is in PLUS.md,
# and only this prompt asks for it.
#
#   ./demoplus.sh
#   ./demoplus.sh --rebuild
#   ./demoplus.sh --no-prefill
#   ./demoplus.sh --permission-mode manual
#   ./demoplus.sh --model <id>
#   ./demoplus.sh --reset-login
#   ./demoplus.sh --skip-checks

set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export DEMO_PROMPT_FILE="$REPO/DEMO_PROMPT_PLUS.md"
exec "$REPO/demo.sh" "$@"
