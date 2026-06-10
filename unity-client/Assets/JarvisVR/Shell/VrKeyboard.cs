using System;
using System.Collections.Generic;
using System.Text;
using UnityEngine;
using TMPro;
using JarvisVR.Holograms;

namespace JarvisVR.Shell
{
    /// <summary>
    /// Optional 3D keyboard backend (Meta OVRVirtualKeyboard). Registered by
    /// JarvisVR.Meta.MetaVirtualKeyboard when <c>HAS_META_KEYBOARD</c> is defined. Used for
    /// non-secure fields; secure fields prefer the masked system keyboard.
    /// </summary>
    public interface IVrKeyboardBackend
    {
        bool IsAvailable { get; }
        void Open(string initial, string label, Action<string> onSubmit, Action onCancel);
        void Close();
    }

    /// <summary>
    /// Spatial text entry for VR. Prefers the device **system keyboard** via Unity
    /// <see cref="TouchScreenKeyboard"/> (which surfaces Meta's VR keyboard on Quest and supports a
    /// <c>secure</c> masked mode for API keys); falls back to an on-panel procedural keyboard
    /// (editor/desktop, or where no system keyboard exists). A Meta 3D keyboard backend can be
    /// plugged in for non-secure fields.
    ///
    /// Security: secure entry never echoes characters (the system keyboard masks; the on-panel
    /// preview shows dots). The entered value is delivered once via <c>onSubmit</c> and not retained.
    /// </summary>
    [DisallowMultipleComponent]
    public class VrKeyboard : MonoBehaviour
    {
        public Transform follow;                 // head, for placing the on-panel keyboard
        public IVrKeyboardBackend metaBackend;   // optional (Meta), set by the Meta bridge

        public bool IsOpen { get; private set; }

        private bool _secure;
        private bool _multiline;
        private Action<string> _onSubmit;
        private Action _onCancel;

        private TouchScreenKeyboard _system;
        private bool _usingMeta;

        // on-panel state
        private GameObject _panel;
        private TextMeshPro _preview;
        private TextMeshPro _labelText;
        private readonly Dictionary<Transform, string> _keyIds = new Dictionary<Transform, string>();
        private readonly StringBuilder _buffer = new StringBuilder();
        private bool _shift;
        private bool _onPanelActive;

        /// <summary>Open the keyboard to edit a field. Set <paramref name="multiline"/> for long
        /// instruction bodies (adds a newline key on the fallback panel).</summary>
        public void Open(string initial, bool secure, string label, Action<string> onSubmit, Action onCancel = null, bool multiline = false)
        {
            Close();
            _secure = secure;
            _multiline = multiline;
            _onSubmit = onSubmit;
            _onCancel = onCancel;
            IsOpen = true;

            // Secure fields must be masked → only the system keyboard or the on-panel (dot preview).
            if (!secure && metaBackend != null && metaBackend.IsAvailable)
            {
                _usingMeta = true;
                metaBackend.Open(initial ?? "", label, Submit, Cancel);
                return;
            }

            if (TouchScreenKeyboard.isSupported)
            {
                // text, type, autocorrection, multiline, secure, alert, placeholder
                _system = TouchScreenKeyboard.Open(initial ?? "", TouchScreenKeyboardType.Default,
                    false, _multiline, secure, false, label ?? "");
                return;
            }

            OpenOnPanel(initial ?? "", label);
        }

        public void Close()
        {
            if (_usingMeta) { metaBackend?.Close(); _usingMeta = false; }
            if (_system != null) { _system.active = false; _system = null; }
            if (_panel != null) _panel.SetActive(false);
            _onPanelActive = false;
            _buffer.Length = 0;
            _shift = false;
            IsOpen = false;
        }

        private void Submit(string value)
        {
            var cb = _onSubmit;
            ClearCallbacks();
            Close();
            cb?.Invoke(value);
        }

        private void Cancel()
        {
            var cb = _onCancel;
            ClearCallbacks();
            Close();
            cb?.Invoke();
        }

