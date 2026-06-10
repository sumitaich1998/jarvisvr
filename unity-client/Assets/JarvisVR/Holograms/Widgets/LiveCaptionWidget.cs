using System.Collections.Generic;
using UnityEngine;
using TMPro;
using Newtonsoft.Json.Linq;

namespace JarvisVR.Holograms.Widgets
{
    /// <summary>
    /// widget_type "live_caption" (§8.5). Rolling captions of speech Jarvis hears. Props:
    /// { lines:[..] (full set) | text|caption (append one line), max_lines, title }.
    /// </summary>
    public class LiveCaptionWidget : HoloWidget
    {
        private TextMeshPro _title;
        private TextMeshPro _body;
        private readonly List<string> _lines = new List<string>();
        private int _maxLines = 4;

        protected override void Build()
        {
            CreatePrimitive(PrimitiveType.Cube, "bg", Vector3.zero, new Vector3(0.7f, 0.22f, 0.008f),
                new Color(0.03f, 0.04f, 0.06f, 0.85f));
            _title = CreateText("title", "Live captions", 0.028f, new Color(0.6f, 0.8f, 1f),
                new Vector3(0f, 0.09f, -0.006f), align: TextAlignmentOptions.Center, size: new Vector2(0.66f, 0.04f));
            _body = CreateText("body", "", 0.03f, Color.white, new Vector3(0f, -0.01f, -0.006f),
                align: TextAlignmentOptions.Bottom, size: new Vector2(0.66f, 0.16f));
        }

        protected override void ApplyProps(JObject props)
        {
            _maxLines = Mathf.Clamp(GetInt("max_lines", 4), 1, 10);
            if (Has("title")) _title.text = GetString("title");

            var arr = GetArray("lines");
            if (arr != null)
            {
                _lines.Clear();
                foreach (var t in arr) _lines.Add(t.ToString());
            }
            else
            {
                string line = Has("caption") ? GetString("caption") : (Has("text") ? GetString("text") : null);
                if (!string.IsNullOrEmpty(line)) _lines.Add(line);
            }

            while (_lines.Count > _maxLines) _lines.RemoveAt(0);
            _body.text = string.Join("\n", _lines);
        }
    }
}
