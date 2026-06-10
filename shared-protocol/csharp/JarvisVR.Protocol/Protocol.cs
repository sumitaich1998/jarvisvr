// JarvisVR wire protocol (v1) — C# constants.
// Source of truth: docs/PROTOCOL.md + shared-protocol/schema/*.schema.json.
// Drop the JarvisVR.Protocol folder into a Unity project that has
// Newtonsoft.Json available (com.unity.nuget.newtonsoft-json).

namespace JarvisVR.Protocol
{
    /// <summary>Top-level protocol metadata.</summary>
    public static class Protocol
    {
        /// <summary>Wire-protocol version implemented by these bindings.</summary>
        public const string Version = "1.1.0";

        /// <summary>Protocol versions accepted on the wire (v1.1 still serves v1.0 clients).</summary>
        public static readonly string[] SupportedVersions = { "1.0.0", "1.1.0" };

        /// <summary>Default WebSocket path for the v1.1 vision binary transport.</summary>
        public const string VisionPath = "/vision";

        /// <summary>Default WebSocket path on the agent-backend.</summary>
        public const string DefaultPath = "/jarvis";

        /// <summary>Default agent-backend port.</summary>
        public const int DefaultPort = 8765;
    }

    /// <summary>String constants for every message <c>type</c> in the v1 catalog.</summary>
    public static class MessageTypes
    {
        // client -> server
        public const string ClientHello = "client.hello";
        public const string ClientBye = "client.bye";
        public const string ClientHeartbeat = "client.heartbeat";
        public const string UserText = "user.text";
        public const string UserVoiceTranscript = "user.voice_transcript";
        public const string UserVoicePartial = "user.voice_partial";
        public const string ClientInteraction = "client.interaction";
        public const string ClientScene = "client.scene";
        public const string ClientAck = "client.ack";
        public const string ClientError = "client.error";
        public const string ClientBargeIn = "client.barge_in"; // v1.1: cancel the in-flight turn
        public const string ClientSettingsGet = "client.settings_get"; // v1.1 §5.15
        public const string ClientSettingsUpdate = "client.settings_update"; // v1.1 §5.15

        // client -> server (v1.1 perception)
        public const string PerceptionVisionFrame = "perception.vision_frame";
        public const string PerceptionAudioEvent = "perception.audio_event";
        public const string PerceptionAudioScene = "perception.audio_scene";
        public const string PerceptionGaze = "perception.gaze";
        public const string PerceptionSceneObjects = "perception.scene_objects";
        public const string PerceptionState = "perception.state";

        // server -> client
        public const string ServerHelloAck = "server.hello_ack";
        public const string ServerHeartbeat = "server.heartbeat";
        public const string AgentThinking = "agent.thinking";
        public const string AgentSpeech = "agent.speech";
        public const string AgentTranscript = "agent.transcript";
        public const string HoloSpawn = "holo.spawn";
        public const string HoloUpdate = "holo.update";
        public const string HoloDestroy = "holo.destroy";
        public const string HoloLayout = "holo.layout";
        public const string ServerError = "server.error";

        // server -> client (v1.1 perception)
        public const string PerceptionRequest = "perception.request";
        public const string AgentObservation = "agent.observation";

        // server -> client (v1.1 §5.15 settings)
        public const string ServerSettings = "server.settings";

        // server -> client (v1.2 §9 multi-agent orchestration)
        public const string OrchestrationPlan = "orchestration.plan";
        public const string OrchestrationAgentStatus = "orchestration.agent_status";
        public const string OrchestrationHandoff = "orchestration.handoff";

        // v1.3 §10 tracing + authoring (client -> server)
        public const string ClientTraceSubscribe = "client.trace_subscribe";
        public const string ClientTraceGet = "client.trace_get";
        public const string ClientAgentInspect = "client.agent_inspect";
        public const string ClientAuthorList = "client.author_list";
        public const string ClientAuthorSkill = "client.author_skill";
        public const string ClientAuthorAgent = "client.author_agent";
        // v1.3 §10 (server -> client)
        public const string OrchestrationTraceEvent = "orchestration.trace_event";
        public const string ServerTrace = "server.trace";
        public const string ServerAgentInfo = "server.agent_info";
        public const string ServerAuthoring = "server.authoring";
    }

