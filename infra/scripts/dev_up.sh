#!/usr/bin/env bash
# Bring up the real stack (agent-backend + voice-service) via Docker Compose.
# Usage: scripts/dev_up.sh [extra docker compose args]
set -euo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_lib.sh"

ensure_env_file
cd "$INFRA_DIR"

log "starting stack: docker compose up --build -d $*"
if ! compose up --build -d "$@"; then
  warn "compose up failed — sibling images (../agent-backend, ../voice-service) may not exist yet."
  warn "For a no-sibling dev loop, run the mock instead:  make mock   (or scripts/e2e.sh)"
  exit 1
fi
compose ps
log "agent-backend should be reachable at ws://localhost:8765/jarvis"
