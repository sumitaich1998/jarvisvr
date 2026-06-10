"""Wake-word detection ("Jarvis").

Interface :class:`WakeWordDetector` with three implementations:

* :class:`OpenWakeWord` — preferred, open models (built-in ``hey_jarvis``).
* :class:`Porcupine`    — Picovoice (built-in ``jarvis`` keyword; needs access key).
* :class:`EnergyFallback` — dependency-free; approximates wake via speech onset.

All detectors are *streaming*: feed fixed-size PCM16 frames via :meth:`process`,
which returns ``True`` on the frame where the wake word is spotted. Real engines
buffer internally to their required window size, decoupling them from the mic
frame size. :func:`create_wakeword` selects an engine from config with an
``auto`` fallback chain that never hard-crashes.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod

from .audio import rms_energy
from .config import Config

log = logging.getLogger(__name__)


class WakeWordDetectorError(RuntimeError):
    """Raised when a concrete detector cannot initialize (triggers fallback)."""


class WakeWordDetector(ABC):
    """Streaming wake-word detector interface."""

    name: str = "base"

    @abstractmethod
    def process(self, frame: bytes) -> bool:
        """Feed one PCM16 frame; return True iff the wake word fired on it."""
        raise NotImplementedError

    def reset(self) -> None:
        """Clear internal state (called when returning to the listening state)."""

    def close(self) -> None:
        """Release any underlying resources."""


# --- OpenWakeWord (preferred) ----------------------------------------------

class OpenWakeWord(WakeWordDetector):
    """openWakeWord-backed detector. Uses the built-in ``hey_jarvis`` model."""

    name = "openwakeword"
    # openWakeWord recommends ~80ms chunks at 16 kHz.
    CHUNK_SAMPLES = 1280

    def __init__(self, config: Config) -> None:
        try:
            from openwakeword.model import Model  # type: ignore
        except Exception as exc:  # pragma: no cover - optional dep
            raise WakeWordDetectorError(f"openwakeword not installed: {exc}") from exc

        self.config = config
        self.threshold = config.wake_threshold
        self._buf = bytearray()
        try:
            model_arg = config.oww_model
            # Accept either a built-in model name or a path to a model file.
            if model_arg and (model_arg.endswith(".onnx") or model_arg.endswith(".tflite")):
                self._model = Model(wakeword_models=[model_arg])
            elif model_arg:
                self._model = Model(wakeword_models=[model_arg])
            else:
                self._model = Model()
        except Exception as exc:  # pragma: no cover - needs model download
            raise WakeWordDetectorError(
                f"could not load openwakeword model {config.oww_model!r}: {exc}"
            ) from exc
        log.info("OpenWakeWord ready (model=%s, threshold=%.2f)", config.oww_model, self.threshold)

    def process(self, frame: bytes) -> bool:
        import numpy as np  # numpy is a base dep

        self._buf.extend(frame)
        fired = False
        chunk_bytes = self.CHUNK_SAMPLES * 2
        while len(self._buf) >= chunk_bytes:
            chunk = bytes(self._buf[:chunk_bytes])
            del self._buf[:chunk_bytes]
            samples = np.frombuffer(chunk, dtype=np.int16)
            try:
                scores = self._model.predict(samples)
            except Exception as exc:  # pragma: no cover - runtime guard
                log.warning("openwakeword predict failed: %s", exc)
                return False
            # Pick the score for the jarvis-ish model key.
            best = 0.0
            for key, val in scores.items():
                if "jarvis" in key.lower() or self.config.wake_word in key.lower():
                    best = max(best, float(val))
            if best == 0.0 and scores:
                best = max(float(v) for v in scores.values())
            if best >= self.threshold:
                fired = True
        return fired

    def reset(self) -> None:
        self._buf.clear()
        try:  # pragma: no cover - depends on lib internals
            self._model.reset()
        except Exception:
            pass


# --- Porcupine --------------------------------------------------------------

class Porcupine(WakeWordDetector):
    """Picovoice Porcupine detector. Uses the built-in ``jarvis`` keyword."""

    name = "porcupine"

    def __init__(self, config: Config) -> None:
        try:
            import pvporcupine  # type: ignore
        except Exception as exc:  # pragma: no cover - optional dep
            raise WakeWordDetectorError(f"pvporcupine not installed: {exc}") from exc

        if not config.porcupine_access_key:
            raise WakeWordDetectorError(
                "JARVIS_PORCUPINE_ACCESS_KEY is required for the Porcupine engine"
            )
        try:
            self._pv = pvporcupine.create(
                access_key=config.porcupine_access_key,
                keywords=[config.porcupine_keyword],
                sensitivities=[config.wake_threshold],
            )
        except Exception as exc:  # pragma: no cover - needs key/model
            raise WakeWordDetectorError(f"could not create Porcupine: {exc}") from exc

        self._frame_bytes = self._pv.frame_length * 2
        self._buf = bytearray()
        log.info(
            "Porcupine ready (keyword=%s, frame_length=%d)",
            config.porcupine_keyword,
            self._pv.frame_length,
        )

    def process(self, frame: bytes) -> bool:
        import struct

        self._buf.extend(frame)
        fired = False
        while len(self._buf) >= self._frame_bytes:
            chunk = bytes(self._buf[: self._frame_bytes])
            del self._buf[: self._frame_bytes]
            pcm = struct.unpack_from("<%dh" % self._pv.frame_length, chunk)
            try:
                if self._pv.process(pcm) >= 0:
                    fired = True
            except Exception as exc:  # pragma: no cover - runtime guard
                log.warning("porcupine process failed: %s", exc)
                return False
        return fired

    def reset(self) -> None:
        self._buf.clear()

    def close(self) -> None:  # pragma: no cover - hardware/lib dependent
        try:
            self._pv.delete()
        except Exception:
            pass


# --- Energy fallback (no deps) ---------------------------------------------

class EnergyFallback(WakeWordDetector):
    """Dependency-free fallback.

    It cannot recognize the literal word "Jarvis" — instead it fires on a burst
    of speech-level energy (``wake_energy_threshold`` sustained for
    ``wake_min_frames`` consecutive frames). This makes the pipeline usable with
    zero models (e.g. push-to-talk-ish / "just start talking"), and is clearly
    documented as an approximation. A short cooldown prevents immediate re-fire.
    """

    name = "energy"

    def __init__(self, config: Config) -> None:
        self.threshold = config.wake_energy_threshold
        self.min_frames = max(1, config.wake_min_frames)
        self._loud_run = 0
        self._cooldown = 0
        self._cooldown_frames = config.frames_for_ms(1000)
        log.info(
            "EnergyFallback wake ready (threshold=%.0f, min_frames=%d) — "
            "fires on speech onset, not the literal word.",
            self.threshold,
            self.min_frames,
        )

    def process(self, frame: bytes) -> bool:
        if self._cooldown > 0:
            self._cooldown -= 1
            return False
        if rms_energy(frame) >= self.threshold:
            self._loud_run += 1
        else:
            self._loud_run = 0
        if self._loud_run >= self.min_frames:
            self._loud_run = 0
            self._cooldown = self._cooldown_frames
            return True
        return False

    def reset(self) -> None:
        self._loud_run = 0
        self._cooldown = 0


# --- Factory ----------------------------------------------------------------

def create_wakeword(config: Config) -> WakeWordDetector:
    """Build a detector from ``config.wake_engine`` with an ``auto`` fallback chain.

    ``auto`` order: openwakeword -> porcupine -> energy. Concrete selections fall
    back to :class:`EnergyFallback` on failure so we never hard-crash.
    """
    choice = (config.wake_engine or "auto").lower()

    def _energy() -> WakeWordDetector:
        return EnergyFallback(config)

    builders = {
        "openwakeword": lambda: OpenWakeWord(config),
        "oww": lambda: OpenWakeWord(config),
        "porcupine": lambda: Porcupine(config),
        "pvporcupine": lambda: Porcupine(config),
        "energy": _energy,
        "fallback": _energy,
    }

    if choice == "auto":
        for builder in (lambda: OpenWakeWord(config), lambda: Porcupine(config)):
            try:
                return builder()
            except WakeWordDetectorError as exc:
                log.info("wake auto: %s", exc)
            except Exception as exc:  # pragma: no cover - defensive
                log.warning("wake auto: unexpected error: %s", exc)
        log.info("wake auto: using EnergyFallback")
        return _energy()

    builder = builders.get(choice)
    if builder is None:
        log.warning("unknown JARVIS_WAKE=%r; using EnergyFallback", choice)
        return _energy()
    try:
        return builder()
    except WakeWordDetectorError as exc:
        log.warning("wake engine %r unavailable (%s); using EnergyFallback", choice, exc)
        return _energy()
    except Exception as exc:  # pragma: no cover - defensive
        log.warning("wake engine %r failed (%s); using EnergyFallback", choice, exc)
        return _energy()
