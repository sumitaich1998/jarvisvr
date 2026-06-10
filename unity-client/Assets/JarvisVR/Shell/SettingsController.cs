using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using TMPro;
using JarvisVR.Net;
using JarvisVR.Protocol;
using JarvisVR.Holograms;

namespace JarvisVR.Shell
{
    /// <summary>
    /// In-headset **Settings** for the LLM provider / model / API key (docs/PROTOCOL.md §5.15).
    /// On open it sends <c>client.settings_get{section:"llm"}</c> and renders the <c>server.settings</c>
    /// reply: a provider selector, a model selector (catalog + free-text override), a base_url field
    /// (only when the provider needs it), and a masked API-key field with a key-set indicator. Save
    /// emits <c>client.settings_update</c> (api_key only when a new one was typed) and reflects the
    /// applied/error state. Falls back to a manual free-text form if no catalog arrives.
    ///
    /// Security: the API key is entered via the masked VR keyboard, shown only as dots, never logged
    /// (sent via JarvisConnection sensitive send), and cleared from memory right after sending.
    /// </summary>
    [DisallowMultipleComponent]
    public class SettingsController : MonoBehaviour
    {
        public JarvisConnection connection;
        public VrKeyboard keyboard;
        public Transform follow; // head

        public bool IsOpen { get; private set; }

        // ---- state ----
        private readonly List<ProviderInfo> _providers = new List<ProviderInfo>();
        internal string _providerId = "";   // internal: set by tests via InternalsVisibleTo
        internal string _model = "";
        internal string _baseUrl = "";
        private bool _keySet;
        internal string _pendingApiKey;    // transient; non-null only between typing and saving
        private bool _catalogReceived;
        internal bool _manual;
        private bool _saving;
        private bool _appliedOnce;
        private Coroutine _fallback;

        // ---- visuals ----
        private GameObject _panel;
        private TextMeshPro _provValue, _modelValue, _baseUrlValue, _keyIndicator, _status;
        private Transform _baseUrlRow;
        private readonly Dictionary<Transform, string> _buttons = new Dictionary<Transform, string>();

        private void Awake()
        {
            if (connection == null) connection = FindObjectOfType<JarvisConnection>();
            if (keyboard == null) keyboard = FindObjectOfType<VrKeyboard>();
            BuildPanel();
            _panel.SetActive(false);
        }

        private void OnEnable()
        {
            if (connection == null) return;
            connection.Router.On(MessageTypes.ServerSettings, OnServerSettings);
            connection.Router.On(MessageTypes.ServerError, OnServerError);
        }

        private void OnDisable()
        {
            if (connection == null) return;
            connection.Router.Off(MessageTypes.ServerSettings, OnServerSettings);
            connection.Router.Off(MessageTypes.ServerError, OnServerError);
        }

        // ---- open / close -------------------------------------------------------------------

        public void Toggle() { if (IsOpen) Close(); else Open(); }

        public void Open()
        {
            IsOpen = true;
            _pendingApiKey = null;
            _saving = false;
            _appliedOnce = false;
            _catalogReceived = false;
            _manual = false;
            _panel.SetActive(true);
            PlaceInFront();
            SetStatus("Loading…", false);
            RenderState();

            connection?.SendSettingsGet(SettingsSections.Llm);

            if (_fallback != null) StopCoroutine(_fallback);
            _fallback = StartCoroutine(FallbackAfter(2.5f));
        }

        public void Close()
        {
            IsOpen = false;
            _pendingApiKey = null; // never retain a typed key
            keyboard?.Close();
            if (_panel != null) _panel.SetActive(false);
            if (_fallback != null) { StopCoroutine(_fallback); _fallback = null; }
        }

        private IEnumerator FallbackAfter(float seconds)
        {
            yield return new WaitForSeconds(seconds);
            if (!_catalogReceived)
            {
                _manual = true;
                SetStatus("Manual mode — type provider, model, base URL & key", false);
                RenderState();
            }
        }

