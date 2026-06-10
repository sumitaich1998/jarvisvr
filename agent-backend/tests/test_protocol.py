"""Protocol envelope + payload model tests."""

from __future__ import annotations

import json

import pytest

from jarvis_backend import protocol
from jarvis_backend.protocol import (
    AgentSpeech,
    BadEnvelope,
    Envelope,
    HoloObject,
    Transform,
    make,
    parse_inbound,
)


def test_envelope_roundtrip():
    env = make(
        protocol.MsgType.AGENT_SPEECH,
        AgentSpeech(text="Hello", final=True),
        session="S1",
    )
    raw = env.to_json()
    data = json.loads(raw)
    # Envelope fields present and correct.
    assert data["v"] == protocol.PROTOCOL_VERSION
    assert data["type"] == "agent.speech"
    assert data["session"] == "S1"
    assert isinstance(data["id"], str) and len(data["id"]) >= 8
    assert isinstance(data["ts"], int) and data["ts"] > 0
    assert data["payload"]["text"] == "Hello"
    assert data["payload"]["final"] is True

    parsed = parse_inbound(raw)
    assert isinstance(parsed, Envelope)
    assert parsed.type == env.type
    assert parsed.session == "S1"
    assert parsed.payload["text"] == "Hello"


def test_session_omitted_when_none():
    env = make(protocol.MsgType.CLIENT_HELLO, {"device": "quest3"})
    data = json.loads(env.to_json())
    assert "session" not in data  # omitted on first hello
    assert "reply_to" not in data


def test_holo_object_defaults_and_transform():
    obj = HoloObject(widget_type="weather_orb", props={"city": "Tokyo"})
    assert obj.object_id  # auto-assigned uuid
    assert obj.transform.anchor == "world"
    assert obj.transform.position == [0.0, 0.0, 0.0]
    assert obj.transform.rotation == [0.0, 0.0, 0.0, 1.0]
    assert obj.transform.scale == [1.0, 1.0, 1.0]
    assert obj.ttl_ms == 0
    assert obj.interactable is True


def test_transform_vector_lengths_validated():
    with pytest.raises(Exception):
        Transform(position=[0.0, 1.0])  # too short
    with pytest.raises(Exception):
        Transform(rotation=[0.0, 0.0, 0.0])  # quaternion needs 4


def test_anchor_enum_in_object():
    obj = HoloObject(
        widget_type="timer",
        transform=Transform(anchor="head", billboard=True),
    )
    assert obj.transform.anchor == "head"
    assert obj.transform.billboard is True


def test_parse_inbound_rejects_garbage():
    with pytest.raises(BadEnvelope):
        parse_inbound("this is not json")
    with pytest.raises(BadEnvelope):
        parse_inbound(json.dumps({"v": "1.0.0", "payload": {}}))  # missing type


def test_unknown_payload_keys_ignored():
    # Forward-compatibility: extra payload keys are tolerated.
    env = parse_inbound(
        json.dumps(
            {
                "v": "1.0.0",
                "id": "x",
                "type": "user.text",
                "ts": 1,
                "session": "S",
                "payload": {"text": "hi", "future_field": 123},
            }
        )
    )
    assert env.payload["text"] == "hi"
    text = protocol.UserText.model_validate(env.payload)
    assert text.text == "hi"  # extra key dropped, no error
