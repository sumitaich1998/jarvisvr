"""Protocol envelope build/parse, ids/ts, and version compatibility edge cases."""

from __future__ import annotations

import pytest

from jarvis_backend import protocol
from jarvis_backend.protocol import (
    AgentSpeech,
    BadEnvelope,
    Envelope,
    HoloObject,
    Transform,
    is_compatible_version,
    make,
    new_id,
    now_ms,
    parse_inbound,
)


def test_ids_and_timestamps():
    assert new_id() != new_id()
    assert isinstance(now_ms(), int) and now_ms() > 0


def test_make_with_none_dict_and_model():
    assert make("x", None).payload == {}  # None payload -> {}
    assert make("x", {"a": 1}).payload == {"a": 1}
    env = make("agent.speech", AgentSpeech(text="hi", final=True), session="S", reply_to="r")
    assert env.payload["text"] == "hi" and env.session == "S" and env.reply_to == "r"
    assert env.v == protocol.PROTOCOL_VERSION and env.id and env.ts >= 0


def test_envelope_roundtrip():
    env = make("agent.thinking", {"stage": "planning"}, session="S")
    parsed = parse_inbound(env.to_json())
    assert parsed.type == "agent.thinking" and parsed.payload["stage"] == "planning"


def test_parse_inbound_bad_envelope():
    with pytest.raises(BadEnvelope):
        parse_inbound("{ not json")
    with pytest.raises(BadEnvelope):
        parse_inbound('{"no": "type field"}')


def test_is_compatible_version():
    assert is_compatible_version(protocol.PROTOCOL_VERSION) is True
    assert is_compatible_version("1.0.0") is True
    assert is_compatible_version("9.9.9") is False
    assert is_compatible_version(None) is False  # .split on None -> handled
    assert is_compatible_version(123) is False


def test_holo_object_validation_roundtrip():
    obj = HoloObject(object_id="o1", widget_type="panel", transform=Transform(), props={"title": "T", "body": "B"})
    again = HoloObject.model_validate(obj.model_dump())
    assert again.widget_type == "panel"
    assert len(again.transform.rotation) == 4  # quaternion default