        private void PlaceInFront()
        {
            var head = follow != null ? follow : (Camera.main != null ? Camera.main.transform : null);
            if (head == null) return;
            transform.position = head.position + head.forward * 0.7f;
            transform.rotation = Quaternion.LookRotation(transform.position - head.position);
        }

        // ---- protocol handlers --------------------------------------------------------------

        private void OnServerSettings(Envelope env)
        {
            var s = env.PayloadAs<ServerSettings>();
            if (s?.Llm == null) return;

            if (s.Llm.Providers != null && s.Llm.Providers.Count > 0)
            {
                _providers.Clear();
                _providers.AddRange(s.Llm.Providers);
                _catalogReceived = true;
                _manual = false;
            }

            // Apply the server's current selection on first load or right after a save.
            var cur = s.Llm.Current;
            if (cur != null && (!_appliedOnce || _saving))
            {
                _providerId = cur.Provider ?? _providerId;
                _model = cur.Model ?? _model;
                _baseUrl = cur.BaseUrl ?? "";
                _keySet = cur.KeySet;
            }
            else if (cur != null)
            {
                _keySet = cur.KeySet; // keep the user's in-progress edits, refresh key indicator
            }

            if (_saving) { SetStatus("Applied ✓", false); _saving = false; }
            else if (!_appliedOnce) SetStatus("", false);
            _appliedOnce = true;

            RenderState();
        }

        private void OnServerError(Envelope env)
        {
            if (!IsOpen) return;
            var e = env.PayloadAs<ErrorPayload>();
            bool settingsError = e != null && (e.Code == ErrorCodes.InvalidSettings
                || e.Code == ErrorCodes.ProviderUnavailable || e.Code == ErrorCodes.InvalidKey);
            if (!_saving && !settingsError) return; // unrelated error
            SetStatus("⚠ " + (e?.Message ?? e?.Code ?? "settings error"), true);
            _saving = false;
        }

        // ---- actions (button elements) ------------------------------------------------------

        /// <summary>Handle a settings-panel button by element id (mouse tester / Meta poke / gaze).</summary>
        public void Press(string element)
        {
            switch (element)
            {
                case "prov_prev": CycleProvider(-1); break;
                case "prov_next": CycleProvider(1); break;
                case "prov_edit": EditText("Provider id", _providerId, false, v => { _providerId = v.Trim(); RenderState(); }); break;
                case "model_prev": CycleModel(-1); break;
                case "model_next": CycleModel(1); break;
                case "model_edit": EditText("Model", _model, false, v => { _model = v.Trim(); RenderState(); }); break;
                case "baseurl_edit": EditText("Base URL", _baseUrl, false, v => { _baseUrl = v.Trim(); RenderState(); }); break;
                case "key_edit": EditText("API key", "", true, v => { _pendingApiKey = v; RenderState(); }); break;
                case "save": Save(); break;
                case "close": Close(); break;
            }
        }

        private void EditText(string label, string initial, bool secure, System.Action<string> onSubmit)
        {
            if (keyboard == null) { SetStatus("No keyboard available", true); return; }
            keyboard.Open(initial, secure, label, onSubmit);
        }

        private ProviderInfo Selected()
        {
            foreach (var p in _providers) if (p != null && p.Id == _providerId) return p;
            return null;
        }

        private void CycleProvider(int dir)
        {
            if (_providers.Count == 0) return;
            int idx = 0;
            for (int i = 0; i < _providers.Count; i++) if (_providers[i].Id == _providerId) { idx = i; break; }
            idx = ((idx + dir) % _providers.Count + _providers.Count) % _providers.Count;
            var p = _providers[idx];
            _providerId = p.Id;
            _model = !string.IsNullOrEmpty(p.DefaultModel) ? p.DefaultModel
                     : (p.Models != null && p.Models.Count > 0 ? p.Models[0] : _model);
            _keySet = p.KeySet;
            if (!p.NeedsBaseUrl) _baseUrl = ""; // base_url only meaningful for some providers
            RenderState();
        }

