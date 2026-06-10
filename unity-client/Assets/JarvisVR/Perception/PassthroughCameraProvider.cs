using System.Collections;
using UnityEngine;
using JarvisVR.Net;
using JarvisVR.Holograms;
using JarvisVR.Protocol;
#if UNITY_ANDROID && !UNITY_EDITOR
using UnityEngine.Android;
#endif

namespace JarvisVR.Perception
{
    /// <summary>A single captured passthrough frame: JPEG bytes + the camera pose at capture time.</summary>
    public struct VisionCaptureFrame
    {
        public byte[] Jpeg;
        public int Width;
        public int Height;
        public Vector3 Position;
        public Quaternion Rotation;
        public CameraIntrinsics Intrinsics; // null unless a pose source supplies it
        public long TimestampMs;
        public string Camera;
    }

    /// <summary>
    /// Optional accurate camera pose/intrinsics source (Meta Passthrough Camera API). Implemented by
    /// JarvisVR.Meta when <c>HAS_META_PCA</c> is defined; otherwise the head pose is used.
    /// </summary>
    public interface ICameraPoseSource
    {
        bool TryGetPose(out Vector3 position, out Quaternion rotation);
        CameraIntrinsics GetIntrinsics(int width, int height);
        string CameraId { get; }
    }

    /// <summary>
    /// Captures the forward RGB passthrough stream and JPEG-encodes downscaled frames on demand.
    ///
    /// On Quest 3/3S the Meta **Passthrough Camera API** exposes the cameras as a
    /// <see cref="WebCamTexture"/> device once the headset-camera permission is granted, so this uses
    /// WebCamTexture as the capture path (selected via <c>visionCameraNameHint</c>). In the editor it
    /// uses the default webcam, and with no camera it produces a synthetic frame so the pipeline is
    /// still testable. Accurate pose/intrinsics come from an optional <see cref="ICameraPoseSource"/>
    /// (Meta PCA, define-gated); otherwise the head pose is reported.
    ///
    /// Capture is pull-based: it only runs while <see cref="VisionStreamer"/> asks for frames.
    /// </summary>
    [DisallowMultipleComponent]
    public class PassthroughCameraProvider : MonoBehaviour
    {
        public JarvisConfig config;
        public AnchorService anchors;
        public ICameraPoseSource poseSource;

        /// <summary>True if a real passthrough/webcam is (or will be) available — used to advertise
        /// <c>camera_passthrough</c> truthfully. In the editor we allow synthetic frames for testing.</summary>
        public bool IsAvailable { get; private set; }
        public bool Running => _cam != null && _cam.isPlaying;
        public string CameraId => poseSource?.CameraId ?? CameraIds.RgbCenter;

        /// <summary>Live capture texture (the WebCamTexture) for an in-world preview (vision_feed),
        /// or null when not capturing. Read-only — do not modify.</summary>
        public Texture PreviewTexture => _cam;

        private WebCamTexture _cam;
        private Texture2D _readback;
        private Texture2D _synthetic;
        private bool _starting;
        private bool _permissionAsked;

        private void Awake()
        {
            if (anchors == null) anchors = FindObjectOfType<AnchorService>();
            IsAvailable = DetectAvailability();
        }

        private bool DetectAvailability()
        {
#if HAS_META_PCA
            return true;
#else
            if (WebCamTexture.devices != null && WebCamTexture.devices.Length > 0) return true;
            return Application.isEditor; // synthetic fallback for in-editor testing
#endif
        }

        public void StartCapture()
        {
            if (Running || _starting) return;
            _starting = true;
            StartCoroutine(StartRoutine());
        }

        private IEnumerator StartRoutine()
        {
            RequestPermissions();

            // Wait briefly for permission grants (non-blocking best effort).
            float t = 0f;
            while (t < 3f && !HasCameraPermission()) { t += Time.deltaTime; yield return null; }

            yield return Application.RequestUserAuthorization(UserAuthorization.WebCam);

            var device = PickDevice();
            if (!string.IsNullOrEmpty(device))
            {
                int req = Mathf.Clamp(config != null ? config.visionMaxResolution : 1024, 64, 2048);
                _cam = new WebCamTexture(device, req, req, 30);
                _cam.Play();
            }
            // else: no device → synthetic frames in TryCapture.
            _starting = false;
        }

        public void StopCapture()
        {
            if (_cam != null)
            {
                if (_cam.isPlaying) _cam.Stop();
                Destroy(_cam);
                _cam = null;
            }
        }

