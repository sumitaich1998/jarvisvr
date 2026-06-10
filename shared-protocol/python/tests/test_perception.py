"""v1.1 Multimodal Perception: round-trip, schema validation, and the §8.6 example."""

from __future__ import annotations

import pytest

import jarvis_protocol as jp
from jarvis_protocol import (
    AgentObservation,
    Annotation,
    AudioEvent,
    AudioScene,
    Gaze,
    Intrinsics,
    MessageType,
    PerceptionRequest,
    PerceptionState,
    Pose,
    ProtocolValidationError,
    SceneObject,
    SceneObjects,
    SoundLabel,
    StreamState,
    TextInput,
    VisionFrame,
    VisionStreamState,
)

PERCEPTION_CASES = [
    (MessageType.PERCEPTION_VISION_FRAME, VisionFrame(
        frame_id="F1", camera="rgb_center", format="jpeg", width=1024, height=1024,
        quality=70, transport="inline", data="/9j/4AAQ", seq=1, ts_capture=2,
        pose=Pose(position=[0, 1.6, 0], rotation=[0, 0, 0, 1]),
        intrinsics=Intrinsics(fx=720, fy=720, cx=512, cy=512),
    )),
    (MessageType.PERCEPTION_AUDIO_EVENT, AudioEvent(label="doorbell", confidence=0.82, ts=10, loudness_db=-22.0)),
    (MessageType.PERCEPTION_AUDIO_SCENE, AudioScene(
        ambient_transcript="…overheard…", speaker="other",
        sounds=[SoundLabel(label="music", confidence=0.6)], loudness_db=-30.0, window_ms=4000,
    )),
    (MessageType.PERCEPTION_GAZE, Gaze(source="eyes", origin=[0, 1.6, 0], direction=[0, 0, 1], hit_object_id=None, hit_point=[0.2, 1.3, 0.9], dwell_ms=600)),
    (MessageType.PERCEPTION_SCENE_OBJECTS, SceneObjects(objects=[
        SceneObject(label="coffee mug", confidence=0.78, bbox=[120, 80, 64, 64], position=[0.3, 0.8, 0.7], anchor="world"),
    ])),
    (MessageType.PERCEPTION_STATE, PerceptionState(
        vision=VisionStreamState(active=True, fps=2, resolution="1024x1024", camera="rgb_center"),
        ambient_audio=StreamState(active=True), gaze=StreamState(active=False), thermal="nominal", battery=0.74,
    )),
    (MessageType.PERCEPTION_REQUEST, PerceptionRequest(stream="vision", action="start", fps=2, reason="user asked")),
    (MessageType.AGENT_OBSERVATION, AgentObservation(
        text="I can see a coffee mug and a laptop on your desk.", final=True,
        annotations=[Annotation(label="coffee mug", object_id="O9", position=[0.3, 0.8, 0.7], anchor="world")],
    )),
]


@pytest.mark.parametrize("type_name,payload", PERCEPTION_CASES, ids=[c[0] for c in PERCEPTION_CASES])
def test_perception_roundtrip_and_validate(type_name, payload):
    msg = jp.new_message(type_name, payload, session="S")
    assert msg.v == "1.3.0"
    wire = jp.encode(msg)
    decoded = jp.decode(wire)
    assert decoded.type == type_name
    assert jp.to_dict(decoded) == jp.to_dict(msg)
    jp.validate(msg, allow_unknown_types=False)  # raises on failure
    assert jp.is_valid(msg)


@pytest.mark.parametrize("type_name,payload", PERCEPTION_CASES, ids=[c[0] for c in PERCEPTION_CASES])
def test_perception_typed_parse(type_name, payload):
    msg = jp.new_message(type_name, payload, session="S")
    parsed = jp.parse_payload(msg.type, msg.payload)
    assert type(parsed) is type(payload)


def _msg(type_name, payload, **env):
    base = {"v": "1.1.0", "id": "m1", "type": type_name, "ts": 1, "session": "S", "payload": payload}
    base.update(env)
    return base


@pytest.mark.parametrize(
    "bad",
    [
        _msg("perception.vision_frame", {"frame_id": "F1", "format": "jpeg"}),               # missing camera
        _msg("perception.vision_frame", {"frame_id": "F1", "camera": "rgb_back", "format": "jpeg"}),  # bad camera enum
        _msg("perception.vision_frame", {"frame_id": "F1", "camera": "rgb_center", "format": "tiff"}),  # bad format
        _msg("perception.request", {"stream": "vision"}),                                     # missing action
        _msg("perception.request", {"stream": "smell", "action": "start"}),                   # bad stream enum
        _msg("perception.request", {"stream": "vision", "action": "blink"}),                  # bad action enum
        _msg("perception.gaze", {"origin": [0, 0, 0]}),                                        # missing direction
        _msg("perception.scene_objects", {"objects": [{"confidence": 0.5}]}),                  # object missing label
        _msg("agent.observation", {"final": True}),                                            # missing text
        _msg("perception.state", {"vision": {"fps": 2}}),                                       # vision missing active
    ],
)
def test_malformed_perception_rejected(bad):
    assert not jp.is_valid(bad)
    with pytest.raises(ProtocolValidationError) as ei:
        jp.validate(bad)
    assert ei.value.errors


