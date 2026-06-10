"""Direct in-process unit tests for the mock brain (infra/mock-backend/server.py).

The live e2e (test_conformance.py) drives the mock in a *subprocess*, which the
in-process coverage cannot see — so here we import `server` directly and exercise
every handler (hello, heartbeat, user.*, interaction, perception incl. /vision,
settings) with a fake WebSocket.
"""

from __future__ import annotations

import asyncio
import json
import pathlib
import sys
import types

import pytest
import websockets

import jarvis_protocol as jp

# Make the mock-backend package importable (it's a sibling dir, not on sys.path).
_MOCK_DIR = pathlib.Path(__file__).resolve().parent.parent / "mock-backend"
sys.path.insert(0, str(_MOCK_DIR))
import server  # noqa: E402

run = asyncio.run


class FakeWS:
    """Minimal duck-typed WebSocket: async-iterable for incoming, records sends."""

    def __init__(self, incoming=None, *, path="/jarvis", use_request=True, raise_exc=None):
        self._incoming = list(incoming or [])
        self.sent = []
        self._raise_exc = raise_exc
        if use_request:
            self.request = types.SimpleNamespace(path=path)
        else:
            self.path = path

    async def send(self, data):
        self.sent.append(data)

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self._incoming:
            return self._incoming.pop(0)
        if self._raise_exc is not None:
            exc, self._raise_exc = self._raise_exc, None
            raise exc
        raise StopAsyncIteration


def enc(type_, payload, session="S"):
    return jp.encode(jp.new_message(type_, payload, session=session))


def sent_types(ws):
    return [jp.decode(s).type for s in ws.sent]


def _closed():
    return websockets.ConnectionClosed(None, None)


# --------------------------------------------------------------------------- #
# registry helpers                                                            #
# --------------------------------------------------------------------------- #

def test_registry_widget_types_shapes():
    s1 = server._registry_widget_types({"widgets": [{"widget_type": "a"}, {"type": "b"}, {"name": "c"}, {"no": "x"}, 123]})
    assert {"a", "b", "c"} <= s1
    s2 = server._registry_widget_types({"alpha": {"x": 1}, "$schema": "s", "beta": {"y": 2}})
    assert s2 == {"alpha", "beta"}
    s3 = server._registry_widget_types([{"id": "d"}, "notdict", {"nope": 1}])
    assert s3 == {"d"}
    assert server._registry_widget_types(42) == set()
    assert server._registry_widget_types({"widgets": 123}) == set()  # widgets neither dict nor list


def test_find_registry_env(monkeypatch, tmp_path):
    reg = tmp_path / "registry.json"
    reg.write_text('{"widgets":[{"widget_type":"x"}]}')
    monkeypatch.setenv("HOLO_TOOLS_REGISTRY", str(reg))
    assert server._find_registry() == reg


def test_find_registry_upward(monkeypatch):
    monkeypatch.delenv("HOLO_TOOLS_REGISTRY", raising=False)
    p = server._find_registry()
    assert p is not None and p.name == "registry.json"


def test_find_registry_none(monkeypatch):
    monkeypatch.delenv("HOLO_TOOLS_REGISTRY", raising=False)
    monkeypatch.setattr(pathlib.Path, "is_file", lambda self: False)
    assert server._find_registry() is None


def test_load_known_widgets_variants(monkeypatch, tmp_path):
    monkeypatch.setattr(server, "_find_registry", lambda: None)
    assert server.load_known_widgets() == set(server.BUILTIN_WIDGETS)

    empty = tmp_path / "registry.json"
    empty.write_text('{"widgets":[]}')
    monkeypatch.setattr(server, "_find_registry", lambda: empty)
    assert server.load_known_widgets() == set(server.BUILTIN_WIDGETS)

    bad = tmp_path / "bad.json"
    bad.write_text("{ not json")
    monkeypatch.setattr(server, "_find_registry", lambda: bad)
    assert server.load_known_widgets() == set(server.BUILTIN_WIDGETS)


def test_load_known_widgets_real(monkeypatch):
    # Use the real repo registry (found via upward search).
    monkeypatch.delenv("HOLO_TOOLS_REGISTRY", raising=False)
    known = server.load_known_widgets()
    assert "weather_orb" in known and "vision_annotation" in known


def test_pick_widget(monkeypatch):
    monkeypatch.setattr(server, "KNOWN_WIDGETS", {"weather_orb", "timer", "panel"})
    assert server.pick_widget("timer") == "timer"
    assert server.pick_widget("does_not_exist") == "weather_orb"  # first builtin in known
    monkeypatch.setattr(server, "KNOWN_WIDGETS", {"xyz"})
    assert server.pick_widget("abc") == "xyz"  # sorted fallback (no builtin in known)
    monkeypatch.setattr(server, "KNOWN_WIDGETS", set())
    assert server.pick_widget("anything") == "anything"  # empty registry -> preferred


