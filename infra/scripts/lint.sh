#!/usr/bin/env bash
# Best-effort lint/typecheck across the owned dirs. Fails on real errors, but
# gracefully skips tools that aren't installed.
# Usage: scripts/lint.sh
set -euo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_lib.sh"

status=0
PY_TARGETS=("$PY_BINDING/src" "$INFRA_DIR/mock-backend" "$INFRA_DIR/e2e")

# --- Python ---
if command -v ruff >/dev/null 2>&1; then
  log "ruff check"
  ruff check "${PY_TARGETS[@]}" || status=1
else
  warn "ruff not installed; falling back to byte-compile check"
  python3 -m compileall -q "${PY_TARGETS[@]}" || status=1
fi

# --- TypeScript ---
TS_DIR="$REPO_ROOT/shared-protocol/typescript"
if command -v npm >/dev/null 2>&1 && [ -d "$TS_DIR/node_modules" ]; then
  log "tsc --noEmit"
  ( cd "$TS_DIR" && npm run -s typecheck ) || status=1
else
  warn "skipping tsc (npm or node_modules missing; run 'make test' once to install)"
fi

[ "$status" -eq 0 ] && log "lint OK" || warn "lint found issues"
exit "$status"
