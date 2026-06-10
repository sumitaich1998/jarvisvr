"""JarvisVR wire-protocol models and helpers (v1).

This is a *self-contained* implementation of the envelope + payload schemas
defined in ``docs/PROTOCOL.md``. The ``shared-protocol/`` package will later
publish canonical Python bindings generated from the JSON Schema; when that
lands, reconcile this module against it (the field names/shapes here mirror the
protocol doc exactly, so the swap should be mechanical).

Design notes
------------
* ``Envelope`` keeps ``payload`` as a free-form dict. Typed payload models below
  are used to *build* and *validate* specific message types, but the transport
  layer never rejects a message just because its payload has extra keys
  (forward-compatibility, per the protocol's conformance checklist).
* All payload models ignore unknown keys (``extra="ignore"``).
* Helpers assign a uuid-v4 ``id`` and epoch-millisecond ``ts`` automatically.
"""

from __future__ import annotations

import time
import uuid
from typing import Annotated, Any, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PROTOCOL_VERSION = "1.3.0"  # 1.3 adds Tracing & In-headset Authoring (§10); 1.0-1.2 clients still OK

# Anchor enum (ARCHITECTURE.md §5 / PROTOCOL.md §5.6).
Anchor = Literal["world", "head", "hand_left", "hand_right", "surface"]

# Fixed-length vector aliases (meters; Unity right-handed, Y up).
Vec3 = Annotated[list[float], Field(min_length=3, max_length=3)]
# Quaternion x, y, z, w.
Quat = Annotated[list[float], Field(min_length=4, max_length=4)]


class MsgType:
    """Canonical ``type`` string constants from the message catalog (§4)."""

    # client -> server
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
    CLIENT_BARGE_IN = "client.barge_in"  # v1.1 (§5.14): user spoke over Jarvis; cancel turn
    CLIENT_SETTINGS_GET = "client.settings_get"  # v1.1 (§5.15): read settings + catalog
    CLIENT_SETTINGS_UPDATE = "client.settings_update"  # v1.1 (§5.15): change provider/model/key
    # v1.3 tracing + authoring (§10), client -> server
    CLIENT_TRACE_SUBSCRIBE = "client.trace_subscribe"
    CLIENT_TRACE_GET = "client.trace_get"
    CLIENT_AGENT_INSPECT = "client.agent_inspect"
    CLIENT_AUTHOR_LIST = "client.author_list"
    CLIENT_AUTHOR_SKILL = "client.author_skill"
    CLIENT_AUTHOR_AGENT = "client.author_agent"

    # client -> server (v1.1 perception, §8.3)
    PERCEPTION_VISION_FRAME = "perception.vision_frame"
    PERCEPTION_AUDIO_EVENT = "perception.audio_event"
    PERCEPTION_AUDIO_SCENE = "perception.audio_scene"
    PERCEPTION_GAZE = "perception.gaze"
    PERCEPTION_SCENE_OBJECTS = "perception.scene_objects"
    PERCEPTION_STATE = "perception.state"

    # server -> client
    SERVER_HELLO_ACK = "server.hello_ack"
    SERVER_HEARTBEAT = "server.heartbeat"
    AGENT_THINKING = "agent.thinking"
    AGENT_SPEECH = "agent.speech"
    AGENT_TRANSCRIPT = "agent.transcript"
    AGENT_OBSERVATION = "agent.observation"  # v1.1, §8.4
    HOLO_SPAWN = "holo.spawn"
    HOLO_UPDATE = "holo.update"
    HOLO_DESTROY = "holo.destroy"
    HOLO_LAYOUT = "holo.layout"
    PERCEPTION_REQUEST = "perception.request"  # v1.1, §8.4 (pull-based control)
    SERVER_SETTINGS = "server.settings"  # v1.1, §5.15 (settings + catalog; no keys)
    # v1.2 multi-agent orchestration (§9)
    ORCHESTRATION_PLAN = "orchestration.plan"
    ORCHESTRATION_AGENT_STATUS = "orchestration.agent_status"
    ORCHESTRATION_HANDOFF = "orchestration.handoff"
    # v1.3 tracing + authoring (§10), server -> client
    ORCHESTRATION_TRACE_EVENT = "orchestration.trace_event"
    SERVER_TRACE = "server.trace"
    SERVER_AGENT_INFO = "server.agent_info"
    SERVER_AUTHORING = "server.authoring"
    SERVER_ERROR = "server.error"


