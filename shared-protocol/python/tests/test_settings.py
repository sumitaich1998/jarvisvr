"""v1.1 §5.15 Settings: round-trip, schema validation, and the no-key-leak rule."""

from __future__ import annotations

import json

import pytest

import jarvis_protocol as jp
from jarvis_protocol import (
    ClientSettingsGet,
    ClientSettingsUpdate,
    CurrentLlm,
    LlmSettings,
    LlmSettingsUpdate,
    MessageType,
    ProtocolValidationError,
    ProviderCapabilities,
    ProviderEntry,
    ServerSettings,
)

_SERVER_SETTINGS = ServerSettings(
    llm=LlmSettings(
        current=CurrentLlm(provider="openai", model="gpt-4o", base_url=None, key_set=True),
        providers=[
            ProviderEntry(
                id="openai", name="OpenAI", default_model="gpt-4o",
                models=["gpt-4o", "gpt-4o-mini"], needs_key=True, needs_base_url=False,
                key_set=True, capabilities=ProviderCapabilities(tools=True, vision=True),
            ),
            ProviderEntry(
                id="ollama", name="Ollama (local)", default_model="llama3.1",
                needs_key=False, needs_base_url=True, key_set=False,
                capabilities=ProviderCapabilities(tools=True, vision=False),
            ),
        ],
    )
)

SETTINGS_CASES = [
    (MessageType.CLIENT_SETTINGS_GET, ClientSettingsGet(section="llm")),
    (MessageType.CLIENT_SETTINGS_UPDATE, ClientSettingsUpdate(
        llm=LlmSettingsUpdate(provider="openai", model="gpt-4o", base_url=None, api_key="sk-secret"))),
    (MessageType.SERVER_SETTINGS, _SERVER_SETTINGS),
]


@pytest.mark.parametrize("type_name,payload", SETTINGS_CASES, ids=[c[0] for c in SETTINGS_CASES])
def test_settings_roundtrip_and_validate(type_name, payload):
    msg = jp.new_message(type_name, payload, session="S")
    assert msg.v == "1.3.0"
    decoded = jp.decode(jp.encode(msg))
    assert decoded.type == type_name
    assert jp.to_dict(decoded) == jp.to_dict(msg)
    jp.validate(msg, allow_unknown_types=False)  # raises on failure
    assert jp.is_valid(msg)


def test_settings_typed_parse():
    for type_name, payload in SETTINGS_CASES:
        msg = jp.new_message(type_name, payload, session="S")
        assert type(jp.parse_payload(msg.type, msg.payload)) is type(payload)


def _msg(type_name, payload, **env):
    base = {"v": "1.1.0", "id": "m1", "type": type_name, "ts": 1, "session": "S", "payload": payload}
    base.update(env)
    return base


def test_server_settings_never_contains_api_key():
    """SECURITY: server.settings is a closed schema, so an api_key anywhere fails."""
    placements = [
        {"llm": {"current": {"provider": "openai", "model": "gpt-4o", "key_set": True, "api_key": "sk-x"},
                 "providers": []}},
        {"llm": {"current": {"provider": "openai", "model": "gpt-4o", "key_set": True},
                 "providers": [{"id": "openai", "name": "OpenAI", "default_model": "gpt-4o",
                                "needs_key": True, "needs_base_url": False, "key_set": True,
                                "capabilities": {"tools": True, "vision": True}, "api_key": "sk-x"}]}},
        {"llm": {"api_key": "sk-x", "current": {"provider": "openai", "model": "gpt-4o", "key_set": True},
                 "providers": []}},
    ]
    for p in placements:
        bad = _msg("server.settings", p)
        assert not jp.is_valid(bad), f"api_key should be rejected: {p}"
        with pytest.raises(ProtocolValidationError):
            jp.validate(bad)
    # And the canonical (key-free) shape is valid.
    assert jp.is_valid(_msg("server.settings", jp.to_dict(_SERVER_SETTINGS_payload())))


def _SERVER_SETTINGS_payload():
    # helper: the payload dict of a valid server.settings
    return jp.new_message("server.settings", _SERVER_SETTINGS).payload


@pytest.mark.parametrize(
    "bad",
    [
        _msg("server.settings", {}),  # missing llm
        _msg("server.settings", {"llm": {"providers": []}}),  # missing current
        _msg("server.settings", {"llm": {"current": {"provider": "openai", "model": "x"}, "providers": []}}),  # current missing key_set
        _msg("client.settings_get", {"section": "everything"}),  # bad section enum
    ],
)
def test_malformed_settings_rejected(bad):
    assert not jp.is_valid(bad)
    with pytest.raises(ProtocolValidationError) as ei:
        jp.validate(bad)
    assert ei.value.errors


def test_section_5_15_server_settings_example_validates():
    # Mirrors the PROTOCOL.md §5.15 server.settings example shape.
    example = {
        "llm": {
            "current": {"provider": "openai", "model": "gpt-4o", "base_url": None, "key_set": True},
            "providers": [
                {"id": "openai", "name": "OpenAI", "default_model": "gpt-4o",
                 "models": ["gpt-4o", "gpt-4o-mini"], "needs_key": True, "needs_base_url": False,
                 "key_set": True, "capabilities": {"tools": True, "vision": True}},
                {"id": "anthropic", "name": "Anthropic", "default_model": "claude-3-7-sonnet",
                 "needs_key": True, "needs_base_url": False, "key_set": False,
                 "capabilities": {"tools": True, "vision": True}},
                {"id": "ollama", "name": "Ollama (local)", "default_model": "llama3.1",
                 "needs_key": False, "needs_base_url": True, "key_set": False,
                 "capabilities": {"tools": True, "vision": False}},
            ],
        }
    }
    jp.validate(_msg("server.settings", example), allow_unknown_types=False)
    assert "api_key" not in json.dumps(example)
