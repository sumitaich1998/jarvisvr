"""Pydantic v2 models for the JarvisVR envelope and every v1 payload.

The JSON Schemas in ``shared-protocol/schema`` are the source of truth; these
models mirror them for ergonomic construction/parsing. Payload models use
``extra="allow"`` so unknown keys round-trip (PROTOCOL.md §2: receivers ignore
unknown payload keys). The :class:`Envelope` uses ``extra="ignore"`` so decoding
is lenient; strict envelope checks live in :func:`jarvis_protocol.validate`.
"""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from .catalog import MessageType
from .version import PROTOCOL_VERSION

# ---- Enumerations (mirrors of the JSON Schema enums) ------------------------

Anchor = Literal["world", "head", "hand_left", "hand_right", "surface"]
Interaction = Literal["tap", "grab", "release", "drag", "slider", "toggle", "resize", "dwell"]
ThinkingStage = Literal["planning", "tool_call", "rendering", "done", "perceiving", "looking"]
Arrangement = Literal["arc", "grid", "stack", "free"]
Hand = Literal["left", "right"]

# v1.1 perception enums
Camera = Literal["rgb_left", "rgb_right", "rgb_center"]
VisionFormat = Literal["jpeg", "png", "rgb24"]
VisionTransport = Literal["inline", "binary"]
PerceptionStream = Literal["vision", "ambient_audio", "gaze", "scene_objects"]
PerceptionAction = Literal["start", "stop", "once", "set"]
GazeSource = Literal["eyes", "head"]
Speaker = Literal["user", "other", "unknown"]
Thermal = Literal["nominal", "fair", "serious", "critical"]


class _Payload(BaseModel):
    """Base for all payloads: extra keys are preserved (forward-compatible)."""

    model_config = ConfigDict(extra="allow")


# ---- Envelope --------------------------------------------------------------


class Envelope(BaseModel):
    """The v1 wire envelope. ``payload`` is kept as a plain dict for fidelity."""

    model_config = ConfigDict(extra="ignore")

    v: str = Field(default=PROTOCOL_VERSION)
    id: str
    type: str
    ts: int
    session: Optional[str] = None
    reply_to: Optional[str] = None
    payload: Dict[str, Any] = Field(default_factory=dict)


# ---- Handshake -------------------------------------------------------------


class Capabilities(_Payload):
    passthrough: Optional[bool] = None
    hand_tracking: Optional[bool] = None
    controllers: Optional[bool] = None
    mic: Optional[bool] = None
    speaker: Optional[bool] = None
    scene_understanding: Optional[bool] = None
    # v1.1 perception capabilities
    camera_passthrough: Optional[bool] = None
    ambient_audio: Optional[bool] = None
    eye_tracking: Optional[bool] = None
    on_device_vision: Optional[bool] = None
    depth: Optional[bool] = None


class ClientHello(_Payload):
    device: str
    app_version: Optional[str] = None
    protocol_version: str = PROTOCOL_VERSION
    capabilities: Optional[Capabilities] = None
    locale: Optional[str] = None


class AgentInfo(_Payload):
    name: Optional[str] = None
    model: Optional[str] = None


class VoiceInfo(_Payload):
    tts: Optional[bool] = None
    wake_word: Optional[str] = None


class ServerHelloAck(_Payload):
    session: str
    protocol_version: str = PROTOCOL_VERSION
    agent: Optional[AgentInfo] = None
    tools: Optional[List[str]] = None
    voice: Optional[VoiceInfo] = None


# ---- Text I/O (user.* + agent.transcript) ----------------------------------


class TextInput(_Payload):
    text: str
    confidence: Optional[float] = None
    attach_perception: Optional[bool] = None  # v1.1


# ---- Agent status / speech -------------------------------------------------


class AgentThinking(_Payload):
    stage: ThinkingStage
    label: Optional[str] = None
    tool: Optional[str] = None
    # v1.2 §9: attribute a step to a specific agent in the team.
    agent_id: Optional[str] = None
    role: Optional[str] = None
    skill: Optional[str] = None


