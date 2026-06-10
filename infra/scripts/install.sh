#!/usr/bin/env bash
# Install the JarvisVR agent-backend ("the brain") and run its setup wizard,
# which asks the user for their LLM API key and writes agent-backend/.env.
#
# Usage:
#   scripts/install.sh                       # venv + install + interactive setup
#   JARVIS_RUN_SETUP=0 scripts/install.sh    # install only (skip the key prompt)
#   JARVIS_INSTALL_EXTRAS="" scripts/install.sh  # base install (no LiteLLM extra)
#   scripts/install.sh --non-interactive --provider openai   # CI / scripted
#
# Any extra args are passed through to `jarvis-backend setup`.
set -euo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_lib.sh"

BACKEND_DIR="$REPO_ROOT/agent-backend"
PYTHON="${PYTHON:-python3}"
EXTRAS="${JARVIS_INSTALL_EXTRAS-providers}"   # set to "" to install the base only
RUN_SETUP="${JARVIS_RUN_SETUP:-1}"

[ -d "$BACKEND_DIR" ] || die "agent-backend not found at $BACKEND_DIR"

log "installing the agent-backend (brain) into a virtualenv"
cd "$BACKEND_DIR"

if [ ! -d .venv ]; then
  log "creating venv at agent-backend/.venv"
  "$PYTHON" -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
python -m pip install --quiet --upgrade pip

spec="."
[ -n "$EXTRAS" ] && spec=".[$EXTRAS]"
log "installing jarvis-backend ($spec)"
if ! pip install -e "$spec"; then
  warn "install of '$spec' failed (offline or unavailable extra); retrying base install"
  pip install -e .
fi

if [ "$RUN_SETUP" = "1" ]; then
  echo
  log "running the setup wizard — it will ask which LLM provider to use and for your API key"
  log "(choose 'mock' to run fully offline with no key)"
  echo
  if ! jarvis-backend setup "$@"; then
    warn "setup did not finish; re-run later with:"
    warn "  (cd agent-backend && source .venv/bin/activate && jarvis-backend setup)"
  fi
else
  log "skipping setup (JARVIS_RUN_SETUP=0). Configure later: jarvis-backend setup"
fi

echo
log "installed. Start the brain with:"
log "  cd agent-backend && source .venv/bin/activate && python -m jarvis_backend"
