#!/usr/bin/env bash
# Start the mock brain (locally, no Docker) and run the conformance harness.
# Exits non-zero if any received message violates the protocol.
#
# Usage:
#   scripts/e2e.sh                          # start mock + run harness
#   JARVIS_BACKEND_URL=ws://host:8765/jarvis scripts/e2e.sh   # against another backend
#   E2E_STRICT_PROPS=1 scripts/e2e.sh       # fail on holo-tools props mismatches
set -euo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_lib.sh"

ensure_venv

MOCK_PID=""
cleanup() { [ -n "$MOCK_PID" ] && kill "$MOCK_PID" 2>/dev/null || true; }
trap cleanup EXIT

URL="${JARVIS_BACKEND_URL:-}"
if [ -z "$URL" ]; then
  PORT="$(free_port)"
  log "starting mock brain on 127.0.0.1:$PORT"
  JARVIS_HOST=127.0.0.1 JARVIS_PORT="$PORT" JARVIS_WS_PATH=/jarvis LOG_LEVEL="${LOG_LEVEL:-WARNING}" \
    python "$INFRA_DIR/mock-backend/server.py" &
  MOCK_PID=$!
  wait_for_port 127.0.0.1 "$PORT" 15 || die "mock backend did not start"
  URL="ws://127.0.0.1:$PORT/jarvis"
else
  log "using existing backend at $URL"
fi

log "running conformance harness against $URL"
python "$INFRA_DIR/e2e/harness.py" --url "$URL"
