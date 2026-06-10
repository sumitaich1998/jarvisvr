"""Coverage for the remaining AmbientListener branches."""

from __future__ import annotations

import threading

from jarvis_voice import audio
from jarvis_voice.ambient import AmbientCallbacks, AmbientListener, build_ambient
from jarvis_voice.sound_events import SoundEvent, SoundEventDetector
from jarvis_voice.stt import MockSTT

from conftest import fast_config


class DupDetector(SoundEventDetector):
    """Returns two events with the same label (2nd lower conf) to exercise the
    soundscape de-dup branch; emits nothing per-frame."""

    name = "dup"

    def analyze(self, pcm):
        return [
            SoundEvent("music", 0.8, -10.0, 1),
            SoundEvent("music", 0.6, -10.0, 1),  # lower -> should not replace
        ]

    def feed(self, frame):
        return []


def _loud_window(cfg):
    return audio.tone(300.0, cfg.ambient_window_ms, amplitude=0.6)


def test_speech_ratio_empty():
    amb = build_ambient(fast_config())
    assert amb._speech_ratio(b"") == 0.0


def test_analyze_window_dedupes_sounds():
    cfg = fast_config()
    amb = AmbientListener(MockSTT(cfg), DupDetector(cfg), cfg)
    scene = amb.analyze_window(_loud_window(cfg))
    music = [s for s in scene.sounds if s["label"] == "music"]
    assert len(music) == 1
    assert music[0]["confidence"] == 0.8  # kept the higher-confidence hit


def test_analyze_window_speech_present_but_empty_transcript():
    # MockSTT with empty canned transcript -> speech detected but transcript "".
    cfg = fast_config(mock_transcript="")
    amb = AmbientListener(MockSTT(cfg), DupDetector(cfg), cfg)
    scene = amb.analyze_window(_loud_window(cfg))
    assert scene.ambient_transcript == ""
    assert scene.speaker == "unknown"  # never assigned because transcript empty


def test_run_breaks_on_preset_stop():
    cfg = fast_config()
    amb = build_ambient(cfg)
    stop = threading.Event()
    stop.set()
    amb.run([audio.silence(cfg.frame_ms)] * 3, stop=stop)


def test_run_consumes_source_default_stop():
    cfg = fast_config()
    scenes = []
    amb = build_ambient(cfg, AmbientCallbacks(on_audio_scene=scenes.append))
    frame = audio.tone(300.0, cfg.frame_ms, amplitude=0.6)
    amb.run([frame] * (cfg.frames_for_ms(cfg.ambient_window_ms) + 1))
    assert scenes


def test_stop_sets_event():
    amb = build_ambient(fast_config())
    amb.stop()
    assert amb._stop.is_set()


def test_set_language_forwards():
    amb = build_ambient(fast_config())
    amb.set_language("es")
    assert amb.language == "es"


def test_close_closes_engines():
    build_ambient(fast_config()).close()


def test_simulate_event_emits():
    events = []
    amb = build_ambient(fast_config(), AmbientCallbacks(on_audio_event=events.append))
    ev = amb.simulate_event("doorbell", 0.95)
    assert ev.label == "doorbell"
    assert events and events[0].label == "doorbell"
