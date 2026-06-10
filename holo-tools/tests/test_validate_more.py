"""Additional validator coverage: per-widget negatives + edge branches + error API."""

import copy

import pytest

import holo_tools as ht
from holo_tools.validate import (
    HoloValidationError,
    InvalidPropsError,
    UnknownWidgetError,
    iter_widget_errors,
)

REGISTRY = ht.load_registry()
WIDGETS = REGISTRY["widgets"]
WIDGET_IDS = [w["widget_type"] for w in WIDGETS]

_CONCRETE_TYPES = {"string", "integer", "number", "boolean", "array", "object"}


def _first_typed_prop(schema):
    for name, sub in schema.get("properties", {}).items():
        t = sub.get("type")
        if isinstance(t, str) and t in _CONCRETE_TYPES:
            return name, t
    return None, None


def _wrong_value(json_type):
    # a string is a wrong value for every concrete type except "string",
    # for which we use an integer instead.
    return 12345 if json_type == "string" else "wrong-type-string"


def _first_enum_prop(schema):
    for name, sub in schema.get("properties", {}).items():
        if isinstance(sub.get("enum"), list) and sub.get("type") == "string":
            return name
    return None


WIDGETS_WITH_ENUM = [w for w in WIDGETS if _first_enum_prop(w["props_schema"])]
WWE_IDS = [w["widget_type"] for w in WIDGETS_WITH_ENUM]


@pytest.mark.parametrize("widget", WIDGETS, ids=WIDGET_IDS)
def test_wrong_type_prop_is_rejected(widget):
    name, json_type = _first_typed_prop(widget["props_schema"])
    assert name is not None, f"{widget['widget_type']} has no concretely-typed prop"
    bad = copy.deepcopy(widget["example_props"])
    bad[name] = _wrong_value(json_type)
    assert ht.is_valid_widget(widget["widget_type"], bad) is False
    with pytest.raises(InvalidPropsError):
        ht.validate_widget(widget["widget_type"], bad)


@pytest.mark.parametrize("widget", WIDGETS_WITH_ENUM, ids=WWE_IDS)
def test_bad_enum_value_is_rejected(widget):
    name = _first_enum_prop(widget["props_schema"])
    bad = copy.deepcopy(widget["example_props"])
    bad[name] = "__not_a_valid_enum_value__"
    with pytest.raises(InvalidPropsError):
        ht.validate_widget(widget["widget_type"], bad)


def test_holo_object_without_interactions_key_is_valid():
    """Exercises the `requested is None` branch in validate_holo_object."""
    obj = {
        "widget_type": "timer",
        "transform": copy.deepcopy(ht.WIDGETS_BY_TYPE["timer"]["default_transform"]),
        "props": {"duration_ms": 1000, "remaining_ms": 1000, "state": "running"},
    }
    assert ht.validate_holo_object(obj) is obj


def test_holo_object_minimal_only_widget_type():
    """No transform / interactions / props: props defaults to {}; clock has no required props."""
    obj = {"widget_type": "clock"}
    assert ht.validate_holo_object(obj) is obj


def test_holo_object_empty_widget_type_string_rejected():
    with pytest.raises(InvalidPropsError):
        ht.validate_holo_object({"widget_type": "", "props": {}})


def test_holo_object_with_empty_interactions_list_is_valid():
    obj = {
        "widget_type": "clock",
        "interactions": [],
        "props": {},
    }
    assert ht.validate_holo_object(obj) is obj


def test_bad_ttl_ms_is_rejected():
    obj = {
        "widget_type": "clock",
        "ttl_ms": -5,  # minimum 0
        "props": {},
    }
    with pytest.raises(InvalidPropsError):
        ht.validate_holo_object(obj)


def test_interactions_with_unknown_action_value_rejected():
    # an interaction value outside the global enum fails the structural schema
    obj = {
        "widget_type": "clock",
        "interactions": ["levitate"],
        "props": {},
    }
    with pytest.raises(InvalidPropsError):
        ht.validate_holo_object(obj)


def test_iter_widget_errors_empty_for_valid_and_nonempty_for_invalid():
    assert iter_widget_errors("clock", {}) == []
    errs = iter_widget_errors("weather_orb", {"city": "X"})  # missing temp_c + condition
    assert errs and all(isinstance(e, str) for e in errs)


def test_format_error_includes_location_for_nested_error():
    # humidity_pct out of range -> error path is '/humidity_pct' (non-empty location)
    errs = iter_widget_errors(
        "weather_orb", {"city": "X", "temp_c": 1, "condition": "clear", "humidity_pct": 999}
    )
    assert any("humidity_pct" in e for e in errs)


def test_error_str_and_payload():
    err = InvalidPropsError("boom", errors=["e1", "e2"])
    assert str(err) == "[invalid_props] boom"
    assert err.errors == ["e1", "e2"]
    assert err.to_error_payload() == {"code": "invalid_props", "message": "boom", "fatal": False}
    assert err.to_error_payload(fatal=True)["fatal"] is True


def test_base_error_default_code_and_str():
    base = HoloValidationError("x")
    assert base.code == "invalid"
    assert str(base) == "[invalid] x"
    assert base.errors == []


def test_error_explicit_code_overrides_class_default():
    # exercises the `if code is not None: self.code = code` branch
    err = HoloValidationError("msg", code="custom_code", errors=["x"])
    assert err.code == "custom_code"
    assert err.to_error_payload() == {"code": "custom_code", "message": "msg", "fatal": False}


def test_unknown_widget_error_code_and_str():
    err = UnknownWidgetError("nope")
    assert err.code == "unknown_widget"
    assert str(err) == "[unknown_widget] nope"


def test_validate_holo_object_props_default_empty_uses_widget_required():
    # timer requires props; omitting props entirely -> {} -> invalid_props
    with pytest.raises(InvalidPropsError):
        ht.validate_holo_object({"widget_type": "timer"})
