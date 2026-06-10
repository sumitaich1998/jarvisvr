"""Exhaustive catalog/models coverage: every v1.0-v1.3 message type round-trips,
validates strictly against its schema, and parses into the right pydantic model.
Plus the version enum (1.0.0-1.3.0) and catalog/registry consistency."""

from __future__ import annotations

import pytest

import jarvis_protocol as jp
from jarvis_protocol import PAYLOAD_MODELS, TYPE_TO_SCHEMA, MessageType

MT = MessageType

# A minimal-but-valid payload for every message type in the catalog. Nested
# objects are included where useful so the nested models get exercised too.
VALID_PAYLOADS = {
    MT.CLIENT_HELLO: {"device": "quest3", "protocol_version": "1.3.0",
                      "capabilities": {"mic": True, "camera_passthrough": True}, "locale": "en-US"},
    MT.CLIENT_BYE: {"reason": "done"},
    MT.CLIENT_HEARTBEAT: {},
    MT.USER_TEXT: {"text": "hello", "confidence": 0.9, "attach_perception": True},
    MT.USER_VOICE_TRANSCRIPT: {"text": "weather in tokyo", "confidence": 0.97},
    MT.USER_VOICE_PARTIAL: {"text": "weath"},
    MT.CLIENT_INTERACTION: {"object_id": "O1", "widget_type": "timer", "action": "tap",
                            "element": "pause_button", "value": {"x": 1}, "hand": "right"},
    MT.CLIENT_SCENE: {"head": {"position": [0, 1.6, 0], "rotation": [0, 0, 0, 1]},
                      "surfaces": [{"id": "floor", "type": "floor", "center": [0, 0, 0], "normal": [0, 1, 0]}],
                      "anchors": [{"id": "a1", "position": [0, 0, 0], "rotation": [0, 0, 0, 1]}]},
    MT.CLIENT_ACK: {},
    MT.CLIENT_ERROR: {"code": "internal", "message": "boom", "fatal": False},
    MT.CLIENT_BARGE_IN: {"reason": "user_speech"},
    MT.SERVER_HELLO_ACK: {"session": "S", "protocol_version": "1.3.0",
                          "agent": {"name": "Jarvis", "model": "mock"}, "tools": ["get_weather"],
                          "voice": {"tts": True, "wake_word": "jarvis"}},
    MT.SERVER_HEARTBEAT: {},
    MT.AGENT_THINKING: {"stage": "tool_call", "tool": "get_weather", "label": "Calling",
                        "agent_id": "a0", "role": "researcher", "skill": "search"},
    MT.AGENT_SPEECH: {"text": "Here's Tokyo.", "final": True, "emotion": "neutral"},
    MT.AGENT_TRANSCRIPT: {"text": "weather in tokyo", "confidence": 0.95},
    MT.HOLO_SPAWN: {"object_id": "O1", "widget_type": "weather_orb",
                    "transform": {"anchor": "head", "position": [0.3, 0, 0.8], "rotation": [0, 0, 0, 1],
                                  "scale": [1, 1, 1], "billboard": True},
                    "props": {"city": "Tokyo"}, "interactable": True, "interactions": ["grab", "tap"], "ttl_ms": 0},
    MT.HOLO_UPDATE: {"object_id": "O1", "transform": {"position": [0, 1, 0]}, "props": {"temp_c": 19}},
    MT.HOLO_DESTROY: {"object_id": "O1", "fade_ms": 300},
    MT.HOLO_LAYOUT: {"arrangement": "arc", "anchor": "head", "objects": ["O1", "O2"], "spacing": 0.25},
    MT.SERVER_ERROR: {"code": "tool_failed", "message": "nope", "fatal": False},
    # --- v1.1 perception ---
    MT.PERCEPTION_VISION_FRAME: {"frame_id": "F1", "camera": "rgb_center", "format": "jpeg",
                                 "width": 1024, "height": 1024, "quality": 70, "transport": "inline",
                                 "data": "/9j/4AAQ", "seq": 1, "ts_capture": 2,
                                 "pose": {"position": [0, 1.6, 0], "rotation": [0, 0, 0, 1]},
                                 "intrinsics": {"fx": 720, "fy": 720, "cx": 512, "cy": 512}},
    MT.PERCEPTION_AUDIO_EVENT: {"label": "doorbell", "confidence": 0.82, "ts": 10, "loudness_db": -22.0},
    MT.PERCEPTION_AUDIO_SCENE: {"ambient_transcript": "...", "speaker": "other",
                                "sounds": [{"label": "music", "confidence": 0.6}],
                                "loudness_db": -30.0, "window_ms": 4000},
    MT.PERCEPTION_GAZE: {"source": "eyes", "origin": [0, 1.6, 0], "direction": [0, 0, 1],
                         "hit_object_id": None, "hit_point": [0.2, 1.3, 0.9], "dwell_ms": 600},
    MT.PERCEPTION_SCENE_OBJECTS: {"frame_id": "F1", "objects": [
        {"label": "coffee mug", "confidence": 0.78, "bbox": [120, 80, 64, 64], "position": [0.3, 0.8, 0.7], "anchor": "world"}]},
    MT.PERCEPTION_STATE: {"vision": {"active": True, "fps": 2, "resolution": "1024x1024", "camera": "rgb_center"},
                          "ambient_audio": {"active": True}, "gaze": {"active": False},
                          "thermal": "nominal", "battery": 0.74},
    MT.PERCEPTION_REQUEST: {"stream": "vision", "action": "start", "fps": 2, "max_resolution": "1024x1024",
                            "quality": 70, "duration_ms": 0, "reason": "user asked"},
    MT.AGENT_OBSERVATION: {"text": "I see a mug.", "final": True,
                           "annotations": [{"label": "coffee mug", "object_id": "O9", "position": [0.3, 0.8, 0.7], "anchor": "world"}]},
    # --- v1.1 settings (§5.15) ---
    MT.CLIENT_SETTINGS_GET: {"section": "llm"},
    MT.CLIENT_SETTINGS_UPDATE: {"llm": {"provider": "openai", "model": "gpt-4o", "base_url": None, "api_key": "sk-x"}},
    MT.SERVER_SETTINGS: {"llm": {"current": {"provider": "openai", "model": "gpt-4o", "base_url": None, "key_set": True},
                                 "providers": [{"id": "openai", "name": "OpenAI", "default_model": "gpt-4o",
                                                "models": ["gpt-4o"], "needs_key": True, "needs_base_url": False,
                                                "key_set": True, "capabilities": {"tools": True, "vision": True}}]}},
    # --- v1.2 orchestration (§9) ---
    MT.ORCHESTRATION_PLAN: {"plan_id": "P1", "goal": "research", "agents": [
        {"agent_id": "a0", "role": "orchestrator", "name": "L0", "parent": None, "level": 0,
         "subtask": "coordinate", "skills": ["plan"]}], "edges": [{"from": "a0", "to": "a1"}]},
    MT.ORCHESTRATION_AGENT_STATUS: {"plan_id": "P1", "agent_id": "a0", "role": "orchestrator", "parent": None,
                                    "level": 0, "state": "working", "skill": "plan", "label": "x", "progress": 0.5},
    MT.ORCHESTRATION_HANDOFF: {"plan_id": "P1", "from_agent": "a0", "to_agent": "a1", "to_role": "researcher",
                               "level": 1, "subtask": "search", "reason": "delegation"},
    # --- v1.3 tracing + authoring (§10) ---
    MT.CLIENT_TRACE_SUBSCRIBE: {"enabled": True},
    MT.CLIENT_TRACE_GET: {"plan_id": "P1"},
    MT.CLIENT_AGENT_INSPECT: {"role": "researcher", "agent_id": "a1"},
    MT.CLIENT_AUTHOR_LIST: {},
    MT.CLIENT_AUTHOR_SKILL: {"op": "create", "name": "summarize", "category": "research", "agent": "researcher",
                             "description": "d", "body": "...", "allowed_tools": ["web"], "license": "MIT",
                             "compatibility": ">=1.3"},
    MT.CLIENT_AUTHOR_AGENT: {"op": "create", "role": "researcher", "name": "R", "persona": "p",
                             "tools": ["web"], "skills": ["summarize"]},
    MT.ORCHESTRATION_TRACE_EVENT: {"plan_id": "P1", "seq": 1, "ts": 1, "agent_id": "a0", "role": "orchestrator",
                                   "parent": None, "level": 0, "kind": "tool_call", "label": "search",
                                   "skill": "s", "tool": "web", "detail": "...", "duration_ms": 12},
    MT.SERVER_TRACE: {"plan_id": "P1", "goal": "research",
                      "agents": [{"agent_id": "a0", "role": "orchestrator", "parent": None, "level": 0}],
                      "entries": [{"plan_id": "P1", "seq": 1, "ts": 1, "agent_id": "a0", "role": "orchestrator",
                                   "kind": "speech", "label": "hi"}]},
    MT.SERVER_AGENT_INFO: {"role": "researcher", "name": "R", "source": "builtin", "persona": "p",
                           "tools": ["web"], "skills": [{"name": "summarize", "description": "d", "source": "builtin"}],
                           "memory": {"summary": "s", "items": 3, "recent": [{"ts": 1, "text": "noted"}]}},
    MT.SERVER_AUTHORING: {"agents": [{"role": "researcher", "name": "R", "source": "builtin",
                                      "skills": ["summarize"], "tools": ["web"]}],
                          "skills": [{"name": "summarize", "agent": "researcher", "category": "research",
                                      "source": "builtin", "description": "d"}],
                          "categories": ["research"], "tools": ["web"]},
}


