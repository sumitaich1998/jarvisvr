"""Audio I/O helpers: mic capture + playback, 16 kHz mono PCM16.

Every optional dependency (``sounddevice``, ``numpy``) is import-guarded so this
module imports cleanly on a headless box with no audio stack. Capture/playback
degrade gracefully: they log and raise :class:`AudioUnavailable` instead of
crashing the process, and callers (pipeline/CLI) fall back accordingly.
"""

from __future__ import annotations

import io
import logging
import math
import struct
import threading
import wave
from typing import Iterator, List, Optional

log = logging.getLogger(__name__)

# --- Optional deps, guarded -------------------------------------------------
try:  # numpy is a base dep, but stay robust if it's somehow missing.
    import numpy as _np  # type: ignore
except Exception:  # pragma: no cover
    _np = None  # type: ignore

try:  # sounddevice is an optional extra ([audio]); absence is normal/headless.
    import sounddevice as _sd  # type: ignore
except Exception:  # pragma: no cover - environment dependent
    _sd = None  # type: ignore


SAMPLE_RATE = 16000
CHANNELS = 1
SAMPLE_WIDTH = 2  # bytes (int16)


class AudioUnavailable(RuntimeError):
    """Raised when mic/speaker hardware or the audio backend is unavailable."""


def numpy_available() -> bool:
    return _np is not None


def audio_io_available() -> bool:
    """True if a real audio backend (sounddevice) is importable."""
    return _sd is not None


# --- Energy / VAD -----------------------------------------------------------

def rms_energy(frame: bytes) -> float:
    """RMS amplitude of a little-endian PCM16 mono frame (0..32767-ish).

    Used by the energy wake fallback and the silence-based endpointer. Works with
    or without numpy.
    """
    if not frame:
        return 0.0
    if _np is not None:
        samples = _np.frombuffer(frame, dtype=_np.int16)
        if samples.size == 0:
            return 0.0
        # float64 accumulation avoids int overflow on loud frames.
        return float(_np.sqrt(_np.mean(samples.astype(_np.float64) ** 2)))
    # Pure-python fallback.
    count = len(frame) // SAMPLE_WIDTH
    if count == 0:
        return 0.0
    total = 0
    for (sample,) in struct.iter_unpack("<h", frame[: count * SAMPLE_WIDTH]):
        total += sample * sample
    return math.sqrt(total / count)


def is_silent(frame: bytes, threshold: float) -> bool:
    return rms_energy(frame) < threshold


def dbfs(frame: bytes) -> float:
    """Loudness in dBFS (decibels relative to full scale; ~0 is max, negative is quieter).

    Matches the ``loudness_db`` convention in ``perception.audio_scene`` /
    ``perception.audio_event`` (e.g. -22.0, -30.0). Returns -120.0 for silence.
    """
    rms = rms_energy(frame)
    if rms <= 0.0:
        return -120.0
    return max(-120.0, 20.0 * math.log10(rms / 32768.0))


