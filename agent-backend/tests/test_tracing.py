"""Per-turn tracing (v1.3 §10.1): capture, live streaming, fetch, redaction."""

from __future__ import annotations

from pathlib import Path

from jarvis_backend import protocol
from jarvis_backend.agent import Agent
from jarvis_backend.agent.llm import MockLLM
from jarvis_backend.agent.trace import redact
from jarvis_backend.config import Config


class Recorder:
    def __init__(self):
        self.sent: list[protocol.Envelope] = []

    async def emit(self, type, payload=None, *, reply_to=None):
        self.sent.append(protocol.make(type, payload, session="S", reply_to=reply_to))

    def of(self, type: str) -> list[protocol.Envelope]:
        return [e for e in self.sent if e.type == type]


async def test_trace_capture_for_multi_agent_turn(agent):
    rec = Recorder()
    s = agent.create_session("S", rec.emit)
    s.tracer.subscribed = True  # the trace view turns streaming on
    await s.handle_user_text("show weather in tokyo and start a 5 minute timer")

    live = rec.of("orchestration.trace_event")
    assert live, "expected live trace_event stream when subscribed"
    kinds = {e.payload["kind"] for e in live}
    # A multi-agent turn touches memory, tools, and ends in a synthesized speech.
    assert {"memory_read", "tool_call", "tool_result", "memory_write", "speech"} <= kinds

    # Every event conforms to the schema shape + carries attribution.
    for e in live:
        protocol.TraceEvent.model_validate(e.payload)
        assert e.payload["agent_id"] and e.payload["role"]

    # The full trace is fetchable by plan_id (ring buffer).
    plan_id = rec.of("orchestration.plan")[0].payload["plan_id"]
    trace = s.tracer.get(plan_id)
    assert trace is not None
    server_trace = trace.to_server_trace()
    assert server_trace.plan_id == plan_id
    assert len(server_trace.entries) == len(live)  # recorded == streamed
    roles = {e.role for e in server_trace.entries}
    assert "research-agent" in roles and "orchestrator" in roles
    assert any(a.role == "orchestrator" for a in server_trace.agents)


async def test_trace_recorded_but_not_streamed_when_unsubscribed(agent):
    rec = Recorder()
    s = agent.create_session("S", rec.emit)  # subscribed defaults to False
    await s.handle_user_text("show weather in tokyo")
    assert not rec.of("orchestration.trace_event")  # nothing streamed
    plan_id = rec.of("orchestration.plan")[0].payload["plan_id"]
    assert s.tracer.get(plan_id) is not None  # but still recorded + fetchable


async def test_trace_includes_delegation_kind(agent):
    rec = Recorder()
    s = agent.create_session("S", rec.emit)
    s.tracer.subscribed = True
    await s.handle_user_text("search the web for mars rovers")
    kinds = {e.payload["kind"] for e in rec.of("orchestration.trace_event")}
    assert "delegated" in kinds


async def test_trace_get_most_recent_when_no_plan_id(agent):
    rec = Recorder()
    s = agent.create_session("S", rec.emit)
    await s.handle_user_text("what's on my calendar")
    assert s.tracer.get(None) is not None  # most recent turn


async def test_trace_disabled_records_nothing(tmp_path):
    cfg = Config(holo_registry_path=None, data_dir=Path(tmp_path), llm_provider="mock", trace_enabled=False)
    a = Agent.build(cfg, MockLLM())
    rec = Recorder()
    s = a.create_session("S", rec.emit)
    s.tracer.subscribed = True
    await s.handle_user_text("show weather in tokyo")
    assert not rec.of("orchestration.trace_event")
    assert s.tracer.get() is None


def test_redaction_scrubs_secrets_and_truncates():
    assert "[redacted]" in redact("my key is sk-ABCDEF1234567890QQ")
    assert "[redacted]" in redact("Authorization: Bearer abc.def.ghi")
    assert redact(None) is None
    assert len(redact("x" * 500)) <= 200
