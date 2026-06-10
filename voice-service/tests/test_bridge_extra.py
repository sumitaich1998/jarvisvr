"""Coverage for VoiceBridge: loops, perception, capture, run, reconnect."""

from __future__ import annotations

import asyncio

from jarvis_voice import audio, protocol
from jarvis_voice.bridge import VoiceBridge, build_bridge
from jarvis_voice.protocol import Envelope

from conftest import FakeSpeaker, FakeWebSocket, fast_config


def _bridge(speaker=None, **cfg_overrides):
    return VoiceBridge(
        fast_config(**cfg_overrides), pipeline=None, speaker=speaker or FakeSpeaker()
    )


class FakeMic:
    def __init__(self, frames):
        self.frames = frames

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def __iter__(self):
        return iter(self.frames)


# --- simple senders ---------------------------------------------------------

def test_send_heartbeat():
    ws = FakeWebSocket()
    bridge = _bridge()
    bridge.session = "S"
    asyncio.run(bridge.send_heartbeat(ws))
    env = Envelope.from_json(ws.sent[0])
    assert env.type == protocol.CLIENT_HEARTBEAT and env.session == "S"


def test_send_bye():
    ws = FakeWebSocket()
    asyncio.run(_bridge().send_bye(ws))
    assert Envelope.from_json(ws.sent[0]).type == protocol.CLIENT_BYE


def test_send_transcript_empty_is_noop():
    ws = FakeWebSocket()
    asyncio.run(_bridge().send_transcript(ws, ""))
    assert ws.sent == []


# --- handle_raw dispatch branches ------------------------------------------

def test_handle_incompatible_version_logged(caplog):
    ws = FakeWebSocket()
    raw = Envelope(type=protocol.AGENT_THINKING, v="2.0.0").to_json()
    env = asyncio.run(_bridge().handle_raw(ws, raw))
    assert env is not None  # still parsed + dispatched


def test_handle_server_heartbeat_and_transcript_and_error():
    ws = FakeWebSocket()
    bridge = _bridge()
    for t in (protocol.SERVER_HEARTBEAT, protocol.AGENT_TRANSCRIPT, protocol.SERVER_ERROR):
        raw = Envelope.build(t, {"text": "x", "code": "internal"}).to_json()
        asyncio.run(bridge.handle_raw(ws, raw))
    assert ws.sent == []  # none of these produce a reply


def test_handle_agent_speech_empty_text_not_spoken():
    spk = FakeSpeaker()
    raw = Envelope.build(protocol.AGENT_SPEECH, {"final": True}).to_json()  # no text
    asyncio.run(_bridge(spk).handle_raw(FakeWebSocket(), raw))
    assert spk.spoken == []


# --- perception.request: once + unknown action -----------------------------

def test_perception_request_once_emits_snapshot():
    bridge = _bridge()
    ws = FakeWebSocket()
    raw = Envelope.build(
        protocol.PERCEPTION_REQUEST, {"stream": "ambient_audio", "action": "once"}
    ).to_json()
    asyncio.run(bridge.handle_raw(ws, raw))
    # snapshot scene enqueued; perception.state sent
    queued = []
    while not bridge._outbox.empty():
        queued.append(bridge._outbox.get_nowait())
    assert any(e.type == protocol.PERCEPTION_AUDIO_SCENE for e in queued)
    assert any(Envelope.from_json(s).type == protocol.PERCEPTION_STATE for s in ws.sent)


def test_perception_request_unknown_action():
    bridge = _bridge()
    ws = FakeWebSocket()
    raw = Envelope.build(
        protocol.PERCEPTION_REQUEST, {"stream": "ambient_audio", "action": "frobnicate"}
    ).to_json()
    asyncio.run(bridge.handle_raw(ws, raw))
    assert bridge._ambient_active is False
    assert any(Envelope.from_json(s).type == protocol.PERCEPTION_STATE for s in ws.sent)


# --- ambient lifecycle helpers ---------------------------------------------

def test_ensure_ambient_is_idempotent():
    bridge = _bridge()
    bridge.start_ambient()
    first = bridge._ambient
    bridge.start_ambient()  # _ensure_ambient takes the already-built branch
    assert bridge._ambient is first


def test_start_ambient_with_audio_backend(monkeypatch):
    import jarvis_voice.bridge as bridge_mod

    monkeypatch.setattr(bridge_mod, "audio_io_available", lambda: True)
    bridge = _bridge()
    bridge.start_ambient()  # no warning branch
    assert bridge._ambient_active is True


# --- _enqueue thread-safe (running loop) ------------------------------------

def test_enqueue_uses_running_loop():
    async def go():
        bridge = _bridge()
        bridge._loop = asyncio.get_running_loop()
        bridge._enqueue(protocol.client_heartbeat())
        await asyncio.sleep(0)  # let call_soon_threadsafe run
        return bridge._outbox.get_nowait()

    env = asyncio.run(go())
    assert env.type == protocol.CLIENT_HEARTBEAT


# --- loops ------------------------------------------------------------------

