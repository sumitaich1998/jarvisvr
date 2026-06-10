"""Sound-event detection (doorbell, alarm, phone, knock, glass-break, music, speech…).

Interface :class:`SoundEventDetector` with:

* :class:`YamnetSoundEvents`   — real engine option (Google YAMNet via TF-Hub),
  guarded behind the ``sound-yamnet`` extra.
* :class:`HeuristicSoundEvents`— dependency-free fallback using loudness + simple
  spectral heuristics (dominant freq, spectral flatness, zero-crossing rate) to
  map a window of audio to a plausible label. Runs fully headless.
* :class:`NullSoundEvents`     — disabled (returns nothing).

Detectors are *window based*: ``analyze(pcm)`` classifies one chunk; ``feed(frame)``
buffers fixed-size PCM16 frames into ``sound_event_window_ms`` windows and analyzes
each. Results map directly to ``perception.audio_event`` (label/confidence/loudness).
:func:`create_sound_event_detector` selects an engine with an ``auto`` fallback chain.
"""

from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional

from . import audio
from .config import Config

log = logging.getLogger(__name__)

# Canonical labels referenced by PROTOCOL.md §8.4.
KNOWN_LABELS = (
    "doorbell", "alarm", "phone", "knock", "name_called",
    "glass_break", "music", "speech", "appliance", "noise",
)


class SoundEventError(RuntimeError):
    """Raised when a concrete detector cannot initialize (triggers fallback)."""


@dataclass
class SoundEvent:
    label: str
    confidence: float
    loudness_db: float
    ts: int


def _now_ms() -> int:
    return int(time.time() * 1000)


class SoundEventDetector(ABC):
    """Window-based sound-event detector interface."""

    name: str = "base"

    def __init__(self, config: Config) -> None:
        self.config = config
        self._window_frames = max(1, config.frames_for_ms(config.sound_event_window_ms))
        self._buf = bytearray()
        self._frames = 0

    @abstractmethod
    def analyze(self, pcm: bytes) -> List[SoundEvent]:
        """Classify one window of PCM16 audio into zero or more events."""
        raise NotImplementedError

    def feed(self, frame: bytes) -> List[SoundEvent]:
        """Accumulate one frame; analyze + return events when a window completes."""
        self._buf.extend(frame)
        self._frames += 1
        if self._frames >= self._window_frames:
            pcm = bytes(self._buf)
            self._buf.clear()
            self._frames = 0
            return self.analyze(pcm)
        return []

    def reset(self) -> None:
        self._buf.clear()
        self._frames = 0

    def close(self) -> None:
        pass


# --- YAMNet (real, optional) -----------------------------------------------

class YamnetSoundEvents(SoundEventDetector):
    """Google YAMNet (521 AudioSet classes) via TensorFlow Hub.

    Heavy + downloads a model on first use; guarded so its absence simply falls
    back to the heuristic detector. Maps YAMNet classes onto our label space.
    """

    name = "yamnet"
    _HUB_URL = "https://tfhub.dev/google/yamnet/1"
    _MAP = {
        "doorbell": "doorbell", "ding-dong": "doorbell", "bell": "doorbell",
        "alarm": "alarm", "smoke detector": "alarm", "siren": "alarm",
        "beep": "alarm", "buzzer": "alarm",
        "telephone": "phone", "ringtone": "phone", "telephone bell ringing": "phone",
        "knock": "knock", "tap": "knock",
        "glass": "glass_break", "shatter": "glass_break", "breaking": "glass_break",
        "music": "music", "musical instrument": "music", "singing": "music",
        "speech": "speech", "conversation": "speech", "narration": "speech",
    }

    def __init__(self, config: Config) -> None:
        super().__init__(config)
        try:
            import csv as _csv  # noqa: F401  (used below)
            import tensorflow_hub as hub  # type: ignore
            import tensorflow as tf  # type: ignore
        except Exception as exc:  # pragma: no cover - optional dep
            raise SoundEventError(f"yamnet deps not installed: {exc}") from exc
        try:  # pragma: no cover - network/model download
            self._tf = tf
            self._model = hub.load(self._HUB_URL)
            class_map_path = self._model.class_map_path().numpy().decode("utf-8")
            import csv
            with tf.io.gfile.GFile(class_map_path) as fh:
                self._classes = [row["display_name"] for row in csv.DictReader(fh)]
        except Exception as exc:  # pragma: no cover
            raise SoundEventError(f"could not load YAMNet: {exc}") from exc
        log.info("YamnetSoundEvents ready")

    def analyze(self, pcm: bytes) -> List[SoundEvent]:  # pragma: no cover - needs model
        if not pcm:
            return []
        import numpy as np

        loud = audio.dbfs(pcm)
        wav = np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768.0
        try:
            scores, _emb, _spec = self._model(wav)
            mean = scores.numpy().mean(axis=0)
            idx = int(mean.argmax())
            raw = self._classes[idx].lower()
            conf = float(mean[idx])
        except Exception as exc:
            log.warning("yamnet analyze failed: %s", exc)
            return []
        label = self._map_label(raw)
        if conf < self.config.sound_event_threshold or label is None:
            return []
        return [SoundEvent(label, conf, loud, _now_ms())]

    def _map_label(self, raw: str) -> Optional[str]:
        for key, mapped in self._MAP.items():
            if key in raw:
                return mapped
        return "noise"


