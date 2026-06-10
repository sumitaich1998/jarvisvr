#!/usr/bin/env bash
# Best-effort autoformat (ruff for Python, prettier for TS). Skips missing tools.
# Usage: scripts/fmt.sh
set -euo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_lib.sh"

if command -v ruff >/dev/null 2>&1; then
  log "ruff format"
  ruff format "$PY_BINDING/src" "$INFRA_DIR/mock-backend" "$INFRA_DIR/e2e"
else
  warn "ruff not installed; skipping Python formatting"
fi

TS_DIR="$REPO_ROOT/shared-protocol/typescript"
if command -v npx >/dev/null 2>&1; then
  log "prettier (typescript, if available)"
  ( cd "$TS_DIR" && npx --no-install prettier --write "src/**/*.ts" "test/**/*.ts" 2>/dev/null ) \
    || warn "prettier not available; skipping TS formatting"
fi
log "fmt done"
