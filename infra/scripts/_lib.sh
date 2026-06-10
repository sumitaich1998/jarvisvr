#!/usr/bin/env bash
# Shared helpers for the JarvisVR infra scripts. Source this; don't run directly.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INFRA_DIR="$(dirname "$SCRIPT_DIR")"
REPO_ROOT="$(dirname "$INFRA_DIR")"
VENV="$INFRA_DIR/.venv"
PY_BINDING="$REPO_ROOT/shared-protocol/python"

# The bindings find schemas via upward search, but pin it for safety everywhere.
export JARVIS_PROTOCOL_SCHEMA_DIR="$REPO_ROOT/shared-protocol/schema"

log()  { printf '\033[1;36m[jarvis]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[jarvis]\033[0m %s\n' "$*" >&2; }
die()  { printf '\033[1;31m[jarvis] ERROR:\033[0m %s\n' "$*" >&2; exit 1; }

# Echo the available Docker Compose command (v2 plugin or legacy binary).
compose() {
  if docker compose version >/dev/null 2>&1; then
    docker compose "$@"
  elif command -v docker-compose >/dev/null 2>&1; then
    docker-compose "$@"
  else
    die "neither 'docker compose' nor 'docker-compose' is installed"
  fi
}

# Copy .env from the example if it's missing (compose env_file needs it to exist).
ensure_env_file() {
  if [ ! -f "$INFRA_DIR/.env" ]; then
    log "creating infra/.env from .env.example"
    cp "$INFRA_DIR/.env.example" "$INFRA_DIR/.env"
  fi
}

# Create the venv (if needed) and install the protocol binding + harness deps.
ensure_venv() {
  if [ ! -d "$VENV" ]; then
    log "creating venv at infra/.venv"
    python3 -m venv "$VENV"
  fi
  # shellcheck disable=SC1091
  source "$VENV/bin/activate"
  python -m pip install --quiet --upgrade pip
  log "installing jarvis-protocol (editable) + deps"
  pip install --quiet -e "$PY_BINDING[dev]"
  pip install --quiet -r "$INFRA_DIR/e2e/requirements.txt"
}

# Find a free TCP port (prints the number).
free_port() {
  python3 - <<'PY'
import socket
s = socket.socket()
s.bind(("127.0.0.1", 0))
print(s.getsockname()[1])
s.close()
PY
}

# Block until host:port accepts a connection (args: host port [timeout_s]).
wait_for_port() {
  local host="$1" port="$2" timeout="${3:-15}"
  python3 - "$host" "$port" "$timeout" <<'PY'
import socket, sys, time
host, port, timeout = sys.argv[1], int(sys.argv[2]), float(sys.argv[3])
end = time.time() + timeout
while time.time() < end:
    try:
        with socket.create_connection((host, port), 0.5):
            sys.exit(0)
    except OSError:
        time.sleep(0.1)
sys.exit(1)
PY
}
