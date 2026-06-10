"""Coverage for wakeword detectors via mocked optional libraries."""

from __future__ import annotations

import struct

import pytest

from jarvis_voice import audio
from jarvis_voice.wakeword import (
    EnergyFallback,
    OpenWakeWord,
    Porcupine,
    WakeWordDetector,
    WakeWordDetectorError,
    create_wakeword,
)

from conftest import fast_config


# --- abstract interface -----------------------------------------------------

def test_abstract_process_raises():
    class Concrete(WakeWordDetector):
        def process(self, frame):
            return super().process(frame)

    det = Concrete()
    with pytest.raises(NotImplementedError):
        det.process(b"")
    # default reset/close are no-ops
    det.reset()
    det.close()


# --- OpenWakeWord (fake openwakeword.model.Model) ---------------------------

def _install_oww(fake_module, predict_result):
    class FakeModel:
        def __init__(self, wakeword_models=None):
            self.wakeword_models = wakeword_models

        def predict(self, samples):
            return predict_result

        def reset(self):
            pass

    fake_module("openwakeword")
    fake_module("openwakeword.model", Model=FakeModel)
    return FakeModel


def test_openwakeword_fires_on_jarvis_key(fake_module):
    _install_oww(fake_module, {"hey_jarvis": 0.9})
    det = OpenWakeWord(fast_config(oww_model="hey_jarvis", wake_threshold=0.5))
    # feed >= 1 chunk (1280 samples * 2 bytes)
    fired = det.process(b"\x10\x10" * 1300)
    assert fired is True
    det.reset()


def test_openwakeword_non_jarvis_key_uses_max(fake_module):
    _install_oww(fake_module, {"other_model": 0.7})
    det = OpenWakeWord(fast_config(wake_threshold=0.5))
    assert det.process(b"\x10\x10" * 1300) is True


def test_openwakeword_below_threshold(fake_module):
    _install_oww(fake_module, {"hey_jarvis": 0.1})
    det = OpenWakeWord(fast_config(wake_threshold=0.5))
    assert det.process(b"\x10\x10" * 1300) is False


def test_openwakeword_model_path_branch(fake_module):
    _install_oww(fake_module, {"hey_jarvis": 0.9})
    det = OpenWakeWord(fast_config(oww_model="/models/hey_jarvis.onnx"))
    assert det.name == "openwakeword"


def test_openwakeword_empty_model_branch(fake_module):
    _install_oww(fake_module, {"hey_jarvis": 0.9})
    det = OpenWakeWord(fast_config(oww_model=""))
    assert det.process(b"\x10\x10" * 1300) is True


def test_openwakeword_not_installed_raises():
    # No fake installed -> import fails -> WakeWordDetectorError.
    with pytest.raises(WakeWordDetectorError):
        OpenWakeWord(fast_config())


# --- Porcupine (fake pvporcupine) -------------------------------------------

def _install_porcupine(fake_module, fire_first=True):
    class FakePorc:
        frame_length = 512

        def __init__(self):
            self.calls = 0

        def process(self, pcm):
            self.calls += 1
            return 0 if (fire_first and self.calls == 1) else -1

        def delete(self):
            pass

    fake_module("pvporcupine", create=lambda **kw: FakePorc())
    return FakePorc


def test_porcupine_fires(fake_module):
    _install_porcupine(fake_module, fire_first=True)
    det = Porcupine(fast_config(porcupine_access_key="key", porcupine_keyword="jarvis"))
    frame = struct.pack("<%dh" % 512, *([1000] * 512))
    assert det.process(frame) is True
    det.reset()
    det.close()


def test_porcupine_no_detection(fake_module):
    _install_porcupine(fake_module, fire_first=False)
    det = Porcupine(fast_config(porcupine_access_key="key"))
    frame = struct.pack("<%dh" % 512, *([0] * 512))
    assert det.process(frame) is False


def test_porcupine_requires_access_key(fake_module):
    _install_porcupine(fake_module)
    with pytest.raises(WakeWordDetectorError):
        Porcupine(fast_config(porcupine_access_key=None))


def test_porcupine_not_installed_raises():
    with pytest.raises(WakeWordDetectorError):
        Porcupine(fast_config(porcupine_access_key="key"))


# --- EnergyFallback ---------------------------------------------------------

def test_energy_fallback_reset():
    det = EnergyFallback(fast_config())
    loud = audio.tone(300.0, 30, amplitude=0.6)
    det.process(loud)
    det.reset()
    assert det._loud_run == 0 and det._cooldown == 0


# --- factory ----------------------------------------------------------------

def test_factory_concrete_openwakeword(fake_module):
    _install_oww(fake_module, {"hey_jarvis": 0.9})
    det = create_wakeword(fast_config(wake_engine="openwakeword"))
    assert det.name == "openwakeword"


def test_factory_auto_prefers_openwakeword(fake_module):
    _install_oww(fake_module, {"hey_jarvis": 0.9})
    det = create_wakeword(fast_config(wake_engine="auto"))
    assert det.name == "openwakeword"


def test_factory_concrete_porcupine(fake_module):
    _install_porcupine(fake_module)
    det = create_wakeword(fast_config(wake_engine="porcupine", porcupine_access_key="k"))
    assert det.name == "porcupine"


def test_factory_unknown_falls_back_to_energy():
    assert create_wakeword(fast_config(wake_engine="bogus")).name == "energy"


def test_factory_energy_explicit():
    assert create_wakeword(fast_config(wake_engine="energy")).name == "energy"