class AgentSpeech(_Payload):
    text: str
    final: Optional[bool] = None
    emotion: Optional[str] = None


# ---- Holograms -------------------------------------------------------------


class Transform(_Payload):
    anchor: Optional[Anchor] = None
    position: Optional[List[float]] = None
    rotation: Optional[List[float]] = None
    scale: Optional[List[float]] = None
    billboard: Optional[bool] = None


class HoloObject(_Payload):
    object_id: str
    widget_type: str
    transform: Transform
    props: Dict[str, Any] = Field(default_factory=dict)
    interactable: Optional[bool] = None
    interactions: Optional[List[Interaction]] = None
    ttl_ms: Optional[int] = None


class HoloUpdate(_Payload):
    object_id: str
    transform: Optional[Transform] = None
    props: Optional[Dict[str, Any]] = None


class HoloDestroy(_Payload):
    object_id: str
    fade_ms: Optional[int] = None


class HoloLayout(_Payload):
    arrangement: Arrangement
    anchor: Optional[Anchor] = None
    objects: List[str]
    spacing: Optional[float] = None


# ---- Interaction + scene ---------------------------------------------------


class ClientInteraction(_Payload):
    object_id: str
    widget_type: Optional[str] = None
    action: Interaction
    element: Optional[str] = None
    value: Optional[Dict[str, Any]] = None
    hand: Optional[Hand] = None


class Pose(_Payload):
    position: Optional[List[float]] = None
    rotation: Optional[List[float]] = None


class Surface(_Payload):
    id: Optional[str] = None
    type: Optional[str] = None
    center: Optional[List[float]] = None
    normal: Optional[List[float]] = None


class SceneAnchor(_Payload):
    id: Optional[str] = None
    position: Optional[List[float]] = None
    rotation: Optional[List[float]] = None


class ClientScene(_Payload):
    head: Optional[Pose] = None
    surfaces: Optional[List[Surface]] = None
    anchors: Optional[List[SceneAnchor]] = None


# ---- Perception (v1.1) -----------------------------------------------------


class Intrinsics(_Payload):
    fx: Optional[float] = None
    fy: Optional[float] = None
    cx: Optional[float] = None
    cy: Optional[float] = None


class VisionFrame(_Payload):
    frame_id: str
    camera: Camera
    format: VisionFormat
    width: Optional[int] = None
    height: Optional[int] = None
    quality: Optional[int] = None
    transport: Optional[VisionTransport] = None
    data: Optional[str] = None
    seq: Optional[int] = None
    ts_capture: Optional[int] = None
    pose: Optional[Pose] = None
    intrinsics: Optional[Intrinsics] = None


class AudioEvent(_Payload):
    label: str
    confidence: Optional[float] = None
    ts: Optional[int] = None
    loudness_db: Optional[float] = None


class SoundLabel(_Payload):
    label: str
    confidence: Optional[float] = None


class AudioScene(_Payload):
    ambient_transcript: Optional[str] = None
    speaker: Optional[Speaker] = None
    sounds: Optional[List[SoundLabel]] = None
    loudness_db: Optional[float] = None
    window_ms: Optional[int] = None


class Gaze(_Payload):
    source: Optional[GazeSource] = None
    origin: List[float]
    direction: List[float]
    hit_object_id: Optional[str] = None
    hit_point: Optional[List[float]] = None
    dwell_ms: Optional[int] = None


class SceneObject(_Payload):
    label: str
    confidence: Optional[float] = None
    bbox: Optional[List[float]] = None
    position: Optional[List[float]] = None
    anchor: Optional[Anchor] = None


class SceneObjects(_Payload):
    objects: List[SceneObject]
    frame_id: Optional[str] = None


class VisionStreamState(_Payload):
    active: bool
    fps: Optional[float] = None
    resolution: Optional[str] = None
    camera: Optional[Camera] = None


class StreamState(_Payload):
    active: bool


