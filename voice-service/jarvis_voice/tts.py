"""Text-to-speech.

Interface :class:`Speaker` with:

* :class:`PiperTTS`   — preferred; fast, high-quality, fully offline (needs a voice).
* :class:`Pyttsx3TTS` — uses the OS speech engine (offline, no model download).
* :class:`MockTTS`    — synthesizes a valid WAV (a short tone) and logs the text.

Every speaker provides both:

* ``synthesize(text) -> bytes`` — WAV (PCM16) bytes, usable headless / for tests
  and for streaming raw audio over the optional ``/audio`` channel.
* ``speak(text)`` — render and play through the speaker (or log, for the mock).

:func:`create_speaker` selects an engine with an ``auto`` fallback chain.
"""

from __future__ import annotations

import logging
import os
import tempfile
from abc import ABC, abstractmethod

from . import audio
from .audio import AudioUnavailable
from .config import Config

log = logging.getLogger(__name__)


class SpeakerError(RuntimeError):
    """Raised when a concrete speaker cannot initialize (triggers fallback)."""


class Speaker(ABC):
    name: str = "base"
    sample_rate: int = audio.SAMPLE_RATE

    @abstractmethod
    def synthesize(self, text: str) -> bytes:
        """Return WAV (PCM16) bytes for ``text``."""
        raise NotImplementedError

    def speak(self, text: str) -> None:
        """Default: synthesize then play via the audio backend (guarded)."""
        if not text:
            return
        wav = self.synthesize(text)
        try:
            audio.play_wav_bytes(wav, output_device=self._output_device)
        except AudioUnavailable as exc:
            log.warning("[TTS:%s] no audio output (%s). Text was: %r", self.name, exc, text)

    def stop(self) -> None:
        """Interrupt in-progress playback (best-effort; used for barge-in)."""
        audio.stop_playback()

    def set_language(self, language: str) -> None:
        """Best-effort multi-language hook (engine dependent; see subclasses)."""
        self._language = language

    _output_device = None
    _language = ""

    def close(self) -> None:
        pass


# --- Piper (preferred, offline) --------------------------------------------

class PiperTTS(Speaker):
    """Piper neural TTS. Requires a voice model (.onnx + .onnx.json)."""

    name = "piper"

    def __init__(self, config: Config) -> None:
        try:  # import path varies across piper-tts releases
            try:
                from piper.voice import PiperVoice  # type: ignore
            except Exception:
                from piper import PiperVoice  # type: ignore
        except Exception as exc:  # pragma: no cover - optional dep
            raise SpeakerError(f"piper-tts not installed: {exc}") from exc
        if not config.piper_model or not os.path.exists(config.piper_model):
            raise SpeakerError(
                "JARVIS_PIPER_MODEL must point to a downloaded Piper voice .onnx"
            )
        self._output_device = config.output_device
        try:
            self._voice = PiperVoice.load(config.piper_model, config_path=config.piper_config)
            self.sample_rate = int(self._voice.config.sample_rate)
        except Exception as exc:  # pragma: no cover - needs model
            raise SpeakerError(f"could not load Piper voice: {exc}") from exc
        log.info("PiperTTS ready (model=%s, sr=%d)", config.piper_model, self.sample_rate)

    def synthesize(self, text: str) -> bytes:
        import wave as _wave

        buf = tempfile.SpooledTemporaryFile()
        try:
            with _wave.open(buf, "wb") as wf:  # type: ignore[arg-type]
                self._voice.synthesize(text, wf)
            buf.seek(0)
            return buf.read()
        except Exception as exc:  # pragma: no cover - runtime guard
            log.warning("piper synthesize failed (%s); emitting silence", exc)
            return audio.pcm16_to_wav(audio.silence(300, self.sample_rate), self.sample_rate)
        finally:
            buf.close()


# --- pyttsx3 (OS voices, offline) ------------------------------------------

