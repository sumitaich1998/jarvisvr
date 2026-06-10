using System.Collections.Generic;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;

namespace JarvisVR.Protocol
{
    // ---- Handshake ---------------------------------------------------------

    /// <summary>client.hello capability advertisement (PROTOCOL.md §5.1).</summary>
    public class Capabilities
    {
        [JsonProperty("passthrough", NullValueHandling = NullValueHandling.Ignore)] public bool? Passthrough { get; set; }
        [JsonProperty("hand_tracking", NullValueHandling = NullValueHandling.Ignore)] public bool? HandTracking { get; set; }
        [JsonProperty("controllers", NullValueHandling = NullValueHandling.Ignore)] public bool? Controllers { get; set; }
        [JsonProperty("mic", NullValueHandling = NullValueHandling.Ignore)] public bool? Mic { get; set; }
        [JsonProperty("speaker", NullValueHandling = NullValueHandling.Ignore)] public bool? Speaker { get; set; }
        [JsonProperty("scene_understanding", NullValueHandling = NullValueHandling.Ignore)] public bool? SceneUnderstanding { get; set; }
        // v1.1 perception capabilities
        [JsonProperty("camera_passthrough", NullValueHandling = NullValueHandling.Ignore)] public bool? CameraPassthrough { get; set; }
        [JsonProperty("ambient_audio", NullValueHandling = NullValueHandling.Ignore)] public bool? AmbientAudio { get; set; }
        [JsonProperty("eye_tracking", NullValueHandling = NullValueHandling.Ignore)] public bool? EyeTracking { get; set; }
        [JsonProperty("on_device_vision", NullValueHandling = NullValueHandling.Ignore)] public bool? OnDeviceVision { get; set; }
        [JsonProperty("depth", NullValueHandling = NullValueHandling.Ignore)] public bool? Depth { get; set; }
    }

    /// <summary>client.hello payload (PROTOCOL.md §5.1).</summary>
    public class ClientHello
    {
        [JsonProperty("device")] public string Device { get; set; }
        [JsonProperty("app_version", NullValueHandling = NullValueHandling.Ignore)] public string AppVersion { get; set; }
        [JsonProperty("protocol_version")] public string ProtocolVersion { get; set; } = Protocol.Version;
        [JsonProperty("capabilities", NullValueHandling = NullValueHandling.Ignore)] public Capabilities Capabilities { get; set; }
        [JsonProperty("locale", NullValueHandling = NullValueHandling.Ignore)] public string Locale { get; set; }
    }

    /// <summary>server.hello_ack agent descriptor.</summary>
    public class AgentInfo
    {
        [JsonProperty("name", NullValueHandling = NullValueHandling.Ignore)] public string Name { get; set; }
        [JsonProperty("model", NullValueHandling = NullValueHandling.Ignore)] public string Model { get; set; }
    }

    /// <summary>server.hello_ack voice descriptor.</summary>
    public class VoiceInfo
    {
        [JsonProperty("tts", NullValueHandling = NullValueHandling.Ignore)] public bool? Tts { get; set; }
        [JsonProperty("wake_word", NullValueHandling = NullValueHandling.Ignore)] public string WakeWord { get; set; }
    }

    /// <summary>server.hello_ack payload (PROTOCOL.md §5.2).</summary>
    public class ServerHelloAck
    {
        [JsonProperty("session")] public string Session { get; set; }
        [JsonProperty("protocol_version")] public string ProtocolVersion { get; set; } = Protocol.Version;
        [JsonProperty("agent", NullValueHandling = NullValueHandling.Ignore)] public AgentInfo Agent { get; set; }
        [JsonProperty("tools", NullValueHandling = NullValueHandling.Ignore)] public List<string> Tools { get; set; }
        [JsonProperty("voice", NullValueHandling = NullValueHandling.Ignore)] public VoiceInfo Voice { get; set; }
    }

    // ---- Text I/O (user.* + agent.transcript) ------------------------------

    /// <summary>Shape for user.text / user.voice_transcript / user.voice_partial / agent.transcript (§5.3).</summary>
    public class TextInput
    {
        [JsonProperty("text")] public string Text { get; set; }
        [JsonProperty("confidence", NullValueHandling = NullValueHandling.Ignore)] public float? Confidence { get; set; }
        [JsonProperty("attach_perception", NullValueHandling = NullValueHandling.Ignore)] public bool? AttachPerception { get; set; }  // v1.1
    }

    // ---- Agent status / speech --------------------------------------------