# --------------------------------------------------------------------------- #
# tiny NLU + helpers                                                          #
# --------------------------------------------------------------------------- #

def test_parse_helpers():
    assert server.parse_city("weather in tokyo") == "Tokyo"
    assert server.parse_city("just a greeting") == "Tokyo"
    assert server.parse_minutes("start a 5 minute timer") == 5
    assert server.parse_minutes("start a timer") == 5
    assert server.is_vision_query("what is this?") is True
    assert server.is_vision_query("hello there") is False


def test_default_model():
    assert server._default_model("openai") == "gpt-4o"
    assert server._default_model("ghost-provider") == "mock"


def test_ws_path():
    assert server._ws_path(FakeWS(path="/vision")) == "/vision"
    assert server._ws_path(FakeWS(path="/jarvis", use_request=False)) == "/jarvis"


def test_is_vision_path(monkeypatch):
    assert server._is_vision_path("/vision") is True
    assert server._is_vision_path("/audio/vision?x=1") is True
    assert server._is_vision_path("/jarvis") is False
    monkeypatch.setattr(server, "VISION_PATH", "")
    assert server._is_vision_path("/vision") is False


# --------------------------------------------------------------------------- #
# builders + settings                                                         #
# --------------------------------------------------------------------------- #

def test_build_server_settings_and_widgets_are_conformant():
    st = server.ConnState()
    st.settings = {"provider": "openai", "model": "gpt-4o", "base_url": None}
    st.keys_set = {"openai"}
    jp.validate(jp.new_message(jp.MessageType.SERVER_SETTINGS, server.build_server_settings(st), session="S"))
    for holo in (
        server.build_weather_orb("Tokyo"),
        server.build_timer(5),
        server.build_panel("t", "b"),
        server.build_vision_annotation("coffee mug", 0.8, [0.3, 0.8, 0.7], "ceramic"),
        server.build_vision_annotation("lamp", 0.8, [0.0, 0.0, 0.0]),  # detail=None branch
    ):
        jp.validate(jp.new_message(jp.MessageType.HOLO_SPAWN, holo, session="S"))


def test_handle_settings_update_branches():
    st = server.ConnState()
    st.session = "S"

    ws = FakeWS()
    run(server.handle_settings_update(ws, st, {}))  # no llm object
    assert any(jp.decode(s).payload.get("code") == "invalid_settings" for s in ws.sent)

    ws = FakeWS()
    run(server.handle_settings_update(ws, st, {"llm": {"provider": "ghost"}}))  # unknown provider
    assert any(jp.decode(s).payload.get("code") == "provider_unavailable" for s in ws.sent)

    ws = FakeWS()
    run(server.handle_settings_update(ws, st, {"llm": {"provider": "openai", "model": "gpt-4o", "base_url": "http://x", "api_key": "sk"}}))
    settings = [jp.decode(s) for s in ws.sent if jp.decode(s).type == "server.settings"]
    assert settings and settings[0].payload["llm"]["current"]["key_set"] is True

    ws = FakeWS()
    run(server.handle_settings_update(ws, st, {"llm": {}}))  # empty llm -> just echo
    assert any(jp.decode(s).type == "server.settings" for s in ws.sent)


# --------------------------------------------------------------------------- #
# send + perception selection                                                 #
# --------------------------------------------------------------------------- #

def test_send_valid_and_refuses_invalid():
    ws = FakeWS()
    msg = run(server.send(ws, "S", jp.MessageType.AGENT_SPEECH, jp.AgentSpeech(text="hi")))
    assert msg is not None and len(ws.sent) == 1

    ws2 = FakeWS()
    refused = run(server.send(ws2, "S", jp.MessageType.AGENT_SPEECH, {"final": True}))  # missing text
    assert refused is None and ws2.sent == []


def test_pick_perceived_object():
    st = server.ConnState()
    assert server.pick_perceived_object(st) == ("coffee mug", 0.78, [0.3, 0.8, 0.7])
    st.perception["scene_objects"] = {"objects": [{"label": "lamp", "confidence": 0.9, "position": [1, 2, 3]}]}
    assert server.pick_perceived_object(st) == ("lamp", 0.9, [1, 2, 3])
    st.perception["scene_objects"] = {"objects": [{"label": "y", "position": [1, 2]}]}  # bad pos length
    assert server.pick_perceived_object(st)[2] == [0.3, 0.8, 0.7]


# --------------------------------------------------------------------------- #
# turn handlers                                                               #
# --------------------------------------------------------------------------- #

