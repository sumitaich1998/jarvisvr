"""Round-trip: build -> encode -> decode -> equal, for every message type."""

from __future__ import annotations

import uuid

import pytest

import jarvis_protocol as jp
from jarvis_protocol import (
    Ack,
    AgentInfo,
    AgentSpeech,
    AgentThinking,
    Capabilities,
    ClientBargeIn,
    ClientHello,
    ClientInteraction,
    ClientScene,
    Heartbeat,
    HoloDestroy,
    HoloLayout,
    HoloObject,
    HoloUpdate,
    MessageType,
    Pose,
    ProtocolError,
    ServerHelloAck,
    TextInput,
    Transform,
    VoiceInfo,
)

CASES = [
    (MessageType.CLIENT_HELLO, ClientHello(
        device="quest3",
        app_version="0.1.0",
        capabilities=Capabilities(passthrough=True, hand_tracking=True, mic=True, speaker=True),
        locale="en-US",
    )),
    (MessageType.SERVER_HELLO_ACK, ServerHelloAck(
        session="S1",
        agent=AgentInfo(name="Jarvis", model="mock"),
        tools=["get_weather", "start_timer"],
        voice=VoiceInfo(tts=True, wake_word="jarvis"),
    )),
    (MessageType.USER_VOICE_TRANSCRIPT, TextInput(text="weather in tokyo", confidence=0.97)),
    (MessageType.USER_TEXT, TextInput(text="start a 5 minute timer")),
    (MessageType.AGENT_THINKING, AgentThinking(stage="tool_call", tool="get_weather", label="Calling get_weather")),
    (MessageType.AGENT_SPEECH, AgentSpeech(text="Here's Tokyo.", final=True, emotion="neutral")),
    (MessageType.HOLO_SPAWN, HoloObject(
        object_id="O1",
        widget_type="weather_orb",
        transform=Transform(anchor="head", position=[0.3, 0.0, 0.8], rotation=[0, 0, 0, 1], scale=[1, 1, 1], billboard=True),
        props={"city": "Tokyo", "temp_c": 18, "condition": "clouds"},
        interactable=True,
        interactions=["grab", "tap"],
        ttl_ms=0,
    )),
    (MessageType.HOLO_UPDATE, HoloUpdate(object_id="O1", props={"temp_c": 19})),
    (MessageType.HOLO_DESTROY, HoloDestroy(object_id="O1", fade_ms=300)),
    (MessageType.HOLO_LAYOUT, HoloLayout(arrangement="arc", anchor="head", objects=["O1", "O2"], spacing=0.25)),
    (MessageType.CLIENT_INTERACTION, ClientInteraction(
        object_id="O2", widget_type="timer", action="tap", element="pause_button", value={"pressed": True}, hand="right",
    )),
    (MessageType.CLIENT_SCENE, ClientScene(head=Pose(position=[0, 1.6, 0], rotation=[0, 0, 0, 1]))),
    (MessageType.CLIENT_HEARTBEAT, Heartbeat()),
    (MessageType.SERVER_HEARTBEAT, Heartbeat()),
    (MessageType.SERVER_ERROR, ProtocolError(code="internal", message="boom", fatal=False)),
    (MessageType.CLIENT_BARGE_IN, ClientBargeIn(reason="user_speech")),
]


@pytest.mark.parametrize("type_name,payload", CASES, ids=[c[0] for c in CASES])
def test_roundtrip_equal(type_name, payload):
    msg = jp.new_message(type_name, payload, session="S")
    wire = jp.encode(msg)
    assert isinstance(wire, str)
    decoded = jp.decode(wire)
    assert decoded.type == type_name
    assert jp.to_dict(decoded) == jp.to_dict(msg)


@pytest.mark.parametrize("type_name,payload", CASES, ids=[c[0] for c in CASES])
def test_each_case_validates(type_name, payload):
    msg = jp.new_message(type_name, payload, session="S")
    # Raises on failure; also exercise strict-type mode (all are known types).
    jp.validate(msg, allow_unknown_types=False)
    assert jp.is_valid(msg)


def test_new_message_id_is_uuid_and_ts_is_epoch_ms():
    before = jp.now_ms()
    msg = jp.new_message(MessageType.AGENT_SPEECH, AgentSpeech(text="hi"))
    after = jp.now_ms()
    # id parses as a UUID
    uuid.UUID(msg.id)
    # ts is epoch-ms within the call window
    assert before <= msg.ts <= after
    assert msg.v == jp.PROTOCOL_VERSION


def test_first_hello_omits_session_and_reply_to():
    msg = jp.new_message(MessageType.CLIENT_HELLO, ClientHello(device="quest3"))
    wire = jp.encode(msg)
    assert '"session"' not in wire
    assert '"reply_to"' not in wire
    assert jp.is_valid(wire)


def test_client_ack_carries_reply_to():
    msg = jp.new_message(MessageType.CLIENT_ACK, Ack(), session="S", reply_to="b3")
    doc = jp.to_dict(msg)
    assert doc["reply_to"] == "b3"
    assert doc["payload"] == {}
    jp.validate(msg)


def test_parse_payload_returns_typed_model():
    msg = jp.new_message(MessageType.AGENT_SPEECH, AgentSpeech(text="hi", final=True), session="S")
    model = jp.parse_payload(msg.type, msg.payload)
    assert isinstance(model, AgentSpeech)
    assert model.text == "hi" and model.final is True
    assert jp.parse_payload("totally.unknown", {}) is None


def test_forward_compatible_extra_payload_keys_preserved():
    raw = '{"v":"1.0.0","id":"x","type":"agent.speech","ts":1,"session":"S","payload":{"text":"hi","future_field":42}}'
    decoded = jp.decode(raw)
    assert decoded.payload["future_field"] == 42


def test_barge_in_roundtrip_and_empty_payload(): 
    # With a reason.
    msg = jp.new_message(MessageType.CLIENT_BARGE_IN, ClientBargeIn(reason="user_speech"), session="S")
    jp.validate(msg, allow_unknown_types=False)  # raises on failure
    model = jp.parse_payload(msg.type, msg.payload)
    assert isinstance(model, ClientBargeIn) and model.reason == "user_speech"

    # reason is optional: an empty barge_in (idempotent no-op signal) is valid too.
    empty = jp.new_message(MessageType.CLIENT_BARGE_IN, ClientBargeIn(), session="S")
    assert empty.payload == {}
    assert jp.is_valid(empty, allow_unknown_types=False)
    assert jp.is_valid(
        {"v": "1.1.0", "id": "x", "type": "client.barge_in", "ts": 1, "session": "S", "payload": {}},
        allow_unknown_types=False,
    )
