"""Bridge ↔ protocol mapping, exercised against a fake websocket.

These tests drive the async bridge via ``asyncio.run`` so they don't depend on
any pytest-asyncio behavior.
"""

from __future__ import annotations

import asyncio

from jarvis_voice import audio, protocol
from jarvis_voice.bridge import VoiceBridge
from jarvis_voice.protocol import Envelope

from conftest import FakeSpeaker, FakeWebSocket, fast_config


def _bridge(speaker=None):
    return VoiceBridge(fast_config(), pipeline=None, speaker=speaker or FakeSpeaker())


def test_hello_sends_mic_and_speaker_capabilities():
    bridge = _bridge()
    ws = FakeWebSocket()
    asyncio.run(bridge.send_hello(ws))

    assert len(ws.sent) == 1
    env = Envelope.from_json(ws.sent[0])
    assert env.type == protocol.CLIENT_HELLO
    assert env.payload["capabilities"]["mic"] is True
    assert env.payload["capabilities"]["speaker"] is True
    assert env.session is None  # first hello carries no session


def test_send_transcript_emits_user_voice_transcript():
    bridge = _bridge()
    bridge.session = "S42"
    ws = FakeWebSocket()
    asyncio.run(bridge.send_transcript(ws, "show me the weather in tokyo", 0.93))

    env = Envelope.from_json(ws.sent[0])
    assert env.type == protocol.USER_VOICE_TRANSCRIPT
    assert env.payload["text"] == "show me the weather in tokyo"
    assert env.payload["confidence"] == 0.93
    assert env.session == "S42"


def test_send_partial_emits_user_voice_partial():
    bridge = _bridge()
    ws = FakeWebSocket()
    asyncio.run(bridge.send_transcript(ws, "show me", 0.0, final=False))
    env = Envelope.from_json(ws.sent[0])
    assert env.type == protocol.USER_VOICE_PARTIAL
    assert env.payload["text"] == "show me"


def test_agent_speech_is_spoken():
    spk = FakeSpeaker()
    bridge = _bridge(spk)
    ws = FakeWebSocket()
    raw = Envelope.build(protocol.AGENT_SPEECH, {"text": "Here is Tokyo.", "final": True}).to_json()

    asyncio.run(bridge.handle_raw(ws, raw))
    assert spk.spoken == ["Here is Tokyo."]


def test_hello_ack_sets_session():
    bridge = _bridge()
    ws = FakeWebSocket()
    raw = Envelope.build(
        protocol.SERVER_HELLO_ACK,
        {"session": "S123", "agent": {"name": "Jarvis", "model": "mock"}},
    ).to_json()
    asyncio.run(bridge.handle_raw(ws, raw))
    assert bridge.session == "S123"


def test_unknown_type_is_ignored_no_crash():
    bridge = _bridge()
    ws = FakeWebSocket()
    raw = Envelope.build("holo.spawn", {"object_id": "O1", "widget_type": "weather_orb"}).to_json()
    env = asyncio.run(bridge.handle_raw(ws, raw))
    assert env is not None and env.type == "holo.spawn"
    assert ws.sent == []  # nothing sent in response


def test_bad_envelope_sends_client_error():
    bridge = _bridge()
    ws = FakeWebSocket()
    result = asyncio.run(bridge.handle_raw(ws, "not-json{"))
    assert result is None
    assert len(ws.sent) == 1
    err = Envelope.from_json(ws.sent[0])
    assert err.type == protocol.CLIENT_ERROR
    assert err.payload["code"] == "bad_envelope"


def test_recv_loop_processes_a_session(monkeypatch):
    """Full inbound round-trip over a fake socket: hello_ack → speech → unknown."""
    spk = FakeSpeaker()
    bridge = _bridge(spk)
    incoming = [
        Envelope.build(protocol.SERVER_HELLO_ACK, {"session": "S9"}).to_json(),
        Envelope.build(protocol.AGENT_THINKING, {"stage": "planning"}).to_json(),
        Envelope.build(protocol.AGENT_SPEECH, {"text": "On it.", "final": True}).to_json(),
        Envelope.build("holo.spawn", {"object_id": "O1"}).to_json(),  # ignored
    ]
    ws = FakeWebSocket(incoming)

    asyncio.run(bridge.recv_loop(ws))

    assert bridge.session == "S9"
    assert spk.spoken == ["On it."]


# --- v1.1: ambient perception + observation --------------------------------

def test_hello_advertises_ambient_audio():
    bridge = _bridge()
    ws = FakeWebSocket()
    asyncio.run(bridge.send_hello(ws))
    env = Envelope.from_json(ws.sent[0])
    assert env.payload["capabilities"]["ambient_audio"] is True


def test_agent_observation_is_spoken():
    spk = FakeSpeaker()
    bridge = _bridge(spk)
    ws = FakeWebSocket()
    raw = Envelope.build(
        protocol.AGENT_OBSERVATION, {"text": "I see a coffee mug.", "final": True}
    ).to_json()
    asyncio.run(bridge.handle_raw(ws, raw))
    assert spk.spoken == ["I see a coffee mug."]


def test_perception_request_starts_and_stops_ambient():
    bridge = _bridge()
    ws = FakeWebSocket()
    start = Envelope.build(
        protocol.PERCEPTION_REQUEST, {"stream": "ambient_audio", "action": "start"}
    ).to_json()
    asyncio.run(bridge.handle_raw(ws, start))
    assert bridge._ambient_active is True
    states = [Envelope.from_json(s) for s in ws.sent]
    assert any(
        e.type == protocol.PERCEPTION_STATE and e.payload["ambient_audio"]["active"] is True
        for e in states
    )

    stop = Envelope.build(
        protocol.PERCEPTION_REQUEST, {"stream": "ambient_audio", "action": "stop"}
    ).to_json()
    asyncio.run(bridge.handle_raw(ws, stop))
    assert bridge._ambient_active is False


def test_perception_request_other_stream_ignored():
    bridge = _bridge()
    ws = FakeWebSocket()
    raw = Envelope.build(
        protocol.PERCEPTION_REQUEST, {"stream": "vision", "action": "start"}
    ).to_json()
    asyncio.run(bridge.handle_raw(ws, raw))
    assert bridge._ambient_active is False
    assert ws.sent == []  # voice-service doesn't own the vision stream


def test_ambient_emits_audio_scene_and_event_to_outbox():
    bridge = _bridge()
    bridge.start_ambient()
    cfg = bridge.config
    frame = audio.tone(300.0, cfg.frame_ms, sample_rate=cfg.sample_rate, amplitude=0.6)
    for _ in range(cfg.frames_for_ms(cfg.ambient_window_ms) + 1):
        bridge._ambient.process_frame(frame)

    envs = []
    while not bridge._outbox.empty():
        envs.append(bridge._outbox.get_nowait())
    types = {e.type for e in envs}
    assert protocol.PERCEPTION_AUDIO_SCENE in types
    assert protocol.PERCEPTION_AUDIO_EVENT in types


def test_ambient_disabled_request_is_noop():
    bridge = VoiceBridge(fast_config(ambient_mode="off"), pipeline=None, speaker=FakeSpeaker())
    ws = FakeWebSocket()
    raw = Envelope.build(
        protocol.PERCEPTION_REQUEST, {"stream": "ambient_audio", "action": "start"}
    ).to_json()
    asyncio.run(bridge.handle_raw(ws, raw))
    assert bridge._ambient_active is False
    states = [Envelope.from_json(s) for s in ws.sent]
    assert any(
        e.type == protocol.PERCEPTION_STATE and e.payload["ambient_audio"]["active"] is False
        for e in states
    )
