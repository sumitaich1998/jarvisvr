"""Orchestrator edge branches: empty goal, specialist failure, delegate-empty, stage skill."""

from __future__ import annotations

from pathlib import Path

from jarvis_backend import protocol
from jarvis_backend.agent import Agent
from jarvis_backend.agent.llm import MockLLM
from jarvis_backend.agent.orchestrator import SubTask
from jarvis_backend.config import Config


class Recorder:
    def __init__(self):
        self.sent = []

    async def emit(self, type, payload=None, *, reply_to=None):
        self.sent.append(protocol.make(type, payload, session="S", reply_to=reply_to))

    def of(self, t):
        return [e for e in self.sent if e.type == t]


def _session(tmp_path, **over):
    cfg = Config(holo_registry_path=None, data_dir=Path(tmp_path), llm_provider="mock", **over)
    rec = Recorder()
    return Agent.build(cfg, MockLLM()).create_session("S", rec.emit), rec


async def test_run_empty_goal_is_noop(tmp_path):
    s, rec = _session(tmp_path)
    await s.orchestrator.run("   ")
    assert rec.sent == []


async def test_specialist_failure_marks_failed(tmp_path):
    s, rec = _session(tmp_path)

    async def boom_run(name, args, ctx):
        raise RuntimeError("tool blew up")

    s.agent.registry.run = boom_run  # every tool now raises
    s.tracer.subscribed = True
    await s.handle_user_text("show weather in tokyo")
    states = [e.payload["state"] for e in rec.of("orchestration.agent_status")]
    assert "failed" in states
    assert any(e.payload["kind"] == "error" for e in rec.of("orchestration.trace_event"))


async def test_delegate_summarizers_no_items(tmp_path):
    s, _ = _session(tmp_path)
    s.tracer.start("P", "g")
    st = SubTask(agent_id="a1", role="research-agent", name="Research", label="research", calls=[])
    assert await s.orchestrator._delegate_summarizers("P", st, {}) == ""  # no results/articles


async def test_stage_activates_skill_when_present(tmp_path, monkeypatch):
    s, rec = _session(tmp_path)
    # Force the stage-agent to "have" a skill so the activate branch runs.
    real = s.orchestrator._skills_for

    def fake_skills_for(role, text):
        return ["compose-workspace"] if role == "stage-agent" else real(role, text)

    monkeypatch.setattr(s.orchestrator, "_skills_for", fake_skills_for)
    await s.handle_user_text("show weather in tokyo and start a 5 minute timer")
    stage_status = [e.payload for e in rec.of("orchestration.agent_status") if e.payload["role"] == "stage-agent"]
    assert any(p.get("skill") == "compose-workspace" for p in stage_status)
    assert rec.of("holo.layout")
