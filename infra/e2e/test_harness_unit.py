"""Direct unit tests for the e2e harness + holo-tools validator (not via the live
socket). Covers ConformanceClient, the helpers, print_report, _vision_url,
_exercise_vision_binary's failure path, every run_* scenario's violation
branches (via a scripted fake connection), and main()."""

from __future__ import annotations

import asyncio
import json
import pathlib

import pytest

import harness
import holo_tools as ht
import jarvis_protocol as jp

run = asyncio.run
MT = jp.MessageType


def F(type_, payload):
    return jp.encode(jp.new_message(type_, payload, session="S"))


class FakeConn:
    """Duck-typed connection: async CM + recv()/send(). recv() blocks when the
    scripted queue is empty (so recv_until times out under a short timeout)."""

    def __init__(self, frames=None):
        self._frames = list(frames or [])
        self.sent = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def send(self, data):
        self.sent.append(data)

    async def recv(self):
        if self._frames:
            return self._frames.pop(0)
        await asyncio.sleep(3600)  # block -> wait_for times out


def patch_connect(monkeypatch, script):
    monkeypatch.setattr(harness.websockets, "connect", lambda *a, **k: FakeConn(script))


# --------------------------------------------------------------------------- #
# holo_tools validator                                                        #
# --------------------------------------------------------------------------- #

def test_holo_tools_parsing_helpers():
    assert ht._entry_type({"widget_type": "a"}) == "a"
    assert ht._entry_type({"type": "b"}) == "b"
    assert ht._entry_type({"nope": 1}) is None
    assert ht._entry_type("x") is None
    assert ht._entries({"widgets": [{"widget_type": "a"}, "bad", {"no": 1}]}) == {"a": {"widget_type": "a"}}
    assert set(ht._entries({"alpha": {"x": 1}, "$schema": "s"})) == {"alpha"}
    assert set(ht._entries([{"id": "c"}, "bad"])) == {"c"}
    assert ht._entries(42) == {}
    assert ht._entries({"widgets": 123}) == {}  # widgets neither dict nor list
    assert ht._looks_like_schema({"type": "object"}) is True
    assert ht._looks_like_schema({"no": 1}) is False
    assert ht._looks_like_schema("x") is False
    assert ht._props_schema({"props_schema": {"type": "object"}}) == {"type": "object"}
    assert ht._props_schema({"no": 1}) is None
    assert ht._props_schema("x") is None


def test_find_registry_variants(monkeypatch, tmp_path):
    reg = tmp_path / "registry.json"
    reg.write_text("{}")
    monkeypatch.setenv("HOLO_TOOLS_REGISTRY", str(reg))
    assert ht.find_registry() == reg
    monkeypatch.delenv("HOLO_TOOLS_REGISTRY", raising=False)
    assert ht.find_registry() is not None  # upward search finds the repo registry
    monkeypatch.setattr(pathlib.Path, "is_file", lambda self: False)
    assert ht.find_registry() is None


def test_holo_tools_load_variants(monkeypatch, tmp_path):
    monkeypatch.setattr(ht, "find_registry", lambda: None)
    assert ht.HoloToolsValidator.load().available is False

    bad = tmp_path / "registry.json"
    bad.write_text("{ bad json")
    monkeypatch.setattr(ht, "find_registry", lambda: bad)
    assert ht.HoloToolsValidator.load().available is False

    good = tmp_path / "good.json"
    good.write_text(json.dumps({"widgets": [{"widget_type": "weather_orb"}]}))
    monkeypatch.setattr(ht, "find_registry", lambda: good)
    assert ht.HoloToolsValidator.load(strict_props=True).available is True


