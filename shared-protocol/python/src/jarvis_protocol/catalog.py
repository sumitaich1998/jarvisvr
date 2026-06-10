"""Canonical message-type catalog and the type -> JSON Schema file mapping.

This module is import-cycle-free on purpose: both ``models`` and ``schemas``
depend on it.
"""

from __future__ import annotations


class MessageType:
    """String constants for every message ``type`` in the v1 catalog."""

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
    CLIENT_BARGE_IN = "client.barge_in"  # v1.1: user spoke over Jarvis; cancel turn
    CLIENT_SETTINGS_GET = "client.settings_get"  # v1.1 §5.15: read settings + catalog
    CLIENT_SETTINGS_UPDATE = "client.settings_update"  # v1.1 §5.15: change provider/model/key

    # client -> server (v1.1 perception)
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
    HOLO_SPAWN = "holo.spawn"
    HOLO_UPDATE = "holo.update"
    HOLO_DESTROY = "holo.destroy"
    HOLO_LAYOUT = "holo.layout"
    SERVER_ERROR = "server.error"

    # server -> client (v1.1 perception)
    PERCEPTION_REQUEST = "perception.request"
    AGENT_OBSERVATION = "agent.observation"

    # server -> client (v1.1 §5.15 settings)
    SERVER_SETTINGS = "server.settings"  # current settings + provider catalog (no keys)

    # server -> client (v1.2 §9 multi-agent orchestration)
    ORCHESTRATION_PLAN = "orchestration.plan"
    ORCHESTRATION_AGENT_STATUS = "orchestration.agent_status"
    ORCHESTRATION_HANDOFF = "orchestration.handoff"

    # v1.3 §10 tracing + authoring (client -> server)
    CLIENT_TRACE_SUBSCRIBE = "client.trace_subscribe"
    CLIENT_TRACE_GET = "client.trace_get"
    CLIENT_AGENT_INSPECT = "client.agent_inspect"
    CLIENT_AUTHOR_LIST = "client.author_list"
    CLIENT_AUTHOR_SKILL = "client.author_skill"
    CLIENT_AUTHOR_AGENT = "client.author_agent"
    # v1.3 §10 (server -> client)
    ORCHESTRATION_TRACE_EVENT = "orchestration.trace_event"
    SERVER_TRACE = "server.trace"
    SERVER_AGENT_INFO = "server.agent_info"
    SERVER_AUTHORING = "server.authoring"


#: Maps a message ``type`` to the JSON Schema file that validates its ``payload``.
TYPE_TO_SCHEMA: dict[str, str] = {
    MessageType.CLIENT_HELLO: "client.hello.schema.json",
    MessageType.CLIENT_BYE: "client.bye.schema.json",
    MessageType.CLIENT_HEARTBEAT: "heartbeat.schema.json",
    MessageType.USER_TEXT: "user.text.schema.json",
    MessageType.USER_VOICE_TRANSCRIPT: "user.voice_transcript.schema.json",
    MessageType.USER_VOICE_PARTIAL: "user.voice_partial.schema.json",
    MessageType.CLIENT_INTERACTION: "client.interaction.schema.json",
    MessageType.CLIENT_SCENE: "client.scene.schema.json",
    MessageType.CLIENT_ACK: "client.ack.schema.json",
    MessageType.CLIENT_ERROR: "error.schema.json",
    MessageType.CLIENT_BARGE_IN: "client.barge_in.schema.json",
    MessageType.SERVER_HELLO_ACK: "server.hello_ack.schema.json",
    MessageType.SERVER_HEARTBEAT: "heartbeat.schema.json",
    MessageType.AGENT_THINKING: "agent.thinking.schema.json",
    MessageType.AGENT_SPEECH: "agent.speech.schema.json",
    MessageType.AGENT_TRANSCRIPT: "agent.transcript.schema.json",
    MessageType.HOLO_SPAWN: "holo.spawn.schema.json",
    MessageType.HOLO_UPDATE: "holo.update.schema.json",
    MessageType.HOLO_DESTROY: "holo.destroy.schema.json",
    MessageType.HOLO_LAYOUT: "holo.layout.schema.json",
    MessageType.SERVER_ERROR: "error.schema.json",
    # v1.1 perception
    MessageType.PERCEPTION_VISION_FRAME: "perception.vision_frame.schema.json",
    MessageType.PERCEPTION_AUDIO_EVENT: "perception.audio_event.schema.json",
    MessageType.PERCEPTION_AUDIO_SCENE: "perception.audio_scene.schema.json",
    MessageType.PERCEPTION_GAZE: "perception.gaze.schema.json",
    MessageType.PERCEPTION_SCENE_OBJECTS: "perception.scene_objects.schema.json",
    MessageType.PERCEPTION_STATE: "perception.state.schema.json",
    MessageType.PERCEPTION_REQUEST: "perception.request.schema.json",
    MessageType.AGENT_OBSERVATION: "agent.observation.schema.json",
    # v1.1 §5.15 settings
    MessageType.CLIENT_SETTINGS_GET: "client.settings_get.schema.json",
    MessageType.CLIENT_SETTINGS_UPDATE: "client.settings_update.schema.json",
    MessageType.SERVER_SETTINGS: "server.settings.schema.json",
    # v1.2 §9 orchestration
    MessageType.ORCHESTRATION_PLAN: "orchestration.plan.schema.json",
    MessageType.ORCHESTRATION_AGENT_STATUS: "orchestration.agent_status.schema.json",
    MessageType.ORCHESTRATION_HANDOFF: "orchestration.handoff.schema.json",
    # v1.3 §10 tracing + authoring
    MessageType.CLIENT_TRACE_SUBSCRIBE: "client.trace_subscribe.schema.json",
    MessageType.CLIENT_TRACE_GET: "client.trace_get.schema.json",
    MessageType.CLIENT_AGENT_INSPECT: "client.agent_inspect.schema.json",
    MessageType.CLIENT_AUTHOR_LIST: "client.author_list.schema.json",
    MessageType.CLIENT_AUTHOR_SKILL: "client.author_skill.schema.json",
    MessageType.CLIENT_AUTHOR_AGENT: "client.author_agent.schema.json",
    MessageType.ORCHESTRATION_TRACE_EVENT: "orchestration.trace_event.schema.json",
    MessageType.SERVER_TRACE: "server.trace.schema.json",
    MessageType.SERVER_AGENT_INFO: "server.agent_info.schema.json",
    MessageType.SERVER_AUTHORING: "server.authoring.schema.json",
}

#: Every message ``type`` known to this binding.
KNOWN_TYPES = frozenset(TYPE_TO_SCHEMA)

__all__ = ["MessageType", "TYPE_TO_SCHEMA", "KNOWN_TYPES"]