# Suggested error codes (§5.13 / §5.15).
class ErrorCode:
    BAD_ENVELOPE = "bad_envelope"
    UNSUPPORTED_VERSION = "unsupported_version"
    UNKNOWN_TYPE = "unknown_type"
    UNKNOWN_WIDGET = "unknown_widget"
    INVALID_PROPS = "invalid_props"
    TOOL_FAILED = "tool_failed"
    INTERNAL = "internal"
    # v1.1 settings (§5.15)
    INVALID_SETTINGS = "invalid_settings"
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    INVALID_KEY = "invalid_key"
    # v1.3 authoring (§10.2)
    INVALID_SKILL = "invalid_skill"
    INVALID_AGENT = "invalid_agent"
    NAME_CONFLICT = "name_conflict"
    FORBIDDEN = "forbidden"
    NOT_FOUND = "not_found"


# ---------------------------------------------------------------------------
# Small utilities
# ---------------------------------------------------------------------------


def now_ms() -> int:
    """Current time as epoch milliseconds (sender clock)."""
    return int(time.time() * 1000)


def new_id() -> str:
    """A fresh uuid-v4 string."""
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# Envelope
# ---------------------------------------------------------------------------


class Envelope(BaseModel):
    """The v1 message envelope (§2): ``v, id, type, ts, session, payload``."""

    model_config = ConfigDict(extra="ignore")

    v: str = PROTOCOL_VERSION
    id: str = Field(default_factory=new_id)
    type: str
    ts: int = Field(default_factory=now_ms)
    # Assigned by the server in hello_ack; omitted on the very first client.hello.
    session: Optional[str] = None
    # Optional correlation id (e.g. client.ack -> the render command it acks).
    reply_to: Optional[str] = None
    payload: dict[str, Any] = Field(default_factory=dict)

    def to_json(self) -> str:
        """Serialize to a compact JSON text frame, omitting null envelope keys."""
        return self.model_dump_json(exclude_none=True)


# ---------------------------------------------------------------------------
# Payload models (§5). All ignore unknown keys for forward-compatibility.
# ---------------------------------------------------------------------------


class _Payload(BaseModel):
    model_config = ConfigDict(extra="ignore")


class Capabilities(_Payload):
    passthrough: bool = True
    hand_tracking: bool = True
    controllers: bool = True
    mic: bool = True
    speaker: bool = True
    scene_understanding: bool = True
    # v1.1 perception capabilities (§8.1); default off (client advertises true).
    camera_passthrough: bool = False
    ambient_audio: bool = False
    eye_tracking: bool = False
    on_device_vision: bool = False
    depth: bool = False


class ClientHello(_Payload):
    device: str = "quest3"
    app_version: str = "0.0.0"
    protocol_version: str = PROTOCOL_VERSION
    capabilities: Capabilities = Field(default_factory=Capabilities)
    locale: str = "en-US"


class AgentInfo(_Payload):
    name: str = "Jarvis"
    model: str = "mock"


class VoiceInfo(_Payload):
    tts: bool = True
    wake_word: str = "jarvis"


class PerceptionSupport(_Payload):
    """Advertised in ``server.hello_ack`` so the client knows we speak v1.1."""

    vision: bool = True
    ambient_audio: bool = True
    gaze: bool = True
    scene_objects: bool = True
    annotations: bool = True


