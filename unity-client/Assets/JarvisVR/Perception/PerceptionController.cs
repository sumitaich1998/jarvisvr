using UnityEngine;
using TMPro;
using JarvisVR.Net;
using JarvisVR.Protocol;
using JarvisVR.Holograms;

namespace JarvisVR.Perception
{
    /// <summary>
    /// Orchestrates v1.1 perception (docs/PROTOCOL.md §8 + FEATURES §1/§7):
    /// • handles inbound <c>perception.request</c> (start/stop/once/set) per stream,
    /// • maintains and emits <c>perception.state</c> (active streams + thermal + battery),
    /// • shows a visible **capture indicator** whenever camera/mic is active (privacy),
    /// • enforces an fps + thermal guard on vision,
    /// • advertises camera/audio/eye capabilities truthfully in the hello handshake.
    /// All capture is pull-based and runs only while a stream is active.
    /// </summary>
    [DefaultExecutionOrder(-90)] // set capability override before the connection's hello (Start)
    [DisallowMultipleComponent]
    public class PerceptionController : MonoBehaviour
    {
        public JarvisConfig config;
        public JarvisConnection connection;
        public VisionStreamer vision;
        public AmbientAudioStreamer ambientAudio;
        public GazeProvider gaze;
        public PassthroughCameraProvider cameraProvider;
        public Transform follow; // head, for the indicator

        public string Thermal { get; private set; } = ThermalStates.Nominal;
        public bool VisionActive => vision != null && vision.Active;
        public bool AmbientActive => ambientAudio != null && ambientAudio.Active;
        public bool GazeActive => gaze != null && gaze.Active;

        private Transform _indicator;
        private Renderer _indicatorDot;
        private TextMeshPro _indicatorLabel;
        private float _stateAccum;
        private string _lastStateHash;

        private void Awake()
        {
            if (connection == null) connection = FindObjectOfType<JarvisConnection>();
            if (vision == null) vision = FindObjectOfType<VisionStreamer>();
            if (ambientAudio == null) ambientAudio = FindObjectOfType<AmbientAudioStreamer>();
            if (gaze == null) gaze = FindObjectOfType<GazeProvider>();
            if (cameraProvider == null) cameraProvider = FindObjectOfType<PassthroughCameraProvider>();

            // Advertise v1.1 capabilities truthfully (evaluated at hello time so optional providers
            // like Meta eye gaze have registered), without mutating the shared config asset.
            if (connection != null) connection.CapabilityProvider = BuildTruthfulCapabilities;

            if (config == null || config.showCaptureIndicator) BuildIndicator();
        }

        private void OnEnable()
        {
            if (connection != null) connection.Router.On(MessageTypes.PerceptionRequest, HandleRequest);
        }

        private void OnDisable()
        {
            if (connection != null) connection.Router.Off(MessageTypes.PerceptionRequest, HandleRequest);
        }

        private Capabilities BuildTruthfulCapabilities()
        {
            var caps = config != null ? config.BuildCapabilities() : new Capabilities();
            bool cameraOk = cameraProvider != null && cameraProvider.IsAvailable;
            bool micOk = Microphone.devices != null && Microphone.devices.Length > 0;
            bool eyesOk = gaze != null && gaze.eyeSource != null && gaze.eyeSource.IsAvailable;

            caps.CameraPassthrough = caps.CameraPassthrough && cameraOk;
            caps.AmbientAudio = caps.AmbientAudio && micOk;
            caps.EyeTracking = caps.EyeTracking && eyesOk;
            return caps;
        }

        // ---- inbound perception.request -----------------------------------------------------

        private void HandleRequest(Envelope env)
        {
            var req = env.PayloadAs<PerceptionRequest>();
            if (req == null || string.IsNullOrEmpty(req.Stream)) return;

            switch (req.Stream)
            {
                case PerceptionStreams.Vision: HandleVision(req); break;
                case PerceptionStreams.AmbientAudio: HandleAmbient(req); break;
                case PerceptionStreams.Gaze: HandleGaze(req); break;
                case PerceptionStreams.SceneObjects:
                    // on_device_vision not implemented client-side; ignore politely.
                    Debug.Log("[Jarvis] perception.request scene_objects ignored (no on-device detection).");
                    break;
                default:
                    Debug.Log($"[Jarvis] unknown perception stream '{req.Stream}'.");
                    break;
            }
            EmitState(force: true);
        }

        private void HandleVision(PerceptionRequest req)
        {
            if (vision == null) return;
            switch (req.Action)
            {
                case PerceptionActions.Start: vision.StartStream(req.Fps, req.Quality, req.MaxResolution); break;
                case PerceptionActions.Stop: vision.StopStream(); break;
                case PerceptionActions.Once: vision.CaptureOnce(req.Quality, req.MaxResolution); break;
                case PerceptionActions.Set: vision.SetParams(req.Fps, req.Quality, req.MaxResolution); break;
            }
            connection.AttachPerceptionDefault = vision.Active; // §8.3 default true while vision active
        }

        private void HandleAmbient(PerceptionRequest req)
        {
            if (ambientAudio == null) return;
            if (req.Action == PerceptionActions.Stop) ambientAudio.StopCapture();
            else ambientAudio.StartCapture(); // start | once | set all imply "listening"
        }

