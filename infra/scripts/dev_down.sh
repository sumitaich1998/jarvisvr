#!/usr/bin/env bash
# Tear down the stack (works for both the real and mock compositions).
# Usage: scripts/dev_down.sh [extra docker compose args]
set -euo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_lib.sh"

cd "$INFRA_DIR"
log "stopping stack: docker compose down $*"
compose -f docker-compose.yml -f docker-compose.mock.yml down "$@" 2>/dev/null \
  || compose down "$@"
log "done"