class HelloAck(_Payload):
    session: str
    protocol_version: str = PROTOCOL_VERSION
    agent: AgentInfo = Field(default_factory=AgentInfo)
    tools: list[str] = Field(default_factory=list)
    voice: VoiceInfo = Field(default_factory=VoiceInfo)
    # v1.1: advertise multimodal perception support (additive, forward-compatible).
    perception: PerceptionSupport = Field(default_factory=PerceptionSupport)
    widgets: list[str] = Field(default_factory=list)
    # v1.1 (§5.15): runtime settings (provider/model/API key) are configurable.
    settings: bool = True
    # v1.2 (§9): multi-agent orchestration + the specialist role roster.
    orchestration: bool = True
    agents: list[str] = Field(default_factory=list)
    # v1.3 (§10): per-agent tracing + in-headset authoring.
    tracing: bool = True
    authoring: bool = True


class UserText(_Payload):
    """``user.text`` / ``user.voice_transcript`` / ``user.voice_partial``."""

    text: str
    confidence: float = 1.0
    # v1.1 (§8.3): consider current sight/sound for this turn. None = use default.
    attach_perception: Optional[bool] = None


class AgentThinking(_Payload):
    stage: Literal[
        "planning", "tool_call", "rendering", "done", "perceiving", "looking"
    ] = "planning"
    label: Optional[str] = None
    tool: Optional[str] = None
    # v1.2 (§9): attribute a step to a specific agent in the team.
    agent_id: Optional[str] = None
    role: Optional[str] = None
    skill: Optional[str] = None


class AgentSpeech(_Payload):
    text: str
    final: bool = True
    emotion: str = "neutral"


class AgentTranscript(_Payload):
    text: str
    confidence: float = 1.0


class Transform(_Payload):
    """A hologram's spatial transform (§5.6). Meters + quaternion + anchor."""

    anchor: Anchor = "world"
    position: Vec3 = Field(default_factory=lambda: [0.0, 0.0, 0.0])
    rotation: Quat = Field(default_factory=lambda: [0.0, 0.0, 0.0, 1.0])
    scale: Vec3 = Field(default_factory=lambda: [1.0, 1.0, 1.0])
    billboard: bool = False


class HoloObject(_Payload):
    """The Holographic Object (§5.6); payload for ``holo.spawn``."""

    object_id: str = Field(default_factory=new_id)
    widget_type: str
    transform: Transform = Field(default_factory=Transform)
    props: dict[str, Any] = Field(default_factory=dict)
    interactable: bool = True
    interactions: list[str] = Field(default_factory=list)
    ttl_ms: int = 0


class HoloUpdate(_Payload):
    """``holo.update`` — partial patch; omit unchanged keys (§5.8)."""

    object_id: str
    transform: Optional[dict[str, Any]] = None
    props: Optional[dict[str, Any]] = None


class HoloDestroy(_Payload):
    object_id: str
    fade_ms: int = 300


class HoloLayout(_Payload):
    arrangement: Literal["arc", "grid", "stack", "free"] = "arc"
    anchor: Anchor = "head"
    objects: list[str] = Field(default_factory=list)
    spacing: float = 0.25


class ClientInteraction(_Payload):
    object_id: str
    widget_type: Optional[str] = None
    action: Literal[
        "tap", "grab", "release", "drag", "slider", "toggle", "resize", "dwell"
    ] = "tap"
    element: Optional[str] = None
    value: dict[str, Any] = Field(default_factory=dict)
    hand: Optional[str] = None


class ErrorPayload(_Payload):
    code: str = ErrorCode.INTERNAL
    message: str = ""
    fatal: bool = False


class ClientBargeIn(_Payload):
    """``client.barge_in`` (§5.14) — user interrupted; cancel the active turn."""

    reason: Optional[str] = None


# ---------------------------------------------------------------------------
# v1.1 Settings payloads (§5.15) — inbound. server.settings is built as a plain
# dict by settings_service so it can NEVER accidentally carry an api_key.
# ---------------------------------------------------------------------------


