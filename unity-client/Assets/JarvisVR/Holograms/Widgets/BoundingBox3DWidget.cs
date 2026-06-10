using System.Collections.Generic;
using UnityEngine;
using TMPro;
using Newtonsoft.Json.Linq;

namespace JarvisVR.Holograms.Widgets
{
    /// <summary>
    /// widget_type "bounding_box_3d" (§8.5). A wireframe box around a detected real-world object.
    /// Props: { size:[x,y,z] (meters) | extents, label, color }.
    /// </summary>
    public class BoundingBox3DWidget : HoloWidget
    {
        private Transform _edges;
        private TextMeshPro _label;
        private readonly List<Transform> _edge = new List<Transform>();

        protected override void Build()
        {
            _edges = new GameObject("edges").transform;
            _edges.SetParent(transform, false);
            _label = CreateText("label", "", 0.03f, Color.white, Vector3.zero,
                align: TextAlignmentOptions.Center, size: new Vector2(0.3f, 0.05f));
        }

        protected override void ApplyProps(JObject props)
        {
            Vector3 size = ReadSize();
            var color = GetColor("color", new Color(0.3f, 1f, 0.6f));
            RebuildEdges(size, color);
            _label.text = GetString("label", "");
            _label.transform.localPosition = new Vector3(0f, size.y * 0.5f + 0.04f, 0f);
            _label.color = color;
        }

        private Vector3 ReadSize()
        {
            var a = GetArray("size") ?? GetArray("extents");
            if (a != null && a.Count >= 3)
                return new Vector3(SafeF(a[0]), SafeF(a[1]), SafeF(a[2]));
            return Vector3.one * 0.3f;
        }

        private void RebuildEdges(Vector3 s, Color c)
        {
            foreach (var e in _edge) if (e != null) Destroy(e.gameObject);
            _edge.Clear();

            Vector3 h = s * 0.5f;
            float t = 0.006f;
            // 4 verticals
            AddEdge(new Vector3(-h.x, 0, -h.z), new Vector3(t, s.y, t), c);
            AddEdge(new Vector3(h.x, 0, -h.z), new Vector3(t, s.y, t), c);
            AddEdge(new Vector3(-h.x, 0, h.z), new Vector3(t, s.y, t), c);
            AddEdge(new Vector3(h.x, 0, h.z), new Vector3(t, s.y, t), c);
            // 4 along X (top + bottom)
            AddEdge(new Vector3(0, h.y, -h.z), new Vector3(s.x, t, t), c);
            AddEdge(new Vector3(0, -h.y, -h.z), new Vector3(s.x, t, t), c);
            AddEdge(new Vector3(0, h.y, h.z), new Vector3(s.x, t, t), c);
            AddEdge(new Vector3(0, -h.y, h.z), new Vector3(s.x, t, t), c);
            // 4 along Z (top + bottom)
            AddEdge(new Vector3(-h.x, h.y, 0), new Vector3(t, t, s.z), c);
            AddEdge(new Vector3(h.x, h.y, 0), new Vector3(t, t, s.z), c);
            AddEdge(new Vector3(-h.x, -h.y, 0), new Vector3(t, t, s.z), c);
            AddEdge(new Vector3(h.x, -h.y, 0), new Vector3(t, t, s.z), c);
        }

        private void AddEdge(Vector3 pos, Vector3 scale, Color c)
            => _edge.Add(CreatePrimitive(PrimitiveType.Cube, "edge", pos, scale, c, _edges));

        private static float SafeF(JToken t)
            => (t != null && (t.Type == JTokenType.Float || t.Type == JTokenType.Integer)) ? t.Value<float>() : 0.3f;
    }
}
