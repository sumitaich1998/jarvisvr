using System;
using System.Collections;
using System.Text;
using System.Threading.Tasks;
using NativeWebSocket;
using UnityEngine;
using JarvisVR.Protocol;

namespace JarvisVR.Net
{
    public enum ConnectionState { Disconnected, Connecting, Connected, Reconnecting }

    /// <summary>
    /// WebSocket client implementing docs/PROTOCOL.md: connects to ws://host:port/jarvis, sends
    /// <c>client.hello</c>, stores the session from <c>server.hello_ack</c>, beats every 5s, and
    /// auto-reconnects with exponential backoff. Inbound envelopes are surfaced via
    /// <see cref="OnMessage"/> and dispatched through <see cref="Router"/>.
    ///
    /// Threading: NativeWebSocket queues inbound frames; we drain them on the main thread in
    /// Update() via DispatchMessageQueue, so all handler callbacks run on Unity's main thread.
    /// </summary>
    [DisallowMultipleComponent]
    public class JarvisConnection : MonoBehaviour
    {
        [SerializeField] private JarvisConfig config;
        public JarvisConfig Config { get => config; set => config = value; }

        public ConnectionState State { get; private set; } = ConnectionState.Disconnected;
        public string SessionId { get; private set; }
        public ServerHelloAck LastHelloAck { get; private set; }
        public bool IsReady => State == ConnectionState.Connected && !string.IsNullOrEmpty(SessionId);

        /// <summary>If set, used for the hello handshake instead of config (so PerceptionController can
        /// advertise v1.1 capabilities truthfully without mutating the shared config asset).</summary>
        public Capabilities CapabilityOverride;

        /// <summary>If set, evaluated at hello time (latest possible) to compute truthful capabilities
        /// after optional providers (e.g. Meta eye gaze) have registered. Takes precedence.</summary>
        public System.Func<Capabilities> CapabilityProvider;

        /// <summary>While true, outbound user.text/voice carry <c>attach_perception:true</c> (§8.3),
        /// so the agent correlates current sight/sound. Set by PerceptionController when vision is on.</summary>
        public bool AttachPerceptionDefault;

        /// <summary>Type-keyed dispatcher. Subscribe with <c>Router.On(MessageTypes.X, handler)</c>.</summary>
        public readonly MessageRouter Router = new MessageRouter();

        public event Action OnConnected;            // raw socket opened
        public event Action OnReady;                // server.hello_ack received (session assigned)
        public event Action<string> OnClosed;       // socket closed (reason)
        public event Action<string> OnErrorMessage; // transport/parse error
        public event Action<Envelope> OnMessage;    // every inbound envelope (post-parse)
        public event Action<ConnectionState> OnStateChanged;

        /// <summary>When false, Start() does not auto-connect (used by tests to exercise the Router
        /// without opening a real socket). Default true preserves runtime behavior.</summary>
        public bool autoConnectOnStart = true;

        private WebSocket _ws;
        private float _reconnectDelay;
        private bool _intentionalClose;
        private Coroutine _heartbeat;

        private void Awake()
        {
            Router.On(MessageTypes.ServerHelloAck, HandleHelloAck);
            // server.heartbeat: liveness is implied by socket state; nothing else required.
            Router.On(MessageTypes.ServerHeartbeat, _ => { });
        }

        private void Start()
        {
            if (config == null)
            {
                Debug.LogError("[Jarvis] JarvisConnection has no JarvisConfig assigned; not connecting.");
                return;
            }
            if (autoConnectOnStart) Connect();
        }

        // ---- lifecycle ----------------------------------------------------------------------

        public async void Connect()
        {
            if (config == null) return;
            if (State == ConnectionState.Connecting || State == ConnectionState.Connected) return;

            _intentionalClose = false;
            SetState(ConnectionState.Connecting);

            try
            {
                _ws = new WebSocket(config.MainUrl);
                _ws.OnOpen += HandleOpen;
                _ws.OnError += HandleSocketError;
                _ws.OnClose += HandleClose;
                _ws.OnMessage += HandleRawMessage;

                // Connect() completes when the connection is closed (it runs the receive loop).
                await _ws.Connect();
            }
            catch (Exception e)
            {
                OnErrorMessage?.Invoke(e.Message);
                ScheduleReconnect($"connect failed: {e.Message}");
            }
        }

