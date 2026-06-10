using System.Collections.Generic;
using UnityEngine;
using TMPro;
using Newtonsoft.Json.Linq;

namespace JarvisVR.Holograms.Widgets
{
    /// <summary>
    /// widget_type "smart_home_panel". A list of device rows with on/off indicators.
    /// Props: { title, devices:[{id,name,type,on,value}] }.
    /// Tapping a row indicator (collider "device_&lt;id&gt;") reports a tap with that element.
    /// </summary>
    public class SmartHomePanelWidget : HoloWidget
    {
        private const float Width = 0.5f;
        private const float RowH = 0.07f;

        private Transform _bg;
        private TextMeshPro _title;
        private Transform _rows;

        protected override void Build()
        {
            _bg = CreatePrimitive(PrimitiveType.Cube, "bg", Vector3.zero, new Vector3(Width, 0.4f, 0.01f),
                new Color(0.09f, 0.11f, 0.16f, 0.96f));
            _title = CreateText("title", "", 0.04f, new Color(0.7f, 0.9f, 1f), Vector3.zero,
                align: TextAlignmentOptions.Center, size: new Vector2(Width * 0.95f, 0.06f));
            _rows = new GameObject("rows").transform;
            _rows.SetParent(transform, false);
        }

        protected override void ApplyProps(JObject props)
        {
            _title.text = GetString("title", "Smart Home");

            foreach (Transform c in _rows) Destroy(c.gameObject);

            var devices = GetArray("devices");
            int n = devices?.Count ?? 0;
            float panelH = Mathf.Max(0.2f, 0.1f + n * RowH);
            _bg.localScale = new Vector3(Width, panelH, 0.01f);
            _title.transform.localPosition = new Vector3(0f, panelH * 0.5f - 0.05f, -0.011f);

            if (devices == null) return;
            float top = panelH * 0.5f - 0.12f;
            for (int i = 0; i < n; i++)
            {
                if (!(devices[i] is JObject d)) continue;
                string id = d.TryGetValue("id", out var idv) ? idv.ToString() : $"dev{i}";
                string name = d.TryGetValue("name", out var nv) ? nv.ToString() : id;
                bool on = d.TryGetValue("on", out var ov) && ov.Type == JTokenType.Boolean && ov.Value<bool>();
                float y = top - i * RowH;

                var dot = CreatePrimitive(PrimitiveType.Sphere, $"device_{id}", new Vector3(-Width * 0.5f + 0.05f, y, -0.012f),
                    Vector3.one * 0.035f, on ? new Color(0.3f, 0.9f, 0.4f) : new Color(0.4f, 0.42f, 0.48f), _rows, keepCollider: true);

                CreateText($"name_{i}", name, 0.03f, Color.white, new Vector3(-0.02f, y, -0.012f), _rows,
                    TextAlignmentOptions.Left, new Vector2(Width * 0.6f, RowH));
                CreateText($"state_{i}", on ? "ON" : "OFF", 0.028f, on ? new Color(0.4f, 0.95f, 0.5f) : new Color(0.6f, 0.62f, 0.68f),
                    new Vector3(Width * 0.5f - 0.06f, y, -0.012f), _rows, TextAlignmentOptions.Right, new Vector2(0.12f, RowH));
            }
        }
    }
}
