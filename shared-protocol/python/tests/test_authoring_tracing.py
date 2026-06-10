"""v1.3 §10 Tracing & In-headset Authoring: round-trip, schema validation, version."""

from __future__ import annotations

import pytest

import jarvis_protocol as jp
from jarvis_protocol import (
    AuthoringAgent,
    AuthoringSkill,
    ClientAgentInspect,
    ClientAuthorAgent,
    ClientAuthorList,
    ClientAuthorSkill,
    ClientTraceGet,
    ClientTraceSubscribe,
    MemoryInfo,
    MemoryRecentItem,
    MessageType,
    ProtocolValidationError,
    ServerAgentInfo,
    ServerAuthoring,
    ServerTrace,
    SkillInfo,
    TraceAgent,
    TraceEvent,
)

CASES = [
    (MessageType.CLIENT_TRACE_SUBSCRIBE, ClientTraceSubscribe(enabled=True)),
    (MessageType.CLIENT_TRACE_GET, ClientTraceGet(plan_id="P1")),
    (MessageType.CLIENT_AGENT_INSPECT, ClientAgentInspect(role="research-agent")),
    (MessageType.CLIENT_AUTHOR_LIST, ClientAuthorList()),
    (MessageType.CLIENT_AUTHOR_SKILL, ClientAuthorSkill(
        op="create", name="track-habit", category="productivity", agent="productivity-agent",
        description="Track a habit.", body="# Track\n1. note", allowed_tools=["take_note"])),
    (MessageType.CLIENT_AUTHOR_AGENT, ClientAuthorAgent(
        op="create", role="finance-agent", name="Finance", persona="Meticulous.",
        tools=["get_stocks"], skills=["market-briefing"])),
    (MessageType.ORCHESTRATION_TRACE_EVENT, TraceEvent(
        plan_id="P1", seq=3, ts=1733397600000, agent_id="a1", role="research-agent",
        parent="jarvis", level=1, kind="tool_call", label="get_weather(city=Tokyo)",
        tool="get_weather", detail="ok", duration_ms=12)),
    (MessageType.SERVER_TRACE, ServerTrace(
        plan_id="P1", goal="weather + timer",
        agents=[TraceAgent(agent_id="a1", role="research-agent", parent="jarvis", level=1)],
        entries=[TraceEvent(plan_id="P1", seq=0, ts=1, agent_id="a1", role="research-agent",
                            kind="memory_read", label="recalled 0 items")])),
    (MessageType.SERVER_AGENT_INFO, ServerAgentInfo(
        role="research-agent", name="Research", source="builtin", persona="Knowledge.",
        tools=["get_weather"], skills=[SkillInfo(name="web-research", description="d", source="builtin")],
        memory=MemoryInfo(summary="1 item", items=1, recent=[MemoryRecentItem(ts=1, text="t")]))),
    (MessageType.SERVER_AUTHORING, ServerAuthoring(
        agents=[AuthoringAgent(role="research-agent", name="Research", source="builtin",
                               skills=["web-research"], tools=["get_weather"])],
        skills=[AuthoringSkill(name="web-research", agent="research-agent", category="research",
                               source="builtin", description="d")],
        categories=["research"], tools=["get_weather"])),
]


@pytest.mark.parametrize("type_name,payload", CASES, ids=[c[0] for c in CASES])
def test_v13_roundtrip_and_validate(type_name, payload):
    msg = jp.new_message(type_name, payload, session="S")
    assert msg.v == "1.3.0"
    decoded = jp.decode(jp.encode(msg))
    assert decoded.type == type_name
    assert jp.to_dict(decoded) == jp.to_dict(msg)
    jp.validate(msg, allow_unknown_types=False)
    assert jp.is_valid(msg)


@pytest.mark.parametrize("type_name,payload", CASES, ids=[c[0] for c in CASES])
def test_v13_typed_parse(type_name, payload):
    msg = jp.new_message(type_name, payload, session="S")
    assert type(jp.parse_payload(msg.type, msg.payload)) is type(payload)


def _msg(type_name, payload):
    return {"v": "1.3.0", "id": "m1", "type": type_name, "ts": 1, "session": "S", "payload": payload}


@pytest.mark.parametrize(
    "bad",
    [
        _msg("orchestration.trace_event", {"plan_id": "P", "seq": 0, "ts": 1, "agent_id": "a1", "role": "r", "label": "x"}),  # missing kind
        _msg("orchestration.trace_event", {"plan_id": "P", "seq": 0, "ts": 1, "agent_id": "a1", "role": "r", "kind": "napping", "label": "x"}),  # bad kind
        _msg("client.author_skill", {"op": "create"}),  # missing name
        _msg("client.author_skill", {"op": "rename", "name": "x"}),  # bad op
        _msg("client.author_agent", {"op": "create"}),  # missing role
        _msg("client.agent_inspect", {}),  # needs role or agent_id (anyOf)
        _msg("server.authoring", {"agents": []}),  # missing skills
        _msg("server.trace", {"plan_id": "P"}),  # missing entries
        _msg("client.trace_subscribe", {}),  # missing enabled
    ],
)
def test_malformed_v13_rejected(bad):
    assert not jp.is_valid(bad)
    with pytest.raises(ProtocolValidationError):
        jp.validate(bad)


def test_version_is_1_3_0_and_backward_compatible():
    assert jp.PROTOCOL_VERSION == "1.3.0"
    for v in ("1.0.0", "1.1.0", "1.2.0", "1.3.0"):
        assert v in jp.SUPPORTED_VERSIONS
    jp.validate(
        '{"v":"1.2.0","id":"a","type":"orchestration.plan","ts":1,"session":"S",'
        '"payload":{"plan_id":"p","goal":"g","agents":[{"agent_id":"a1","role":"r","level":1}]}}',
        allow_unknown_types=False,
    )