def test_every_catalog_type_has_a_test_payload():
    missing = set(TYPE_TO_SCHEMA) - set(VALID_PAYLOADS)
    assert not missing, f"no sample payload for: {sorted(missing)}"


@pytest.mark.parametrize("type_name", sorted(TYPE_TO_SCHEMA))
def test_message_type_roundtrips_validates_and_parses(type_name):
    payload = VALID_PAYLOADS[type_name]
    msg = jp.new_message(type_name, payload, session="S")
    # round-trip
    assert jp.to_dict(jp.decode(jp.encode(msg))) == jp.to_dict(msg)
    # strict schema validation (known type, valid payload)
    jp.validate(msg, allow_unknown_types=False)
    assert jp.is_valid(msg, allow_unknown_types=False)
    # parses into the right pydantic model
    model = jp.parse_payload(type_name, payload)
    assert isinstance(model, PAYLOAD_MODELS[type_name])


def test_catalog_and_registry_are_consistent():
    # Every MessageType constant is mapped to a schema + a model.
    consts = {v for k, v in vars(MessageType).items() if not k.startswith("_") and isinstance(v, str)}
    assert consts == set(TYPE_TO_SCHEMA), "MessageType constants and TYPE_TO_SCHEMA disagree"
    assert set(PAYLOAD_MODELS) == set(TYPE_TO_SCHEMA), "PAYLOAD_MODELS and TYPE_TO_SCHEMA disagree"
    assert jp.KNOWN_TYPES == frozenset(TYPE_TO_SCHEMA)
    # Every referenced schema file actually exists.
    schemas = jp.load_schemas()
    for type_name, filename in TYPE_TO_SCHEMA.items():
        assert filename in schemas, f"{type_name} -> {filename} missing from schema dir"


