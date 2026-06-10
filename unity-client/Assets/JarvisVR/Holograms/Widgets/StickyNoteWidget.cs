using UnityEngine;
using TMPro;
using Newtonsoft.Json.Linq;

namespace JarvisVR.Holograms.Widgets
{
    /// <summary>
    /// widget_type "sticky_note". A colored note you can place and grab. Props: { text, title, color }.
    /// </summary>
    public class StickyNoteWidget : HoloWidget
    {
        private Transform _paper;
        private TextMeshPro _title;
        private TextMeshPro _body;

        protected override void Build()
        {
            _paper = CreatePrimitive(PrimitiveType.Cube, "paper", Vector3.zero, new Vector3(0.24f, 0.24f, 0.006f),
                new Color(1f, 0.9f, 0.45f), keepCollider: true);
            _title = CreateText("title", "", 0.03f, new Color(0.2f, 0.18f, 0.05f), new Vector3(0f, 0.085f, -0.005f),
                align: TextAlignmentOptions.Center, size: new Vector2(0.22f, 0.04f));
            _body = CreateText("body", "", 0.026f, new Color(0.15f, 0.13f, 0.05f), new Vector3(0f, -0.01f, -0.005f),
                align: TextAlignmentOptions.Top, size: new Vector2(0.21f, 0.16f));
        }

        protected override void ApplyProps(JObject props)
        {
            _title.text = GetString("title", "");
            _body.text = GetString("text", "");
            SetColor(_paper, GetColor("color", new Color(1f, 0.9f, 0.45f)));
        }
    }
}
