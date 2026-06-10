"""v1.2 §9 Multi-Agent Orchestration: round-trip, schema validation, version."""

from __future__ import annotations

import pytest

import jarvis_protocol as jp
from jarvis_protocol import (
    MessageType,
    OrchestrationAgent,
    OrchestrationAgentStatus,
    OrchestrationHandoff,
    OrchestrationPlan,
    ProtocolValidationError,
)

_PLAN = OrchestrationPlan(
    plan_id="P1",
    goal="show the weather in Tokyo and start a 5-minute timer",
    agents=[
        OrchestrationAgent(agent_id="jarvis", role="orchestrator", name="Jarvis", parent=None, level=0),
        OrchestrationAgent(agent_id="a1", role="research-agent", name="Research", parent="jarvis",
                           level=1, subtask="get current weather for Tokyo", skills=["web-research"]),
        OrchestrationAgent(agent_id="a2", role="productivity-agent", name="Productivity", parent="jarvis",
                           level=1, subtask="start a 5-minute timer", skills=["manage-timers"]),
    ],
    edges=[{"from": "jarvis", "to": "a1"}, {"from": "jarvis", "to": "a2"}],
)

CASES = [
    (MessageType.ORCHESTRATION_PLAN, _PLAN),
    (MessageType.ORCHESTRATION_AGENT_STATUS, OrchestrationAgentStatus(
        plan_id="P1", agent_id="a1", role="research-agent", parent="jarvis", level=1,
        state="working", skill="web-research", label="Looking up Tokyo weather…", progress=0.5)),
    (MessageType.ORCHESTRATION_HANDOFF, OrchestrationHandoff(
        plan_id="P1", from_agent="a1", to_agent="a1.1", to_role="summarizer", level=2,
        subtask="summarize the 3 sources into one forecast", reason="delegating summarization")),
]


@pytest.mark.parametrize("type_name,payload", CASES, ids=[c[0] for c in CASES])
def test_orchestration_roundtrip_and_validate(type_name, payload):
    msg = jp.new_message(type_name, payload, session="S")
    assert msg.v == "1.3.0"
    decoded = jp.decode(jp.encode(msg))
    assert decoded.type == type_name
    assert jp.to_dict(decoded) == jp.to_dict(msg)
    jp.validate(msg, allow_unknown_types=False)  # raises on failure
    assert jp.is_valid(msg)


@pytest.mark.parametrize("type_name,payload", CASES, ids=[c[0] for c in CASES])
def test_orchestration_typed_parse(type_name, payload):
    msg = jp.new_message(type_name, payload, session="S")
    assert type(jp.parse_payload(msg.type, msg.payload)) is type(payload)


def test_agent_thinking_attribution_fields():
    # agent.thinking MAY carry agent_id/role/skill (additive, §9.1).
    msg = jp.new_message("agent.thinking", {
        "stage": "looking", "label": "Identifying…", "tool": "identify_object",
        "agent_id": "a3", "role": "perception-agent", "skill": "identify-object",
    }, session="S")
    jp.validate(msg, allow_unknown_types=False)
    assert jp.is_valid(msg)


def _msg(type_name, payload, **env):
    base = {"v": "1.2.0", "id": "m1", "type": type_name, "ts": 1, "session": "S", "payload": payload}
    base.update(env)
    return base


@pytest.mark.parametrize(
    "bad",
    [
        _msg("orchestration.plan", {"goal": "g", "agents": []}),  # missing plan_id
        _msg("orchestration.plan", {"plan_id": "P", "goal": "g", "agents": [{"role": "x", "level": 1}]}),  # agent missing agent_id
        _msg("orchestration.agent_status", {"plan_id": "P", "agent_id": "a1", "role": "r"}),  # missing state
        _msg("orchestration.agent_status", {"plan_id": "P", "agent_id": "a1", "role": "r", "state": "napping"}),  # bad state enum
        _msg("orchestration.handoff", {"plan_id": "P", "from_agent": "a1", "to_agent": "a1.1"}),  # missing to_role
    ],
)
def test_malformed_orchestration_rejected(bad):
    assert not jp.is_valid(bad)
    with pytest.raises(ProtocolValidationError) as ei:
        jp.validate(bad)
    assert ei.value.errors


def test_version_is_1_2_0_and_backward_compatible():
    assert jp.PROTOCOL_VERSION == "1.3.0"
    for v in ("1.0.0", "1.1.0", "1.2.0"):
        assert v in jp.SUPPORTED_VERSIONS
    # older clients are still accepted on the wire
    v1 = '{"v":"1.0.0","id":"a1","type":"agent.speech","ts":1,"session":"S","payload":{"text":"hi","final":true}}'
    jp.validate(v1, allow_unknown_types=False)
    v11 = '{"v":"1.1.0","id":"a1","type":"agent.observation","ts":1,"session":"S","payload":{"text":"hi"}}'
    jp.validate(v11, allow_unknown_types=False)


def test_section_9_2_plan_example_validates():
    example = {
        "plan_id": "plan-1",
        "goal": "show the weather in Tokyo and start a 5-minute timer",
        "agents": [
            {"agent_id": "jarvis", "role": "orchestrator", "name": "Jarvis", "parent": None, "level": 0},
            {"agent_id": "a1", "role": "research-agent", "name": "Research", "parent": "jarvis",
             "level": 1, "subtask": "get current weather for Tokyo", "skills": ["web-research"]},
            {"agent_id": "a2", "role": "productivity-agent", "name": "Productivity", "parent": "jarvis",
             "level": 1, "subtask": "start a 5-minute timer", "skills": ["manage-timers"]},
        ],
        "edges": [{"from": "jarvis", "to": "a1"}, {"from": "jarvis", "to": "a2"}],
    }
    jp.validate(_msg("orchestration.plan", example), allow_unknown_types=False)