class PerceptionState(_Payload):
    vision: Optional[VisionStreamState] = None
    ambient_audio: Optional[StreamState] = None
    gaze: Optional[StreamState] = None
    thermal: Optional[Thermal] = None
    battery: Optional[float] = None


class PerceptionRequest(_Payload):
    stream: PerceptionStream
    action: PerceptionAction
    fps: Optional[float] = None
    max_resolution: Optional[str] = None
    quality: Optional[int] = None
    duration_ms: Optional[int] = None
    reason: Optional[str] = None


class Annotation(_Payload):
    label: str
    object_id: Optional[str] = None
    position: Optional[List[float]] = None
    anchor: Optional[Anchor] = None


class AgentObservation(_Payload):
    text: str
    final: Optional[bool] = None
    annotations: Optional[List[Annotation]] = None


# ---- Settings (v1.1 §5.15) -------------------------------------------------


class ClientSettingsGet(_Payload):
    """``client.settings_get`` — read current settings + provider catalog."""

    section: Optional[Literal["llm", "all"]] = None


class LlmSettingsUpdate(_Payload):
    """The ``llm`` block of ``client.settings_update``. ``api_key`` is inbound-only."""

    provider: Optional[str] = None
    model: Optional[str] = None
    base_url: Optional[str] = None
    api_key: Optional[str] = None  # sensitive: never appears in server.settings


class ClientSettingsUpdate(_Payload):
    llm: Optional[LlmSettingsUpdate] = None


class ProviderCapabilities(_Payload):
    tools: Optional[bool] = None
    vision: Optional[bool] = None


class ProviderEntry(_Payload):
    """One entry in ``server.settings.llm.providers`` — never carries a key."""

    id: str
    name: str
    default_model: str
    models: Optional[List[str]] = None
    needs_key: bool
    needs_base_url: bool
    key_set: bool
    capabilities: Optional[ProviderCapabilities] = None


class CurrentLlm(_Payload):
    """The active LLM config — ``key_set`` boolean only, never the key."""

    provider: str
    model: str
    base_url: Optional[str] = None
    key_set: bool


class LlmSettings(_Payload):
    current: CurrentLlm
    providers: List[ProviderEntry]


class ServerSettings(_Payload):
    """``server.settings`` — current config + catalog. NEVER contains an api_key."""

    llm: LlmSettings


# ---- Multi-agent orchestration (v1.2 §9) -----------------------------------

AgentState = Literal[
    "queued", "planning", "working", "delegating", "waiting", "done", "failed"
]


class OrchestrationAgent(_Payload):
    """An agent node in an ``orchestration.plan``."""

    agent_id: str
    role: str
    name: Optional[str] = None
    parent: Optional[str] = None  # null for the L0 orchestrator
    level: int = 0
    subtask: Optional[str] = None
    skills: Optional[List[str]] = None


class OrchestrationPlan(_Payload):
    plan_id: str
    goal: str
    agents: List[OrchestrationAgent] = Field(default_factory=list)
    edges: Optional[List[Dict[str, str]]] = None  # {"from": .., "to": ..}


class OrchestrationAgentStatus(_Payload):
    plan_id: str
    agent_id: str
    role: str
    parent: Optional[str] = None
    level: Optional[int] = None
    state: AgentState
    skill: Optional[str] = None
    label: Optional[str] = None
    progress: Optional[float] = None


class OrchestrationHandoff(_Payload):
    plan_id: str
    from_agent: str
    to_agent: str
    to_role: str
    level: Optional[int] = None
    subtask: Optional[str] = None
    reason: Optional[str] = None


# ---- Tracing & in-headset authoring (v1.3 §10) -----------------------------

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
    allowed_tools: Optional[List[str]] = None
    license: Optional[str] = None
    compatibility: Optional[str] = None


class ClientAuthorAgent(_Payload):
    op: Literal["create", "update", "delete"]
    role: str
    name: Optional[str] = None
    persona: Optional[str] = None
    tools: Optional[List[str]] = None
    skills: Optional[List[str]] = None