        /// <summary>Capture + JPEG-encode one frame at the requested resolution/quality.</summary>
        public bool TryCapture(int maxEdge, int jpegQuality, out VisionCaptureFrame frame)
        {
            frame = default;
            maxEdge = Mathf.Clamp(maxEdge, 64, 2048);
            jpegQuality = Mathf.Clamp(jpegQuality, 10, 100);

            byte[] jpeg;
            int w, h;

            if (_cam != null && _cam.isPlaying && _cam.width > 16)
            {
                if (!_cam.didUpdateThisFrame) return false;
                EncodeFromWebcam(maxEdge, jpegQuality, out jpeg, out w, out h);
            }
            else if (Application.isEditor || _cam == null)
            {
                EncodeSynthetic(Mathf.Min(maxEdge, 256), jpegQuality, out jpeg, out w, out h);
            }
            else
            {
                return false;
            }

            if (jpeg == null) return false;

            ResolvePose(out var pos, out var rot);
            frame = new VisionCaptureFrame
            {
                Jpeg = jpeg,
                Width = w,
                Height = h,
                Position = pos,
                Rotation = rot,
                Intrinsics = poseSource != null ? poseSource.GetIntrinsics(w, h) : null,
                TimestampMs = System.DateTimeOffset.UtcNow.ToUnixTimeMilliseconds(),
                Camera = CameraId,
            };
            return true;
        }

        private void EncodeFromWebcam(int maxEdge, int quality, out byte[] jpeg, out int outW, out int outH)
        {
            int sw = _cam.width, sh = _cam.height;
            float scale = Mathf.Min(1f, maxEdge / (float)Mathf.Max(sw, sh));
            outW = Mathf.Max(1, Mathf.RoundToInt(sw * scale));
            outH = Mathf.Max(1, Mathf.RoundToInt(sh * scale));

            var rt = RenderTexture.GetTemporary(outW, outH, 0, RenderTextureFormat.ARGB32);
            // Correct WebCamTexture vertical mirroring while blitting.
            var scaleVec = new Vector2(1f, _cam.videoVerticallyMirrored ? -1f : 1f);
            var offset = new Vector2(0f, _cam.videoVerticallyMirrored ? 1f : 0f);
            Graphics.Blit(_cam, rt, scaleVec, offset);

            EnsureReadback(outW, outH);
            var prev = RenderTexture.active;
            RenderTexture.active = rt;
            _readback.ReadPixels(new Rect(0, 0, outW, outH), 0, 0, false);
            _readback.Apply(false);
            RenderTexture.active = prev;
            RenderTexture.ReleaseTemporary(rt);

            jpeg = _readback.EncodeToJPG(quality);
        }

        private void EncodeSynthetic(int edge, int quality, out byte[] jpeg, out int outW, out int outH)
        {
            edge = Mathf.Clamp(edge, 64, 512);
            outW = outH = edge;
            if (_synthetic == null || _synthetic.width != edge)
                _synthetic = new Texture2D(edge, edge, TextureFormat.RGB24, false);

            float ph = Time.time * 0.5f;
            var px = new Color32[edge * edge];
            for (int y = 0; y < edge; y++)
            for (int x = 0; x < edge; x++)
            {
                float u = x / (float)edge, v = y / (float)edge;
                byte r = (byte)(Mathf.Sin((u + ph) * 6.28f) * 90 + 110);
                byte g = (byte)(v * 200 + 30);
                byte b = (byte)(Mathf.Cos((v - ph) * 6.28f) * 90 + 120);
                px[y * edge + x] = new Color32(r, g, b, 255);
            }
            _synthetic.SetPixels32(px);
            _synthetic.Apply(false);
            jpeg = _synthetic.EncodeToJPG(quality);
        }

        private void EnsureReadback(int w, int h)
        {
            if (_readback == null || _readback.width != w || _readback.height != h)
                _readback = new Texture2D(w, h, TextureFormat.RGB24, false);
        }

        private void ResolvePose(out Vector3 pos, out Quaternion rot)
        {
            if (poseSource != null && poseSource.TryGetPose(out pos, out rot)) return;
            var head = anchors != null ? anchors.FallbackHead() : (Camera.main != null ? Camera.main.transform : null);
            if (head != null) { pos = head.position; rot = head.rotation; }
            else { pos = Vector3.zero; rot = Quaternion.identity; }
        }

        private string PickDevice()
        {
            var devices = WebCamTexture.devices;
            if (devices == null || devices.Length == 0) return null;
            string hint = config != null ? config.visionCameraNameHint : null;
            if (!string.IsNullOrEmpty(hint))
                foreach (var d in devices)
                    if (!string.IsNullOrEmpty(d.name) && d.name.ToLowerInvariant().Contains(hint.ToLowerInvariant()))
                        return d.name;
            return devices[0].name;
        }

        private void RequestPermissions()
        {
            if (_permissionAsked) return;
            _permissionAsked = true;
#if UNITY_ANDROID && !UNITY_EDITOR
            if (!Permission.HasUserAuthorizedPermission(Permission.Camera))
                Permission.RequestUserPermission(Permission.Camera);
            // Quest-specific headset camera permission (Passthrough Camera API).
            const string headsetCamera = "horizonos.permission.HEADSET_CAMERA";
            if (!Permission.HasUserAuthorizedPermission(headsetCamera))
                Permission.RequestUserPermission(headsetCamera);
#endif
        }

        private bool HasCameraPermission()
        {
#if UNITY_ANDROID && !UNITY_EDITOR
            return Permission.HasUserAuthorizedPermission(Permission.Camera)
                || Permission.HasUserAuthorizedPermission("horizonos.permission.HEADSET_CAMERA");
#else
            return true;
#endif
        }

        private void OnDestroy() => StopCapture();
    }
}