class ClientSettingsGet(_Payload):
    section: Optional[str] = None  # "llm" | "all" | None


class LLMSettingsUpdate(_Payload):
    """The ``llm`` block of ``client.settings_update``. ``api_key`` is inbound-only."""

    provider: Optional[str] = None
    model: Optional[str] = None
    base_url: Optional[str] = None
    api_key: Optional[str] = None


class ClientSettingsUpdate(_Payload):
    llm: Optional[LLMSettingsUpdate] = None


# ---------------------------------------------------------------------------
# v1.2 Multi-Agent Orchestration payloads (§9) — server -> client, additive.
# ---------------------------------------------------------------------------


class OrchestrationAgent(_Payload):
    """An agent node in an ``orchestration.plan``."""

    agent_id: str
    role: str
    name: Optional[str] = None
    parent: Optional[str] = None  # null for the L0 orchestrator
    level: int = 0
    subtask: Optional[str] = None
    skills: Optional[list[str]] = None


class OrchestrationPlan(_Payload):
    plan_id: str
    goal: str
    agents: list[OrchestrationAgent] = Field(default_factory=list)
    edges: list[dict[str, str]] = Field(default_factory=list)  # {"from": .., "to": ..}


class OrchestrationAgentStatus(_Payload):
    plan_id: str
    agent_id: str
    role: str
    parent: Optional[str] = None
    level: int = 1
    state: Literal[
        "queued", "planning", "working", "delegating", "waiting", "done", "failed"
    ] = "queued"
    skill: Optional[str] = None
    label: Optional[str] = None
    progress: Optional[float] = None


class OrchestrationHandoff(_Payload):
    plan_id: str
    from_agent: str
    to_agent: str
    to_role: str
    level: int = 2
    subtask: Optional[str] = None
    reason: Optional[str] = None


# ---------------------------------------------------------------------------
# v1.3 Tracing & In-Headset Authoring payloads (§10) — additive, optional.
# ---------------------------------------------------------------------------

TraceKind = Literal[
    "memory_read", "memory_write", "skill_activated", "tool_call", "tool_result",
    "observation", "delegated", "speech", "error",
]


class ClientTraceSubscribe(_Payload):
    enabled: bool = True


class ClientTraceGet(_Payload):
    plan_id: Optional[str] = None


class ClientAgentInspect(_Payload):
    role: Optional[str] = None
    agent_id: Optional[str] = None


class ClientAuthorList(_Payload):
    pass


class ClientAuthorSkill(_Payload):
    op: Literal["create", "update", "delete"]
    name: str
    category: Optional[str] = None
    agent: Optional[str] = None
    description: Optional[str] = None
    body: Optional[str] = None
    allowed_tools: Optional[list[str]] = None
    license: Optional[str] = None
    compatibility: Optional[str] = None


class ClientAuthorAgent(_Payload):
    op: Literal["create", "update", "delete"]
    role: str
    name: Optional[str] = None
    persona: Optional[str] = None
    tools: Optional[list[str]] = None
    skills: Optional[list[str]] = None


class TraceEvent(_Payload):
    plan_id: str
    seq: int
    ts: int
    agent_id: str
    role: str
    parent: Optional[str] = None
    level: int = 1
    kind: TraceKind
    label: str
    skill: Optional[str] = None
    tool: Optional[str] = None
    detail: Optional[str] = None
    duration_ms: Optional[int] = None


class TraceAgent(_Payload):
    agent_id: str
    role: str
    parent: Optional[str] = None
    level: int = 1


class ServerTrace(_Payload):
    plan_id: str
    goal: str
    agents: list[TraceAgent] = Field(default_factory=list)
    entries: list[TraceEvent] = Field(default_factory=list)


class SkillInfo(_Payload):
    name: str
    description: Optional[str] = None
    source: str = "builtin"


class MemoryRecentItem(_Payload):
    ts: int
    text: str


class MemoryInfo(_Payload):
    summary: str = ""
    items: int = 0
    recent: list[MemoryRecentItem] = Field(default_factory=list)


