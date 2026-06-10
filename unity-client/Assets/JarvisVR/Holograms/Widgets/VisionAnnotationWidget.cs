using UnityEngine;
using TMPro;
using Newtonsoft.Json.Linq;

namespace JarvisVR.Holograms.Widgets
{
    /// <summary>
    /// widget_type "vision_annotation" (§8.5). A world-anchored callout pinning a label to a real
    /// object Jarvis recognized. Props: { label, confidence, color }.
    /// </summary>
    public class VisionAnnotationWidget : HoloWidget
    {
        private Transform _marker;
        private Transform _bg;
        private TextMeshPro _label;

        protected override void Build()
        {
            _marker = CreatePrimitive(PrimitiveType.Sphere, "marker", Vector3.zero,
                Vector3.one * 0.03f, new Color(0.3f, 0.9f, 1f), keepCollider: true);
            // leader line going up to the label
            CreatePrimitive(PrimitiveType.Cube, "leader", new Vector3(0f, 0.06f, 0f),
                new Vector3(0.004f, 0.12f, 0.004f), new Color(0.3f, 0.9f, 1f, 0.7f));
            _bg = CreatePrimitive(PrimitiveType.Cube, "bg", new Vector3(0f, 0.14f, 0f),
                new Vector3(0.26f, 0.06f, 0.005f), new Color(0.05f, 0.1f, 0.16f, 0.95f));
            _label = CreateText("label", "", 0.03f, Color.white, new Vector3(0f, 0.14f, -0.006f),
                align: TextAlignmentOptions.Center, size: new Vector2(0.25f, 0.05f));
        }

        protected override void ApplyProps(JObject props)
        {
            string label = GetString("label", "object");
            float conf = GetFloat("confidence", -1f);
            _label.text = conf >= 0f ? $"{label}  {Mathf.RoundToInt(conf * 100)}%" : label;
            var c = GetColor("color", new Color(0.3f, 0.9f, 1f));
            SetColor(_marker, c);
        }
    }
}
