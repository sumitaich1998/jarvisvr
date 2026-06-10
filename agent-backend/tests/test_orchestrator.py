"""Multi-agent orchestrator (§9): decompose → route → execute → synthesize."""

from __future__ import annotations

from pathlib import Path

from jarvis_backend import protocol
from jarvis_backend.agent import Agent
from jarvis_backend.agent.llm import MockLLM
from jarvis_backend.config import Config

FIX = Path(__file__).parent / "fixtures" / "skills"


class Recorder:
    def __init__(self):
        self.sent: list[protocol.Envelope] = []

    async def emit(self, type, payload=None, *, reply_to=None):
        self.sent.append(protocol.make(type, payload, session="S", reply_to=reply_to))

    def of(self, type: str) -> list[protocol.Envelope]:
        return [e for e in self.sent if e.type == type]

    def widgets(self) -> set[str]:
        return {e.payload["widget_type"] for e in self.of("holo.spawn")}

    def all_speech(self) -> str:
        return " ".join(e.payload.get("text", "") for e in self.of("agent.speech")).lower()

    def states_for(self, agent_id: str) -> list[str]:
        return [
            e.payload["state"]
            for e in self.of("orchestration.agent_status")
            if e.payload["agent_id"] == agent_id
        ]


async def test_multi_agent_plan_and_status_lifecycle(agent):
    rec = Recorder()
    s = agent.create_session("S", rec.emit)
    await s.handle_user_text("show weather in tokyo and start a 5 minute timer")

    # Exactly one plan, with ≥2 specialists + the orchestrator.
    plans = rec.of("orchestration.plan")
    assert len(plans) == 1
    plan = plans[0].payload
    protocol.OrchestrationPlan.model_validate(plan)  # conforms to §9.2
    roles = {a["role"] for a in plan["agents"]}
    assert "orchestrator" in roles
    assert {"research-agent", "productivity-agent"} <= roles
    specialists = [a for a in plan["agents"] if a["level"] == 1]
    assert len(specialists) >= 2

    # Each specialist progressed queued → working → done.
    for sp in specialists:
        states = rec.states_for(sp["agent_id"])
        assert "queued" in states and "working" in states and "done" in states

    # Real work surfaced as holograms + a stage layout, ending in a final speech.
    assert {"weather_orb", "timer"} <= rec.widgets()
    assert rec.of("holo.layout")
    speeches = rec.of("agent.speech")
    assert speeches and speeches[-1].payload["final"] is True

    # agent.thinking is attributed to agents (orchestrator + a specialist).
    tagged = [e.payload for e in rec.of("agent.thinking") if e.payload.get("agent_id")]
    assert any(p.get("role") == "orchestrator" for p in tagged)
    assert any(p.get("agent_id", "").startswith("a") for p in tagged)


async def test_parallel_specialists_both_run(agent):
    rec = Recorder()
    s = agent.create_session("S", rec.emit)
    await s.handle_user_text("what's the weather in tokyo and what's on my calendar")
    done = {e.payload["role"] for e in rec.of("orchestration.agent_status") if e.payload["state"] == "done"}
    assert {"research-agent", "productivity-agent"} <= done
    assert {"weather_orb", "calendar"} <= rec.widgets()


async def test_subagent_handoff(agent):
    rec = Recorder()
    s = agent.create_session("S", rec.emit)
    await s.handle_user_text("search the web for mars rovers")

    handoffs = rec.of("orchestration.handoff")
    assert handoffs, "expected the research-agent to delegate to summarizer sub-agents"
    h = handoffs[0].payload
    protocol.OrchestrationHandoff.model_validate(h)
    assert h["to_role"] == "summarizer"
    assert h["level"] == 2
    assert "." in h["to_agent"]  # dotted multi-level id (a1.1)
    assert h["from_agent"] == "a1"

    # the sub-agent reported its own lifecycle, and a1 went through 'delegating'
    assert "done" in rec.states_for(h["to_agent"])
    assert "delegating" in rec.states_for("a1")
    assert "web_panel" in rec.widgets()
    assert "mars rovers" in rec.all_speech()


async def test_trivial_goal_is_one_agent_plan(agent):
    rec = Recorder()
    s = agent.create_session("S", rec.emit)
    await s.handle_user_text("set a 10 minute timer")
    plan = rec.of("orchestration.plan")[0].payload
    specialists = [a for a in plan["agents"] if a["level"] == 1]
    assert len(specialists) == 1
    assert specialists[0]["role"] == "productivity-agent"
    assert not rec.of("holo.layout")  # single agent → no stage composition pass
    assert rec.of("agent.speech")


async def test_greeting_has_no_specialists(agent):
    rec = Recorder()
    s = agent.create_session("S", rec.emit)
    await s.handle_user_text("hello jarvis")
    plan = rec.of("orchestration.plan")[0].payload
    assert [a["role"] for a in plan["agents"]] == ["orchestrator"]
    assert not rec.of("holo.spawn")
    assert rec.of("agent.speech")[-1].payload["final"] is True


async def test_worked_example_offline_end_to_end(agent):
    """ORCHESTRATION.md §6: 'what's this + weather in Tokyo + 5-min timer'."""
    rec = Recorder()
    s = agent.create_session("S", rec.emit)
    s.ingest_scene_objects(
        {"objects": [{"label": "coffee mug", "confidence": 0.82, "position": [0.3, 0.8, 0.7], "anchor": "world"}]}
    )
    await s.handle_user_text(
        "Jarvis, what's this on my desk, and what's the weather in Tokyo? Start a 5-minute timer.",
        attach_perception=True,
    )

    plan = rec.of("orchestration.plan")[0].payload
    roles = {a["role"] for a in plan["agents"]}
    assert {"perception-agent", "research-agent", "productivity-agent", "stage-agent"} <= roles

    done_roles = {e.payload["role"] for e in rec.of("orchestration.agent_status") if e.payload["state"] == "done"}
    assert {"perception-agent", "research-agent", "productivity-agent"} <= done_roles

    assert {"weather_orb", "timer", "vision_annotation"} <= rec.widgets()
    assert rec.of("holo.layout")

    final = rec.of("agent.speech")[-1].payload
    assert final["final"] is True
    speech = rec.all_speech()
    assert "tokyo" in speech and "timer" in speech and ("mug" in speech or "coffee" in speech)

    # Camera control around the perception sub-task (§8.6) still holds.
    actions = [e.payload["action"] for e in rec.of("perception.request")]
    assert "start" in actions and "stop" in actions


def _skilled_agent(tmp_path: Path) -> Agent:
    cfg = Config(holo_registry_path=None, data_dir=Path(tmp_path), llm_provider="mock", skills_dir=FIX)
    return Agent.build(cfg, MockLLM())


async def test_skills_enrich_agents(tmp_path):
    a = _skilled_agent(tmp_path)
    assert a.skills.for_agent("research-agent")  # fixture skill loaded + assigned
    rec = Recorder()
    s = a.create_session("S", rec.emit)
    await s.handle_user_text("what's the weather in tokyo")

    plan = rec.of("orchestration.plan")[0].payload
    research = next(x for x in plan["agents"] if x["role"] == "research-agent")
    assert "web-research" in (research.get("skills") or [])

    # the agent_status for the research-agent names its active skill
    statuses = [e.payload for e in rec.of("orchestration.agent_status") if e.payload["role"] == "research-agent"]
    assert any(p.get("skill") == "web-research" for p in statuses)
    # the skill body was activated on demand (progressive disclosure)
    assert a.skills.get("web-research").activated is True
