/** TypeScript types for the JarvisVR wire protocol (v1). Mirrors the JSON Schemas. */

export type Anchor = "world" | "head" | "hand_left" | "hand_right" | "surface";
export type InteractionKind =
  | "tap"
  | "grab"
  | "release"
  | "drag"
  | "slider"
  | "toggle"
  | "resize"
  | "dwell";
export type ThinkingStage =
  | "planning"
  | "tool_call"
  | "rendering"
  | "done"
  | "perceiving"
  | "looking";
export type Arrangement = "arc" | "grid" | "stack" | "free";
export type Hand = "left" | "right";

// v1.1 perception enums
export type Camera = "rgb_left" | "rgb_right" | "rgb_center";
export type VisionFormat = "jpeg" | "png" | "rgb24";
export type VisionTransport = "inline" | "binary";
export type PerceptionStream = "vision" | "ambient_audio" | "gaze" | "scene_objects";
export type PerceptionAction = "start" | "stop" | "once" | "set";
export type GazeSource = "eyes" | "head";
export type Speaker = "user" | "other" | "unknown";
export type Thermal = "nominal" | "fair" | "serious" | "critical";

export type Vec3 = [number, number, number];
export type Quat = [number, number, number, number];
/** 2D image bounding box [x, y, width, height] in pixels. */
export type BBox = [number, number, number, number];
export type Json = Record<string, unknown>;

/** The v1 wire envelope (PROTOCOL.md §2). */
export interface Envelope<P = Json> {
  v: string;
  id: string;
  type: string;
  ts: number;
  session?: string;
  reply_to?: string;
  payload: P;
}

// ---- Handshake -------------------------------------------------------------

export interface Capabilities {
  passthrough?: boolean;
  hand_tracking?: boolean;
  controllers?: boolean;
  mic?: boolean;
  speaker?: boolean;
  scene_understanding?: boolean;
  // v1.1 perception capabilities
  camera_passthrough?: boolean;
  ambient_audio?: boolean;
  eye_tracking?: boolean;
  on_device_vision?: boolean;
  depth?: boolean;
}

export interface ClientHello {
  device: string;
  app_version?: string;
  protocol_version: string;
  capabilities?: Capabilities;
  locale?: string;
}

export interface AgentInfo {
  name?: string;
  model?: string;
}

export interface VoiceInfo {
  tts?: boolean;
  wake_word?: string;
}

export interface ServerHelloAck {
  session: string;
  protocol_version: string;
  agent?: AgentInfo;
  tools?: string[];
  voice?: VoiceInfo;
}

// ---- Text I/O (user.* + agent.transcript) ----------------------------------

export interface TextInput {
  text: string;
  confidence?: number;
  /** v1.1: include current sight/sound buffer in the turn (default true while vision active). */
  attach_perception?: boolean;
}

// ---- Agent status / speech -------------------------------------------------

export interface AgentThinking {
  stage: ThinkingStage;
  label?: string;
  tool?: string;
  // v1.2 §9: attribute a step to a specific agent in the team.
  agent_id?: string;
  role?: string;
  skill?: string;
}

export interface AgentSpeech {
  text: string;
  final?: boolean;
  emotion?: string;
}

// ---- Holograms -------------------------------------------------------------

export interface Transform {
  anchor?: Anchor;
  position?: Vec3;
  rotation?: Quat;
  scale?: Vec3;
  billboard?: boolean;
}

export interface HoloObject {
  object_id: string;
  widget_type: string;
  transform: Transform;
  props?: Json;
  interactable?: boolean;
  interactions?: InteractionKind[];
  ttl_ms?: number;
}

export interface HoloUpdate {
  object_id: string;
  transform?: Transform;
  props?: Json;
}

export interface HoloDestroy {
  object_id: string;
  fade_ms?: number;
}

export interface HoloLayout {
  arrangement: Arrangement;
  anchor?: Anchor;
  objects: string[];
  spacing?: number;
}

// ---- Interaction + scene ---------------------------------------------------

export interface ClientInteraction {
  object_id: string;
  widget_type?: string;
  action: InteractionKind;
  element?: string;
  value?: Json;
  hand?: Hand;
}

export interface Pose {
  position?: Vec3;
  rotation?: Quat;
}

export interface Surface {
  id?: string;
  type?: string;
  center?: Vec3;
  normal?: Vec3;
}

export interface SceneAnchor {
  id?: string;
  position?: Vec3;
  rotation?: Quat;
}

export interface ClientScene {
  head?: Pose;
  surfaces?: Surface[];
  anchors?: SceneAnchor[];
}

// ---- Misc ------------------------------------------------------------------

export interface ProtocolErrorPayload {
  code: string;
  message: string;
  fatal?: boolean;
}

export interface ClientBye {
  reason?: string;
}

