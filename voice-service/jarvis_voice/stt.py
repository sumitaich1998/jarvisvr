"""Speech-to-text.

Interface :class:`Transcriber` with:

* :class:`FasterWhisperSTT` — preferred; high accuracy, batch (final-only).
* :class:`VoskSTT`          — streaming partials + final, fully offline.
* :class:`MockSTT`          — deterministic canned text; runs anywhere.

The interface unifies streaming and batch engines:

* ``accept(frame)`` feeds one PCM16 frame and may return an interim partial
  (streaming engines) or ``None`` (batch engines).
* ``final(pcm)`` returns the final :class:`TranscriptResult`. Batch engines use
  the supplied buffer; streaming engines use their internal accumulation.
* ``transcribe(pcm)`` = ``reset()`` + ``final(pcm)`` for one-shot use.

:func:`create_transcriber` selects an engine with an ``auto`` fallback chain.
"""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

from .config import Config

log = logging.getLogger(__name__)


class TranscriberError(RuntimeError):
    """Raised when a concrete transcriber cannot initialize (triggers fallback)."""


@dataclass
class TranscriptResult:
    text: str
    confidence: float = 1.0
    is_final: bool = True


class Transcriber(ABC):
    name: str = "base"
    supports_streaming: bool = False

    @abstractmethod
    def final(self, pcm: Optional[bytes] = None) -> TranscriptResult:
        """Return the final transcript for the current utterance."""
        raise NotImplementedError

    def accept(self, frame: bytes) -> Optional[str]:
        """Feed one PCM16 frame; optionally return an interim partial string."""
        return None

    def reset(self) -> None:
        """Begin a new utterance."""

    def set_language(self, language: str) -> None:
        """Best-effort multi-language hook (engine dependent; see subclasses)."""

    def transcribe(self, pcm: bytes) -> TranscriptResult:
        """One-shot convenience: reset + final over a whole buffer."""
        self.reset()
        return self.final(pcm)

    def close(self) -> None:
        pass


# --- faster-whisper (preferred) --------------------------------------------

class FasterWhisperSTT(Transcriber):
    """CTranslate2 Whisper. Batch: emits the final transcript at utterance end."""

    name = "faster-whisper"
    supports_streaming = False

    def __init__(self, config: Config) -> None:
        try:
            from faster_whisper import WhisperModel  # type: ignore
        except Exception as exc:  # pragma: no cover - optional dep
            raise TranscriberError(f"faster-whisper not installed: {exc}") from exc

        self.config = config
        self.language = config.stt_language or None
        try:
            self._model = WhisperModel(
                config.whisper_model,
                device=config.whisper_device,
                compute_type=config.whisper_compute_type,
            )
        except Exception as exc:  # pragma: no cover - needs model download
            raise TranscriberError(
                f"could not load Whisper model {config.whisper_model!r}: {exc}"
            ) from exc
        log.info("FasterWhisperSTT ready (model=%s)", config.whisper_model)

    def set_language(self, language: str) -> None:
        # Whisper supports per-call language; ""/"auto" => autodetect.
        self.language = (language or None) if language not in ("", "auto") else None

    def final(self, pcm: Optional[bytes] = None) -> TranscriptResult:
        if not pcm:
            return TranscriptResult("", 0.0, True)
        import numpy as np

        audio = np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768.0
        try:
            segments, _info = self._model.transcribe(
                audio, language=self.language, beam_size=1
            )
            parts, logprobs = [], []
            for seg in segments:
                parts.append(seg.text)
                if getattr(seg, "avg_logprob", None) is not None:
                    logprobs.append(seg.avg_logprob)
            text = "".join(parts).strip()
        except Exception as exc:  # pragma: no cover - runtime guard
            log.warning("whisper transcribe failed: %s", exc)
            return TranscriptResult("", 0.0, True)
        # Map avg logprob (~[-1,0]) to a rough 0..1 confidence.
        import math

        conf = 1.0
        if logprobs:
            conf = max(0.0, min(1.0, math.exp(sum(logprobs) / len(logprobs))))
        return TranscriptResult(text, conf, True)


# --- Vosk (streaming, offline) ---------------------------------------------

