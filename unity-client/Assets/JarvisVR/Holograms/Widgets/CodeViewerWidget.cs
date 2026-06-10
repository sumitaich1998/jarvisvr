using UnityEngine;
using TMPro;
using Newtonsoft.Json.Linq;

namespace JarvisVR.Holograms.Widgets
{
    /// <summary>
    /// widget_type "code_viewer". A monospaced code panel. Props: { title, code, language }.
    /// </summary>
    public class CodeViewerWidget : HoloWidget
    {
        private TextMeshPro _title;
        private TextMeshPro _code;

        protected override void Build()
        {
            CreatePrimitive(PrimitiveType.Cube, "bg", Vector3.zero, new Vector3(0.7f, 0.5f, 0.008f),
                new Color(0.04f, 0.05f, 0.07f, 0.97f));
            CreatePrimitive(PrimitiveType.Cube, "titlebar", new Vector3(0f, 0.225f, -0.006f), new Vector3(0.7f, 0.05f, 0.006f),
                new Color(0.1f, 0.12f, 0.16f));
            _title = CreateText("title", "", 0.03f, new Color(0.7f, 0.85f, 1f), new Vector3(0f, 0.225f, -0.011f),
                align: TextAlignmentOptions.Center, size: new Vector2(0.66f, 0.04f));
            _code = CreateText("code", "", 0.022f, new Color(0.85f, 0.92f, 0.85f), new Vector3(-0.005f, -0.02f, -0.011f),
                align: TextAlignmentOptions.TopLeft, size: new Vector2(0.66f, 0.4f));
            _code.enableWordWrapping = false;
            _code.overflowMode = TextOverflowModes.Truncate;
        }

        protected override void ApplyProps(JObject props)
        {
            string lang = GetString("language", "");
            string title = GetString("title", "");
            _title.text = string.IsNullOrEmpty(lang) ? title : $"{title}  ·  {lang}";
            _code.text = GetString("code", "");
        }
    }
}
