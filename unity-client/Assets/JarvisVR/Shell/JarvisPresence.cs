using UnityEngine;
using TMPro;
using JarvisVR.Net;
using JarvisVR.Protocol;
using JarvisVR.Holograms;
using JarvisVR.Audio;

namespace JarvisVR.Shell
{
    /// <summary>
    /// The persistent "Jarvis" presence: a glowing orb that pulses and changes color with agent
    /// state (agent.thinking) plus a floating caption that shows what Jarvis hears/says
    /// (agent.transcript / agent.speech). Soft-follows the head like a HUD companion.
    /// </summary>
    [DisallowMultipleComponent]
    public class JarvisPresence : MonoBehaviour
    {
        public JarvisConnection connection;
        public Transform follow;
        [Tooltip("Optional on-device TTS for spoken narration (agent.observation).")]
        public SpeechPlayer speech;

        [Header("State colors")]
        public Color idleColor = new Color(0.25f, 0.6f, 1f);
        public Color thinkingColor = new Color(1f, 0.72f, 0.15f);
        public Color speakingColor = new Color(0.25f, 1f, 0.6f);
        public Color perceivingColor = new Color(0.7f, 0.4f, 1f);   // v1.1 looking/perceiving
        public Color errorColor = new Color(1f, 0.3f, 0.3f);
        public Color offlineColor = new Color(0.4f, 0.42f, 0.5f);

        [Header("Placement (head-relative, meters)")]
        public Vector3 offset = new Vector3(0f, -0.35f, 0.6f);
        public float followLerp = 6f;

        private Transform _orb;
        private Renderer _orbRenderer;
        private Material _orbMat;
        private TextMeshPro _status;
        private TextMeshPro _caption;
        private Color _target;
        private float _pulse;
        private float _captionHideAt;
        private bool _lastSpeechFinal = true;

        // ---- testability accessors (read-only) ----
        internal Color CurrentTarget => _target;
        internal string StatusText => _status != null ? _status.text : null;
        internal string CaptionText => _caption != null ? _caption.text : null;

        private void Awake()
        {
            if (connection == null) connection = FindObjectOfType<JarvisConnection>();
            BuildVisuals();
            _target = offlineColor;
        }

        private void OnEnable()
        {
            if (connection == null) return;
            connection.Router.On(MessageTypes.AgentThinking, OnThinking);
            connection.Router.On(MessageTypes.AgentSpeech, OnSpeech);
            connection.Router.On(MessageTypes.AgentTranscript, OnTranscript);
            connection.Router.On(MessageTypes.AgentObservation, OnObservation);
            connection.Router.On(MessageTypes.ServerError, OnServerError);
            connection.OnStateChanged += OnConnState;
            connection.OnReady += OnReady;
        }

        private void OnDisable()
        {
            if (connection == null) return;
            connection.Router.Off(MessageTypes.AgentThinking, OnThinking);
            connection.Router.Off(MessageTypes.AgentSpeech, OnSpeech);
            connection.Router.Off(MessageTypes.AgentTranscript, OnTranscript);
            connection.Router.Off(MessageTypes.AgentObservation, OnObservation);
            connection.Router.Off(MessageTypes.ServerError, OnServerError);
            connection.OnStateChanged -= OnConnState;
            connection.OnReady -= OnReady;
        }

        private void BuildVisuals()
        {
            var orbGo = GameObject.CreatePrimitive(PrimitiveType.Sphere);
            orbGo.name = "JarvisOrb";
            var col = orbGo.GetComponent<Collider>();
            if (col != null) Destroy(col);
            _orb = orbGo.transform;
            _orb.SetParent(transform, false);
            _orb.localScale = Vector3.one * 0.07f;
            _orbRenderer = orbGo.GetComponent<Renderer>();
            _orbMat = HoloMaterials.Solid(idleColor);
            _orbRenderer.material = _orbMat;

            _status = MakeText("Status", 0.022f, new Color(0.8f, 0.85f, 0.95f), new Vector3(0f, 0.08f, 0f), new Vector2(0.5f, 0.04f));
            _caption = MakeText("Caption", 0.03f, Color.white, new Vector3(0f, -0.09f, 0f), new Vector2(0.7f, 0.2f));
            _caption.text = "";
            _status.text = "connecting…";
        }

