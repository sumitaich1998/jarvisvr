using UnityEngine;
using TMPro;
using Newtonsoft.Json.Linq;

namespace JarvisVR.Holograms.Widgets
{
    /// <summary>
    /// widget_type "button". A pressable surface; taps are reported as client.interaction
    /// (action "tap", element = "button"). Props: { label, color }.
    /// The child mesh keeps its collider so the tap raycast hits "button".
    /// </summary>
    public class ButtonWidget : HoloWidget
    {
        private Transform _face;
        private TextMeshPro _label;

        protected override void Build()
        {
            _face = CreatePrimitive(PrimitiveType.Cube, "button", Vector3.zero,
                new Vector3(0.22f, 0.09f, 0.02f), new Color(0.18f, 0.45f, 0.85f), keepCollider: true);

            _label = CreateText("label", "", 0.035f, Color.white, new Vector3(0f, 0f, -0.02f),
                align: TextAlignmentOptions.Center, size: new Vector2(0.21f, 0.08f));
        }

        protected override void ApplyProps(JObject props)
        {
            _label.text = GetString("label", "Button");
            SetColor(_face, GetColor("color", new Color(0.18f, 0.45f, 0.85f)));
        }
    }
}
