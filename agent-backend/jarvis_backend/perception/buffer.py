"""Per-session rolling perception buffer + /vision binary transport codec."""

from __future__ import annotations

import base64
import json
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Optional

from ..protocol import now_ms


# ---------------------------------------------------------------------------
# /vision binary transport (PROTOCOL §8.2):
#   [4-byte BE uint32 headerLen][headerLen bytes UTF-8 JSON header][image bytes]
# ---------------------------------------------------------------------------


def decode_binary_vision_frame(message: bytes) -> tuple[dict[str, Any], bytes]:
    if len(message) < 4:
        raise ValueError("vision frame too short for length prefix")
    header_len = int.from_bytes(message[:4], "big")
    end = 4 + header_len
    if end > len(message):
        raise ValueError("vision frame header length exceeds message size")
    header = json.loads(message[4:end].decode("utf-8"))
    image = message[end:]
    return header, image


def encode_binary_vision_frame(header: dict[str, Any], image: bytes) -> bytes:
    raw_header = json.dumps(header).encode("utf-8")
    return len(raw_header).to_bytes(4, "big") + raw_header + image


# ---------------------------------------------------------------------------
# Buffer
# ---------------------------------------------------------------------------


@dataclass
class FrameRecord:
    frame_id: str
    camera: str = "rgb_center"
    format: str = "jpeg"
    width: int = 0
    height: int = 0
    seq: int = 0
    ts_capture: int = 0
    transport: str = "inline"
    size_bytes: int = 0
    pose: Optional[dict[str, Any]] = None
    intrinsics: Optional[dict[str, Any]] = None
    # base64 image kept only for the most-recent few frames (for the LLM path).
    data_b64: Optional[str] = None

    def meta(self) -> dict[str, Any]:
        """Lightweight thumbnail/size metadata (no pixels)."""
        return {
            "frame_id": self.frame_id,
            "camera": self.camera,
            "format": self.format,
            "width": self.width,
            "height": self.height,
            "seq": self.seq,
            "size_bytes": self.size_bytes,
            "ts_capture": self.ts_capture,
            "transport": self.transport,
            "has_pixels": self.data_b64 is not None,
        }


