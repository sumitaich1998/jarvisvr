"""Environment-driven configuration for the voice pipeline.

All knobs have safe defaults so the service runs offline with mock/fallback
engines out of the box. Real engines are opted into via env vars (see
``.env.example``). A ``.env`` file is auto-loaded if ``python-dotenv`` is present.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field, fields
from typing import Optional

# Optional .env loading — guarded so the package imports without python-dotenv.
try:  # pragma: no cover - trivial import guard
    from dotenv import load_dotenv as _load_dotenv
except Exception:  # pragma: no cover

    def _load_dotenv(*_args, **_kwargs) -> bool:
        return False


def _env(key: str, default: str) -> str:
    val = os.environ.get(key)
    return default if val is None or val == "" else val


def _env_opt(key: str) -> Optional[str]:
    val = os.environ.get(key)
    return None if val is None or val == "" else val


def _env_int(key: str, default: int) -> int:
    try:
        return int(_env(key, str(default)))
    except (TypeError, ValueError):
        return default


def _env_float(key: str, default: float) -> float:
    try:
        return float(_env(key, str(default)))
    except (TypeError, ValueError):
        return default


def _env_int_opt(key: str) -> Optional[int]:
    raw = _env_opt(key)
    if raw is None:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


_TRUTHY = {"1", "true", "yes", "on", "y", "start", "enable", "enabled"}
_FALSY = {"0", "false", "no", "off", "n", "stop", "disable", "disabled", "none"}


def _env_bool(key: str, default: bool) -> bool:
    raw = _env_opt(key)
    if raw is None:
        return default
    low = raw.strip().lower()
    if low in _TRUTHY:
        return True
    if low in _FALSY:
        return False
    return default


@dataclass
class Config:
    """Runtime configuration for the voice service.

    Construct directly (e.g. in tests) or via :meth:`from_env`.
    """

    # --- Backend bridge ---
    backend_url: str = "ws://localhost:8765/jarvis"
    audio_url: str = "ws://localhost:8765/audio"
    locale: str = "en-US"
    device_name: str = "quest3"
    app_version: str = "0.1.0"

    # --- Engine selection: "auto" | concrete name ---
    wake_engine: str = "auto"     # auto | openwakeword | porcupine | energy
    stt_engine: str = "auto"      # auto | faster-whisper | vosk | mock
    tts_engine: str = "auto"      # auto | piper | pyttsx3 | mock

    # --- Audio framing (PCM16 mono) ---
    sample_rate: int = 16000
    frame_ms: int = 30
    input_device: Optional[int] = None
    output_device: Optional[int] = None

    # --- Wake word ---
    wake_word: str = "jarvis"
    wake_threshold: float = 0.5
    oww_model: str = "hey_jarvis"
    porcupine_access_key: Optional[str] = None
    porcupine_keyword: str = "jarvis"
    wake_energy_threshold: float = 1000.0
    wake_min_frames: int = 3

    # --- Endpointing / VAD ---
    vad_threshold: float = 300.0
    silence_ms: int = 800
    max_utterance_ms: int = 12000
    wake_grace_ms: int = 3000

    # --- STT ---
    whisper_model: str = "base.en"
    whisper_device: str = "cpu"
    whisper_compute_type: str = "int8"
    stt_language: str = "en"
    vosk_model: Optional[str] = None
    mock_transcript: str = "jarvis what is the weather in tokyo"

    # --- TTS ---
    piper_model: Optional[str] = None
    piper_config: Optional[str] = None
    pyttsx3_voice: Optional[str] = None
    pyttsx3_rate: Optional[int] = None
    tts_language: str = ""  # multi-language hook (best-effort; engine dependent)

    # --- Continuous ambient listening (v1.1 perception) ---
    # ambient_mode: auto (respond to perception.request) | on (autostart) | off (disabled)
    ambient_mode: str = "auto"
    ambient_window_ms: int = 4000          # one perception.audio_scene per window
    ambient_speaker: str = "other"          # user | other | unknown (overheard default)
    ambient_min_speech_ratio: float = 0.25  # frac. of voiced frames => speech present

    # --- Sound-event detection (v1.1 perception) ---
    sound_events_engine: str = "auto"       # auto | yamnet | heuristic | mock | off
    sound_event_threshold: float = 0.5
    sound_event_window_ms: int = 1000

    # --- Barge-in (interrupt TTS when the user starts talking) ---
    barge_in_enabled: bool = True
    barge_in_energy_threshold: float = 1500.0  # a bit above VAD to resist TTS bleed
    barge_in_min_frames: int = 3

    # --- Logging ---
    log_level: str = "INFO"

    # --- Derived ---
    @property
    def samples_per_frame(self) -> int:
        return int(self.sample_rate * self.frame_ms / 1000)

    @property
    def bytes_per_frame(self) -> int:
        return self.samples_per_frame * 2  # int16 == 2 bytes/sample, mono

    def frames_for_ms(self, ms: int) -> int:
        return max(1, int(round(ms / self.frame_ms)))

    @property
    def ambient_disabled(self) -> bool:
        return self.ambient_mode.lower() in _FALSY

    @property
    def ambient_autostart(self) -> bool:
        """True if ambient listening should start on connect (not just on request)."""
        return self.ambient_mode.lower() in _TRUTHY

    @classmethod
    def from_env(cls, load_dotenv: bool = True) -> "Config":
        """Build a config from environment variables (and optional .env)."""
        if load_dotenv:
            _load_dotenv()
        return cls(
            backend_url=_env("JARVIS_BACKEND_URL", cls.backend_url),
            audio_url=_env("JARVIS_AUDIO_URL", cls.audio_url),
            locale=_env("JARVIS_LOCALE", cls.locale),
            device_name=_env("JARVIS_DEVICE", cls.device_name),
            app_version=_env("JARVIS_APP_VERSION", cls.app_version),
            wake_engine=_env("JARVIS_WAKE", cls.wake_engine).lower(),
            stt_engine=_env("JARVIS_STT", cls.stt_engine).lower(),
            tts_engine=_env("JARVIS_TTS", cls.tts_engine).lower(),
            sample_rate=_env_int("JARVIS_SAMPLE_RATE", cls.sample_rate),
            frame_ms=_env_int("JARVIS_FRAME_MS", cls.frame_ms),
            input_device=_env_int_opt("JARVIS_INPUT_DEVICE"),
            output_device=_env_int_opt("JARVIS_OUTPUT_DEVICE"),
            wake_word=_env("JARVIS_WAKE_WORD", cls.wake_word),
            wake_threshold=_env_float("JARVIS_WAKE_THRESHOLD", cls.wake_threshold),
            oww_model=_env("JARVIS_OWW_MODEL", cls.oww_model),
            porcupine_access_key=_env_opt("JARVIS_PORCUPINE_ACCESS_KEY"),
            porcupine_keyword=_env("JARVIS_PORCUPINE_KEYWORD", cls.porcupine_keyword),
            wake_energy_threshold=_env_float(
                "JARVIS_WAKE_ENERGY_THRESHOLD", cls.wake_energy_threshold
            ),
            wake_min_frames=_env_int("JARVIS_WAKE_MIN_FRAMES", cls.wake_min_frames),
            vad_threshold=_env_float("JARVIS_VAD_THRESHOLD", cls.vad_threshold),
            silence_ms=_env_int("JARVIS_SILENCE_MS", cls.silence_ms),
            max_utterance_ms=_env_int("JARVIS_MAX_UTTERANCE_MS", cls.max_utterance_ms),
            wake_grace_ms=_env_int("JARVIS_WAKE_GRACE_MS", cls.wake_grace_ms),
            whisper_model=_env("JARVIS_WHISPER_MODEL", cls.whisper_model),
            whisper_device=_env("JARVIS_WHISPER_DEVICE", cls.whisper_device),
            whisper_compute_type=_env(
                "JARVIS_WHISPER_COMPUTE_TYPE", cls.whisper_compute_type
            ),
            stt_language=_env("JARVIS_STT_LANGUAGE", cls.stt_language),
            vosk_model=_env_opt("JARVIS_VOSK_MODEL"),
            mock_transcript=_env("JARVIS_MOCK_TRANSCRIPT", cls.mock_transcript),
            piper_model=_env_opt("JARVIS_PIPER_MODEL"),
            piper_config=_env_opt("JARVIS_PIPER_CONFIG"),
            pyttsx3_voice=_env_opt("JARVIS_PYTTSX3_VOICE"),
            pyttsx3_rate=_env_int_opt("JARVIS_PYTTSX3_RATE"),
            tts_language=_env("JARVIS_TTS_LANGUAGE", cls.tts_language),
            ambient_mode=_env("JARVIS_AMBIENT", cls.ambient_mode).lower(),
            ambient_window_ms=_env_int("JARVIS_AMBIENT_WINDOW_MS", cls.ambient_window_ms),
            ambient_speaker=_env("JARVIS_AMBIENT_SPEAKER", cls.ambient_speaker).lower(),
            ambient_min_speech_ratio=_env_float(
                "JARVIS_AMBIENT_MIN_SPEECH_RATIO", cls.ambient_min_speech_ratio
            ),
            sound_events_engine=_env("JARVIS_SOUND_EVENTS", cls.sound_events_engine).lower(),
            sound_event_threshold=_env_float(
                "JARVIS_SOUND_EVENT_THRESHOLD", cls.sound_event_threshold
            ),
            sound_event_window_ms=_env_int(
                "JARVIS_SOUND_EVENT_WINDOW_MS", cls.sound_event_window_ms
            ),
            barge_in_enabled=_env_bool("JARVIS_BARGE_IN", cls.barge_in_enabled),
            barge_in_energy_threshold=_env_float(
                "JARVIS_BARGE_IN_THRESHOLD", cls.barge_in_energy_threshold
            ),
            barge_in_min_frames=_env_int("JARVIS_BARGE_IN_MIN_FRAMES", cls.barge_in_min_frames),
            log_level=_env("JARVIS_LOG_LEVEL", cls.log_level).upper(),
        )

    def summary(self) -> str:
        """One-line human summary of the active engine selection."""
        return (
            f"wake={self.wake_engine} stt={self.stt_engine} tts={self.tts_engine} "
            f"ambient={self.ambient_mode} sound_events={self.sound_events_engine} "
            f"barge_in={self.barge_in_enabled} sr={self.sample_rate} "
            f"frame_ms={self.frame_ms} backend={self.backend_url}"
        )

    def as_dict(self) -> dict:
        out = {}
        for f in fields(self):
            out[f.name] = getattr(self, f.name)
        return out