    /// <summary>agent.thinking payload (PROTOCOL.md §5.4).</summary>
    public class AgentThinking
    {
        [JsonProperty("stage")] public string Stage { get; set; }
        [JsonProperty("label", NullValueHandling = NullValueHandling.Ignore)] public string Label { get; set; }
        [JsonProperty("tool", NullValueHandling = NullValueHandling.Ignore)] public string Tool { get; set; }
        // v1.2 §9: attribute a step to a specific agent in the team.
        [JsonProperty("agent_id", NullValueHandling = NullValueHandling.Ignore)] public string AgentId { get; set; }
        [JsonProperty("role", NullValueHandling = NullValueHandling.Ignore)] public string Role { get; set; }
        [JsonProperty("skill", NullValueHandling = NullValueHandling.Ignore)] public string Skill { get; set; }
    }

    /// <summary>agent.speech payload (PROTOCOL.md §5.5).</summary>
    public class AgentSpeech
    {
        [JsonProperty("text")] public string Text { get; set; }
        [JsonProperty("final", NullValueHandling = NullValueHandling.Ignore)] public bool? Final { get; set; }
        [JsonProperty("emotion", NullValueHandling = NullValueHandling.Ignore)] public string Emotion { get; set; }
    }

    // ---- Holograms ---------------------------------------------------------

    /// <summary>Spatial transform (PROTOCOL.md §5.6). Vectors are meters; rotation is a quaternion [x,y,z,w].</summary>
    public class Transform
    {
        [JsonProperty("anchor", NullValueHandling = NullValueHandling.Ignore)] public string Anchor { get; set; }
        [JsonProperty("position", NullValueHandling = NullValueHandling.Ignore)] public float[] Position { get; set; }
        [JsonProperty("rotation", NullValueHandling = NullValueHandling.Ignore)] public float[] Rotation { get; set; }
        [JsonProperty("scale", NullValueHandling = NullValueHandling.Ignore)] public float[] Scale { get; set; }
        [JsonProperty("billboard", NullValueHandling = NullValueHandling.Ignore)] public bool? Billboard { get; set; }
    }

    /// <summary>The holographic object, used by holo.spawn / holo.update (PROTOCOL.md §5.6).</summary>
    public class HoloObject
    {
        [JsonProperty("object_id")] public string ObjectId { get; set; }
        [JsonProperty("widget_type")] public string WidgetType { get; set; }
        [JsonProperty("transform")] public Transform Transform { get; set; }
        [JsonProperty("props", NullValueHandling = NullValueHandling.Ignore)] public JObject Props { get; set; }
        [JsonProperty("interactable", NullValueHandling = NullValueHandling.Ignore)] public bool? Interactable { get; set; }
        [JsonProperty("interactions", NullValueHandling = NullValueHandling.Ignore)] public string[] Interactions { get; set; }
        [JsonProperty("ttl_ms", NullValueHandling = NullValueHandling.Ignore)] public int? TtlMs { get; set; }
    }

    /// <summary>holo.update partial patch (PROTOCOL.md §5.8).</summary>
    public class HoloUpdate
    {
        [JsonProperty("object_id")] public string ObjectId { get; set; }
        [JsonProperty("transform", NullValueHandling = NullValueHandling.Ignore)] public Transform Transform { get; set; }
        [JsonProperty("props", NullValueHandling = NullValueHandling.Ignore)] public JObject Props { get; set; }
    }

    /// <summary>holo.destroy payload (PROTOCOL.md §5.9).</summary>
    public class HoloDestroy
    {
        [JsonProperty("object_id")] public string ObjectId { get; set; }
        [JsonProperty("fade_ms", NullValueHandling = NullValueHandling.Ignore)] public int? FadeMs { get; set; }
    }

    /// <summary>holo.layout payload (PROTOCOL.md §5.10).</summary>
    public class HoloLayout
    {
        [JsonProperty("arrangement")] public string Arrangement { get; set; }
        [JsonProperty("anchor", NullValueHandling = NullValueHandling.Ignore)] public string Anchor { get; set; }
        [JsonProperty("objects")] public List<string> Objects { get; set; }
        [JsonProperty("spacing", NullValueHandling = NullValueHandling.Ignore)] public float? Spacing { get; set; }
    }

    // ---- Interaction + scene ----------------------------------------------

    /// <summary>client.interaction payload (PROTOCOL.md §5.11).</summary>
    public class ClientInteraction
    {
        [JsonProperty("object_id")] public string ObjectId { get; set; }
        [JsonProperty("widget_type", NullValueHandling = NullValueHandling.Ignore)] public string WidgetType { get; set; }
        [JsonProperty("action")] public string Action { get; set; }
        [JsonProperty("element", NullValueHandling = NullValueHandling.Ignore)] public string Element { get; set; }
        [JsonProperty("value", NullValueHandling = NullValueHandling.Ignore)] public JObject Value { get; set; }
        [JsonProperty("hand", NullValueHandling = NullValueHandling.Ignore)] public string Hand { get; set; }
    }