        private void CycleModel(int dir)
        {
            var p = Selected();
            if (p?.Models == null || p.Models.Count == 0) return;
            int idx = Mathf.Max(0, p.Models.IndexOf(_model));
            idx = ((idx + dir) % p.Models.Count + p.Models.Count) % p.Models.Count;
            _model = p.Models[idx];
            RenderState();
        }

        private bool ShouldSendBaseUrl()
        {
            var p = Selected();
            return (p != null && p.NeedsBaseUrl) || _manual || !string.IsNullOrEmpty(_baseUrl);
        }

        /// <summary>Build the client.settings_update payload from the current form state. Pure +
        /// testable: <c>api_key</c> is included only when a new key was typed; <c>base_url</c> only
        /// when the provider needs it / it's set.</summary>
        internal ClientSettingsUpdate BuildUpdatePayload() => new ClientSettingsUpdate
        {
            Llm = new LlmConfigUpdate
            {
                Provider = _providerId,
                Model = _model,
                BaseUrl = ShouldSendBaseUrl() ? _baseUrl : null,
                // api_key only when the user typed a new one (blank = keep existing).
                ApiKey = string.IsNullOrEmpty(_pendingApiKey) ? null : _pendingApiKey,
            },
        };

        private void Save()
        {
            if (connection == null) { SetStatus("Not connected", true); return; }
            if (string.IsNullOrEmpty(_providerId)) { SetStatus("Pick a provider first", true); return; }

            var update = BuildUpdatePayload();
            bool sentKey = !string.IsNullOrEmpty(update.Llm.ApiKey);
            connection.SendSettingsUpdate(update); // sensitive: never logged

            // Clear the typed key from memory immediately after sending.
            _pendingApiKey = null;
            update.Llm.ApiKey = null;
            if (sentKey) _keySet = true; // optimistic; confirmed by the server.settings reply

            _saving = true;
            SetStatus("Saving…", false);
            RenderState();
        }

        // ---- rendering ----------------------------------------------------------------------

        private void RenderState()
        {
            var p = Selected();
            string provText = p != null ? p.Name : (string.IsNullOrEmpty(_providerId) ? "(tap to set)" : _providerId);
            if (p?.Capabilities != null)
            {
                var caps = new List<string>();
                if (p.Capabilities.Vision) caps.Add("vision");
                if (p.Capabilities.Tools) caps.Add("tools");
                if (caps.Count > 0) provText += $"  <size=60%><color=#88aacc>{string.Join("·", caps)}</color></size>";
            }
            _provValue.richText = true;
            _provValue.text = provText;

            _modelValue.text = string.IsNullOrEmpty(_model) ? "(default)" : _model;

            bool showBaseUrl = (p != null && p.NeedsBaseUrl) || _manual;
            _baseUrlRow.gameObject.SetActive(showBaseUrl);
            _baseUrlValue.text = string.IsNullOrEmpty(_baseUrl) ? "(none)" : _baseUrl;

            if (!string.IsNullOrEmpty(_pendingApiKey))
                SetKeyIndicator("new key ready ✓ (unsaved)", new Color(1f, 0.85f, 0.3f));
            else if (_keySet)
                SetKeyIndicator("key set ✓", new Color(0.4f, 0.9f, 0.5f));
            else
                SetKeyIndicator("not set", new Color(0.9f, 0.5f, 0.5f));
        }

        private void SetKeyIndicator(string text, Color color)
        {
            if (_keyIndicator == null) return;
            _keyIndicator.text = text;
            _keyIndicator.color = color;
        }

