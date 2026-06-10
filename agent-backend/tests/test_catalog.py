"""Widget catalog loader + validation tests.

Exercises the *canonical* holo-tools registry.json shape (a list of widget
entries with JSON-Schema props_schema and additionalProperties:false), plus the
built-in fallback.
"""

from __future__ import annotations

import json

import pytest

from jarvis_backend import protocol
from jarvis_backend.agent import Agent
from jarvis_backend.agent.llm import MockLLM
from jarvis_backend.catalog import CatalogError, WidgetCatalog
from jarvis_backend.config import Config

# Minimal canonical-shaped registry (mirrors holo-tools/registry.json).
CANONICAL = {
    "version": "1.0.0",
    "widgets": [
        {
            "widget_type": "weather_orb",
            "prefab_id": "Holo_WeatherOrb",
            "interactions": ["tap", "grab", "resize", "dwell"],
            "default_transform": {
                "anchor": "head",
                "position": [0.45, 0.1, 0.9],
                "rotation": [0, 0, 0, 1],
                "scale": [1, 1, 1],
                "billboard": True,
            },
            "props_schema": {
                "type": "object",
                "additionalProperties": False,
                "required": ["city", "temp_c", "condition"],
                "properties": {
                    "city": {"type": "string"},
                    "temp_c": {"type": "number"},
                    "condition": {
                        "type": "string",
                        "enum": ["clear", "clouds", "rain", "snow", "fog", "wind", "storm"],
                    },
                    "humidity_pct": {"type": "integer"},
                    "wind_kph": {"type": "number"},
                    "unit": {"type": "string", "enum": ["c", "f"]},
                },
            },
        },
        {
            "widget_type": "timer",
            "prefab_id": "Holo_Timer",
            "interactions": ["tap", "grab", "resize"],
            "default_transform": {
                "anchor": "head",
                "position": [-0.45, 0.1, 0.9],
                "rotation": [0, 0, 0, 1],
                "scale": [1, 1, 1],
                "billboard": True,
            },
            "props_schema": {
                "type": "object",
                "additionalProperties": False,
                "required": ["duration_ms", "remaining_ms", "state"],
                "properties": {
                    "label": {"type": "string"},
                    "duration_ms": {"type": "integer"},
                    "remaining_ms": {"type": "integer"},
                    "state": {
                        "type": "string",
                        "enum": ["idle", "running", "paused", "completed"],
                    },
                    "mode": {"type": "string"},
                },
            },
        },
    ],
}


def test_parses_list_shaped_registry():
    cat = WidgetCatalog(CANONICAL, source="test")
    assert cat.has("weather_orb") and cat.has("timer")
    assert cat.get("weather_orb").prefab_id == "Holo_WeatherOrb"
    assert "dwell" in cat.supported_interactions("weather_orb")
    assert cat.default_transform("timer")["anchor"] == "head"


def test_validate_canonical_props_ok():
    cat = WidgetCatalog(CANONICAL)
    cat.validate(
        "weather_orb",
        {"city": "Tokyo", "temp_c": 18, "condition": "clouds", "humidity_pct": 64, "wind_kph": 12, "unit": "c"},
    )
    cat.validate(
        "timer",
        {"label": "Tea", "duration_ms": 300000, "remaining_ms": 142000, "state": "running"},
    )


def test_validate_rejects_unknown_prop_when_closed():
    cat = WidgetCatalog(CANONICAL)
    with pytest.raises(CatalogError):
        cat.validate("weather_orb", {"city": "Tokyo", "temp_c": 18, "condition": "clouds", "humidity": 64})


def test_validate_rejects_bad_enum():
    cat = WidgetCatalog(CANONICAL)
    with pytest.raises(CatalogError):
        cat.validate("weather_orb", {"city": "Tokyo", "temp_c": 18, "condition": "sunny"})


def test_validate_unknown_widget_and_missing_required():
    cat = WidgetCatalog(CANONICAL)
    with pytest.raises(CatalogError):
        cat.validate("nonexistent", {})
    with pytest.raises(CatalogError):
        cat.validate("weather_orb", {"city": "Tokyo"})  # missing temp_c, condition


def test_load_from_file(tmp_path):
    p = tmp_path / "registry.json"
    p.write_text(json.dumps(CANONICAL))
    cat = WidgetCatalog.load(p)
    assert cat.has("weather_orb")
    assert cat.version == "1.0.0"


def test_load_missing_file_uses_fallback(tmp_path):
    cat = WidgetCatalog.load(tmp_path / "does_not_exist.json")
    assert "builtin" in cat.source
    assert cat.has("weather_orb")


async def test_agent_spawns_valid_props_against_canonical_registry(tmp_path):
    """The tools' props must validate against the canonical (closed) schemas."""
    p = tmp_path / "registry.json"
    p.write_text(json.dumps(CANONICAL))
    config = Config(holo_registry_path=p, data_dir=tmp_path, llm_provider="mock")
    agent = Agent.build(config, MockLLM())

    sent: list[protocol.Envelope] = []

    async def emit(type, payload=None, *, reply_to=None):
        sent.append(protocol.make(type, payload))

    session = agent.create_session("S", emit)
    await session.handle_user_text("show weather in tokyo and start a 5 minute timer")

    errors = [e for e in sent if e.type == "server.error"]
    assert not errors, f"props failed canonical validation: {[e.payload for e in errors]}"

    spawns = [e for e in sent if e.type == "holo.spawn"]
    widget_types = {s.payload["widget_type"] for s in spawns}
    assert {"weather_orb", "timer"} <= widget_types
