"""Exhaustive coverage of jarvis_voice.audio (headless, numpy + fake sounddevice)."""

from __future__ import annotations

import types

import pytest

from jarvis_voice import audio
from jarvis_voice.audio import AudioUnavailable

from conftest import FakeSoundDevice


# --- availability flags -----------------------------------------------------

def test_numpy_available_true():
    assert audio.numpy_available() is True


def test_audio_io_available_false_headless():
    assert audio.audio_io_available() is False


# --- rms_energy -------------------------------------------------------------

def test_rms_energy_empty_is_zero():
    assert audio.rms_energy(b"") == 0.0


def test_rms_energy_loud_positive():
    loud = audio.tone(300.0, 30, amplitude=0.6)
    assert audio.rms_energy(loud) > 1000.0


def test_rms_energy_numpy_size_zero_guard(monkeypatch):
    # Force a numpy whose frombuffer yields an empty array -> size==0 guard.
    fake_np = types.SimpleNamespace(
        int16="int16",
        frombuffer=lambda *a, **k: types.SimpleNamespace(size=0),
    )
    monkeypatch.setattr(audio, "_np", fake_np)
    assert audio.rms_energy(b"\x01\x02") == 0.0


def test_rms_energy_pure_python_fallback(monkeypatch):
    monkeypatch.setattr(audio, "_np", None)
    loud = audio.tone(300.0, 30, amplitude=0.6)
    assert audio.rms_energy(loud) > 1000.0
    # 1-byte frame -> count==0 pure-python guard.
    assert audio.rms_energy(b"\x00") == 0.0


def test_is_silent():
    assert audio.is_silent(audio.silence(30), threshold=100.0) is True
    assert audio.is_silent(audio.tone(300.0, 30, amplitude=0.6), threshold=100.0) is False


# --- dbfs -------------------------------------------------------------------

def test_dbfs_silence_floor():
    assert audio.dbfs(audio.silence(30)) == -120.0


def test_dbfs_loud_is_negative_but_high():
    d = audio.dbfs(audio.tone(300.0, 30, amplitude=0.6))
    assert -20.0 < d < 0.0


# --- zero_crossing_rate -----------------------------------------------------

def test_zcr_empty_zero():
    assert audio.zero_crossing_rate(b"") == 0.0


def test_zcr_single_sample_guard():
    # one int16 sample -> size < 2 guard (numpy path)
    assert audio.zero_crossing_rate(b"\x01\x02") == 0.0


def test_zcr_tone_positive():
    assert audio.zero_crossing_rate(audio.tone(2000.0, 30, amplitude=0.6)) > 0.0


def test_zcr_pure_python_fallback(monkeypatch):
    monkeypatch.setattr(audio, "_np", None)
    assert audio.zero_crossing_rate(audio.tone(2000.0, 30, amplitude=0.6)) > 0.0
    # 1-byte frame -> count==0 ternary else branch
    assert audio.zero_crossing_rate(b"\x00") == 0.0


# --- spectral_features ------------------------------------------------------

def test_spectral_features_numpy_absent(monkeypatch):
    monkeypatch.setattr(audio, "_np", None)
    out = audio.spectral_features(audio.tone(300.0, 30))
    assert out == {"dominant_hz": 0.0, "centroid_hz": 0.0, "flatness": 0.0}


def test_spectral_features_empty_pcm():
    assert audio.spectral_features(b"")["dominant_hz"] == 0.0


def test_spectral_features_too_short():
    # < 8 samples -> early return of zeros
    assert audio.spectral_features(b"\x01\x02\x03\x04")["flatness"] == 0.0


def test_spectral_features_silence_zero_spectrum():
    # all-zero signal -> spectrum sums to 0 -> early return
    out = audio.spectral_features(audio.silence(30))
    assert out["dominant_hz"] == 0.0


def test_spectral_features_tone_has_dominant():
    out = audio.spectral_features(audio.tone(1000.0, 60, amplitude=0.8))
    assert out["dominant_hz"] > 0.0
    assert 0.0 <= out["flatness"] <= 1.0


# --- WAV round trip ---------------------------------------------------------

def test_wav_round_trip():
    pcm = audio.tone(440.0, 50)
    wav = audio.pcm16_to_wav(pcm, sample_rate=16000, channels=1)
    assert wav[:4] == b"RIFF"
    back, sr, ch = audio.wav_to_pcm16(wav)
    assert back == pcm and sr == 16000 and ch == 1


def test_silence_and_tone_lengths():
    assert len(audio.silence(10, 16000)) == int(16000 * 10 / 1000) * 2
    assert len(audio.tone(440.0, 10, 16000)) == int(16000 * 10 / 1000) * 2


# --- playback (fake sounddevice) -------------------------------------------

def test_play_pcm16_raises_without_backend():
    with pytest.raises(AudioUnavailable):
        audio.play_pcm16(audio.silence(10))


def test_play_pcm16_with_fake_sd(monkeypatch):
    fake = FakeSoundDevice()
    monkeypatch.setattr(audio, "_sd", fake)
    audio.play_pcm16(audio.tone(440.0, 10), sample_rate=16000)
    assert fake.played and fake.waited == 1
    # non-blocking path skips wait()
    audio.play_pcm16(audio.tone(440.0, 10), blocking=False)
    assert fake.waited == 1


def test_play_wav_bytes_with_fake_sd(monkeypatch):
    fake = FakeSoundDevice()
    monkeypatch.setattr(audio, "_sd", fake)
    audio.play_wav_bytes(audio.pcm16_to_wav(audio.tone(440.0, 10)))
    assert fake.played


def test_stop_playback_no_backend_is_noop():
    audio.stop_playback()  # _sd is None -> returns quietly


# --- MicStream (fake sounddevice) ------------------------------------------

def test_micstream_unavailable_without_backend():
    with pytest.raises(AudioUnavailable):
        with audio.MicStream():
            pass


def test_micstream_iterates_with_fake_sd(monkeypatch):
    fake = FakeSoundDevice()
    monkeypatch.setattr(audio, "_sd", fake)
    mic = audio.MicStream(sample_rate=16000, frame_samples=160)
    mic.__enter__()
    mic._frames.append(b"\x00\x00")
    it = iter(mic)
    assert next(it) == b"\x00\x00"
    mic.close()
    with pytest.raises(StopIteration):
        next(it)


def test_micstream_context_manager_with_fake_sd(monkeypatch):
    fake = FakeSoundDevice()
    monkeypatch.setattr(audio, "_sd", fake)
    with audio.MicStream() as mic:
        assert mic is not None


# --- list_devices -----------------------------------------------------------

def test_list_devices_without_backend():
    assert "not installed" in audio.list_devices()