        private void SetStatus(string text, bool error)
        {
            if (_status == null) return;
            _status.text = text;
            _status.color = error ? new Color(1f, 0.45f, 0.4f) : new Color(0.7f, 0.85f, 1f);
        }

        // ---- panel construction -------------------------------------------------------------

        private void BuildPanel()
        {
            _panel = new GameObject("SettingsPanel");
            _panel.transform.SetParent(transform, false);

            Quad("bg", new Vector3(0f, 0f, 0.005f), new Vector3(0.7f, 0.52f, 0.01f), new Color(0.07f, 0.08f, 0.12f, 0.97f));
            Label("title", "Settings · Assistant (LLM)", 0.036f, new Color(0.7f, 0.85f, 1f), new Vector3(0f, 0.21f, -0.006f), new Vector2(0.66f, 0.05f));

            // Provider row
            Label("plabel", "Provider", 0.026f, new Color(0.7f, 0.75f, 0.85f), new Vector3(-0.3f, 0.12f, -0.006f), new Vector2(0.18f, 0.04f), TextAlignmentOptions.Left);
            _provValue = Label("pvalue", "", 0.028f, Color.white, new Vector3(-0.02f, 0.12f, -0.006f), new Vector2(0.3f, 0.04f), TextAlignmentOptions.Left);
            Button("prov_prev", "‹", new Vector3(0.18f, 0.12f, -0.006f), new Vector3(0.045f, 0.045f, 0.014f), new Color(0.2f, 0.28f, 0.42f));
            Button("prov_next", "›", new Vector3(0.235f, 0.12f, -0.006f), new Vector3(0.045f, 0.045f, 0.014f), new Color(0.2f, 0.28f, 0.42f));
            Button("prov_edit", "✎", new Vector3(0.3f, 0.12f, -0.006f), new Vector3(0.045f, 0.045f, 0.014f), new Color(0.25f, 0.3f, 0.4f));

            // Model row
            Label("mlabel", "Model", 0.026f, new Color(0.7f, 0.75f, 0.85f), new Vector3(-0.3f, 0.05f, -0.006f), new Vector2(0.18f, 0.04f), TextAlignmentOptions.Left);
            _modelValue = Label("mvalue", "", 0.028f, Color.white, new Vector3(-0.02f, 0.05f, -0.006f), new Vector2(0.3f, 0.04f), TextAlignmentOptions.Left);
            Button("model_prev", "‹", new Vector3(0.18f, 0.05f, -0.006f), new Vector3(0.045f, 0.045f, 0.014f), new Color(0.2f, 0.28f, 0.42f));
            Button("model_next", "›", new Vector3(0.235f, 0.05f, -0.006f), new Vector3(0.045f, 0.045f, 0.014f), new Color(0.2f, 0.28f, 0.42f));
            Button("model_edit", "✎", new Vector3(0.3f, 0.05f, -0.006f), new Vector3(0.045f, 0.045f, 0.014f), new Color(0.25f, 0.3f, 0.4f));

            // Base URL row (conditional)
            _baseUrlRow = new GameObject("baseUrlRow").transform;
            _baseUrlRow.SetParent(_panel.transform, false);
            Label("blabel", "Base URL", 0.026f, new Color(0.7f, 0.75f, 0.85f), new Vector3(-0.3f, -0.02f, -0.006f), new Vector2(0.18f, 0.04f), TextAlignmentOptions.Left, _baseUrlRow);
            _baseUrlValue = Label("bvalue", "", 0.026f, Color.white, new Vector3(0.02f, -0.02f, -0.006f), new Vector2(0.34f, 0.04f), TextAlignmentOptions.Left, _baseUrlRow);
            Button("baseurl_edit", "✎", new Vector3(0.3f, -0.02f, -0.006f), new Vector3(0.045f, 0.045f, 0.014f), new Color(0.25f, 0.3f, 0.4f), _baseUrlRow);

            // API key row
            Label("klabel", "API key", 0.026f, new Color(0.7f, 0.75f, 0.85f), new Vector3(-0.3f, -0.09f, -0.006f), new Vector2(0.18f, 0.04f), TextAlignmentOptions.Left);
            _keyIndicator = Label("kindicator", "not set", 0.026f, new Color(0.9f, 0.5f, 0.5f), new Vector3(-0.02f, -0.09f, -0.006f), new Vector2(0.3f, 0.04f), TextAlignmentOptions.Left);
            Button("key_edit", "Set key", new Vector3(0.26f, -0.09f, -0.006f), new Vector3(0.14f, 0.05f, 0.014f), new Color(0.3f, 0.35f, 0.5f));

            // Status + actions
            _status = Label("status", "", 0.024f, new Color(0.7f, 0.85f, 1f), new Vector3(0f, -0.16f, -0.006f), new Vector2(0.64f, 0.04f));
            Button("save", "Save", new Vector3(-0.12f, -0.22f, -0.006f), new Vector3(0.18f, 0.06f, 0.016f), new Color(0.2f, 0.55f, 0.4f));
            Button("close", "Close", new Vector3(0.12f, -0.22f, -0.006f), new Vector3(0.18f, 0.06f, 0.016f), new Color(0.4f, 0.3f, 0.35f));

            var bb = gameObject.AddComponent<Billboard>();
            bb.yawOnly = false;
        }

