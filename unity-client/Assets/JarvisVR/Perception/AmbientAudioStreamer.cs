using System;
using UnityEngine;
using JarvisVR.Net;
using JarvisVR.Audio;

namespace JarvisVR.Perception
{
    /// <summary>
    /// Continuous ambient room-audio capture for perception (docs/PROTOCOL.md §8 / FEATURES §1),
    /// distinct from the wake-word/STT mic path (<see cref="MicStreamer"/>). Streams mono 16 kHz
    /// PCM16 to the /audio channel (the voice-service consumes it for ambient transcript + sound
    /// events, which it emits as <c>perception.audio_*</c>). Pull-based: only captures while active.
    /// Emits an RMS level for the privacy indicator / music_visualizer.
    /// </summary>
    [DisallowMultipleComponent]
    public class AmbientAudioStreamer : MonoBehaviour
    {
        public JarvisConfig config;
        public AudioChannel channel;

        public bool Active { get; private set; }
        public float Level { get; private set; }   // 0..1 RMS of the last window
        public event Action<float> OnLevel;

        private AudioClip _clip;
        private string _device;
        private int _lastPos;
        private int _srcRate;
        private int _dstRate = 16000;

        private void Awake()
        {
            if (channel == null) channel = FindObjectOfType<AudioChannel>();
        }

        public void StartCapture()
        {
            if (Active) return;
            if (Microphone.devices == null || Microphone.devices.Length == 0)
            {
                Debug.LogWarning("[Jarvis] ambient audio: no microphone device.");
                return;
            }
            if (config != null) channel?.SetConfig(config);
            _dstRate = config != null ? config.ambientSampleRate : 16000;
            _device = null;
            // Capture at a device-friendly rate; we resample to _dstRate before sending.
            _srcRate = 48000;
            _clip = Microphone.Start(_device, true, 1, _srcRate);
            _srcRate = _clip != null ? _clip.frequency : _srcRate;
            _lastPos = 0;
            Active = true;
            channel?.Connect();
        }

        public void StopCapture()
        {
            if (!Active) return;
            Active = false;
            Microphone.End(_device);
            Level = 0f;
        }

        private void Update()
        {
            if (!Active || _clip == null) return;

            int pos = Microphone.GetPosition(_device);
            if (pos < 0 || pos == _lastPos) return;

            int count = pos - _lastPos;
            if (count < 0) count += _clip.samples;
            if (count <= 0) return;

            int ch = _clip.channels;
            var raw = new float[count * ch];
            _clip.GetData(raw, _lastPos);
            _lastPos = pos;

            var mono = ch > 1 ? DownmixMono(raw, ch) : raw;
            Level = Rms(mono);
            OnLevel?.Invoke(Level);

            var resampled = (_srcRate == _dstRate) ? mono : Resample(mono, _srcRate, _dstRate);
            channel?.SendPcm(FloatToPcm16(resampled));
        }

        private static float[] DownmixMono(float[] s, int ch)
        {
            int frames = s.Length / ch;
            var m = new float[frames];
            for (int i = 0; i < frames; i++)
            {
                float sum = 0f;
                for (int c = 0; c < ch; c++) sum += s[i * ch + c];
                m[i] = sum / ch;
            }
            return m;
        }

        private static float[] Resample(float[] src, int srcRate, int dstRate)
        {
            if (src.Length == 0 || srcRate <= 0 || dstRate <= 0) return src;
            int dstCount = Mathf.Max(1, (int)((long)src.Length * dstRate / srcRate));
            var dst = new float[dstCount];
            double step = (double)srcRate / dstRate;
            for (int i = 0; i < dstCount; i++)
            {
                double sp = i * step;
                int i0 = (int)sp;
                int i1 = Mathf.Min(i0 + 1, src.Length - 1);
                float frac = (float)(sp - i0);
                dst[i] = Mathf.Lerp(src[i0], src[i1], frac);
            }
            return dst;
        }

        private static float Rms(float[] s)
        {
            if (s.Length == 0) return 0f;
            double sum = 0;
            for (int i = 0; i < s.Length; i++) sum += s[i] * (double)s[i];
            return Mathf.Clamp01((float)Math.Sqrt(sum / s.Length) * 4f);
        }

        private static byte[] FloatToPcm16(float[] s)
        {
            var bytes = new byte[s.Length * 2];
            for (int i = 0; i < s.Length; i++)
            {
                short v = (short)Mathf.Clamp(Mathf.RoundToInt(s[i] * 32767f), short.MinValue, short.MaxValue);
                bytes[i * 2] = (byte)(v & 0xff);
                bytes[i * 2 + 1] = (byte)((v >> 8) & 0xff);
            }
            return bytes;
        }

        private void OnDestroy() => StopCapture();
    }
}
