#!/usr/bin/env bash
# Bring up the mock brain via Docker Compose (no sibling images needed).
# Usage: scripts/mock.sh [extra docker compose args]
set -euo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_lib.sh"

ensure_env_file
cd "$INFRA_DIR"

log "starting mock brain on ws://localhost:8765/jarvis"
compose -f docker-compose.yml -f docker-compose.mock.yml up --build "$@" agent-backend
