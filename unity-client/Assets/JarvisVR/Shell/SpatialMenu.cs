using System.Collections.Generic;
using UnityEngine;
using TMPro;
using JarvisVR.Net;
using JarvisVR.Holograms;

namespace JarvisVR.Shell
{
    /// <summary>
    /// A minimal spatial main menu: a small floating panel of quick voice-equivalent commands.
    /// Activating an item sends a <c>user.text</c> message (as if the user spoke it), letting you
    /// drive the agent without the voice pipeline. Buttons carry colliders named "menu_0", "menu_1",
    /// … so the in-editor mouse tester or a Meta poke interactable can trigger them.
    /// </summary>
    [DisallowMultipleComponent]
    public class SpatialMenu : MonoBehaviour
    {
        public JarvisConnection connection;
        public Transform follow;
        public SettingsController settings;
        public OrchestrationController orchestration;
        public StudioController studio;
        public bool placeOnStart = true;
        public Vector3 headOffset = new Vector3(-0.45f, -0.1f, 0.7f);

        [Tooltip("Quick commands sent as user.text when activated.")]
        public List<string> commands = new List<string>
        {
            "What's the weather in Tokyo?",
            "Start a 5 minute timer",
            "Show my to-do list",
            "Play some music",
        };

        private readonly List<Transform> _buttons = new List<Transform>();
        private Transform _settingsButton;
        private Transform _teamButton;
        private Transform _studioButton;

        private void Awake()
        {
            if (connection == null) connection = FindObjectOfType<JarvisConnection>();
            if (settings == null) settings = FindObjectOfType<SettingsController>();
            if (orchestration == null) orchestration = FindObjectOfType<OrchestrationController>();
            if (studio == null) studio = FindObjectOfType<StudioController>();
        }

        private void Start()
        {
            Build();
            if (placeOnStart) PlaceInFront();
        }

        private void Build()
        {
            var titleGo = new GameObject("MenuTitle");
            titleGo.transform.SetParent(transform, false);
            titleGo.transform.localPosition = new Vector3(0f, 0.09f + commands.Count * 0.055f * 0.5f, 0f);
            var title = titleGo.AddComponent<TextMeshPro>();
            title.text = "Jarvis";
            title.fontSize = 0.05f;
            title.alignment = TextAlignmentOptions.Center;
            title.color = new Color(0.6f, 0.85f, 1f);
            title.rectTransform.sizeDelta = new Vector2(0.4f, 0.06f);

            float top = (commands.Count - 1) * 0.5f * 0.06f;
            for (int i = 0; i < commands.Count; i++)
            {
                float y = top - i * 0.06f;
                var btn = GameObject.CreatePrimitive(PrimitiveType.Cube);
                btn.name = $"menu_{i}";
                btn.transform.SetParent(transform, false);
                btn.transform.localPosition = new Vector3(0f, y, 0f);
                btn.transform.localScale = new Vector3(0.36f, 0.05f, 0.02f);
                var r = btn.GetComponent<Renderer>();
                if (r != null) r.material = HoloMaterials.Solid(new Color(0.15f, 0.2f, 0.32f, 0.95f));
                _buttons.Add(btn.transform);

                var lblGo = new GameObject($"menu_lbl_{i}");
                lblGo.transform.SetParent(transform, false);
                lblGo.transform.localPosition = new Vector3(0f, y, -0.02f);
                var lbl = lblGo.AddComponent<TextMeshPro>();
                lbl.text = commands[i];
                lbl.fontSize = 0.022f;
                lbl.alignment = TextAlignmentOptions.Center;
                lbl.color = Color.white;
                lbl.rectTransform.sizeDelta = new Vector2(0.34f, 0.05f);
            }

            // Settings entry — opens the in-headset Settings panel locally (not sent to the agent).
            float sy = top - commands.Count * 0.06f;
            var sbtn = GameObject.CreatePrimitive(PrimitiveType.Cube);
            sbtn.name = "menu_settings";
            sbtn.transform.SetParent(transform, false);
            sbtn.transform.localPosition = new Vector3(0f, sy, 0f);
            sbtn.transform.localScale = new Vector3(0.36f, 0.05f, 0.02f);
            var sr = sbtn.GetComponent<Renderer>();
            if (sr != null) sr.material = HoloMaterials.Solid(new Color(0.25f, 0.22f, 0.4f, 0.95f));
            _settingsButton = sbtn.transform;

            var slGo = new GameObject("menu_settings_lbl");
            slGo.transform.SetParent(transform, false);
            slGo.transform.localPosition = new Vector3(0f, sy, -0.02f);
            var slbl = slGo.AddComponent<TextMeshPro>();
            slbl.text = "⚙ Settings";
            slbl.fontSize = 0.022f;
            slbl.alignment = TextAlignmentOptions.Center;
            slbl.color = Color.white;
            slbl.rectTransform.sizeDelta = new Vector2(0.34f, 0.05f);

            // Agent Team entry — toggles the orchestration org-chart view locally.
            float ty = top - (commands.Count + 1) * 0.06f;
            var tbtn = GameObject.CreatePrimitive(PrimitiveType.Cube);
            tbtn.name = "menu_team";
            tbtn.transform.SetParent(transform, false);
            tbtn.transform.localPosition = new Vector3(0f, ty, 0f);
            tbtn.transform.localScale = new Vector3(0.36f, 0.05f, 0.02f);
            var tr = tbtn.GetComponent<Renderer>();
            if (tr != null) tr.material = HoloMaterials.Solid(new Color(0.18f, 0.32f, 0.42f, 0.95f));
            _teamButton = tbtn.transform;

            var tlGo = new GameObject("menu_team_lbl");
            tlGo.transform.SetParent(transform, false);
            tlGo.transform.localPosition = new Vector3(0f, ty, -0.02f);
            var tlbl = tlGo.AddComponent<TextMeshPro>();
            tlbl.text = "Agent Team";
            tlbl.fontSize = 0.022f;
            tlbl.alignment = TextAlignmentOptions.Center;
            tlbl.color = Color.white;
            tlbl.rectTransform.sizeDelta = new Vector2(0.34f, 0.05f);

            // Studio entry — opens the in-headset agent/skill composer locally.
            float uy = top - (commands.Count + 2) * 0.06f;
            var ubtn = GameObject.CreatePrimitive(PrimitiveType.Cube);
            ubtn.name = "menu_studio";
            ubtn.transform.SetParent(transform, false);
            ubtn.transform.localPosition = new Vector3(0f, uy, 0f);
            ubtn.transform.localScale = new Vector3(0.36f, 0.05f, 0.02f);
            var ur = ubtn.GetComponent<Renderer>();
            if (ur != null) ur.material = HoloMaterials.Solid(new Color(0.2f, 0.34f, 0.32f, 0.95f));
            _studioButton = ubtn.transform;

            var ulGo = new GameObject("menu_studio_lbl");
            ulGo.transform.SetParent(transform, false);
            ulGo.transform.localPosition = new Vector3(0f, uy, -0.02f);
            var ulbl = ulGo.AddComponent<TextMeshPro>();
            ulbl.text = "Studio";
            ulbl.fontSize = 0.022f;
            ulbl.alignment = TextAlignmentOptions.Center;
            ulbl.color = Color.white;
            ulbl.rectTransform.sizeDelta = new Vector2(0.34f, 0.05f);

            var bb = gameObject.AddComponent<Billboard>();
            bb.target = follow;
            bb.yawOnly = true;
        }