/** client.barge_in payload (PROTOCOL.md §5.14, v1.1) — cancel the in-flight turn. */
export interface ClientBargeIn {
  reason?: string;
}

export type Heartbeat = Record<string, never>;
export type Ack = Record<string, never>;

// ---- Perception (v1.1) -----------------------------------------------------

export interface Intrinsics {
  fx?: number;
  fy?: number;
  cx?: number;
  cy?: number;
}

export interface VisionFrame {
  frame_id: string;
  camera: Camera;
  format: VisionFormat;
  width?: number;
  height?: number;
  quality?: number;
  transport?: VisionTransport;
  /** Base64 image bytes; present iff transport=inline. */
  data?: string;
  seq?: number;
  ts_capture?: number;
  pose?: Pose;
  intrinsics?: Intrinsics;
}

export interface AudioEvent {
  label: string;
  confidence?: number;
  ts?: number;
  loudness_db?: number;
}

export interface SoundLabel {
  label: string;
  confidence?: number;
}

export interface AudioScene {
  ambient_transcript?: string;
  speaker?: Speaker;
  sounds?: SoundLabel[];
  loudness_db?: number;
  window_ms?: number;
}

export interface Gaze {
  source?: GazeSource;
  origin: Vec3;
  direction: Vec3;
  hit_object_id?: string | null;
  hit_point?: Vec3;
  dwell_ms?: number;
}

export interface SceneObject {
  label: string;
  confidence?: number;
  bbox?: BBox;
  position?: Vec3;
  anchor?: Anchor;
}

export interface SceneObjects {
  frame_id?: string;
  objects: SceneObject[];
}

export interface VisionStreamState {
  active: boolean;
  fps?: number;
  resolution?: string;
  camera?: Camera;
}

export interface StreamState {
  active: boolean;
}

export interface PerceptionState {
  vision?: VisionStreamState;
  ambient_audio?: StreamState;
  gaze?: StreamState;
  thermal?: Thermal;
  battery?: number;
}

export interface PerceptionRequest {
  stream: PerceptionStream;
  action: PerceptionAction;
  fps?: number;
  max_resolution?: string;
  quality?: number;
  duration_ms?: number;
  reason?: string;
}

export interface Annotation {
  label: string;
  object_id?: string;
  position?: Vec3;
  anchor?: Anchor;
}

export interface AgentObservation {
  text: string;
  final?: boolean;
  annotations?: Annotation[];
}

// ---- Settings (v1.1 §5.15) -------------------------------------------------

export interface ClientSettingsGet {
  section?: "llm" | "all";
}

/** The `llm` block of client.settings_update. `api_key` is inbound-only. */
export interface LlmSettingsUpdate {
  provider?: string;
  model?: string;
  base_url?: string | null;
  /** Sensitive: send only to set/replace; never echoed in server.settings. */
  api_key?: string;
}

export interface ClientSettingsUpdate {
  llm?: LlmSettingsUpdate;
}

export interface ProviderCapabilities {
  tools?: boolean;
  vision?: boolean;
}

/** A provider entry in server.settings — never carries a key (only key_set). */
export interface ProviderEntry {
  id: string;
  name: string;
  default_model: string;
  models?: string[];
  needs_key: boolean;
  needs_base_url: boolean;
  key_set: boolean;
  capabilities?: ProviderCapabilities;
}

export interface CurrentLlm {
  provider: string;
  model: string;
  base_url?: string | null;
  key_set: boolean;
}

export interface LlmSettings {
  current: CurrentLlm;
  providers: ProviderEntry[];
}

/** server.settings payload — current config + catalog. NEVER contains an api_key. */
export interface ServerSettings {
  llm: LlmSettings;
}

// ---- Multi-agent orchestration (v1.2 §9) -----------------------------------

export type AgentState =
  | "queued"
  | "planning"
  | "working"
  | "delegating"
  | "waiting"
  | "done"
  | "failed";

export interface OrchestrationAgent {
  agent_id: string;
  role: string;
  name?: string;
  /** Parent agent_id; null for the L0 orchestrator. */
  parent?: string | null;
  level: number;
  subtask?: string;
  skills?: string[];
}

export interface OrchestrationEdge {
  from: string;
  to: string;
}

export interface OrchestrationPlan {
  plan_id: string;
  goal: string;
  agents: OrchestrationAgent[];
  edges?: OrchestrationEdge[];
}

export interface OrchestrationAgentStatus {
  plan_id: string;
  agent_id: string;
  role: string;
  parent?: string | null;
  level?: number;
  state: AgentState;
  skill?: string;
  label?: string;
  progress?: number;
}

export interface OrchestrationHandoff {
  plan_id: string;
  from_agent: string;
  to_agent: string;
  to_role: string;
  level?: number;
  subtask?: string;
  reason?: string;
}

