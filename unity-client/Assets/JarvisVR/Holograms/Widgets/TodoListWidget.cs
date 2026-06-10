using UnityEngine;
using TMPro;
using Newtonsoft.Json.Linq;

namespace JarvisVR.Holograms.Widgets
{
    /// <summary>
    /// widget_type "todo_list". A checklist; tapping a checkbox (collider "item_&lt;index&gt;")
    /// reports a tap so the agent can toggle the item. Props: { title, items:[{text,done}] }.
    /// </summary>
    public class TodoListWidget : HoloWidget
    {
        private const float Width = 0.5f;
        private const float RowH = 0.06f;

        private Transform _bg;
        private TextMeshPro _title;
        private Transform _rows;

        protected override void Build()
        {
            _bg = CreatePrimitive(PrimitiveType.Cube, "bg", Vector3.zero, new Vector3(Width, 0.4f, 0.01f),
                new Color(0.10f, 0.10f, 0.14f, 0.96f));
            _title = CreateText("title", "", 0.04f, new Color(0.85f, 0.85f, 0.6f), Vector3.zero,
                align: TextAlignmentOptions.Center, size: new Vector2(Width * 0.95f, 0.06f));
            _rows = new GameObject("rows").transform;
            _rows.SetParent(transform, false);
        }

        protected override void ApplyProps(JObject props)
        {
            _title.text = GetString("title", "To-Do");

            foreach (Transform c in _rows) Destroy(c.gameObject);

            var items = GetArray("items");
            int n = items?.Count ?? 0;
            float panelH = Mathf.Max(0.2f, 0.1f + n * RowH);
            _bg.localScale = new Vector3(Width, panelH, 0.01f);
            _title.transform.localPosition = new Vector3(0f, panelH * 0.5f - 0.05f, -0.011f);

            if (items == null) return;
            float top = panelH * 0.5f - 0.12f;
            for (int i = 0; i < n; i++)
            {
                string text;
                bool done;
                if (items[i] is JObject o)
                {
                    text = o.TryGetValue("text", out var tv) ? tv.ToString() : "";
                    done = o.TryGetValue("done", out var dv) && dv.Type == JTokenType.Boolean && dv.Value<bool>();
                }
                else { text = items[i].ToString(); done = false; }

                float y = top - i * RowH;
                CreatePrimitive(PrimitiveType.Cube, $"item_{i}", new Vector3(-Width * 0.5f + 0.05f, y, -0.012f),
                    Vector3.one * 0.03f, done ? new Color(0.3f, 0.85f, 0.45f) : new Color(0.35f, 0.37f, 0.43f), _rows, keepCollider: true);

                string shown = done ? $"<s>{text}</s>" : text;
                var label = CreateText($"text_{i}", shown, 0.028f, done ? new Color(0.6f, 0.62f, 0.66f) : Color.white,
                    new Vector3(-0.01f, y, -0.012f), _rows, TextAlignmentOptions.Left, new Vector2(Width * 0.82f, RowH));
                label.richText = true;
            }
        }
    }
}