    /// <summary>Transform anchor frames (PROTOCOL.md §5.6 / ARCHITECTURE §5).</summary>
    public static class Anchors
    {
        public const string World = "world";
        public const string Head = "head";
        public const string HandLeft = "hand_left";
        public const string HandRight = "hand_right";
        public const string Surface = "surface";
    }

    /// <summary>Interaction kinds (PROTOCOL.md §5.11).</summary>
    public static class Interactions
    {
        public const string Tap = "tap";
        public const string Grab = "grab";
        public const string Release = "release";
        public const string Drag = "drag";
        public const string Slider = "slider";
        public const string Toggle = "toggle";
        public const string Resize = "resize";
        public const string Dwell = "dwell";
    }

    /// <summary>agent.thinking stages (PROTOCOL.md §5.4, +§8.3).</summary>
    public static class ThinkingStages
    {
        public const string Planning = "planning";
        public const string ToolCall = "tool_call";
        public const string Rendering = "rendering";
        public const string Done = "done";
        public const string Perceiving = "perceiving";  // v1.1
        public const string Looking = "looking";        // v1.1
    }

    /// <summary>Passthrough RGB camera ids (PROTOCOL.md §8.4, v1.1).</summary>
    public static class Cameras
    {
        public const string RgbLeft = "rgb_left";
        public const string RgbRight = "rgb_right";
        public const string RgbCenter = "rgb_center";
    }

    /// <summary>Vision frame encodings (PROTOCOL.md §8.4, v1.1).</summary>
    public static class VisionFormats
    {
        public const string Jpeg = "jpeg";
        public const string Png = "png";
        public const string Rgb24 = "rgb24";
    }

    /// <summary>Vision frame transports (PROTOCOL.md §8.2, v1.1).</summary>
    public static class VisionTransports
    {
        public const string Inline = "inline";
        public const string Binary = "binary";
    }

    /// <summary>Perception streams the server can request (PROTOCOL.md §8.4, v1.1).</summary>
    public static class PerceptionStreams
    {
        public const string Vision = "vision";
        public const string AmbientAudio = "ambient_audio";
        public const string Gaze = "gaze";
        public const string SceneObjects = "scene_objects";
    }

    /// <summary>perception.request actions (PROTOCOL.md §8.4, v1.1).</summary>
    public static class PerceptionActions
    {
        public const string Start = "start";
        public const string Stop = "stop";
        public const string Once = "once";
        public const string Set = "set";
    }

    /// <summary>Gaze sources (PROTOCOL.md §8.4, v1.1).</summary>
    public static class GazeSources
    {
        public const string Eyes = "eyes";
        public const string Head = "head";
    }

    /// <summary>Ambient speaker attribution (PROTOCOL.md §8.4, v1.1).</summary>
    public static class Speakers
    {
        public const string User = "user";
        public const string Other = "other";
        public const string Unknown = "unknown";
    }

    /// <summary>Device thermal states (PROTOCOL.md §8.4, v1.1).</summary>
    public static class ThermalStates
    {
        public const string Nominal = "nominal";
        public const string Fair = "fair";
        public const string Serious = "serious";
        public const string Critical = "critical";
    }

    /// <summary>holo.layout arrangements (PROTOCOL.md §5.10).</summary>
    public static class Arrangements
    {
        public const string Arc = "arc";
        public const string Grid = "grid";
        public const string Stack = "stack";
        public const string Free = "free";
    }

    /// <summary>Suggested error codes (PROTOCOL.md §5.13).</summary>
    public static class ErrorCodes
    {
        public const string BadEnvelope = "bad_envelope";
        public const string UnsupportedVersion = "unsupported_version";
        public const string UnknownType = "unknown_type";
        public const string UnknownWidget = "unknown_widget";
        public const string InvalidProps = "invalid_props";
        public const string ToolFailed = "tool_failed";
        public const string Internal = "internal";
    }
}