def zero_crossing_rate(frame: bytes) -> float:
    """Fraction of adjacent samples that change sign (0..1). High for noisy/fricative
    sounds (glass, hiss), low for tonal sounds (alarms, hums). numpy-optional."""
    if not frame:
        return 0.0
    if _np is not None:
        s = _np.frombuffer(frame, dtype=_np.int16).astype(_np.int32)
        if s.size < 2:
            return 0.0
        return float(_np.mean(_np.abs(_np.diff(_np.sign(s))) > 0))
    prev_sign = 0
    crossings = 0
    count = 0
    for (sample,) in struct.iter_unpack("<h", frame[: (len(frame) // 2) * 2]):
        sign = 1 if sample > 0 else (-1 if sample < 0 else 0)
        if count > 0 and sign != 0 and prev_sign != 0 and sign != prev_sign:
            crossings += 1
        if sign != 0:
            prev_sign = sign
        count += 1
    return crossings / count if count else 0.0


def spectral_features(pcm: bytes, sample_rate: int = SAMPLE_RATE) -> dict:
    """Cheap spectral descriptors used by the heuristic sound-event fallback.

    Returns ``{dominant_hz, centroid_hz, flatness}``. ``flatness`` ~0 => tonal,
    ~1 => noise-like. Requires numpy; degrades to zeros without it.
    """
    out = {"dominant_hz": 0.0, "centroid_hz": 0.0, "flatness": 0.0}
    if _np is None or not pcm:
        return out
    samples = _np.frombuffer(pcm, dtype=_np.int16).astype(_np.float64)
    if samples.size < 8:
        return out
    samples = samples - samples.mean()
    window = _np.hanning(samples.size)
    spectrum = _np.abs(_np.fft.rfft(samples * window))
    freqs = _np.fft.rfftfreq(samples.size, d=1.0 / sample_rate)
    if spectrum.sum() <= 0:
        return out
    mag = spectrum + 1e-12  # strictly positive, so arith_mean below is always > 0
    out["dominant_hz"] = float(freqs[int(_np.argmax(spectrum))])
    out["centroid_hz"] = float((freqs * mag).sum() / mag.sum())
    geo_mean = float(_np.exp(_np.mean(_np.log(mag))))
    arith_mean = float(_np.mean(mag))
    out["flatness"] = max(0.0, min(1.0, geo_mean / arith_mean))
    return out


# --- WAV (de)serialization (stdlib only) ------------------------------------

def pcm16_to_wav(pcm: bytes, sample_rate: int = SAMPLE_RATE, channels: int = CHANNELS) -> bytes:
    """Wrap raw PCM16 bytes in a WAV container."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(SAMPLE_WIDTH)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm)
    return buf.getvalue()


def wav_to_pcm16(wav_bytes: bytes) -> tuple[bytes, int, int]:
    """Extract ``(pcm_bytes, sample_rate, channels)`` from a WAV container."""
    with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
        sample_rate = wf.getframerate()
        channels = wf.getnchannels()
        frames = wf.readframes(wf.getnframes())
    return frames, sample_rate, channels


def silence(ms: int, sample_rate: int = SAMPLE_RATE) -> bytes:
    """A block of PCM16 silence of the given duration."""
    n = int(sample_rate * ms / 1000)
    return b"\x00\x00" * n


def tone(
    freq_hz: float,
    ms: int,
    sample_rate: int = SAMPLE_RATE,
    amplitude: float = 0.25,
) -> bytes:
    """A simple sine tone as PCM16 — handy for mock TTS / smoke tests."""
    n = int(sample_rate * ms / 1000)
    amp = max(0.0, min(1.0, amplitude)) * 32767.0
    out = bytearray()
    two_pi_f = 2.0 * math.pi * freq_hz
    for i in range(n):
        val = int(amp * math.sin(two_pi_f * (i / sample_rate)))
        out += struct.pack("<h", max(-32768, min(32767, val)))
    return bytes(out)


# --- Playback ---------------------------------------------------------------

def play_pcm16(
    pcm: bytes,
    sample_rate: int = SAMPLE_RATE,
    output_device: Optional[int] = None,
    blocking: bool = True,
) -> None:
    """Play raw PCM16 mono audio through the default (or chosen) output device."""
    if _sd is None or _np is None:
        raise AudioUnavailable("sounddevice/numpy not installed; cannot play audio")
    samples = _np.frombuffer(pcm, dtype=_np.int16)
    try:
        _sd.play(samples, samplerate=sample_rate, device=output_device)
        if blocking:
            _sd.wait()
    except Exception as exc:  # pragma: no cover - hardware dependent
        raise AudioUnavailable(f"playback failed: {exc}") from exc


def play_wav_bytes(wav_bytes: bytes, output_device: Optional[int] = None) -> None:
    pcm, sample_rate, _channels = wav_to_pcm16(wav_bytes)
    play_pcm16(pcm, sample_rate=sample_rate, output_device=output_device)


def stop_playback() -> None:
    """Immediately stop any in-progress playback (used for barge-in). No-op if no
    audio backend; never raises."""
    if _sd is None:
        return
    try:  # pragma: no cover - hardware dependent
        _sd.stop()
    except Exception:
        pass


# --- Capture ----------------------------------------------------------------

class MicStream:
    """Context-managed microphone stream yielding fixed-size PCM16 frames.

    Usage::

        with MicStream(sample_rate=16000, frame_samples=480) as mic:
            for frame in mic:   # each `frame` is `frame_samples*2` bytes
                ...

    Raises :class:`AudioUnavailable` on ``__enter__`` if no backend/device.
    """

    def __init__(
        self,
        sample_rate: int = SAMPLE_RATE,
        frame_samples: int = 480,
        input_device: Optional[int] = None,
        queue_max: int = 100,
    ) -> None:
        self.sample_rate = sample_rate
        self.frame_samples = frame_samples
        self.input_device = input_device
        self._queue_max = queue_max
        self._frames: "List[bytes]" = []
        self._cv = threading.Condition()
        self._stream = None
        self._closed = False

    def _callback(self, indata, _frames, _time, status):  # pragma: no cover - hw
        if status:
            log.debug("mic status: %s", status)
        data = bytes(indata)
        with self._cv:
            if len(self._frames) >= self._queue_max:
                self._frames.pop(0)  # drop oldest to bound latency
            self._frames.append(data)
            self._cv.notify()

    def __enter__(self) -> "MicStream":
        if _sd is None:
            raise AudioUnavailable("sounddevice not installed; mic capture unavailable")
        try:
            self._stream = _sd.RawInputStream(
                samplerate=self.sample_rate,
                blocksize=self.frame_samples,
                device=self.input_device,
                channels=CHANNELS,
                dtype="int16",
                callback=self._callback,
            )
            self._stream.start()
        except Exception as exc:  # pragma: no cover - hardware dependent
            raise AudioUnavailable(f"could not open microphone: {exc}") from exc
        return self

    def __iter__(self) -> Iterator[bytes]:
        while not self._closed:
            with self._cv:
                while not self._frames and not self._closed:
                    self._cv.wait(timeout=0.5)
                if self._closed and not self._frames:
                    return
                # Past the wait loop, a frame is guaranteed available.
                yield self._frames.pop(0)

    def close(self) -> None:
        self._closed = True
        with self._cv:
            self._cv.notify_all()
        if self._stream is not None:  # pragma: no cover - hardware dependent
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None

    def __exit__(self, *_exc) -> None:
        self.close()


def list_devices() -> str:
    """Human-readable device listing (or a notice if unavailable)."""
    if _sd is None:
        return "audio backend (sounddevice) not installed"
    try:  # pragma: no cover - hardware dependent
        return str(_sd.query_devices())
    except Exception as exc:  # pragma: no cover
        return f"could not query audio devices: {exc}"