    /// <summary>Head pose for client.scene (PROTOCOL.md §5.12).</summary>
    public class Pose
    {
        [JsonProperty("position", NullValueHandling = NullValueHandling.Ignore)] public float[] Position { get; set; }
        [JsonProperty("rotation", NullValueHandling = NullValueHandling.Ignore)] public float[] Rotation { get; set; }
    }

    /// <summary>Detected surface for client.scene (PROTOCOL.md §5.12).</summary>
    public class Surface
    {
        [JsonProperty("id", NullValueHandling = NullValueHandling.Ignore)] public string Id { get; set; }
        [JsonProperty("type", NullValueHandling = NullValueHandling.Ignore)] public string Type { get; set; }
        [JsonProperty("center", NullValueHandling = NullValueHandling.Ignore)] public float[] Center { get; set; }
        [JsonProperty("normal", NullValueHandling = NullValueHandling.Ignore)] public float[] Normal { get; set; }
    }

    /// <summary>Spatial anchor for client.scene (PROTOCOL.md §5.12).</summary>
    public class SceneAnchor
    {
        [JsonProperty("id", NullValueHandling = NullValueHandling.Ignore)] public string Id { get; set; }
        [JsonProperty("position", NullValueHandling = NullValueHandling.Ignore)] public float[] Position { get; set; }
        [JsonProperty("rotation", NullValueHandling = NullValueHandling.Ignore)] public float[] Rotation { get; set; }
    }

    /// <summary>client.scene payload (PROTOCOL.md §5.12).</summary>
    public class ClientScene
    {
        [JsonProperty("head", NullValueHandling = NullValueHandling.Ignore)] public Pose Head { get; set; }
        [JsonProperty("surfaces", NullValueHandling = NullValueHandling.Ignore)] public List<Surface> Surfaces { get; set; }
        [JsonProperty("anchors", NullValueHandling = NullValueHandling.Ignore)] public List<SceneAnchor> Anchors { get; set; }
    }

    // ---- Misc --------------------------------------------------------------

    /// <summary>server.error / client.error payload (PROTOCOL.md §5.13).</summary>
    public class ProtocolError
    {
        [JsonProperty("code")] public string Code { get; set; }
        [JsonProperty("message")] public string Message { get; set; }
        [JsonProperty("fatal", NullValueHandling = NullValueHandling.Ignore)] public bool? Fatal { get; set; }
    }

    /// <summary>client.bye payload (PROTOCOL.md §3).</summary>
    public class ClientBye
    {
        [JsonProperty("reason", NullValueHandling = NullValueHandling.Ignore)] public string Reason { get; set; }
    }

    /// <summary>client.barge_in payload (PROTOCOL.md §5.14, v1.1) — cancel the in-flight turn.</summary>
    public class ClientBargeIn
    {
        [JsonProperty("reason", NullValueHandling = NullValueHandling.Ignore)] public string Reason { get; set; }
    }

    // ---- Perception (v1.1) -------------------------------------------------

    /// <summary>Camera intrinsics for unprojection (PROTOCOL.md §8.4).</summary>
    public class Intrinsics
    {
        [JsonProperty("fx", NullValueHandling = NullValueHandling.Ignore)] public float? Fx { get; set; }
        [JsonProperty("fy", NullValueHandling = NullValueHandling.Ignore)] public float? Fy { get; set; }
        [JsonProperty("cx", NullValueHandling = NullValueHandling.Ignore)] public float? Cx { get; set; }
        [JsonProperty("cy", NullValueHandling = NullValueHandling.Ignore)] public float? Cy { get; set; }
    }

    /// <summary>perception.vision_frame payload / §8.2 binary header (PROTOCOL.md §8.4).</summary>
    public class VisionFrame
    {
        [JsonProperty("frame_id")] public string FrameId { get; set; }
        [JsonProperty("camera")] public string Camera { get; set; }
        [JsonProperty("format")] public string Format { get; set; }
        [JsonProperty("width", NullValueHandling = NullValueHandling.Ignore)] public int? Width { get; set; }
        [JsonProperty("height", NullValueHandling = NullValueHandling.Ignore)] public int? Height { get; set; }
        [JsonProperty("quality", NullValueHandling = NullValueHandling.Ignore)] public int? Quality { get; set; }
        [JsonProperty("transport", NullValueHandling = NullValueHandling.Ignore)] public string Transport { get; set; }
        [JsonProperty("data", NullValueHandling = NullValueHandling.Ignore)] public string Data { get; set; }
        [JsonProperty("seq", NullValueHandling = NullValueHandling.Ignore)] public int? Seq { get; set; }
        [JsonProperty("ts_capture", NullValueHandling = NullValueHandling.Ignore)] public long? TsCapture { get; set; }
        [JsonProperty("pose", NullValueHandling = NullValueHandling.Ignore)] public Pose Pose { get; set; }
        [JsonProperty("intrinsics", NullValueHandling = NullValueHandling.Ignore)] public Intrinsics Intrinsics { get; set; }
    }

