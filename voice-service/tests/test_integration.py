"""End-to-end integration: fake-WebSocket bridge round-trips with mock engines.

Covers the full contract loop without any real audio, models, or network:
  * speech-in (`agent.speech` / `agent.observation`) -> TTS spoken,
  * transcript-out (pipeline STT -> `user.voice_transcript`),
  * barge-in signal (`client.barge_in`),
  * ambient perception emission (`perception.audio_scene` / `perception.audio_event`),
  * `perception.request` start/stop control.
"""

from __future__ import annotations

import asyncio

from jarvis_voice import audio, protocol
from jarvis_voice.bridge import VoiceBridge, build_bridge
from jarvis_voice.protocol import Envelope

from conftest import FakeSpeaker, FakeWebSocket, fast_config


def _types(ws):
    return [Envelope.from_json(s).type for s in ws.sent]


def test_full_session_round_trip():
    """A scripted server session: handshake, speech, observation, perception."""
    spk = FakeSpeaker()
    incoming = [
        Envelope.build(protocol.SERVER_HELLO_ACK, {"session": "SES"}).to_json(),
        Envelope.build(protocol.AGENT_THINKING, {"stage": "planning"}).to_json(),
        Envelope.build(protocol.AGENT_SPEECH, {"text": "Hello there.", "final": True}).to_json(),
        Envelope.build(protocol.AGENT_OBSERVATION, {"text": "I hear a doorbell."}).to_json(),
        Envelope.build(
            protocol.PERCEPTION_REQUEST, {"stream": "ambient_audio", "action": "start"}
        ).to_json(),
        Envelope.build("holo.spawn", {"object_id": "O1"}).to_json(),  # unknown -> ignored
    ]
    ws = FakeWebSocket(incoming)
    bridge = VoiceBridge(fast_config(), pipeline=None, speaker=spk)

    asyncio.run(bridge.run(ws))

    sent = _types(ws)
    assert protocol.CLIENT_HELLO in sent
    assert protocol.CLIENT_BYE in sent
    assert protocol.PERCEPTION_STATE in sent          # replied to perception.request
    assert bridge.session == "SES"
    assert bridge._ambient_active is True
    assert spk.spoken == ["Hello there.", "I hear a doorbell."]


def test_transcript_out_and_barge_in_signal():
    """Pipeline (mock engines) -> bridge outbox: transcript + barge-in envelopes."""
    cfg = fast_config()
    bridge = build_bridge(cfg)
    bridge.session = "S"

    # Wire pipeline events to the outbox exactly as capture_loop does.
    bridge.pipeline.cb.on_transcript = lambda res: bridge._enqueue(
        protocol.voice_transcript(res.text, res.confidence, session=bridge.session)
    )
    bridge.pipeline.cb.on_barge_in = lambda: bridge._enqueue(
        protocol.client_barge_in(session=bridge.session)
    )

    loud = audio.tone(300.0, cfg.frame_ms, amplitude=0.6)
    quiet = audio.silence(cfg.frame_ms)

    # Wake (energy) -> speak -> silence endpoint -> final transcript.
    for _ in range(6):
        bridge.pipeline.process_frame(loud)
    for _ in range(cfg.frames_for_ms(cfg.silence_ms) + 3):
        bridge.pipeline.process_frame(quiet)

    # Now simulate TTS playing and the user barging in.
    bridge.pipeline._speaking = True
    for _ in range(cfg.barge_in_min_frames + 2):
        bridge.pipeline.process_frame(loud)

    queued = []
    while not bridge._outbox.empty():
        queued.append(bridge._outbox.get_nowait())
    types = {e.type for e in queued}
    assert protocol.USER_VOICE_TRANSCRIPT in types
    assert protocol.CLIENT_BARGE_IN in types

    transcript = next(e for e in queued if e.type == protocol.USER_VOICE_TRANSCRIPT)
    assert transcript.payload["text"] == cfg.mock_transcript
    assert transcript.session == "S"


def test_ambient_perception_emission_via_bridge():
    """Ambient frames flowing through the bridge produce audio_scene + audio_event."""
    cfg = fast_config()
    bridge = build_bridge(cfg)
    bridge.start_ambient()

    loud = audio.tone(300.0, cfg.frame_ms, amplitude=0.6)
    for _ in range(cfg.frames_for_ms(cfg.ambient_window_ms) + 1):
        bridge._ambient.process_frame(loud)

    queued = []
    while not bridge._outbox.empty():
        queued.append(bridge._outbox.get_nowait())
    types = {e.type for e in queued}
    assert protocol.PERCEPTION_AUDIO_SCENE in types
    assert protocol.PERCEPTION_AUDIO_EVENT in types


def test_perception_request_stop_after_start():
    bridge = VoiceBridge(fast_config(), pipeline=None, speaker=FakeSpeaker())
    ws = FakeWebSocket()
    asyncio.run(bridge.handle_raw(
        ws, Envelope.build(protocol.PERCEPTION_REQUEST,
                           {"stream": "ambient_audio", "action": "start"}).to_json()))
    assert bridge._ambient_active is True
    asyncio.run(bridge.handle_raw(
        ws, Envelope.build(protocol.PERCEPTION_REQUEST,
                           {"stream": "ambient_audio", "action": "stop"}).to_json()))
    assert bridge._ambient_active is False
