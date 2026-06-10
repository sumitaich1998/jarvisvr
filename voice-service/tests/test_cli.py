"""Coverage for the jarvis-voice CLI (jarvis_voice.__main__)."""

from __future__ import annotations

import asyncio

import pytest

import jarvis_voice.audio as audio_mod
import jarvis_voice.protocol as protocol_mod
import jarvis_voice.tts as tts_mod
from jarvis_voice.__main__ import main


# --- helpers ----------------------------------------------------------------

class FakeMic:
    def __init__(self, frames):
        self.frames = frames

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def __iter__(self):
        return iter(self.frames)


def _feed_inputs(monkeypatch, lines):
    it = iter(lines)

    def fake_input(prompt=""):
        try:
            return next(it)
        except StopIteration:
            raise EOFError

    monkeypatch.setattr("builtins.input", fake_input)


# --- version / no-command ---------------------------------------------------

def test_version_exits_zero():
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0


def test_no_command_errors():
    with pytest.raises(SystemExit) as exc:
        main([])
    assert exc.value.code == 2


# --- say --------------------------------------------------------------------

def test_say_plain(capsys):
    assert main(["say", "hello", "--tts", "mock"]) == 0
    assert "hello" in capsys.readouterr().out


def test_say_with_out_and_play(tmp_path):
    out = tmp_path / "o.wav"
    assert main(["say", "hi there", "--out", str(out), "--tts", "mock"]) == 0
    assert out.read_bytes()[:4] == b"RIFF"


def test_say_with_out_no_play(tmp_path):
    out = tmp_path / "o.wav"
    assert main(["say", "hi", "--out", str(out), "--no-play", "--tts", "mock"]) == 0
    assert out.exists()


# --- devices ----------------------------------------------------------------

def test_devices(capsys):
    assert main(["devices"]) == 0
    assert "audio backend available" in capsys.readouterr().out


# --- demo -------------------------------------------------------------------

def test_demo_simulate_repl(monkeypatch, capsys):
    _feed_inputs(monkeypatch, ["hello jarvis", ""])  # one utterance then blank -> quit
    assert main(["demo", "--simulate", "--stt", "mock", "--tts", "mock"]) == 0
    assert "transcript" in capsys.readouterr().out


def test_demo_simulate_eof(monkeypatch):
    _feed_inputs(monkeypatch, [])  # immediate EOF -> break
    assert main(["demo", "--simulate"]) == 0


def test_demo_mic_path(monkeypatch):
    monkeypatch.setattr(audio_mod, "audio_io_available", lambda: True)
    monkeypatch.setattr(audio_mod, "MicStream", lambda **kw: FakeMic([audio_mod.silence(30)] * 2))
    assert main(["demo"]) == 0


def test_demo_mic_unavailable_falls_to_simulate(monkeypatch):
    def boom(**kw):
        raise audio_mod.AudioUnavailable("no mic")

    monkeypatch.setattr(audio_mod, "audio_io_available", lambda: True)
    monkeypatch.setattr(audio_mod, "MicStream", boom)
    _feed_inputs(monkeypatch, [""])  # quit the simulate REPL immediately
    assert main(["demo"]) == 0


def test_demo_mic_keyboard_interrupt(monkeypatch):
    class KIMic(FakeMic):
        def __iter__(self):
            raise KeyboardInterrupt

    monkeypatch.setattr(audio_mod, "audio_io_available", lambda: True)
    monkeypatch.setattr(audio_mod, "MicStream", lambda **kw: KIMic([]))
    assert main(["demo"]) == 0


# --- ambient ----------------------------------------------------------------

def test_ambient_simulate(monkeypatch, capsys):
    _feed_inputs(monkeypatch, ["someone talking", ""])
    assert main(["ambient", "--simulate"]) == 0
    out = capsys.readouterr().out
    assert "scene" in out or "event" in out


def test_ambient_simulate_sound_events_off(monkeypatch):
    # NullSoundEvents has no set_canned -> the try/except guard is exercised.
    _feed_inputs(monkeypatch, [""])
    assert main(["ambient", "--simulate", "--sound-events", "off"]) == 0


def test_ambient_simulate_repl_keyboard_interrupt(monkeypatch):
    def ki(prompt=""):
        raise KeyboardInterrupt

    monkeypatch.setattr("builtins.input", ki)
    assert main(["ambient", "--simulate"]) == 0


def test_ambient_mic_path(monkeypatch):
    monkeypatch.setattr(audio_mod, "audio_io_available", lambda: True)
    monkeypatch.setattr(audio_mod, "MicStream", lambda **kw: FakeMic([audio_mod.silence(30)] * 2))
    assert main(["ambient"]) == 0


def test_ambient_mic_unavailable_falls_to_simulate(monkeypatch):
    def boom(**kw):
        raise audio_mod.AudioUnavailable("no mic")

    monkeypatch.setattr(audio_mod, "audio_io_available", lambda: True)
    monkeypatch.setattr(audio_mod, "MicStream", boom)
    _feed_inputs(monkeypatch, [""])
    assert main(["ambient"]) == 0


def test_ambient_mic_keyboard_interrupt(monkeypatch):
    class KIMic(FakeMic):
        def __iter__(self):
            raise KeyboardInterrupt

    monkeypatch.setattr(audio_mod, "audio_io_available", lambda: True)
    monkeypatch.setattr(audio_mod, "MicStream", lambda **kw: KIMic([]))
    assert main(["ambient"]) == 0


# --- bridge -----------------------------------------------------------------

def test_bridge_connect_fails_fast(monkeypatch):
    async def fast_sleep(_):
        return None

    monkeypatch.setattr(asyncio, "sleep", fast_sleep)
    rc = main(["bridge", "--no-mic", "--max-retries", "1", "--backend", "ws://127.0.0.1:1/jarvis"])
    assert rc == 0


def test_bridge_keyboard_interrupt(monkeypatch):
    import jarvis_voice.bridge as bridge_mod

    class FakeBridge:
        async def connect_and_run(self, max_retries=0):
            raise KeyboardInterrupt

    monkeypatch.setattr(bridge_mod, "build_bridge", lambda *a, **k: FakeBridge())
    assert main(["bridge"]) == 0


# --- selftest ---------------------------------------------------------------

def test_selftest_passes():
    assert main(["selftest"]) == 0


@pytest.mark.parametrize(
    "target_mod,attr",
    [
        ("protocol", "voice_transcript"),  # check 1
        ("audio", "tone"),                 # checks 3/6/7/8
        ("protocol", "client_hello"),      # check 5
        ("protocol", "audio_scene"),       # check 9
    ],
)
def test_selftest_reports_failures(monkeypatch, target_mod, attr):
    def boom(*a, **k):
        raise RuntimeError("forced")

    mod = {"protocol": protocol_mod, "audio": audio_mod}[target_mod]
    monkeypatch.setattr(mod, attr, boom)
    assert main(["selftest"]) == 1


def test_selftest_tts_failure(monkeypatch):
    monkeypatch.setattr(tts_mod.MockTTS, "synthesize", lambda self, text: (_ for _ in ()).throw(RuntimeError("x")))
    assert main(["selftest"]) == 1


# --- overrides + logging ----------------------------------------------------

def test_apply_all_overrides(capsys):
    rc = main([
        "--wake", "energy", "--stt", "mock", "--tts", "mock",
        "--backend", "ws://example/jarvis", "--ambient", "off",
        "--sound-events", "off", "--language", "es", "--log-level", "DEBUG",
        "devices",
    ])
    assert rc == 0