class Pyttsx3TTS(Speaker):
    """pyttsx3 wrapper around the OS speech engine (SAPI5/NSSpeech/espeak)."""

    name = "pyttsx3"

    def __init__(self, config: Config) -> None:
        try:
            import pyttsx3  # type: ignore
        except Exception as exc:  # pragma: no cover - optional dep
            raise SpeakerError(f"pyttsx3 not installed: {exc}") from exc
        self.config = config
        self._output_device = config.output_device
        try:
            self._engine = pyttsx3.init()
            if config.pyttsx3_rate:
                self._engine.setProperty("rate", config.pyttsx3_rate)
            if config.pyttsx3_voice:
                self._engine.setProperty("voice", config.pyttsx3_voice)
        except Exception as exc:  # pragma: no cover - platform dependent
            raise SpeakerError(f"could not init pyttsx3: {exc}") from exc
        log.info("Pyttsx3TTS ready")

    def synthesize(self, text: str) -> bytes:
        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        tmp.close()
        try:
            self._engine.save_to_file(text, tmp.name)
            self._engine.runAndWait()
            with open(tmp.name, "rb") as fh:
                return fh.read()
        except Exception as exc:  # pragma: no cover - platform dependent
            log.warning("pyttsx3 synthesize failed (%s); emitting silence", exc)
            return audio.pcm16_to_wav(audio.silence(300, self.sample_rate), self.sample_rate)
        finally:
            try:
                os.unlink(tmp.name)
            except OSError:
                pass

    def speak(self, text: str) -> None:
        if not text:
            return
        try:  # pyttsx3 plays natively; preferred over WAV round-trip.
            self._engine.say(text)
            self._engine.runAndWait()
        except Exception as exc:  # pragma: no cover - platform dependent
            log.warning("[TTS:pyttsx3] speak failed (%s). Text was: %r", exc, text)

    def stop(self) -> None:  # pragma: no cover - platform dependent
        try:
            self._engine.stop()
        except Exception:
            pass
        audio.stop_playback()

    def set_language(self, language: str) -> None:  # pragma: no cover - platform dependent
        self._language = language
        try:  # pick the first installed voice whose languages match the request.
            for voice in self._engine.getProperty("voices"):
                langs = " ".join(str(x) for x in getattr(voice, "languages", []))
                if language.lower() in (langs + " " + (voice.id or "")).lower():
                    self._engine.setProperty("voice", voice.id)
                    return
        except Exception:
            pass


# --- Mock (offline fallback) -----------------------------------------------

class MockTTS(Speaker):
    """Logs the text and synthesizes a short, valid WAV tone.

    Always works headless: ``speak`` never requires audio hardware, and
    ``synthesize`` returns a real WAV whose length scales with the text so tests
    can assert it parses and contains frames.
    """

    name = "mock"

    def __init__(self, config: Config) -> None:
        self.config = config
        self.sample_rate = config.sample_rate
        self._output_device = config.output_device
        log.info("MockTTS ready (logs text; synth = tone WAV)")

    def synthesize(self, text: str) -> bytes:
        # ~60ms/word, clamped, so output is always a non-empty valid WAV.
        words = max(1, len((text or "").split()))
        duration_ms = max(200, min(4000, words * 220))
        pcm = audio.tone(220.0, duration_ms, sample_rate=self.sample_rate, amplitude=0.2)
        return audio.pcm16_to_wav(pcm, self.sample_rate)

    def speak(self, text: str) -> None:
        log.info('[TTS:mock] "%s"', text)
        print(f'[Jarvis 🔊] "{text}"')
        # Best-effort playback if an audio backend exists; otherwise it's a no-op.
        if audio.audio_io_available():
            try:
                audio.play_wav_bytes(self.synthesize(text), output_device=self._output_device)
            except AudioUnavailable:
                pass


# --- Factory ----------------------------------------------------------------

def create_speaker(config: Config) -> Speaker:
    """Build a speaker from ``config.tts_engine`` with ``auto`` fallback.

    ``auto`` order: piper -> pyttsx3 -> mock. Falls back to :class:`MockTTS` on any
    failure so we never hard-crash.
    """
    choice = (config.tts_engine or "auto").lower()

    def _mock() -> Speaker:
        return MockTTS(config)

    builders = {
        "piper": lambda: PiperTTS(config),
        "piper-tts": lambda: PiperTTS(config),
        "pyttsx3": lambda: Pyttsx3TTS(config),
        "mock": _mock,
    }

    if choice == "auto":
        for builder in (lambda: PiperTTS(config), lambda: Pyttsx3TTS(config)):
            try:
                return builder()
            except SpeakerError as exc:
                log.info("tts auto: %s", exc)
            except Exception as exc:  # pragma: no cover - defensive
                log.warning("tts auto: unexpected error: %s", exc)
        log.info("tts auto: using MockTTS")
        return _mock()

    builder = builders.get(choice)
    if builder is None:
        log.warning("unknown JARVIS_TTS=%r; using MockTTS", choice)
        return _mock()
    try:
        return builder()
    except SpeakerError as exc:
        log.warning("tts engine %r unavailable (%s); using MockTTS", choice, exc)
        return _mock()
    except Exception as exc:  # pragma: no cover - defensive
        log.warning("tts engine %r failed (%s); using MockTTS", choice, exc)
        return _mock()