def test_validate_holo_all_branches():
    registry = {"widgets": [
        {"widget_type": "weather_orb", "props_schema": {
            "type": "object", "required": ["city"], "additionalProperties": False,
            "properties": {"city": {"type": "string"}}}},
        {"widget_type": "plain"},  # no props schema
    ]}
    v = ht.HoloToolsValidator(registry)

    assert ht.HoloToolsValidator(None).validate_holo({"widget_type": "weather_orb"}) == ([], [])
    assert v.validate_holo({"widget_type": "weather_orb", "props": {"city": "Tokyo"}}) == ([], [])

    errs, warns = v.validate_holo({"widget_type": "weather_orb", "props": {"nope": 1}})
    assert errs == [] and warns  # invalid props -> warning by default

    serrs, _ = ht.HoloToolsValidator(registry, strict_props=True).validate_holo(
        {"widget_type": "weather_orb", "props": {"nope": 1}})
    assert serrs  # strict -> error

    pe, pw = v.validate_holo({"widget_type": "vision_annotation", "props": {}})
    assert pe == [] and pw  # pending v1.1 widget -> warning, not error

    ue, _ = v.validate_holo({"widget_type": "totally_unknown", "props": {}})
    assert ue  # unknown + not pending -> error

    ne, nw = v.validate_holo({"widget_type": "plain", "props": {}})
    assert ne == [] and nw  # in registry but no props schema -> warning


# --------------------------------------------------------------------------- #
# helpers / Report / print_report / _vision_url                               #
# --------------------------------------------------------------------------- #

def test_helpers_and_report():
    assert harness._is_done({"type": "agent.thinking", "payload": {"stage": "done"}}) is True
    assert harness._is_done({"type": "agent.speech", "payload": {}}) is False
    assert harness._first([{"type": "a"}, {"type": "b"}], "b") == {"type": "b"}
    assert harness._first([{"type": "a"}], "z") is None
    r = harness.Report()
    assert r.ok() is True
    r.violations.append("x")
    assert r.ok() is False


def test_print_report_pass_and_fail(capsys):
    harness.print_report(harness.Report(steps=["s"], sent=1, received=2, seen_types=["a"]), title="t")
    assert "PASS" in capsys.readouterr().out
    harness.print_report(harness.Report(warnings=["w"], violations=["v"]))
    out = capsys.readouterr().out
    assert "FAIL" in out and "w" in out and "v" in out


def test_vision_url_branches():
    assert harness._vision_url("ws://h:8765/jarvis") == "ws://h:8765/vision"
    assert harness._vision_url("ws://h:8765/jarvis?x=1") == "ws://h:8765/vision"
    assert harness._vision_url("ws://h:8765/other") == "ws://h:8765/vision"  # else: has path segment
    assert harness._vision_url("ws://h:8765") == "ws://h:8765/vision"        # else: no path segment


def test_exercise_vision_binary_failure():
    report = harness.Report()
    run(harness._exercise_vision_binary("ws://127.0.0.1:1/vision", report))  # nothing listening
    assert any("/vision transport failed" in v for v in report.violations)


# --------------------------------------------------------------------------- #
# ConformanceClient                                                           #
# --------------------------------------------------------------------------- #

def _client(frames=None, *, strict_props=False, registry=None):
    report = harness.Report()
    holo = ht.HoloToolsValidator(registry, strict_props=strict_props)
    client = harness.ConformanceClient(FakeConn(frames), report, holo, recv_timeout=0.15)
    return client, report


def test_client_send_valid_and_invalid():
    client, report = _client()
    run(client.send("agent.speech", jp.AgentSpeech(text="hi")))
    assert report.sent == 1 and not report.violations

    client2, report2 = _client()
    run(client2.send("agent.speech", {"final": True}))  # missing text -> OUTGOING violation
    assert any(v.startswith("OUTGOING") for v in report2.violations)


def test_client_check_spawn_errors_and_warnings():
    registry = {"widgets": [{"widget_type": "weather_orb", "props_schema": {
        "type": "object", "required": ["city"], "additionalProperties": False,
        "properties": {"city": {"type": "string"}}}}]}
    client, report = _client(registry=registry)
    tf = {"anchor": "world", "position": [0, 0, 0], "rotation": [0, 0, 0, 1], "scale": [1, 1, 1]}
    client._check(F("holo.spawn", {"object_id": "O", "widget_type": "ghost", "transform": tf}))
    assert any("holo-tools" in v for v in report.violations)  # unknown widget -> error
    client._check(F("holo.spawn", {"object_id": "O", "widget_type": "weather_orb", "props": {"x": 1}, "transform": tf}))
    assert any("holo-tools" in w for w in report.warnings)  # bad props -> warning


