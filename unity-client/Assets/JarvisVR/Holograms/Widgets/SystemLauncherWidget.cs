using UnityEngine;
using TMPro;
using Newtonsoft.Json.Linq;

namespace JarvisVR.Holograms.Widgets
{
    /// <summary>
    /// widget_type "system_launcher". An app grid; each tile reports a tap with element "app_&lt;id&gt;".
    /// Props: { title, apps:[{id,name,color}], columns }.
    /// </summary>
    public class SystemLauncherWidget : HoloWidget
    {
        private TextMeshPro _title;
        private Transform _grid;

        protected override void Build()
        {
            CreatePrimitive(PrimitiveType.Cube, "bg", Vector3.zero, new Vector3(0.56f, 0.42f, 0.01f),
                new Color(0.06f, 0.07f, 0.1f, 0.95f));
            _title = CreateText("title", "Apps", 0.034f, new Color(0.75f, 0.85f, 1f), new Vector3(0f, 0.17f, -0.011f),
                align: TextAlignmentOptions.Center, size: new Vector2(0.5f, 0.05f));
            _grid = new GameObject("grid").transform;
            _grid.SetParent(transform, false);
        }

        protected override void ApplyProps(JObject props)
        {
            _title.text = GetString("title", "Apps");
            foreach (Transform c in _grid) Destroy(c.gameObject);

            var apps = GetArray("apps");
            if (apps == null) return;
            int cols = Mathf.Max(1, GetInt("columns", 4));
            float tile = 0.1f, gap = 0.03f, step = tile + gap;
            float x0 = -(cols - 1) * step * 0.5f;
            float y0 = 0.08f;

            for (int i = 0; i < apps.Count; i++)
            {
                if (!(apps[i] is JObject a)) continue;
                string id = a.TryGetValue("id", out var idv) ? idv.ToString() : $"app{i}";
                string name = a.TryGetValue("name", out var nv) ? nv.ToString() : id;
                Color col = a.TryGetValue("color", out var cv) ? Util.ColorUtil.Parse(cv.ToString(), new Color(0.2f, 0.45f, 0.85f)) : new Color(0.2f, 0.45f, 0.85f);
                int r = i / cols, c = i % cols;
                var pos = new Vector3(x0 + c * step, y0 - r * step, -0.012f);

                CreatePrimitive(PrimitiveType.Cube, $"app_{id}", pos, new Vector3(tile, tile, 0.02f), col, _grid, keepCollider: true);
                CreateText($"name_{i}", name, 0.02f, Color.white, pos + new Vector3(0, -0.065f, -0.01f), _grid,
                    TextAlignmentOptions.Center, new Vector2(step, 0.03f));
            }
        }
    }
}
