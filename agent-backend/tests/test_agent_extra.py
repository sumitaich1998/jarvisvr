"""Remaining agent.py branches: cancelled loop, timer-without-meta, intent
parsing, obj-None interactions, transform merge, ingest, user-role naming."""

from __future__ import annotations

from pathlib import Path

from jarvis_backend import protocol
from jarvis_backend.agent import Agent
from jarvis_backend.agent.llm import MockLLM
from jarvis_backend.agent.user_roster import UserAgent
from jarvis_backend.config import Config


class Recorder:
    def __init__(self):
        self.sent = []

    async def emit(self, type, payload=None, *, reply_to=None):
        self.sent.append(protocol.make(type, payload, session="S", reply_to=reply_to))

    def of(self, t):
        return [e for e in self.sent if e.type == t]

    def speech(self):
        return " ".join(e.payload.get("text", "") for e in self.of("agent.speech")).lower()


def _session(tmp_path, **over):
    cfg = Config(holo_registry_path=None, data_dir=Path(tmp_path), llm_provider="mock", orchestration_enabled=False, **over)
    rec = Recorder()
    return Agent.build(cfg, MockLLM()).create_session("S", rec.emit), rec


# --- cancelled single-agent loop --------------------------------------------


async def test_cancelled_before_loop_drops_turn(tmp_path):
    s, rec = _session(tmp_path)
    s._cancelled = True
    await s.handle_user_text("show weather in tokyo")
    assert rec.of("agent.speech") == []  # barged-in: no speech


async def test_cancelled_with_started_vision_stops_camera(tmp_path):
    s, rec = _session(tmp_path)
    s._cancelled = True
    await s.handle_user_text("what is this?", attach_perception=True)
    actions = [e.payload["action"] for e in rec.of("perception.request")]
    assert "start" in actions and "stop" in actions  # camera started then stopped on abort


# --- timer interaction without server-side meta -----------------------------


async def test_timer_interaction_without_meta_uses_props(tmp_path):
    s, rec = _session(tmp_path)
    obj = protocol.HoloObject(
        object_id="t1", widget_type="timer", transform=protocol.Transform(),
        props={"state": "running", "remaining_ms": 120000},
    )
    s.state.track(obj)  # tracked but NO entry in store["timers"]
    await s.handle_interaction({"object_id": "t1", "widget_type": "timer", "action": "tap", "element": "pause"})
    assert rec.of("holo.update")[-1].payload["props"]["state"] == "paused"
    await s.handle_interaction({"object_id": "t1", "widget_type": "timer", "action": "tap", "element": "resume"})
    assert rec.of("holo.update")[-1].payload["props"]["state"] == "running"


def test_timer_intent_parsing(tmp_path):
    s, _ = _session(tmp_path)
    Inter = protocol.ClientInteraction
    assert s._timer_intent(Inter(object_id="x", element="cancel")) == "cancel"
    assert s._timer_intent(Inter(object_id="x", element="pause")) == "pause"
    assert s._timer_intent(Inter(object_id="x", element="resume")) == "resume"
    assert s._timer_intent(Inter(object_id="x", action="toggle")) == "toggle"
    assert s._timer_intent(Inter(object_id="x")) == "toggle"  # default


# --- interactions with missing objects --------------------------------------


async def test_panel_interaction_obj_none_routes_back(tmp_path):
    s, rec = _session(tmp_path)
    await s.handle_interaction({"object_id": "ghost", "widget_type": "panel", "action": "tap", "element": "close"})
    # _interact_panel returns False (obj None) -> synthetic turn -> thinking{done}
    assert any(e.payload.get("stage") == "done" for e in rec.of("agent.thinking"))


async def test_media_interaction_obj_none_routes_back(tmp_path):
    s, rec = _session(tmp_path)
    await s.handle_interaction({"object_id": "ghost", "widget_type": "media_player", "action": "toggle"})
    assert rec.sent  # did not crash


# --- update with transform merge --------------------------------------------


async def test_update_object_merges_transform(tmp_path):
    from jarvis_backend.agent.tools import SpawnDirective

    s, rec = _session(tmp_path)
    ids = await s._apply_directives([SpawnDirective(widget_type="panel", props={"title": "A", "body": "x"}, ref="p")])
    await s._update_object(ids[0], transform={"position": [1, 2, 3]})
    obj = s.state.get_object(ids[0])
    assert obj.transform.position == [1, 2, 3]


# --- ingestion --------------------------------------------------------------


def test_ingest_vision_frame_and_state(tmp_path):
    s, _ = _session(tmp_path)
    s.ingest_vision_frame({"frame_id": "F", "width": 4, "height": 4}, raw=b"abcd")
    assert s.state.perception.latest_frame().frame_id == "F"
    s.ingest_state({"vision": {"active": True}})
    assert s.state.perception.vision_active is True


# --- user-role naming -------------------------------------------------------


def test_agent_user_role_spec_and_name(tmp_path):
    cfg = Config(holo_registry_path=None, data_dir=Path(tmp_path), llm_provider="mock")
    a = Agent.build(cfg, MockLLM())
    a.register_user_agent(UserAgent(role="finance-agent", name="Finance", persona="p"))
    assert a.get_spec("finance-agent").name == "Finance"
    assert a.display_name("finance-agent") == "Finance"
    assert a.is_builtin_role("finance-agent") is False
    assert a.is_builtin_role("research-agent") is True
