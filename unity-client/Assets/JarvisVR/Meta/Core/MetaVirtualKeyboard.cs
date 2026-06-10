// Optional Meta 3D system keyboard (OVRVirtualKeyboard) backend for VrKeyboard, used for non-secure
// text fields (model / base_url). Secure fields (the API key) keep using the masked system keyboard.
//
// Opt-in via the HAS_META_KEYBOARD scripting define (also requires the Meta XR Core SDK and an
// OVRVirtualKeyboard + keyboard model in the scene). The OVRVirtualKeyboard event surface can vary
// by SDK version — adjust the CommitText/Backspace/Enter hookups below if your version differs.
#if HAS_META_CORE && HAS_META_KEYBOARD
using System.Text;
using UnityEngine;
using JarvisVR.Shell;

namespace JarvisVR.Meta
{
    public class MetaVirtualKeyboard : MonoBehaviour, IVrKeyboardBackend
    {
        public OVRVirtualKeyboard keyboard;

        private readonly StringBuilder _buffer = new StringBuilder();
        private System.Action<string> _onSubmit;
        private System.Action _onCancel;
        private bool _hooked;

        private void Awake()
        {
            if (keyboard == null) keyboard = FindObjectOfType<OVRVirtualKeyboard>();
            var vk = FindObjectOfType<VrKeyboard>();
            if (vk != null) vk.metaBackend = this; // register as the preferred non-secure backend
        }

        public bool IsAvailable => keyboard != null;

        public void Open(string initial, string label, System.Action<string> onSubmit, System.Action onCancel)
        {
            if (keyboard == null) { onCancel?.Invoke(); return; }
            _onSubmit = onSubmit;
            _onCancel = onCancel;
            _buffer.Length = 0;
            if (!string.IsNullOrEmpty(initial)) _buffer.Append(initial);
            Hook();
            keyboard.gameObject.SetActive(true);
            try { keyboard.ChangeTextContext(_buffer.ToString()); } catch { /* version-dependent */ }
        }

        public void Close()
        {
            Unhook();
            if (keyboard != null) keyboard.gameObject.SetActive(false);
            _onSubmit = null;
            _onCancel = null;
        }

        private void Hook()
        {
            if (_hooked || keyboard == null) return;
            keyboard.CommitText.AddListener(OnCommit);
            keyboard.Backspace.AddListener(OnBackspace);
            keyboard.Enter.AddListener(OnEnter);
            _hooked = true;
        }

        private void Unhook()
        {
            if (!_hooked || keyboard == null) return;
            keyboard.CommitText.RemoveListener(OnCommit);
            keyboard.Backspace.RemoveListener(OnBackspace);
            keyboard.Enter.RemoveListener(OnEnter);
            _hooked = false;
        }

        private void OnCommit(string s) => _buffer.Append(s);
        private void OnBackspace() { if (_buffer.Length > 0) _buffer.Length -= 1; }
        private void OnEnter()
        {
            var cb = _onSubmit;
            var value = _buffer.ToString();
            Close();
            cb?.Invoke(value);
        }
    }
}
#endif