class TraceEvent(_Payload):
    plan_id: str
    seq: int
    ts: int
    agent_id: str
    role: str
    parent: Optional[str] = None
    level: Optional[int] = None
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
    level: Optional[int] = None


class ServerTrace(_Payload):
    plan_id: str
    goal: Optional[str] = None
    agents: List[TraceAgent] = Field(default_factory=list)
    entries: List[TraceEvent] = Field(default_factory=list)


class SkillInfo(_Payload):
    name: str
    description: Optional[str] = None
    source: Optional[str] = None


class MemoryRecentItem(_Payload):
    ts: int
    text: str


class MemoryInfo(_Payload):
    summary: Optional[str] = None
    items: Optional[int] = None
    recent: List[MemoryRecentItem] = Field(default_factory=list)


class ServerAgentInfo(_Payload):
    role: str
    name: str
    source: Optional[str] = None
    persona: Optional[str] = None
    tools: List[str] = Field(default_factory=list)
    skills: List[SkillInfo] = Field(default_factory=list)
    memory: Optional[MemoryInfo] = None


class AuthoringAgent(_Payload):
    role: str
    name: str
    source: Optional[str] = None
    skills: List[str] = Field(default_factory=list)
    tools: List[str] = Field(default_factory=list)


class AuthoringSkill(_Payload):
    name: str
    agent: Optional[str] = None
    category: Optional[str] = None
    source: Optional[str] = None
    description: Optional[str] = None


class ServerAuthoring(_Payload):
    agents: List[AuthoringAgent] = Field(default_factory=list)
    skills: List[AuthoringSkill] = Field(default_factory=list)
    categories: List[str] = Field(default_factory=list)
    tools: List[str] = Field(default_factory=list)


# ---- Misc ------------------------------------------------------------------


class ProtocolError(_Payload):
    """Shared by ``server.error`` and ``client.error``."""

    code: str
    message: str
    fatal: Optional[bool] = None


class ClientBye(_Payload):
    reason: Optional[str] = None


class ClientBargeIn(_Payload):
    """``client.barge_in`` (v1.1) — user spoke over Jarvis; cancel the turn."""

    reason: Optional[str] = None


class Heartbeat(_Payload):
    """``client.heartbeat`` / ``server.heartbeat`` — empty payload."""


class Ack(_Payload):
    """``client.ack`` — empty payload (correlation via envelope.reply_to)."""