        public async void Disconnect(bool sendBye = true)
        {
            _intentionalClose = true;
            StopHeartbeat();
            try
            {
                if (_ws != null && _ws.State == WebSocketState.Open)
                {
                    if (sendBye) Send(MessageTypes.ClientBye, new EmptyPayload());
                    await _ws.Close();
                }
            }
            catch (Exception e)
            {
                Debug.LogWarning($"[Jarvis] error during close: {e.Message}");
            }
            SetState(ConnectionState.Disconnected);
        }

        private void HandleOpen()
        {
            _reconnectDelay = 0f;
            SetState(ConnectionState.Connected);
            OnConnected?.Invoke();
            SendHello();
            StartHeartbeat();
        }

        private void HandleSocketError(string err) => OnErrorMessage?.Invoke(err);

        private void HandleClose(WebSocketCloseCode code)
        {
            StopHeartbeat();
            SessionId = null;
            OnClosed?.Invoke(code.ToString());
            if (_intentionalClose) { SetState(ConnectionState.Disconnected); return; }
            ScheduleReconnect($"socket closed: {code}");
        }

        private void HandleHelloAck(Envelope env)
        {
            var ack = env.PayloadAs<ServerHelloAck>();
            if (ack == null) return;
            LastHelloAck = ack;
            SessionId = ack.Session;
            if (config != null && config.logTraffic)
                Debug.Log($"[Jarvis] hello_ack session={ack.Session} agent={ack.Agent?.Name} model={ack.Agent?.Model}");
            OnReady?.Invoke();
        }

        // ---- inbound ------------------------------------------------------------------------

        private void HandleRawMessage(byte[] data)
        {
            string json = Encoding.UTF8.GetString(data);
            if (config != null && config.logTraffic) Debug.Log($"[Jarvis] << {json}");

            if (!EnvelopeSerializer.TryDeserialize(json, out var env, out var error))
            {
                OnErrorMessage?.Invoke($"bad envelope: {error}");
                SendError(ErrorCodes.BadEnvelope, $"could not parse message: {error}");
                return;
            }

            try
            {
                OnMessage?.Invoke(env);
                Router.Route(env); // unknown types are ignored inside the router
            }
            catch (Exception e)
            {
                Debug.LogException(e);
            }
        }

        private void Update()
        {
#if !UNITY_WEBGL || UNITY_EDITOR
            _ws?.DispatchMessageQueue();
#endif
        }

        // ---- outbound -----------------------------------------------------------------------

        public void SendHello()
        {
            var hello = new ClientHello
            {
                Device = "quest3",
                AppVersion = config.appVersion,
                ProtocolVersion = ProtocolConstants.Version,
                Locale = config.locale,
                Capabilities = CapabilityProvider != null ? CapabilityProvider()
                              : (CapabilityOverride ?? config.BuildCapabilities()),
            };
            // session is intentionally null on the first hello (assigned in hello_ack).
            Send(MessageTypes.ClientHello, hello);
        }

        /// <summary>Wrap a payload in the v1 envelope (using the current session) and send it.
        /// Set <paramref name="sensitive"/> for payloads that may contain secrets (e.g. an API key in
        /// client.settings_update) so the body is never written to the traffic log.</summary>
        public void Send(string type, object payload, string replyTo = null, bool sensitive = false)
        {
            if (_ws == null || _ws.State != WebSocketState.Open) return;
            string json = EnvelopeSerializer.BuildJson(type, payload, SessionId, null, replyTo);
            if (config != null && config.logTraffic)
                Debug.Log(sensitive ? $"[Jarvis] >> {type} (payload redacted)" : $"[Jarvis] >> {json}");
            _ = SendRaw(json);
        }

