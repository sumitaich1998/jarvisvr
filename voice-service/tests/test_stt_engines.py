"""Coverage for STT engines (FasterWhisper/Vosk mocked) + base + factory."""

from __future__ import annotations

import json

import pytest

from jarvis_voice import audio
from jarvis_voice.stt import (
    FasterWhisperSTT,
    MockSTT,
    Transcriber,
    TranscriberError,
    TranscriptResult,
    VoskSTT,
    create_transcriber,
)

from conftest import fast_config


# --- base interface ---------------------------------------------------------

def test_abstract_final_raises():
    class Concrete(Transcriber):
        def final(self, pcm=None):
            return super().final(pcm)

    with pytest.raises(NotImplementedError):
        Concrete().final(b"")


def test_base_accept_set_language_close_via_mock():
    stt = MockSTT(fast_config())
    # base set_language is a no-op hook (MockSTT doesn't override it)
    stt.set_language("es")
    stt.close()
    assert stt.name == "mock"


# --- FasterWhisper (mocked faster_whisper.WhisperModel) ---------------------

class _Seg:
    def __init__(self, text, avg_logprob):
        self.text = text
        self.avg_logprob = avg_logprob


def _install_whisper(fake_module, segments):
    class FakeWhisperModel:
        def __init__(self, model, device=None, compute_type=None):
            self.model = model

        def transcribe(self, audio_arr, language=None, beam_size=1):
            return iter(segments), {"language": language}

    fake_module("faster_whisper", WhisperModel=FakeWhisperModel)
    return FakeWhisperModel


def test_faster_whisper_transcribe(fake_module):
    _install_whisper(fake_module, [_Seg(" hello", -0.2), _Seg(" world", None)])
    stt = FasterWhisperSTT(fast_config(stt_language="en"))
    # base reset (not overridden) + accept (returns None)
    stt.reset()
    assert stt.accept(b"\x00\x00") is None
    res = stt.final(audio.tone(200.0, 30, amplitude=0.5))
    assert res.text == "hello world"
    assert 0.0 <= res.confidence <= 1.0


def test_faster_whisper_empty_pcm(fake_module):
    _install_whisper(fake_module, [])
    stt = FasterWhisperSTT(fast_config())
    res = stt.final(b"")
    assert res.text == "" and res.confidence == 0.0


def test_faster_whisper_set_language(fake_module):
    _install_whisper(fake_module, [])
    stt = FasterWhisperSTT(fast_config(stt_language="en"))
    stt.set_language("es")
    assert stt.language == "es"
    stt.set_language("auto")
    assert stt.language is None
    stt.set_language("")
    assert stt.language is None


def test_faster_whisper_not_installed_raises():
    with pytest.raises(TranscriberError):
        FasterWhisperSTT(fast_config())


# --- Vosk (mocked vosk.Model + KaldiRecognizer) -----------------------------

def _install_vosk(fake_module, rec_factory):
    class FakeModel:
        def __init__(self, path):
            self.path = path

    fake_module("vosk", Model=FakeModel, KaldiRecognizer=rec_factory)


def test_vosk_streaming_result_and_partial(fake_module):
    class FakeRec:
        def __init__(self, model, sr):
            self.n = 0

        def SetWords(self, flag):
            pass

        def AcceptWaveform(self, data):
            self.n += 1
            return self.n % 2 == 1  # True, then False…

        def Result(self):
            return json.dumps({"text": "hello world", "result": [{"conf": 0.9}]})

        def PartialResult(self):
            return json.dumps({"partial": "hel"})

        def FinalResult(self):
            return json.dumps({"text": "the end", "result": [{"conf": 0.8}, {"conf": 0.6}]})

    _install_vosk(fake_module, FakeRec)
    stt = VoskSTT(fast_config(vosk_model="/models/vosk-en"))
    assert stt.accept(b"\x00\x00") == "hello world"   # AcceptWaveform True -> Result
    assert stt.accept(b"\x00\x00") == "hel"            # False -> PartialResult
    stt.reset()
    res = stt.final(b"\x00\x00")
    assert res.text == "the end"
    assert res.confidence == pytest.approx(0.7)        # mean(0.8, 0.6)


def test_vosk_empty_results_return_none(fake_module):
    class EmptyRec:
        def __init__(self, model, sr):
            pass

        def SetWords(self, flag):
            pass

        def AcceptWaveform(self, data):
            return True  # always final-ish

        def Result(self):
            return json.dumps({"text": ""})

        def PartialResult(self):
            return json.dumps({"partial": ""})

        def FinalResult(self):
            return json.dumps({"text": ""})

    _install_vosk(fake_module, EmptyRec)
    stt = VoskSTT(fast_config(vosk_model="/m"))
    assert stt.accept(b"\x00\x00") is None  # Result text "" -> None
    res = stt.final(None)                   # pcm None -> skip AcceptWaveform
    assert res.text == ""


def test_vosk_partial_empty_returns_none(fake_module):
    class PartialRec:
        def __init__(self, model, sr):
            pass

        def SetWords(self, flag):
            pass

        def AcceptWaveform(self, data):
            return False  # always partial

        def Result(self):
            return json.dumps({"text": "x"})

        def PartialResult(self):
            return json.dumps({"partial": ""})

        def FinalResult(self):
            return json.dumps({"text": "done"})

    _install_vosk(fake_module, PartialRec)
    stt = VoskSTT(fast_config(vosk_model="/m"))
    assert stt.accept(b"\x00\x00") is None  # partial "" -> None


def test_vosk_avg_conf_empty_is_one():
    assert VoskSTT._avg_conf({}) == 1.0
    assert VoskSTT._avg_conf({"result": [{"conf": 0.4}, {"conf": 0.6}]}) == pytest.approx(0.5)


def test_vosk_requires_model(fake_module):
    _install_vosk(fake_module, object)
    with pytest.raises(TranscriberError):
        VoskSTT(fast_config(vosk_model=None))


def test_vosk_not_installed_raises():
    with pytest.raises(TranscriberError):
        VoskSTT(fast_config(vosk_model="/m"))


# --- factory ----------------------------------------------------------------

def test_factory_auto_prefers_whisper(fake_module):
    _install_whisper(fake_module, [])
    assert create_transcriber(fast_config(stt_engine="auto")).name == "faster-whisper"


def test_factory_concrete_vosk(fake_module):
    _install_vosk(
        fake_module,
        lambda m, sr: type(
            "R", (), {"SetWords": lambda s, f: None, "FinalResult": lambda s: "{}"}
        )(),
    )
    assert create_transcriber(fast_config(stt_engine="vosk", vosk_model="/m")).name == "vosk"


def test_factory_unknown_falls_back_to_mock():
    assert create_transcriber(fast_config(stt_engine="bogus")).name == "mock"


def test_factory_concrete_failure_falls_back():
    # vosk requested but not installed -> TranscriberError -> mock
    assert create_transcriber(fast_config(stt_engine="vosk", vosk_model="/m")).name == "mock"


def test_transcribe_convenience():
    stt = MockSTT(fast_config(mock_transcript="canned text"))
    assert stt.transcribe(b"\x00\x00").text == "canned text"
    assert isinstance(stt.transcribe(b""), TranscriptResult)
