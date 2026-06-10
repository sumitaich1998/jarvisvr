"""Targeted edge-case tests closing the last coverage gaps in each module."""

from __future__ import annotations

import asyncio
import threading

import pytest

import jarvis_voice.tts as tts_mod
from jarvis_voice import audio, protocol
from jarvis_voice.ambient import AmbientListener
from jarvis_voice.bridge import build_bridge
from jarvis_voice.pipeline import VoicePipeline
from jarvis_voice.sound_events import HeuristicSoundEvents
from jarvis_voice.stt import FasterWhisperSTT, VoskSTT
from jarvis_voice.tts import Pyttsx3TTS
from jarvis_voice.wakeword import OpenWakeWord

from conftest import FakeMic, FakeSoundDevice, FakeWebSocket, fast_config
from test_cli import _feed_inputs
from test_stt_engines import _Seg, _install_vosk, _install_whisper
from test_tts_engines import _FakeEngine, _install_pyttsx3


# --- audio: stop_playback + MicStream wait branch ---------------------------

def test_stop_playback_with_fake_sd(monkeypatch):
    fake = FakeSoundDevice()
    monkeypatch.setattr(audio, "_sd", fake)
    audio.stop_playback()
    assert fake.stopped == 1


def test_stop_playback_swallows_errors(monkeypatch):
    class BadSd:
        def stop(self):
            raise RuntimeError("device gone")

    monkeypatch.setattr(audio, "_sd", BadSd())
    audio.stop_playback()  # must not raise


def test_micstream_iter_waits_then_closes(monkeypatch):
    fake = FakeSoundDevice()
    monkeypatch.setattr(audio, "_sd", fake)
    mic = audio.MicStream()
    mic.__enter__()
    it = iter(mic)
    # No frames -> generator blocks in cv.wait(); close it from a timer.
    threading.Timer(0.05, mic.close).start()
    with pytest.raises(StopIteration):
        next(it)


# --- wakeword: OpenWakeWord.reset model.reset() raising ----------------------

def test_openwakeword_reset_swallows_model_error(fake_module):
    class FakeModel:
        def __init__(self, wakeword_models=None):
            pass

        def predict(self, samples):
            return {"hey_jarvis": 0.0}

        def reset(self):
            raise RuntimeError("lib internal")

    fake_module("openwakeword")
    fake_module("openwakeword.model", Model=FakeModel)
    det = OpenWakeWord(fast_config())
    det.reset()  # _buf.clear + model.reset() raises -> swallowed


# --- stt: whisper no-logprob + vosk SetWords raising ------------------------

def test_faster_whisper_no_logprob_confidence_one(fake_module):
    _install_whisper(fake_module, [_Seg(" hi", None)])
    stt = FasterWhisperSTT(fast_config())
    res = stt.final(audio.tone(200.0, 30, amplitude=0.5))
    assert res.text == "hi"
    assert res.confidence == 1.0  # no logprobs -> default confidence


def test_vosk_setwords_error_swallowed(fake_module):
    class RecSetWordsRaises:
        def __init__(self, model, sr):
            pass

        def SetWords(self, flag):
            raise RuntimeError("no words support")

        def FinalResult(self):
            return "{}"

    _install_vosk(fake_module, RecSetWordsRaises)
    stt = VoskSTT(fast_config(vosk_model="/m"))  # _new_rec swallows SetWords error
    assert stt.name == "vosk"


# --- tts: pyttsx3 synthesize finally unlink OSError -------------------------

def test_pyttsx3_synthesize_unlink_oserror(fake_module, monkeypatch):
    _install_pyttsx3(fake_module, _FakeEngine())
    spk = Pyttsx3TTS(fast_config())

    def boom(path):
        raise OSError("cannot unlink")

    monkeypatch.setattr(tts_mod.os, "unlink", boom)
    wav = spk.synthesize("hi")  # finally-unlink OSError swallowed
    assert wav[:4] == b"RIFF"


# --- sound_events: empty pcm ------------------------------------------------

def test_heuristic_analyze_empty_pcm():
    assert HeuristicSoundEvents(fast_config()).analyze(b"") == []


# --- ambient/pipeline: set_language with engines lacking the hook -----------

def test_ambient_set_language_engine_without_hook():
    cfg = fast_config()
    amb = AmbientListener(object(), HeuristicSoundEvents(cfg), cfg)
    amb.set_language("es")  # transcriber has no set_language -> skipped
    assert amb.language == "es"


def test_pipeline_set_language_engines_without_hook():
    from conftest import FakeWake

    pipe = VoicePipeline(FakeWake(armed=False), object(), object(), fast_config())
    pipe.set_language("es")  # neither engine has set_language -> skipped, no error


# --- bridge: capture mic loop without ambient active (amb is None) ----------

def test_capture_loop_runs_mic_without_ambient(monkeypatch):
    import jarvis_voice.bridge as bridge_mod

    cfg = fast_config()
    monkeypatch.setattr(bridge_mod, "audio_io_available", lambda: True)
    monkeypatch.setattr(audio, "MicStream", lambda **kw: FakeMic([audio.silence(cfg.frame_ms)] * 2))
    bridge = build_bridge(cfg)  # _ambient stays None
    asyncio.run(bridge.capture_loop(FakeWebSocket()))


# --- CLI: remaining demo/ambient/selftest branches --------------------------

def test_cli_demo_simulate_keyboard_interrupt(monkeypatch):
    def ki(prompt=""):
        raise KeyboardInterrupt

    monkeypatch.setattr("builtins.input", ki)
    from jarvis_voice.__main__ import main

    assert main(["demo", "--simulate"]) == 0


def test_cli_ambient_simulate_eof(monkeypatch):
    _feed_inputs(monkeypatch, [])  # REPL hits EOFError immediately
    from jarvis_voice.__main__ import main

    assert main(["ambient", "--simulate"]) == 0


def test_cli_ambient_mic_emits_no_speech_scene(monkeypatch):
    from jarvis_voice.__main__ import main
    from jarvis_voice.config import Config

    cfg = Config.from_env()
    n = cfg.frames_for_ms(cfg.ambient_window_ms) + 1
    frames = [audio.silence(cfg.frame_ms)] * n
    monkeypatch.setattr(audio, "audio_io_available", lambda: True)
    monkeypatch.setattr(audio, "MicStream", lambda **kw: FakeMic(frames))
    assert main(["ambient"]) == 0  # a silent window -> on_scene "(no speech)" branch


def test_cli_selftest_simulate_fallback(monkeypatch):
    # Wake never fires on synthetic tone -> selftest takes the simulate fallback.
    monkeypatch.setenv("JARVIS_WAKE_ENERGY_THRESHOLD", "999999")
    from jarvis_voice.__main__ import main

    assert main(["selftest"]) == 0
