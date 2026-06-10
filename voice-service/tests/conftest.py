"""Shared pytest fixtures + fakes for headless voice-service tests.

Everything here runs with zero audio hardware and zero models: we use the Mock
STT/TTS engines and synthetic PCM16 frames, plus a controllable fake wake word
and a fake websocket.
"""

from __future__ import annotations

import sys
import threading
import types

import pytest

from jarvis_voice import audio
from jarvis_voice.config import Config
from jarvis_voice.tts import MockTTS
from jarvis_voice.wakeword import WakeWordDetector


# --- optional-engine mocking ------------------------------------------------

def install_module(monkeypatch, fullname: str, **attrs) -> types.ModuleType:
    """Inject a fake module into ``sys.modules`` (auto-reverted by monkeypatch).

    Lets us exercise the *success* branch of optional-engine imports (openwakeword,
    faster_whisper, vosk, piper, pyttsx3, tensorflow…) without installing them.
    Submodules (e.g. ``piper.voice``) are linked onto their parent.
    """
    mod = types.ModuleType(fullname)
    for key, value in attrs.items():
        setattr(mod, key, value)
    monkeypatch.setitem(sys.modules, fullname, mod)
    if "." in fullname:
        parent_name, child = fullname.rsplit(".", 1)
        parent = sys.modules.get(parent_name)
        if parent is not None:
            monkeypatch.setattr(parent, child, mod, raising=False)
    return mod


@pytest.fixture
def fake_module(monkeypatch):
    """Fixture returning an installer bound to the test's monkeypatch."""
    def _install(fullname: str, **attrs) -> types.ModuleType:
        return install_module(monkeypatch, fullname, **attrs)

    return _install


class FakeSoundDevice:
    """A minimal stand-in for the ``sounddevice`` module."""

    def __init__(self) -> None:
        self.played = []
        self.waited = 0
        self.stopped = 0

    def play(self, samples, samplerate=None, device=None):
        self.played.append((bytes(samples.tobytes()), samplerate, device))

    def wait(self):
        self.waited += 1

    def stop(self):
        self.stopped += 1

    def query_devices(self):
        return "fake-device-0"

    def RawInputStream(self, **kwargs):  # noqa: N802 (match sd API)
        return FakeRawInputStream(**kwargs)


class FakeRawInputStream:
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.started = False

    def start(self):
        self.started = True

    def stop(self):
        self.started = False

    def close(self):
        pass


class FakeMic:
    """A drop-in for :class:`~jarvis_voice.audio.MicStream` yielding fixed frames."""

    def __init__(self, frames):
        self.frames = frames

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def __iter__(self):
        return iter(self.frames)


def fast_config(**overrides) -> Config:
    """A Config tuned for fast, deterministic tests."""
    base = dict(
        wake_engine="energy",
        stt_engine="mock",
        tts_engine="mock",
        sample_rate=16000,
        frame_ms=30,
        wake_energy_threshold=1000.0,
        wake_min_frames=3,
        vad_threshold=500.0,
        silence_ms=90,        # -> 3 frames at 30ms
        max_utterance_ms=3000,
        wake_grace_ms=300,    # -> 10 frames
        mock_transcript="jarvis what is the weather",
        # --- v1.1 perception (fast windows) ---
        ambient_mode="auto",
        ambient_window_ms=120,        # -> 4 frames at 30ms
        ambient_speaker="other",
        ambient_min_speech_ratio=0.25,
        sound_events_engine="heuristic",
        sound_event_threshold=0.5,
        sound_event_window_ms=60,     # -> 2 frames
        barge_in_enabled=True,
        barge_in_energy_threshold=1000.0,
        barge_in_min_frames=3,
    )
    base.update(overrides)
    return Config(**base)


@pytest.fixture
def config() -> Config:
    return fast_config()


@pytest.fixture
def loud(config: Config) -> bytes:
    """A loud PCM16 frame (well above the VAD/wake thresholds)."""
    return audio.tone(300.0, config.frame_ms, sample_rate=config.sample_rate, amplitude=0.6)


@pytest.fixture
def quiet(config: Config) -> bytes:
    """A silent PCM16 frame."""
    return audio.silence(config.frame_ms, config.sample_rate)


class FakeWake(WakeWordDetector):
    """Wake detector that fires exactly once (re-armable), independent of audio."""

    name = "fake"

    def __init__(self, armed: bool = True) -> None:
        self._armed = armed

    def process(self, frame: bytes) -> bool:
        if self._armed:
            self._armed = False
            return True
        return False

    def arm(self) -> None:
        self._armed = True

    def reset(self) -> None:
        # Intentionally does NOT re-arm, so it won't refire after an utterance.
        pass


class FakeSpeaker:
    """Records spoken text; synthesizes a tiny valid WAV."""

    name = "fake"

    def __init__(self) -> None:
        self.spoken: list[str] = []
        self.stopped = False

    def speak(self, text: str) -> None:
        self.spoken.append(text)

    def stop(self) -> None:
        self.stopped = True

    def synthesize(self, text: str) -> bytes:
        return audio.pcm16_to_wav(audio.silence(50))


class BlockingTTS(MockTTS):
    """A speaker whose ``speak`` blocks until ``stop`` is called — used to test
    barge-in interrupting an in-progress TTS playback (the realistic concurrent
    flow: speak() runs in one thread, process_frame() in another)."""

    name = "blocking"

    def __init__(self, config) -> None:
        super().__init__(config)
        self.spoken: list[str] = []
        self.stopped = False
        self._release = threading.Event()

    def speak(self, text: str) -> None:  # type: ignore[override]
        self.spoken.append(text)
        # Block as if rendering/playing audio; released by stop() (barge-in).
        self._release.wait(timeout=5.0)

    def stop(self) -> None:  # type: ignore[override]
        self.stopped = True
        self._release.set()


class FakeWebSocket:
    """Minimal async websocket double: async ``send`` + async iteration."""

    def __init__(self, incoming=None) -> None:
        self.incoming = list(incoming or [])
        self.sent: list[str] = []
        self.closed = False

    async def send(self, data) -> None:
        self.sent.append(data)

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self.incoming:
            return self.incoming.pop(0)
        raise StopAsyncIteration

    async def close(self) -> None:
        self.closed = True
