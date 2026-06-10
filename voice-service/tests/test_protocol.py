"""Envelope build/parse + protocol conformance."""

from __future__ import annotations

import json

import pytest

from jarvis_voice import protocol
from jarvis_voice.protocol import Envelope, ProtocolError


def test_build_sets_envelope_fields():
    env = Envelope.build(protocol.USER_TEXT, {"text": "hi"})
    assert env.v == protocol.PROTOCOL_VERSION
    assert env.type == protocol.USER_TEXT
    assert env.payload == {"text": "hi"}
    assert isinstance(env.id, str) and len(env.id) >= 8
    assert isinstance(env.ts, int) and env.ts > 0


def test_json_round_trip_preserves_everything():
    env = Envelope.build(
        protocol.USER_VOICE_TRANSCRIPT, {"text": "weather", "confidence": 0.9}, session="S1"
    )
    raw = env.to_json()
    back = Envelope.from_json(raw)
    assert back.type == env.type
    assert back.payload == env.payload
    assert back.session == "S1"
    assert back.v == env.v
    assert back.id == env.id
    assert back.ts == env.ts


def test_first_hello_omits_session():
    env = protocol.client_hello()
    data = json.loads(env.to_json())
    assert "session" not in data  # spec: omitted on first hello
    assert data["type"] == protocol.CLIENT_HELLO


def test_hello_advertises_mic_and_speaker():
    env = protocol.client_hello(mic=True, speaker=True)
    caps = env.payload["capabilities"]
    assert caps["mic"] is True
    assert caps["speaker"] is True
    assert env.payload["protocol_version"] == protocol.PROTOCOL_VERSION


def test_voice_transcript_and_partial_builders():
    final = protocol.voice_transcript("hello", 0.8, session="S")
    assert final.type == protocol.USER_VOICE_TRANSCRIPT
    assert final.payload["text"] == "hello"
    assert final.payload["confidence"] == pytest.approx(0.8)
    assert final.session == "S"

    partial = protocol.voice_partial("hel", session="S")
    assert partial.type == protocol.USER_VOICE_PARTIAL
    assert partial.payload["text"] == "hel"


def test_missing_required_key_raises():
    with pytest.raises(ProtocolError):
        Envelope.from_dict({"v": "1.0.0", "type": "x", "ts": 1})  # no id


def test_invalid_json_raises_protocol_error():
    with pytest.raises(ProtocolError):
        Envelope.from_json("definitely not json {")


def test_unknown_type_still_parses():
    raw = json.dumps(
        {"v": "1.0.0", "id": "a", "type": "holo.spawn", "ts": 1, "payload": {"object_id": "O1"}}
    )
    env = Envelope.from_json(raw)
    assert env.type == "holo.spawn"
    assert env.payload["object_id"] == "O1"


def test_payload_defaults_to_empty_dict():
    raw = json.dumps({"v": "1.0.0", "id": "a", "type": "server.heartbeat", "ts": 1})
    env = Envelope.from_json(raw)
    assert env.payload == {}


@pytest.mark.parametrize(
    "version,expected",
    [("1.0.0", True), ("1.5.2", True), ("2.0.0", False)],
)
def test_version_major_compat(version, expected):
    env = Envelope(type="x", v=version)
    assert env.is_version_compatible() is expected


def test_text_property():
    env = protocol.voice_transcript("spoken words")
    assert env.text == "spoken words"
    assert Envelope.build("agent.speech", {}).text is None


# --- v1.1 Multimodal Perception --------------------------------------------

def test_protocol_version_is_1_1():
    assert protocol.PROTOCOL_VERSION == "1.1.0"


def test_hello_advertises_ambient_audio():
    env = protocol.client_hello(mic=True, speaker=True, ambient_audio=True)
    caps = env.payload["capabilities"]
    assert caps["ambient_audio"] is True
    assert caps["mic"] is True and caps["speaker"] is True
    assert env.payload["protocol_version"] == "1.1.0"


def test_audio_scene_builder_round_trips():
    env = protocol.audio_scene(
        "overheard chatter", "other",
        [{"label": "music", "confidence": 0.6}], -30.0, 4000, session="S",
    )
    assert env.type == protocol.PERCEPTION_AUDIO_SCENE
    assert env.payload["speaker"] == "other"
    assert env.payload["window_ms"] == 4000
    assert env.payload["sounds"][0]["label"] == "music"
    assert env.session == "S"
    back = Envelope.from_json(env.to_json())
    assert back.payload["ambient_transcript"] == "overheard chatter"


def test_audio_event_builder_has_ts_and_label():
    env = protocol.audio_event("doorbell", 0.82, -22.0)
    assert env.type == protocol.PERCEPTION_AUDIO_EVENT
    assert env.payload["label"] == "doorbell"
    assert env.payload["confidence"] == pytest.approx(0.82)
    assert env.payload["loudness_db"] == pytest.approx(-22.0)
    assert "ts" in env.payload


def test_perception_state_builder():
    env = protocol.perception_state(ambient_audio_active=True)
    assert env.type == protocol.PERCEPTION_STATE
    assert env.payload["ambient_audio"]["active"] is True
    assert env.payload["vision"]["active"] is False


def test_perception_request_parses():
    raw = protocol.Envelope.build(
        protocol.PERCEPTION_REQUEST, {"stream": "ambient_audio", "action": "start"}
    ).to_json()
    env = Envelope.from_json(raw)
    assert env.type == protocol.PERCEPTION_REQUEST
    assert env.payload["action"] == "start"


def test_client_barge_in_builder():
    env = protocol.client_barge_in(session="S")
    assert env.type == protocol.CLIENT_BARGE_IN
    assert env.payload["reason"] == "user_speech"
    assert env.session == "S"
