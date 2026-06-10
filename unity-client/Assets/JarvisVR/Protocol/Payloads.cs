using System.Collections.Generic;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;

namespace JarvisVR.Protocol
{
    // ---------------------------------------------------------------------------------------------
    // Strongly-typed payloads for the v1 message catalog (docs/PROTOCOL.md §5).
    // All types are tolerant of missing/extra fields (forward-compatible).
    // ---------------------------------------------------------------------------------------------

    // §5.1 client.hello
    public class ClientHello
    {
        [JsonProperty("device")] public string Device = "quest3";
        [JsonProperty("app_version")] public string AppVersion;
        [JsonProperty("protocol_version")] public string ProtocolVersion = ProtocolConstants.Version;
        [JsonProperty("capabilities")] public Capabilities Capabilities = new Capabilities();
        [JsonProperty("locale")] public string Locale = "en-US";
    }

    public class Capabilities
    {
        [JsonProperty("passthrough")] public bool Passthrough = true;
        [JsonProperty("hand_tracking")] public bool HandTracking = true;
        [JsonProperty("controllers")] public bool Controllers = true;
        [JsonProperty("mic")] public bool Mic = true;
        [JsonProperty("speaker")] public bool Speaker = true;
        [JsonProperty("scene_understanding")] public bool SceneUnderstanding = true;

        // v1.1 multimodal perception (§8.1) — advertise truthfully for the running device.
        [JsonProperty("camera_passthrough")] public bool CameraPassthrough = false;
        [JsonProperty("ambient_audio")] public bool AmbientAudio = false;
        [JsonProperty("eye_tracking")] public bool EyeTracking = false;
        [JsonProperty("on_device_vision")] public bool OnDeviceVision = false;
        [JsonProperty("depth")] public bool Depth = false;
    }

    // §5.2 server.hello_ack
    public class ServerHelloAck
    {
        [JsonProperty("session")] public string Session;
        [JsonProperty("protocol_version")] public string ProtocolVersion;
        [JsonProperty("agent")] public AgentInfo Agent;
        [JsonProperty("tools")] public string[] Tools;
        [JsonProperty("voice")] public VoiceInfo Voice;
        // v1.2 (§9): server advertises multi-agent orchestration + the available specialist roles.
        [JsonProperty("orchestration", NullValueHandling = NullValueHandling.Ignore)] public bool Orchestration;
        [JsonProperty("agents", NullValueHandling = NullValueHandling.Ignore)] public string[] Agents;
        // v1.3 (§10): server advertises per-agent tracing + in-headset authoring.
        [JsonProperty("tracing", NullValueHandling = NullValueHandling.Ignore)] public bool Tracing;
        [JsonProperty("authoring", NullValueHandling = NullValueHandling.Ignore)] public bool Authoring;
    }

    public class AgentInfo
    {
        [JsonProperty("name")] public string Name;
        [JsonProperty("model")] public string Model;
    }

    public class VoiceInfo
    {
        [JsonProperty("tts")] public bool Tts;
        [JsonProperty("wake_word")] public string WakeWord;
    }

    // §5.3 user.text / user.voice_transcript / user.voice_partial / agent.transcript
    public class TextPayload
    {
        [JsonProperty("text")] public string Text;
        [JsonProperty("confidence", NullValueHandling = NullValueHandling.Ignore)] public float? Confidence;
        // v1.1 (§8.3): hint that the agent should correlate current sight/sound with this utterance.
        [JsonProperty("attach_perception", NullValueHandling = NullValueHandling.Ignore)] public bool? AttachPerception;

        public TextPayload() { }
        public TextPayload(string text, float? confidence = null) { Text = text; Confidence = confidence; }
    }

    // §5.4 agent.thinking
    public class AgentThinking
    {
        [JsonProperty("stage")] public string Stage;
        [JsonProperty("label", NullValueHandling = NullValueHandling.Ignore)] public string Label;
        [JsonProperty("tool", NullValueHandling = NullValueHandling.Ignore)] public string Tool;
        // v1.2 (§9): attribute a thinking step to a specific agent in the team.
        [JsonProperty("agent_id", NullValueHandling = NullValueHandling.Ignore)] public string AgentId;
        [JsonProperty("role", NullValueHandling = NullValueHandling.Ignore)] public string Role;
        [JsonProperty("skill", NullValueHandling = NullValueHandling.Ignore)] public string Skill;
    }

