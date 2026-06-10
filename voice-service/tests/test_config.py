"""Exhaustive coverage of jarvis_voice.config (env knobs + derived properties)."""

from __future__ import annotations

from jarvis_voice import config as cfgmod
from jarvis_voice.config import Config


# --- low-level env helpers --------------------------------------------------

def test_env_default_and_value(monkeypatch):
    monkeypatch.delenv("JARVIS_X", raising=False)
    assert cfgmod._env("JARVIS_X", "def") == "def"
    monkeypatch.setenv("JARVIS_X", "val")
    assert cfgmod._env("JARVIS_X", "def") == "val"
    monkeypatch.setenv("JARVIS_X", "")  # empty -> default
    assert cfgmod._env("JARVIS_X", "def") == "def"


def test_env_opt(monkeypatch):
    monkeypatch.delenv("JARVIS_X", raising=False)
    assert cfgmod._env_opt("JARVIS_X") is None
    monkeypatch.setenv("JARVIS_X", "v")
    assert cfgmod._env_opt("JARVIS_X") == "v"


def test_env_int_valid_and_invalid(monkeypatch):
    monkeypatch.setenv("JARVIS_N", "42")
    assert cfgmod._env_int("JARVIS_N", 7) == 42
    monkeypatch.setenv("JARVIS_N", "notint")
    assert cfgmod._env_int("JARVIS_N", 7) == 7


def test_env_float_valid_and_invalid(monkeypatch):
    monkeypatch.setenv("JARVIS_F", "3.5")
    assert cfgmod._env_float("JARVIS_F", 1.0) == 3.5
    monkeypatch.setenv("JARVIS_F", "nan-ish-xyz")
    assert cfgmod._env_float("JARVIS_F", 1.0) == 1.0


def test_env_int_opt(monkeypatch):
    monkeypatch.delenv("JARVIS_D", raising=False)
    assert cfgmod._env_int_opt("JARVIS_D") is None
    monkeypatch.setenv("JARVIS_D", "5")
    assert cfgmod._env_int_opt("JARVIS_D") == 5
    monkeypatch.setenv("JARVIS_D", "bad")
    assert cfgmod._env_int_opt("JARVIS_D") is None


def test_env_bool_all_paths(monkeypatch):
    monkeypatch.delenv("JARVIS_B", raising=False)
    assert cfgmod._env_bool("JARVIS_B", True) is True   # unset -> default
    monkeypatch.setenv("JARVIS_B", "yes")
    assert cfgmod._env_bool("JARVIS_B", False) is True
    monkeypatch.setenv("JARVIS_B", "OFF")
    assert cfgmod._env_bool("JARVIS_B", True) is False
    monkeypatch.setenv("JARVIS_B", "maybe")             # unknown -> default
    assert cfgmod._env_bool("JARVIS_B", True) is True


# --- Config.from_env --------------------------------------------------------

def test_from_env_defaults(monkeypatch):
    for key in list(__import__("os").environ):
        if key.startswith("JARVIS_"):
            monkeypatch.delenv(key, raising=False)
    c = Config.from_env()
    assert c.wake_engine == "auto"
    assert c.backend_url.startswith("ws://")
    assert c.sample_rate == 16000


def test_from_env_overrides(monkeypatch):
    monkeypatch.setenv("JARVIS_WAKE", "ENERGY")
    monkeypatch.setenv("JARVIS_STT", "Mock")
    monkeypatch.setenv("JARVIS_TTS", "MOCK")
    monkeypatch.setenv("JARVIS_SAMPLE_RATE", "8000")
    monkeypatch.setenv("JARVIS_FRAME_MS", "20")
    monkeypatch.setenv("JARVIS_INPUT_DEVICE", "2")
    monkeypatch.setenv("JARVIS_BARGE_IN", "off")
    monkeypatch.setenv("JARVIS_AMBIENT", "on")
    monkeypatch.setenv("JARVIS_SOUND_EVENTS", "yamnet")
    monkeypatch.setenv("JARVIS_AMBIENT_SPEAKER", "Unknown")
    c = Config.from_env()
    assert c.wake_engine == "energy"      # lowercased
    assert c.stt_engine == "mock"
    assert c.sample_rate == 8000
    assert c.frame_ms == 20
    assert c.input_device == 2
    assert c.barge_in_enabled is False
    assert c.ambient_mode == "on"
    assert c.sound_events_engine == "yamnet"
    assert c.ambient_speaker == "unknown"


def test_from_env_without_dotenv_load():
    # load_dotenv=False exercises the branch that skips .env loading.
    c = Config.from_env(load_dotenv=False)
    assert isinstance(c, Config)


# --- derived properties -----------------------------------------------------

def test_samples_and_bytes_per_frame():
    c = Config(sample_rate=16000, frame_ms=30)
    assert c.samples_per_frame == 480
    assert c.bytes_per_frame == 960


def test_frames_for_ms_min_one():
    c = Config(frame_ms=30)
    assert c.frames_for_ms(90) == 3
    assert c.frames_for_ms(1) == 1  # rounds up to at least 1


def test_ambient_disabled_and_autostart():
    assert Config(ambient_mode="off").ambient_disabled is True
    assert Config(ambient_mode="off").ambient_autostart is False
    assert Config(ambient_mode="on").ambient_autostart is True
    assert Config(ambient_mode="on").ambient_disabled is False
    assert Config(ambient_mode="auto").ambient_disabled is False
    assert Config(ambient_mode="auto").ambient_autostart is False


def test_summary_and_as_dict():
    c = Config()
    s = c.summary()
    assert "wake=" in s and "ambient=" in s and "backend=" in s
    d = c.as_dict()
    assert d["sample_rate"] == 16000 and "wake_engine" in d