        /// <summary>Acknowledge a render command: client.ack with reply_to = the command's id.</summary>
        public void Ack(string commandId) => Send(MessageTypes.ClientAck, new EmptyPayload(), commandId);

        public void SendText(string text, float? confidence = null)
            => Send(MessageTypes.UserText, WithPerception(new TextPayload(text, confidence)));

        public void SendVoiceTranscript(string text, float? confidence = null)
            => Send(MessageTypes.UserVoiceTranscript, WithPerception(new TextPayload(text, confidence)));

        private TextPayload WithPerception(TextPayload p)
        {
            if (AttachPerceptionDefault) p.AttachPerception = true; // §8.3
            return p;
        }

        public void SendError(string code, string message, bool fatal = false)
            => Send(MessageTypes.ClientError, new ErrorPayload { Code = code, Message = message, Fatal = fatal });

        // §5.15 settings helpers
        public void SendSettingsGet(string section = SettingsSections.Llm)
            => Send(MessageTypes.ClientSettingsGet, new SettingsGet(section));

        /// <summary>Send a settings change. Marked sensitive so an included api_key is never logged.</summary>
        public void SendSettingsUpdate(ClientSettingsUpdate update)
            => Send(MessageTypes.ClientSettingsUpdate, update, sensitive: true);

        private async Task SendRaw(string json)
        {
            try
            {
                if (_ws != null && _ws.State == WebSocketState.Open)
                    await _ws.SendText(json);
            }
            catch (Exception e)
            {
                OnErrorMessage?.Invoke($"send failed: {e.Message}");
            }
        }

        // ---- heartbeat & reconnect ----------------------------------------------------------

        private void StartHeartbeat()
        {
            StopHeartbeat();
            _heartbeat = StartCoroutine(HeartbeatLoop());
        }

        private void StopHeartbeat()
        {
            if (_heartbeat != null) { StopCoroutine(_heartbeat); _heartbeat = null; }
        }

        private IEnumerator HeartbeatLoop()
        {
            var wait = new WaitForSeconds(Mathf.Max(1f, config.heartbeatSeconds));
            while (_ws != null && _ws.State == WebSocketState.Open)
            {
                Send(MessageTypes.ClientHeartbeat, new EmptyPayload());
                yield return wait;
            }
        }

        /// <summary>Pure exponential-backoff step (testable): first delay = max(0.1, initial);
        /// subsequent = min(max, prev * max(1, mult)).</summary>
        internal static float NextReconnectDelay(float prev, float initial, float max, float mult)
            => prev <= 0f ? Mathf.Max(0.1f, initial) : Mathf.Min(max, prev * Mathf.Max(1f, mult));

        private void ScheduleReconnect(string reason)
        {
            if (config == null || !config.autoReconnect)
            {
                SetState(ConnectionState.Disconnected);
                return;
            }

            SetState(ConnectionState.Reconnecting);
            _reconnectDelay = NextReconnectDelay(_reconnectDelay, config.reconnectInitialDelay,
                config.reconnectMaxDelay, config.reconnectBackoffMultiplier);

            Debug.LogWarning($"[Jarvis] reconnecting in {_reconnectDelay:0.0}s ({reason})");
            StartCoroutine(ReconnectAfter(_reconnectDelay));
        }

        private IEnumerator ReconnectAfter(float delay)
        {
            yield return new WaitForSeconds(delay);
            if (!_intentionalClose) Connect();
        }

        private void SetState(ConnectionState s)
        {
            if (State == s) return;
            State = s;
            OnStateChanged?.Invoke(s);
        }

        // ---- teardown -----------------------------------------------------------------------

        private async void OnApplicationQuit()
        {
            Disconnect();
            await Task.Yield();
        }

        private void OnDestroy()
        {
            _intentionalClose = true;
            StopHeartbeat();
            if (_ws != null)
            {
                _ws.OnOpen -= HandleOpen;
                _ws.OnError -= HandleSocketError;
                _ws.OnClose -= HandleClose;
                _ws.OnMessage -= HandleRawMessage;
            }
        }
    }
}
