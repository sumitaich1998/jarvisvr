"""Exhaustive tool tests: builtins (incl. live-weather httpx mock), perception,
knowledge, dynamic widget tools, and the ToolRegistry primitives."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from jarvis_backend.agent.memory import EpisodicMemory, LongTermStore
from jarvis_backend.agent.state import SessionState
from jarvis_backend.agent.tools import base as B
from jarvis_backend.agent.tools import builtins as BT
from jarvis_backend.agent.tools import knowledge_tools as KT
from jarvis_backend.agent.tools import perception_tools as PT
from jarvis_backend.agent.tools import widget_tools as WT
from jarvis_backend.agent.tools.base import Tool, ToolContext, ToolRegistry, ToolResult
from jarvis_backend.catalog import WidgetCatalog
from jarvis_backend.config import Config


def _ctx(tmp_path, config=None) -> ToolContext:
    lt = LongTermStore(Path(tmp_path) / "m.json")
    return ToolContext(
        config=config or Config(data_dir=Path(tmp_path)),
        session=SessionState(session_id="S"),
        catalog=WidgetCatalog.builtin(),
        longterm=lt,
        episodic=EpisodicMemory(lt),
    )


# --- builtins ---------------------------------------------------------------


async def test_get_weather_preset_and_hashed(tmp_path):
    r = await BT._get_weather({"city": "tokyo"}, _ctx(tmp_path))
    assert r.data["temp_c"] == 18 and r.data["city"] == "Tokyo"
    r2 = await BT._get_weather({"city": "Zzzville"}, _ctx(tmp_path))  # hashed fallback
    assert isinstance(r2.data["temp_c"], int)
    assert r2.directives[0].widget_type == "weather_orb"


async def test_get_weather_default_city(tmp_path):
    r = await BT._get_weather({}, _ctx(tmp_path))
    assert r.data["city"] == "San Francisco"


async def test_get_weather_live_success(tmp_path, monkeypatch):
    payload = {"main": {"temp": 9.4, "humidity": 71}, "wind": {"speed": 3.0},
               "weather": [{"main": "Rain"}], "name": "London"}

    class _Resp:
        def raise_for_status(self):
            return None

        def json(self):
            return payload

    class _Client:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def get(self, url, params=None):
            return _Resp()

    monkeypatch.setitem(sys.modules, "httpx", SimpleNamespace(AsyncClient=_Client))
    r = await BT._get_weather({"city": "london"}, _ctx(tmp_path, Config(weather_api_key="k")))
    assert r.data["source"] == "openweathermap"
    assert r.data["temp_c"] == 9 and r.data["city"] == "London"


async def test_get_weather_live_error_falls_back(tmp_path, monkeypatch):
    class _Client:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def get(self, *a, **k):
            raise RuntimeError("network down")

    monkeypatch.setitem(sys.modules, "httpx", SimpleNamespace(AsyncClient=_Client))
    r = await BT._get_weather({"city": "tokyo"}, _ctx(tmp_path, Config(weather_api_key="k")))
    assert r.data["source"] == "mock"  # gracefully fell back


def test_human_duration():
    assert BT._human_duration(7200) == "2 hours"
    assert BT._human_duration(90) == "1 minute 30 seconds"
    assert BT._human_duration(3661) == "1 hour 1 minute"  # seconds dropped when hours present
    assert BT._human_duration(60) == "1 minute"
    assert BT._human_duration(45) == "45 seconds"
    assert BT._human_duration(0) == "0 seconds"


def test_start_and_stop_timer(tmp_path):
    ctx = _ctx(tmp_path)
    r = BT._start_timer({"duration_seconds": 7200, "label": "Tea"}, ctx)
    assert "2 hours" in r.data["speech"]
    ref = r.data["timer_ref"]
    assert ctx.session.store["timers"][ref]["state"] == "running"

    stop = BT._stop_timer({}, ctx)  # uses last_timer_ref
    assert stop.data["stopped"] is True
    assert stop.directives[0].ref == ref
    # nothing left to stop
    assert BT._stop_timer({}, ctx).data["stopped"] is False


def test_start_timer_default_duration(tmp_path):
    r = BT._start_timer({}, _ctx(tmp_path))
    assert r.data["duration_s"] == 60


def test_get_time(tmp_path):
    r = BT._get_time({}, _ctx(tmp_path))
    assert "time" in r.data and r.directives[0].widget_type == "panel"


def test_take_note_and_list_notes(tmp_path):
    ctx = _ctx(tmp_path)
    assert BT._take_note({}, ctx).data["saved"] is False  # empty
    assert BT._list_notes({}, ctx).data["count"] == 0  # none -> message
    BT._take_note({"text": "milk"}, ctx)
    assert BT._list_notes({}, ctx).data["count"] == 1  # singular branch
    BT._take_note({"text": "eggs"}, ctx)
    assert "2 notes" in BT._list_notes({}, ctx).data["speech"]


def test_set_reminder_variants(tmp_path):
    ctx = _ctx(tmp_path)
    assert BT._set_reminder({}, ctx).data["set"] is False
    assert "in 1 minute" in BT._set_reminder({"text": "call", "in_seconds": 60}, ctx).data["speech"]
    assert "at 18:00" in BT._set_reminder({"text": "meet", "at": "18:00"}, ctx).data["speech"]
    assert BT._set_reminder({"text": "plain"}, ctx).data["set"] is True


def test_show_panel_and_text(tmp_path):
    ctx = _ctx(tmp_path)
    assert BT._show_panel({"title": "T", "body": "B"}, ctx).directives[0].props["title"] == "T"
    assert BT._show_text({}, ctx).data["speech"] == "Here you go."  # empty text default
    assert BT._show_text({"text": "hi"}, ctx).data["speech"] == "hi"


def test_open_widget(tmp_path):
    ctx = _ctx(tmp_path)
    bad = BT._open_widget({"widget_type": "nope_widget"}, ctx)
    assert bad.error == "unknown_widget"
    ok = BT._open_widget({"widget_type": "panel", "anchor": "head", "position": [0, 1, 1]}, ctx)
    assert ok.data["opened"] is True
    assert ok.directives[0].transform == {"anchor": "head", "position": [0, 1, 1]}
    plain = BT._open_widget({"widget_type": "panel"}, ctx)
    assert plain.directives[0].transform is None


# --- perception tools -------------------------------------------------------


def test_describe_view(tmp_path):
    r = PT._describe_view({}, _ctx(tmp_path))
    assert r.data["observation"]["annotations"]
    assert r.data["objects"]


def test_identify_object_present_and_none(tmp_path, monkeypatch):
    r = PT._identify_object({}, _ctx(tmp_path))
    assert r.data["object"]  # canned scene -> something
    monkeypatch.setattr(PT, "focus_object", lambda cd: None)
    none = PT._identify_object({}, _ctx(tmp_path))
    assert "don't see anything" in none.data["speech"]


def test_read_text_and_translate(tmp_path):
    ctx = _ctx(tmp_path)
    assert PT._read_text({}, ctx).directives[0].props["title"] == "Read"
    assert PT._translate_text({}, ctx).data["speech"].startswith("What")  # empty
    tr = PT._translate_text({"text": "hello", "target_lang": "french"}, ctx)
    assert tr.data["translated"] and tr.directives[0].widget_type == "translator"
    tv = PT._translate_view({"target_lang": "spanish"}, ctx)
    assert tv.data["observation"]["text"]


def test_remember_object_with_and_without_position(tmp_path, monkeypatch):
    ctx = _ctx(tmp_path)
    r = PT._remember_object({"name": "keys", "position": [1, 1, 1], "anchor": "world"}, ctx)
    assert r.directives and "marked the spot" in r.data["speech"]
    monkeypatch.setattr(PT, "focus_object", lambda cd: None)
    r2 = PT._remember_object({"name": "wallet"}, ctx)  # no position resolvable
    assert r2.directives == []


def test_resolve_position_gaze_hit_point(tmp_path):
    ctx = _ctx(tmp_path)
    ctx.session.perception.set_gaze({"hit_point": [2, 2, 2]})
    pos, anchor = PT._resolve_position(ctx, {})
    assert pos == [2, 2, 2] and anchor == "world"


def test_find_object_states(tmp_path):
    ctx = _ctx(tmp_path)
    assert PT._find_object({"name": "keys"}, ctx).data["found"] is False  # not seen
    ctx.episodic.remember_object("keys", position=[0.5, 0.8, 0.6], anchor="world")
    found = PT._find_object({"name": "keys"}, ctx)
    assert found.data["found"] is True
    assert {d.widget_type for d in found.directives} == {"vision_annotation", "navigation_arrow"}
    ctx.episodic.remember_object("wallet", position=None)
    vague = PT._find_object({"name": "wallet"}, ctx)
    assert "didn't note exactly where" in vague.data["speech"]


def test_identify_sound_states(tmp_path):
    ctx = _ctx(tmp_path)
    assert "haven't heard" in PT._identify_sound({}, ctx).data["speech"]
    ctx.session.perception.add_audio_event({"label": "doorbell", "confidence": 0.9})
    assert "doorbell" in PT._identify_sound({}, ctx).data["speech"]


def test_measure_with_and_without_objects(tmp_path, monkeypatch):
    ctx = _ctx(tmp_path)
    r = PT._measure({}, ctx)  # canned scene has >=2 placed objects
    assert r.data["distance_m"] >= 0
    monkeypatch.setattr(PT, "scene_objects", lambda cd: [])
    r2 = PT._measure({}, ctx)
    assert "span in front of you" in r2.data["speech"]


# --- knowledge tools --------------------------------------------------------


def test_web_search(tmp_path):
    ctx = _ctx(tmp_path)
    assert "What should I search" in KT._web_search({}, ctx).data["speech"]
    r = KT._web_search({"query": "mars rovers"}, ctx)
    assert r.data["results"] and r.directives[0].widget_type == "web_panel"


def test_get_news(tmp_path):
    ctx = _ctx(tmp_path)
    assert KT._get_news({}, ctx).data["articles"]
    assert KT._get_news({"topic": "space"}, ctx).directives[0].props["category"] == "space"


def test_get_stocks_list_str_default(tmp_path):
    ctx = _ctx(tmp_path)
    assert len(KT._get_stocks({"symbols": ["AAPL", "TSLA"]}, ctx).data["quotes"]) == 2
    assert len(KT._get_stocks({"symbols": "AAPL, TSLA NVDA"}, ctx).data["quotes"]) == 3
    assert KT._get_stocks({"symbols": []}, ctx).data["quotes"][0]["symbol"] == "AAPL"


def test_get_calendar(tmp_path):
    r = KT._get_calendar({}, _ctx(tmp_path))
    assert r.data["events"] and r.directives[0].widget_type == "calendar"


def test_navigate_to(tmp_path):
    ctx = _ctx(tmp_path)
    assert "Where would you like" in KT._navigate_to({}, ctx).data["speech"]
    r = KT._navigate_to({"destination": "the kitchen"}, ctx)
    assert r.directives[0].props["target_label"] == "the kitchen"
    assert len(r.directives[0].props["direction"]) == 3


# --- widget tools -----------------------------------------------------------


def test_load_tools_json(tmp_path):
    assert WT._load_tools_json(None) == {}
    assert WT._load_tools_json(tmp_path / "nope.json") == {}
    good = tmp_path / "tools.json"
    good.write_text('{"tools": [{"name": "show_map", "description": "Map", "x_widget_type": "map_3d", "x_action": "spawn"}]}')
    meta = WT._load_tools_json(good)
    assert meta["map_3d"]["name"] == "show_map"
    bad = tmp_path / "bad.json"
    bad.write_text("{not json")
    assert WT._load_tools_json(bad) == {}


def test_register_widget_tools_and_handler(tmp_path):
    reg = ToolRegistry()
    cat = WidgetCatalog.builtin()
    added = WT.register_widget_tools(reg, cat)
    assert added > 0
    # claimed widgets are NOT given a dynamic tool
    assert not reg.has("show_weather_orb")
    # spawn tool handler returns a spawn directive
    name = next(n for n in reg.names() if n.startswith("show_"))
    handler = reg.get(name).handler
    res = handler({"x": 1}, _ctx(tmp_path))
    assert res.directives[0].widget_type == name[len("show_"):]


def test_register_widget_tools_skips_existing(tmp_path):
    reg = ToolRegistry()
    cat = WidgetCatalog.builtin()
    # Pre-register a name that would collide -> skipped (not clobbered).
    first = [n for n in cat.names() if n not in WT._CLAIMED_WIDGETS][0]
    reg.add(f"show_{first}", "pre", {"type": "object"}, lambda a, c: ToolResult())
    before = len(reg.names())
    WT.register_widget_tools(reg, cat)
    assert reg.get(f"show_{first}").description == "pre"  # untouched
    assert len(reg.names()) >= before


def test_register_widget_tools_uses_tools_json_meta(tmp_path):
    reg = ToolRegistry()
    cat = WidgetCatalog.builtin()
    target = next(n for n in cat.names() if n not in WT._CLAIMED_WIDGETS)
    tj = tmp_path / "tools.json"
    tj.write_text(
        '{"tools": [{"name": "custom_show", "description": "Custom desc", '
        f'"x_widget_type": "{target}", "x_action": "spawn"}}]}}'
    )
    WT.register_widget_tools(reg, cat, tj)
    assert reg.has("custom_show")
    assert reg.get("custom_show").description == "Custom desc"


# --- ToolRegistry primitives ------------------------------------------------


async def test_registry_unknown_tool(tmp_path):
    res = await ToolRegistry().run("ghost", {}, _ctx(tmp_path))
    assert res.error == "tool_failed" and not res.ok


async def test_registry_handler_exception(tmp_path):
    reg = ToolRegistry()

    def boom(args, ctx):
        raise ValueError("nope")

    reg.add("boom", "d", {"type": "object"}, boom)
    res = await reg.run("boom", {}, _ctx(tmp_path))
    assert res.error == "tool_failed"


async def test_registry_async_and_sync_handlers(tmp_path):
    reg = ToolRegistry()

    async def ah(args, ctx):
        return ToolResult(data={"ok": "async"})

    def sh(args, ctx):
        return ToolResult(data={"ok": "sync"})

    reg.add("a", "d", {"type": "object"}, ah)
    reg.add("s", "d", {"type": "object"}, sh)
    assert (await reg.run("a", {}, _ctx(tmp_path))).data["ok"] == "async"
    assert (await reg.run("s", None, _ctx(tmp_path))).data["ok"] == "sync"


def test_registry_register_overwrite_warns_and_helpers(caplog):
    reg = ToolRegistry()
    t = Tool("x", "d", {"type": "object"}, lambda a, c: ToolResult())
    reg.register(t)
    reg.register(t)  # overwrite -> warning path
    assert reg.has("x") and "x" in reg.names()
    assert reg.get("x") is t and reg.get("missing") is None
    assert reg.specs()[0].name == "x"


def test_toolresult_ok_and_context_perception(tmp_path):
    assert ToolResult().ok is True
    assert ToolResult(error="e").ok is False
    ctx = _ctx(tmp_path)
    assert ctx.perception is ctx.session.perception
