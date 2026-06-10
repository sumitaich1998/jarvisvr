using UnityEngine;
using TMPro;
using Newtonsoft.Json.Linq;

namespace JarvisVR.Holograms.Widgets
{
    /// <summary>
    /// widget_type "settings_panel". Rows of toggles/sliders. Each control reports a tap with
    /// element "set_&lt;id&gt;". Props: { title, settings:[{id,label,type:"toggle"|"slider",value}] }.
    /// </summary>
    public class SettingsPanelWidget : HoloWidget
    {
        private const float W = 0.54f;
        private const float RowH = 0.07f;
        private Transform _bg;
        private TextMeshPro _title;
        private Transform _rows;

        protected override void Build()
        {
            _bg = CreatePrimitive(PrimitiveType.Cube, "bg", Vector3.zero, new Vector3(W, 0.4f, 0.01f),
                new Color(0.08f, 0.09f, 0.13f, 0.96f));
            _title = CreateText("title", "Settings", 0.036f, new Color(0.75f, 0.85f, 1f), Vector3.zero,
                align: TextAlignmentOptions.Center, size: new Vector2(W * 0.95f, 0.05f));
            _rows = new GameObject("rows").transform;
            _rows.SetParent(transform, false);
        }

        protected override void ApplyProps(JObject props)
        {
            _title.text = GetString("title", "Settings");
            foreach (Transform c in _rows) Destroy(c.gameObject);

            var settings = GetArray("settings");
            int n = settings?.Count ?? 0;
            float panelH = Mathf.Max(0.2f, 0.12f + n * RowH);
            _bg.localScale = new Vector3(W, panelH, 0.01f);
            _title.transform.localPosition = new Vector3(0f, panelH * 0.5f - 0.05f, -0.011f);
            if (settings == null) return;

            float top = panelH * 0.5f - 0.13f;
            for (int i = 0; i < n; i++)
            {
                if (!(settings[i] is JObject s)) continue;
                string id = s.TryGetValue("id", out var idv) ? idv.ToString() : $"s{i}";
                string label = s.TryGetValue("label", out var lv) ? lv.ToString() : id;
                string type = s.TryGetValue("type", out var tv) ? tv.ToString() : "toggle";
                float y = top - i * RowH;

                CreateText($"lbl_{i}", label, 0.028f, Color.white, new Vector3(-W * 0.5f + 0.04f, y, -0.012f), _rows,
                    TextAlignmentOptions.Left, new Vector2(W * 0.55f, RowH));

                if (type == "slider")
                {
                    float v = s.TryGetValue("value", out var vv) && (vv.Type == JTokenType.Float || vv.Type == JTokenType.Integer) ? Mathf.Clamp01(vv.Value<float>()) : 0.5f;
                    float barW = 0.18f, bx = W * 0.5f - 0.13f;
                    CreatePrimitive(PrimitiveType.Cube, $"track_{i}", new Vector3(bx, y, -0.012f), new Vector3(barW, 0.01f, 0.004f), new Color(0.3f, 0.32f, 0.4f), _rows);
                    CreatePrimitive(PrimitiveType.Cube, $"set_{id}", new Vector3(bx - barW * 0.5f + barW * v, y, -0.014f), new Vector3(0.02f, 0.03f, 0.01f), new Color(0.3f, 0.7f, 1f), _rows, keepCollider: true);
                }
                else
                {
                    bool on = s.TryGetValue("value", out var vv) && vv.Type == JTokenType.Boolean && vv.Value<bool>();
                    CreatePrimitive(PrimitiveType.Sphere, $"set_{id}", new Vector3(W * 0.5f - 0.06f, y, -0.012f), Vector3.one * 0.035f,
                        on ? new Color(0.3f, 0.9f, 0.45f) : new Color(0.4f, 0.42f, 0.5f), _rows, keepCollider: true);
                }
            }
        }
    }
}
