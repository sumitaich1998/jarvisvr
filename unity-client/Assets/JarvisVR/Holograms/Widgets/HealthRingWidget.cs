using System.Collections.Generic;
using UnityEngine;
using TMPro;
using Newtonsoft.Json.Linq;

namespace JarvisVR.Holograms.Widgets
{
    /// <summary>
    /// widget_type "health_ring". Concentric activity rings (Move/Exercise/Stand style). Props:
    /// { rings:[{label,value,goal,color}], center_label } or a single { value, goal, color }.
    /// </summary>
    public class HealthRingWidget : HoloWidget
    {
        private const int Segments = 36;
        private TextMeshPro _center;
        private Transform _ringRoot;
        private readonly List<Transform> _segs = new List<Transform>();

        protected override void Build()
        {
            _ringRoot = new GameObject("rings").transform;
            _ringRoot.SetParent(transform, false);
            _center = CreateText("center", "", 0.03f, Color.white, new Vector3(0, 0, -0.02f),
                align: TextAlignmentOptions.Center, size: new Vector2(0.2f, 0.06f));
        }

        protected override void ApplyProps(JObject props)
        {
            foreach (var s in _segs) if (s != null) Destroy(s.gameObject);
            _segs.Clear();

            var rings = GetArray("rings");
            if (rings == null)
            {
                float v = GetFloat("value", 0.5f), g = Mathf.Max(0.0001f, GetFloat("goal", 1f));
                BuildRing(0.16f, Mathf.Clamp01(v / g), GetColor("color", new Color(1f, 0.3f, 0.4f)));
            }
            else
            {
                for (int i = 0; i < rings.Count && i < 3; i++)
                {
                    if (!(rings[i] is JObject r)) continue;
                    float v = r.TryGetValue("value", out var vv) ? vv.Value<float>() : 0f;
                    float g = r.TryGetValue("goal", out var gv) ? Mathf.Max(0.0001f, gv.Value<float>()) : 1f;
                    Color col = r.TryGetValue("color", out var cv) ? Util.ColorUtil.Parse(cv.ToString(), DefaultColor(i)) : DefaultColor(i);
                    BuildRing(0.16f - i * 0.045f, Mathf.Clamp01(v / g), col);
                }
            }
            _center.text = GetString("center_label", "");
        }

        private void BuildRing(float radius, float fraction, Color color)
        {
            int lit = Mathf.RoundToInt(fraction * Segments);
            for (int i = 0; i < Segments; i++)
            {
                float a = (i / (float)Segments) * Mathf.PI * 2f - Mathf.PI * 0.5f;
                var pos = new Vector3(Mathf.Cos(a) * radius, Mathf.Sin(a) * radius, 0f);
                bool on = i < lit;
                var c = on ? color : color * 0.25f;
                var seg = CreatePrimitive(PrimitiveType.Cube, "seg", pos, new Vector3(0.018f, 0.03f, 0.018f), c, _ringRoot);
                seg.localRotation = Quaternion.Euler(0, 0, a * Mathf.Rad2Deg);
                _segs.Add(seg);
            }
        }

        private static Color DefaultColor(int i)
        {
            switch (i)
            {
                case 0: return new Color(1f, 0.25f, 0.35f);
                case 1: return new Color(0.5f, 1f, 0.3f);
                default: return new Color(0.3f, 0.8f, 1f);
            }
        }
    }
}
