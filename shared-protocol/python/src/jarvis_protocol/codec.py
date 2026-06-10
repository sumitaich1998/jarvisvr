"""Encode / decode / construct / validate JarvisVR protocol messages."""

from __future__ import annotations

import json
import time
import uuid
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel

from .catalog import TYPE_TO_SCHEMA
from .models import Envelope, PAYLOAD_MODELS
from .schemas import envelope_validator, payload_validator
from .version import PROTOCOL_VERSION

#: Anything :func:`validate` / :func:`decode` accept.
MessageLike = Union[Envelope, Dict[str, Any], str, bytes, bytearray]


class ProtocolValidationError(ValueError):
    """Raised by :func:`validate` when a message violates the schemas."""

    def __init__(self, errors: List[str]):
        self.errors = list(errors)
        super().__init__("; ".join(self.errors) if self.errors else "invalid message")


def now_ms() -> int:
    """Current time as epoch milliseconds (sender clock)."""
    return int(time.time() * 1000)


def new_id() -> str:
    """A fresh UUID v4 string."""
    return str(uuid.uuid4())


def new_message(
    type: str,
    payload: Union[Dict[str, Any], BaseModel, None] = None,
    session: Optional[str] = None,
    *,
    reply_to: Optional[str] = None,
    id: Optional[str] = None,
    ts: Optional[int] = None,
) -> Envelope:
    """Build an :class:`Envelope` with a fresh uuid ``id`` and epoch-ms ``ts``.

    ``payload`` may be a dict or any pydantic payload model (it is dumped to a
    JSON-compatible dict, dropping ``None`` fields).
    """
    if isinstance(payload, BaseModel):
        payload = payload.model_dump(mode="json", exclude_none=True)
    elif payload is None:
        payload = {}
    return Envelope(
        v=PROTOCOL_VERSION,
        id=id or new_id(),
        type=type,
        ts=now_ms() if ts is None else ts,
        session=session,
        reply_to=reply_to,
        payload=payload,
    )


def to_dict(msg: MessageLike) -> Dict[str, Any]:
    """Normalize any accepted message form into a plain dict (wire shape)."""
    if isinstance(msg, Envelope):
        return msg.model_dump(mode="json", exclude_none=True)
    if isinstance(msg, (bytes, bytearray)):
        msg = msg.decode("utf-8")
    if isinstance(msg, str):
        return json.loads(msg)
    if isinstance(msg, dict):
        return msg
    raise TypeError(f"Unsupported message type: {type(msg)!r}")


def encode(msg: Union[Envelope, Dict[str, Any]]) -> str:
    """Serialize a message to a compact JSON text frame (``None`` fields omitted)."""
    if isinstance(msg, Envelope):
        return msg.model_dump_json(exclude_none=True)
    return json.dumps(msg, separators=(",", ":"))


def decode(data: Union[str, bytes, bytearray, Dict[str, Any]]) -> Envelope:
    """Parse a JSON text frame (or dict) into an :class:`Envelope`.

    Decoding is intentionally lenient (unknown envelope keys are dropped). Use
    :func:`validate` for strict schema conformance checks.
    """
    if isinstance(data, (bytes, bytearray)):
        data = data.decode("utf-8")
    obj = json.loads(data) if isinstance(data, str) else data
    return Envelope.model_validate(obj)


def parse_payload(type_name: str, payload: Dict[str, Any]) -> Optional[BaseModel]:
    """Parse a payload dict into its typed model, or ``None`` for unknown types."""
    model = PAYLOAD_MODELS.get(type_name)
    if model is None:
        return None
    return model.model_validate(payload)


def _fmt_path(error) -> str:
    path = "/".join(str(p) for p in error.path)
    return f"/{path}" if path else "<root>"


def iter_errors(msg: MessageLike, *, allow_unknown_types: bool = True) -> List[str]:
    """Return a list of human-readable schema violations (empty == valid).

    Validates the envelope, then the payload against the schema for its ``type``.
    Unknown ``type`` values pass by default (PROTOCOL.md §2: receivers ignore
    unknown types); set ``allow_unknown_types=False`` to flag them instead.
    """
    doc = to_dict(msg)
    errors: List[str] = []

    for err in envelope_validator().iter_errors(doc):
        errors.append(f"envelope {_fmt_path(err)}: {err.message}")

    type_name = doc.get("type")
    payload = doc.get("payload", {})
    if isinstance(type_name, str):
        validator = payload_validator(type_name)
        if validator is None:
            if type_name not in TYPE_TO_SCHEMA and not allow_unknown_types:
                errors.append(f"unknown message type: {type_name!r}")
        elif not isinstance(payload, dict):
            errors.append("payload: must be an object")
        else:
            for err in validator.iter_errors(payload):
                errors.append(f"{type_name} payload {_fmt_path(err)}: {err.message}")
    return errors


def validate(msg: MessageLike, *, allow_unknown_types: bool = True) -> Dict[str, Any]:
    """Validate a message against the JSON Schemas.

    Returns the normalized dict on success; raises
    :class:`ProtocolValidationError` (with ``.errors``) on any violation.
    """
    errors = iter_errors(msg, allow_unknown_types=allow_unknown_types)
    if errors:
        raise ProtocolValidationError(errors)
    return to_dict(msg)


def is_valid(msg: MessageLike, *, allow_unknown_types: bool = True) -> bool:
    """Return ``True`` if the message conforms to the schemas."""
    return not iter_errors(msg, allow_unknown_types=allow_unknown_types)


__all__ = [
    "MessageLike",
    "ProtocolValidationError",
    "now_ms",
    "new_id",
    "new_message",
    "to_dict",
    "encode",
    "decode",
    "parse_payload",
    "iter_errors",
    "validate",
    "is_valid",
]
