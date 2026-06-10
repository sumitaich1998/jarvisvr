using UnityEngine;
using TMPro;
using Newtonsoft.Json.Linq;

namespace JarvisVR.Holograms.Widgets
{
    /// <summary>
    /// widget_type "scene_label" (§8.5). A floating tag pinned to a place/region in the room
    /// (e.g. "Kitchen", "North"). Props: { text, sublabel, color }.
    /// </summary>
    public class SceneLabelWidget : HoloWidget
    {
        private Transform _pill;
        private TextMeshPro _text;
        private TextMeshPro _sub;

        protected override void Build()
        {
            _pill = CreatePrimitive(PrimitiveType.Cube, "pill", Vector3.zero, new Vector3(0.3f, 0.08f, 0.01f),
                new Color(0.1f, 0.13f, 0.2f, 0.9f), keepCollider: true);
            _text = CreateText("text", "", 0.04f, Color.white, new Vector3(0f, 0.005f, -0.011f),
                align: TextAlignmentOptions.Center, size: new Vector2(0.28f, 0.05f));
            _sub = CreateText("sub", "", 0.022f, new Color(0.7f, 0.78f, 0.9f), new Vector3(0f, -0.03f, -0.011f),
                align: TextAlignmentOptions.Center, size: new Vector2(0.28f, 0.03f));
        }

        protected override void ApplyProps(JObject props)
        {
            _text.text = GetString("text", "Label");
            _sub.text = GetString("sublabel", "");
            SetColor(_pill, GetColor("color", new Color(0.1f, 0.13f, 0.2f, 0.9f)));
        }
    }
}
