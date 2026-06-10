using UnityEngine;
using TMPro;
using Newtonsoft.Json.Linq;

namespace JarvisVR.Holograms.Widgets
{
    /// <summary>
    /// widget_type "notification_toast". A transient notice (the server usually sets ttl_ms to
    /// auto-dismiss). Props: { title, body, level:"info"|"warn"|"error" }.
    /// </summary>
    public class NotificationToastWidget : HoloWidget
    {
        private Transform _accent;
        private TextMeshPro _title;
        private TextMeshPro _body;

        protected override void Build()
        {
            CreatePrimitive(PrimitiveType.Cube, "bg", Vector3.zero, new Vector3(0.5f, 0.14f, 0.01f),
                new Color(0.1f, 0.11f, 0.15f, 0.97f));
            _accent = CreatePrimitive(PrimitiveType.Cube, "accent", new Vector3(-0.23f, 0f, -0.006f),
                new Vector3(0.02f, 0.14f, 0.004f), new Color(0.3f, 0.7f, 1f));
            _title = CreateText("title", "", 0.032f, Color.white, new Vector3(0.01f, 0.035f, -0.011f),
                align: TextAlignmentOptions.Left, size: new Vector2(0.42f, 0.04f));
            _body = CreateText("body", "", 0.026f, new Color(0.8f, 0.83f, 0.9f), new Vector3(0.01f, -0.03f, -0.011f),
                align: TextAlignmentOptions.Left, size: new Vector2(0.42f, 0.06f));
        }

        protected override void ApplyProps(JObject props)
        {
            _title.text = GetString("title", "Notification");
            _body.text = GetString("body", GetString("text", ""));
            SetColor(_accent, LevelColor(GetString("level", "info")));
        }

        private static Color LevelColor(string level)
        {
            switch (level)
            {
                case "warn": case "warning": return new Color(1f, 0.7f, 0.2f);
                case "error": return new Color(1f, 0.35f, 0.3f);
                case "success": return new Color(0.3f, 0.9f, 0.5f);
                default: return new Color(0.3f, 0.7f, 1f);
            }
        }
    }
}
