using UnityEngine;
using JarvisVR.Net;

namespace JarvisVR.Audio
{
    /// <summary>
    /// Captures the device microphone and streams 16-bit PCM frames to the optional /audio channel.
    /// Channels are down-mixed to mono. NOTE: this sends at the device's capture rate; the
    /// voice-service is expected to resample to 16 kHz if needed (a production build may add a
    /// resampler here). Disabled by default — enable via JarvisConfig.enableMicStreaming.
    /// </summary>
    [DisallowMultipleComponent]
    public class MicStreamer : MonoBehaviour
    {
        public JarvisConfig config;
        public AudioChannel channel;

        private AudioClip _clip;
        private string _device;
        private int _lastPos;
        private bool _running;

        private void Awake()
        {
            if (channel == null) channel = GetComponent<AudioChannel>();
        }

        private void Start()
        {
            if (config != null) channel?.SetConfig(config);
            if (config != null && config.enableMicStreaming) StartStreaming();
        }

        public void StartStreaming()
        {
            if (_running) return;
            if (Microphone.devices == null || Microphone.devices.Length == 0)
            {
                Debug.LogWarning("[Jarvis] no microphone device available.");
                return;
            }
            _device = null; // default device
            int rate = config != null ? config.micSampleRate : 16000;
            _clip = Microphone.Start(_device, true, 1, rate);
            _lastPos = 0;
            _running = true;
            channel?.Connect();
        }

        public void StopStreaming()
        {
            if (!_running) return;
            _running = false;
            Microphone.End(_device);
        }

        private void Update()
        {
            if (!_running || _clip == null) return;

            int pos = Microphone.GetPosition(_device);
            if (pos < 0 || pos == _lastPos) return;

            int count = pos - _lastPos;
            if (count < 0) count += _clip.samples; // wrapped
            if (count <= 0) return;

            var samples = new float[count * _clip.channels];
            _clip.GetData(samples, _lastPos);
            _lastPos = pos;

            channel?.SendPcm(FloatToPcm16(samples, _clip.channels));
        }

        private static byte[] FloatToPcm16(float[] s, int channels)
        {
            int frames = channels > 1 ? s.Length / channels : s.Length;
            var bytes = new byte[frames * 2];
            for (int i = 0; i < frames; i++)
            {
                float sample = channels > 1 ? AvgChannels(s, i, channels) : s[i];
                short v = (short)Mathf.Clamp(Mathf.RoundToInt(sample * 32767f), short.MinValue, short.MaxValue);
                bytes[i * 2] = (byte)(v & 0xff);
                bytes[i * 2 + 1] = (byte)((v >> 8) & 0xff);
            }
            return bytes;
        }

        private static float AvgChannels(float[] s, int frame, int ch)
        {
            float sum = 0f;
            for (int c = 0; c < ch; c++) sum += s[frame * ch + c];
            return sum / ch;
        }

        private void OnDestroy() => StopStreaming();
    }
}
