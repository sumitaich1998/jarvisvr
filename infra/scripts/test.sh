#!/usr/bin/env bash
# Run the shared-protocol test suites (Python always; TypeScript if Node is present).
# Usage: scripts/test.sh
set -euo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_lib.sh"

ensure_venv

log "running Python protocol tests (jarvis-protocol)"
( cd "$PY_BINDING" && python -m pytest -q )

TS_DIR="$REPO_ROOT/shared-protocol/typescript"
if command -v npm >/dev/null 2>&1; then
  log "running TypeScript protocol tests (@jarvisvr/protocol)"
  ( cd "$TS_DIR" && { [ -d node_modules ] || npm install --silent; } && npm test --silent )
else
  warn "npm not found; skipping TypeScript tests"
fi

log "all protocol tests passed"
