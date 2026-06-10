"""Perception buffer, /vision binary codec, and deterministic offline vision."""

from __future__ import annotations

import pytest

from jarvis_backend.perception import buffer as BUF
from jarvis_backend.perception import vision as V
from jarvis_backend.perception.buffer import (
    PerceptionBuffer,
    decode_binary_vision_frame,
    encode_binary_vision_frame,
)
from jarvis_backend.protocol import now_ms


# --- binary codec -----------------------------------------------------------


def test_codec_roundtrip():
    msg = encode_binary_vision_frame({"frame_id": "F", "seq": 1}, b"\xff\xd8pixels")
    header, image = decode_binary_vision_frame(msg)
    assert header["frame_id"] == "F" and image == b"\xff\xd8pixels"


def test_codec_too_short():
    with pytest.raises(ValueError):
        decode_binary_vision_frame(b"\x00\x01")


def test_codec_header_len_exceeds():
    with pytest.raises(ValueError):
        decode_binary_vision_frame((1000).to_bytes(4, "big") + b"short")


# --- buffer ingest/query ----------------------------------------------------


def test_add_vision_frame_raw_and_inline():
    b = PerceptionBuffer(max_frames=2)
    rec = b.add_vision_frame({"frame_id": "a", "width": 4, "height": 4}, raw=b"abcd")
    assert rec.size_bytes == 4 and rec.data_b64 is not None
    b.add_vision_frame({"frame_id": "b", "data": "QUJDRA=="})  # inline base64
    assert b.frames_seen == 2 and b.latest_frame().frame_id == "b"
    assert b.latest_frame().size_bytes > 0  # estimated from b64 length
    assert b.vision_active is True


def test_add_vision_frame_meta_and_has_vision():
    b = PerceptionBuffer()
    assert b.has_vision() is False
    b.add_vision_frame({"frame_id": "x", "format": "png", "data": "QQ=="})
    meta = b.latest_frame().meta()
    assert meta["has_pixels"] is True and meta["format"] == "png"
    assert b.has_vision() is True


def test_audio_gaze_scene_and_state():
    b = PerceptionBuffer()
    b.add_audio_event({"label": "doorbell"})
    b.add_audio_scene({"ambient_transcript": "hi"})
    b.set_gaze({"hit_object_id": "O1"})
    b.set_scene_objects({"objects": [{"label": "mug"}], "frame_id": "F9"})
    assert b.latest_audio_event()["label"] == "doorbell"
    assert b.latest_audio_scene()["ambient_transcript"] == "hi"
    assert b.latest_gaze["hit_object_id"] == "O1"
    assert b.scene_objects_frame_id == "F9"
    assert b.ambient_active is True


def test_set_state_toggles_active_flags():
    b = PerceptionBuffer()
    b.set_state({"vision": {"active": True}, "ambient_audio": {"active": True}})
    assert b.vision_active is True and b.ambient_active is True
    b.set_state({"vision": {"active": False}, "ambient_audio": {"active": False}})
    assert b.vision_active is False and b.ambient_active is False
    b.set_state({"unrelated": 1})  # no active keys -> unchanged
    assert b.vision_active is False


def test_recent_sounds_window():
    b = PerceptionBuffer(audio_window_ms=1000)
    b.add_audio_event({"label": "old", "ts": now_ms() - 100000})
    b.add_audio_event({"label": "new"})
    labels = [e["label"] for e in b.recent_sounds()]
    assert "new" in labels and "old" not in labels
    assert b.recent_sounds(window_ms=10_000_000)  # wide window includes old


def test_images_for_llm_filters_and_limits():
    b = PerceptionBuffer()
    b.add_vision_frame({"frame_id": "nopix"})  # no data -> skipped
    b.add_vision_frame({"frame_id": "p", "format": "png", "data": "QQ=="})
    b.add_vision_frame({"frame_id": "j", "format": "jpeg", "data": "Qg=="})
    imgs = b.images_for_llm(1)
    assert len(imgs) == 1 and imgs[0][1] == "image/jpeg"  # most recent first
    assert b.images_for_llm(5)[1][1] == "image/png"


def test_current_context_snapshot():
    b = PerceptionBuffer()
    b.add_vision_frame({"frame_id": "f", "data": "QQ=="})
    cd = b.current_context()
    assert cd["has_vision"] and cd["frame"]["frame_id"] == "f"
    assert cd["frame_count"] == 1


def test_latest_frame_empty():
    assert PerceptionBuffer().latest_frame() is None


# --- vision -----------------------------------------------------------------


def test_normalize_lang():
    assert V.normalize_lang(None) == "es"
    assert V.normalize_lang("Spanish") == "es"
    assert V.normalize_lang("klingon") == "klingon"


def test_scene_objects_detected_vs_canned():
    assert V.scene_objects({"objects": [{"label": "x"}]}) == [{"label": "x"}]
    assert V.scene_objects({}) == V.CANNED_OBJECTS


def test_join_labels():
    assert V._join_labels([]) == "nothing in particular"
    assert V._join_labels(["a"]) == "a"
    assert V._join_labels(["a", "b"]) == "a and b"
    assert V._join_labels(["a", "b", "c"]) == "a, b, and c"


def test_describe_scene_camera_vs_desk():
    cam = V.describe_scene({"objects": [{"label": "phone"}]})
    assert "your camera" in cam["text"]
    desk = V.describe_scene({})
    assert "your desk" in desk["text"]


def test_focus_object_by_hit_id_point_and_fallback(monkeypatch):
    objs = [
        {"label": "a", "object_id": "O1", "position": [0, 0, 0]},
        {"label": "b", "id": "O2", "position": [5, 5, 5]},
    ]
    assert V.focus_object({"objects": objs, "gaze": {"hit_object_id": "O2"}})["label"] == "b"
    near = V.focus_object({"objects": objs, "gaze": {"hit_point": [4.9, 5, 5]}})
    assert near["label"] == "b"
    assert V.focus_object({"objects": objs})["label"] == "a"  # fallback first
    monkeypatch.setattr(V, "CANNED_OBJECTS", [])
    assert V.focus_object({"objects": []}) is None


def test_mock_ocr_object_text_and_canned():
    assert V.mock_ocr({"objects": [{"text": "HELLO"}]}) == "HELLO"
    canned = V.mock_ocr({"frame": {"seq": 3}})
    assert canned in V._CANNED_SIGNS


def test_mock_translate():
    assert V.mock_translate("hello", "spanish") == "hola"
    assert V.mock_translate("CAUTION wet floor", "fr").lower().startswith("attention")
    assert V.mock_translate("xyz", "es") == "[es] xyz"  # no phrase match
    assert V.mock_translate("hello", "klingon") == "[klingon] hello"  # unknown lang