class ServerAgentInfo(_Payload):
    role: str
    name: str
    source: str = "builtin"
    persona: str = ""
    tools: list[str] = Field(default_factory=list)
    skills: list[SkillInfo] = Field(default_factory=list)
    memory: MemoryInfo = Field(default_factory=MemoryInfo)


class AuthoringAgent(_Payload):
    role: str
    name: str
    source: str = "builtin"
    skills: list[str] = Field(default_factory=list)
    tools: list[str] = Field(default_factory=list)


class AuthoringSkill(_Payload):
    name: str
    agent: Optional[str] = None
    category: Optional[str] = None
    source: str = "builtin"
    description: Optional[str] = None


class ServerAuthoring(_Payload):
    agents: list[AuthoringAgent] = Field(default_factory=list)
    skills: list[AuthoringSkill] = Field(default_factory=list)
    categories: list[str] = Field(default_factory=list)
    tools: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# v1.1 Multimodal Perception payloads (§8.4)
# ---------------------------------------------------------------------------


class Pose(_Payload):
    position: Vec3 = Field(default_factory=lambda: [0.0, 1.6, 0.0])
    rotation: Quat = Field(default_factory=lambda: [0.0, 0.0, 0.0, 1.0])


class VisionFrame(_Payload):
    """A passthrough RGB camera frame + camera pose (§8.4)."""

    frame_id: str = Field(default_factory=new_id)
    camera: Literal["rgb_left", "rgb_right", "rgb_center"] = "rgb_center"
    format: Literal["jpeg", "png", "rgb24"] = "jpeg"
    width: int = 0
    height: int = 0
    quality: int = 70
    transport: Literal["inline", "binary"] = "inline"
    data: Optional[str] = None  # base64, present iff transport == inline
    seq: int = 0
    ts_capture: int = Field(default_factory=now_ms)
    pose: Optional[Pose] = None
    intrinsics: Optional[dict[str, Any]] = None


class AudioEvent(_Payload):
    label: str
    confidence: float = 1.0
    ts: int = Field(default_factory=now_ms)
    loudness_db: Optional[float] = None


class AudioScene(_Payload):
    ambient_transcript: str = ""
    speaker: Literal["user", "other", "unknown"] = "unknown"
    sounds: list[dict[str, Any]] = Field(default_factory=list)
    loudness_db: Optional[float] = None
    window_ms: int = 4000


class Gaze(_Payload):
    source: Literal["eyes", "head"] = "head"
    origin: Vec3 = Field(default_factory=lambda: [0.0, 1.6, 0.0])
    direction: Vec3 = Field(default_factory=lambda: [0.0, 0.0, 1.0])
    hit_object_id: Optional[str] = None
    hit_point: Optional[Vec3] = None
    dwell_ms: int = 0


class SceneObject(_Payload):
    label: str
    confidence: float = 1.0
    bbox: Optional[list[float]] = None  # [x, y, w, h] in image pixels
    position: Optional[Vec3] = None
    anchor: Anchor = "world"


class SceneObjects(_Payload):
    frame_id: Optional[str] = None
    objects: list[SceneObject] = Field(default_factory=list)


class PerceptionState(_Payload):
    vision: dict[str, Any] = Field(default_factory=dict)
    ambient_audio: dict[str, Any] = Field(default_factory=dict)
    gaze: dict[str, Any] = Field(default_factory=dict)
    thermal: Literal["nominal", "fair", "serious", "critical"] = "nominal"
    battery: Optional[float] = None


class PerceptionRequest(_Payload):
    """Server -> client: pull-based perception stream control (§8.4)."""

    stream: Literal["vision", "ambient_audio", "gaze", "scene_objects"] = "vision"
    action: Literal["start", "stop", "once", "set"] = "once"
    fps: Optional[int] = None
    max_resolution: Optional[str] = None
    quality: Optional[int] = None
    duration_ms: int = 0
    reason: Optional[str] = None


