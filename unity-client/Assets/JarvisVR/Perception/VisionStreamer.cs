using System;
using System.Text;
using UnityEngine;
using Newtonsoft.Json;
using JarvisVR.Net;
using JarvisVR.Protocol;
using JarvisVR.Util;

namespace JarvisVR.Perception
{
    /// <summary>
    /// Pull-based passthrough-vision streamer (docs/PROTOCOL.md §8). Streams JPEG frames + camera
    /// pose ONLY while the server has requested vision (privacy). Sends length-prefixed binary on
    /// /vision when available, else inline base64 <c>perception.vision_frame</c> on the main channel.
    /// Honors fps / quality / max_resolution from <c>perception.request</c>, clamped by JarvisConfig.
    /// </summary>
    [DisallowMultipleComponent]
    public class VisionStreamer : MonoBehaviour
    {
        public JarvisConfig config;
        public JarvisConnection connection;
        public PassthroughCameraProvider provider;
        public VisionChannel visionChannel;

        public bool Active { get; private set; }
        public float Fps => _fps;
        public string ResolutionLabel => $"{_maxEdge}x{_maxEdge}";
        public string Camera => provider != null ? provider.CameraId : CameraIds.RgbCenter;

        private float _fps = 2f;
        private int _quality = 70;
        private int _maxEdge = 1024;
        private long _seq;
        private float _accum;
        private bool _oncePending;

        private void Awake()
        {
            if (connection == null) connection = FindObjectOfType<JarvisConnection>();
            if (provider == null) provider = FindObjectOfType<PassthroughCameraProvider>();
            if (visionChannel == null) visionChannel = FindObjectOfType<VisionChannel>();
            if (config != null) { _fps = config.visionDefaultFps; _quality = config.visionJpegQuality; _maxEdge = config.visionMaxResolution; }
        }

        public void StartStream(float? fps, int? quality, string maxResolution)
        {
            ApplyParams(fps, quality, maxResolution);
            Active = true;
            _accum = 999f; // capture promptly
            provider?.StartCapture();
            if (PreferBinary) visionChannel?.Connect();
        }

        public void StopStream()
        {
            Active = false;
            if (!_oncePending)
            {
                provider?.StopCapture();
                visionChannel?.Disconnect();
            }
        }

        public void SetParams(float? fps, int? quality, string maxResolution) => ApplyParams(fps, quality, maxResolution);

        public void CaptureOnce(int? quality, string maxResolution)
        {
            ApplyParams(null, quality, maxResolution);
            _oncePending = true;
            provider?.StartCapture();
            if (PreferBinary) visionChannel?.Connect();
        }

        private bool PreferBinary => config != null && config.visionPreferBinary;

        private void ApplyParams(float? fps, int? quality, string maxResolution)
        {
            float maxFps = config != null ? config.visionMaxFps : 5f;
            if (fps.HasValue) _fps = Mathf.Clamp(fps.Value, 0.2f, maxFps);
            if (quality.HasValue) _quality = Mathf.Clamp(quality.Value, 10, 100);
            int cap = config != null ? config.visionMaxResolution : 1024;
            if (!string.IsNullOrEmpty(maxResolution)) _maxEdge = Mathf.Min(cap, ParseEdge(maxResolution, cap));
            else _maxEdge = Mathf.Min(cap, _maxEdge);
        }

        /// <summary>Allow the thermal/fps guard to clamp the effective rate.</summary>
        public void ClampFps(float maxFps)
        {
            if (maxFps > 0f && _fps > maxFps) _fps = maxFps;
        }

        private void Update()
        {
            if (!Active && !_oncePending) return;
            if (provider == null || connection == null) return;

            _accum += Time.deltaTime;
            float interval = Active ? 1f / Mathf.Max(0.2f, _fps) : 0f;
            if (_accum < interval) return;

            if (!provider.TryCapture(_maxEdge, _quality, out var frame)) return;
            _accum = 0f;
            SendFrame(frame);

            if (_oncePending)
            {
                _oncePending = false;
                if (!Active) { provider.StopCapture(); visionChannel?.Disconnect(); }
            }
        }

        private void SendFrame(VisionCaptureFrame f)
        {
            var header = new VisionFrame
            {
                FrameId = Guid.NewGuid().ToString(),
                Camera = f.Camera,
                Format = "jpeg",
                Width = f.Width,
                Height = f.Height,
                Quality = _quality,
                Seq = ++_seq,
                TsCapture = f.TimestampMs,
                Pose = new PosePayload { Position = f.Position.ToArray(), Rotation = f.Rotation.ToArray() },
                Intrinsics = f.Intrinsics,
            };

            bool binarySent = false;
            if (PreferBinary && visionChannel != null && visionChannel.IsOpen)
            {
                header.Transport = VisionTransports.Binary; // data omitted
                visionChannel.Send(BuildBinaryFrame(header, f.Jpeg));
                binarySent = true;
            }

            if (!binarySent)
            {
                header.Transport = VisionTransports.Inline;
                header.Data = Convert.ToBase64String(f.Jpeg);
                connection.Send(MessageTypes.PerceptionVisionFrame, header);
            }
        }

        // [4-byte big-endian uint32 headerLen][header JSON][jpeg bytes]  (§8.2)
        internal static byte[] BuildBinaryFrame(VisionFrame header, byte[] jpeg)
        {
            string json = JsonConvert.SerializeObject(header, EnvelopeSerializer.Settings);
            byte[] headerBytes = Encoding.UTF8.GetBytes(json);
            uint len = (uint)headerBytes.Length;
            var buffer = new byte[4 + headerBytes.Length + jpeg.Length];
            buffer[0] = (byte)((len >> 24) & 0xff);
            buffer[1] = (byte)((len >> 16) & 0xff);
            buffer[2] = (byte)((len >> 8) & 0xff);
            buffer[3] = (byte)(len & 0xff);
            Buffer.BlockCopy(headerBytes, 0, buffer, 4, headerBytes.Length);
            Buffer.BlockCopy(jpeg, 0, buffer, 4 + headerBytes.Length, jpeg.Length);
            return buffer;
        }

        private static int ParseEdge(string res, int fallback)
        {
            if (string.IsNullOrEmpty(res)) return fallback;
            var parts = res.ToLowerInvariant().Split('x');
            int best = 0;
            foreach (var p in parts)
                if (int.TryParse(p.Trim(), out var n)) best = Mathf.Max(best, n);
            return best > 0 ? best : fallback;
        }
    }
}
