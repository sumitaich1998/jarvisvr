using System;
using System.Threading.Tasks;
using NativeWebSocket;
using UnityEngine;
using JarvisVR.Net;

namespace JarvisVR.Perception
{
    /// <summary>
    /// Binary WebSocket on ws://host:port/vision (docs/PROTOCOL.md §8.2). Carries length-prefixed
    /// JPEG frames ([4-byte BE len][JSON header][image bytes]) built by <see cref="VisionStreamer"/>.
    /// Connected only while vision streaming is active (privacy/bandwidth).
    /// </summary>
    [DisallowMultipleComponent]
    public class VisionChannel : MonoBehaviour
    {
        public JarvisConfig config;

        private WebSocket _ws;
        private bool _connecting;

        public bool IsOpen => _ws != null && _ws.State == WebSocketState.Open;

        public async void Connect()
        {
            if (config == null || IsOpen || _connecting) return;
            _connecting = true;
            try
            {
                _ws = new WebSocket(config.VisionUrl);
                _ws.OnError += e => Debug.LogWarning($"[Jarvis/vision] {e}");
                await _ws.Connect();
            }
            catch (Exception e)
            {
                Debug.LogWarning($"[Jarvis/vision] connect failed: {e.Message}");
            }
            finally { _connecting = false; }
        }

        public void Send(byte[] frame)
        {
            if (!IsOpen || frame == null || frame.Length == 0) return;
            _ = SendRaw(frame);
        }

        private async Task SendRaw(byte[] frame)
        {
            try { if (IsOpen) await _ws.Send(frame); }
            catch (Exception e) { Debug.LogWarning($"[Jarvis/vision] send failed: {e.Message}"); }
        }

        private void Update()
        {
#if !UNITY_WEBGL || UNITY_EDITOR
            _ws?.DispatchMessageQueue();
#endif
        }

        public async void Disconnect()
        {
            try { if (IsOpen) await _ws.Close(); }
            catch (Exception e) { Debug.LogWarning($"[Jarvis/vision] close: {e.Message}"); }
            _ws = null;
        }

        private void OnDestroy() => Disconnect();
    }
}