        private TextMeshPro MakeText(string name, float size, Color color, Vector3 localPos, Vector2 rect)
        {
            var go = new GameObject(name);
            go.transform.SetParent(transform, false);
            go.transform.localPosition = localPos;
            var tmp = go.AddComponent<TextMeshPro>();
            tmp.fontSize = size;
            tmp.color = color;
            tmp.alignment = TextAlignmentOptions.Center;
            tmp.enableWordWrapping = true;
            tmp.rectTransform.sizeDelta = rect;
            return tmp;
        }

        private void Update()
        {
            var head = follow != null ? follow : (Camera.main != null ? Camera.main.transform : null);
            if (head != null)
            {
                Vector3 targetPos = head.position + head.forward * offset.z + head.up * offset.y + head.right * offset.x;
                transform.position = Vector3.Lerp(transform.position, targetPos, Time.deltaTime * followLerp);
                Vector3 lookDir = transform.position - head.position;
                if (lookDir.sqrMagnitude > 1e-5f)
                    transform.rotation = Quaternion.Slerp(transform.rotation, Quaternion.LookRotation(lookDir), Time.deltaTime * followLerp);
            }

            _pulse += Time.deltaTime * 2.2f;
            if (_orb != null) _orb.localScale = Vector3.one * (0.07f + Mathf.Sin(_pulse) * 0.006f);

            if (_orbMat != null)
            {
                Color cur = Color.Lerp(HoloMaterials.GetAlbedo(_orbMat, idleColor), _target, Time.deltaTime * 4f);
                HoloMaterials.SetAlbedo(_orbMat, cur);
                if (_orbMat.HasProperty("_EmissionColor")) _orbMat.SetColor("_EmissionColor", cur * 0.6f);
            }

            if (_captionHideAt > 0f && Time.time > _captionHideAt)
            {
                _caption.text = "";
                _captionHideAt = 0f;
            }
        }

        // ---- protocol handlers --------------------------------------------------------------

        private void OnThinking(Envelope env)
        {
            var t = env.PayloadAs<AgentThinking>();
            if (t == null) return;
            _status.text = !string.IsNullOrEmpty(t.Label) ? t.Label : (t.Stage ?? "thinking…");
            switch (t.Stage)
            {
                case ThinkingStages.Done: _target = idleColor; break;
                case ThinkingStages.Perceiving:
                case ThinkingStages.Looking: _target = perceivingColor; break;
                default: _target = thinkingColor; break;
            }
        }

        private void OnSpeech(Envelope env)
        {
            var s = env.PayloadAs<AgentSpeech>();
            if (s == null) return;
            _target = speakingColor;
            if (_lastSpeechFinal) _caption.text = "";          // start a fresh utterance
            _caption.text += s.Text;
            _lastSpeechFinal = s.Final;
            if (s.Final)
            {
                _status.text = "";
                _captionHideAt = Time.time + 5f;
                _target = idleColor;
            }
        }

        private void OnTranscript(Envelope env)
        {
            var t = env.PayloadAs<TextPayload>();
            if (t == null || string.IsNullOrEmpty(t.Text)) return;
            _caption.text = $"<color=#9fd0ff>“{t.Text}”</color>";
            _caption.richText = true;
            _captionHideAt = Time.time + 4f;
            _lastSpeechFinal = true;
        }

        // v1.1 §8.4: what Jarvis perceives — caption + (optional on-device) speech.
        private void OnObservation(Envelope env)
        {
            var o = env.PayloadAs<AgentObservation>();
            if (o == null || string.IsNullOrEmpty(o.Text)) return;
            _target = perceivingColor;
            _caption.richText = true;
            _caption.text = $"<color=#c9a8ff>\U0001F441 {o.Text}</color>";
            _lastSpeechFinal = true;
            if (o.Final)
            {
                _captionHideAt = Time.time + 6f;
                _target = idleColor;
                if (speech != null) speech.Speak(o.Text);
            }
        }

        private void OnServerError(Envelope env)
        {
            var e = env.PayloadAs<ErrorPayload>();
            _status.text = e != null ? $"error: {e.Message}" : "error";
            _target = errorColor;
            _captionHideAt = Time.time + 5f;
        }

        private void OnReady() => _status.text = connection.LastHelloAck?.Agent?.Name ?? "Jarvis online";

        private void OnConnState(ConnectionState s)
        {
            switch (s)
            {
                case ConnectionState.Connected: _target = idleColor; break;
                case ConnectionState.Connecting:
                case ConnectionState.Reconnecting: _status.text = "connecting…"; _target = offlineColor; break;
                case ConnectionState.Disconnected: _status.text = "offline"; _target = offlineColor; break;
            }
        }
    }
}
