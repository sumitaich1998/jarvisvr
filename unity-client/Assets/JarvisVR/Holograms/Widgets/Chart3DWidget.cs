using System.Collections.Generic;
using UnityEngine;
using TMPro;
using Newtonsoft.Json.Linq;

namespace JarvisVR.Holograms.Widgets
{
    /// <summary>
    /// widget_type "chart_3d". Renders a 3D bar chart from a numeric series.
    /// Props: { title, values:[..] | series:[..], labels:[..], color }.
    /// </summary>
    public class Chart3DWidget : HoloWidget
    {
        private TextMeshPro _title;
        private Transform _bars;
        private readonly List<Transform> _bar = new List<Transform>();

        protected override void Build()
        {
            _title = CreateText("title", "", 0.045f, new Color(0.7f, 0.9f, 1f),
                new Vector3(0f, 0.22f, 0f), align: TextAlignmentOptions.Center, size: new Vector2(0.6f, 0.06f));
            _bars = new GameObject("bars").transform;
            _bars.SetParent(transform, false);
        }

        protected override void ApplyProps(JObject props)
        {
            _title.text = GetString("title", "Chart");

            var values = GetArray("values") ?? GetArray("series");
            var labels = GetArray("labels");
            Color baseColor = GetColor("color", new Color(0.2f, 0.8f, 1f));

            RebuildBars(values, labels, baseColor);
        }

        private void RebuildBars(JArray values, JArray labels, Color baseColor)
        {
            foreach (var b in _bar) if (b != null) Destroy(b.gameObject);
            _bar.Clear();
            if (values == null || values.Count == 0) return;

            int n = values.Count;
            float max = 0.0001f;
            var nums = new float[n];
            for (int i = 0; i < n; i++)
            {
                nums[i] = SafeFloat(values[i]);
                max = Mathf.Max(max, Mathf.Abs(nums[i]));
            }

            float width = 0.5f;
            float step = width / Mathf.Max(1, n);
            float barW = step * 0.7f;

            for (int i = 0; i < n; i++)
            {
                float h = Mathf.Max(0.01f, (Mathf.Abs(nums[i]) / max) * 0.4f);
                float x = -width * 0.5f + step * (i + 0.5f);
                var col = Color.Lerp(baseColor, new Color(1f, 0.5f, 0.3f), n > 1 ? i / (float)(n - 1) : 0f);
                var bar = CreatePrimitive(PrimitiveType.Cube, $"bar_{i}", new Vector3(x, h * 0.5f - 0.18f, 0f),
                    new Vector3(barW, h, barW), col, _bars);
                _bar.Add(bar);

                string lbl = labels != null && i < labels.Count ? labels[i].ToString() : null;
                if (!string.IsNullOrEmpty(lbl))
                    CreateText($"lbl_{i}", lbl, 0.022f, Color.white, new Vector3(x, -0.2f, 0f), _bars,
                        TextAlignmentOptions.Center, new Vector2(step, 0.04f));
            }
        }

        private static float SafeFloat(JToken t)
            => (t != null && (t.Type == JTokenType.Float || t.Type == JTokenType.Integer)) ? t.Value<float>() : 0f;
    }
}
