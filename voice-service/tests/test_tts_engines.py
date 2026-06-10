"""Coverage for TTS engines (Piper/pyttsx3 mocked) + base + MockTTS playback."""

from __future__ import annotations

import pytest

from jarvis_voice import audio
from jarvis_voice.audio import AudioUnavailable
from jarvis_voice.tts import (
    MockTTS,
    PiperTTS,
    Pyttsx3TTS,
    Speaker,
    SpeakerError,
    create_speaker,
)

from conftest import fast_config


# --- base Speaker abstract --------------------------------------------------

def test_abstract_synthesize_raises():
    class Concrete(Speaker):
        def synthesize(self, text):
            return super().synthesize(text)

    with pytest.raises(NotImplementedError):
        Concrete().synthesize("x")


# --- Piper (mocked piper.voice.PiperVoice) ----------------------------------

class _FakeCfg:
    sample_rate = 22050


class _FakePiperVoice:
    def __init__(self):
        self.config = _FakeCfg()

    @classmethod
    def load(cls, model, config_path=None):
        return cls()

    def synthesize(self, text, wf):
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(22050)
        wf.writeframes(b"\x00\x00" * 200)


def _piper_model(tmp_path):
    f = tmp_path / "voice.onnx"
    f.write_bytes(b"fake-onnx")
    return str(f)


def test_piper_synthesize_primary_import(fake_module, tmp_path):
    fake_module("piper")
    fake_module("piper.voice", PiperVoice=_FakePiperVoice)
    spk = PiperTTS(fast_config(piper_model=_piper_model(tmp_path)))
    assert spk.sample_rate == 22050
    wav = spk.synthesize("hello there")
    assert wav[:4] == b"RIFF"


def test_piper_fallback_import(fake_module, tmp_path):
    # Only top-level `piper` exists (no piper.voice) -> fallback import path.
    fake_module("piper", PiperVoice=_FakePiperVoice)
    spk = PiperTTS(fast_config(piper_model=_piper_model(tmp_path)))
    assert spk.name == "piper"


def test_piper_missing_model_raises(fake_module):
    fake_module("piper")
    fake_module("piper.voice", PiperVoice=_FakePiperVoice)
    with pytest.raises(SpeakerError):
        PiperTTS(fast_config(piper_model=None))


def test_piper_not_installed_raises(tmp_path):
    with pytest.raises(SpeakerError):
        PiperTTS(fast_config(piper_model=_piper_model(tmp_path)))


def test_piper_drives_base_speak_stop_set_language(fake_module, tmp_path):
    fake_module("piper")
    fake_module("piper.voice", PiperVoice=_FakePiperVoice)
    spk = PiperTTS(fast_config(piper_model=_piper_model(tmp_path)))
    # base speak: synthesize + play (no audio backend -> AudioUnavailable logged)
    spk.speak("hello")
    spk.speak("")  # empty -> early return
    # base stop + set_language + close (no-ops here)
    spk.stop()
    spk.set_language("es")
    assert spk._language == "es"
    spk.close()


# --- pyttsx3 (mocked) -------------------------------------------------------

class _FakeEngine:
    def __init__(self):
        self.props = {}
        self.said = []

    def setProperty(self, key, value):
        self.props[key] = value

    def say(self, text):
        self.said.append(text)

    def runAndWait(self):
        pass

    def save_to_file(self, text, path):
        with open(path, "wb") as fh:
            fh.write(audio.pcm16_to_wav(audio.silence(50)))


def _install_pyttsx3(fake_module, engine):
    fake_module("pyttsx3", init=lambda: engine)


def test_pyttsx3_init_synthesize_speak(fake_module):
    engine = _FakeEngine()
    _install_pyttsx3(fake_module, engine)
    spk = Pyttsx3TTS(fast_config(pyttsx3_rate=180, pyttsx3_voice="en"))
    assert engine.props["rate"] == 180
    assert engine.props["voice"] == "en"
    wav = spk.synthesize("hi")
    assert wav[:4] == b"RIFF"
    spk.speak("hello")
    spk.speak("")  # empty -> early return
    assert "hello" in engine.said


def test_pyttsx3_not_installed_raises():
    with pytest.raises(SpeakerError):
        Pyttsx3TTS(fast_config())


# --- MockTTS ----------------------------------------------------------------

def test_mock_tts_synthesize_valid_wav():
    wav = MockTTS(fast_config()).synthesize("a few words here")
    assert wav[:4] == b"RIFF"


def test_mock_tts_speak_headless(capsys):
    MockTTS(fast_config()).speak("hello world")
    assert "hello world" in capsys.readouterr().out


def test_mock_tts_speak_plays_when_backend_available(monkeypatch):
    played = []
    monkeypatch.setattr(audio, "audio_io_available", lambda: True)
    monkeypatch.setattr(audio, "play_wav_bytes", lambda wav, output_device=None: played.append(wav))
    MockTTS(fast_config()).speak("hi")
    assert played


def test_mock_tts_speak_swallows_audio_unavailable(monkeypatch):
    def boom(*a, **k):
        raise AudioUnavailable("no device")

    monkeypatch.setattr(audio, "audio_io_available", lambda: True)
    monkeypatch.setattr(audio, "play_wav_bytes", boom)
    MockTTS(fast_config()).speak("hi")  # must not raise


# --- factory ----------------------------------------------------------------

def test_factory_auto_prefers_piper(fake_module, tmp_path):
    fake_module("piper")
    fake_module("piper.voice", PiperVoice=_FakePiperVoice)
    spk = create_speaker(fast_config(tts_engine="auto", piper_model=_piper_model(tmp_path)))
    assert spk.name == "piper"


def test_factory_concrete_pyttsx3(fake_module):
    _install_pyttsx3(fake_module, _FakeEngine())
    assert create_speaker(fast_config(tts_engine="pyttsx3")).name == "pyttsx3"


def test_factory_unknown_falls_back_to_mock():
    assert create_speaker(fast_config(tts_engine="bogus")).name == "mock"


def test_factory_concrete_failure_falls_back():
    assert create_speaker(fast_config(tts_engine="piper", piper_model=None)).name == "mock"
