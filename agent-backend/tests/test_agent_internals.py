"""Agent internals: the single-agent loop (orchestration off), interactions,
perception control/context, audio events, and barge-in."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from jarvis_backend import protocol
from jarvis_backend.agent import Agent
from jarvis_backend.agent.llm import ImageInput, LLMMessage, LLMProvider, LLMResult, MockLLM, ToolCall
from jarvis_backend.agent.tools import SpawnDirective, UpdateDirective, DestroyDirective
from jarvis_backend.config import Config


class Recorder:
    def __init__(self):
        self.sent: list[protocol.Envelope] = []

    async def emit(self, type, payload=None, *, reply_to=None):
        self.sent.append(protocol.make(type, payload, session="S", reply_to=reply_to))

    def of(self, type):
        return [e for e in self.sent if e.type == type]

    def types(self):
        return [e.type for e in self.sent]

    def speech(self):
        return " ".join(e.payload.get("text", "") for e in self.of("agent.speech")).lower()

    def widgets(self):
        return {e.payload["widget_type"] for e in self.of("holo.spawn")}


def _agent(tmp_path, llm=None, **over) -> Agent:
    cfg = Config(holo_registry_path=None, data_dir=Path(tmp_path), llm_provider="mock",
                 orchestration_enabled=False, **over)
    return Agent.build(cfg, llm or MockLLM())


def _session(tmp_path, llm=None, **over):
    rec = Recorder()
    return _agent(tmp_path, llm, **over).create_session("S", rec.emit), rec


# --- single-agent loop ------------------------------------------------------


async def test_single_agent_weather_turn(tmp_path):
    s, rec = _session(tmp_path)
    await s.handle_user_text("show weather in tokyo")
    assert "agent.transcript" in rec.types()
    stages = [e.payload.get("stage") for e in rec.of("agent.thinking")]
    assert "planning" in stages and "done" in stages
    assert "weather_orb" in rec.widgets()
    assert rec.of("agent.speech")[-1].payload["final"] is True


async def test_single_agent_multi_tool_layout(tmp_path):
    s, rec = _session(tmp_path)
    await s.handle_user_text("show weather in tokyo and start a 5 minute timer")
    assert {"weather_orb", "timer"} <= rec.widgets()
    assert rec.of("holo.layout")


async def test_single_agent_perceiving_turn(tmp_path):
    s, rec = _session(tmp_path)
    s.ingest_scene_objects({"objects": [{"label": "mug", "confidence": 0.8, "position": [0.3, 0.8, 0.7], "anchor": "world"}]})
    await s.handle_user_text("what is this on my desk?", attach_perception=True)
    actions = [e.payload["action"] for e in rec.of("perception.request")]
    assert "start" in actions and "stop" in actions
    assert rec.of("agent.observation")
    assert "vision_annotation" in rec.widgets()
    assert "perceiving" in [e.payload.get("stage") for e in rec.of("agent.thinking")]


async def test_single_agent_empty_text_noop(tmp_path):
    s, rec = _session(tmp_path)
    await s.handle_user_text("   ")
    assert rec.sent == []


async def test_single_agent_llm_error(tmp_path):
    class BoomLLM(LLMProvider):
        name = "mock"

        async def complete(self, messages, tools, *, images=None):
            raise RuntimeError("kaboom")

    s, rec = _session(tmp_path, BoomLLM())
    await s.handle_user_text("hello")
    assert rec.of("server.error")
    assert "problem" in rec.speech()


async def test_single_agent_max_steps_without_final(tmp_path):
    class LoopLLM(LLMProvider):
        name = "mock"

        async def complete(self, messages, tools, *, images=None):
            return LLMResult(tool_calls=[ToolCall(protocol.new_id(), "get_time", {})])

    s, rec = _session(tmp_path, LoopLLM(), max_tool_steps=2)
    await s.handle_user_text("loop please")
    assert "i've done what i can" in rec.speech()


# --- perception control + context -------------------------------------------


async def test_watch_start_and_stop(tmp_path):
    s, rec = _session(tmp_path)
    await s.handle_user_text("start watching my room")
    assert s.state.perception.watching is True
    assert any(e.payload["action"] == "start" for e in rec.of("perception.request"))
    assert "watching" in rec.speech()

    rec.sent.clear()
    await s.handle_user_text("stop watching")
    assert s.state.perception.watching is False
    assert any(e.payload["action"] == "stop" for e in rec.of("perception.request"))


async def test_resolve_attach_rules(tmp_path):
    s, _ = _session(tmp_path)
    assert s._resolve_attach("what is this", None) is True  # hint
    assert s._resolve_attach("hello", None) is False
    assert s._resolve_attach("hello", True) is True  # explicit
    assert s._resolve_attach("what is this", False) is False  # explicit override
    s.state.perception.vision_active = True
    assert s._resolve_attach("hello", None) is True  # active stream
    # perception disabled entirely
    s2, _ = _session(tmp_path, perception_enabled=False)
    assert s2._resolve_attach("what is this", True) is False


async def test_begin_perception_skips_when_watching(tmp_path):
    s, rec = _session(tmp_path)
    s.state.perception.watching = True
    assert await s._begin_perception_for_turn() is False
    assert rec.of("perception.request") == []


def test_perception_note_variants(tmp_path):
    s, _ = _session(tmp_path)
    assert s._perception_note() is None  # nothing sensed
    s.state.perception.add_vision_frame({"frame_id": "F1", "width": 4, "height": 4, "data": "QQ==", "seq": 1})
    s.state.perception.set_scene_objects({"objects": [{"label": "mug", "confidence": 0.8}]})
    s.state.perception.set_gaze({"hit_object_id": "O1"})
    s.state.perception.add_audio_event({"label": "doorbell"})
    s.state.perception.add_audio_scene({"ambient_transcript": "hello there"})
    note = s._perception_note()
    assert "Camera frame" in note and "mug" in note and "Gaze" in note
    assert "doorbell" in note and "Overheard" in note


def test_perception_images_gating(tmp_path):
    s, _ = _session(tmp_path)
    assert s._perception_images() is None  # mock provider -> no raw pixels

    class VisionLLM(LLMProvider):
        name = "openai"

        async def complete(self, *a, **k):
            return LLMResult(content="x")

    s.agent.set_llm(VisionLLM())
    assert s._perception_images() is None  # no frames yet
    s.state.perception.add_vision_frame({"frame_id": "F", "format": "jpeg", "data": "QQ==", "seq": 1})
    imgs = s._perception_images()
    assert imgs and isinstance(imgs[0], ImageInput)


# --- audio events -----------------------------------------------------------


async def test_audio_event_proactive(tmp_path):
    s, rec = _session(tmp_path, proactive=True)
    await s.handle_audio_event({"label": "doorbell", "confidence": 0.9})
    assert rec.of("agent.observation")
    assert "doorbell" in rec.speech()
    assert "live_caption" in rec.widgets()
    assert s.agent.episodic.recent_events(kind="audio")


async def test_audio_event_non_notable_silent(tmp_path):
    s, rec = _session(tmp_path, proactive=True)
    await s.handle_audio_event({"label": "keyboard_typing"})
    assert rec.of("agent.speech") == []


async def test_audio_scene_ingest(tmp_path):
    s, _ = _session(tmp_path)
    await s.handle_audio_scene({"ambient_transcript": "meeting"})
    assert s.state.perception.latest_audio_scene()["ambient_transcript"] == "meeting"


# --- interactions -----------------------------------------------------------


async def test_timer_interaction_pause_resume_cancel(tmp_path):
    s, rec = _session(tmp_path)
    await s.handle_user_text("set a 10 minute timer")
    oid = rec.of("holo.spawn")[0].payload["object_id"]

    await s.handle_interaction({"object_id": oid, "widget_type": "timer", "action": "tap"})
    assert rec.of("holo.update")[-1].payload["props"]["state"] == "paused"

    await s.handle_interaction({"object_id": oid, "widget_type": "timer", "action": "tap"})
    assert rec.of("holo.update")[-1].payload["props"]["state"] == "running"

    await s.handle_interaction({"object_id": oid, "widget_type": "timer", "action": "tap", "element": "cancel"})
    assert rec.of("holo.destroy")
    assert "cancelled" in rec.speech()


async def test_panel_close_interaction(tmp_path):
    s, rec = _session(tmp_path)
    await s.handle_user_text("what time is it")
    oid = rec.of("holo.spawn")[0].payload["object_id"]
    await s.handle_interaction({"object_id": oid, "widget_type": "panel", "action": "tap", "element": "close"})
    assert rec.of("holo.destroy")
    assert "closed" in rec.speech()


async def test_media_interaction_toggle(tmp_path):
    s, rec = _session(tmp_path)
    obj = protocol.HoloObject(
        object_id="m1", widget_type="media_player",
        transform=protocol.Transform(), props={"state": "playing"},
    )
    s.state.track(obj)
    await s.handle_interaction({"object_id": "m1", "widget_type": "media_player", "action": "toggle"})
    assert rec.of("holo.update")[-1].payload["props"]["state"] == "paused"
    await s.handle_interaction({"object_id": "m1", "widget_type": "media_player", "action": "toggle"})
    assert rec.of("holo.update")[-1].payload["props"]["state"] == "playing"


async def test_unhandled_interaction_routes_to_agent(tmp_path):
    s, rec = _session(tmp_path)
    # An interaction on an unknown widget -> synthetic user text into the loop.
    await s.handle_interaction({"object_id": "x", "widget_type": "doohickey", "action": "tap"})
    # The synthetic turn still produces some thinking{done}.
    assert any(e.payload.get("stage") == "done" for e in rec.of("agent.thinking"))


async def test_timer_interaction_unknown_object_is_noop(tmp_path):
    s, rec = _session(tmp_path)
    # widget_type timer but object not tracked -> _interact_timer returns False ->
    # routed back as synthetic text (no crash).
    await s.handle_interaction({"object_id": "ghost", "widget_type": "timer", "action": "tap"})
    assert rec.sent  # produced something, didn't crash


# --- directives + spawn edge cases ------------------------------------------


async def test_spawn_idempotent_then_update(tmp_path):
    s, rec = _session(tmp_path)
    await s._apply_directives([SpawnDirective(widget_type="panel", props={"title": "A", "body": "x"}, ref="p")])
    await s._apply_directives([SpawnDirective(widget_type="panel", props={"title": "B", "body": "y"}, ref="p")])
    assert len(rec.of("holo.spawn")) == 1  # second became an update
    assert rec.of("holo.update")


async def test_spawn_invalid_props_emits_error(tmp_path):
    s, rec = _session(tmp_path)
    ids = await s._apply_directives([SpawnDirective(widget_type="totally_unknown_widget", props={})])
    assert ids == []
    assert rec.of("server.error")


async def test_update_and_destroy_by_ref(tmp_path):
    s, rec = _session(tmp_path)
    await s._apply_directives([SpawnDirective(widget_type="panel", props={"title": "A", "body": "x"}, ref="p")])
    await s._apply_directives([UpdateDirective(ref="p", props={"body": "z"})])
    assert rec.of("holo.update")
    await s._apply_directives([DestroyDirective(ref="p")])
    assert rec.of("holo.destroy")
    assert s.state.resolve("p") is None


async def test_emit_observation_links_spawned_ids(tmp_path):
    s, rec = _session(tmp_path)
    ids = await s._apply_directives([SpawnDirective(widget_type="vision_annotation", props={"label": "mug", "confidence": 0.8})])
    await s._emit_observation({"text": "a mug", "annotations": [{"label": "mug"}]}, ids)
    obs = rec.of("agent.observation")[0].payload
    assert obs["annotations"][0]["object_id"] == ids[0]


# --- barge-in ---------------------------------------------------------------


async def test_barge_in_no_active_turn(tmp_path):
    s, _ = _session(tmp_path)
    assert await s.barge_in("user spoke") is False


async def test_barge_in_cancels_active_turn(tmp_path):
    s, rec = _session(tmp_path)
    started = asyncio.Event()

    async def long_turn():
        started.set()
        await asyncio.sleep(10)

    async def driver():
        await s.run_turn(long_turn())

    task = asyncio.create_task(driver())
    await started.wait()
    assert await s.barge_in("interrupt") is True
    assert s._cancelled is True
    with pytest.raises(asyncio.CancelledError):
        await task
    assert any(e.payload.get("label") == "Interrupted" for e in rec.of("agent.thinking"))


async def test_stream_speech_stops_when_cancelled(tmp_path):
    s, rec = _session(tmp_path)
    s._cancelled = True
    await s._stream_speech("One. Two. Three.")
    assert rec.of("agent.speech") == []


async def test_emit_observation_suppressed_when_cancelled(tmp_path):
    s, rec = _session(tmp_path)
    s._cancelled = True
    await s._emit_observation({"text": "x", "annotations": []}, [])
    assert rec.of("agent.observation") == []
