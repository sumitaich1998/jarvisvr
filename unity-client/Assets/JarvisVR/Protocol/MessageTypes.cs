namespace JarvisVR.Protocol
{
    /// <summary>
    /// Canonical <c>type</c> string constants for every message in the v1 catalog
    /// (docs/PROTOCOL.md §4). Using constants avoids typos across the codebase.
    /// </summary>
    public static class MessageTypes
    {
        // ---- Client → Server (§4.1) ----
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
        public const string ClientBargeIn = "client.barge_in"; // §5.14: user interrupted active TTS

        // ---- Server → Client (§4.2) ----
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

        // ---- v1.1 Multimodal Perception (§8.3) ----
        // Client → Server
        public const string PerceptionVisionFrame = "perception.vision_frame";
        public const string PerceptionAudioEvent = "perception.audio_event";
        public const string PerceptionAudioScene = "perception.audio_scene";
        public const string PerceptionGaze = "perception.gaze";
        public const string PerceptionSceneObjects = "perception.scene_objects";
        public const string PerceptionState = "perception.state";
        // Server → Client
        public const string PerceptionRequest = "perception.request";
        public const string AgentObservation = "agent.observation";

        // ---- v1.1 Settings (§5.15) ----
        public const string ClientSettingsGet = "client.settings_get";        // client → server
        public const string ClientSettingsUpdate = "client.settings_update";  // client → server
        public const string ServerSettings = "server.settings";              // server → client

        // ---- v1.2 Multi-Agent Orchestration (§9) — server → client ----
        public const string OrchestrationPlan = "orchestration.plan";
        public const string OrchestrationAgentStatus = "orchestration.agent_status";
        public const string OrchestrationHandoff = "orchestration.handoff";

        // ---- v1.3 Per-agent tracing (§10.1) ----
        public const string ClientTraceSubscribe = "client.trace_subscribe"; // client → server
        public const string ClientTraceGet = "client.trace_get";            // client → server
        public const string ClientAgentInspect = "client.agent_inspect";    // client → server
        public const string OrchestrationTraceEvent = "orchestration.trace_event"; // server → client
        public const string ServerTrace = "server.trace";                   // server → client
        public const string ServerAgentInfo = "server.agent_info";          // server → client

        // ---- v1.3 In-headset authoring (§10.2) ----
        public const string ClientAuthorList = "client.author_list";        // client → server
        public const string ClientAuthorSkill = "client.author_skill";      // client → server
        public const string ClientAuthorAgent = "client.author_agent";      // client → server
        public const string ServerAuthoring = "server.authoring";           // server → client
    }

    /// <summary>orchestration.agent_status state machine (§9.2).</summary>
    public static class AgentStates
    {
        public const string Queued = "queued";
        public const string Planning = "planning";
        public const string Working = "working";
        public const string Delegating = "delegating";
        public const string Waiting = "waiting";
        public const string Done = "done";
        public const string Failed = "failed";

        /// <summary>Terminal states (the agent has finished, successfully or not).</summary>
        public static bool IsTerminal(string state) => state == Done || state == Failed;
    }

    /// <summary>Well-known orchestration role ids (§3 of ORCHESTRATION.md). Display names come from
    /// the plan; these are for reference/keys.</summary>
    public static class AgentRoles
    {
        public const string Orchestrator = "orchestrator";
        public const string Perception = "perception-agent";
        public const string Research = "research-agent";
        public const string Productivity = "productivity-agent";
        public const string SmartHome = "smart-home-agent";
        public const string Navigation = "navigation-agent";
        public const string Media = "media-agent";
        public const string Communication = "communication-agent";
        public const string Stage = "stage-agent";
        public const string System = "system-agent";
    }

    /// <summary>client.settings_get sections (§5.15).</summary>
    public static class SettingsSections
    {
        public const string Llm = "llm";
        public const string All = "all";
    }

    /// <summary>perception.request stream identifiers (§8.4).</summary>
    public static class PerceptionStreams
    {
        public const string Vision = "vision";
        public const string AmbientAudio = "ambient_audio";
        public const string Gaze = "gaze";
        public const string SceneObjects = "scene_objects";
    }

    /// <summary>perception.request actions (§8.4): start | stop | once | set.</summary>
    public static class PerceptionActions
    {
        public const string Start = "start";
        public const string Stop = "stop";
        public const string Once = "once";   // single snapshot
        public const string Set = "set";     // adjust params (fps/quality/resolution)
    }

    /// <summary>Vision frame transports (§8.2 / §8.4).</summary>
    public static class VisionTransports
    {
        public const string Inline = "inline";   // base64 in `data` on the main channel
        public const string Binary = "binary";   // length-prefixed on /vision
    }

    /// <summary>Passthrough camera ids (§8.4).</summary>
    public static class CameraIds
    {
        public const string RgbCenter = "rgb_center";
        public const string RgbLeft = "rgb_left";
        public const string RgbRight = "rgb_right";
    }

    /// <summary>perception.gaze sources (§8.4).</summary>
    public static class GazeSources
    {
        public const string Eyes = "eyes";
        public const string Head = "head";
    }

    /// <summary>perception.state thermal levels (§8.4).</summary>
    public static class ThermalStates
    {
        public const string Nominal = "nominal";
        public const string Fair = "fair";
        public const string Serious = "serious";
        public const string Critical = "critical";
    }

    /// <summary>Anchor enum values (docs/PROTOCOL.md §5.6 / cross-cutting conventions).</summary>
    public static class Anchors
    {
        public const string World = "world";
        public const string Head = "head";
        public const string HandLeft = "hand_left";
        public const string HandRight = "hand_right";
        public const string Surface = "surface";
    }

    /// <summary>holo.layout arrangement values (§5.10).</summary>
    public static class Arrangements
    {
        public const string Arc = "arc";
        public const string Grid = "grid";
        public const string Stack = "stack";
        public const string Free = "free";
    }

    /// <summary>client.interaction action values (§5.11).</summary>
    public static class InteractionActions
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

    /// <summary>agent.thinking stage values (§5.4; §8.3 adds perceiving/looking).</summary>
    public static class ThinkingStages
    {
        public const string Planning = "planning";
        public const string ToolCall = "tool_call";
        public const string Rendering = "rendering";
        public const string Done = "done";
        public const string Perceiving = "perceiving"; // v1.1
        public const string Looking = "looking";       // v1.1
    }

    /// <summary>
    /// Known widget_type identifiers. The authoritative list lives in holo-tools/registry.json;
    /// these mirror the catalog described in ARCHITECTURE.md §3.4 / PROTOCOL.md so the client can
    /// render them procedurally even before the registry asset is wired in.
    /// </summary>
    public static class WidgetTypes
    {
        public const string WeatherOrb = "weather_orb";
        public const string Timer = "timer";
        public const string Panel = "panel";
        public const string Chart3D = "chart_3d";
        public const string ModelViewer = "model_viewer";
        public const string MediaPlayer = "media_player";
        public const string Map3D = "map_3d";
        public const string SmartHomePanel = "smart_home_panel";
        public const string TextLabel = "text_label";
        public const string Button = "button";
        public const string TodoList = "todo_list";
        public const string ImageBoard = "image_board";

        // ---- v1.1 perception widgets (§8.5) ----
        public const string VisionAnnotation = "vision_annotation";
        public const string BoundingBox3D = "bounding_box_3d";
        public const string LiveCaption = "live_caption";
        public const string VisionFeed = "vision_feed";
        public const string SceneLabel = "scene_label";

        // ---- v1.1 P1 feature widgets (FEATURES §3) ----
        public const string Clock = "clock";
        public const string WorldClock = "world_clock";
        public const string Calendar = "calendar";
        public const string StickyNote = "sticky_note";
        public const string NavigationArrow = "navigation_arrow";
        public const string MeasuringTape = "measuring_tape";
        public const string SystemLauncher = "system_launcher";
        public const string NotificationToast = "notification_toast";
        public const string SettingsPanel = "settings_panel";
        public const string MusicVisualizer = "music_visualizer";
        public const string DataTable = "data_table";
        public const string Pomodoro = "pomodoro";
        public const string HealthRing = "health_ring";
        public const string StocksTicker = "stocks_ticker";
        public const string CodeViewer = "code_viewer";
        public const string Graph3D = "graph_3d";
    }

    /// <summary>orchestration.trace_event kinds (§10.1).</summary>
    public static class TraceKinds
    {
        public const string MemoryRead = "memory_read";
        public const string MemoryWrite = "memory_write";
        public const string SkillActivated = "skill_activated";
        public const string ToolCall = "tool_call";
        public const string ToolResult = "tool_result";
        public const string Observation = "observation";
        public const string Delegated = "delegated";
        public const string Speech = "speech";
        public const string Error = "error";
    }

    /// <summary>author_skill / author_agent operations (§10.2).</summary>
    public static class AuthorOps
    {
        public const string Create = "create";
        public const string Update = "update";
        public const string Delete = "delete";
    }

    /// <summary>Item provenance (§10): built-in (read-only) vs user-authored (editable).</summary>
    public static class AuthoringSources
    {
        public const string Builtin = "builtin";
        public const string User = "user";
    }

    /// <summary>Suggested error codes (§5.13 + §5.15 settings + §10 authoring).</summary>
    public static class ErrorCodes
    {
        public const string BadEnvelope = "bad_envelope";
        public const string UnsupportedVersion = "unsupported_version";
        public const string UnknownType = "unknown_type";
        public const string UnknownWidget = "unknown_widget";
        public const string InvalidProps = "invalid_props";
        public const string ToolFailed = "tool_failed";
        public const string Internal = "internal";
        // §5.15 settings
        public const string InvalidSettings = "invalid_settings";
        public const string ProviderUnavailable = "provider_unavailable";
        public const string InvalidKey = "invalid_key";
        // §10 authoring
        public const string InvalidSkill = "invalid_skill";
        public const string InvalidAgent = "invalid_agent";
        public const string NameConflict = "name_conflict";
        public const string Forbidden = "forbidden";
    }
}