// ---- Tracing & in-headset authoring (v1.3 §10) -----------------------------

export type TraceKind =
  | "memory_read"
  | "memory_write"
  | "skill_activated"
  | "tool_call"
  | "tool_result"
  | "observation"
  | "delegated"
  | "speech"
  | "error";

export interface ClientTraceSubscribe {
  enabled: boolean;
}

export interface ClientTraceGet {
  plan_id?: string;
}

export interface ClientAgentInspect {
  role?: string;
  agent_id?: string;
}

export type ClientAuthorList = Record<string, never>;

export interface ClientAuthorSkill {
  op: "create" | "update" | "delete";
  name: string;
  category?: string;
  agent?: string;
  description?: string;
  body?: string;
  allowed_tools?: string[];
  license?: string;
  compatibility?: string;
}

export interface ClientAuthorAgent {
  op: "create" | "update" | "delete";
  role: string;
  name?: string;
  persona?: string;
  tools?: string[];
  skills?: string[];
}

export interface TraceEvent {
  plan_id: string;
  seq: number;
  ts: number;
  agent_id: string;
  role: string;
  parent?: string | null;
  level?: number;
  kind: TraceKind;
  label: string;
  skill?: string;
  tool?: string;
  detail?: string;
  duration_ms?: number;
}

export interface TraceAgentRef {
  agent_id: string;
  role: string;
  parent?: string | null;
  level?: number;
}

export interface ServerTrace {
  plan_id: string;
  goal?: string;
  agents?: TraceAgentRef[];
  entries: TraceEvent[];
}

export interface SkillInfo {
  name: string;
  description?: string;
  source?: "builtin" | "user";
}

export interface MemoryRecentItem {
  ts: number;
  text: string;
}

export interface MemoryInfo {
  summary?: string;
  items?: number;
  recent?: MemoryRecentItem[];
}

export interface ServerAgentInfo {
  role: string;
  name: string;
  source?: "builtin" | "user";
  persona?: string;
  tools?: string[];
  skills?: SkillInfo[];
  memory?: MemoryInfo;
}

export interface AuthoringAgent {
  role: string;
  name: string;
  source?: "builtin" | "user";
  skills?: string[];
  tools?: string[];
}

export interface AuthoringSkill {
  name: string;
  agent?: string;
  category?: string;
  source?: "builtin" | "user";
  description?: string;
}

export interface ServerAuthoring {
  agents: AuthoringAgent[];
  skills: AuthoringSkill[];
  categories?: string[];
  tools?: string[];
}

/** Map of message type -> payload type, for typed helpers. */
export interface PayloadByType {
  "client.hello": ClientHello;
  "client.bye": ClientBye;
  "client.heartbeat": Heartbeat;
  "user.text": TextInput;
  "user.voice_transcript": TextInput;
  "user.voice_partial": TextInput;
  "client.interaction": ClientInteraction;
  "client.scene": ClientScene;
  "client.ack": Ack;
  "client.error": ProtocolErrorPayload;
  "client.barge_in": ClientBargeIn;
  "server.hello_ack": ServerHelloAck;
  "server.heartbeat": Heartbeat;
  "agent.thinking": AgentThinking;
  "agent.speech": AgentSpeech;
  "agent.transcript": TextInput;
  "holo.spawn": HoloObject;
  "holo.update": HoloUpdate;
  "holo.destroy": HoloDestroy;
  "holo.layout": HoloLayout;
  "server.error": ProtocolErrorPayload;
  // v1.1 perception
  "perception.vision_frame": VisionFrame;
  "perception.audio_event": AudioEvent;
  "perception.audio_scene": AudioScene;
  "perception.gaze": Gaze;
  "perception.scene_objects": SceneObjects;
  "perception.state": PerceptionState;
  "perception.request": PerceptionRequest;
  "agent.observation": AgentObservation;
  // v1.1 §5.15 settings
  "client.settings_get": ClientSettingsGet;
  "client.settings_update": ClientSettingsUpdate;
  "server.settings": ServerSettings;
  // v1.2 §9 orchestration
  "orchestration.plan": OrchestrationPlan;
  "orchestration.agent_status": OrchestrationAgentStatus;
  "orchestration.handoff": OrchestrationHandoff;
  // v1.3 §10 tracing + authoring
  "client.trace_subscribe": ClientTraceSubscribe;
  "client.trace_get": ClientTraceGet;
  "client.agent_inspect": ClientAgentInspect;
  "client.author_list": ClientAuthorList;
  "client.author_skill": ClientAuthorSkill;
  "client.author_agent": ClientAuthorAgent;
  "orchestration.trace_event": TraceEvent;
  "server.trace": ServerTrace;
  "server.agent_info": ServerAgentInfo;
  "server.authoring": ServerAuthoring;
}
