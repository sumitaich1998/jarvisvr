"""Barge-in: user speech while TTS plays interrupts playback + notifies."""

from __future__ import annotations

import threading
import time

from jarvis_voice import audio
from jarvis_voice.pipeline import PipelineCallbacks, VoicePipeline
from jarvis_voice.stt import MockSTT

from conftest import BlockingTTS, FakeWake, fast_config


def _wait(pred, timeout=2.0) -> bool:
    end = time.time() + timeout
    while time.time() < end:
        if pred():
            return True
        time.sleep(0.005)
    return pred()


def _loud(cfg) -> bytes:
    return audio.tone(300.0, cfg.frame_ms, sample_rate=cfg.sample_rate, amplitude=0.6)


def test_barge_in_interrupts_tts():
    """The realistic flow: speak() blocks in one thread; mic frames in another
    detect the user talking and interrupt playback via tts.stop()."""
    cfg = fast_config()
    tts = BlockingTTS(cfg)
    fired = []
    cb = PipelineCallbacks(on_barge_in=lambda: fired.append(True))
    pipe = VoicePipeline(FakeWake(armed=False), MockSTT(cfg), tts, cfg, cb)

    t = threading.Thread(target=pipe.speak, args=("a long sentence to read aloud",))
    t.start()
    try:
        assert _wait(pipe.is_speaking), "pipeline should be speaking"
        loud = _loud(cfg)
        for _ in range(cfg.barge_in_min_frames + 5):
            pipe.process_frame(loud)
            if fired:
                break
        assert fired, "barge-in should fire while speaking"
        assert tts.stopped is True
    finally:
        tts.stop()  # ensure the worker thread is released even on failure
        t.join(timeout=2.0)
    assert not t.is_alive()
    assert not pipe.is_speaking()


def test_no_barge_in_when_not_speaking():
    cfg = fast_config()
    fired = []
    pipe = VoicePipeline(
        FakeWake(armed=False), MockSTT(cfg), BlockingTTS(cfg), cfg,
        PipelineCallbacks(on_barge_in=lambda: fired.append(True)),
    )
    for _ in range(10):
        pipe.process_frame(_loud(cfg))
    assert not fired


def test_barge_in_can_be_disabled():
    cfg = fast_config(barge_in_enabled=False)
    fired = []
    pipe = VoicePipeline(
        FakeWake(armed=False), MockSTT(cfg), BlockingTTS(cfg), cfg,
        PipelineCallbacks(on_barge_in=lambda: fired.append(True)),
    )
    pipe._speaking = True  # simulate TTS playing
    for _ in range(10):
        pipe.process_frame(_loud(cfg))
    assert not fired
    assert pipe.is_speaking()  # never interrupted
