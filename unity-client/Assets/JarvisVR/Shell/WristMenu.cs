using System.Collections.Generic;
using UnityEngine;
using TMPro;
using JarvisVR.Holograms;
using JarvisVR.Perception;

namespace JarvisVR.Shell
{
    /// <summary>
    /// A wrist/hand-anchored quick menu (FEATURES §5) for privacy + spatial-OS actions:
    /// stop all capture, toggle camera, toggle mic, save/restore the hologram layout. Anchored to the
    /// left hand so it rides the wrist; buttons carry colliders ("wrist_0"…) for the mouse tester or a
    /// Meta poke interactable. The "Stop capture" item is an always-available privacy kill switch.
    /// </summary>
    [DisallowMultipleComponent]
    public class WristMenu : MonoBehaviour
    {
        public Transform hand;        // left hand anchor
        public PerceptionController perception;
        public HologramPersistence persistence;
        public SettingsController settings;
        public OrchestrationController orchestration;
        public StudioController studio;
        public Vector3 localOffset = new Vector3(0f, 0.06f, 0.02f);

        private readonly List<Transform> _buttons = new List<Transform>();
        private TextMeshPro _camLabel;
        private TextMeshPro _micLabel;

        private void Awake()
        {
            if (perception == null) perception = FindObjectOfType<PerceptionController>();
            if (persistence == null) persistence = FindObjectOfType<HologramPersistence>();
            if (settings == null) settings = FindObjectOfType<SettingsController>();
            if (orchestration == null) orchestration = FindObjectOfType<OrchestrationController>();
            if (studio == null) studio = FindObjectOfType<StudioController>();
        }

        private void Start()
        {
            if (hand != null)
            {
                transform.SetParent(hand, false);
                transform.localPosition = localOffset;
                transform.localRotation = Quaternion.identity;
            }
            Build();
        }

        private void Build()
        {
            string[] labels = { "■ Stop capture", "Camera", "Mic", "Save layout", "Restore", "⚙ Settings", "Team", "Studio" };
            var accent = new[]
            {
                new Color(0.8f, 0.25f, 0.25f), new Color(0.2f, 0.4f, 0.7f), new Color(0.2f, 0.4f, 0.7f),
                new Color(0.25f, 0.5f, 0.35f), new Color(0.3f, 0.35f, 0.5f), new Color(0.35f, 0.3f, 0.55f),
                new Color(0.2f, 0.45f, 0.6f), new Color(0.3f, 0.45f, 0.4f),
            };

            for (int i = 0; i < labels.Length; i++)
            {
                float y = (labels.Length - 1) * 0.5f * 0.035f - i * 0.035f;
                var btn = GameObject.CreatePrimitive(PrimitiveType.Cube);
                btn.name = $"wrist_{i}";
                btn.transform.SetParent(transform, false);
                btn.transform.localPosition = new Vector3(0f, y, 0f);
                btn.transform.localScale = new Vector3(0.12f, 0.03f, 0.012f);
                var r = btn.GetComponent<Renderer>();
                if (r != null) r.material = HoloMaterials.Solid(accent[i]);
                _buttons.Add(btn.transform);

                var lblGo = new GameObject($"wrist_lbl_{i}");
                lblGo.transform.SetParent(transform, false);
                lblGo.transform.localPosition = new Vector3(0f, y, -0.012f);
                var lbl = lblGo.AddComponent<TextMeshPro>();
                lbl.text = labels[i];
                lbl.fontSize = 0.014f;
                lbl.alignment = TextAlignmentOptions.Center;
                lbl.color = Color.white;
                lbl.rectTransform.sizeDelta = new Vector2(0.11f, 0.03f);
                if (i == 1) _camLabel = lbl;
                if (i == 2) _micLabel = lbl;
            }

            var bb = gameObject.AddComponent<Billboard>();
            bb.yawOnly = false;
        }

        private void Update()
        {
            if (perception != null)
            {
                if (_camLabel != null) _camLabel.text = perception.VisionActive ? "Camera ●" : "Camera";
                if (_micLabel != null) _micLabel.text = perception.AmbientActive ? "Mic ●" : "Mic";
            }
#if ENABLE_LEGACY_INPUT_MANAGER
            if (Input.GetMouseButtonDown(0)) TryMouseActivate();
#endif
        }

        public void Activate(int index)
        {
            switch (index)
            {
                case 0: perception?.StopAllCapture(); break;
                case 1: perception?.ToggleVision(); break;
                case 2: perception?.ToggleAmbient(); break;
                case 3: persistence?.SaveLayout(); break;
                case 4: persistence?.RestoreLayout(); break;
                case 5: settings?.Toggle(); break;
                case 6: orchestration?.Toggle(); break;
                case 7: studio?.Toggle(); break;
            }
        }

#if ENABLE_LEGACY_INPUT_MANAGER
        private void TryMouseActivate()
        {
            var cam = Camera.main;
            if (cam == null) return;
            if (!Physics.Raycast(cam.ScreenPointToRay(Input.mousePosition), out var hit, 20f)) return;
            for (int i = 0; i < _buttons.Count; i++)
                if (_buttons[i] != null && hit.collider.transform == _buttons[i]) { Activate(i); break; }
        }
#endif
    }
}
