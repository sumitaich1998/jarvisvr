"""Tests for holo_tools.loader: path resolution, env override, caching, errors."""

import json

import pytest

import holo_tools as ht
from holo_tools import loader
from holo_tools.loader import CatalogFileNotFound


def test_catalog_file_not_found_is_filenotfounderror():
    assert issubclass(CatalogFileNotFound, FileNotFoundError)


def test_registry_and_tools_paths_point_at_real_files():
    rp = loader.registry_path()
    tp = loader.tools_path()
    assert rp.is_file() and rp.name == loader.REGISTRY_FILENAME
    assert tp.is_file() and tp.name == loader.TOOLS_FILENAME


def test_load_registry_and_tools_default():
    reg = loader.load_registry()
    tools = loader.load_tools()
    assert reg["version"] == tools["version"]
    assert reg["widgets"] and tools["tools"]


def test_load_registry_is_cached():
    # lru_cache: same no-arg call returns the identical object.
    assert loader.load_registry() is loader.load_registry()


def test_load_registry_explicit_path(tmp_path):
    data = {"version": "9.9.9", "widgets": []}
    p = tmp_path / "registry.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    assert loader.load_registry(str(p)) == data


def test_load_tools_explicit_path(tmp_path):
    data = {"version": "9.9.9", "tools": []}
    p = tmp_path / "tools.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    assert loader.load_tools(str(p)) == data


def test_load_registry_garbled_file_raises(tmp_path):
    p = tmp_path / "garbled_registry.json"
    p.write_text("{ this is : not valid json ", encoding="utf-8")
    with pytest.raises(json.JSONDecodeError):
        loader.load_registry(str(p))


def test_load_tools_garbled_file_raises(tmp_path):
    p = tmp_path / "garbled_tools.json"
    p.write_text("definitely not json", encoding="utf-8")
    with pytest.raises(json.JSONDecodeError):
        loader.load_tools(str(p))


def test_search_upwards_from_file_start_finds_self_dir(tmp_path):
    target = tmp_path / "marker_catalog.json"
    target.write_text("{}", encoding="utf-8")
    sibling = tmp_path / "sibling.txt"
    sibling.write_text("x", encoding="utf-8")
    # start is a *file* -> exercises the `base.is_file()` True branch
    found = loader._search_upwards("marker_catalog.json", start=sibling)
    assert found == target


def test_search_upwards_from_directory_start(tmp_path):
    target = tmp_path / "marker_catalog.json"
    target.write_text("{}", encoding="utf-8")
    nested = tmp_path / "a" / "b" / "c"
    nested.mkdir(parents=True)
    # start is a *directory* -> exercises the `base.is_file()` False branch
    found = loader._search_upwards("marker_catalog.json", start=nested)
    assert found == target


def test_search_upwards_not_found_raises(tmp_path):
    with pytest.raises(CatalogFileNotFound):
        loader._search_upwards("definitely_missing_catalog_xyz.json", start=tmp_path)


def test_registry_path_env_override(tmp_path, monkeypatch):
    p = tmp_path / "custom_registry.json"
    p.write_text("{}", encoding="utf-8")
    monkeypatch.setenv(loader.REGISTRY_ENV, str(p))
    assert loader.registry_path() == p


def test_tools_path_env_override(tmp_path, monkeypatch):
    p = tmp_path / "custom_tools.json"
    p.write_text("{}", encoding="utf-8")
    monkeypatch.setenv(loader.TOOLS_ENV, str(p))
    assert loader.tools_path() == p


def test_registry_path_env_override_missing_file_raises(tmp_path, monkeypatch):
    monkeypatch.setenv(loader.REGISTRY_ENV, str(tmp_path / "nope.json"))
    with pytest.raises(CatalogFileNotFound):
        loader.registry_path()


def test_tools_path_env_override_missing_file_raises(tmp_path, monkeypatch):
    monkeypatch.setenv(loader.TOOLS_ENV, str(tmp_path / "nope.json"))
    with pytest.raises(CatalogFileNotFound):
        loader.tools_path()


def test_get_widgets_with_explicit_registry():
    reg = {"widgets": [{"widget_type": "x"}, {"widget_type": "y"}]}
    assert loader.get_widgets(reg) == reg["widgets"]


def test_get_widgets_default_uses_loaded_registry():
    widgets = loader.get_widgets()
    assert any(w["widget_type"] == "timer" for w in widgets)


def test_widgets_by_type_with_explicit_registry():
    reg = {"widgets": [{"widget_type": "x"}, {"widget_type": "y"}]}
    mapping = loader.widgets_by_type(reg)
    assert set(mapping) == {"x", "y"}


def test_widgets_by_type_default():
    assert "weather_orb" in loader.widgets_by_type()


def test_get_tools_with_explicit_doc():
    doc = {"tools": [{"name": "a"}, {"name": "b"}]}
    assert loader.get_tools(doc) == doc["tools"]


def test_get_tools_default_uses_loaded_tools():
    assert any(t["name"] == "show_weather" for t in loader.get_tools())


def test_get_widgets_missing_key_returns_empty():
    assert loader.get_widgets({}) == []


def test_get_tools_missing_key_returns_empty():
    assert loader.get_tools({}) == []
