"""Self-contained JarvisVR wire-protocol (v1.1) helpers.

Implements the envelope + the subset of message types the voice-service needs,
exactly per ``docs/PROTOCOL.md``. v1.1 adds **Multimodal Perception** (§8): the
voice-service emits ``perception.audio_scene`` / ``perception.audio_event`` and
handles inbound ``perception.request`` (ambient_audio) + ``agent.observation``.
These are intentionally dependency-free structs; ``shared-protocol/`` will ship
canonical Python bindings later and this module can be swapped for them without
touching the rest of the package.

Envelope::

    {"v","id","type","ts","session","payload"}  (+ optional "reply_to")
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

PROTOCOL_VERSION = "1.1.0"  # 1.1 adds Multimodal Perception (§8); 1.0 still supported


# --- Message type constants (docs/PROTOCOL.md §4) ---------------------------
# Client -> Server
CLIENT_HELLO = "client.hello"
CLIENT_BYE = "client.bye"
CLIENT_HEARTBEAT = "client.heartbeat"
USER_TEXT = "user.text"
USER_VOICE_TRANSCRIPT = "user.voice_transcript"
USER_VOICE_PARTIAL = "user.voice_partial"
CLIENT_INTERACTION = "client.interaction"
CLIENT_SCENE = "client.scene"
CLIENT_ACK = "client.ack"
CLIENT_ERROR = "client.error"

# Client -> Server (v1.1 perception). voice-service emits audio_* + state.
PERCEPTION_VISION_FRAME = "perception.vision_frame"
PERCEPTION_AUDIO_EVENT = "perception.audio_event"
PERCEPTION_AUDIO_SCENE = "perception.audio_scene"
PERCEPTION_GAZE = "perception.gaze"
PERCEPTION_SCENE_OBJECTS = "perception.scene_objects"
PERCEPTION_STATE = "perception.state"
# Voice-service extension: signals the user spoke over TTS (barge-in). Namespaced
# under client.* so v1.1 backends that don't know it simply ignore it.
CLIENT_BARGE_IN = "client.barge_in"

# Server -> Client
SERVER_HELLO_ACK = "server.hello_ack"
SERVER_HEARTBEAT = "server.heartbeat"
AGENT_THINKING = "agent.thinking"
AGENT_SPEECH = "agent.speech"
AGENT_TRANSCRIPT = "agent.transcript"
HOLO_SPAWN = "holo.spawn"
HOLO_UPDATE = "holo.update"
HOLO_DESTROY = "holo.destroy"
HOLO_LAYOUT = "holo.layout"
SERVER_ERROR = "server.error"

# Server -> Client (v1.1 perception)
PERCEPTION_REQUEST = "perception.request"   # start/stop/once a perception stream
AGENT_OBSERVATION = "agent.observation"     # what Jarvis perceives (spoken via TTS)

HEARTBEAT_INTERVAL_S = 5.0


def now_ms() -> int:
    """Epoch milliseconds (sender clock)."""
    return int(time.time() * 1000)


def new_id() -> str:
    """A fresh UUID-v4 string."""
    return str(uuid.uuid4())


class ProtocolError(ValueError):
    """Raised when a frame cannot be parsed as a v1 envelope."""

    def __init__(self, message: str, code: str = "bad_envelope") -> None:
        super().__init__(message)
        self.code = code


@dataclass
class Envelope:
    """A v1 protocol envelope."""

    type: str
    payload: Dict[str, Any] = field(default_factory=dict)
    v: str = PROTOCOL_VERSION
    id: str = field(default_factory=new_id)
    ts: int = field(default_factory=now_ms)
    session: Optional[str] = None
    reply_to: Optional[str] = None

    # --- construction ---
    @classmethod
    def build(
        cls,
        type: str,
        payload: Optional[Dict[str, Any]] = None,
        *,
        session: Optional[str] = None,
        reply_to: Optional[str] = None,
    ) -> "Envelope":
        return cls(
            type=type,
            payload=payload or {},
            session=session,
            reply_to=reply_to,
        )

    # --- (de)serialization ---
    def to_dict(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {
            "v": self.v,
            "id": self.id,
            "type": self.type,
            "ts": self.ts,
            "payload": self.payload,
        }
        # `session` is omitted on the very first hello (per spec); include when set.
        if self.session is not None:
            out["session"] = self.session
        if self.reply_to is not None:
            out["reply_to"] = self.reply_to
        return out

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), separators=(",", ":"), ensure_ascii=False)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Envelope":
        if not isinstance(data, dict):
            raise ProtocolError("envelope must be a JSON object")
        for key in ("v", "id", "type", "ts"):
            if key not in data:
                raise ProtocolError(f"missing required envelope key: {key!r}")
        payload = data.get("payload", {})
        if payload is None:
            payload = {}
        if not isinstance(payload, dict):
            raise ProtocolError("payload must be an object")
        return cls(
            type=str(data["type"]),
            payload=payload,
            v=str(data["v"]),
            id=str(data["id"]),
            ts=int(data["ts"]),
            session=data.get("session"),
            reply_to=data.get("reply_to"),
        )

    @classmethod
    def from_json(cls, raw: str | bytes) -> "Envelope":
        try:
            data = json.loads(raw)
        except (ValueError, TypeError) as exc:
            raise ProtocolError(f"invalid JSON frame: {exc}") from exc
        return cls.from_dict(data)

    # --- convenience ---
    @property
    def text(self) -> Optional[str]:
        """Shortcut for the common ``payload.text`` field."""
        val = self.payload.get("text")
        return None if val is None else str(val)

    def is_version_compatible(self, version: str = PROTOCOL_VERSION) -> bool:
        """Major-version compatibility check (semver)."""
        try:
            return self.v.split(".")[0] == version.split(".")[0]
        except (AttributeError, IndexError):
            return False


# --- High-level builders the voice-service emits ----------------------------

def client_hello(
    *,
    mic: bool = True,
    speaker: bool = True,
    ambient_audio: bool = False,
    camera_passthrough: bool = False,
    eye_tracking: bool = False,
    on_device_vision: bool = False,
    depth: bool = False,
    device: str = "quest3",
    app_version: str = "0.1.0",
    locale: str = "en-US",
    extra_capabilities: Optional[Dict[str, Any]] = None,
) -> Envelope:
    """``client.hello`` advertising this front-end's capabilities.

    The voice-service advertises ``mic`` + ``speaker`` and, in v1.1,
    ``ambient_audio`` (continuous room listening). Vision/gaze/depth capabilities
    belong to the unity-client and default to ``False`` here.
    """
    capabilities: Dict[str, Any] = {
        "passthrough": False,
        "hand_tracking": False,
        "controllers": False,
        "mic": mic,
        "speaker": speaker,
        "scene_understanding": False,
        # v1.1 perception capabilities
        "camera_passthrough": camera_passthrough,
        "ambient_audio": ambient_audio,
        "eye_tracking": eye_tracking,
        "on_device_vision": on_device_vision,
        "depth": depth,
    }
    if extra_capabilities:
        capabilities.update(extra_capabilities)
    payload = {
        "device": device,
        "app_version": app_version,
        "protocol_version": PROTOCOL_VERSION,
        "capabilities": capabilities,
        "locale": locale,
    }
    return Envelope.build(CLIENT_HELLO, payload)


def client_heartbeat(session: Optional[str] = None) -> Envelope:
    return Envelope.build(CLIENT_HEARTBEAT, {}, session=session)


def client_bye(session: Optional[str] = None) -> Envelope:
    return Envelope.build(CLIENT_BYE, {}, session=session)


def voice_transcript(
    text: str, confidence: float = 1.0, session: Optional[str] = None
) -> Envelope:
    """Final STT result -> ``user.voice_transcript``."""
    return Envelope.build(
        USER_VOICE_TRANSCRIPT,
        {"text": text, "confidence": round(float(confidence), 4)},
        session=session,
    )


def voice_partial(
    text: str, confidence: float = 0.0, session: Optional[str] = None
) -> Envelope:
    """Interim/streaming STT result -> ``user.voice_partial``."""
    return Envelope.build(
        USER_VOICE_PARTIAL,
        {"text": text, "confidence": round(float(confidence), 4)},
        session=session,
    )


def client_error(
    code: str, message: str, fatal: bool = False, session: Optional[str] = None
) -> Envelope:
    return Envelope.build(
        CLIENT_ERROR,
        {"code": code, "message": message, "fatal": fatal},
        session=session,
    )


def client_barge_in(
    reason: str = "user_speech", session: Optional[str] = None
) -> Envelope:
    """Voice-service extension: notify the backend the user spoke over TTS so the
    agent can stop its current turn. Forward-compatible (ignored if unknown)."""
    return Envelope.build(CLIENT_BARGE_IN, {"reason": reason}, session=session)


# --- v1.1 perception builders (PROTOCOL.md §8.4) ----------------------------

def audio_scene(
    ambient_transcript: str = "",
    speaker: str = "unknown",
    sounds: Optional[List[Dict[str, Any]]] = None,
    loudness_db: float = -60.0,
    window_ms: int = 4000,
    session: Optional[str] = None,
) -> Envelope:
    """Ambient audio understanding -> ``perception.audio_scene``.

    ``speaker`` is ``user | other | unknown``; ``sounds`` is a list of
    ``{"label","confidence"}`` soundscape tags.
    """
    return Envelope.build(
        PERCEPTION_AUDIO_SCENE,
        {
            "ambient_transcript": ambient_transcript,
            "speaker": speaker,
            "sounds": sounds or [],
            "loudness_db": round(float(loudness_db), 1),
            "window_ms": int(window_ms),
        },
        session=session,
    )


def audio_event(
    label: str,
    confidence: float = 1.0,
    loudness_db: float = -30.0,
    ts: Optional[int] = None,
    session: Optional[str] = None,
) -> Envelope:
    """A detected ambient sound event -> ``perception.audio_event``."""
    env = Envelope.build(
        PERCEPTION_AUDIO_EVENT,
        {
            "label": label,
            "confidence": round(float(confidence), 4),
            "loudness_db": round(float(loudness_db), 1),
        },
        session=session,
    )
    # The §8.4 example carries `ts` inside the payload as well as the envelope.
    env.payload["ts"] = int(ts) if ts is not None else env.ts
    return env


def perception_state(
    ambient_audio_active: bool = False,
    vision_active: bool = False,
    gaze_active: bool = False,
    thermal: str = "nominal",
    battery: Optional[float] = None,
    session: Optional[str] = None,
) -> Envelope:
    """Which perception streams are currently active -> ``perception.state``.

    The voice-service owns the ``ambient_audio`` stream; vision/gaze are reported
    as inactive (owned by the unity-client).
    """
    payload: Dict[str, Any] = {
        "vision": {"active": vision_active},
        "ambient_audio": {"active": ambient_audio_active},
        "gaze": {"active": gaze_active},
        "thermal": thermal,
    }
    if battery is not None:
        payload["battery"] = battery
    return Envelope.build(PERCEPTION_STATE, payload, session=session)
