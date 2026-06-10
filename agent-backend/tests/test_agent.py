"""Agent orchestration-loop tests (mock LLM, in-process, no sockets)."""

from __future__ import annotations

from jarvis_backend import protocol


class Recorder:
    """Captures emitted messages exactly as the server would build them."""

    def __init__(self):
        self.sent: list[protocol.Envelope] = []

    async def emit(self, type, payload=None, *, reply_to=None):
        self.sent.append(
            protocol.make(type, payload, session="S", reply_to=reply_to)
        )

    def types(self) -> list[str]:
        return [e.type for e in self.sent]

    def of(self, type: str) -> list[protocol.Envelope]:
        return [e for e in self.sent if e.type == type]


async def test_weather_in_tokyo_produces_valid_holo_spawn(agent):
    rec = Recorder()
    session = agent.create_session("S", rec.emit)

    await session.handle_user_text("show weather in tokyo")

    types = rec.types()
    assert "agent.transcript" in types
    assert "agent.thinking" in types

    # Final speech present.
    speeches = rec.of("agent.speech")
    assert speeches, "expected at least one agent.speech"
    assert speeches[-1].payload["final"] is True

    # A valid weather_orb hologram was spawned.
    spawns = rec.of("holo.spawn")
    assert spawns, "expected a holo.spawn"
    obj_payload = spawns[0].payload
    obj = protocol.HoloObject.model_validate(obj_payload)  # validates the shape
    assert obj.widget_type == "weather_orb"
    assert obj.props["city"] == "Tokyo"
    assert "temp_c" in obj.props
    assert obj.transform.anchor in {"world", "head", "hand_left", "hand_right", "surface"}
    assert len(obj.transform.rotation) == 4  # quaternion

    # thinking stages include planning and done.
    stages = [e.payload.get("stage") for e in rec.of("agent.thinking")]
    assert "planning" in stages
    assert "done" in stages


async def test_thinking_emits_tool_call_stage(agent):
    rec = Recorder()
    session = agent.create_session("S", rec.emit)
    await session.handle_user_text("what's the weather in london")
    thinking = rec.of("agent.thinking")
    tool_stages = [e.payload for e in thinking if e.payload.get("stage") == "tool_call"]
    assert tool_stages
    assert tool_stages[0]["tool"] == "get_weather"


async def test_multi_tool_turn_emits_layout(agent):
    rec = Recorder()
    session = agent.create_session("S", rec.emit)
    await session.handle_user_text("show weather in tokyo and start a 5 minute timer")

    spawns = rec.of("holo.spawn")
    widget_types = {protocol.HoloObject.model_validate(s.payload).widget_type for s in spawns}
    assert {"weather_orb", "timer"} <= widget_types

    timer = next(
        s for s in spawns
        if protocol.HoloObject.model_validate(s.payload).widget_type == "timer"
    )
    assert timer.payload["props"]["duration_ms"] == 300_000

    layouts = rec.of("holo.layout")
    assert layouts, "expected a holo.layout when spawning multiple objects"
    assert len(layouts[0].payload["objects"]) >= 2


async def test_timer_interaction_pauses(agent):
    rec = Recorder()
    session = agent.create_session("S", rec.emit)
    await session.handle_user_text("set a 10 minute timer")

    spawn = rec.of("holo.spawn")[0]
    object_id = spawn.payload["object_id"]
    assert spawn.payload["props"]["state"] == "running"

    await session.handle_interaction(
        {"object_id": object_id, "widget_type": "timer", "action": "tap"}
    )

    updates = rec.of("holo.update")
    assert updates, "expected a holo.update from the interaction"
    assert updates[-1].payload["object_id"] == object_id
    assert updates[-1].payload["props"]["state"] == "paused"


async def test_fallback_shows_panel(agent):
    rec = Recorder()
    session = agent.create_session("S", rec.emit)
    await session.handle_user_text("tell me something interesting")

    spawns = rec.of("holo.spawn")
    assert spawns
    assert protocol.HoloObject.model_validate(spawns[0].payload).widget_type == "panel"
    assert rec.of("agent.speech")


async def test_greeting_speaks_without_holo(agent):
    rec = Recorder()
    session = agent.create_session("S", rec.emit)
    await session.handle_user_text("hello jarvis")
    assert rec.of("agent.speech")
    assert not rec.of("holo.spawn")


async def test_notes_persist_via_long_term_memory(agent):
    rec = Recorder()
    session = agent.create_session("S", rec.emit)
    await session.handle_user_text("take a note buy oat milk")
    panel = rec.of("holo.spawn")[0]
    assert protocol.HoloObject.model_validate(panel.payload).widget_type == "panel"
    assert agent.longterm.get("notes")
    assert agent.longterm.get("notes")[0]["text"] == "buy oat milk"
