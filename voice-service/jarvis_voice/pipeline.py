"""Voice pipeline orchestration.

A small, fully testable state machine:

    LISTENING ──wake──▶ RECORDING ──(silence/endpoint)──▶ [STT] ──▶ LISTENING

It is *frame-driven*: push fixed-size PCM16 frames into :meth:`process_frame`,
which advances the machine and fires callbacks. This means the whole thing can be
unit-tested headless by feeding synthetic frames (no mic, no models) using the
Mock/Energy engines. :meth:`run` is a convenience blocking loop over any frame
iterable (e.g. a :class:`~jarvis_voice.audio.MicStream`).

A separate :meth:`speak` path drives TTS for ``agent.speech`` text.
"""

from __future__ import annotations

import enum
import logging
import threading
from dataclasses import dataclass
from typing import Callable, Iterable, Optional

from .audio import rms_energy
from .config import Config
from .stt import MockSTT, TranscriptResult, Transcriber
from .tts import Speaker
from .wakeword import WakeWordDetector

log = logging.getLogger(__name__)


class PipelineState(enum.Enum):
    LISTENING = "listening"   # waiting for the wake word
    RECORDING = "recording"   # capturing an utterance until endpoint


@dataclass
class PipelineCallbacks:
    """Optional event hooks. All are best-effort and exceptions are swallowed."""

    on_state_change: Optional[Callable[[PipelineState], None]] = None
    on_wake: Optional[Callable[[], None]] = None
    on_partial: Optional[Callable[[str], None]] = None
    on_transcript: Optional[Callable[[TranscriptResult], None]] = None
    on_utterance_empty: Optional[Callable[[], None]] = None
    on_speak_start: Optional[Callable[[str], None]] = None
    on_speak_end: Optional[Callable[[str], None]] = None
    on_barge_in: Optional[Callable[[], None]] = None


def _safe(cb, *args) -> None:
    if cb is None:
        return
    try:
        cb(*args)
    except Exception as exc:  # pragma: no cover - callbacks shouldn't break the loop
        log.warning("pipeline callback error: %s", exc)


