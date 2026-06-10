"""A few remaining agent-loop false-branches (no-directive tool, by-object_id
directives, unknown-object update, frame-less perception note)."""

from __future__ import annotations

from pathlib import Path

from jarvis_backend import protocol
from jarvis_backend.agent import Agent
from jarvis_backend.agent.llm import LLMProvider, LLMResult, MockLLM, ToolCall
from jarvis_backend.agent.tools import DestroyDirective, SpawnDirective, UpdateDirective
from jarvis_backend.config import Config


class Recorder:
    def __init__(self):
        self.sent = []

    async def emit(self, type, payload=None, *, reply_to=None):
        self.sent.append(protocol.make(type, payload, session="S", reply_to=reply_to))

    def of(self, t):
        return [e for e in self.sent if e.type == t]


def _session(tmp_path, llm=None):
    cfg = Config(holo_registry_path=None, data_dir=Path(tmp_path), llm_provider="mock", orchestration_enabled=False)
    rec = Recorder()
    return Agent.build(cfg, llm or MockLLM()).create_session("S", rec.emit), rec


async def test_single_agent_tool_without_directives(tmp_path):
    class TwoStep(LLMProvider):
        name = "mock"

        def __init__(self):
            self.n = 0

        async def complete(self, messages, tools, *, images=None):
            self.n += 1
            if self.n == 1:
                return LLMResult(tool_calls=[ToolCall("c", "take_note", {"text": ""})])  # no directives
            return LLMResult(content="All set.")

    s, rec = _session(tmp_path, TwoStep())
    await s.handle_user_text("note nothing")
    assert "all set" in " ".join(e.payload.get("text", "") for e in rec.of("agent.speech")).lower()
    assert rec.of("holo.spawn") == []  # the empty note produced no hologram


async def test_directives_by_object_id(tmp_path):
    s, rec = _session(tmp_path)
    ids = await s._apply_directives([SpawnDirective(widget_type="panel", props={"title": "A", "body": "x"})])
    await s._apply_directives([UpdateDirective(object_id=ids[0], props={"body": "y"})])
    await s._apply_directives([DestroyDirective(object_id=ids[0])])
    assert rec.of("holo.update") and rec.of("holo.destroy")


async def test_apply_all_directive_types_in_one_call(tmp_path):
    # spawn -> update -> destroy in a single batch exercises the isinstance chain.
    s, rec = _session(tmp_path)
    await s._apply_directives([
        SpawnDirective(widget_type="panel", props={"title": "A", "body": "x"}, ref="p"),
        UpdateDirective(ref="p", props={"body": "y"}),
        DestroyDirective(ref="p"),
    ])
    assert rec.of("holo.spawn") and rec.of("holo.update") and rec.of("holo.destroy")


async def test_update_and_destroy_directive_without_target_noop(tmp_path):
    # ref/object_id both None -> resolved object_id None -> directive is skipped.
    s, rec = _session(tmp_path)
    await s._apply_directives([UpdateDirective(props={"x": 1})])
    await s._apply_directives([DestroyDirective()])
    assert rec.of("holo.update") == [] and rec.of("holo.destroy") == []


async def test_update_unknown_object_still_emits(tmp_path):
    s, rec = _session(tmp_path)
    await s._update_object("ghost-id", props={"x": 1})  # obj None -> skip merge, still emit
    assert rec.of("holo.update")[-1].payload["object_id"] == "ghost-id"


def test_perception_note_without_frame(tmp_path):
    s, _ = _session(tmp_path)
    s.state.perception.set_scene_objects({"objects": [{"label": "mug", "confidence": 0.8}]})
    s.state.perception.set_gaze({"hit_object_id": "O1"})
    s.state.perception.add_audio_event({"label": "doorbell"})
    note = s._perception_note()
    assert "Camera frame" not in note  # no frame ingested
    assert "mug" in note and "Gaze" in note
