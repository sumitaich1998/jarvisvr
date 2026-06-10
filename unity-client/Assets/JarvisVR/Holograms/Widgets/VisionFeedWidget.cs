using System;
using UnityEngine;
using TMPro;
using Newtonsoft.Json.Linq;
using JarvisVR.Perception;

namespace JarvisVR.Holograms.Widgets
{
    /// <summary>
    /// widget_type "vision_feed" (§8.5). A panel showing what Jarvis currently sees. With
    /// { live:true } it mirrors the local passthrough capture texture (only while capturing);
    /// otherwise it shows a static { image } (base64 JPEG/PNG) or a placeholder. Props:
    /// { title, live, image }.
    /// </summary>
    public class VisionFeedWidget : HoloWidget
    {
        private TextMeshPro _title;
        private Renderer _screen;
        private bool _live;
        private PassthroughCameraProvider _provider;

        protected override void Build()
        {
            CreatePrimitive(PrimitiveType.Cube, "frame", Vector3.zero, new Vector3(0.42f, 0.30f, 0.008f),
                new Color(0.04f, 0.05f, 0.07f, 0.95f));
            var screen = CreatePrimitive(PrimitiveType.Quad, "screen", new Vector3(0f, -0.01f, -0.006f),
                new Vector3(0.38f, 0.24f, 1f), new Color(0.1f, 0.12f, 0.16f), keepCollider: true);
            _screen = screen.GetComponent<Renderer>();
            _title = CreateText("title", "Vision feed", 0.03f, new Color(0.7f, 0.85f, 1f),
                new Vector3(0f, 0.16f, -0.006f), align: TextAlignmentOptions.Center, size: new Vector2(0.4f, 0.04f));
        }

        protected override void ApplyProps(JObject props)
        {
            _title.text = GetString("title", "Vision feed");
            _live = GetBool("live", false);

            if (!_live && Has("image"))
            {
                var tex = DecodeBase64(GetString("image"));
                if (tex != null && _screen != null) _screen.material.mainTexture = tex;
            }
        }

        private void Update()
        {
            if (!_live || _screen == null) return;
            if (_provider == null) _provider = FindObjectOfType<PassthroughCameraProvider>();
            var t = _provider != null ? _provider.PreviewTexture : null;
            if (t != null) _screen.material.mainTexture = t;
        }

        private static Texture2D DecodeBase64(string b64)
        {
            if (string.IsNullOrEmpty(b64)) return null;
            try
            {
                var bytes = Convert.FromBase64String(b64);
                var tex = new Texture2D(2, 2, TextureFormat.RGB24, false);
                return tex.LoadImage(bytes) ? tex : null;
            }
            catch { return null; }
        }
    }
}
