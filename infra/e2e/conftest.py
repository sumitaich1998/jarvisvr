"""Pytest fixtures for the e2e harness: spin up the mock backend on a free port."""

from __future__ import annotations

import contextlib
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

E2E_DIR = Path(__file__).resolve().parent
INFRA_DIR = E2E_DIR.parent
REPO_ROOT = INFRA_DIR.parent
MOCK_SERVER = INFRA_DIR / "mock-backend" / "server.py"
SCHEMA_DIR = REPO_ROOT / "shared-protocol" / "schema"


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _wait_for_port(host: str, port: int, timeout: float = 15.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        with contextlib.suppress(OSError):
            with socket.create_connection((host, port), timeout=0.5):
                return True
        time.sleep(0.1)
    return False


@pytest.fixture(scope="session")
def mock_backend_url():
    """Start infra/mock-backend on a free port; yield its ws URL; tear down."""
    port = _free_port()
    env = dict(os.environ)
    env.update(
        JARVIS_HOST="127.0.0.1",
        JARVIS_PORT=str(port),
        JARVIS_WS_PATH="/jarvis",
        LOG_LEVEL=env.get("LOG_LEVEL", "WARNING"),
    )
    env.setdefault("JARVIS_PROTOCOL_SCHEMA_DIR", str(SCHEMA_DIR))

    proc = subprocess.Popen(
        [sys.executable, str(MOCK_SERVER)],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        if not _wait_for_port("127.0.0.1", port):
            output = proc.stdout.read() if proc.stdout else ""
            proc.terminate()
            raise RuntimeError(f"mock backend failed to start on port {port}:\n{output}")
        yield f"ws://127.0.0.1:{port}/jarvis"
    finally:
        proc.terminate()
        with contextlib.suppress(Exception):
            proc.wait(timeout=5)