#: Maps a message ``type`` to the pydantic model for its ``payload``.
PAYLOAD_MODELS: Dict[str, type[_Payload]] = {
    MessageType.CLIENT_HELLO: ClientHello,
    MessageType.CLIENT_BYE: ClientBye,
    MessageType.CLIENT_HEARTBEAT: Heartbeat,
    MessageType.USER_TEXT: TextInput,
    MessageType.USER_VOICE_TRANSCRIPT: TextInput,
    MessageType.USER_VOICE_PARTIAL: TextInput,
    MessageType.CLIENT_INTERACTION: ClientInteraction,
    MessageType.CLIENT_SCENE: ClientScene,
    MessageType.CLIENT_ACK: Ack,
    MessageType.CLIENT_ERROR: ProtocolError,
    MessageType.CLIENT_BARGE_IN: ClientBargeIn,
    MessageType.SERVER_HELLO_ACK: ServerHelloAck,
    MessageType.SERVER_HEARTBEAT: Heartbeat,
    MessageType.AGENT_THINKING: AgentThinking,
    MessageType.AGENT_SPEECH: AgentSpeech,
    MessageType.AGENT_TRANSCRIPT: TextInput,
    MessageType.HOLO_SPAWN: HoloObject,
    MessageType.HOLO_UPDATE: HoloUpdate,
    MessageType.HOLO_DESTROY: HoloDestroy,
    MessageType.HOLO_LAYOUT: HoloLayout,
    MessageType.SERVER_ERROR: ProtocolError,
    # v1.1 perception
    MessageType.PERCEPTION_VISION_FRAME: VisionFrame,
    MessageType.PERCEPTION_AUDIO_EVENT: AudioEvent,
    MessageType.PERCEPTION_AUDIO_SCENE: AudioScene,
    MessageType.PERCEPTION_GAZE: Gaze,
    MessageType.PERCEPTION_SCENE_OBJECTS: SceneObjects,
    MessageType.PERCEPTION_STATE: PerceptionState,
    MessageType.PERCEPTION_REQUEST: PerceptionRequest,
    MessageType.AGENT_OBSERVATION: AgentObservation,
    # v1.1 §5.15 settings
    MessageType.CLIENT_SETTINGS_GET: ClientSettingsGet,
    MessageType.CLIENT_SETTINGS_UPDATE: ClientSettingsUpdate,
    MessageType.SERVER_SETTINGS: ServerSettings,
    # v1.2 §9 orchestration
    MessageType.ORCHESTRATION_PLAN: OrchestrationPlan,
    MessageType.ORCHESTRATION_AGENT_STATUS: OrchestrationAgentStatus,
    MessageType.ORCHESTRATION_HANDOFF: OrchestrationHandoff,
    # v1.3 §10 tracing + authoring
    MessageType.CLIENT_TRACE_SUBSCRIBE: ClientTraceSubscribe,
    MessageType.CLIENT_TRACE_GET: ClientTraceGet,
    MessageType.CLIENT_AGENT_INSPECT: ClientAgentInspect,
    MessageType.CLIENT_AUTHOR_LIST: ClientAuthorList,
    MessageType.CLIENT_AUTHOR_SKILL: ClientAuthorSkill,
    MessageType.CLIENT_AUTHOR_AGENT: ClientAuthorAgent,
    MessageType.ORCHESTRATION_TRACE_EVENT: TraceEvent,
    MessageType.SERVER_TRACE: ServerTrace,
    MessageType.SERVER_AGENT_INFO: ServerAgentInfo,
    MessageType.SERVER_AUTHORING: ServerAuthoring,
}

__all__ = [
    "Anchor",
    "Interaction",
    "ThinkingStage",
    "Arrangement",
    "Hand",
    "Envelope",
    "Capabilities",
    "ClientHello",
    "AgentInfo",
    "VoiceInfo",
    "ServerHelloAck",
    "TextInput",
    "AgentThinking",
    "AgentSpeech",
    "Transform",
    "HoloObject",
    "HoloUpdate",
    "HoloDestroy",
    "HoloLayout",
    "ClientInteraction",
    "Pose",
    "Surface",
    "SceneAnchor",
    "ClientScene",
    "ProtocolError",
    "ClientBye",
    "ClientBargeIn",
    "Heartbeat",
    "Ack",
    # v1.1 perception enums
    "Camera",
    "VisionFormat",
    "VisionTransport",
    "PerceptionStream",
    "PerceptionAction",
    "GazeSource",
    "Speaker",
    "Thermal",
    # v1.1 perception models
    "Intrinsics",
    "VisionFrame",
    "AudioEvent",
    "SoundLabel",
    "AudioScene",
    "Gaze",
    "SceneObject",
    "SceneObjects",
    "VisionStreamState",
    "StreamState",
    "PerceptionState",
    "PerceptionRequest",
    "Annotation",
    "AgentObservation",
    # v1.1 settings (§5.15)
    "ClientSettingsGet",
    "LlmSettingsUpdate",
    "ClientSettingsUpdate",
    "ProviderCapabilities",
    "ProviderEntry",
    "CurrentLlm",
    "LlmSettings",
    "ServerSettings",
    # v1.2 orchestration (§9)
    "AgentState",
    "OrchestrationAgent",
    "OrchestrationPlan",
    "OrchestrationAgentStatus",
    "OrchestrationHandoff",
    # v1.3 tracing + authoring (§10)
    "TraceKind",
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
    "PAYLOAD_MODELS",
]
