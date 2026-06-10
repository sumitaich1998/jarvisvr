"""v1.1 multimodal perception tests: buffer, vision turns, /vision ingest, tools."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
import websockets

from jarvis_backend import protocol
from jarvis_backend.agent import Agent
from jarvis_backend.agent.llm import MockLLM
from jarvis_backend.config import Config

_REAL_REGISTRY = Path("/Users/sumitaich/jarvisVR/holo-tools/registry.json")
from jarvis_backend.perception import (
    PerceptionBuffer,
    decode_binary_vision_frame,
    encode_binary_vision_frame,
)
from jarvis_backend.server import start_server


class Recorder:
    def __init__(self):
        self.sent: list[protocol.Envelope] = []

    async def emit(self, type, payload=None, *, reply_to=None):
        self.sent.append(protocol.make(type, payload, session="S", reply_to=reply_to))

    def of(self, type: str):
        return [e for e in self.sent if e.type == type]

    def widget_spawns(self):
        return {e.payload["widget_type"] for e in self.of("holo.spawn")}

    def all_speech(self) -> str:
        return " ".join(e.payload.get("text", "") for e in self.of("agent.speech")).lower()


def _proactive_agent(tmp_path: Path) -> Agent:
    cfg = Config(holo_registry_path=None, data_dir=Path(tmp_path), llm_provider="mock", proactive=True)
    return Agent.build(cfg, MockLLM())


# --- unit: buffer + binary transport ----------------------------------------


def test_binary_vision_frame_roundtrip():
    header = {"frame_id": "F1", "camera": "rgb_center", "width": 4, "height": 4, "transport": "binary", "seq": 7}
    img = b"\x01\x02\x03\x04\x05"
    msg = encode_binary_vision_frame(header, img)
    h2, i2 = decode_binary_vision_frame(msg)
    assert h2["frame_id"] == "F1"
    assert i2 == img


def test_perception_buffer_basics():
    b = PerceptionBuffer(max_frames=2)
    b.add_vision_frame({"frame_id": "a", "width": 2, "height": 2, "data": "AAAA", "seq": 1})
    b.add_vision_frame({"frame_id": "b", "seq": 2}, raw=b"xyz")
    assert b.frames_seen == 2
    assert b.latest_frame().frame_id == "b"
    assert b.latest_frame().size_bytes == 3
    assert b.vision_active is True
    b.add_audio_event({"label": "doorbell", "confidence": 0.9})
    assert b.latest_audio_event()["label"] == "doorbell"
    b.set_scene_objects({"objects": [{"label": "mug", "position": [0, 0, 1]}]})
    ctx = b.current_context()
    assert ctx["objects"][0]["label"] == "mug"
    imgs = b.images_for_llm(1)
    assert imgs and imgs[0][1] == "image/jpeg"


# --- in-process vision turns ------------------------------------------------


async def test_vision_turn_emits_request_observation_and_annotation(agent):
    rec = Recorder()
    s = agent.create_session("S", rec.emit)
    # Client-detected objects (no frame yet -> vision not active -> request 'once').
    s.ingest_scene_objects(
        {"frame_id": "F1", "objects": [
            {"label": "coffee mug", "confidence": 0.82, "position": [0.3, 0.8, 0.7], "anchor": "world"},
        ]}
    )
    await s.handle_user_text("what is this on my desk?", attach_perception=True)

    # Pull-based control: a perception.request was emitted (vision wasn't active).
    reqs = rec.of("perception.request")
    assert reqs and reqs[0].payload["stream"] == "vision"

    # An agent.observation narration was produced.
    obs = rec.of("agent.observation")
    assert obs
    assert "coffee mug" in obs[0].payload["text"].lower()

    # A valid vision_annotation hologram was spawned, anchored in the world.
    spawns = [e for e in rec.of("holo.spawn") if e.payload["widget_type"] == "vision_annotation"]
    assert spawns
    obj = protocol.HoloObject.model_validate(spawns[0].payload)
    assert obj.props["label"] == "coffee mug"
    assert obj.transform.anchor == "world"

    # thinking surfaced a perceiving/looking stage.
    stages = {e.payload.get("stage") for e in rec.of("agent.thinking")}
    assert stages & {"perceiving", "looking"}


async def test_describe_view_offline_canned(agent):
    rec = Recorder()
    s = agent.create_session("S", rec.emit)
    await s.handle_user_text("what do you see?", attach_perception=True)
    obs = rec.of("agent.observation")
    assert obs and "see" in obs[0].payload["text"].lower()
    annotations = [e for e in rec.of("holo.spawn") if e.payload["widget_type"] == "vision_annotation"]
    assert annotations  # canned scene gets annotated even with no detections


async def test_attach_perception_false_suppresses_vision(agent):
    rec = Recorder()
    s = agent.create_session("S", rec.emit)
    # Even though the text looks visual, the client said don't attach perception.
    await s.handle_user_text("what is this?", attach_perception=False)
    assert not rec.of("perception.request")


async def test_identify_sound_from_buffer(agent):
    rec = Recorder()
    s = agent.create_session("S", rec.emit)
    s.state.perception.add_audio_event({"label": "doorbell", "confidence": 0.8})
    await s.handle_user_text("what was that sound?")
    assert "doorbell" in rec.all_speech()


async def test_proactive_sound_event(tmp_path):
    agent = _proactive_agent(tmp_path)
    rec = Recorder()
    s = agent.create_session("S", rec.emit)
    await s.handle_audio_event({"label": "doorbell", "confidence": 0.9})
    assert rec.of("agent.observation")
    assert "doorbell" in rec.all_speech()
    assert "live_caption" in rec.widget_spawns()


async def test_remember_and_find_object(agent):
    rec = Recorder()
    s = agent.create_session("S", rec.emit)
    # Detected objects are auto-indexed into spatial memory.
    s.ingest_scene_objects(
        {"objects": [{"label": "keys", "confidence": 0.9, "position": [0.5, 0.8, 0.6], "anchor": "world"}]}
    )
    await s.handle_user_text("where did I leave my keys?")
    assert "keys" in rec.all_speech()
    assert "vision_annotation" in rec.widget_spawns()


async def test_web_search_tool(agent):
    rec = Recorder()
    s = agent.create_session("S", rec.emit)
    await s.handle_user_text("search the web for mars rovers")
    assert "web_panel" in rec.widget_spawns()
    assert "mars rovers" in rec.all_speech()


async def test_read_and_translate(agent):
    rec = Recorder()
    s = agent.create_session("S", rec.emit)
    await s.handle_user_text("read this sign and translate it to spanish")
    widgets = rec.widget_spawns()
    assert "panel" in widgets  # read_text -> panel
    assert "translator" in widgets  # translate_view -> translator


async def test_stocks_and_news_and_calendar(agent):
    rec = Recorder()
    s = agent.create_session("S", rec.emit)
    await s.handle_user_text("show me stock prices for AAPL and TSLA")
    await s.handle_user_text("what's the news about space")
    await s.handle_user_text("what's on my calendar")
    widgets = rec.widget_spawns()
    assert {"stocks_ticker", "news_feed", "calendar"} <= widgets


@pytest.mark.skipif(not _REAL_REGISTRY.is_file(), reason="canonical registry.json not present")
async def test_all_tools_validate_against_canonical_registry(tmp_path):
    """Every perception/knowledge tool's props must pass the *canonical* (closed)
    holo-tools schemas — not just our lenient fallback."""
    cfg = Config(holo_registry_path=_REAL_REGISTRY, data_dir=Path(tmp_path), llm_provider="mock")
    agent = Agent.build(cfg, MockLLM())
    rec = Recorder()
    s = agent.create_session("S", rec.emit)
    s.ingest_scene_objects(
        {"objects": [
            {"label": "laptop", "confidence": 0.9, "position": [0.0, 0.8, 0.7], "anchor": "world"},
            {"label": "keys", "confidence": 0.8, "position": [0.5, 0.8, 0.6], "anchor": "world"},
        ]}
    )
    s.state.perception.add_audio_event({"label": "doorbell", "confidence": 0.9})
    utterances = [
        "what is this on my desk?",
        "what do you see?",
        "read this sign and translate it to spanish",
        "remember my wallet is on the counter",
        "where did I leave my keys?",
        "what was that sound?",
        "show me stock prices for AAPL and TSLA",
        "what's the news about space",
        "what's on my calendar",
        "navigate to the kitchen",
        "measure the desk",
        "search the web for mars rovers",
        "set a 5 minute timer",
        "what's the weather in tokyo",
    ]
    for u in utterances:
        await s.handle_user_text(u, attach_perception=True)

    errors = [e.payload for e in rec.of("server.error")]
    assert not errors, f"props rejected by canonical schema: {errors}"
    # We should have spawned a healthy variety of holograms, all validated.
    assert len(rec.of("holo.spawn")) >= 10


# --- /vision binary endpoint (real sockets) ---------------------------------


async def _start(config):
    server, _agent = await start_server(config)
    port = server.sockets[0].getsockname()[1]
    return server, port


async def _recv(ws):
    return protocol.parse_inbound(await ws.recv())


async def _wait_for(ws, type_, timeout=5.0):
    async def loop():
        while True:
            env = await _recv(ws)
            if env.type == type_:
                return env

    return await asyncio.wait_for(loop(), timeout)


async def test_vision_endpoint_binary_ingest_and_turn(config):
    server, port = await _start(config)
    main_uri = f"ws://127.0.0.1:{port}/jarvis"
    try:
        async with websockets.connect(main_uri) as ws:
            await ws.send(
                protocol.make(
                    "client.hello",
                    {"device": "quest3", "capabilities": {"camera_passthrough": True}},
                ).to_json()
            )
            ack = await _wait_for(ws, "server.hello_ack")
            session = ack.payload["session"]
            assert ack.payload["perception"]["vision"] is True
            assert "describe_view" in ack.payload["tools"]

            # Detected objects (inline JSON on the main channel).
            await ws.send(
                protocol.make(
                    "perception.scene_objects",
                    {"objects": [{"label": "laptop", "confidence": 0.9, "position": [0.0, 0.8, 0.7], "anchor": "world"}]},
                    session=session,
                ).to_json()
            )

            # Binary passthrough frame on the parallel /vision endpoint.
            vision_uri = f"ws://127.0.0.1:{port}/vision?session={session}"
            async with websockets.connect(vision_uri) as vws:
                frame = encode_binary_vision_frame(
                    {"frame_id": "F9", "camera": "rgb_center", "width": 1024, "height": 1024, "seq": 1},
                    b"\xff\xd8\xff\xe0_fake_jpeg_bytes_",
                )
                await vws.send(frame)
                await asyncio.sleep(0.25)  # let the server ingest it

                # Now ask about the view; perception auto-attaches.
                await ws.send(
                    protocol.make(
                        "user.text",
                        {"text": "what is this on my desk?", "attach_perception": True},
                        session=session,
                    ).to_json()
                )

                got_obs = False
                got_annotation = False
                request_actions: list[str] = []
                deadline = asyncio.get_event_loop().time() + 6.0
                while asyncio.get_event_loop().time() < deadline:
                    try:
                        env = await asyncio.wait_for(_recv(ws), timeout=2.0)
                    except asyncio.TimeoutError:
                        break
                    if env.type == "agent.observation":
                        got_obs = True
                    elif env.type == "perception.request":
                        request_actions.append(env.payload.get("action"))
                    elif env.type == "holo.spawn" and env.payload["widget_type"] == "vision_annotation":
                        got_annotation = True
                    # The vision turn ends with perception.request{stop} (§8.6).
                    if env.type == "perception.request" and env.payload.get("action") == "stop":
                        break

                assert got_obs, "expected an agent.observation"
                assert got_annotation, "expected a vision_annotation holo.spawn"
                # The one-shot vision turn controls the camera per PROTOCOL §8.6:
                # start at the beginning, stop once the question is answered.
                assert "start" in request_actions, "expected perception.request{start}"
                assert "stop" in request_actions, "expected perception.request{stop}"
    finally:
        server.close()
        await server.wait_closed()
