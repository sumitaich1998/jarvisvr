using UnityEngine;
using TMPro;
using Newtonsoft.Json.Linq;

namespace JarvisVR.Holograms.Widgets
{
    /// <summary>
    /// widget_type "media_player". A transport panel with play/pause + skip buttons and a progress
    /// bar. Props: { title, artist, state:"playing"|"paused", position (0..1) | position_s + duration_s }.
    /// Sub-elements (collider names): "play_button", "skip_back", "skip_fwd".
    /// </summary>
    public class MediaPlayerWidget : HoloWidget
    {
        private const float BarWidth = 0.42f;

        private TextMeshPro _title;
        private TextMeshPro _artist;
        private TextMeshPro _playLabel;
        private Transform _play;
        private Transform _fill;

        protected override void Build()
        {
            CreatePrimitive(PrimitiveType.Cube, "bg", Vector3.zero, new Vector3(0.5f, 0.3f, 0.01f),
                new Color(0.08f, 0.09f, 0.13f, 0.96f));

            _title = CreateText("title", "", 0.04f, Color.white, new Vector3(0f, 0.1f, -0.011f),
                align: TextAlignmentOptions.Center, size: new Vector2(0.46f, 0.05f));
            _artist = CreateText("artist", "", 0.028f, new Color(0.7f, 0.75f, 0.85f), new Vector3(0f, 0.055f, -0.011f),
                align: TextAlignmentOptions.Center, size: new Vector2(0.46f, 0.04f));

            // progress bar
            CreatePrimitive(PrimitiveType.Cube, "bar_bg", new Vector3(0f, -0.02f, -0.011f),
                new Vector3(BarWidth, 0.012f, 0.005f), new Color(0.25f, 0.27f, 0.32f));
            _fill = CreatePrimitive(PrimitiveType.Cube, "bar_fill", new Vector3(-BarWidth * 0.5f, -0.02f, -0.013f),
                new Vector3(0.001f, 0.012f, 0.006f), new Color(0.3f, 0.8f, 1f));

            // transport buttons
            CreatePrimitive(PrimitiveType.Cube, "skip_back", new Vector3(-0.12f, -0.1f, -0.01f),
                new Vector3(0.07f, 0.06f, 0.02f), new Color(0.3f, 0.32f, 0.4f), keepCollider: true);
            CreateText("skip_back_lbl", "<<", 0.03f, Color.white, new Vector3(-0.12f, -0.1f, -0.025f),
                align: TextAlignmentOptions.Center, size: new Vector2(0.07f, 0.05f));

            _play = CreatePrimitive(PrimitiveType.Cube, "play_button", new Vector3(0f, -0.1f, -0.01f),
                new Vector3(0.08f, 0.07f, 0.02f), new Color(0.2f, 0.6f, 0.9f), keepCollider: true);
            _playLabel = CreateText("play_lbl", "Play", 0.03f, Color.white, new Vector3(0f, -0.1f, -0.025f),
                align: TextAlignmentOptions.Center, size: new Vector2(0.08f, 0.05f));

            CreatePrimitive(PrimitiveType.Cube, "skip_fwd", new Vector3(0.12f, -0.1f, -0.01f),
                new Vector3(0.07f, 0.06f, 0.02f), new Color(0.3f, 0.32f, 0.4f), keepCollider: true);
            CreateText("skip_fwd_lbl", ">>", 0.03f, Color.white, new Vector3(0.12f, -0.1f, -0.025f),
                align: TextAlignmentOptions.Center, size: new Vector2(0.07f, 0.05f));
        }

        protected override void ApplyProps(JObject props)
        {
            _title.text = GetString("title", "Now Playing");
            _artist.text = GetString("artist", "");

            bool playing = GetString("state", "paused") == "playing";
            _playLabel.text = playing ? "Pause" : "Play";
            SetColor(_play, playing ? new Color(0.2f, 0.7f, 0.5f) : new Color(0.2f, 0.6f, 0.9f));

            float frac = ComputeProgress();
            float w = Mathf.Clamp01(frac) * BarWidth;
            _fill.localScale = new Vector3(Mathf.Max(0.001f, w), 0.012f, 0.006f);
            _fill.localPosition = new Vector3(-BarWidth * 0.5f + w * 0.5f, -0.02f, -0.013f);
        }

        private float ComputeProgress()
        {
            if (Has("position") && !Has("duration_s")) return GetFloat("position", 0f); // already 0..1
            float dur = GetFloat("duration_s", 0f);
            float pos = GetFloat("position_s", 0f);
            return dur > 0f ? pos / dur : 0f;
        }
    }
}
