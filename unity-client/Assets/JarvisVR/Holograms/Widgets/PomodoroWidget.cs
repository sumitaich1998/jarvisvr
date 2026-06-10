using UnityEngine;
using TMPro;
using Newtonsoft.Json.Linq;

namespace JarvisVR.Holograms.Widgets
{
    /// <summary>
    /// widget_type "pomodoro". A focus timer with work/break phases (server stays authoritative;
    /// counts down locally for smooth display). Props:
    /// { phase:"work"|"break", remaining_s, running, cycle, total_cycles }.
    /// Sub-elements: "pause_button", "skip_button".
    /// </summary>
    public class PomodoroWidget : HoloWidget
    {
        private Transform _bg;
        private TextMeshPro _phase;
        private TextMeshPro _display;
        private TextMeshPro _cycles;
        private float _remaining;
        private bool _running;
        private bool _work = true;

        protected override void Build()
        {
            _bg = CreatePrimitive(PrimitiveType.Cube, "bg", Vector3.zero, new Vector3(0.36f, 0.3f, 0.01f),
                new Color(0.12f, 0.08f, 0.1f, 0.96f));
            _phase = CreateText("phase", "", 0.034f, Color.white, new Vector3(0f, 0.1f, -0.011f),
                align: TextAlignmentOptions.Center, size: new Vector2(0.34f, 0.05f));
            _display = CreateText("display", "0:00", 0.085f, Color.white, new Vector3(0f, 0.0f, -0.011f),
                align: TextAlignmentOptions.Center, size: new Vector2(0.34f, 0.12f));
            _cycles = CreateText("cycles", "", 0.026f, new Color(0.8f, 0.7f, 0.7f), new Vector3(0f, -0.08f, -0.011f),
                align: TextAlignmentOptions.Center, size: new Vector2(0.34f, 0.04f));

            CreatePrimitive(PrimitiveType.Cube, "pause_button", new Vector3(-0.08f, -0.12f, -0.01f),
                new Vector3(0.13f, 0.05f, 0.02f), new Color(0.5f, 0.3f, 0.4f), keepCollider: true);
            CreateText("pause_lbl", "Pause", 0.026f, Color.white, new Vector3(-0.08f, -0.12f, -0.025f),
                align: TextAlignmentOptions.Center, size: new Vector2(0.12f, 0.04f));
            CreatePrimitive(PrimitiveType.Cube, "skip_button", new Vector3(0.08f, -0.12f, -0.01f),
                new Vector3(0.13f, 0.05f, 0.02f), new Color(0.35f, 0.35f, 0.45f), keepCollider: true);
            CreateText("skip_lbl", "Skip", 0.026f, Color.white, new Vector3(0.08f, -0.12f, -0.025f),
                align: TextAlignmentOptions.Center, size: new Vector2(0.12f, 0.04f));
        }

        protected override void ApplyProps(JObject props)
        {
            _work = GetString("phase", "work") != "break";
            if (Has("remaining_s")) _remaining = GetFloat("remaining_s");
            _running = GetBool("running", _running);
            _phase.text = _work ? "FOCUS" : "BREAK";
            SetColor(_bg, _work ? new Color(0.12f, 0.08f, 0.1f, 0.96f) : new Color(0.08f, 0.12f, 0.1f, 0.96f));
            _phase.color = _work ? new Color(1f, 0.6f, 0.5f) : new Color(0.5f, 1f, 0.7f);

            int cycle = GetInt("cycle", 0), total = GetInt("total_cycles", 0);
            _cycles.text = total > 0 ? $"cycle {cycle}/{total}" : "";
            Render();
        }

        private void Update()
        {
            if (!_running || _remaining <= 0f) return;
            _remaining = Mathf.Max(0f, _remaining - Time.deltaTime);
            Render();
        }

        private void Render()
        {
            int t = Mathf.CeilToInt(_remaining);
            _display.text = $"{t / 60}:{t % 60:00}";
        }
    }
}
