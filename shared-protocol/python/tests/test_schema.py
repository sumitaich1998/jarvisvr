"""Schema validation: good messages pass, malformed ones are rejected."""

from __future__ import annotations

import pytest

import jarvis_protocol as jp
from jarvis_protocol import ProtocolValidationError


def _msg(type_name, payload, **env):
    base = {"v": "1.0.0", "id": "m1", "type": type_name, "ts": 1, "session": "S", "payload": payload}
    base.update(env)
    return base


def test_valid_messages_pass():
    assert jp.is_valid(_msg("agent.speech", {"text": "hi", "final": True}))
    assert jp.is_valid(_msg("client.heartbeat", {}))
    assert jp.is_valid(_msg("client.ack", {}, reply_to="b3"))


@pytest.mark.parametrize(
    "bad",
    [
        # bad envelope: wrong protocol version
        _msg("agent.speech", {"text": "hi"}, v="2.0.0"),
        # bad envelope: unexpected top-level key (additionalProperties: false)
        _msg("agent.speech", {"text": "hi"}, surprise=1),
        # bad envelope: ts not an integer
        _msg("agent.speech", {"text": "hi"}, ts="nope"),
        # missing required payload field
        _msg("agent.speech", {"final": True}),
        # bad enum value
        _msg("agent.thinking", {"stage": "daydreaming"}),
        # client.interaction missing required action
        _msg("client.interaction", {"object_id": "O1"}),
        # holo.spawn missing a required transform field (no rotation)
        _msg("holo.spawn", {
            "object_id": "O1", "widget_type": "weather_orb",
            "transform": {"anchor": "head", "position": [0, 0, 0], "scale": [1, 1, 1]},
        }),
        # holo.spawn vec3 wrong length
        _msg("holo.spawn", {
            "object_id": "O1", "widget_type": "weather_orb",
            "transform": {"anchor": "head", "position": [0, 0], "rotation": [0, 0, 0, 1], "scale": [1, 1, 1]},
        }),
        # holo.spawn bad anchor enum
        _msg("holo.spawn", {
            "object_id": "O1", "widget_type": "weather_orb",
            "transform": {"anchor": "ceiling", "position": [0, 0, 0], "rotation": [0, 0, 0, 1], "scale": [1, 1, 1]},
        }),
        # error payload missing message
        _msg("server.error", {"code": "internal"}),
        # holo.layout bad arrangement
        _msg("holo.layout", {"arrangement": "spiral", "objects": ["O1"]}),
    ],
)
def test_malformed_messages_rejected(bad):
    assert not jp.is_valid(bad)
    with pytest.raises(ProtocolValidationError) as ei:
        jp.validate(bad)
    assert ei.value.errors  # carries a non-empty list of reasons


def test_missing_required_envelope_field():
    bad = {"v": "1.0.0", "type": "agent.speech", "ts": 1, "payload": {"text": "hi"}}  # no id
    errors = jp.iter_errors(bad)
    assert any("id" in e for e in errors)


def test_unknown_type_policy():
    msg = _msg("vendor.future_thing", {"anything": True})
    # default: unknown types are tolerated (forward-compatible)
    assert jp.is_valid(msg)
    # strict: unknown types are flagged
    assert not jp.is_valid(msg, allow_unknown_types=False)
    with pytest.raises(ProtocolValidationError):
        jp.validate(msg, allow_unknown_types=False)


def test_reference_holo_object_schema_directly():
    schemas = jp.load_schemas()
    assert "holo_object.schema.json" in schemas
    assert "envelope.schema.json" in schemas
    assert jp.PROTOCOL_VERSION == "1.3.0"
