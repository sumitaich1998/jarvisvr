"""WidgetCatalog: load paths, normalization, merge, and light props validation."""

from __future__ import annotations

import json

import pytest

from jarvis_backend.catalog import CatalogError, WidgetCatalog, WidgetSpec

_SCHEMA = {
    "type": "object",
    "required": ["a"],
    "additionalProperties": False,
    "properties": {
        "a": {"type": "string"},
        "n": {"type": "integer"},
        "e": {"type": "string", "enum": ["x", "y"]},
    },
}
_DATA = {"version": "1.2.3", "widgets": {"foo": {"prefab_id": "Foo", "interactions": ["tap"],
         "default_transform": {"anchor": "head"}, "props_schema": _SCHEMA}}}


def test_widgetspec_from_entry_defaults():
    spec = WidgetSpec.from_entry("bar", {})
    assert spec.widget_type == "bar" and spec.prefab_id == "bar"
    assert spec.interactions == [] and spec.props_schema == {}


def test_builtin_catalog():
    cat = WidgetCatalog.builtin()
    assert "builtin" in cat.source
    assert "panel" in cat.names()


def test_load_none_and_missing_use_builtin(tmp_path):
    assert "builtin" in WidgetCatalog.load(None).source
    assert "builtin" in WidgetCatalog.load(tmp_path / "nope.json").source


def test_load_valid_merges_fallback(tmp_path):
    p = tmp_path / "registry.json"
    p.write_text(json.dumps(_DATA))
    cat = WidgetCatalog.load(p)
    assert cat.has("foo")  # published widget
    assert cat.has("panel")  # merged-in builtin fallback
    assert "builtin fallback" in cat.source


def test_load_empty_widgets_uses_builtin(tmp_path):
    p = tmp_path / "registry.json"
    p.write_text(json.dumps({"version": "1", "widgets": {}}))
    assert "builtin" in WidgetCatalog.load(p).source


def test_load_invalid_json_uses_builtin(tmp_path):
    p = tmp_path / "registry.json"
    p.write_text("{not json")
    assert "builtin" in WidgetCatalog.load(p).source


def test_normalize_list_format():
    data = {"widgets": [{"widget_type": "foo", "prefab_id": "Foo"}, {"no_type": True}]}
    cat = WidgetCatalog(data)
    assert cat.has("foo") and len(cat.names()) == 1


def test_merge_missing():
    cat = WidgetCatalog({"widgets": {"foo": {"prefab_id": "Foo"}}})
    added = cat.merge_missing({"widgets": {"foo": {}, "bar": {"prefab_id": "Bar"}}})
    assert added == 1 and cat.has("bar")  # foo already present, only bar added


def test_queries():
    cat = WidgetCatalog(_DATA)
    assert cat.has("foo") and not cat.has("zzz")
    assert cat.get("foo").prefab_id == "Foo" and cat.get("zzz") is None
    assert cat.default_transform("foo") == {"anchor": "head"}
    assert cat.default_transform("zzz") == {}
    assert cat.supported_interactions("foo") == ["tap"]
    assert cat.supported_interactions("zzz") == []


# --- validation -------------------------------------------------------------


def test_validate_ok():
    WidgetCatalog(_DATA).validate("foo", {"a": "hi", "n": 3, "e": "x"})  # no raise


def test_validate_unknown_widget():
    with pytest.raises(CatalogError) as e:
        WidgetCatalog(_DATA).validate("ghost", {})
    assert e.value.code == "unknown_widget"


def test_validate_missing_required():
    with pytest.raises(CatalogError) as e:
        WidgetCatalog(_DATA).validate("foo", {"n": 1})
    assert e.value.code == "invalid_props"


def test_validate_additional_property_rejected():
    with pytest.raises(CatalogError):
        WidgetCatalog(_DATA).validate("foo", {"a": "x", "extra": 1})


def test_validate_type_and_bool_rejection():
    with pytest.raises(CatalogError):
        WidgetCatalog(_DATA).validate("foo", {"a": "x", "n": "notint"})
    with pytest.raises(CatalogError):
        WidgetCatalog(_DATA).validate("foo", {"a": "x", "n": True})  # bool != integer


def test_validate_enum():
    with pytest.raises(CatalogError):
        WidgetCatalog(_DATA).validate("foo", {"a": "x", "e": "z"})


def test_validate_skips_unknown_schema():
    # props_schema without an object "type" -> accept anything.
    cat = WidgetCatalog({"widgets": {"open": {"prefab_id": "O", "props_schema": {}}}})
    cat.validate("open", {"whatever": 1})  # no raise


def test_validate_allows_unspecified_props_when_open():
    schema = {"type": "object", "properties": {"a": {"type": "string"}}}  # additionalProperties not False
    cat = WidgetCatalog({"widgets": {"w": {"prefab_id": "W", "props_schema": schema}}})
    cat.validate("w", {"a": "x", "unlisted": 99})  # unlisted allowed
