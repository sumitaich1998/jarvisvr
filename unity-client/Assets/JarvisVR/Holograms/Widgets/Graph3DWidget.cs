using System.Collections.Generic;
using UnityEngine;
using TMPro;
using Newtonsoft.Json.Linq;

namespace JarvisVR.Holograms.Widgets
{
    /// <summary>
    /// widget_type "graph_3d". A node/edge network. Nodes use given positions or a circular layout;
    /// each node reports a tap with element "node_&lt;id&gt;". Props:
    /// { title, nodes:[{id,label,position:[x,y,z],color}], edges:[[a,b] | {from,to}] }.
    /// </summary>
    public class Graph3DWidget : HoloWidget
    {
        private TextMeshPro _title;
        private Transform _root;
        private readonly Dictionary<string, Vector3> _pos = new Dictionary<string, Vector3>();

        protected override void Build()
        {
            _title = CreateText("title", "", 0.034f, new Color(0.8f, 0.85f, 1f), new Vector3(0f, 0.22f, 0f),
                align: TextAlignmentOptions.Center, size: new Vector2(0.5f, 0.05f));
            _root = new GameObject("graph").transform;
            _root.SetParent(transform, false);
        }

        protected override void ApplyProps(JObject props)
        {
            _title.text = GetString("title", "");
            foreach (Transform c in _root) Destroy(c.gameObject);
            _pos.Clear();

            var nodes = GetArray("nodes");
            if (nodes == null) return;

            // positions
            for (int i = 0; i < nodes.Count; i++)
            {
                if (!(nodes[i] is JObject n)) continue;
                string id = n.TryGetValue("id", out var idv) ? idv.ToString() : i.ToString();
                Vector3 p;
                if (n.TryGetValue("position", out var pv) && pv is JArray pa && pa.Count >= 3)
                    p = new Vector3(pa[0].Value<float>(), pa[1].Value<float>(), pa[2].Value<float>());
                else
                {
                    float a = (i / (float)nodes.Count) * Mathf.PI * 2f;
                    p = new Vector3(Mathf.Cos(a) * 0.18f, Mathf.Sin(a) * 0.18f, 0f);
                }
                _pos[id] = p;
            }

            // edges first (so nodes render on top)
            var edges = GetArray("edges");
            if (edges != null)
                foreach (var e in edges) DrawEdge(e);

            // nodes
            for (int i = 0; i < nodes.Count; i++)
            {
                if (!(nodes[i] is JObject n)) continue;
                string id = n.TryGetValue("id", out var idv) ? idv.ToString() : i.ToString();
                string label = n.TryGetValue("label", out var lv) ? lv.ToString() : id;
                Color col = n.TryGetValue("color", out var cv) ? Util.ColorUtil.Parse(cv.ToString(), new Color(0.3f, 0.7f, 1f)) : new Color(0.3f, 0.7f, 1f);
                var p = _pos[id];
                CreatePrimitive(PrimitiveType.Sphere, $"node_{id}", p, Vector3.one * 0.04f, col, _root, keepCollider: true);
                CreateText($"lbl_{id}", label, 0.02f, Color.white, p + new Vector3(0, 0.04f, -0.01f), _root,
                    TextAlignmentOptions.Center, new Vector2(0.16f, 0.03f));
            }
        }

        private void DrawEdge(JToken e)
        {
            string a = null, b = null;
            if (e is JArray arr && arr.Count >= 2) { a = arr[0].ToString(); b = arr[1].ToString(); }
            else if (e is JObject o) { a = o.Value<string>("from"); b = o.Value<string>("to"); }
            if (a == null || b == null || !_pos.TryGetValue(a, out var pa) || !_pos.TryGetValue(b, out var pb)) return;

            Vector3 mid = (pa + pb) * 0.5f;
            Vector3 dir = pb - pa;
            float len = dir.magnitude;
            var edge = CreatePrimitive(PrimitiveType.Cube, "edge", mid, new Vector3(0.006f, 0.006f, Mathf.Max(0.001f, len)),
                new Color(0.5f, 0.55f, 0.7f, 0.7f), _root);
            if (len > 1e-4f) edge.localRotation = Quaternion.LookRotation(dir);
        }
    }
}