@pytest.mark.parametrize("version", list(jp.SUPPORTED_VERSIONS))
def test_supported_versions_validate(version):
    msg = {"v": version, "id": "a", "type": "client.heartbeat", "ts": 1, "session": "S", "payload": {}}
    jp.validate(msg, allow_unknown_types=False)


@pytest.mark.parametrize("version", ["0.9.0", "1.4.0", "2.0.0", "nope"])
def test_unsupported_versions_rejected(version):
    msg = {"v": version, "id": "a", "type": "client.heartbeat", "ts": 1, "session": "S", "payload": {}}
    assert not jp.is_valid(msg)


def test_unknown_type_tolerated_or_flagged():
    msg = {"v": "1.3.0", "id": "a", "type": "vendor.future", "ts": 1, "session": "S", "payload": {"x": 1}}
    assert jp.is_valid(msg)  # default: forward-compatible
    assert not jp.is_valid(msg, allow_unknown_types=False)  # strict: flagged


@pytest.mark.parametrize("type_name,bad_payload", [
    (MT.PERCEPTION_REQUEST, {"stream": "vision"}),                      # missing action
    (MT.PERCEPTION_REQUEST, {"stream": "smell", "action": "start"}),    # bad stream enum
    (MT.ORCHESTRATION_PLAN, {"goal": "g"}),                             # missing plan_id
    (MT.ORCHESTRATION_AGENT_STATUS, {"plan_id": "P", "agent_id": "a", "role": "r", "state": "vibing"}),  # bad state
    (MT.ORCHESTRATION_TRACE_EVENT, {"plan_id": "P", "seq": 1, "ts": 1, "agent_id": "a", "role": "r", "kind": "nope", "label": "L"}),  # bad kind
    (MT.CLIENT_AUTHOR_SKILL, {"name": "s"}),                            # missing op
    (MT.CLIENT_AUTHOR_AGENT, {"op": "frobnicate", "role": "r"}),        # bad op enum
    (MT.SERVER_SETTINGS, {"llm": {"current": {"provider": "x", "model": "y"}, "providers": []}}),  # current missing key_set
    (MT.SERVER_AGENT_INFO, {"name": "R"}),                              # missing role
])
def test_malformed_new_messages_rejected(type_name, bad_payload):
    assert not jp.is_valid({"v": "1.3.0", "id": "m", "type": type_name, "ts": 1, "session": "S", "payload": bad_payload})