def test_client_recv_until_match_timeout_and_maxmsgs():
    client, report = _client([F("server.hello_ack", {"session": "S", "protocol_version": "1.3.0"})])
    docs = run(client.recv_until(lambda d: d.get("type") == "server.hello_ack", what="ack"))
    assert docs and not report.violations

    client2, report2 = _client()  # empty -> recv blocks -> timeout
    run(client2.recv_until(lambda d: False, what="never"))
    assert any("timeout" in v for v in report2.violations)

    client3, report3 = _client([F("server.heartbeat", {})] * 3)
    run(client3.recv_until(lambda d: False, what="hb", max_msgs=2))
    assert any("did not observe" in v for v in report3.violations)


# --------------------------------------------------------------------------- #
# run_* scenarios: violation branches via scripted fake connections           #
# --------------------------------------------------------------------------- #

def test_run_conformance_no_acks(monkeypatch):
    patch_connect(monkeypatch, [])  # server says nothing -> every recv_until times out
    report = run(harness.run_conformance("ws://x/jarvis", recv_timeout=0.1))
    blob = "\n".join(report.violations)
    assert "did not assign a session" in blob
    assert "no agent.speech" in blob and "no holo.spawn" in blob


def test_run_conformance_no_holo_update(monkeypatch):
    tf = {"anchor": "world", "position": [0, 0, 0], "rotation": [0, 0, 0, 1], "scale": [1, 1, 1]}
    script = [
        F("server.hello_ack", {"session": "S", "protocol_version": "1.3.0"}),
        F("server.heartbeat", {}),
        F("agent.speech", {"text": "x", "final": True}),
        F("holo.spawn", {"object_id": "W1", "widget_type": "weather_orb",
                         "props": {"city": "Tokyo", "temp_c": 18, "condition": "clouds"}, "transform": tf}),
        F("agent.thinking", {"stage": "done"}),
        F("agent.speech", {"text": "x", "final": True}),
        F("holo.spawn", {"object_id": "T1", "widget_type": "timer",
                         "props": {"duration_ms": 1000, "remaining_ms": 1000, "state": "running"}, "transform": tf}),
        F("agent.thinking", {"stage": "done"}),
        F("agent.thinking", {"stage": "done"}),  # tap turn: done only -> no holo.update
    ]
    patch_connect(monkeypatch, script)
    report = run(harness.run_conformance("ws://x/jarvis", recv_timeout=0.3))
    assert any("no holo.update" in v for v in report.violations)


def test_run_multimodal_no_acks(monkeypatch):
    patch_connect(monkeypatch, [])
    report = run(harness.run_multimodal_conformance("ws://x/jarvis", recv_timeout=0.1))
    blob = "\n".join(report.violations)
    assert "did not assign a session" in blob
    for needle in ("no perception.request{start}", "no agent.thinking{perceiving}",
                   "no agent.observation", "no holo.spawn", "no agent.speech"):
        assert needle in blob


def test_run_multimodal_wrong_widget(monkeypatch):
    tf = {"anchor": "world", "position": [0, 0, 0], "rotation": [0, 0, 0, 1], "scale": [1, 1, 1]}
    script = [
        F("server.hello_ack", {"session": "S", "protocol_version": "1.3.0"}),
        F("perception.request", {"stream": "vision", "action": "start"}),
        F("agent.thinking", {"stage": "perceiving"}),
        F("agent.observation", {"text": "I see"}),
        F("holo.spawn", {"object_id": "O", "widget_type": "panel", "props": {"title": "t"}, "transform": tf}),
        F("agent.speech", {"text": "x", "final": True}),
        F("perception.request", {"stream": "vision", "action": "stop"}),
    ]
    patch_connect(monkeypatch, script)
    report = run(harness.run_multimodal_conformance("ws://x/jarvis", recv_timeout=0.3))
    assert any("expected holo.spawn vision_annotation" in v for v in report.violations)


