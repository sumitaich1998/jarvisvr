using UnityEngine;
using TMPro;
using Newtonsoft.Json.Linq;

namespace JarvisVR.Holograms.Widgets
{
    /// <summary>
    /// widget_type "stocks_ticker". Rows of symbol / price / % change (green up, red down).
    /// Props: { title, items:[{symbol, price, change_pct}] }.
    /// </summary>
    public class StocksTickerWidget : HoloWidget
    {
        private TextMeshPro _title;
        private Transform _rows;

        protected override void Build()
        {
            CreatePrimitive(PrimitiveType.Cube, "bg", Vector3.zero, new Vector3(0.5f, 0.36f, 0.01f),
                new Color(0.05f, 0.06f, 0.09f, 0.96f));
            _title = CreateText("title", "Markets", 0.032f, new Color(0.7f, 0.85f, 1f), new Vector3(0f, 0.15f, -0.011f),
                align: TextAlignmentOptions.Center, size: new Vector2(0.46f, 0.05f));
            _rows = new GameObject("rows").transform;
            _rows.SetParent(transform, false);
        }

        protected override void ApplyProps(JObject props)
        {
            _title.text = GetString("title", "Markets");
            foreach (Transform c in _rows) Destroy(c.gameObject);

            var items = GetArray("items");
            if (items == null) return;
            float top = 0.09f;
            for (int i = 0; i < items.Count && i < 6; i++)
            {
                if (!(items[i] is JObject it)) continue;
                string sym = it.TryGetValue("symbol", out var sv) ? sv.ToString() : "—";
                float price = it.TryGetValue("price", out var pv) ? pv.Value<float>() : 0f;
                float chg = it.TryGetValue("change_pct", out var cv) ? cv.Value<float>() : 0f;
                float y = top - i * 0.05f;
                var chgCol = chg >= 0 ? new Color(0.3f, 0.9f, 0.5f) : new Color(1f, 0.4f, 0.4f);

                CreateText($"sym_{i}", sym, 0.028f, Color.white, new Vector3(-0.2f, y, -0.011f), _rows,
                    TextAlignmentOptions.Left, new Vector2(0.16f, 0.04f));
                CreateText($"pr_{i}", price.ToString("0.00"), 0.026f, new Color(0.85f, 0.88f, 0.95f), new Vector3(0.02f, y, -0.011f), _rows,
                    TextAlignmentOptions.Right, new Vector2(0.16f, 0.04f));
                CreateText($"ch_{i}", (chg >= 0 ? "+" : "") + chg.ToString("0.0") + "%", 0.026f, chgCol, new Vector3(0.21f, y, -0.011f), _rows,
                    TextAlignmentOptions.Right, new Vector2(0.12f, 0.04f));
            }
        }
    }
}
