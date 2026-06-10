"""Tests for the validator API (validate_widget / validate_holo_object)."""

import copy

import pytest

import holo_tools as ht
from holo_tools.validate import (
    HoloValidationError,
    InvalidPropsError,
    UnknownWidgetError,
)

REGISTRY = ht.load_registry()
WIDGETS = REGISTRY["widgets"]
WIDGET_IDS = [w["widget_type"] for w in WIDGETS]
ALL_INTERACTIONS = set(REGISTRY["interactions"])

# Some widgets are intentionally all-optional (sensible defaults, e.g. clock/avatar);
# the "missing required" negative test only applies to those with required props.
WIDGETS_WITH_REQUIRED = [w for w in WIDGETS if w["props_schema"].get("required")]
WWR_IDS = [w["widget_type"] for w in WIDGETS_WITH_REQUIRED]


def _holo_object(widget):
    """Build a full holo object (PROTOCOL.md §5.6) from a widget's defaults."""
    return {
        "object_id": "00000000-0000-4000-8000-000000000000",
        "widget_type": widget["widget_type"],
        "transform": copy.deepcopy(widget["default_transform"]),
        "props": copy.deepcopy(widget["example_props"]),
        "interactable": True,
        "interactions": list(widget["interactions"]),
        "ttl_ms": 0,
    }


@pytest.mark.parametrize("widget", WIDGETS, ids=WIDGET_IDS)
def test_validate_widget_accepts_example(widget):
    result = ht.validate_widget(widget["widget_type"], widget["example_props"])
    assert result == widget["example_props"]
    assert ht.is_valid_widget(widget["widget_type"], widget["example_props"]) is True


@pytest.mark.parametrize("widget", WIDGETS, ids=WIDGET_IDS)
def test_validate_holo_object_accepts_example(widget):
    obj = _holo_object(widget)
    assert ht.validate_holo_object(obj) is obj


@pytest.mark.parametrize("widget", WIDGETS_WITH_REQUIRED, ids=WWR_IDS)
def test_missing_required_prop_is_rejected(widget):
    required = widget["props_schema"]["required"]
    bad = copy.deepcopy(widget["example_props"])
    bad.pop(required[0])
    with pytest.raises(InvalidPropsError) as exc:
        ht.validate_widget(widget["widget_type"], bad)
    assert exc.value.code == "invalid_props"
    assert ht.is_valid_widget(widget["widget_type"], bad) is False


@pytest.mark.parametrize("widget", WIDGETS, ids=WIDGET_IDS)
def test_unknown_extra_prop_is_rejected(widget):
    bad = copy.deepcopy(widget["example_props"])
    bad["__definitely_not_a_real_prop__"] = True
    with pytest.raises(InvalidPropsError):
        ht.validate_widget(widget["widget_type"], bad)


@pytest.mark.parametrize("widget", WIDGETS, ids=WIDGET_IDS)
def test_unsupported_interaction_is_rejected(widget):
    unsupported = sorted(ALL_INTERACTIONS - set(widget["interactions"]))
    assert unsupported, f"{widget['widget_type']} supports every interaction?"
    obj = _holo_object(widget)
    obj["interactions"] = [unsupported[0]]
    with pytest.raises(InvalidPropsError):
        ht.validate_holo_object(obj)


def test_unknown_widget_raises():
    with pytest.raises(UnknownWidgetError) as exc:
        ht.validate_widget("not_a_widget", {})
    assert exc.value.code == "unknown_widget"
    with pytest.raises(UnknownWidgetError):
        ht.validate_holo_object({"widget_type": "not_a_widget", "props": {}})


def test_props_must_be_object():
    with pytest.raises(InvalidPropsError):
        ht.validate_widget("text_label", "not-a-dict")


def test_holo_object_must_be_dict_and_have_widget_type():
    with pytest.raises(InvalidPropsError):
        ht.validate_holo_object(["not", "a", "dict"])
    with pytest.raises(InvalidPropsError):
        ht.validate_holo_object({"props": {}})


def test_bad_transform_is_rejected():
    obj = {
        "widget_type": "timer",
        "transform": {"anchor": "outer_space", "position": [0, 0, 1]},  # bad anchor
        "props": {"duration_ms": 1000, "remaining_ms": 1000, "state": "running"},
    }
    with pytest.raises(InvalidPropsError):
        ht.validate_holo_object(obj)

    obj2 = {
        "widget_type": "timer",
        "transform": {"rotation": [0, 0, 1]},  # quaternion must have 4 components
        "props": {"duration_ms": 1000, "remaining_ms": 1000, "state": "running"},
    }
    with pytest.raises(InvalidPropsError):
        ht.validate_holo_object(obj2)


def test_enum_and_range_constraints():
    # bad enum value
    assert ht.is_valid_widget("weather_orb", {"city": "X", "temp_c": 1, "condition": "sunny"}) is False
    # out-of-range humidity
    assert ht.is_valid_widget(
        "weather_orb", {"city": "X", "temp_c": 1, "condition": "clear", "humidity_pct": 150}
    ) is False
    # volume above 1.0
    assert ht.is_valid_widget(
        "media_player", {"source_url": "https://x/y.mp3", "media_type": "audio", "volume": 2}
    ) is False


PERCEPTION_WIDGETS = ["vision_annotation", "bounding_box_3d", "live_caption", "vision_feed", "scene_label"]


@pytest.mark.parametrize("wt", PERCEPTION_WIDGETS)
def test_perception_widget_validates_as_holo_object(wt):
    """Perception widgets (PROTOCOL.md §8.5) must validate as full §5.6 holo objects."""
    widget = ht.WIDGETS_BY_TYPE[wt]
    obj = _holo_object(widget)
    assert ht.validate_holo_object(obj) is obj


def test_vision_annotation_world_anchored_billboard_object():
    """Mirror of the PROTOCOL.md §8.6 realtime-perception example (world anchor + billboard)."""
    obj = {
        "object_id": "O9",
        "widget_type": "vision_annotation",
        "transform": {
            "anchor": "world",
            "position": [0.3, 0.95, 0.7],
            "rotation": [0, 0, 0, 1],
            "scale": [1, 1, 1],
            "billboard": True,
        },
        "props": {"label": "coffee mug", "confidence": 0.78},
        "interactable": True,
        "interactions": ["tap"],
    }
    assert ht.validate_holo_object(obj) is obj
    # the catalog default is world-anchored and billboarded
    dt = ht.WIDGETS_BY_TYPE["vision_annotation"]["default_transform"]
    assert dt["anchor"] == "world" and dt["billboard"] is True


def test_error_payload_shape():
    try:
        ht.validate_widget("weather_orb", {"city": "X"})  # missing temp_c, condition
    except HoloValidationError as e:
        payload = e.to_error_payload()
        assert payload["code"] == "invalid_props"
        assert isinstance(payload["message"], str) and payload["message"]
        assert payload["fatal"] is False
        assert e.errors  # human-readable per-field messages
    else:  # pragma: no cover
        pytest.fail("expected validation to fail")
