using UnityEngine;
using TMPro;
using Newtonsoft.Json.Linq;

namespace JarvisVR.Holograms.Widgets
{
    /// <summary>
    /// widget_type "data_table". A simple header + rows grid. Props:
    /// { title, columns:["A","B"], rows:[["1","2"], ...] }.
    /// </summary>
    public class DataTableWidget : HoloWidget
    {
        private TextMeshPro _title;
        private Transform _cells;

        protected override void Build()
        {
            _title = CreateText("title", "", 0.034f, new Color(0.8f, 0.88f, 1f), Vector3.zero,
                align: TextAlignmentOptions.Center, size: new Vector2(0.6f, 0.05f));
            _cells = new GameObject("cells").transform;
            _cells.SetParent(transform, false);
        }

        protected override void ApplyProps(JObject props)
        {
            _title.text = GetString("title", "Table");
            foreach (Transform c in _cells) Destroy(c.gameObject);

            var cols = GetArray("columns");
            var rows = GetArray("rows");
            int nc = cols?.Count ?? (rows != null && rows.Count > 0 && rows[0] is JArray r0 ? r0.Count : 0);
            if (nc == 0) return;

            float width = Mathf.Min(0.8f, 0.16f * nc);
            float colW = width / nc;
            float x0 = -width * 0.5f + colW * 0.5f;
            float top = 0.16f;
            float rowH = 0.05f;

            CreatePrimitive(PrimitiveType.Cube, "bg", new Vector3(0, top - 0.005f, 0.002f), new Vector3(width + 0.04f, 0.5f, 0.008f),
                new Color(0.06f, 0.07f, 0.11f, 0.95f));

            if (cols != null)
                for (int c = 0; c < nc; c++)
                    CreateText($"h{c}", c < cols.Count ? cols[c].ToString() : "", 0.026f, new Color(0.6f, 0.8f, 1f),
                        new Vector3(x0 + c * colW, top, -0.006f), _cells, TextAlignmentOptions.Center, new Vector2(colW, rowH));

            if (rows == null) return;
            for (int r = 0; r < rows.Count && r < 10; r++)
            {
                if (!(rows[r] is JArray row)) continue;
                float y = top - rowH - r * rowH;
                for (int c = 0; c < nc && c < row.Count; c++)
                    CreateText($"c{r}_{c}", row[c].ToString(), 0.024f, Color.white,
                        new Vector3(x0 + c * colW, y, -0.006f), _cells, TextAlignmentOptions.Center, new Vector2(colW, rowH));
            }
        }
    }
}
