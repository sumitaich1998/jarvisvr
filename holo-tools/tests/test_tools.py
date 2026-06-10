"""Tests for tools.json and the registry -> tools derivation."""

import pytest
from jsonschema import Draft202012Validator

import holo_tools as ht

REGISTRY = ht.load_registry()
TOOLS_DOC = ht.load_tools()
TOOLS = TOOLS_DOC["tools"]
TOOL_IDS = [t["name"] for t in TOOLS]
SPAWN_TOOLS = [t for t in TOOLS if t.get("x_action") == "spawn"]
SPAWN_TOOL_IDS = [t["name"] for t in SPAWN_TOOLS]
WIDGET_TYPES = {w["widget_type"] for w in REGISTRY["widgets"]}
PREFAB_BY_TYPE = {w["widget_type"]: w["prefab_id"] for w in REGISTRY["widgets"]}


def test_tools_doc_top_level():
    assert TOOLS_DOC["version"] == REGISTRY["version"]
    assert isinstance(TOOLS, list) and TOOLS


def test_tool_names_unique():
    assert len(TOOL_IDS) == len(set(TOOL_IDS)), "duplicate tool name"


@pytest.mark.parametrize("tool", TOOLS, ids=TOOL_IDS)
def test_tool_shape_is_function_calling_compatible(tool):
    assert isinstance(tool["name"], str) and tool["name"]
    assert isinstance(tool["description"], str) and tool["description"]
    params = tool["parameters"]
    assert params["type"] == "object"
    # parameters must itself be a valid JSON Schema
    Draft202012Validator.check_schema(params)


@pytest.mark.parametrize("tool", TOOLS, ids=TOOL_IDS)
def test_widget_tools_reference_real_widget_types(tool):
    if tool.get("x_action") == "spawn":
        wt = tool.get("x_widget_type")
        assert wt in WIDGET_TYPES, f"{tool['name']} references unknown widget_type {wt!r}"
        assert tool.get("x_prefab_id") == PREFAB_BY_TYPE[wt]


def test_every_widget_has_a_spawn_tool():
    produced = {t.get("x_widget_type") for t in TOOLS if t.get("x_action") == "spawn"}
    assert produced == WIDGET_TYPES


def test_utility_tools_present():
    names = set(TOOL_IDS)
    assert {"arrange_holograms", "close_hologram"}.issubset(names)
    # utility tools do not produce a widget
    for name in ("arrange_holograms", "close_hologram"):
        tool = ht.TOOLS_BY_NAME[name]
        assert "x_widget_type" not in tool


def test_expected_widget_tool_names():
    expected = {
        # v1.0
        "show_weather", "show_chart", "open_model_viewer", "start_timer",
        "show_smart_home", "show_todo_list",
        # v1.1 feature tools
        "show_clock", "show_calendar", "show_sticky_note", "show_stocks", "show_news",
        "show_translator", "show_web", "show_navigation", "measure",
        "show_system_launcher", "notify",
    }
    assert expected.issubset(set(TOOL_IDS))


def test_perception_tools_present():
    expected = {
        "annotate_object", "draw_bounding_box", "show_live_caption",
        "show_vision_feed", "drop_scene_label",
    }
    assert expected.issubset(set(TOOL_IDS))
    # each perception tool produces a perception-category widget
    for name in expected:
        tool = ht.TOOLS_BY_NAME[name]
        widget = ht.WIDGETS_BY_TYPE[tool["x_widget_type"]]
        assert widget["category"] == "perception"


def test_tools_json_matches_registry_derivation():
    """tools.json must be exactly what derive_tools() produces (no drift)."""
    derived = ht.derive_tools(REGISTRY)
    assert derived == TOOLS_DOC, (
        "tools.json is out of sync with registry.json. Regenerate it with:\n"
        "  python -c \"import json, holo_tools as ht; "
        "open('tools.json','w').write(json.dumps(ht.derive_tools(ht.REGISTRY), "
        "indent=2, ensure_ascii=False) + '\\n')\""
    )


@pytest.mark.parametrize("tool", SPAWN_TOOLS, ids=SPAWN_TOOL_IDS)
def test_spawn_tool_required_matches_widget_required(tool):
    """A widget tool's required params should match its widget's required props."""
    widget = ht.WIDGETS_BY_TYPE[tool["x_widget_type"]]
    assert set(tool["parameters"]["required"]) == set(widget["props_schema"].get("required", []))
