"""Branch coverage for holo_tools.tools (derive_widget_tool / utility_tools / derive_tools)."""

from jsonschema import Draft202012Validator

import holo_tools as ht
from holo_tools import tools as toolmod

# A widget whose type is intentionally NOT in WIDGET_TOOL_NAMES, to exercise the
# `f"show_{widget_type}"` fallback name path.
FAKE_WIDGET = {
    "widget_type": "made_up_widget",
    "title": "Made Up",
    "description": "A widget not present in WIDGET_TOOL_NAMES.",
    "prefab_id": "Holo_MadeUp",
    "props_schema": {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "additionalProperties": False,
        "required": ["foo"],
        "properties": {"foo": {"type": "string"}},
    },
}


def test_derive_widget_tool_default_name_from_map_and_default_anchors():
    w = ht.WIDGETS_BY_TYPE["weather_orb"]
    tool = toolmod.derive_widget_tool(w)  # name=None (map), anchors=None (default)
    assert tool["name"] == "show_weather"
    assert tool["x_widget_type"] == "weather_orb"
    assert tool["x_prefab_id"] == "Holo_WeatherOrb"
    assert tool["x_action"] == "spawn"
    props = tool["parameters"]["properties"]
    assert {"anchor", "position", "billboard"}.issubset(props)
    # default anchors used
    assert props["anchor"]["enum"] == toolmod._DEFAULT_ANCHORS
    Draft202012Validator.check_schema(tool["parameters"])


def test_derive_widget_tool_explicit_name_overrides_map():
    w = ht.WIDGETS_BY_TYPE["timer"]
    tool = toolmod.derive_widget_tool(w, name="custom_timer_tool")
    assert tool["name"] == "custom_timer_tool"


def test_derive_widget_tool_fallback_name_for_unknown_type():
    tool = toolmod.derive_widget_tool(FAKE_WIDGET)
    assert tool["name"] == "show_made_up_widget"
    assert tool["parameters"]["required"] == ["foo"]
    assert tool["x_prefab_id"] == "Holo_MadeUp"


def test_derive_widget_tool_custom_anchors():
    tool = toolmod.derive_widget_tool(FAKE_WIDGET, anchors=["world"])
    assert tool["parameters"]["properties"]["anchor"]["enum"] == ["world"]


def test_utility_tools_default_anchors():
    util = toolmod.utility_tools()  # anchors=None -> default
    names = [t["name"] for t in util]
    assert names == ["arrange_holograms", "close_hologram", "update_hologram"]
    arrange = util[0]
    assert arrange["parameters"]["properties"]["anchor"]["enum"] == toolmod._DEFAULT_ANCHORS
    for t in util:
        Draft202012Validator.check_schema(t["parameters"])


def test_utility_tools_custom_anchors():
    util = toolmod.utility_tools(anchors=["head"])
    assert util[0]["parameters"]["properties"]["anchor"]["enum"] == ["head"]


def test_derive_tools_default_registry():
    doc = toolmod.derive_tools()  # registry=None -> loader.load_registry()
    names = {t["name"] for t in doc["tools"]}
    assert doc["version"] == ht.VERSION
    assert "show_weather" in names and "arrange_holograms" in names
    assert len(doc["tools"]) == len(ht.WIDGETS) + 3  # one spawn per widget + 3 utility


def test_derive_tools_explicit_registry_matches_file():
    assert toolmod.derive_tools(ht.REGISTRY) == ht.load_tools()


def test_placement_properties_shape():
    props = toolmod._placement_properties(["world", "head"])
    assert props["anchor"]["enum"] == ["world", "head"]
    assert props["position"]["minItems"] == 3 and props["position"]["maxItems"] == 3
    assert props["billboard"]["type"] == "boolean"
