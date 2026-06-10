"""Targeted branch coverage for codec + schemas internals (encode/decode/new_message,
to_dict edge cases, iter_errors edge branches, schema-dir resolution)."""

from __future__ import annotations

import pathlib

import pytest

import jarvis_protocol as jp
from jarvis_protocol import AgentSpeech, codec, schemas


# ---- new_message: every payload form + explicit id/ts ----------------------

def test_new_message_payload_none_and_default():
    assert jp.new_message("client.heartbeat", None, "S").payload == {}
    assert jp.new_message("client.heartbeat").payload == {}  # default None branch


def test_new_message_payload_dict_with_explicit_id_ts():
    m = jp.new_message("agent.speech", {"text": "hi"}, "S", id="fixed-id", ts=123456)
    assert m.id == "fixed-id" and m.ts == 123456 and m.session == "S"


def test_new_message_payload_model_branch():
    m = jp.new_message("agent.speech", AgentSpeech(text="hi", final=True))
    assert m.payload == {"text": "hi", "final": True}
    # auto id is a uuid, auto ts is recent epoch-ms
    assert len(m.id) == 36 and m.ts > 0


# ---- to_dict: bytes / bytearray / unsupported ------------------------------

_RAW = '{"v":"1.3.0","id":"a","type":"client.ack","ts":1,"session":"S","payload":{}}'


def test_to_dict_bytes_and_bytearray():
    assert jp.to_dict(_RAW.encode("utf-8"))["type"] == "client.ack"
    assert jp.to_dict(bytearray(_RAW.encode("utf-8")))["type"] == "client.ack"


def test_to_dict_unsupported_type_raises():
    with pytest.raises(TypeError):
        jp.to_dict(12345)  # not Envelope/bytes/str/dict


# ---- encode / decode branches ----------------------------------------------

def test_encode_plain_dict_branch():
    assert jp.encode({"a": 1, "b": 2}) == '{"a":1,"b":2}'


def test_decode_bytes_and_dict_branches():
    assert jp.decode(_RAW.encode("utf-8")).type == "client.ack"
    assert jp.decode({"v": "1.3.0", "id": "a", "type": "client.ack", "ts": 1, "payload": {}}).type == "client.ack"


# ---- iter_errors edge branches ---------------------------------------------

def test_iter_errors_type_missing_skips_payload_validation():
    # No 'type' -> type_name is not a str -> payload branch skipped (envelope still flags it).
    errors = jp.iter_errors({"v": "1.3.0", "id": "a", "ts": 1, "payload": {}})
    assert any("type" in e for e in errors)


def test_iter_errors_payload_not_object():
    # Known type but payload is a list, not an object.
    errors = jp.iter_errors({"v": "1.3.0", "id": "a", "type": "agent.speech", "ts": 1, "payload": [1, 2]})
    assert any("must be an object" in e for e in errors)


def test_iter_errors_root_vs_nested_paths():
    # Missing required field -> root path ("<root>" in _fmt_path).
    root_errs = jp.iter_errors({"v": "1.3.0", "id": "a", "type": "agent.speech", "ts": 1, "payload": {}})
    assert any("agent.speech payload" in e for e in root_errs)
    # Nested wrong type -> a '/'-joined path.
    nested = {
        "v": "1.3.0", "id": "a", "type": "holo.spawn", "ts": 1,
        "payload": {"object_id": "O1", "widget_type": "panel",
                    "transform": {"anchor": "world", "position": [0, 0], "rotation": [0, 0, 0, 1], "scale": [1, 1, 1]}},
    }
    nested_errs = jp.iter_errors(nested)
    assert any("/transform/position" in e for e in nested_errs)


# ---- schemas: schema-dir resolution + payload_validator --------------------

def test_find_schema_dir_env_branch(monkeypatch):
    monkeypatch.setenv("JARVIS_PROTOCOL_SCHEMA_DIR", str(jp.SCHEMA_DIR))
    assert schemas._find_schema_dir() == jp.SCHEMA_DIR


def test_find_schema_dir_not_found_raises(monkeypatch):
    monkeypatch.delenv("JARVIS_PROTOCOL_SCHEMA_DIR", raising=False)
    monkeypatch.setattr(pathlib.Path, "is_file", lambda self: False)
    with pytest.raises(RuntimeError):
        schemas._find_schema_dir()


def test_payload_validator_unknown_type_returns_none():
    assert schemas.payload_validator("totally.unknown") is None


def test_protocol_validation_error_empty_message():
    # The ProtocolValidationError "invalid message" fallback (empty error list).
    err = codec.ProtocolValidationError([])
    assert str(err) == "invalid message" and err.errors == []
    err2 = codec.ProtocolValidationError(["a", "b"])
    assert "a" in str(err2) and "b" in str(err2)
