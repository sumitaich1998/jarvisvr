using System.Collections.Generic;
using UnityEngine;
using TMPro;
using Newtonsoft.Json.Linq;

namespace JarvisVR.Holograms.Widgets
{
    /// <summary>
    /// widget_type "map_3d". A flat map tile with pin markers (a real build would texture the tile
    /// from a tile provider). Props: { center:{lat,lng}, zoom, markers:[{lat,lng,label}], title }.
    /// Markers are tappable (collider names "marker_0", "marker_1", ...).
    /// </summary>
    public class Map3DWidget : HoloWidget
    {
        private const float TileSize = 0.5f;

        private TextMeshPro _title;
        private Transform _markers;
        private readonly List<GameObject> _pins = new List<GameObject>();

        protected override void Build()
        {
            CreatePrimitive(PrimitiveType.Cube, "tile", Vector3.zero, new Vector3(TileSize, TileSize, 0.01f),
                new Color(0.12f, 0.18f, 0.16f));
            // subtle grid lines
            for (int i = 1; i < 4; i++)
            {
                float o = (i / 4f - 0.5f) * TileSize;
                CreatePrimitive(PrimitiveType.Cube, $"gx{i}", new Vector3(o, 0, -0.006f), new Vector3(0.003f, TileSize, 0.002f), new Color(0.25f, 0.35f, 0.3f));
                CreatePrimitive(PrimitiveType.Cube, $"gy{i}", new Vector3(0, o, -0.006f), new Vector3(TileSize, 0.003f, 0.002f), new Color(0.25f, 0.35f, 0.3f));
            }
            _title = CreateText("title", "", 0.035f, new Color(0.8f, 0.95f, 0.85f), new Vector3(0f, TileSize * 0.5f + 0.03f, 0f),
                align: TextAlignmentOptions.Center, size: new Vector2(TileSize, 0.05f));
            _markers = new GameObject("markers").transform;
            _markers.SetParent(transform, false);
        }

        protected override void ApplyProps(JObject props)
        {
            _title.text = GetString("title", "Map");

            var center = GetObject("center");
            float cLat = center != null ? Safe(center, "lat") : GetFloat("lat", 0f);
            float cLng = center != null ? Safe(center, "lng") : GetFloat("lng", 0f);
            float zoom = GetFloat("zoom", 10f);
            float span = 180f / Mathf.Pow(2f, Mathf.Clamp(zoom, 1f, 18f)); // degrees visible across the tile
            float k = (TileSize * 0.5f) / Mathf.Max(0.0001f, span);

            foreach (var p in _pins) if (p != null) Destroy(p);
            _pins.Clear();

            var markers = GetArray("markers");
            if (markers == null) return;
            for (int i = 0; i < markers.Count; i++)
            {
                if (!(markers[i] is JObject m)) continue;
                float lat = Safe(m, "lat");
                float lng = Safe(m, "lng");
                float x = Mathf.Clamp((lng - cLng) * k, -TileSize * 0.5f, TileSize * 0.5f);
                float y = Mathf.Clamp((lat - cLat) * k, -TileSize * 0.5f, TileSize * 0.5f);

                var pin = CreatePrimitive(PrimitiveType.Cylinder, $"marker_{i}", new Vector3(x, y, -0.03f),
                    new Vector3(0.02f, 0.03f, 0.02f), new Color(1f, 0.35f, 0.3f), _markers, keepCollider: true);
                pin.localRotation = Quaternion.Euler(90f, 0f, 0f);
                _pins.Add(pin.gameObject);

                string label = m.TryGetValue("label", out var lv) ? lv.ToString() : null;
                if (!string.IsNullOrEmpty(label))
                    CreateText($"marker_lbl_{i}", label, 0.022f, Color.white, new Vector3(x, y + 0.04f, -0.03f), _markers,
                        TextAlignmentOptions.Center, new Vector2(0.18f, 0.03f));
            }
        }

        private static float Safe(JObject o, string key)
            => o.TryGetValue(key, out var v) && (v.Type == JTokenType.Float || v.Type == JTokenType.Integer) ? v.Value<float>() : 0f;
    }
}
