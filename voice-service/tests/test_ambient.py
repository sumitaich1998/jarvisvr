"""Continuous ambient listening → audio_scene / audio_event (headless, mocks)."""

from __future__ import annotations

from jarvis_voice import audio
from jarvis_voice.ambient import AmbientCallbacks, AudioScene, build_ambient

from conftest import fast_config


def _window(cfg, amplitude=0.6):
    return audio.tone(300.0, cfg.ambient_window_ms, sample_rate=cfg.sample_rate, amplitude=amplitude)


def test_analyze_window_with_speech_produces_transcript_and_sounds():
    cfg = fast_config()
    amb = build_ambient(cfg)
    scene = amb.analyze_window(_window(cfg))
    assert isinstance(scene, AudioScene)
    assert scene.window_ms == cfg.ambient_window_ms
    assert scene.loudness_db < 0.0
    # speech present (loud window) -> overheard transcript from MockSTT
    assert scene.ambient_transcript == cfg.mock_transcript
    assert scene.speaker in ("user", "other", "unknown")
    assert scene.sounds  # heuristic soundscape present


def test_analyze_window_silence_has_no_transcript_or_sounds():
    cfg = fast_config()
    amb = build_ambient(cfg)
    scene = amb.analyze_window(audio.silence(cfg.ambient_window_ms, cfg.sample_rate))
    assert scene.ambient_transcript == ""
    assert scene.sounds == []
    assert scene.speaker == "unknown"


def test_process_frame_emits_scene_and_events():
    cfg = fast_config()
    scenes, events = [], []
    amb = build_ambient(
        cfg, AmbientCallbacks(on_audio_scene=scenes.append, on_audio_event=events.append)
    )
    frame = audio.tone(300.0, cfg.frame_ms, sample_rate=cfg.sample_rate, amplitude=0.6)
    for _ in range(cfg.frames_for_ms(cfg.ambient_window_ms) + 1):
        amb.process_frame(frame)
    assert scenes, "a scene should be emitted once a window fills"
    assert scenes[0].loudness_db < 0.0
    assert events, "sound events should fire on loud frames"


def test_speaker_tag_is_configurable():
    cfg = fast_config(ambient_speaker="unknown")
    amb = build_ambient(cfg)
    scene = amb.analyze_window(_window(cfg))
    assert scene.speaker == "unknown"


def test_simulate_scene_and_event():
    cfg = fast_config()
    scenes, events = [], []
    amb = build_ambient(
        cfg, AmbientCallbacks(on_audio_scene=scenes.append, on_audio_event=events.append)
    )
    amb.simulate_scene(transcript="they are discussing lunch", speaker="other")
    amb.simulate_event("doorbell", 0.9)
    assert scenes and scenes[0].speaker == "other"
    assert scenes[0].ambient_transcript.startswith("they")
    assert events and events[0].label == "doorbell"


def test_snapshot_returns_scene():
    cfg = fast_config()
    amb = build_ambient(cfg)
    scene = amb.snapshot()  # empty buffer -> low-loudness scene, no crash
    assert isinstance(scene, AudioScene)
    assert scene.window_ms == cfg.ambient_window_ms
