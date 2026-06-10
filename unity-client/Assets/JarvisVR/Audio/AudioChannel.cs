using System;
using System.Threading.Tasks;
using NativeWebSocket;
using UnityEngine;
using JarvisVR.Net;

namespace JarvisVR.Audio
{
    /// <summary>
    /// Optional parallel binary WebSocket on ws://host:port/audio (docs/PROTOCOL.md §1) carrying
    /// raw 16 kHz mono PCM16 frames. Outbound = mic frames (see <see cref="MicStreamer"/>); inbound
    /// = TTS PCM (see <see cref="SpeechPlayer"/>). JSON transcripts/speech still flow on the main
    /// channel. This channel is entirely optional — the stack works without it.
    /// </summary>
    [DisallowMultipleComponent]
    public class AudioChannel : MonoBehaviour
    {
        public JarvisConfig config;

        public event Action<byte[]> OnPcmReceived;

        private WebSocket _ws;
        private bool _intentional;

        public bool IsOpen => _ws != null && _ws.State == WebSocketState.Open;

        public void SetConfig(JarvisConfig c) => config = c;

        public async void Connect()
        {
            if (config == null || IsOpen) return;
            _intentional = false;
            try
            {
                _ws = new WebSocket(config.AudioUrl);
                _ws.OnMessage += b => OnPcmReceived?.Invoke(b);
                _ws.OnError += e => Debug.LogWarning($"[Jarvis/audio] {e}");
                await _ws.Connect();
            }
            catch (Exception e)
            {
                Debug.LogWarning($"[Jarvis/audio] connect failed: {e.Message}");
            }
        }

        public void SendPcm(byte[] pcm)
        {
            if (!IsOpen || pcm == null || pcm.Length == 0) return;
            _ = SendRaw(pcm);
        }

        private async Task SendRaw(byte[] pcm)
        {
            try { if (IsOpen) await _ws.Send(pcm); }
            catch (Exception e) { Debug.LogWarning($"[Jarvis/audio] send failed: {e.Message}"); }
        }

        private void Update()
        {
#if !UNITY_WEBGL || UNITY_EDITOR
            _ws?.DispatchMessageQueue();
#endif
        }

        public async void Disconnect()
        {
            _intentional = true;
            try { if (IsOpen) await _ws.Close(); }
            catch (Exception e) { Debug.LogWarning($"[Jarvis/audio] close: {e.Message}"); }
        }

        private void OnDestroy() => _intentional = true;
    }
}
