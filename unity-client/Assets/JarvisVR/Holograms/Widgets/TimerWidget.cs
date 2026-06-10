using UnityEngine;
using TMPro;
using Newtonsoft.Json.Linq;

namespace JarvisVR.Holograms.Widgets
{
    /// <summary>
    /// widget_type "timer". Counts down locally for smooth display; the server stays authoritative
    /// (it resyncs via holo.update and reacts to taps on the pause/reset buttons).
    /// Props: { remaining_ms | remaining_s | duration_ms, running, label }.
    /// Sub-elements (collider names): "pause_button", "reset_button".
    /// </summary>
    public class TimerWidget : HoloWidget
    {
        private TextMeshPro _display;
        private TextMeshPro _label;
        private TextMeshPro _pauseLabel;
        private Transform _pauseBtn;
        private float _remaining;
        private bool _running;

        protected override void Build()
        {
            CreatePrimitive(PrimitiveType.Cube, "bg", Vector3.zero, new Vector3(0.4f, 0.26f, 0.01f),
                new Color(0.08f, 0.10f, 0.16f, 0.95f));

            _label = CreateText("label", "", 0.035f, new Color(0.7f, 0.85f, 1f),
                new Vector3(0f, 0.09f, -0.011f), align: TextAlignmentOptions.Center, size: new Vector2(0.38f, 0.05f));

            _display = CreateText("display", "0:00", 0.09f, Color.white,
                new Vector3(0f, 0.0f, -0.011f), align: TextAlignmentOptions.Center, size: new Vector2(0.38f, 0.12f));

            _pauseBtn = CreatePrimitive(PrimitiveType.Cube, "pause_button", new Vector3(-0.09f, -0.09f, -0.01f),
                new Vector3(0.16f, 0.06f, 0.02f), new Color(0.2f, 0.5f, 0.85f), keepCollider: true);
            _pauseLabel = CreateText("pause_label", "Pause", 0.03f, Color.white,
                new Vector3(-0.09f, -0.09f, -0.025f), align: TextAlignmentOptions.Center, size: new Vector2(0.15f, 0.05f));

            CreatePrimitive(PrimitiveType.Cube, "reset_button", new Vector3(0.09f, -0.09f, -0.01f),
                new Vector3(0.16f, 0.06f, 0.02f), new Color(0.5f, 0.3f, 0.3f), keepCollider: true);
            CreateText("reset_label", "Reset", 0.03f, Color.white,
                new Vector3(0.09f, -0.09f, -0.025f), align: TextAlignmentOptions.Center, size: new Vector2(0.15f, 0.05f));
        }

        protected override void ApplyProps(JObject props)
        {
            if (Has("remaining_ms")) _remaining = GetFloat("remaining_ms") / 1000f;
            else if (Has("remaining_s")) _remaining = GetFloat("remaining_s");
            else if (Has("duration_ms")) _remaining = GetFloat("duration_ms") / 1000f;

            _running = GetBool("running", _running);
            _label.text = GetString("label", "Timer");
            _pauseLabel.text = _running ? "Pause" : "Resume";
            SetColor(_pauseBtn, _running ? new Color(0.2f, 0.5f, 0.85f) : new Color(0.25f, 0.65f, 0.4f));
            Render();
        }

        private void Update()
        {
            if (!_running || _remaining <= 0f) return;
            _remaining = Mathf.Max(0f, _remaining - Time.deltaTime);
            Render();
            if (_remaining <= 0f) _pauseLabel.text = "Done";
        }

        private void Render()
        {
            int total = Mathf.CeilToInt(_remaining);
            _display.text = $"{total / 60}:{total % 60:00}";
        }
    }
}
