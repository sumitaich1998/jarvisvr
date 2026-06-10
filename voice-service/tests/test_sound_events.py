"""Sound-event detection (heuristic fallback, headless)."""

from __future__ import annotations

from jarvis_voice import audio
from jarvis_voice.sound_events import (
    HeuristicSoundEvents,
    NullSoundEvents,
    SoundEvent,
    create_sound_event_detector,
)

from conftest import fast_config


def _loud_window(cfg):
    return audio.tone(300.0, cfg.sound_event_window_ms, sample_rate=cfg.sample_rate, amplitude=0.6)


def test_heuristic_detects_on_loud_audio():
    cfg = fast_config()
    det = HeuristicSoundEvents(cfg)
    events = det.analyze(_loud_window(cfg))
    assert events
    e = events[0]
    assert isinstance(e, SoundEvent)
    assert e.label
    assert 0.0 < e.confidence <= 1.0
    assert e.loudness_db < 0.0  # dBFS is negative


def test_heuristic_silence_no_events():
    cfg = fast_config()
    det = HeuristicSoundEvents(cfg)
    sil = audio.silence(cfg.sound_event_window_ms, cfg.sample_rate)
    assert det.analyze(sil) == []


def test_feed_accumulates_into_window():
    cfg = fast_config()
    det = HeuristicSoundEvents(cfg)
    frame = audio.tone(300.0, cfg.frame_ms, sample_rate=cfg.sample_rate, amplitude=0.6)
    got = []
    for _ in range(cfg.frames_for_ms(cfg.sound_event_window_ms) + 1):
        got += det.feed(frame)
    assert got  # at least one event after a full window


def test_canned_labels_rotate():
    cfg = fast_config()
    det = HeuristicSoundEvents(cfg)
    det.set_canned(["doorbell", "alarm"])
    loud = _loud_window(cfg)
    first = det.analyze(loud)[0].label
    second = det.analyze(loud)[0].label
    assert {first, second} == {"doorbell", "alarm"}


def test_factory_auto_is_heuristic_headless():
    det = create_sound_event_detector(fast_config(sound_events_engine="auto"))
    assert det.name == "heuristic"


def test_factory_unknown_falls_back_to_heuristic():
    det = create_sound_event_detector(fast_config(sound_events_engine="bogus"))
    assert det.name == "heuristic"


def test_factory_off_is_null_and_silent():
    det = create_sound_event_detector(fast_config(sound_events_engine="off"))
    assert det.name == "off"
    assert isinstance(det, NullSoundEvents)
    assert det.analyze(audio.tone(300.0, 100)) == []
    assert det.feed(audio.tone(300.0, 30)) == []
