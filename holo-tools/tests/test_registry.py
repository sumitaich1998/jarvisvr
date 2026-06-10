"""Structural tests for registry.json (the single source of truth)."""

import re

import pytest
from jsonschema import Draft202012Validator

import holo_tools as ht

REGISTRY = ht.load_registry()
WIDGETS = REGISTRY["widgets"]
WIDGET_IDS = [w["widget_type"] for w in WIDGETS]

SNAKE_CASE = re.compile(r"^[a-z][a-z0-9_]*$")
REQUIRED_WIDGET_KEYS = {
    "widget_type",
    "title",
    "description",
    "category",
    "props_schema",
    "interactions",
    "default_transform",
    "prefab_id",
    "events",
    "example_props",
}


def test_registry_top_level():
    assert REGISTRY["version"] == "1.1.0"
    assert REGISTRY["protocol_version"] == "1.1.0"
    # v1.0 had 12 widgets; v1.1 adds 5 perception + 25 feature widgets.
    assert isinstance(WIDGETS, list) and len(WIDGETS) >= 42
    # the protocol anchor + interaction enums must be advertised
    assert REGISTRY["anchors"] == ["world", "head", "hand_left", "hand_right", "surface"]
    assert set(REGISTRY["interactions"]) == {
        "tap", "grab", "release", "drag", "slider", "toggle", "resize", "dwell",
    }


def test_v1_widgets_still_present():
    """The 12 v1.0 widgets must keep working (no regressions)."""
    v1 = {
        "weather_orb", "chart_3d", "model_viewer", "panel", "text_label",
        "button", "timer", "media_player", "map_3d", "smart_home_panel",
        "todo_list", "image_board",
    }
    assert v1.issubset(set(WIDGET_IDS))


def test_perception_widgets_present():
    perception = {"vision_annotation", "bounding_box_3d", "live_caption", "vision_feed", "scene_label"}
    assert perception.issubset(set(WIDGET_IDS))
    for wt in perception:
        assert next(w for w in WIDGETS if w["widget_type"] == wt)["category"] == "perception"


def test_v11_feature_widgets_present():
    feature = {
        "clock", "world_clock", "calendar", "stocks_ticker", "news_feed", "translator",
        "recipe_card", "whiteboard", "sticky_note", "code_viewer", "document_viewer",
        "web_panel", "avatar", "navigation_arrow", "health_ring", "music_visualizer",
        "graph_3d", "data_table", "measuring_tape", "pomodoro", "image_gen_viewer",
        "volumetric_globe", "system_launcher", "notification_toast", "settings_panel",
    }
    assert feature.issubset(set(WIDGET_IDS))


def test_widget_types_unique_and_snake_case():
    assert len(WIDGET_IDS) == len(set(WIDGET_IDS)), "duplicate widget_type"
    for wt in WIDGET_IDS:
        assert SNAKE_CASE.match(wt), f"widget_type not snake_case: {wt}"


def test_expected_widgets_present():
    expected = {
        "weather_orb", "chart_3d", "model_viewer", "panel", "text_label",
        "button", "timer", "media_player", "map_3d", "smart_home_panel",
        "todo_list", "image_board",
    }
    assert expected.issubset(set(WIDGET_IDS))


@pytest.mark.parametrize("widget", WIDGETS, ids=WIDGET_IDS)
def test_widget_has_required_keys(widget):
    missing = REQUIRED_WIDGET_KEYS - set(widget)
    assert not missing, f"{widget['widget_type']} missing keys: {missing}"
    assert widget["category"] in REGISTRY["categories"]
    assert widget["prefab_id"].startswith("Holo_")
    assert widget["title"] and widget["description"]


@pytest.mark.parametrize("widget", WIDGETS, ids=WIDGET_IDS)
def test_props_schema_is_valid_draft202012(widget):
    schema = widget["props_schema"]
    # raises SchemaError if the schema itself is malformed
    Draft202012Validator.check_schema(schema)
    assert schema.get("type") == "object"
    assert schema.get("$schema") == "https://json-schema.org/draft/2020-12/schema"


@pytest.mark.parametrize("widget", WIDGETS, ids=WIDGET_IDS)
def test_property_keys_are_snake_case(widget):
    for key in widget["props_schema"].get("properties", {}):
        assert SNAKE_CASE.match(key), f"{widget['widget_type']}.{key} not snake_case"


@pytest.mark.parametrize("widget", WIDGETS, ids=WIDGET_IDS)
def test_interactions_are_valid_subset(widget):
    allowed = set(REGISTRY["interactions"])
    interactions = widget["interactions"]
    assert interactions, f"{widget['widget_type']} has no interactions"
    assert set(interactions).issubset(allowed)
    assert len(interactions) == len(set(interactions)), "duplicate interaction"


@pytest.mark.parametrize("widget", WIDGETS, ids=WIDGET_IDS)
def test_default_transform_conforms(widget):
    t = widget["default_transform"]
    assert t["anchor"] in REGISTRY["anchors"]
    assert len(t["position"]) == 3
    assert len(t["rotation"]) == 4
    assert len(t["scale"]) == 3
    assert isinstance(t["billboard"], bool)
    assert all(isinstance(n, (int, float)) for n in t["position"] + t["rotation"] + t["scale"])


@pytest.mark.parametrize("widget", WIDGETS, ids=WIDGET_IDS)
def test_events_reference_supported_actions(widget):
    supported = set(widget["interactions"])
    for event in widget["events"]:
        assert event["name"]
        assert event["action"] in supported, (
            f"{widget['widget_type']} event {event['name']!r} uses action "
            f"{event['action']!r} not in interactions {sorted(supported)}"
        )
        # value_schema, when present, is a valid schema or null
        vs = event.get("value_schema")
        if vs is not None:
            Draft202012Validator.check_schema(vs)


@pytest.mark.parametrize("widget", WIDGETS, ids=WIDGET_IDS)
def test_example_props_validate_against_own_schema(widget):
    validator = Draft202012Validator(widget["props_schema"])
    errors = sorted(validator.iter_errors(widget["example_props"]), key=lambda e: list(e.path))
    assert not errors, f"{widget['widget_type']} example_props invalid: {[e.message for e in errors]}"