        private void ClearCallbacks() { _onSubmit = null; _onCancel = null; }

        private void Update()
        {
            if (!IsOpen) return;

            if (_system != null)
            {
                switch (_system.status)
                {
                    case TouchScreenKeyboard.Status.Done: Submit(_system.text ?? ""); break;
                    case TouchScreenKeyboard.Status.Canceled:
                    case TouchScreenKeyboard.Status.LostFocus: Cancel(); break;
                }
                return;
            }

            if (_onPanelActive)
            {
                PlacePanel();
#if ENABLE_LEGACY_INPUT_MANAGER
                if (Input.GetMouseButtonDown(0)) TryKeyClick();
#endif
            }
        }

        // ---- on-panel procedural keyboard (fallback) ----------------------------------------

        private static readonly string[] Rows =
        {
            "1234567890",
            "qwertyuiop",
            "asdfghjkl",
            "zxcvbnm",
            ".-_/:@",
        };

        private void OpenOnPanel(string initial, string label)
        {
            _buffer.Length = 0;
            if (!string.IsNullOrEmpty(initial)) _buffer.Append(initial);
            if (_panel == null) BuildPanel();
            _panel.SetActive(true);
            _onPanelActive = true;
            _labelText.text = label ?? "Enter text";
            RefreshPreview();
            PlacePanel();
        }

        private void BuildPanel()
        {
            _panel = new GameObject("OnPanelKeyboard");
            _panel.transform.SetParent(transform, false);

            CreateQuad("kb_bg", Vector3.zero, new Vector3(0.62f, 0.34f, 0.008f), new Color(0.06f, 0.07f, 0.1f, 0.97f), false);
            _labelText = MakeText("kb_label", "", 0.022f, new Color(0.65f, 0.8f, 1f), new Vector3(0f, 0.15f, -0.006f), new Vector2(0.6f, 0.03f));
            _preview = MakeText("kb_preview", "", 0.03f, Color.white, new Vector3(0f, 0.115f, -0.006f), new Vector2(0.58f, 0.04f));

            float keyW = 0.052f, keyH = 0.04f, gap = 0.006f, step = keyW + gap;
            float topY = 0.06f;
            for (int r = 0; r < Rows.Length; r++)
            {
                string row = Rows[r];
                float rowWidth = row.Length * step - gap;
                float x0 = -rowWidth * 0.5f + keyW * 0.5f;
                float y = topY - r * (keyH + gap);
                for (int c = 0; c < row.Length; c++)
                {
                    string ch = row[c].ToString();
                    AddKey(ch, ch, new Vector3(x0 + c * step, y, 0f), new Vector3(keyW, keyH, 0.012f),
                        new Color(0.16f, 0.2f, 0.3f));
                }
            }

            // control row
            float cy = topY - Rows.Length * (keyH + gap) - 0.004f;
            AddKey("shift", "Shift", new Vector3(-0.24f, cy, 0f), new Vector3(0.1f, keyH, 0.012f), new Color(0.25f, 0.28f, 0.4f));
            AddKey("space", "Space", new Vector3(-0.09f, cy, 0f), new Vector3(0.16f, keyH, 0.012f), new Color(0.2f, 0.24f, 0.34f));
            AddKey("back", "⌫", new Vector3(0.07f, cy, 0f), new Vector3(0.08f, keyH, 0.012f), new Color(0.3f, 0.25f, 0.3f));
            AddKey("clear", "Clr", new Vector3(0.16f, cy, 0f), new Vector3(0.08f, keyH, 0.012f), new Color(0.3f, 0.25f, 0.3f));
            AddKey("newline", "⏎", new Vector3(-0.02f, cy + keyH + gap, 0f), new Vector3(0.18f, keyH, 0.012f), new Color(0.22f, 0.26f, 0.36f));
            AddKey("cancel", "Cancel", new Vector3(0.255f, cy + keyH + gap, 0f), new Vector3(0.11f, keyH, 0.012f), new Color(0.5f, 0.25f, 0.25f));
            AddKey("done", "Done", new Vector3(0.255f, cy, 0f), new Vector3(0.11f, keyH, 0.012f), new Color(0.25f, 0.5f, 0.35f));
        }

