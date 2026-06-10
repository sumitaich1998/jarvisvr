using System;
using System.Collections.Generic;
using UnityEngine;
using TMPro;
using Newtonsoft.Json.Linq;

namespace JarvisVR.Holograms.Widgets
{
    /// <summary>
    /// widget_type "world_clock". A list of cities/zones with live times.
    /// Props: { title, zones:[{label, offset_hours}] }.
    /// </summary>
    public class WorldClockWidget : HoloWidget
    {
        private TextMeshPro _title;
        private Transform _rows;
        private readonly List<(TextMeshPro time, float offset)> _entries = new List<(TextMeshPro, float)>();

        protected override void Build()
        {
            CreatePrimitive(PrimitiveType.Cube, "bg", Vector3.zero, new Vector3(0.5f, 0.36f, 0.01f),
                new Color(0.06f, 0.07f, 0.12f, 0.95f));
            _title = CreateText("title", "World Clock", 0.034f, new Color(0.7f, 0.8f, 1f),
                new Vector3(0f, 0.15f, -0.011f), align: TextAlignmentOptions.Center, size: new Vector2(0.46f, 0.05f));
            _rows = new GameObject("rows").transform;
            _rows.SetParent(transform, false);
        }

        protected override void ApplyProps(JObject props)
        {
            _title.text = GetString("title", "World Clock");
            foreach (Transform c in _rows) Destroy(c.gameObject);
            _entries.Clear();

            var zones = GetArray("zones");
            if (zones == null) return;
            float top = 0.09f;
            for (int i = 0; i < zones.Count && i < 6; i++)
            {
                if (!(zones[i] is JObject z)) continue;
                string label = z.TryGetValue("label", out var lv) ? lv.ToString() : $"Zone {i + 1}";
                float offset = z.TryGetValue("offset_hours", out var ov) ? ov.Value<float>() : 0f;
                float y = top - i * 0.05f;
                CreateText($"z_{i}", label, 0.028f, Color.white, new Vector3(-0.12f, y, -0.011f), _rows,
                    TextAlignmentOptions.Left, new Vector2(0.24f, 0.05f));
                var tm = CreateText($"t_{i}", "", 0.028f, new Color(0.8f, 0.9f, 1f), new Vector3(0.14f, y, -0.011f), _rows,
                    TextAlignmentOptions.Right, new Vector2(0.18f, 0.05f));
                _entries.Add((tm, offset));
            }
            Render();
        }

        private void Update() => Render();

        private void Render()
        {
            foreach (var e in _entries)
                if (e.time != null) e.time.text = DateTime.UtcNow.AddHours(e.offset).ToString("HH:mm");
        }
    }
}