    /// <summary>perception.audio_event payload (PROTOCOL.md §8.4).</summary>
    public class AudioEvent
    {
        [JsonProperty("label")] public string Label { get; set; }
        [JsonProperty("confidence", NullValueHandling = NullValueHandling.Ignore)] public float? Confidence { get; set; }
        [JsonProperty("ts", NullValueHandling = NullValueHandling.Ignore)] public long? Ts { get; set; }
        [JsonProperty("loudness_db", NullValueHandling = NullValueHandling.Ignore)] public float? LoudnessDb { get; set; }
    }

    /// <summary>A labelled ambient sound for perception.audio_scene.</summary>
    public class SoundLabel
    {
        [JsonProperty("label")] public string Label { get; set; }
        [JsonProperty("confidence", NullValueHandling = NullValueHandling.Ignore)] public float? Confidence { get; set; }
    }

    /// <summary>perception.audio_scene payload (PROTOCOL.md §8.4).</summary>
    public class AudioScene
    {
        [JsonProperty("ambient_transcript", NullValueHandling = NullValueHandling.Ignore)] public string AmbientTranscript { get; set; }
        [JsonProperty("speaker", NullValueHandling = NullValueHandling.Ignore)] public string Speaker { get; set; }
        [JsonProperty("sounds", NullValueHandling = NullValueHandling.Ignore)] public List<SoundLabel> Sounds { get; set; }
        [JsonProperty("loudness_db", NullValueHandling = NullValueHandling.Ignore)] public float? LoudnessDb { get; set; }
        [JsonProperty("window_ms", NullValueHandling = NullValueHandling.Ignore)] public int? WindowMs { get; set; }
    }

    /// <summary>perception.gaze payload (PROTOCOL.md §8.4).</summary>
    public class Gaze
    {
        [JsonProperty("source", NullValueHandling = NullValueHandling.Ignore)] public string Source { get; set; }
        [JsonProperty("origin")] public float[] Origin { get; set; }
        [JsonProperty("direction")] public float[] Direction { get; set; }
        [JsonProperty("hit_object_id", NullValueHandling = NullValueHandling.Ignore)] public string HitObjectId { get; set; }
        [JsonProperty("hit_point", NullValueHandling = NullValueHandling.Ignore)] public float[] HitPoint { get; set; }
        [JsonProperty("dwell_ms", NullValueHandling = NullValueHandling.Ignore)] public int? DwellMs { get; set; }
    }

    /// <summary>A detected real-world object for perception.scene_objects.</summary>
    public class SceneObject
    {
        [JsonProperty("label")] public string Label { get; set; }
        [JsonProperty("confidence", NullValueHandling = NullValueHandling.Ignore)] public float? Confidence { get; set; }
        [JsonProperty("bbox", NullValueHandling = NullValueHandling.Ignore)] public float[] Bbox { get; set; }
        [JsonProperty("position", NullValueHandling = NullValueHandling.Ignore)] public float[] Position { get; set; }
        [JsonProperty("anchor", NullValueHandling = NullValueHandling.Ignore)] public string Anchor { get; set; }
    }

    /// <summary>perception.scene_objects payload (PROTOCOL.md §8.4).</summary>
    public class SceneObjects
    {
        [JsonProperty("frame_id", NullValueHandling = NullValueHandling.Ignore)] public string FrameId { get; set; }
        [JsonProperty("objects")] public List<SceneObject> Objects { get; set; }
    }

    /// <summary>Vision stream descriptor inside perception.state.</summary>
    public class VisionStreamState
    {
        [JsonProperty("active")] public bool Active { get; set; }
        [JsonProperty("fps", NullValueHandling = NullValueHandling.Ignore)] public float? Fps { get; set; }
        [JsonProperty("resolution", NullValueHandling = NullValueHandling.Ignore)] public string Resolution { get; set; }
        [JsonProperty("camera", NullValueHandling = NullValueHandling.Ignore)] public string Camera { get; set; }
    }

