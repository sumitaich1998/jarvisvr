/** Canonical message-type catalog and the type -> JSON Schema file mapping. */

export const MessageType = {
  // client -> server
  CLIENT_HELLO: "client.hello",
  CLIENT_BYE: "client.bye",
  CLIENT_HEARTBEAT: "client.heartbeat",
  USER_TEXT: "user.text",
  USER_VOICE_TRANSCRIPT: "user.voice_transcript",
  USER_VOICE_PARTIAL: "user.voice_partial",
  CLIENT_INTERACTION: "client.interaction",
  CLIENT_SCENE: "client.scene",
  CLIENT_ACK: "client.ack",
  CLIENT_ERROR: "client.error",
  CLIENT_BARGE_IN: "client.barge_in",
  CLIENT_SETTINGS_GET: "client.settings_get",
  CLIENT_SETTINGS_UPDATE: "client.settings_update",
  // client -> server (v1.1 perception)
  PERCEPTION_VISION_FRAME: "perception.vision_frame",
  PERCEPTION_AUDIO_EVENT: "perception.audio_event",
  PERCEPTION_AUDIO_SCENE: "perception.audio_scene",
  PERCEPTION_GAZE: "perception.gaze",
  PERCEPTION_SCENE_OBJECTS: "perception.scene_objects",
  PERCEPTION_STATE: "perception.state",
  // server -> client
  SERVER_HELLO_ACK: "server.hello_ack",
  SERVER_HEARTBEAT: "server.heartbeat",
  AGENT_THINKING: "agent.thinking",
  AGENT_SPEECH: "agent.speech",
  AGENT_TRANSCRIPT: "agent.transcript",
  HOLO_SPAWN: "holo.spawn",
  HOLO_UPDATE: "holo.update",
  HOLO_DESTROY: "holo.destroy",
  HOLO_LAYOUT: "holo.layout",
  SERVER_ERROR: "server.error",
  // server -> client (v1.1 perception)
  PERCEPTION_REQUEST: "perception.request",
  AGENT_OBSERVATION: "agent.observation",
  // server -> client (v1.1 §5.15 settings)
  SERVER_SETTINGS: "server.settings",
  // server -> client (v1.2 §9 multi-agent orchestration)
  ORCHESTRATION_PLAN: "orchestration.plan",
  ORCHESTRATION_AGENT_STATUS: "orchestration.agent_status",
  ORCHESTRATION_HANDOFF: "orchestration.handoff",
  // v1.3 §10 tracing + authoring (client -> server)
  CLIENT_TRACE_SUBSCRIBE: "client.trace_subscribe",
  CLIENT_TRACE_GET: "client.trace_get",
  CLIENT_AGENT_INSPECT: "client.agent_inspect",
  CLIENT_AUTHOR_LIST: "client.author_list",
  CLIENT_AUTHOR_SKILL: "client.author_skill",
  CLIENT_AUTHOR_AGENT: "client.author_agent",
  // v1.3 §10 (server -> client)
  ORCHESTRATION_TRACE_EVENT: "orchestration.trace_event",
  SERVER_TRACE: "server.trace",
  SERVER_AGENT_INFO: "server.agent_info",
  SERVER_AUTHORING: "server.authoring",
} as const;

export type MessageTypeName = (typeof MessageType)[keyof typeof MessageType];

/** Maps a message `type` to the JSON Schema file that validates its `payload`. */
export const TYPE_TO_SCHEMA: Record<string, string> = {
  "client.hello": "client.hello.schema.json",
  "client.bye": "client.bye.schema.json",
  "client.heartbeat": "heartbeat.schema.json",
  "user.text": "user.text.schema.json",
  "user.voice_transcript": "user.voice_transcript.schema.json",
  "user.voice_partial": "user.voice_partial.schema.json",
  "client.interaction": "client.interaction.schema.json",
  "client.scene": "client.scene.schema.json",
  "client.ack": "client.ack.schema.json",
  "client.error": "error.schema.json",
  "client.barge_in": "client.barge_in.schema.json",
  "server.hello_ack": "server.hello_ack.schema.json",
  "server.heartbeat": "heartbeat.schema.json",
  "agent.thinking": "agent.thinking.schema.json",
  "agent.speech": "agent.speech.schema.json",
  "agent.transcript": "agent.transcript.schema.json",
  "holo.spawn": "holo.spawn.schema.json",
  "holo.update": "holo.update.schema.json",
  "holo.destroy": "holo.destroy.schema.json",
  "holo.layout": "holo.layout.schema.json",
  "server.error": "error.schema.json",
  // v1.1 perception
  "perception.vision_frame": "perception.vision_frame.schema.json",
  "perception.audio_event": "perception.audio_event.schema.json",
  "perception.audio_scene": "perception.audio_scene.schema.json",
  "perception.gaze": "perception.gaze.schema.json",
  "perception.scene_objects": "perception.scene_objects.schema.json",
  "perception.state": "perception.state.schema.json",
  "perception.request": "perception.request.schema.json",
  "agent.observation": "agent.observation.schema.json",
  // v1.1 §5.15 settings
  "client.settings_get": "client.settings_get.schema.json",
  "client.settings_update": "client.settings_update.schema.json",
  "server.settings": "server.settings.schema.json",
  // v1.2 §9 orchestration
  "orchestration.plan": "orchestration.plan.schema.json",
  "orchestration.agent_status": "orchestration.agent_status.schema.json",
  "orchestration.handoff": "orchestration.handoff.schema.json",
  // v1.3 §10 tracing + authoring
  "client.trace_subscribe": "client.trace_subscribe.schema.json",
  "client.trace_get": "client.trace_get.schema.json",
  "client.agent_inspect": "client.agent_inspect.schema.json",
  "client.author_list": "client.author_list.schema.json",
  "client.author_skill": "client.author_skill.schema.json",
  "client.author_agent": "client.author_agent.schema.json",
  "orchestration.trace_event": "orchestration.trace_event.schema.json",
  "server.trace": "server.trace.schema.json",
  "server.agent_info": "server.agent_info.schema.json",
  "server.authoring": "server.authoring.schema.json",
};

/** Every message `type` known to this binding. */
export const KNOWN_TYPES: ReadonlySet<string> = new Set(Object.keys(TYPE_TO_SCHEMA));
