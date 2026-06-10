using System.Collections.Generic;
using Newtonsoft.Json;

namespace JarvisVR.Protocol
{
    // ---------------------------------------------------------------------------------------------
    // v1.1 Multimodal Perception payloads (docs/PROTOCOL.md §8.4).
    // Additive + optional; tolerant of missing/extra fields (forward-compatible).
    // ---------------------------------------------------------------------------------------------

    /// <summary>§8.4 perception.vision_frame. For binary transport this object (minus <see cref="Data"/>)
    /// is the JSON header on /vision (§8.2); for inline transport <see cref="Data"/> is base64 JPEG.</summary>
    public class VisionFrame
    {
        [JsonProperty("frame_id")] public string FrameId;
        [JsonProperty("camera")] public string Camera = CameraIds.RgbCenter;
        [JsonProperty("format")] public string Format = "jpeg";
        [JsonProperty("width")] public int Width;
        [JsonProperty("height")] public int Height;
        [JsonProperty("quality")] public int Quality = 70;
        [JsonProperty("transport")] public string Transport = VisionTransports.Inline;
        [JsonProperty("data", NullValueHandling = NullValueHandling.Ignore)] public string Data; // base64 iff inline
        [JsonProperty("seq")] public long Seq;
        [JsonProperty("ts_capture")] public long TsCapture;
        [JsonProperty("pose", NullValueHandling = NullValueHandling.Ignore)] public PosePayload Pose;
        [JsonProperty("intrinsics", NullValueHandling = NullValueHandling.Ignore)] public CameraIntrinsics Intrinsics;
    }

    public class CameraIntrinsics
    {
        [JsonProperty("fx")] public float Fx;
        [JsonProperty("fy")] public float Fy;
        [JsonProperty("cx")] public float Cx;
        [JsonProperty("cy")] public float Cy;
    }

    /// <summary>§8.4 perception.audio_event.</summary>
    public class AudioEvent
    {
        [JsonProperty("label")] public string Label;
        [JsonProperty("confidence")] public float Confidence;
        [JsonProperty("ts")] public long Ts;
        [JsonProperty("loudness_db", NullValueHandling = NullValueHandling.Ignore)] public float LoudnessDb;
    }

    /// <summary>§8.4 perception.audio_scene.</summary>
    public class AudioScene
    {
        [JsonProperty("ambient_transcript", NullValueHandling = NullValueHandling.Ignore)] public string AmbientTranscript;
        [JsonProperty("speaker", NullValueHandling = NullValueHandling.Ignore)] public string Speaker; // user | other | unknown
        [JsonProperty("sounds", NullValueHandling = NullValueHandling.Ignore)] public List<SoundLabel> Sounds;
        [JsonProperty("loudness_db", NullValueHandling = NullValueHandling.Ignore)] public float LoudnessDb;
        [JsonProperty("window_ms", NullValueHandling = NullValueHandling.Ignore)] public int WindowMs;
    }

    public class SoundLabel
    {
        [JsonProperty("label")] public string Label;
        [JsonProperty("confidence")] public float Confidence;
    }

    /// <summary>§8.4 perception.gaze.</summary>
    public class GazePayload
    {
        [JsonProperty("source")] public string Source = GazeSources.Head;   // eyes | head
        [JsonProperty("origin")] public float[] Origin;
        [JsonProperty("direction")] public float[] Direction;
        [JsonProperty("hit_object_id", NullValueHandling = NullValueHandling.Ignore)] public string HitObjectId;
        [JsonProperty("hit_point", NullValueHandling = NullValueHandling.Ignore)] public float[] HitPoint;
        [JsonProperty("dwell_ms", NullValueHandling = NullValueHandling.Ignore)] public int DwellMs;
    }

    /// <summary>§8.4 perception.scene_objects (optional, client-side detection).</summary>
    public class SceneObjects
    {
        [JsonProperty("frame_id", NullValueHandling = NullValueHandling.Ignore)] public string FrameId;
        [JsonProperty("objects")] public List<DetectedObject> Objects = new List<DetectedObject>();
    }

    public class DetectedObject
    {
        [JsonProperty("label")] public string Label;
        [JsonProperty("confidence")] public float Confidence;
        [JsonProperty("bbox", NullValueHandling = NullValueHandling.Ignore)] public int[] Bbox; // [x,y,w,h] in image px
        [JsonProperty("position", NullValueHandling = NullValueHandling.Ignore)] public float[] Position;
        [JsonProperty("anchor", NullValueHandling = NullValueHandling.Ignore)] public string Anchor = Anchors.World;
    }

    /// <summary>§8.4 perception.state — what is currently being captured + device health.</summary>
    public class PerceptionState
    {
        [JsonProperty("vision")] public VisionState Vision = new VisionState();
        [JsonProperty("ambient_audio")] public StreamActive AmbientAudio = new StreamActive();
        [JsonProperty("gaze")] public StreamActive Gaze = new StreamActive();
        [JsonProperty("thermal")] public string Thermal = ThermalStates.Nominal;
        [JsonProperty("battery")] public float Battery = 1f;
    }

    public class StreamActive
    {
        [JsonProperty("active")] public bool Active;
    }

    public class VisionState
    {
        [JsonProperty("active")] public bool Active;
        [JsonProperty("fps", NullValueHandling = NullValueHandling.Ignore)] public float Fps;
        [JsonProperty("resolution", NullValueHandling = NullValueHandling.Ignore)] public string Resolution;
        [JsonProperty("camera", NullValueHandling = NullValueHandling.Ignore)] public string Camera;
    }

    /// <summary>§8.4 perception.request (server → client). Pull-based stream control.</summary>
    public class PerceptionRequest
    {
        [JsonProperty("stream")] public string Stream;   // vision | ambient_audio | gaze | scene_objects
        [JsonProperty("action")] public string Action;   // start | stop | once | set
        [JsonProperty("fps", NullValueHandling = NullValueHandling.Ignore)] public float? Fps;
        [JsonProperty("max_resolution", NullValueHandling = NullValueHandling.Ignore)] public string MaxResolution;
        [JsonProperty("quality", NullValueHandling = NullValueHandling.Ignore)] public int? Quality;
        [JsonProperty("duration_ms", NullValueHandling = NullValueHandling.Ignore)] public int? DurationMs;
        [JsonProperty("reason", NullValueHandling = NullValueHandling.Ignore)] public string Reason;
    }

    /// <summary>§8.4 agent.observation (server → client). Narration + optional spatial annotations.</summary>
    public class AgentObservation
    {
        [JsonProperty("text")] public string Text;
        [JsonProperty("final")] public bool Final = true;
        [JsonProperty("annotations", NullValueHandling = NullValueHandling.Ignore)] public List<Annotation> Annotations;
    }

    public class Annotation
    {
        [JsonProperty("label")] public string Label;
        [JsonProperty("object_id", NullValueHandling = NullValueHandling.Ignore)] public string ObjectId;
        [JsonProperty("position", NullValueHandling = NullValueHandling.Ignore)] public float[] Position;
        [JsonProperty("anchor", NullValueHandling = NullValueHandling.Ignore)] public string Anchor = Anchors.World;
    }
}