# --- PROTOCOL.md §8.6 realtime multimodal turn (verbatim) ---
SECTION_8_6 = '''
// server enables sight when the user starts asking about the room
{"v":"1.1.0","id":"r1","type":"perception.request","ts":1,"session":"S","payload":{"stream":"vision","action":"start","fps":2,"reason":"user asked what they're looking at"}}
// client streams frames (binary on /vision, or inline as below)
{"v":"1.1.0","id":"f1","type":"perception.vision_frame","ts":2,"session":"S","payload":{"frame_id":"F1","camera":"rgb_center","format":"jpeg","width":1024,"height":1024,"transport":"inline","data":"/9j/4AAQ…","seq":1,"ts_capture":2,"pose":{"position":[0,1.6,0],"rotation":[0,0,0,1]}}}
// user (voice) — perception auto-attached
{"v":"1.1.0","id":"u1","type":"user.voice_transcript","ts":3,"session":"S","payload":{"text":"hey jarvis, what is this on my desk?","attach_perception":true}}
// agent perceives, answers, and annotates the real object
{"v":"1.1.0","id":"o1","type":"agent.observation","ts":4,"session":"S","payload":{"text":"That's a ceramic coffee mug.","final":true,"annotations":[{"label":"coffee mug","position":[0.3,0.8,0.7],"anchor":"world"}]}}
{"v":"1.1.0","id":"o2","type":"holo.spawn","ts":5,"session":"S","payload":{"object_id":"O9","widget_type":"vision_annotation","transform":{"anchor":"world","position":[0.3,0.95,0.7],"rotation":[0,0,0,1],"scale":[1,1,1],"billboard":true},"props":{"label":"coffee mug","confidence":0.78},"interactable":true,"interactions":["tap"]}}
{"v":"1.1.0","id":"o3","type":"agent.speech","ts":6,"session":"S","payload":{"text":"Looks like your coffee mug — want me to set a reminder to refill it?","final":true}}
// server stops the camera when done (privacy/battery)
{"v":"1.1.0","id":"r2","type":"perception.request","ts":7,"session":"S","payload":{"stream":"vision","action":"stop"}}
'''

REFERENCE_8_6 = [ln.strip() for ln in SECTION_8_6.splitlines() if ln.strip() and not ln.strip().startswith("//")]


def test_section_8_6_lines_decode_and_validate():
    assert len(REFERENCE_8_6) == 7
    for line in REFERENCE_8_6:
        env = jp.decode(line)
        assert env.v == "1.1.0" and env.session == "S"
        jp.validate(line, allow_unknown_types=False)  # raises on any violation
        assert jp.is_valid(env)


def test_section_8_6_typed_payloads():
    by_id = {jp.decode(ln).id: jp.decode(ln) for ln in REFERENCE_8_6}
    vf = jp.parse_payload(by_id["f1"].type, by_id["f1"].payload)
    assert isinstance(vf, VisionFrame) and vf.transport == "inline" and vf.camera == "rgb_center"
    obs = jp.parse_payload(by_id["o1"].type, by_id["o1"].payload)
    assert isinstance(obs, AgentObservation) and obs.annotations[0].label == "coffee mug"
    u = jp.parse_payload(by_id["u1"].type, by_id["u1"].payload)
    assert isinstance(u, TextInput) and u.attach_perception is True


def test_version_is_1_1_0_and_backward_compatible():
    assert jp.PROTOCOL_VERSION == "1.3.0"
    assert "1.0.0" in jp.SUPPORTED_VERSIONS and "1.1.0" in jp.SUPPORTED_VERSIONS
    # a v1.0.0 envelope is still accepted
    v1 = '{"v":"1.0.0","id":"a1","type":"agent.speech","ts":1,"session":"S","payload":{"text":"hi","final":true}}'
    jp.validate(v1, allow_unknown_types=False)
    # but an unsupported version is rejected
    assert not jp.is_valid('{"v":"2.0.0","id":"a1","type":"agent.speech","ts":1,"payload":{"text":"hi"}}')
