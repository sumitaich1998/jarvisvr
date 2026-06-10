"""Multimodal perception (v1.1): rolling buffer + deterministic offline vision.

The :class:`PerceptionBuffer` keeps a short, time-windowed view of what the
headset currently sees/hears/looks-at, which the agent correlates with each user
utterance. :mod:`vision` provides a deterministic, offline "vision" used by the
MockLLM path so multimodal turns work with no API keys.
"""

from .buffer import (
    FrameRecord,
    PerceptionBuffer,
    decode_binary_vision_frame,
    encode_binary_vision_frame,
)
from .vision import (
    CANNED_OBJECTS,
    describe_scene,
    focus_object,
    mock_ocr,
    mock_translate,
)

__all__ = [
    "PerceptionBuffer",
    "FrameRecord",
    "decode_binary_vision_frame",
    "encode_binary_vision_frame",
    "describe_scene",
    "focus_object",
    "mock_ocr",
    "mock_translate",
    "CANNED_OBJECTS",
]
