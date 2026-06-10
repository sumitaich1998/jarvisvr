using System.Collections.Generic;
using UnityEngine;
using JarvisVR.Net;

namespace JarvisVR.Audio
{
    /// <summary>
    /// Plays TTS audio if the backend streams PCM16 on the /audio channel. In the default topology
    /// the voice-service speaks directly, so this is optional; it exists so the client CAN render
    /// "Jarvis" speech when the backend chooses to send it. Feed bytes via the channel or
    /// <see cref="PlayPcm"/>.
    /// </summary>
    [RequireComponent(typeof(AudioSource))]
    [DisallowMultipleComponent]
    public class SpeechPlayer : MonoBehaviour
    {
        public AudioChannel channel;
        public JarvisConfig config;
        [Tooltip("Sample rate of inbound TTS PCM16 frames.")]
        public int playbackSampleRate = 24000;

        private AudioSource _source;
        private readonly Queue<float[]> _queue = new Queue<float[]>();

        private void Awake()
        {
            _source = GetComponent<AudioSource>();
            _source.playOnAwake = false;
            _source.spatialBlend = 0f;
            if (channel == null) channel = GetComponent<AudioChannel>();
        }

        private void OnEnable() { if (channel != null) channel.OnPcmReceived += Enqueue; }
        private void OnDisable() { if (channel != null) channel.OnPcmReceived -= Enqueue; }

        public void PlayPcm(byte[] pcm) => Enqueue(pcm);

        private void Enqueue(byte[] pcm)
        {
            if (pcm == null || pcm.Length < 2) return;
            _queue.Enqueue(Pcm16ToFloat(pcm));
        }

        private void Update()
        {
            if (_source.isPlaying || _queue.Count == 0) return;
            var samples = _queue.Dequeue();
            var clip = AudioClip.Create("tts", samples.Length, 1, playbackSampleRate, false);
            clip.SetData(samples, 0);
            _source.clip = clip;
            _source.Play();
        }

        private static float[] Pcm16ToFloat(byte[] b)
        {
            int n = b.Length / 2;
            var f = new float[n];
            for (int i = 0; i < n; i++)
            {
                short v = (short)(b[i * 2] | (b[i * 2 + 1] << 8));
                f[i] = v / 32768f;
            }
            return f;
        }

        // ---- text-to-speech (for agent.observation / on-device speech) ----------------------
        // The voice-service is the primary TTS path; this is an on-device fallback so the client can
        // speak narration (e.g. agent.observation) even without server audio. Uses Android's native
        // TextToSpeech on device; logs elsewhere.

        /// <summary>Speak text on-device (Android TTS) or log it in the editor.</summary>
        public void Speak(string text)
        {
            if (string.IsNullOrEmpty(text)) return;
#if UNITY_ANDROID && !UNITY_EDITOR
            EnsureTts();
            _pending = text;
            if (_ttsReady) Flush();
#else
            Debug.Log($"[Jarvis] (TTS) {text}");
#endif
        }

#if UNITY_ANDROID && !UNITY_EDITOR
        private AndroidJavaObject _tts;
        private bool _ttsReady;
        private string _pending;

        private void EnsureTts()
        {
            if (_tts != null) return;
            try
            {
                using (var player = new AndroidJavaClass("com.unity3d.player.UnityPlayer"))
                {
                    var activity = player.GetStatic<AndroidJavaObject>("currentActivity");
                    _tts = new AndroidJavaObject("android.speech.tts.TextToSpeech", activity, new TtsInitListener(this));
                }
            }
            catch (System.Exception e) { Debug.LogWarning($"[Jarvis] TTS init failed: {e.Message}"); }
        }

        private void OnTtsInit(int status)
        {
            _ttsReady = status == 0; // SUCCESS
            if (_ttsReady) Flush();
        }

        private void Flush()
        {
            if (_tts == null || string.IsNullOrEmpty(_pending)) return;
            try { _tts.Call<int>("speak", _pending, 0 /*QUEUE_FLUSH*/, null, "jarvis"); }
            catch (System.Exception e) { Debug.LogWarning($"[Jarvis] TTS speak failed: {e.Message}"); }
            _pending = null;
        }

        private void OnDestroy()
        {
            if (_tts != null) { try { _tts.Call("shutdown"); } catch { } _tts = null; }
        }

        private class TtsInitListener : AndroidJavaProxy
        {
            private readonly SpeechPlayer _owner;
            public TtsInitListener(SpeechPlayer owner) : base("android.speech.tts.TextToSpeech$OnInitListener") { _owner = owner; }
            public void onInit(int status) => _owner.OnTtsInit(status);
        }
#endif
    }
}