    /// <summary>Simple on/off stream descriptor inside perception.state.</summary>
    public class StreamState
    {
        [JsonProperty("active")] public bool Active { get; set; }
    }

    /// <summary>perception.state payload (PROTOCOL.md §8.4).</summary>
    public class PerceptionState
    {
        [JsonProperty("vision", NullValueHandling = NullValueHandling.Ignore)] public VisionStreamState Vision { get; set; }
        [JsonProperty("ambient_audio", NullValueHandling = NullValueHandling.Ignore)] public StreamState AmbientAudio { get; set; }
        [JsonProperty("gaze", NullValueHandling = NullValueHandling.Ignore)] public StreamState Gaze { get; set; }
        [JsonProperty("thermal", NullValueHandling = NullValueHandling.Ignore)] public string Thermal { get; set; }
        [JsonProperty("battery", NullValueHandling = NullValueHandling.Ignore)] public float? Battery { get; set; }
    }

    /// <summary>perception.request payload — server→client (PROTOCOL.md §8.4).</summary>
    public class PerceptionRequest
    {
        [JsonProperty("stream")] public string Stream { get; set; }
        [JsonProperty("action")] public string Action { get; set; }
        [JsonProperty("fps", NullValueHandling = NullValueHandling.Ignore)] public float? Fps { get; set; }
        [JsonProperty("max_resolution", NullValueHandling = NullValueHandling.Ignore)] public string MaxResolution { get; set; }
        [JsonProperty("quality", NullValueHandling = NullValueHandling.Ignore)] public int? Quality { get; set; }
        [JsonProperty("duration_ms", NullValueHandling = NullValueHandling.Ignore)] public int? DurationMs { get; set; }
        [JsonProperty("reason", NullValueHandling = NullValueHandling.Ignore)] public string Reason { get; set; }
    }

    /// <summary>A spatial annotation inside agent.observation.</summary>
    public class Annotation
    {
        [JsonProperty("label")] public string Label { get; set; }
        [JsonProperty("object_id", NullValueHandling = NullValueHandling.Ignore)] public string ObjectId { get; set; }
        [JsonProperty("position", NullValueHandling = NullValueHandling.Ignore)] public float[] Position { get; set; }
        [JsonProperty("anchor", NullValueHandling = NullValueHandling.Ignore)] public string Anchor { get; set; }
    }

    /// <summary>agent.observation payload — server→client (PROTOCOL.md §8.4).</summary>
    public class AgentObservation
    {
        [JsonProperty("text")] public string Text { get; set; }
        [JsonProperty("final", NullValueHandling = NullValueHandling.Ignore)] public bool? Final { get; set; }
        [JsonProperty("annotations", NullValueHandling = NullValueHandling.Ignore)] public List<Annotation> Annotations { get; set; }
    }

    // ---- Settings (v1.1 §5.15) ---------------------------------------------

    /// <summary>client.settings_get payload (PROTOCOL.md §5.15).</summary>
    public class ClientSettingsGet
    {
        [JsonProperty("section", NullValueHandling = NullValueHandling.Ignore)] public string Section { get; set; }
    }

    /// <summary>The llm block of client.settings_update. ApiKey is inbound-only.</summary>
    public class LlmSettingsUpdate
    {
        [JsonProperty("provider", NullValueHandling = NullValueHandling.Ignore)] public string Provider { get; set; }
        [JsonProperty("model", NullValueHandling = NullValueHandling.Ignore)] public string Model { get; set; }
        [JsonProperty("base_url", NullValueHandling = NullValueHandling.Ignore)] public string BaseUrl { get; set; }
        /// <summary>Sensitive: send only to set/replace; never echoed in server.settings.</summary>
        [JsonProperty("api_key", NullValueHandling = NullValueHandling.Ignore)] public string ApiKey { get; set; }
    }

    /// <summary>client.settings_update payload (PROTOCOL.md §5.15).</summary>
    public class ClientSettingsUpdate
    {
        [JsonProperty("llm", NullValueHandling = NullValueHandling.Ignore)] public LlmSettingsUpdate Llm { get; set; }
    }

    /// <summary>Provider capabilities inside a server.settings provider entry.</summary>
    public class ProviderCapabilities
    {
        [JsonProperty("tools", NullValueHandling = NullValueHandling.Ignore)] public bool? Tools { get; set; }
        [JsonProperty("vision", NullValueHandling = NullValueHandling.Ignore)] public bool? Vision { get; set; }
    }