class Annotation(_Payload):
    """A spatial annotation carried in ``agent.observation`` (§8.4)."""

    label: str
    object_id: Optional[str] = None
    position: Vec3 = Field(default_factory=lambda: [0.0, 1.2, 0.8])
    anchor: Anchor = "world"


class AgentObservation(_Payload):
    """What Jarvis perceives, with optional spatial annotations (§8.4)."""

    text: str
    final: bool = True
    annotations: list[Annotation] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Builders / parsers
# ---------------------------------------------------------------------------

PayloadLike = Union[BaseModel, dict[str, Any], None]


def _payload_to_dict(payload: PayloadLike) -> dict[str, Any]:
    if payload is None:
        return {}
    if isinstance(payload, BaseModel):
        return payload.model_dump(exclude_none=True)
    return dict(payload)


def make(
    type: str,
    payload: PayloadLike = None,
    *,
    session: Optional[str] = None,
    reply_to: Optional[str] = None,
) -> Envelope:
    """Build an outbound :class:`Envelope` with a fresh id + epoch-ms ts."""
    return Envelope(
        type=type,
        session=session,
        reply_to=reply_to,
        payload=_payload_to_dict(payload),
    )


class BadEnvelope(ValueError):
    """Raised when an inbound frame is not a valid v1 envelope."""


def parse_inbound(raw: str | bytes) -> Envelope:
    """Parse + validate an inbound JSON text frame into an :class:`Envelope`.

    Raises :class:`BadEnvelope` if the frame is not valid JSON or is missing the
    required ``type`` field. ``id``/``ts`` are tolerated when absent (filled with
    defaults) so we interoperate with slightly lenient clients.
    """
    try:
        env = Envelope.model_validate_json(raw)
    except Exception as exc:  # noqa: BLE001 - normalize to a single error type
        raise BadEnvelope(str(exc)) from exc
    return env


def is_compatible_version(v: str) -> bool:
    """True if the message's major protocol version matches ours."""
    try:
        return v.split(".")[0] == PROTOCOL_VERSION.split(".")[0]
    except Exception:  # noqa: BLE001
        return False


__all__ = [
    "PROTOCOL_VERSION",
    "Anchor",
    "Vec3",
    "Quat",
    "MsgType",
    "ErrorCode",
    "now_ms",
    "new_id",
    "Envelope",
    "Capabilities",
    "ClientHello",
    "AgentInfo",
    "VoiceInfo",
    "PerceptionSupport",
    "HelloAck",
    "UserText",
    "AgentThinking",
    "AgentSpeech",
    "AgentTranscript",
    "Transform",
    "HoloObject",
    "HoloUpdate",
    "HoloDestroy",
    "HoloLayout",
    "ClientInteraction",
    "ErrorPayload",
    "ClientBargeIn",
    "ClientSettingsGet",
    "LLMSettingsUpdate",
    "ClientSettingsUpdate",
    "OrchestrationAgent",
    "OrchestrationPlan",
    "OrchestrationAgentStatus",
    "OrchestrationHandoff",
    "ClientTraceSubscribe",
    "ClientTraceGet",
    "ClientAgentInspect",
    "ClientAuthorList",
    "ClientAuthorSkill",
    "ClientAuthorAgent",
    "TraceEvent",
    "TraceAgent",
    "ServerTrace",
    "SkillInfo",
    "MemoryRecentItem",
    "MemoryInfo",
    "ServerAgentInfo",
    "AuthoringAgent",
    "AuthoringSkill",
    "ServerAuthoring",
    "Pose",
    "VisionFrame",
    "AudioEvent",
    "AudioScene",
    "Gaze",
    "SceneObject",
    "SceneObjects",
    "PerceptionState",
    "PerceptionRequest",
    "Annotation",
    "AgentObservation",
    "make",
    "parse_inbound",
    "BadEnvelope",
    "is_compatible_version",
]
