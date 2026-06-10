"""Regression tests for scripts/generate_docs.py pure helpers.

The generator lives outside the ``holo_tools`` package (so it is not part of the
measured coverage source) and its ``main()`` writes ``docs/HOLO_TOOLS.md`` outside
this directory, so we never call ``main()`` here -- we only exercise the pure,
side-effect-free string builders to guard against regressions.
"""

import importlib.util
from pathlib import Path

import pytest

import holo_tools as ht

_GEN_PATH = Path(__file__).resolve().parents[1] / "scripts" / "generate_docs.py"


@pytest.fixture(scope="module")
def gen():
    spec = importlib.util.spec_from_file_location("jarvis_generate_docs", _GEN_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_type_str_variants(gen):
    assert gen.type_str({"enum": ["a"]}) == "enum"
    assert gen.type_str({"type": "string"}) == "string"
    assert gen.type_str({"type": "array", "items": {"type": "number"}}) == "array&lt;number&gt;"
    assert gen.type_str({"type": "array", "items": {"type": "object"}}) == "array&lt;object&gt;"
    assert gen.type_str({"type": "array", "items": {"enum": ["x"]}}) == "array&lt;enum&gt;"
    assert gen.type_str({"type": "array"}) == "array"
    assert gen.type_str({"type": ["string", "number"]}) == "string \\| number"
    assert gen.type_str({}) == "any"


def test_constraints_str(gen):
    s = gen.constraints_str({"type": "integer", "minimum": 0, "maximum": 100})
    assert "min 0" in s and "max 100" in s
    assert "one of: `a`" in gen.constraints_str({"enum": ["a", "b"]})
    assert "format: uri" in gen.constraints_str({"type": "string", "format": "uri"})
    assert "hex/pattern" in gen.constraints_str({"type": "string", "pattern": "^#"})
    arr = gen.constraints_str(
        {"type": "array", "items": {"type": "object", "properties": {"x": {}}, "required": ["x"]}}
    )
    assert "items: {x*}" in arr
    enum_items = gen.constraints_str({"type": "array", "items": {"enum": ["m", "n"]}})
    assert "each: `m`" in enum_items
    obj_keys = gen.constraints_str(
        {"type": "object", "properties": {"a": {}, "b": {}}, "required": ["a"]}
    )
    assert "keys: {a*, b}" in obj_keys


def test_esc(gen):
    assert gen.esc("a|b\nc") == "a\\|b c"


def test_props_and_events_tables(gen):
    weather = ht.WIDGETS_BY_TYPE["weather_orb"]
    assert "`city`" in gen.props_table(weather)
    # weather_orb events have value_schema=None -> empty value cell
    assert "expand_forecast" in gen.events_table(weather)
    # chart_3d select_point has a value_schema with properties -> non-empty value cell
    chart = ht.WIDGETS_BY_TYPE["chart_3d"]
    assert "{series_index, point_index}" in gen.events_table(chart)
    # widget with no events
    assert gen.events_table({"events": []}) == "_None._"


def test_example_spawn_and_sections(gen):
    weather = ht.WIDGETS_BY_TYPE["weather_orb"]
    spawn = gen.example_spawn(weather)
    assert spawn["type"] == "holo.spawn"
    assert spawn["payload"]["widget_type"] == "weather_orb"
    assert "weather_orb" in gen.summary_table()
    assert "arrange_holograms" in gen.tools_table()
    assert "vision_annotation" in gen.perception_section()
    assert "### `weather_orb`" in gen.widget_section(weather)


def test_module_constants_and_main_present(gen):
    assert gen.HEADER and gen.CONVENTIONS and gen.SUMMONING and gen.ADD_GUIDE
    assert gen.OUT_PATH.name == "HOLO_TOOLS.md"
    assert callable(gen.main)