def test_handle_turn_weather_timer_panel():
    for text, widget in [("show me the weather in tokyo", "weather_orb"),
                         ("start a 5 minute timer", "timer"),
                         ("tell me a joke", "panel")]:
        ws = FakeWS()
        st = server.ConnState()
        st.session = "S"
        run(server.handle_turn(ws, st, text, False))
        spawns = [jp.decode(s) for s in ws.sent if jp.decode(s).type == "holo.spawn"]
        assert spawns and spawns[0].payload["widget_type"] == widget


def test_handle_turn_vision_query_and_attach():
    ws = FakeWS()
    st = server.ConnState()
    st.session = "S"
    run(server.handle_turn(ws, st, "what is this on my desk?", False))  # vision query
    assert any(jp.decode(s).type == "agent.observation" for s in ws.sent)

    ws2 = FakeWS()
    st2 = server.ConnState()
    st2.session = "S"
    st2.perception["vision_frame"] = {"frame_id": "F"}
    run(server.handle_turn(ws2, st2, "tell me about it", True))  # attach_perception + buffered frame
    assert any(jp.decode(s).payload.get("widget_type") == "vision_annotation"
               for s in ws2.sent if jp.decode(s).type == "holo.spawn")


def test_handle_turn_spawn_refused(monkeypatch):
    async def refuse(*a, **k):
        return None

    monkeypatch.setattr(server, "send", refuse)
    st = server.ConnState()
    st.session = "S"
    run(server.handle_turn(FakeWS(), st, "weather in paris", False))
    assert st.objects == {}  # spawn refused -> nothing recorded


def test_handle_vision_turn_states(monkeypatch):
    # vision inactive -> emits start; mug -> detail set; records the spawned object.
    ws = FakeWS()
    st = server.ConnState()
    st.session = "S"
    st.perception["scene_objects"] = {"objects": [{"label": "coffee mug", "confidence": 0.8, "position": [0.3, 0.8, 0.7]}]}
    run(server.handle_vision_turn(ws, st, "what is this"))
    reqs = [jp.decode(s).payload.get("action") for s in ws.sent if jp.decode(s).type == "perception.request"]
    assert "start" in reqs and "stop" in reqs and st.vision_active is False and st.objects

    # already active -> no second start; non-mug -> detail None.
    ws2 = FakeWS()
    st2 = server.ConnState()
    st2.session = "S"
    st2.vision_active = True
    st2.perception["scene_objects"] = {"objects": [{"label": "lamp", "confidence": 0.5, "position": [1, 1, 1]}]}
    run(server.handle_vision_turn(ws2, st2, "describe what you see"))
    actions = [jp.decode(s).payload.get("action") for s in ws2.sent if jp.decode(s).type == "perception.request"]
    assert "start" not in actions and "stop" in actions


def test_handle_vision_turn_spawn_refused(monkeypatch):
    async def refuse(*a, **k):
        return None

    monkeypatch.setattr(server, "send", refuse)
    st = server.ConnState()
    st.session = "S"
    run(server.handle_vision_turn(FakeWS(), st, "what is this"))
    assert st.objects == {}


def test_handle_interaction_unknown_timer_and_generic():
    st = server.ConnState()
    st.session = "S"

    ws = FakeWS()
    run(server.handle_interaction(ws, st, {"object_id": "ghost", "action": "tap"}))
    assert any(jp.decode(s).payload.get("code") == "unknown_widget" for s in ws.sent if jp.decode(s).type == "server.error")

    st.objects["T1"] = {"widget_type": "timer", "props": {"state": "running"}}
    ws = FakeWS()
    run(server.handle_interaction(ws, st, {"object_id": "T1", "action": "tap", "element": "pause_button"}))
    upd = [jp.decode(s) for s in ws.sent if jp.decode(s).type == "holo.update"]
    assert upd and upd[0].payload["props"]["state"] == "paused"

    ws = FakeWS()  # second tap: paused -> running (ternary other branch)
    run(server.handle_interaction(ws, st, {"object_id": "T1", "action": "tap", "element": "pause_button"}))
    upd = [jp.decode(s) for s in ws.sent if jp.decode(s).type == "holo.update"]
    assert upd[0].payload["props"]["state"] == "running"

    st.objects["P1"] = {"widget_type": "panel", "props": {}}
    ws = FakeWS()  # generic widget -> highlighted
    run(server.handle_interaction(ws, st, {"object_id": "P1", "action": "tap"}))
    assert any(jp.decode(s).payload.get("props", {}).get("highlighted") for s in ws.sent if jp.decode(s).type == "holo.update")


# --------------------------------------------------------------------------- #
# /vision binary transport                                                    #
# --------------------------------------------------------------------------- #

