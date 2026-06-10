using UnityEngine;
using TMPro;
using Newtonsoft.Json.Linq;

namespace JarvisVR.Holograms.Widgets
{
    /// <summary>
    /// widget_type "text_label". Props: { text, size, color }.
    /// </summary>
    public class TextLabelWidget : HoloWidget
    {
        private TextMeshPro _label;

        protected override void Build()
        {
            _label = CreateText("label", "", 0.1f, Color.white, Vector3.zero,
                align: TextAlignmentOptions.Center, size: new Vector2(0.6f, 0.3f));
        }

        protected override void ApplyProps(JObject props)
        {
            _label.text = GetString("text", "");
            float size = GetFloat("size", 0.1f);
            _label.fontSize = Mathf.Max(0.02f, size);
            _label.color = GetColor("color", Color.white);
        }
    }
}