        public void PlaceInFront()
        {
            var head = follow != null ? follow : (Camera.main != null ? Camera.main.transform : null);
            if (head == null) return;
            transform.position = head.position + head.forward * headOffset.z + head.right * headOffset.x + head.up * headOffset.y;
        }

        /// <summary>Activate a menu item by index (call from Meta poke or the mouse tester).</summary>
        public void Activate(int index, string hand = null)
        {
            if (index < 0 || index >= commands.Count || connection == null) return;
            connection.SendText(commands[index]);
        }

        /// <summary>Open the in-headset Settings panel (call from Meta poke / the Settings entry).</summary>
        public void OpenSettings() => settings?.Toggle();

        /// <summary>Toggle the Agent Team org-chart view (call from Meta poke / the Team entry).</summary>
        public void OpenTeam() => orchestration?.Toggle();

        /// <summary>Toggle the Studio composer (call from Meta poke / the Studio entry).</summary>
        public void OpenStudio() => studio?.Toggle();

#if ENABLE_LEGACY_INPUT_MANAGER
        private void Update()
        {
            if (!Input.GetMouseButtonDown(0)) return;
            var cam = Camera.main;
            if (cam == null) return;
            if (!Physics.Raycast(cam.ScreenPointToRay(Input.mousePosition), out var hit, 20f)) return;
            for (int i = 0; i < _buttons.Count; i++)
            {
                if (_buttons[i] != null && hit.collider.transform == _buttons[i])
                {
                    Activate(i, "right");
                    return;
                }
            }
            if (_settingsButton != null && hit.collider.transform == _settingsButton) { settings?.Toggle(); return; }
            if (_teamButton != null && hit.collider.transform == _teamButton) { orchestration?.Toggle(); return; }
            if (_studioButton != null && hit.collider.transform == _studioButton) studio?.Toggle();
        }
#endif
    }
}
