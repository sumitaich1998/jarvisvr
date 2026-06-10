"""Coverage for protocol envelope edge cases + remaining builders."""

from __future__ import annotations

import pytest

from jarvis_voice import protocol
from jarvis_voice.protocol import Envelope, ProtocolError


def test_to_dict_includes_reply_to():
    env = Envelope.build(protocol.CLIENT_ACK, {}, reply_to="abc")
    data = env.to_dict()
    assert data["reply_to"] == "abc"


def test_from_dict_rejects_non_dict():
    with pytest.raises(ProtocolError):
        Envelope.from_dict(["not", "a", "dict"])  # type: ignore[arg-type]


def test_from_dict_payload_none_becomes_empty():
    env = Envelope.from_dict(
        {"v": "1.1.0", "id": "a", "type": "x", "ts": 1, "payload": None}
    )
    assert env.payload == {}


def test_from_dict_rejects_non_object_payload():
    with pytest.raises(ProtocolError):
        Envelope.from_dict({"v": "1.1.0", "id": "a", "type": "x", "ts": 1, "payload": 5})


def test_is_version_compatible_handles_bad_version():
    # v is not a string -> AttributeError caught -> False
    env = Envelope(type="x", v=None)  # type: ignore[arg-type]
    assert env.is_version_compatible() is False


def test_client_hello_extra_capabilities_merge():
    env = protocol.client_hello(extra_capabilities={"custom": True})
    assert env.payload["capabilities"]["custom"] is True


def test_client_heartbeat_and_bye():
    hb = protocol.client_heartbeat(session="S")
    assert hb.type == protocol.CLIENT_HEARTBEAT and hb.session == "S"
    bye = protocol.client_bye(session="S")
    assert bye.type == protocol.CLIENT_BYE and bye.session == "S"


def test_voice_partial_builder():
    env = protocol.voice_partial("hel", 0.3, session="S")
    assert env.type == protocol.USER_VOICE_PARTIAL
    assert env.payload["text"] == "hel"
    assert env.payload["confidence"] == pytest.approx(0.3)


def test_client_error_builder():
    env = protocol.client_error("bad_envelope", "nope", fatal=True, session="S")
    assert env.payload["code"] == "bad_envelope"
    assert env.payload["fatal"] is True


def test_audio_event_explicit_ts():
    env = protocol.audio_event("alarm", 0.9, -10.0, ts=12345)
    assert env.payload["ts"] == 12345


def test_perception_state_with_battery():
    env = protocol.perception_state(ambient_audio_active=True, battery=0.5)
    assert env.payload["battery"] == 0.5
    assert env.payload["ambient_audio"]["active"] is True


def test_now_ms_and_new_id():
    assert isinstance(protocol.now_ms(), int)
    assert protocol.now_ms() > 0
    assert protocol.new_id() != protocol.new_id()
