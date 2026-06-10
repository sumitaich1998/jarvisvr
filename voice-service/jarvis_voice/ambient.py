"""Continuous ambient listening (v1.1 perception).

Separate from the wake-word/STT pipeline, this constantly analyzes *room* audio
and produces:

* periodic ``perception.audio_scene`` — ambient/overheard transcript (when speech
  is present but NOT directed at Jarvis), a soundscape (labels), loudness, and the
  analysis ``window_ms``; and
* ``perception.audio_event`` — low-latency sound events (doorbell, alarm, …).

It is *frame-driven* like the pipeline (push PCM16 frames into
:meth:`process_frame`), so it is unit-testable headless with the Mock STT +
heuristic sound-event engines. The transcript reuses the configured STT engine
(:func:`~jarvis_voice.stt.create_transcriber`) with the Mock fallback; the window
is chunked by the same energy VAD the pipeline uses.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from typing import Callable, Dict, Iterable, List, Optional

from . import audio
from .config import Config
from .sound_events import SoundEvent, SoundEventDetector, create_sound_event_detector
from .stt import Transcriber, create_transcriber

log = logging.getLogger(__name__)


@dataclass
class AudioScene:
    """One window of ambient audio understanding (-> ``perception.audio_scene``)."""

    ambient_transcript: str = ""
    speaker: str = "unknown"           # user | other | unknown
    sounds: List[Dict[str, object]] = field(default_factory=list)
    loudness_db: float = -60.0
    window_ms: int = 4000


@dataclass
class AmbientCallbacks:
    on_audio_scene: Optional[Callable[[AudioScene], None]] = None
    on_audio_event: Optional[Callable[[SoundEvent], None]] = None
    on_state: Optional[Callable[[bool], None]] = None


def _safe(cb, *args) -> None:
    if cb is None:
        return
    try:
        cb(*args)
    except Exception as exc:  # pragma: no cover - callbacks shouldn't break the loop
        log.warning("ambient callback error: %s", exc)


class AmbientListener:
    """Continuously turns room audio into audio scenes + sound events."""

    def __init__(
        self,
        transcriber: Transcriber,
        sound_detector: SoundEventDetector,
        config: Config,
        callbacks: Optional[AmbientCallbacks] = None,
    ) -> None:
        self.transcriber = transcriber
        self.sounds = sound_detector
        self.config = config
        self.cb = callbacks or AmbientCallbacks()

        self._window_frames = max(1, config.frames_for_ms(config.ambient_window_ms))
        self._buf = bytearray()
        self._frames = 0
        self._stop = threading.Event()
        self.language = config.stt_language

    # --- core analysis (pure-ish; safe to call directly in tests) -----------
    def _speech_ratio(self, pcm: bytes) -> float:
        """Fraction of frame-sized chunks in ``pcm`` that are above the VAD floor."""
        step = max(1, self.config.bytes_per_frame)
        chunks = [pcm[i : i + step] for i in range(0, len(pcm), step)]
        if not chunks:
            return 0.0
        voiced = sum(1 for c in chunks if audio.rms_energy(c) >= self.config.vad_threshold)
        return voiced / len(chunks)

    def analyze_window(self, pcm: bytes) -> AudioScene:
        """Analyze a window of PCM16 into an :class:`AudioScene`.

        Speech that is present (but not wake-directed) becomes an *overheard*
        ambient transcript; the soundscape comes from the sound-event detector.
        """
        loudness = audio.dbfs(pcm)
        # Soundscape: aggregate detector hits over the whole window (max conf/label).
        sounds: List[Dict[str, object]] = []
        best: Dict[str, float] = {}
        try:
            for ev in self.sounds.analyze(pcm):
                if ev.confidence > best.get(ev.label, -1.0):
                    best[ev.label] = ev.confidence
        except Exception as exc:  # pragma: no cover - defensive
            log.warning("sound analyze failed: %s", exc)
        for label, conf in sorted(best.items(), key=lambda kv: kv[1], reverse=True):
            sounds.append({"label": label, "confidence": round(float(conf), 4)})

        transcript = ""
        speaker = "unknown"
        if self._speech_ratio(pcm) >= self.config.ambient_min_speech_ratio:
            try:
                transcript = self.transcriber.transcribe(pcm).text.strip()
            except Exception as exc:  # pragma: no cover - defensive
                log.warning("ambient transcribe failed: %s", exc)
                transcript = ""
            if transcript:
                speaker = self.config.ambient_speaker  # overheard => not the wake-caller

        return AudioScene(
            ambient_transcript=transcript,
            speaker=speaker,
            sounds=sounds,
            loudness_db=loudness,
            window_ms=self.config.ambient_window_ms,
        )

    # --- frame-driven loop --------------------------------------------------
    def process_frame(self, frame: bytes) -> Optional[AudioScene]:
        """Push one PCM16 frame. Emits sound events immediately and an audio scene
        once a full window has accumulated (returned + delivered via callback)."""
        # Low-latency sound events (their own short sub-window).
        try:
            for ev in self.sounds.feed(frame):
                _safe(self.cb.on_audio_event, ev)
        except Exception as exc:  # pragma: no cover - defensive
            log.warning("sound feed failed: %s", exc)

        self._buf.extend(frame)
        self._frames += 1
        if self._frames >= self._window_frames:
            pcm = bytes(self._buf)
            self._buf.clear()
            self._frames = 0
            scene = self.analyze_window(pcm)
            _safe(self.cb.on_audio_scene, scene)
            return scene
        return None

    def run(self, source: Iterable[bytes], stop: Optional[threading.Event] = None) -> None:
        """Blocking loop over a frame iterable (e.g. a mic stream)."""
        stop = stop or self._stop
        for frame in source:
            if stop.is_set():
                break
            self.process_frame(frame)

    def stop(self) -> None:
        self._stop.set()

    def snapshot(self) -> AudioScene:
        """Analyze whatever is currently buffered (for ``perception.request:once``)."""
        pcm = bytes(self._buf) if self._buf else audio.silence(self.config.frame_ms)
        scene = self.analyze_window(pcm)
        _safe(self.cb.on_audio_scene, scene)
        return scene

    # --- demo / no-audio helpers -------------------------------------------
    def simulate_scene(
        self,
        transcript: str = "",
        speaker: Optional[str] = None,
        sounds: Optional[List[Dict[str, object]]] = None,
        loudness_db: float = -28.0,
    ) -> AudioScene:
        """Emit a scene without audio (mock-friendly demo)."""
        scene = AudioScene(
            ambient_transcript=transcript,
            speaker=speaker or (self.config.ambient_speaker if transcript else "unknown"),
            sounds=sounds or [],
            loudness_db=loudness_db,
            window_ms=self.config.ambient_window_ms,
        )
        _safe(self.cb.on_audio_scene, scene)
        return scene

    def simulate_event(self, label: str, confidence: float = 0.9, loudness_db: float = -24.0):
        from .sound_events import _now_ms

        ev = SoundEvent(label, confidence, loudness_db, _now_ms())
        _safe(self.cb.on_audio_event, ev)
        return ev

    # --- multi-language hook ------------------------------------------------
    def set_language(self, language: str) -> None:
        """Best-effort: switch the ambient transcription language."""
        self.language = language
        setter = getattr(self.transcriber, "set_language", None)
        if callable(setter):
            setter(language)

    def close(self) -> None:
        for obj in (self.transcriber, self.sounds):
            try:
                obj.close()
            except Exception:  # pragma: no cover
                pass


def build_ambient(
    config: Config, callbacks: Optional[AmbientCallbacks] = None
) -> AmbientListener:
    """Construct an :class:`AmbientListener` with engines selected per config.

    Uses a *separate* STT instance from the main pipeline so recognizer state
    never collides, plus the configured sound-event detector (heuristic fallback).
    """
    transcriber = create_transcriber(config)
    detector = create_sound_event_detector(config)
    log.info(
        "ambient engines: stt=%s sound_events=%s (window=%dms)",
        transcriber.name,
        detector.name,
        config.ambient_window_ms,
    )
    return AmbientListener(transcriber, detector, config, callbacks)
