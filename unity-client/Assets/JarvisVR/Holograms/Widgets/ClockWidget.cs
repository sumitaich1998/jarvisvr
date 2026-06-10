using System;
using UnityEngine;
using TMPro;
using Newtonsoft.Json.Linq;

namespace JarvisVR.Holograms.Widgets
{
    /// <summary>
    /// widget_type "clock". A live digital clock. Props:
    /// { label, utc_offset_hours, format_24h, show_seconds, show_date }.
    /// </summary>
    public class ClockWidget : HoloWidget
    {
        private TextMeshPro _time;
        private TextMeshPro _label;
        private float _offset;
        private bool _h24 = true, _seconds = true, _date = true;

        protected override void Build()
        {
            CreatePrimitive(PrimitiveType.Cube, "bg", Vector3.zero, new Vector3(0.36f, 0.18f, 0.01f),
                new Color(0.06f, 0.07f, 0.12f, 0.95f));
            _time = CreateText("time", "", 0.08f, Color.white, new Vector3(0f, 0.01f, -0.011f),
                align: TextAlignmentOptions.Center, size: new Vector2(0.34f, 0.1f));
            _label = CreateText("label", "", 0.028f, new Color(0.7f, 0.8f, 1f), new Vector3(0f, 0.07f, -0.011f),
                align: TextAlignmentOptions.Center, size: new Vector2(0.34f, 0.04f));
        }

        protected override void ApplyProps(JObject props)
        {
            _offset = GetFloat("utc_offset_hours", 0f);
            _h24 = GetBool("format_24h", true);
            _seconds = GetBool("show_seconds", true);
            _date = GetBool("show_date", true);
            _label.text = GetString("label", "");
            Render();
        }

        private void Update() => Render();

        private void Render()
        {
            if (_time == null) return;
            var now = DateTime.UtcNow.AddHours(_offset);
            string fmt = (_h24 ? "HH:mm" : "h:mm") + (_seconds ? ":ss" : "") + (_h24 ? "" : " tt");
            string text = now.ToString(fmt);
            if (_date) text += "\n<size=40%>" + now.ToString("ddd, MMM d") + "</size>";
            _time.richText = true;
            _time.text = text;
        }
    }
}