class PerceptionBuffer:
    """Rolling, time-windowed store of recent sight/sound/gaze for one session."""

    def __init__(self, *, max_frames: int = 8, audio_window_ms: int = 20000):
        self.max_frames = max_frames
        self.audio_window_ms = audio_window_ms
        self.frames: deque[FrameRecord] = deque(maxlen=max_frames)
        self.audio_events: deque[dict[str, Any]] = deque(maxlen=32)
        self.audio_scenes: deque[dict[str, Any]] = deque(maxlen=16)
        self.latest_gaze: Optional[dict[str, Any]] = None
        self.scene_objects: list[dict[str, Any]] = []
        self.scene_objects_frame_id: Optional[str] = None
        self.scene_objects_ts: int = 0
        self.state: dict[str, Any] = {}
        self.vision_active: bool = False
        # Continuous "watch the room" mode (server keeps the camera streaming),
        # as opposed to a one-shot per-turn snapshot. Distinct from vision_active,
        # which merely reflects that frames have been received.
        self.watching: bool = False
        self.ambient_active: bool = False
        self.frames_seen: int = 0

    # -- ingest -------------------------------------------------------------

    def add_vision_frame(
        self, payload: dict[str, Any], raw: Optional[bytes] = None
    ) -> FrameRecord:
        data_b64 = payload.get("data")
        size = 0
        if raw is not None:
            size = len(raw)
            if data_b64 is None:
                data_b64 = base64.b64encode(raw).decode("ascii")
        elif isinstance(data_b64, str):
            # Estimate decoded size from base64 length without holding the bytes.
            size = (len(data_b64) * 3) // 4
        rec = FrameRecord(
            frame_id=payload.get("frame_id") or "",
            camera=payload.get("camera", "rgb_center"),
            format=payload.get("format", "jpeg"),
            width=int(payload.get("width", 0) or 0),
            height=int(payload.get("height", 0) or 0),
            seq=int(payload.get("seq", 0) or 0),
            ts_capture=int(payload.get("ts_capture", now_ms()) or now_ms()),
            transport=payload.get("transport", "inline"),
            size_bytes=size,
            pose=payload.get("pose"),
            intrinsics=payload.get("intrinsics"),
            data_b64=data_b64,
        )
        self.frames.append(rec)
        self.frames_seen += 1
        self.vision_active = True
        return rec

    def add_audio_event(self, payload: dict[str, Any]) -> None:
        evt = dict(payload)
        evt.setdefault("ts", now_ms())
        self.audio_events.append(evt)
        self.ambient_active = True

    def add_audio_scene(self, payload: dict[str, Any]) -> None:
        scene = dict(payload)
        scene.setdefault("ts", now_ms())
        self.audio_scenes.append(scene)
        self.ambient_active = True

    def set_gaze(self, payload: dict[str, Any]) -> None:
        gaze = dict(payload)
        gaze.setdefault("ts", now_ms())
        self.latest_gaze = gaze

    def set_scene_objects(self, payload: dict[str, Any]) -> None:
        objs = list(payload.get("objects", []) or [])
        self.scene_objects = objs
        self.scene_objects_frame_id = payload.get("frame_id")
        self.scene_objects_ts = now_ms()

    def set_state(self, payload: dict[str, Any]) -> None:
        self.state = dict(payload)
        vision = payload.get("vision") or {}
        if "active" in vision:
            self.vision_active = bool(vision.get("active"))
        ambient = payload.get("ambient_audio") or {}
        if "active" in ambient:
            self.ambient_active = bool(ambient.get("active"))

    # -- queries ------------------------------------------------------------

    def latest_frame(self) -> Optional[FrameRecord]:
        return self.frames[-1] if self.frames else None

    def has_vision(self) -> bool:
        return self.vision_active or bool(self.frames) or bool(self.scene_objects)

    def recent_sounds(self, window_ms: Optional[int] = None) -> list[dict[str, Any]]:
        window = window_ms if window_ms is not None else self.audio_window_ms
        cutoff = now_ms() - window
        out = [e for e in self.audio_events if e.get("ts", 0) >= cutoff]
        return out

    def latest_audio_event(self) -> Optional[dict[str, Any]]:
        return self.audio_events[-1] if self.audio_events else None

    def latest_audio_scene(self) -> Optional[dict[str, Any]]:
        return self.audio_scenes[-1] if self.audio_scenes else None

    def images_for_llm(self, max_images: int = 1) -> list[tuple[str, str]]:
        """Most-recent ``(base64, media_type)`` frames that still carry pixels."""
        out: list[tuple[str, str]] = []
        media = {"jpeg": "image/jpeg", "png": "image/png"}
        for rec in reversed(self.frames):
            if rec.data_b64:
                out.append((rec.data_b64, media.get(rec.format, "image/jpeg")))
            if len(out) >= max_images:
                break
        return out

    def current_context(self) -> dict[str, Any]:
        """A compact, textual-friendly snapshot for the agent + mock vision."""
        frame = self.latest_frame()
        return {
            "has_vision": self.has_vision(),
            "vision_active": self.vision_active,
            "ambient_active": self.ambient_active,
            "frame": frame.meta() if frame else None,
            "frame_count": self.frames_seen,
            "gaze": self.latest_gaze,
            "objects": list(self.scene_objects),
            "scene_objects_frame_id": self.scene_objects_frame_id,
            "sounds": self.recent_sounds(),
            "latest_sound": self.latest_audio_event(),
            "ambient": self.latest_audio_scene(),
            "state": self.state,
        }


__all__ = [
    "FrameRecord",
    "PerceptionBuffer",
    "decode_binary_vision_frame",
    "encode_binary_vision_frame",
]
