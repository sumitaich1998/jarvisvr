"""The PROTOCOL.md §7 reference example must parse and validate exactly.

These lines are copied verbatim from docs/PROTOCOL.md §7. They intentionally use
short non-UUID ids ("a1", "S", "O1"), so the schemas must NOT enforce UUID format.
"""

from __future__ import annotations

import json

import jarvis_protocol as jp
from jarvis_protocol import AgentSpeech, AgentThinking, HoloObject, TextInput

# --- verbatim from docs/PROTOCOL.md §7 ---
REFERENCE = [
    '{"v":"1.0.0","id":"a1","type":"user.voice_transcript","ts":1,"session":"S","payload":{"text":"weather in tokyo"}}',
    '{"v":"1.0.0","id":"b1","type":"agent.thinking","ts":2,"session":"S","payload":{"stage":"tool_call","tool":"get_weather"}}',
    '{"v":"1.0.0","id":"b2","type":"agent.speech","ts":3,"session":"S","payload":{"text":"Here\'s Tokyo.","final":true}}',
    '{"v":"1.0.0","id":"b3","type":"holo.spawn","ts":4,"session":"S","payload":{"object_id":"O1","widget_type":"weather_orb","transform":{"anchor":"head","position":[0.3,0,0.8],"rotation":[0,0,0,1],"scale":[1,1,1],"billboard":true},"props":{"city":"Tokyo","temp_c":18,"condition":"clouds"},"interactable":true,"interactions":["grab","tap"]}}',
    '{"v":"1.0.0","id":"c1","type":"client.ack","ts":5,"session":"S","reply_to":"b3","payload":{}}',
]


def test_reference_messages_decode_and_validate():
    for line in REFERENCE:
        env = jp.decode(line)
        assert env.v == "1.0.0"
        assert env.session == "S"
        # strict-type validation: every line is a known v1 message
        jp.validate(line, allow_unknown_types=False)
        assert jp.is_valid(env)


def test_reference_payloads_parse_into_typed_models():
    env0 = jp.decode(REFERENCE[0])
    assert isinstance(jp.parse_payload(env0.type, env0.payload), TextInput)

    env1 = jp.decode(REFERENCE[1])
    thinking = jp.parse_payload(env1.type, env1.payload)
    assert isinstance(thinking, AgentThinking)
    assert thinking.stage == "tool_call" and thinking.tool == "get_weather"

    env2 = jp.decode(REFERENCE[2])
    speech = jp.parse_payload(env2.type, env2.payload)
    assert isinstance(speech, AgentSpeech)
    assert speech.text == "Here's Tokyo." and speech.final is True

    env3 = jp.decode(REFERENCE[3])
    holo = jp.parse_payload(env3.type, env3.payload)
    assert isinstance(holo, HoloObject)
    assert holo.object_id == "O1"
    assert holo.widget_type == "weather_orb"
    assert holo.transform.anchor == "head"
    assert holo.transform.billboard is True
    assert holo.props["city"] == "Tokyo"


def test_reference_ack_reply_to_correlates():
    env = jp.decode(REFERENCE[4])
    assert env.type == "client.ack"
    assert env.reply_to == "b3"
    assert env.payload == {}


def test_reference_lines_are_valid_json():
    for line in REFERENCE:
        json.loads(line)  # no exception