        private void AddKey(string id, string label, Vector3 pos, Vector3 scale, Color color)
        {
            var key = GameObject.CreatePrimitive(PrimitiveType.Cube); // keep collider for raycast
            key.name = $"k_{id}";
            key.transform.SetParent(_panel.transform, false);
            key.transform.localPosition = pos;
            key.transform.localScale = scale;
            var r = key.GetComponent<Renderer>();
            if (r != null) r.material = HoloMaterials.Solid(color);
            _keyIds[key.transform] = id;

            var t = MakeText($"kl_{id}", label, 0.018f, Color.white, pos + new Vector3(0, 0, -0.012f), new Vector2(scale.x, scale.y));
            t.transform.SetParent(_panel.transform, false);
        }

        /// <summary>Press a key by id ("a".."z","0".."9", symbols, or "shift/space/back/clear/cancel/done").
        /// Public so a Meta poke interactable can drive the on-panel keys too.</summary>
        public void PressKey(string id)
        {
            if (!_onPanelActive || string.IsNullOrEmpty(id)) return;
            switch (id)
            {
                case "shift": _shift = !_shift; return;
                case "space": _buffer.Append(' '); break;
                case "newline": _buffer.Append('\n'); break;
                case "back": if (_buffer.Length > 0) _buffer.Length -= 1; break;
                case "clear": _buffer.Length = 0; break;
                case "cancel": Cancel(); return;
                case "done": Submit(_buffer.ToString()); return;
                default:
                    _buffer.Append(_shift ? id.ToUpperInvariant() : id);
                    break;
            }
            RefreshPreview();
        }

        private void RefreshPreview()
        {
            if (_preview == null) return;
            _preview.text = _secure ? new string('•', _buffer.Length) : _buffer.ToString();
        }

        private void PlacePanel()
        {
            var head = follow != null ? follow : (Camera.main != null ? Camera.main.transform : null);
            if (head == null || _panel == null) return;
            _panel.transform.position = head.position + head.forward * 0.55f - head.up * 0.18f;
            _panel.transform.rotation = Quaternion.LookRotation(_panel.transform.position - head.position);
        }

        private TextMeshPro MakeText(string name, string text, float size, Color color, Vector3 localPos, Vector2 rect)
        {
            var go = new GameObject(name);
            go.transform.SetParent(_panel != null ? _panel.transform : transform, false);
            go.transform.localPosition = localPos;
            var tmp = go.AddComponent<TextMeshPro>();
            tmp.text = text;
            tmp.fontSize = size;
            tmp.color = color;
            tmp.alignment = TextAlignmentOptions.Center;
            tmp.rectTransform.sizeDelta = rect;
            return tmp;
        }

        private void CreateQuad(string name, Vector3 pos, Vector3 scale, Color color, bool collider)
        {
            var go = GameObject.CreatePrimitive(PrimitiveType.Cube);
            go.name = name;
            if (!collider) { var c = go.GetComponent<Collider>(); if (c != null) Destroy(c); }
            go.transform.SetParent(_panel.transform, false);
            go.transform.localPosition = pos;
            go.transform.localScale = scale;
            var r = go.GetComponent<Renderer>();
            if (r != null) r.material = HoloMaterials.Solid(color);
        }

#if ENABLE_LEGACY_INPUT_MANAGER
        private void TryKeyClick()
        {
            var cam = Camera.main;
            if (cam == null) return;
            if (!Physics.Raycast(cam.ScreenPointToRay(Input.mousePosition), out var hit, 20f)) return;
            if (_keyIds.TryGetValue(hit.collider.transform, out var id)) PressKey(id);
        }
#endif
    }
}