class VoskSTT(Transcriber):
    """Kaldi/Vosk streaming recognizer. Emits partials during the utterance."""

    name = "vosk"
    supports_streaming = True

    def __init__(self, config: Config) -> None:
        try:
            from vosk import KaldiRecognizer, Model  # type: ignore
        except Exception as exc:  # pragma: no cover - optional dep
            raise TranscriberError(f"vosk not installed: {exc}") from exc
        if not config.vosk_model:
            raise TranscriberError("JARVIS_VOSK_MODEL (path to model dir) is required")
        try:
            self._model = Model(config.vosk_model)
        except Exception as exc:  # pragma: no cover - needs model
            raise TranscriberError(f"could not load vosk model: {exc}") from exc
        self._KaldiRecognizer = KaldiRecognizer
        self.sample_rate = config.sample_rate
        self._rec = self._new_rec()
        log.info("VoskSTT ready (model=%s)", config.vosk_model)

    def _new_rec(self):
        rec = self._KaldiRecognizer(self._model, self.sample_rate)
        try:  # pragma: no cover - lib option
            rec.SetWords(True)
        except Exception:
            pass
        return rec

    def reset(self) -> None:
        self._rec = self._new_rec()

    def accept(self, frame: bytes) -> Optional[str]:
        try:
            if self._rec.AcceptWaveform(frame):
                res = json.loads(self._rec.Result())
                return res.get("text") or None
            res = json.loads(self._rec.PartialResult())
            return res.get("partial") or None
        except Exception as exc:  # pragma: no cover - runtime guard
            log.warning("vosk accept failed: %s", exc)
            return None

    def final(self, pcm: Optional[bytes] = None) -> TranscriptResult:
        try:
            if pcm:
                self._rec.AcceptWaveform(pcm)
            res = json.loads(self._rec.FinalResult())
            text = (res.get("text") or "").strip()
            conf = self._avg_conf(res)
            return TranscriptResult(text, conf, True)
        except Exception as exc:  # pragma: no cover - runtime guard
            log.warning("vosk final failed: %s", exc)
            return TranscriptResult("", 0.0, True)

    @staticmethod
    def _avg_conf(res: dict) -> float:
        words = res.get("result") or []
        confs = [w.get("conf", 1.0) for w in words if isinstance(w, dict)]
        return float(sum(confs) / len(confs)) if confs else 1.0


# --- Mock (offline fallback) -----------------------------------------------

class MockSTT(Transcriber):
    """Deterministic canned transcriber. Emits word-by-word partials then a final.

    Returns ``config.mock_transcript`` (overridable per call via
    :meth:`set_next`), so demos/tests work with zero audio or models.
    """

    name = "mock"
    supports_streaming = True

    def __init__(self, config: Config) -> None:
        self.config = config
        self._phrase = config.mock_transcript
        self._next: Optional[str] = None
        self._frames = 0
        self._emitted_words = 0
        log.info("MockSTT ready (canned=%r)", self._phrase)

    def set_next(self, text: str) -> None:
        """Override the transcript returned for the next utterance."""
        self._next = text

    def _current_phrase(self) -> str:
        return self._next if self._next is not None else self._phrase

    def reset(self) -> None:
        self._frames = 0
        self._emitted_words = 0

    def accept(self, frame: bytes) -> Optional[str]:
        self._frames += 1
        words = self._current_phrase().split()
        # Reveal one more word roughly every other frame, as a streaming partial.
        target = min(len(words), self._frames // 2)
        if target > self._emitted_words and target > 0:
            self._emitted_words = target
            return " ".join(words[:target])
        return None

    def final(self, pcm: Optional[bytes] = None) -> TranscriptResult:
        text = self._current_phrase().strip()
        self._next = None  # consume one-shot override
        return TranscriptResult(text, 1.0, True)


# --- Factory ----------------------------------------------------------------

def create_transcriber(config: Config) -> Transcriber:
    """Build a transcriber from ``config.stt_engine`` with ``auto`` fallback.

    ``auto`` order: faster-whisper -> vosk -> mock. Falls back to :class:`MockSTT`
    on any failure so we never hard-crash.
    """
    choice = (config.stt_engine or "auto").lower()

    def _mock() -> Transcriber:
        return MockSTT(config)

    builders = {
        "faster-whisper": lambda: FasterWhisperSTT(config),
        "faster_whisper": lambda: FasterWhisperSTT(config),
        "whisper": lambda: FasterWhisperSTT(config),
        "vosk": lambda: VoskSTT(config),
        "mock": _mock,
    }

    if choice == "auto":
        for builder in (lambda: FasterWhisperSTT(config), lambda: VoskSTT(config)):
            try:
                return builder()
            except TranscriberError as exc:
                log.info("stt auto: %s", exc)
            except Exception as exc:  # pragma: no cover - defensive
                log.warning("stt auto: unexpected error: %s", exc)
        log.info("stt auto: using MockSTT")
        return _mock()

    builder = builders.get(choice)
    if builder is None:
        log.warning("unknown JARVIS_STT=%r; using MockSTT", choice)
        return _mock()
    try:
        return builder()
    except TranscriberError as exc:
        log.warning("stt engine %r unavailable (%s); using MockSTT", choice, exc)
        return _mock()
    except Exception as exc:  # pragma: no cover - defensive
        log.warning("stt engine %r failed (%s); using MockSTT", choice, exc)
        return _mock()
