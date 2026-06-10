#!/usr/bin/env bash
# Measure test coverage across the components owned by Integration:
#   * shared-protocol/python   (jarvis_protocol)        -> gated at 100%
#   * shared-protocol/typescript (@jarvisvr/protocol)   -> gated at 100% (vitest thresholds)
#   * infra (mock-backend/server.py + e2e harness/validators) -> gated at 100%
# Prints each component's coverage table and a final summary.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INFRA_DIR="$(dirname "$SCRIPT_DIR")"
REPO_ROOT="$(dirname "$INFRA_DIR")"
VENV="$INFRA_DIR/.venv"
PY="$VENV/bin/python"

echo "==> Preparing venv ($VENV)"
[ -d "$VENV" ] || python3 -m venv "$VENV"
"$PY" -m pip install -q --upgrade pip
"$PY" -m pip install -q -e "$REPO_ROOT/shared-protocol/python[dev]"
"$PY" -m pip install -q -r "$INFRA_DIR/e2e/requirements.txt"

echo
echo "==> shared-protocol/python  (jarvis_protocol)"
( cd "$REPO_ROOT/shared-protocol/python" \
  && "$PY" -m pytest --cov=jarvis_protocol --cov-branch --cov-report=term-missing )

echo
echo "==> shared-protocol/typescript  (@jarvisvr/protocol)"
if command -v npm >/dev/null 2>&1; then
  ( cd "$REPO_ROOT/shared-protocol/typescript" \
    && { [ -d node_modules ] || npm install; } \
    && npm run --silent test:coverage )
else
  echo "    npm not found — skipping TypeScript coverage" >&2
fi

echo
echo "==> infra  (mock-backend/server.py + e2e harness/validators)"
( cd "$REPO_ROOT" \
  && "$PY" -m pytest infra/e2e \
       --cov=server --cov=harness --cov=holo_tools \
       --cov-branch --cov-report=term-missing --cov-fail-under=100 )

echo
echo "==> Coverage complete: shared-protocol (py+ts) and infra are at 100% (gated)."
