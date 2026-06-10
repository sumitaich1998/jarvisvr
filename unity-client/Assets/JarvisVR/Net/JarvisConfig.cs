using UnityEngine;
using JarvisVR.Protocol;

namespace JarvisVR.Net
{
    /// <summary>
    /// Connection + identity settings for the client, editable as an asset
    /// (Create &gt; JarvisVR &gt; Jarvis Config). Point <see cref="host"/>/<see cref="port"/> at the
    /// agent-backend (or the infra/ mock backend) before building/deploying.
    /// </summary>
    [CreateAssetMenu(fileName = "JarvisConfig", menuName = "JarvisVR/Jarvis Config", order = 0)]
    public class JarvisConfig : ScriptableObject
    {
        [Header("Backend endpoint")]
        [Tooltip("Hostname or IP of the agent-backend WebSocket server.")]
        public string host = "127.0.0.1";
        public int port = ProtocolConstants.DefaultPort;
        public string path = ProtocolConstants.DefaultPath;       // /jarvis
        public string audioPath = ProtocolConstants.AudioPath;    // /audio (optional PCM16)
        [Tooltip("Use wss:// instead of ws:// (TLS).")]
        public bool useTls = false;

        [Header("Client identity (client.hello)")]
        public string appVersion = "0.1.0";
        public string locale = "en-US";

        [Header("Advertised capabilities (client.hello)")]
        public bool capPassthrough = true;
        public bool capHandTracking = true;
        public bool capControllers = true;
        public bool capMic = true;
        public bool capSpeaker = true;
        public bool capSceneUnderstanding = true;

        [Header("v1.1 perception capabilities (client.hello §8.1)")]
        [Tooltip("RGB passthrough camera frames (Quest 3/3S Passthrough Camera API). Auto-corrected at runtime to what's actually available.")]
        public bool capCameraPassthrough = true;
        public bool capAmbientAudio = true;
        public bool capEyeTracking = false;
        public bool capOnDeviceVision = false;
        public bool capDepth = false;

        [Header("Connection behavior")]
        public float heartbeatSeconds = ProtocolConstants.HeartbeatSeconds;
        public bool autoReconnect = true;
        public float reconnectInitialDelay = 1f;
        public float reconnectMaxDelay = 30f;
        [Min(1f)] public float reconnectBackoffMultiplier = 2f;
        [Tooltip("Log every inbound/outbound envelope to the Console (verbose).")]
        public bool logTraffic = false;

        [Header("Audio channel (optional /audio PCM16)")]
        public bool enableMicStreaming = false;
        public int micSampleRate = 16000;

        [Header("Scene reporting (client.scene)")]
        public bool enableSceneReporting = true;
        [Min(0.5f)] public float sceneReportInterval = 2f;

        [Header("Perception — vision (§8.2 /vision)")]
        public string visionPath = ProtocolConstants.VisionPath;   // /vision
        [Tooltip("Prefer length-prefixed binary on /vision; falls back to inline base64 on the main channel.")]
        public bool visionPreferBinary = true;
        [Tooltip("Default frames/sec when the server starts vision without specifying.")]
        [Range(0.2f, 10f)] public float visionDefaultFps = 2f;
        [Range(1f, 10f)] public float visionMaxFps = 5f;
        [Range(10, 100)] public int visionJpegQuality = 70;
        [Tooltip("Longest image edge in pixels (frames are downscaled to fit, ≤1024 recommended).")]
        public int visionMaxResolution = 1024;
        [Tooltip("Substring used to pick the passthrough WebCamTexture device on-device (PCA).")]
        public string visionCameraNameHint = "passthrough";

        [Header("Perception — ambient audio")]
        public int ambientSampleRate = 16000;

        [Header("Perception — gaze")]
        [Range(1f, 20f)] public float gazeHz = 8f;
        [Min(0f)] public int gazeDwellThresholdMs = 400;
        public float gazeMaxDistance = 12f;

        [Header("Privacy & guards (§7)")]
        [Tooltip("Show a visible capture indicator whenever camera/mic is active.")]
        public bool showCaptureIndicator = true;
        [Tooltip("Throttle/stop vision when the device gets hot (perception.state thermal).")]
        public bool thermalFpsGuard = true;
        [Tooltip("Emit perception.state on change and at most this often (seconds).")]
        [Min(0.5f)] public float perceptionStateInterval = 3f;

        public string Scheme => useTls ? "wss" : "ws";
        public string MainUrl => $"{Scheme}://{host}:{port}{path}";
        public string AudioUrl => $"{Scheme}://{host}:{port}{audioPath}";
        public string VisionUrl => $"{Scheme}://{host}:{port}{visionPath}";

        public Capabilities BuildCapabilities() => new Capabilities
        {
            Passthrough = capPassthrough,
            HandTracking = capHandTracking,
            Controllers = capControllers,
            Mic = capMic,
            Speaker = capSpeaker,
            SceneUnderstanding = capSceneUnderstanding,
            CameraPassthrough = capCameraPassthrough,
            AmbientAudio = capAmbientAudio,
            EyeTracking = capEyeTracking,
            OnDeviceVision = capOnDeviceVision,
            Depth = capDepth,
        };
    }
}