def test_run_barge_in_no_acks(monkeypatch):
    patch_connect(monkeypatch, [])
    report = run(harness.run_barge_in_conformance("ws://x/jarvis", recv_timeout=0.1))
    assert any("did not assign a session" in v for v in report.violations)


def test_run_barge_in_server_error(monkeypatch):
    script = [
        F("server.hello_ack", {"session": "S", "protocol_version": "1.3.0"}),
        F("server.error", {"code": "x", "message": "y"}),
        F("server.heartbeat", {}),
    ]
    patch_connect(monkeypatch, script)
    report = run(harness.run_barge_in_conformance("ws://x/jarvis", recv_timeout=0.3))
    assert any("barge_in produced a server.error" in v for v in report.violations)


def test_run_settings_no_acks(monkeypatch):
    patch_connect(monkeypatch, [])
    report = run(harness.run_settings_conformance("ws://x/jarvis", recv_timeout=0.1))
    assert any("no server.settings reply" in v for v in report.violations)


def test_run_settings_bad_values(monkeypatch):
    script = [
        F("server.hello_ack", {"session": "S", "protocol_version": "1.3.0"}),
        F("server.settings", {"llm": {"current": {"provider": "mock", "model": "mock", "key_set": False}, "providers": []}}),
        F("server.settings", {"llm": {"current": {"provider": "mock", "model": "mock", "key_set": False},
                                      "providers": [{"id": "mock", "name": "M", "default_model": "mock",
                                                     "needs_key": False, "needs_base_url": False, "key_set": False}]}}),
    ]
    patch_connect(monkeypatch, script)
    report = run(harness.run_settings_conformance("ws://x/jarvis", recv_timeout=0.3))
    blob = "\n".join(report.violations)
    assert "missing current/providers" in blob
    assert "current.provider" in blob and "current.model" in blob and "key_set should be true" in blob


def test_run_settings_key_leak(monkeypatch):
    leak = F("server.settings", {
        "llm": {"current": {"provider": "openai", "model": "gpt-4o", "key_set": True},
                "providers": [{"id": "openai", "name": "O", "default_model": "gpt-4o",
                               "needs_key": True, "needs_base_url": False, "key_set": True}]},
        "leaked": "sk-e2e-SECRET-key", "api_key": "sk-e2e-SECRET-key",
    })
    script = [F("server.hello_ack", {"session": "S", "protocol_version": "1.3.0"}), leak, leak]
    patch_connect(monkeypatch, script)
    report = run(harness.run_settings_conformance("ws://x/jarvis", recv_timeout=0.3))
    blob = "\n".join(report.violations)
    assert "api key value leaked" in blob and "'api_key' field appeared" in blob


# --------------------------------------------------------------------------- #
# main()                                                                       #
# --------------------------------------------------------------------------- #

def test_main_connection_error(monkeypatch):
    async def boom(*a, **k):
        raise OSError("refused")

    monkeypatch.setattr(harness, "run_conformance", boom)
    monkeypatch.setattr("sys.argv", ["harness", "--url", "ws://127.0.0.1:1/jarvis"])
    assert harness.main() == 2


def test_main_all_pass_and_one_fail(monkeypatch):
    async def ok(url, **k):
        return harness.Report()

    async def fail(url, **k):
        r = harness.Report()
        r.violations.append("boom")
        return r

    for name in ("run_conformance", "run_multimodal_conformance", "run_barge_in_conformance", "run_settings_conformance"):
        monkeypatch.setattr(harness, name, ok)
    monkeypatch.setattr("sys.argv", ["harness", "--strict-props"])
    assert harness.main() == 0

    monkeypatch.setattr(harness, "run_settings_conformance", fail)
    monkeypatch.setattr("sys.argv", ["harness"])
    assert harness.main() == 1