    // §5.5 agent.speech
    public class AgentSpeech
    {
        [JsonProperty("text")] public string Text;
        [JsonProperty("final")] public bool Final = true;
        [JsonProperty("emotion", NullValueHandling = NullValueHandling.Ignore)] public string Emotion;
    }

    // §5.8 holo.update (partial patch)
    public class HoloUpdate
    {
        [JsonProperty("object_id")] public string ObjectId;
        [JsonProperty("transform", NullValueHandling = NullValueHandling.Ignore)] public HoloTransform Transform;
        [JsonProperty("props", NullValueHandling = NullValueHandling.Ignore)] public JObject Props;
    }

    // §5.9 holo.destroy
    public class HoloDestroy
    {
        [JsonProperty("object_id")] public string ObjectId;
        [JsonProperty("fade_ms", NullValueHandling = NullValueHandling.Ignore)] public int FadeMs;
    }

    // §5.10 holo.layout
    public class HoloLayout
    {
        [JsonProperty("arrangement")] public string Arrangement = Arrangements.Arc;
        [JsonProperty("anchor", NullValueHandling = NullValueHandling.Ignore)] public string Anchor = Anchors.Head;
        [JsonProperty("objects")] public List<string> Objects = new List<string>();
        [JsonProperty("spacing", NullValueHandling = NullValueHandling.Ignore)] public float Spacing = 0.25f;
    }

    // §5.11 client.interaction
    public class ClientInteraction
    {
        [JsonProperty("object_id")] public string ObjectId;
        [JsonProperty("widget_type", NullValueHandling = NullValueHandling.Ignore)] public string WidgetType;
        // tap | grab | release | drag | slider | toggle | resize | dwell
        [JsonProperty("action")] public string Action;
        [JsonProperty("element", NullValueHandling = NullValueHandling.Ignore)] public string Element;
        [JsonProperty("value", NullValueHandling = NullValueHandling.Ignore)] public JObject Value;
        [JsonProperty("hand", NullValueHandling = NullValueHandling.Ignore)] public string Hand;
    }

    // §5.12 client.scene
    public class ClientScene
    {
        [JsonProperty("head")] public PosePayload Head;
        [JsonProperty("surfaces", NullValueHandling = NullValueHandling.Ignore)] public List<Surface> Surfaces;
        [JsonProperty("anchors", NullValueHandling = NullValueHandling.Ignore)] public List<AnchorPose> Anchors;
    }

    public class PosePayload
    {
        [JsonProperty("position")] public float[] Position;
        [JsonProperty("rotation")] public float[] Rotation;
    }

    public class Surface
    {
        [JsonProperty("id")] public string Id;
        [JsonProperty("type")] public string Type;
        [JsonProperty("center")] public float[] Center;
        [JsonProperty("normal")] public float[] Normal;
    }

    public class AnchorPose
    {
        [JsonProperty("id")] public string Id;
        [JsonProperty("position")] public float[] Position;
        [JsonProperty("rotation")] public float[] Rotation;
    }

    // §5.13 server.error / client.error
    public class ErrorPayload
    {
        [JsonProperty("code")] public string Code;
        [JsonProperty("message")] public string Message;
        [JsonProperty("fatal", NullValueHandling = NullValueHandling.Ignore)] public bool Fatal;
    }

    // client.ack / client.heartbeat / client.bye carry an empty object payload.
    public class EmptyPayload { }

    // §5.14 client.barge_in — the user started talking over Jarvis (interrupt active TTS/turn).
    public class BargePayload
    {
        [JsonProperty("reason", NullValueHandling = NullValueHandling.Ignore)] public string Reason;

        public BargePayload() { }
        public BargePayload(string reason) { Reason = reason; }
    }
}