        private void HandleGaze(PerceptionRequest req)
        {
            if (gaze == null) return;
            if (req.Action == PerceptionActions.Stop) gaze.StopStream();
            else gaze.StartStream();
        }

        // ---- user-facing privacy controls (wrist menu) --------------------------------------

        public void ToggleVision()
        {
            if (vision == null) return;
            if (vision.Active) vision.StopStream(); else vision.StartStream(null, null, null);
            connection.AttachPerceptionDefault = vision.Active;
            EmitState(force: true);
        }

        public void ToggleAmbient()
        {
            if (ambientAudio == null) return;
            if (ambientAudio.Active) ambientAudio.StopCapture(); else ambientAudio.StartCapture();
            EmitState(force: true);
        }

        /// <summary>Hard privacy stop: kill every capture stream immediately.</summary>
        public void StopAllCapture()
        {
            vision?.StopStream();
            ambientAudio?.StopCapture();
            gaze?.StopStream();
            if (connection != null) connection.AttachPerceptionDefault = false;
            EmitState(force: true);
        }

        /// <summary>Allow a native/thermal provider to report the current thermal level.</summary>
        public void SetThermal(string thermal)
        {
            if (!string.IsNullOrEmpty(thermal)) Thermal = thermal;
        }

        // ---- per-frame: guard, indicator, periodic state ------------------------------------

        private void Update()
        {
            ApplyThermalGuard();
            UpdateIndicator();

            _stateAccum += Time.deltaTime;
            float interval = config != null ? config.perceptionStateInterval : 3f;
            if (_stateAccum >= interval) { _stateAccum = 0f; EmitState(force: false); }
        }

        private void ApplyThermalGuard()
        {
            if (config == null || !config.thermalFpsGuard || vision == null || !vision.Active) return;
            switch (Thermal)
            {
                case ThermalStates.Serious: vision.ClampFps(1f); break;
                case ThermalStates.Critical: vision.StopStream(); break; // protect the device
            }
        }

        private void EmitState(bool force)
        {
            if (connection == null || connection.State != ConnectionState.Connected) return;

            var state = new PerceptionState
            {
                Vision = new VisionState
                {
                    Active = VisionActive,
                    Fps = vision != null ? vision.Fps : 0f,
                    Resolution = vision != null ? vision.ResolutionLabel : null,
                    Camera = vision != null ? vision.Camera : null,
                },
                AmbientAudio = new StreamActive { Active = AmbientActive },
                Gaze = new StreamActive { Active = GazeActive },
                Thermal = Thermal,
                Battery = SystemInfo.batteryLevel < 0 ? 1f : SystemInfo.batteryLevel,
            };

            // Avoid spamming identical state unless forced.
            string hash = $"{state.Vision.Active}{state.Vision.Fps}{state.AmbientAudio.Active}{state.Gaze.Active}{state.Thermal}";
            if (!force && hash == _lastStateHash) return;
            _lastStateHash = hash;
            connection.Send(MessageTypes.PerceptionState, state);
        }

        // ---- capture indicator (privacy) ----------------------------------------------------

        private void BuildIndicator()
        {
            var root = new GameObject("CaptureIndicator");
            root.transform.SetParent(transform, false);
            _indicator = root.transform;

            var dot = GameObject.CreatePrimitive(PrimitiveType.Sphere);
            dot.name = "dot";
            var col = dot.GetComponent<Collider>();
            if (col != null) Destroy(col);
            dot.transform.SetParent(_indicator, false);
            dot.transform.localScale = Vector3.one * 0.018f;
            _indicatorDot = dot.GetComponent<Renderer>();
            _indicatorDot.material = HoloMaterials.Solid(new Color(1f, 0.2f, 0.2f));

            var lblGo = new GameObject("label");
            lblGo.transform.SetParent(_indicator, false);
            lblGo.transform.localPosition = new Vector3(0.05f, 0f, 0f);
            _indicatorLabel = lblGo.AddComponent<TextMeshPro>();
            _indicatorLabel.fontSize = 0.02f;
            _indicatorLabel.alignment = TextAlignmentOptions.Left;
            _indicatorLabel.color = new Color(1f, 0.85f, 0.85f);
            _indicatorLabel.rectTransform.sizeDelta = new Vector2(0.3f, 0.03f);

            _indicator.gameObject.SetActive(false);
        }

        private void UpdateIndicator()
        {
            if (_indicator == null) return;
            bool capturing = VisionActive || AmbientActive;
            if (_indicator.gameObject.activeSelf != capturing) _indicator.gameObject.SetActive(capturing);
            if (!capturing) return;

            var head = follow != null ? follow : (Camera.main != null ? Camera.main.transform : null);
            if (head != null)
            {
                // top-center of view
                _indicator.position = head.position + head.forward * 0.5f + head.up * 0.18f - head.right * 0.12f;
                _indicator.rotation = Quaternion.LookRotation(_indicator.position - head.position);
            }

            // blink + label
            float blink = (Mathf.Sin(Time.time * 6f) * 0.5f + 0.5f);
            if (_indicatorDot != null)
                HoloMaterials.SetAlbedo(_indicatorDot.material, new Color(1f, 0.2f * blink + 0.1f, 0.2f * blink + 0.1f));
            if (_indicatorLabel != null)
                _indicatorLabel.text = VisionActive && AmbientActive ? "REC ● MIC"
                                     : VisionActive ? "REC" : "MIC";
        }
    }
}