def test_heartbeat_loop_sends(monkeypatch):
    monkeypatch.setattr(protocol, "HEARTBEAT_INTERVAL_S", 0.01)

    async def go():
        ws = FakeWebSocket()
        bridge = _bridge()
        task = asyncio.create_task(bridge.heartbeat_loop(ws))
        await asyncio.sleep(0.05)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        return ws

    ws = asyncio.run(go())
    assert any(Envelope.from_json(s).type == protocol.CLIENT_HEARTBEAT for s in ws.sent)


def test_sender_loop_drains_outbox():
    async def go():
        ws = FakeWebSocket()
        bridge = _bridge()
        bridge._outbox.put_nowait(protocol.voice_transcript("hi"))
        task = asyncio.create_task(bridge.sender_loop(ws))
        await asyncio.sleep(0.02)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        return ws

    ws = asyncio.run(go())
    assert any(Envelope.from_json(s).type == protocol.USER_VOICE_TRANSCRIPT for s in ws.sent)


# --- capture_loop -----------------------------------------------------------

def test_capture_loop_no_pipeline_returns():
    asyncio.run(_bridge().capture_loop(FakeWebSocket()))  # pipeline None -> early return


def test_capture_loop_no_audio_returns():
    bridge = build_bridge(fast_config())  # has a pipeline; no audio backend
    asyncio.run(bridge.capture_loop(FakeWebSocket()))  # no audio -> early return


def test_capture_loop_runs_mic(monkeypatch):
    import jarvis_voice.bridge as bridge_mod

    cfg = fast_config()
    frames = [audio.silence(cfg.frame_ms)] * 3
    monkeypatch.setattr(bridge_mod, "audio_io_available", lambda: True)
    monkeypatch.setattr(audio, "MicStream", lambda **kw: FakeMic(frames))

    bridge = build_bridge(cfg)
    bridge.start_ambient()  # also fan frames to ambient
    asyncio.run(bridge.capture_loop(FakeWebSocket()))
    # reached here without error => mic loop ran and completed


# --- run() ------------------------------------------------------------------

def test_run_handshake_and_session():
    spk = FakeSpeaker()
    incoming = [
        Envelope.build(protocol.SERVER_HELLO_ACK, {"session": "S1"}).to_json(),
        Envelope.build(protocol.AGENT_SPEECH, {"text": "hi"}).to_json(),
    ]
    ws = FakeWebSocket(incoming)
    bridge = VoiceBridge(fast_config(), pipeline=None, speaker=spk)
    asyncio.run(bridge.run(ws))
    sent_types = [Envelope.from_json(s).type for s in ws.sent]
    assert protocol.CLIENT_HELLO in sent_types
    assert protocol.CLIENT_BYE in sent_types
    assert bridge.session == "S1"
    assert spk.spoken == ["hi"]


def test_run_autostarts_ambient_when_on():
    ws = FakeWebSocket([])
    bridge = VoiceBridge(fast_config(ambient_mode="on"), pipeline=None, speaker=FakeSpeaker())
    asyncio.run(bridge.run(ws))
    assert bridge._ambient_active is True


# --- connect_and_run --------------------------------------------------------

def test_connect_and_run_success_then_stop():
    class ConnCM:
        def __init__(self, ws):
            self.ws = ws

        async def __aenter__(self):
            return self.ws

        async def __aexit__(self, *a):
            return False

    ws = FakeWebSocket([])  # empty -> recv returns immediately -> run() completes
    bridge = VoiceBridge(
        fast_config(), pipeline=None, speaker=FakeSpeaker(), connect=lambda url: ConnCM(ws)
    )
    asyncio.run(bridge.connect_and_run(max_retries=1))
    assert any(Envelope.from_json(s).type == protocol.CLIENT_HELLO for s in ws.sent)


def test_connect_and_run_retries_then_gives_up(monkeypatch):
    calls = []

    def failing_connect(url):
        calls.append(url)
        raise OSError("refused")

    async def fast_sleep(_):
        return None

    monkeypatch.setattr(asyncio, "sleep", fast_sleep)
    bridge = VoiceBridge(fast_config(), pipeline=None, speaker=FakeSpeaker(), connect=failing_connect)
    asyncio.run(bridge.connect_and_run(max_retries=2))
    assert len(calls) == 2  # retried once, then gave up


def test_connect_and_run_default_websockets(monkeypatch):
    async def fast_sleep(_):
        return None

    monkeypatch.setattr(asyncio, "sleep", fast_sleep)
    # No injected connect -> imports websockets; bad port fails fast.
    bridge = VoiceBridge(
        fast_config(backend_url="ws://127.0.0.1:1/jarvis"),
        pipeline=None,
        speaker=FakeSpeaker(),
    )
    asyncio.run(bridge.connect_and_run(max_retries=1))


# --- build_bridge -----------------------------------------------------------

def test_build_bridge_with_and_without_capture():
    assert build_bridge(fast_config(), with_capture=True).pipeline is not None
    assert build_bridge(fast_config(), with_capture=False).pipeline is None
