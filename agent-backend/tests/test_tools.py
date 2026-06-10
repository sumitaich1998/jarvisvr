"""Tool registry + built-in tool tests."""

from __future__ import annotations

from pathlib import Path

from jarvis_backend.agent.state import SessionState
from jarvis_backend.agent.tools import (
    DestroyDirective,
    SpawnDirective,
    ToolContext,
    build_default_registry,
)
from jarvis_backend.agent.memory import LongTermStore
from jarvis_backend.catalog import WidgetCatalog
from jarvis_backend.config import Config


def _ctx(tmp_path: Path) -> ToolContext:
    config = Config(holo_registry_path=None, data_dir=Path(tmp_path))
    return ToolContext(
        config=config,
        session=SessionState(session_id="S"),
        catalog=WidgetCatalog.builtin(),
        longterm=LongTermStore(Path(tmp_path) / "ltm.json"),
    )


async def test_get_weather_mock_deterministic(tmp_path):
    reg = build_default_registry()
    res = await reg.run("get_weather", {"city": "tokyo"}, _ctx(tmp_path))
    assert res.ok
    assert res.data["city"] == "Tokyo"
    assert res.data["temp_c"] == 18
    assert res.data["condition"] == "clouds"
    assert res.directives and isinstance(res.directives[0], SpawnDirective)
    assert res.directives[0].widget_type == "weather_orb"


async def test_start_and_stop_timer(tmp_path):
    reg = build_default_registry()
    ctx = _ctx(tmp_path)
    res = await reg.run("start_timer", {"duration_seconds": 300}, ctx)
    assert res.ok
    spawn = res.directives[0]
    assert isinstance(spawn, SpawnDirective)
    assert spawn.widget_type == "timer"
    assert spawn.props["duration_ms"] == 300_000
    assert spawn.props["state"] == "running"

    stop = await reg.run("stop_timer", {}, ctx)
    assert stop.ok
    assert isinstance(stop.directives[0], DestroyDirective)


async def test_notes_roundtrip(tmp_path):
    reg = build_default_registry()
    ctx = _ctx(tmp_path)
    await reg.run("take_note", {"text": "buy milk"}, ctx)
    await reg.run("take_note", {"text": "call mom"}, ctx)
    listing = await reg.run("list_notes", {}, ctx)
    assert listing.data["count"] == 2
    assert "buy milk" in listing.data["notes"]
    # Persisted to long-term store.
    assert len(ctx.longterm.get("notes")) == 2


async def test_open_widget_unknown_is_graceful(tmp_path):
    reg = build_default_registry()
    res = await reg.run("open_widget", {"widget_type": "nonexistent"}, _ctx(tmp_path))
    assert res.error == "unknown_widget"
    assert not res.directives
    assert "nonexistent" in res.data["speech"]


async def test_open_widget_known(tmp_path):
    reg = build_default_registry()
    res = await reg.run(
        "open_widget",
        {"widget_type": "chart_3d", "props": {"series": [1, 2, 3]}},
        _ctx(tmp_path),
    )
    assert res.ok
    assert res.directives[0].widget_type == "chart_3d"


def test_registry_specs_are_function_schemas():
    reg = build_default_registry()
    specs = {s.name: s for s in reg.specs()}
    assert "get_weather" in specs
    assert specs["get_weather"].parameters["type"] == "object"
    assert "city" in specs["get_weather"].parameters["properties"]