    /// <summary>One entry in server.settings.llm.providers — never carries a key.</summary>
    public class ProviderEntry
    {
        [JsonProperty("id")] public string Id { get; set; }
        [JsonProperty("name")] public string Name { get; set; }
        [JsonProperty("default_model")] public string DefaultModel { get; set; }
        [JsonProperty("models", NullValueHandling = NullValueHandling.Ignore)] public List<string> Models { get; set; }
        [JsonProperty("needs_key")] public bool NeedsKey { get; set; }
        [JsonProperty("needs_base_url")] public bool NeedsBaseUrl { get; set; }
        [JsonProperty("key_set")] public bool KeySet { get; set; }
        [JsonProperty("capabilities", NullValueHandling = NullValueHandling.Ignore)] public ProviderCapabilities Capabilities { get; set; }
    }

    /// <summary>The active LLM config — key_set boolean only, never the key.</summary>
    public class CurrentLlm
    {
        [JsonProperty("provider")] public string Provider { get; set; }
        [JsonProperty("model")] public string Model { get; set; }
        [JsonProperty("base_url", NullValueHandling = NullValueHandling.Ignore)] public string BaseUrl { get; set; }
        [JsonProperty("key_set")] public bool KeySet { get; set; }
    }

    /// <summary>The llm section of server.settings.</summary>
    public class LlmSettings
    {
        [JsonProperty("current")] public CurrentLlm Current { get; set; }
        [JsonProperty("providers")] public List<ProviderEntry> Providers { get; set; }
    }

    /// <summary>server.settings payload — current config + catalog. NEVER contains an api_key.</summary>
    public class ServerSettings
    {
        [JsonProperty("llm")] public LlmSettings Llm { get; set; }
    }

    // ---- Multi-agent orchestration (v1.2 §9) -------------------------------

    /// <summary>An agent node in an orchestration.plan (PROTOCOL.md §9.2).</summary>
    public class OrchestrationAgent
    {
        [JsonProperty("agent_id")] public string AgentId { get; set; }
        [JsonProperty("role")] public string Role { get; set; }
        [JsonProperty("name", NullValueHandling = NullValueHandling.Ignore)] public string Name { get; set; }
        [JsonProperty("parent", NullValueHandling = NullValueHandling.Ignore)] public string Parent { get; set; }
        [JsonProperty("level")] public int Level { get; set; }
        [JsonProperty("subtask", NullValueHandling = NullValueHandling.Ignore)] public string Subtask { get; set; }
        [JsonProperty("skills", NullValueHandling = NullValueHandling.Ignore)] public List<string> Skills { get; set; }
    }

    /// <summary>An edge in the plan DAG.</summary>
    public class OrchestrationEdge
    {
        [JsonProperty("from")] public string From { get; set; }
        [JsonProperty("to")] public string To { get; set; }
    }

    /// <summary>orchestration.plan payload — the team Jarvis built (PROTOCOL.md §9.2).</summary>
    public class OrchestrationPlan
    {
        [JsonProperty("plan_id")] public string PlanId { get; set; }
        [JsonProperty("goal")] public string Goal { get; set; }
        [JsonProperty("agents")] public List<OrchestrationAgent> Agents { get; set; }
        [JsonProperty("edges", NullValueHandling = NullValueHandling.Ignore)] public List<OrchestrationEdge> Edges { get; set; }
    }

    /// <summary>orchestration.agent_status payload — one agent's lifecycle (PROTOCOL.md §9.2).</summary>
    public class OrchestrationAgentStatus
    {
        [JsonProperty("plan_id")] public string PlanId { get; set; }
        [JsonProperty("agent_id")] public string AgentId { get; set; }
        [JsonProperty("role")] public string Role { get; set; }
        [JsonProperty("parent", NullValueHandling = NullValueHandling.Ignore)] public string Parent { get; set; }
        [JsonProperty("level", NullValueHandling = NullValueHandling.Ignore)] public int? Level { get; set; }
        [JsonProperty("state")] public string State { get; set; }
        [JsonProperty("skill", NullValueHandling = NullValueHandling.Ignore)] public string Skill { get; set; }
        [JsonProperty("label", NullValueHandling = NullValueHandling.Ignore)] public string Label { get; set; }
        [JsonProperty("progress", NullValueHandling = NullValueHandling.Ignore)] public float? Progress { get; set; }
    }

    /// <summary>orchestration.handoff payload — a delegation (PROTOCOL.md §9.2).</summary>
    public class OrchestrationHandoff
    {
        [JsonProperty("plan_id")] public string PlanId { get; set; }
        [JsonProperty("from_agent")] public string FromAgent { get; set; }
        [JsonProperty("to_agent")] public string ToAgent { get; set; }
        [JsonProperty("to_role")] public string ToRole { get; set; }
        [JsonProperty("level", NullValueHandling = NullValueHandling.Ignore)] public int? Level { get; set; }
        [JsonProperty("subtask", NullValueHandling = NullValueHandling.Ignore)] public string Subtask { get; set; }
        [JsonProperty("reason", NullValueHandling = NullValueHandling.Ignore)] public string Reason { get; set; }
    }

