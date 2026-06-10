"""Coverage for sound_events: YAMNet (mocked), classify table, base, factory."""

from __future__ import annotations

import io
import types

import pytest

from jarvis_voice import audio
from jarvis_voice.sound_events import (
    HeuristicSoundEvents,
    SoundEvent,
    SoundEventDetector,
    YamnetSoundEvents,
    create_sound_event_detector,
)

from conftest import fast_config


# --- base interface ---------------------------------------------------------

def test_abstract_analyze_raises():
    class Concrete(SoundEventDetector):
        def analyze(self, pcm):
            return super().analyze(pcm)

    det = Concrete(fast_config())
    with pytest.raises(NotImplementedError):
        det.analyze(b"")


def test_base_reset_and_close():
    det = HeuristicSoundEvents(fast_config())
    det.feed(b"\x00\x00")
    det.reset()
    assert det._frames == 0
    det.close()


# --- heuristic classify table (every branch) --------------------------------

@pytest.mark.parametrize(
    "dominant,flatness,zcr,expected",
    [
        (100.0, 0.6, 0.5, "glass_break"),  # broadband + high ZCR
        (300.0, 0.1, 0.0, "alarm"),        # tonal < 500
        (700.0, 0.1, 0.0, "doorbell"),     # tonal 500-1000
        (1500.0, 0.1, 0.0, "phone"),       # tonal 1000-2500
        (3000.0, 0.1, 0.0, "alarm"),       # tonal > 2500
        (1000.0, 0.5, 0.2, "speech"),      # mid-band voiced
        (100.0, 0.5, 0.05, "knock"),       # low dull transient
        (5000.0, 0.3, 0.5, "music"),       # otherwise
    ],
)
def test_classify_branches(dominant, flatness, zcr, expected):
    assert HeuristicSoundEvents._classify(dominant, flatness, zcr) == expected


def test_heuristic_below_threshold_returns_empty():
    # Loud enough to pass the floor but below a very high threshold.
    cfg = fast_config(sound_event_threshold=0.99)
    det = HeuristicSoundEvents(cfg)
    quietish = audio.tone(300.0, cfg.sound_event_window_ms, amplitude=0.05)
    assert det.analyze(quietish) == []


def test_heuristic_real_analyze_emits_event():
    cfg = fast_config()
    det = HeuristicSoundEvents(cfg)
    loud = audio.tone(300.0, cfg.sound_event_window_ms, amplitude=0.6)
    events = det.analyze(loud)
    assert events and isinstance(events[0], SoundEvent)


# --- YAMNet (mocked tensorflow + tensorflow_hub) ----------------------------

def _install_yamnet(fake_module):
    import numpy as np

    class FakeYamnetModel:
        def class_map_path(self):
            return types.SimpleNamespace(numpy=lambda: b"/fake/classmap.csv")

        def __call__(self, wav):
            scores = types.SimpleNamespace(
                numpy=lambda: np.array([[0.1, 0.9], [0.2, 0.8]])
            )
            return scores, None, None

    def gfile(path):
        return io.StringIO("index,mid,display_name\n0,/m/0,Speech\n1,/m/1,Doorbell\n")

    fake_module("tensorflow_hub", load=lambda url: FakeYamnetModel())
    fake_module(
        "tensorflow",
        io=types.SimpleNamespace(gfile=types.SimpleNamespace(GFile=gfile)),
    )


def test_yamnet_init_and_map_label(fake_module):
    _install_yamnet(fake_module)
    det = YamnetSoundEvents(fast_config())
    assert det.name == "yamnet"
    # _map_label is reachable directly (analyze itself needs the real model).
    assert det._map_label("a doorbell rings") == "doorbell"
    assert det._map_label("unmapped sound") == "noise"


def test_yamnet_not_installed_raises():
    from jarvis_voice.sound_events import SoundEventError

    with pytest.raises(SoundEventError):
        YamnetSoundEvents(fast_config())


# --- factory ----------------------------------------------------------------

def test_factory_auto_prefers_yamnet(fake_module):
    _install_yamnet(fake_module)
    assert create_sound_event_detector(fast_config(sound_events_engine="auto")).name == "yamnet"


def test_factory_concrete_yamnet(fake_module):
    _install_yamnet(fake_module)
    assert create_sound_event_detector(fast_config(sound_events_engine="yamnet")).name == "yamnet"


def test_factory_yamnet_unavailable_falls_back():
    # yamnet requested but tensorflow absent -> heuristic fallback
    assert create_sound_event_detector(fast_config(sound_events_engine="yamnet")).name == "heuristic"


def test_factory_mock_alias_is_heuristic():
    assert create_sound_event_detector(fast_config(sound_events_engine="mock")).name == "heuristic"
