using UnityEngine;
using TMPro;
using Newtonsoft.Json.Linq;

namespace JarvisVR.Holograms.Widgets
{
    /// <summary>
    /// widget_type "panel" (also the fallback for unknown widgets). A flat backing surface with a
    /// title and body text. Props: { title, body|text, width, height, color }.
    /// </summary>
    public class PanelWidget : HoloWidget
    {
        private Transform _bg;
        private TextMeshPro _title;
        private TextMeshPro _body;
        private float _w = 0.5f, _h = 0.32f;

        protected override void Build()
        {
            _bg = CreatePrimitive(PrimitiveType.Cube, "bg", Vector3.zero,
                new Vector3(_w, _h, 0.01f), new Color(0.10f, 0.12f, 0.18f, 0.95f));

            _title = CreateText("title", "", 0.05f, new Color(0.6f, 0.85f, 1f),
                new Vector3(0f, _h * 0.5f - 0.05f, -0.011f), align: TextAlignmentOptions.Top,
                size: new Vector2(_w * 0.95f, 0.08f));

            _body = CreateText("body", "", 0.035f, Color.white,
                new Vector3(0f, -0.02f, -0.011f), align: TextAlignmentOptions.Top,
                size: new Vector2(_w * 0.95f, _h * 0.7f));
        }

        protected override void ApplyProps(JObject props)
        {
            _w = Mathf.Max(0.1f, GetFloat("width", _w));
            _h = Mathf.Max(0.1f, GetFloat("height", _h));
            _bg.localScale = new Vector3(_w, _h, 0.01f);
            SetColor(_bg, GetColor("color", new Color(0.10f, 0.12f, 0.18f, 0.95f)));

            _title.text = GetString("title", "");
            _title.rectTransform.sizeDelta = new Vector2(_w * 0.95f, 0.08f);
            _title.transform.localPosition = new Vector3(0f, _h * 0.5f - 0.05f, -0.011f);

            // accept either "body" or "text"
            _body.text = Has("body") ? GetString("body") : GetString("text", "");
            _body.rectTransform.sizeDelta = new Vector2(_w * 0.95f, _h * 0.7f);
        }
    }
}