def test_parse_vision_frame_branches():
    assert server.parse_vision_frame(b"")[0] is False                       # < 4 bytes
    assert server.parse_vision_frame((99).to_bytes(4, "big") + b"x")[0] is False  # header_len > frame
    bad_json = b"{bad"
    assert server.parse_vision_frame(len(bad_json).to_bytes(4, "big") + bad_json)[0] is False
    invalid = json.dumps({"frame_id": "F"}).encode()                        # missing camera/format
    assert server.parse_vision_frame(len(invalid).to_bytes(4, "big") + invalid)[0] is False
    good = json.dumps({"frame_id": "F", "camera": "rgb_center", "format": "jpeg", "transport": "binary"}).encode()
    ok, info = server.parse_vision_frame(len(good).to_bytes(4, "big") + good + b"\xff\xd8")
    assert ok is True and "camera=rgb_center" in info


def test_vision_handler_ok_rejected_text():
    good = json.dumps({"frame_id": "F", "camera": "rgb_center", "format": "jpeg", "transport": "binary"}).encode()
    frame = len(good).to_bytes(4, "big") + good + b"\xff\xd8"
    ws = FakeWS(incoming=[frame, b"\x00\x00", "a text frame"])
    run(server.vision_handler(ws))  # ok + rejected (<4) + text-frame (ignored)


def test_vision_handler_connection_closed():
    ws = FakeWS(incoming=[], raise_exc=_closed())
    run(server.vision_handler(ws))  # except ConnectionClosed -> finally


# --------------------------------------------------------------------------- #
# top-level routing                                                           #
# --------------------------------------------------------------------------- #

def test_handler_routes_to_vision():
    good = json.dumps({"frame_id": "F", "camera": "rgb_center", "format": "jpeg", "transport": "binary"}).encode()
    ws = FakeWS(incoming=[len(good).to_bytes(4, "big") + good], path="/vision")
    run(server.handler(ws))


def test_handler_main_path_and_connection_closed():
    ws = FakeWS(incoming=[enc("client.hello", {"device": "quest3", "protocol_version": "1.3.0"})], path="/jarvis")
    run(server.handler(ws))
    assert "server.hello_ack" in sent_types(ws)

    ws2 = FakeWS(incoming=[], path="/jarvis", raise_exc=_closed())
    run(server.handler(ws2))  # main_handler raises ConnectionClosed -> handler except


# --------------------------------------------------------------------------- #
# main_handler: every message branch                                          #
# --------------------------------------------------------------------------- #

def test_main_handler_covers_all_message_branches():
    frames = [
        b"\x01\x02",                                                        # binary on /jarvis -> continue
        "not json at all",                                                  # bad frame -> server.error
        enc("client.hello", {"device": "quest3", "protocol_version": "1.3.0"}),
        enc("client.heartbeat", {}),
        enc("user.voice_partial", {"text": "we"}),                         # partial -> no turn
        enc("perception.scene_objects", {"objects": [{"label": "mug", "position": [0.3, 0.8, 0.7]}]}),
        enc("user.voice_transcript", {"text": "what is this?", "attach_perception": True}),
        enc("client.interaction", {"object_id": "ghost", "action": "tap"}),
        enc("client.settings_get", {}),
        enc("client.settings_update", {"llm": {"provider": "openai", "api_key": "sk"}}),
        enc("client.scene", {}),
        enc("client.ack", {}),
        enc("vendor.unknown", {}),                                         # forward-compatible ignore
        enc("client.bye", {"reason": "done"}),
        enc("client.heartbeat", {}),                                       # after bye -> never processed
    ]
    ws = FakeWS(incoming=frames)
    st = server.ConnState()
    run(server.main_handler(ws, st))
    types = sent_types(ws)
    assert "server.hello_ack" in types
    assert "server.settings" in types
    assert "agent.observation" in types
    assert "server.error" in types
    assert types.count("server.heartbeat") == 1  # the post-bye heartbeat was not processed


@pytest.mark.parametrize("frame", [
    enc("user.text", {"text": "hi"}),
    enc("client.interaction", {"object_id": "z", "action": "tap"}),
    enc("client.settings_get", {}),
    enc("client.settings_update", {"llm": {"provider": "mock"}}),
])
def test_main_handler_assigns_session_when_missing(frame):
    ws = FakeWS(incoming=[frame])
    st = server.ConnState()
    assert st.session is None
    run(server.main_handler(ws, st))
    assert st.session is not None  # the `session is None` branch assigned one


# --------------------------------------------------------------------------- #
# main() bootstrap                                                            #
# --------------------------------------------------------------------------- #

def test_main_serves_then_cancels(monkeypatch):
    class FakeServer:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

    monkeypatch.setattr(server.websockets, "serve", lambda *a, **k: FakeServer())

    async def drive():
        task = asyncio.create_task(server.main())
        await asyncio.sleep(0.1)  # let it bind + reach `await stop`
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    asyncio.run(drive())
