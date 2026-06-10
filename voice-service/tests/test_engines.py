"""Engine factories + fallbacks (headless: no models, no audio hardware)."""

from __future__ import annotations

from jarvis_voice import audio
from jarvis_voice.stt import MockSTT, create_transcriber
from jarvis_voice.tts import MockTTS, create_speaker
from jarvis_voice.wakeword import EnergyFallback, create_wakeword

from conftest import fast_config


# --- wake word --------------------------------------------------------------

def test_energy_fallback_fires_on_sustained_energy(config):
    det = EnergyFallback(config)
    loud = audio.tone(300.0, config.frame_ms, sample_rate=config.sample_rate, amplitude=0.6)
    quiet = audio.silence(config.frame_ms, config.sample_rate)

    assert det.process(quiet) is False
    fired = [det.process(loud) for _ in range(config.wake_min_frames)]
    assert fired[-1] is True  # fires once min_frames loud frames seen
    # Cooldown after firing: an immediate loud frame should not refire.
    assert det.process(loud) is False


def test_wake_auto_falls_back_to_energy_headless():
    det = create_wakeword(fast_config(wake_engine="auto"))
    assert det.name == "energy"


def test_wake_porcupine_without_key_falls_back():
    det = create_wakeword(fast_config(wake_engine="porcupine", porcupine_access_key=None))
    assert det.name == "energy"


def test_wake_unknown_engine_falls_back():
    det = create_wakeword(fast_config(wake_engine="bogus"))
    assert det.name == "energy"


# --- STT --------------------------------------------------------------------

def test_stt_auto_falls_back_to_mock_headless():
    stt = create_transcriber(fast_config(stt_engine="auto"))
    assert stt.name == "mock"


def test_mock_stt_transcribe_returns_canned(config):
    stt = MockSTT(config)
    result = stt.transcribe(b"\x00\x00" * 100)
    assert result.text == config.mock_transcript
    assert result.is_final is True


def test_mock_stt_set_next_overrides_once(config):
    stt = MockSTT(config)
    stt.set_next("custom phrase")
    assert stt.transcribe(b"").text == "custom phrase"
    # Override is one-shot; reverts to the canned phrase afterwards.
    assert stt.transcribe(b"").text == config.mock_transcript


def test_mock_stt_streams_partials(config):
    stt = MockSTT(config)
    stt.reset()
    partials = [stt.accept(b"\x00\x00" * config.samples_per_frame) for _ in range(8)]
    nonempty = [p for p in partials if p]
    assert nonempty, "expected at least one streaming partial"
    # Partials are monotonically growing prefixes of the phrase.
    assert config.mock_transcript.startswith(nonempty[0])


def test_stt_vosk_without_model_falls_back():
    stt = create_transcriber(fast_config(stt_engine="vosk", vosk_model=None))
    assert stt.name == "mock"


# --- TTS --------------------------------------------------------------------

def test_tts_auto_falls_back_to_mock_headless():
    tts = create_speaker(fast_config(tts_engine="auto"))
    assert tts.name == "mock"


def test_mock_tts_synthesize_is_valid_wav(config):
    tts = MockTTS(config)
    wav = tts.synthesize("Jarvis online and ready.")
    assert wav[:4] == b"RIFF"
    pcm, sr, ch = audio.wav_to_pcm16(wav)
    assert len(pcm) > 0
    assert sr == config.sample_rate
    assert ch == 1


def test_mock_tts_speak_is_headless_safe(config, capsys):
    tts = MockTTS(config)
    tts.speak("hello world")  # must not raise without audio hardware
    out = capsys.readouterr().out
    assert "hello world" in out


def test_tts_piper_without_model_falls_back():
    tts = create_speaker(fast_config(tts_engine="piper", piper_model=None))
    assert tts.name == "mock"


# --- audio helpers ----------------------------------------------------------

def test_rms_energy_loud_vs_quiet(config):
    loud = audio.tone(300.0, config.frame_ms, sample_rate=config.sample_rate, amplitude=0.6)
    quiet = audio.silence(config.frame_ms, config.sample_rate)
    assert audio.rms_energy(loud) > config.vad_threshold
    assert audio.rms_energy(quiet) == 0.0


def test_wav_round_trip():
    pcm = audio.tone(440.0, 100)
    wav = audio.pcm16_to_wav(pcm)
    back, sr, ch = audio.wav_to_pcm16(wav)
    assert back == pcm
    assert sr == audio.SAMPLE_RATE
    assert ch == 1