    // ---- Tracing & in-headset authoring (v1.3 §10) ------------------------

    /// <summary>client.trace_subscribe payload (PROTOCOL.md §10.1).</summary>
    public class ClientTraceSubscribe
    {
        [JsonProperty("enabled")] public bool Enabled { get; set; }
    }

    /// <summary>client.trace_get payload (PROTOCOL.md §10.1).</summary>
    public class ClientTraceGet
    {
        [JsonProperty("plan_id", NullValueHandling = NullValueHandling.Ignore)] public string PlanId { get; set; }
    }

    /// <summary>client.agent_inspect payload (PROTOCOL.md §10.1).</summary>
    public class ClientAgentInspect
    {
        [JsonProperty("role", NullValueHandling = NullValueHandling.Ignore)] public string Role { get; set; }
        [JsonProperty("agent_id", NullValueHandling = NullValueHandling.Ignore)] public string AgentId { get; set; }
    }

    /// <summary>client.author_skill payload (PROTOCOL.md §10.2).</summary>
    public class ClientAuthorSkill
    {
        [JsonProperty("op")] public string Op { get; set; }
        [JsonProperty("name")] public string Name { get; set; }
        [JsonProperty("category", NullValueHandling = NullValueHandling.Ignore)] public string Category { get; set; }
        [JsonProperty("agent", NullValueHandling = NullValueHandling.Ignore)] public string Agent { get; set; }
        [JsonProperty("description", NullValueHandling = NullValueHandling.Ignore)] public string Description { get; set; }
        [JsonProperty("body", NullValueHandling = NullValueHandling.Ignore)] public string Body { get; set; }
        [JsonProperty("allowed_tools", NullValueHandling = NullValueHandling.Ignore)] public List<string> AllowedTools { get; set; }
        [JsonProperty("license", NullValueHandling = NullValueHandling.Ignore)] public string License { get; set; }
        [JsonProperty("compatibility", NullValueHandling = NullValueHandling.Ignore)] public string Compatibility { get; set; }
    }

    /// <summary>client.author_agent payload (PROTOCOL.md §10.2).</summary>
    public class ClientAuthorAgent
    {
        [JsonProperty("op")] public string Op { get; set; }
        [JsonProperty("role")] public string Role { get; set; }
        [JsonProperty("name", NullValueHandling = NullValueHandling.Ignore)] public string Name { get; set; }
        [JsonProperty("persona", NullValueHandling = NullValueHandling.Ignore)] public string Persona { get; set; }
        [JsonProperty("tools", NullValueHandling = NullValueHandling.Ignore)] public List<string> Tools { get; set; }
        [JsonProperty("skills", NullValueHandling = NullValueHandling.Ignore)] public List<string> Skills { get; set; }
    }

    /// <summary>orchestration.trace_event payload — one trace entry (PROTOCOL.md §10.1).</summary>
    public class TraceEvent
    {
        [JsonProperty("plan_id")] public string PlanId { get; set; }
        [JsonProperty("seq")] public int Seq { get; set; }
        [JsonProperty("ts")] public long Ts { get; set; }
        [JsonProperty("agent_id")] public string AgentId { get; set; }
        [JsonProperty("role")] public string Role { get; set; }
        [JsonProperty("parent", NullValueHandling = NullValueHandling.Ignore)] public string Parent { get; set; }
        [JsonProperty("level", NullValueHandling = NullValueHandling.Ignore)] public int? Level { get; set; }
        [JsonProperty("kind")] public string Kind { get; set; }
        [JsonProperty("label")] public string Label { get; set; }
        [JsonProperty("skill", NullValueHandling = NullValueHandling.Ignore)] public string Skill { get; set; }
        [JsonProperty("tool", NullValueHandling = NullValueHandling.Ignore)] public string Tool { get; set; }
        [JsonProperty("detail", NullValueHandling = NullValueHandling.Ignore)] public string Detail { get; set; }
        [JsonProperty("duration_ms", NullValueHandling = NullValueHandling.Ignore)] public int? DurationMs { get; set; }
    }

    /// <summary>An agent reference in a server.trace (PROTOCOL.md §10.1).</summary>
    public class TraceAgentRef
    {
        [JsonProperty("agent_id")] public string AgentId { get; set; }
        [JsonProperty("role")] public string Role { get; set; }
        [JsonProperty("parent", NullValueHandling = NullValueHandling.Ignore)] public string Parent { get; set; }
        [JsonProperty("level", NullValueHandling = NullValueHandling.Ignore)] public int? Level { get; set; }
    }