class VoicePipeline:
    """Orchestrates wake -> record -> STT, plus a TTS ``speak`` path."""

    def __init__(
        self,
        wake: WakeWordDetector,
        stt: Transcriber,
        tts: Speaker,
        config: Config,
        callbacks: Optional[PipelineCallbacks] = None,
    ) -> None:
        self.wake = wake
        self.stt = stt
        self.tts = tts
        self.config = config
        self.cb = callbacks or PipelineCallbacks()

        self.state = PipelineState.LISTENING
        self._buf = bytearray()
        self._heard_speech = False
        self._silence_frames = 0
        self._record_frames = 0

        self._silence_limit = config.frames_for_ms(config.silence_ms)
        self._max_frames = config.frames_for_ms(config.max_utterance_ms)
        self._grace_frames = config.frames_for_ms(config.wake_grace_ms)
        self._stop = threading.Event()
        self._speaking = False

        # --- barge-in (interrupt TTS when the user starts talking) ---
        self._barge_enabled = config.barge_in_enabled
        self._barge_threshold = config.barge_in_energy_threshold
        self._barge_limit = max(1, config.barge_in_min_frames)
        self._barge_run = 0
        self._barge_requested = False

    # --- state helpers ---
    def _set_state(self, state: PipelineState) -> None:
        if state != self.state:
            self.state = state
            log.debug("pipeline state -> %s", state.value)
            _safe(self.cb.on_state_change, state)

    def _begin_recording(self) -> None:
        self._buf.clear()
        self._heard_speech = False
        self._silence_frames = 0
        self._record_frames = 0
        try:
            self.stt.reset()
        except Exception as exc:  # pragma: no cover - defensive
            log.warning("stt.reset failed: %s", exc)
        self._set_state(PipelineState.RECORDING)
        _safe(self.cb.on_wake)

    def _finish_recording(self) -> Optional[TranscriptResult]:
        pcm = bytes(self._buf)
        result: Optional[TranscriptResult] = None
        try:
            result = self.stt.final(pcm)
        except Exception as exc:  # pragma: no cover - defensive
            log.warning("stt.final failed: %s", exc)
            result = None
        try:
            self.wake.reset()
        except Exception:  # pragma: no cover
            pass
        self._set_state(PipelineState.LISTENING)
        if result and result.text.strip():
            _safe(self.cb.on_transcript, result)
        else:
            _safe(self.cb.on_utterance_empty)
        return result

    # --- barge-in -----------------------------------------------------------
    def is_speaking(self) -> bool:
        return self._speaking

    def _barge_check(self, frame: bytes) -> None:
        """While TTS is playing, watch for the user talking over Jarvis."""
        if not self._barge_enabled:
            return
        if rms_energy(frame) >= self._barge_threshold:
            self._barge_run += 1
        else:
            self._barge_run = 0
        if self._barge_run >= self._barge_limit:
            self._trigger_barge_in()

    def _trigger_barge_in(self) -> None:
        if self._barge_requested:
            return
        self._barge_requested = True
        log.info("barge-in: user spoke over TTS — interrupting playback")
        try:
            self.tts.stop()
        except Exception as exc:  # pragma: no cover - defensive
            log.warning("tts.stop failed: %s", exc)
        # Stop suppressing the pipeline; the user's new utterance will flow next.
        self._speaking = False
        self._barge_run = 0
        _safe(self.cb.on_barge_in)

    # --- main entry: push one frame ---
    def process_frame(self, frame: bytes) -> PipelineState:
        """Advance the state machine with one PCM16 frame; returns new state."""
        # While speaking, the only thing we look for is the user barging in.
        if self._speaking:
            self._barge_check(frame)
            return self.state

        if self.state is PipelineState.LISTENING:
            try:
                fired = self.wake.process(frame)
            except Exception as exc:  # pragma: no cover - defensive
                log.warning("wake.process failed: %s", exc)
                fired = False
            if fired:
                log.info("wake word detected")
                self._begin_recording()
            return self.state

        # RECORDING
        self._buf.extend(frame)
        self._record_frames += 1

        partial = None
        try:
            partial = self.stt.accept(frame)
        except Exception as exc:  # pragma: no cover - defensive
            log.warning("stt.accept failed: %s", exc)
        if partial:
            _safe(self.cb.on_partial, partial)

        if rms_energy(frame) >= self.config.vad_threshold:
            self._heard_speech = True
            self._silence_frames = 0
        elif self._heard_speech:
            self._silence_frames += 1

        end_by_silence = self._heard_speech and self._silence_frames >= self._silence_limit
        end_by_max = self._record_frames >= self._max_frames
        end_by_nospeech = (not self._heard_speech) and self._record_frames >= self._grace_frames

        if end_by_silence or end_by_max or end_by_nospeech:
            reason = (
                "silence" if end_by_silence else "max_len" if end_by_max else "no_speech"
            )
            log.debug("utterance end (%s)", reason)
            self._finish_recording()
        return self.state

    # --- convenience loop ---
    def run(self, source: Iterable[bytes], stop: Optional[threading.Event] = None) -> None:
        """Blocking loop: feed frames from ``source`` until exhausted or stopped."""
        stop = stop or self._stop
        for frame in source:
            if stop.is_set():
                break
            self.process_frame(frame)

    def stop(self) -> None:
        self._stop.set()

    # --- TTS path ---
    def speak(self, text: str) -> None:
        """Speak ``text`` (the backend's ``agent.speech``) via the TTS engine.

        Sets the ``speaking`` flag so concurrent :meth:`process_frame` calls (from
        the mic thread) can detect barge-in and interrupt playback via ``tts.stop``.
        """
        if not text:
            return
        _safe(self.cb.on_speak_start, text)
        self._speaking = True
        self._barge_run = 0
        self._barge_requested = False
        try:
            self.tts.speak(text)
        except Exception as exc:  # pragma: no cover - defensive
            log.warning("tts.speak failed: %s", exc)
        finally:
            self._speaking = False
            _safe(self.cb.on_speak_end, text)

    def set_language(self, language: str) -> None:
        """Best-effort multi-language hook: forwards to the STT + TTS engines."""
        for engine in (self.stt, self.tts):
            setter = getattr(engine, "set_language", None)
            if callable(setter):
                try:
                    setter(language)
                except Exception as exc:  # pragma: no cover - defensive
                    log.warning("set_language failed on %s: %s", engine, exc)

    def synthesize(self, text: str) -> bytes:
        """Return WAV bytes for ``text`` (e.g. to stream over the /audio channel)."""
        return self.tts.synthesize(text)

    # --- demo helper (no audio hardware needed) ---
    def simulate_utterance(self, text: str) -> TranscriptResult:
        """Bypass wake+VAD and emit ``text`` as a transcript (mock-friendly demo)."""
        _safe(self.cb.on_wake)
        if isinstance(self.stt, MockSTT):
            self.stt.set_next(text)
        if text:
            _safe(self.cb.on_partial, text)
        result = TranscriptResult(text=text, confidence=1.0, is_final=True)
        if text.strip():
            _safe(self.cb.on_transcript, result)
        else:
            _safe(self.cb.on_utterance_empty)
        return result

    def close(self) -> None:
        for obj in (self.wake, self.stt, self.tts):
            try:
                obj.close()
            except Exception:  # pragma: no cover
                pass


def build_pipeline(
    config: Config, callbacks: Optional[PipelineCallbacks] = None
) -> VoicePipeline:
    """Construct a pipeline with engines selected per ``config`` (with fallbacks)."""
    from .stt import create_transcriber
    from .tts import create_speaker
    from .wakeword import create_wakeword

    wake = create_wakeword(config)
    stt = create_transcriber(config)
    tts = create_speaker(config)
    log.info(
        "pipeline engines: wake=%s stt=%s tts=%s", wake.name, stt.name, tts.name
    )
    return VoicePipeline(wake, stt, tts, config, callbacks)