# --- Heuristic fallback (no deps) ------------------------------------------

class HeuristicSoundEvents(SoundEventDetector):
    """Loudness + spectral heuristics. Not a classifier — a best-effort, fully
    offline approximation so the perception pipeline runs headless.

    Tonal sounds (low spectral flatness) map to alarm/doorbell/phone by dominant
    frequency band; broadband + high zero-crossing transients map to glass_break;
    mid-band moderate-ZCR energy maps to speech; otherwise music/noise. A loudness
    floor suppresses events in a quiet room. ``set_canned`` lets a demo inject a
    rotation of explicit labels.
    """

    name = "heuristic"
    FLOOR_DB = -45.0

    def __init__(self, config: Config) -> None:
        super().__init__(config)
        self._canned: List[str] = []
        self._canned_i = 0
        log.info(
            "HeuristicSoundEvents ready (threshold=%.2f, window=%dms) — "
            "approximate, offline.",
            config.sound_event_threshold,
            config.sound_event_window_ms,
        )

    def set_canned(self, labels: List[str]) -> None:
        """Demo helper: emit these labels in rotation (when loud enough)."""
        self._canned = list(labels)
        self._canned_i = 0

    def analyze(self, pcm: bytes) -> List[SoundEvent]:
        if not pcm:
            return []
        loud = audio.dbfs(pcm)
        if loud < self.FLOOR_DB:
            return []  # quiet room -> nothing notable
        conf = max(0.55, min(0.98, 0.55 + (loud - self.FLOOR_DB) / 50.0))
        if conf < self.config.sound_event_threshold:
            return []

        if self._canned:
            label = self._canned[self._canned_i % len(self._canned)]
            self._canned_i += 1
            return [SoundEvent(label, conf, loud, _now_ms())]

        feats = audio.spectral_features(pcm, self.config.sample_rate)
        zcr = audio.zero_crossing_rate(pcm)
        label = self._classify(feats["dominant_hz"], feats["flatness"], zcr)
        return [SoundEvent(label, conf, loud, _now_ms())]

    @staticmethod
    def _classify(dominant_hz: float, flatness: float, zcr: float) -> str:
        # Broadband, very noisy transient -> shattering glass.
        if flatness > 0.4 and zcr > 0.35:
            return "glass_break"
        # Tonal sounds (peaky spectrum) -> alarm/doorbell/phone by pitch band.
        if flatness < 0.2 and dominant_hz > 0:
            if dominant_hz < 500:
                return "alarm"
            if dominant_hz < 1000:
                return "doorbell"
            if dominant_hz < 2500:
                return "phone"
            return "alarm"
        # Voiced mid-band energy with moderate zero-crossings -> speech.
        if 150 <= dominant_hz <= 3500 and 0.05 <= zcr <= 0.30:
            return "speech"
        # Low, dull transient -> knock; otherwise music-ish broadband.
        if dominant_hz < 200 and zcr < 0.1:
            return "knock"
        return "music"


# --- Null (disabled) --------------------------------------------------------

class NullSoundEvents(SoundEventDetector):
    """Disabled detector — emits nothing (``JARVIS_SOUND_EVENTS=off``)."""

    name = "off"

    def analyze(self, pcm: bytes) -> List[SoundEvent]:
        return []

    def feed(self, frame: bytes) -> List[SoundEvent]:
        return []


# --- Factory ----------------------------------------------------------------

def create_sound_event_detector(config: Config) -> SoundEventDetector:
    """Build a detector from ``config.sound_events_engine`` with ``auto`` fallback.

    ``auto`` order: yamnet -> heuristic. ``off`` disables detection. Falls back to
    :class:`HeuristicSoundEvents` on any failure so we never hard-crash.
    """
    choice = (config.sound_events_engine or "auto").lower()

    def _heuristic() -> SoundEventDetector:
        return HeuristicSoundEvents(config)

    if choice in ("off", "none", "disabled"):
        log.info("sound events disabled (JARVIS_SOUND_EVENTS=off)")
        return NullSoundEvents(config)

    builders = {
        "yamnet": lambda: YamnetSoundEvents(config),
        "heuristic": _heuristic,
        "mock": _heuristic,
    }

    if choice == "auto":
        try:
            return YamnetSoundEvents(config)
        except SoundEventError as exc:
            log.info("sound events auto: %s", exc)
        except Exception as exc:  # pragma: no cover - defensive
            log.warning("sound events auto: unexpected error: %s", exc)
        log.info("sound events auto: using HeuristicSoundEvents")
        return _heuristic()

    builder = builders.get(choice)
    if builder is None:
        log.warning("unknown JARVIS_SOUND_EVENTS=%r; using HeuristicSoundEvents", choice)
        return _heuristic()
    try:
        return builder()
    except SoundEventError as exc:
        log.warning("sound engine %r unavailable (%s); using heuristic", choice, exc)
        return _heuristic()
    except Exception as exc:  # pragma: no cover - defensive
        log.warning("sound engine %r failed (%s); using heuristic", choice, exc)
        return _heuristic()