    /// <summary>server.trace payload — full ordered trace (PROTOCOL.md §10.1).</summary>
    public class ServerTrace
    {
        [JsonProperty("plan_id")] public string PlanId { get; set; }
        [JsonProperty("goal", NullValueHandling = NullValueHandling.Ignore)] public string Goal { get; set; }
        [JsonProperty("agents", NullValueHandling = NullValueHandling.Ignore)] public List<TraceAgentRef> Agents { get; set; }
        [JsonProperty("entries")] public List<TraceEvent> Entries { get; set; }
    }

    /// <summary>A skill descriptor in server.agent_info (PROTOCOL.md §10.1).</summary>
    public class SkillInfo
    {
        [JsonProperty("name")] public string Name { get; set; }
        [JsonProperty("description", NullValueHandling = NullValueHandling.Ignore)] public string Description { get; set; }
        [JsonProperty("source", NullValueHandling = NullValueHandling.Ignore)] public string Source { get; set; }
    }

    /// <summary>A recent memory item in server.agent_info (PROTOCOL.md §10.1).</summary>
    public class MemoryRecentItem
    {
        [JsonProperty("ts")] public long Ts { get; set; }
        [JsonProperty("text")] public string Text { get; set; }
    }

    /// <summary>Memory summary in server.agent_info (PROTOCOL.md §10.1).</summary>
    public class MemoryInfo
    {
        [JsonProperty("summary", NullValueHandling = NullValueHandling.Ignore)] public string Summary { get; set; }
        [JsonProperty("items", NullValueHandling = NullValueHandling.Ignore)] public int? Items { get; set; }
        [JsonProperty("recent", NullValueHandling = NullValueHandling.Ignore)] public List<MemoryRecentItem> Recent { get; set; }
    }

    /// <summary>server.agent_info payload (PROTOCOL.md §10.1).</summary>
    public class ServerAgentInfo
    {
        [JsonProperty("role")] public string Role { get; set; }
        [JsonProperty("name")] public string Name { get; set; }
        [JsonProperty("source", NullValueHandling = NullValueHandling.Ignore)] public string Source { get; set; }
        [JsonProperty("persona", NullValueHandling = NullValueHandling.Ignore)] public string Persona { get; set; }
        [JsonProperty("tools", NullValueHandling = NullValueHandling.Ignore)] public List<string> Tools { get; set; }
        [JsonProperty("skills", NullValueHandling = NullValueHandling.Ignore)] public List<SkillInfo> Skills { get; set; }
        [JsonProperty("memory", NullValueHandling = NullValueHandling.Ignore)] public MemoryInfo Memory { get; set; }
    }

    /// <summary>An agent in server.authoring (PROTOCOL.md §10.2).</summary>
    public class AuthoringAgent
    {
        [JsonProperty("role")] public string Role { get; set; }
        [JsonProperty("name")] public string Name { get; set; }
        [JsonProperty("source", NullValueHandling = NullValueHandling.Ignore)] public string Source { get; set; }
        [JsonProperty("skills", NullValueHandling = NullValueHandling.Ignore)] public List<string> Skills { get; set; }
        [JsonProperty("tools", NullValueHandling = NullValueHandling.Ignore)] public List<string> Tools { get; set; }
    }

    /// <summary>A skill in server.authoring (PROTOCOL.md §10.2).</summary>
    public class AuthoringSkill
    {
        [JsonProperty("name")] public string Name { get; set; }
        [JsonProperty("agent", NullValueHandling = NullValueHandling.Ignore)] public string Agent { get; set; }
        [JsonProperty("category", NullValueHandling = NullValueHandling.Ignore)] public string Category { get; set; }
        [JsonProperty("source", NullValueHandling = NullValueHandling.Ignore)] public string Source { get; set; }
        [JsonProperty("description", NullValueHandling = NullValueHandling.Ignore)] public string Description { get; set; }
    }

    /// <summary>server.authoring payload — authorable agents & skills (PROTOCOL.md §10.2).</summary>
    public class ServerAuthoring
    {
        [JsonProperty("agents")] public List<AuthoringAgent> Agents { get; set; }
        [JsonProperty("skills")] public List<AuthoringSkill> Skills { get; set; }
        [JsonProperty("categories", NullValueHandling = NullValueHandling.Ignore)] public List<string> Categories { get; set; }
        [JsonProperty("tools", NullValueHandling = NullValueHandling.Ignore)] public List<string> Tools { get; set; }
    }
}
