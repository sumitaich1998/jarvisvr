"""Protocol version constant for the JarvisVR wire protocol (v1)."""

from __future__ import annotations

#: The wire-protocol version this binding implements. Mirrors PROTOCOL.md and
#: ``shared-protocol/schema/version.json``. Bump in lock-step with the schemas.
PROTOCOL_VERSION: str = "1.3.0"

#: Protocol versions this binding accepts on the wire (v1.3 still serves v1.0–v1.2).
SUPPORTED_VERSIONS: tuple[str, ...] = ("1.0.0", "1.1.0", "1.2.0", "1.3.0")

__all__ = ["PROTOCOL_VERSION", "SUPPORTED_VERSIONS"]