        private void Quad(string name, Vector3 pos, Vector3 scale, Color color)
        {
            var go = GameObject.CreatePrimitive(PrimitiveType.Cube);
            go.name = name;
            var c = go.GetComponent<Collider>(); if (c != null) Destroy(c);
            go.transform.SetParent(_panel.transform, false);
            go.transform.localPosition = pos;
            go.transform.localScale = scale;
            var r = go.GetComponent<Renderer>();
            if (r != null) r.material = HoloMaterials.Solid(color);
        }

        private TextMeshPro Label(string name, string text, float size, Color color, Vector3 pos, Vector2 rect,
            TextAlignmentOptions align = TextAlignmentOptions.Center, Transform parent = null)
        {
            var go = new GameObject(name);
            go.transform.SetParent(parent != null ? parent : _panel.transform, false);
            go.transform.localPosition = pos;
            var tmp = go.AddComponent<TextMeshPro>();
            tmp.text = text;
            tmp.fontSize = size;
            tmp.color = color;
            tmp.alignment = align;
            tmp.rectTransform.sizeDelta = rect;
            return tmp;
        }

        private void Button(string element, string label, Vector3 pos, Vector3 scale, Color color, Transform parent = null)
        {
            var btn = GameObject.CreatePrimitive(PrimitiveType.Cube); // keep collider for raycast
            btn.name = $"btn_{element}";
            btn.transform.SetParent(parent != null ? parent : _panel.transform, false);
            btn.transform.localPosition = pos;
            btn.transform.localScale = scale;
            var r = btn.GetComponent<Renderer>();
            if (r != null) r.material = HoloMaterials.Solid(color);
            _buttons[btn.transform] = element;

            Label($"lbl_{element}", label, Mathf.Min(0.026f, scale.y * 0.6f), Color.white,
                pos + new Vector3(0, 0, -scale.z), new Vector2(scale.x, scale.y), TextAlignmentOptions.Center, parent);
        }

        private void Update()
        {
            if (!IsOpen) return;
#if ENABLE_LEGACY_INPUT_MANAGER
            if (Input.GetMouseButtonDown(0)) TryClick();
#endif
        }

#if ENABLE_LEGACY_INPUT_MANAGER
        private void TryClick()
        {
            var cam = Camera.main;
            if (cam == null) return;
            if (!Physics.Raycast(cam.ScreenPointToRay(Input.mousePosition), out var hit, 20f)) return;
            if (_buttons.TryGetValue(hit.collider.transform, out var element)) Press(element);
        }
#endif
    }
}
