using UnityEngine;
using Newtonsoft.Json.Linq;
using JarvisVR.Perception;

namespace JarvisVR.Holograms.Widgets
{
    /// <summary>
    /// widget_type "music_visualizer". Reactive bars driven by the ambient audio level (if the
    /// AmbientAudioStreamer is active) or by props.bands / a built-in animation. Props:
    /// { bars, color, bands:[0..1,...] }.
    /// </summary>
    public class MusicVisualizerWidget : HoloWidget
    {
        private Transform[] _bars;
        private float[] _heights;
        private Color _color = new Color(0.4f, 0.8f, 1f);
        private AmbientAudioStreamer _audio;

        protected override void Build()
        {
            CreatePrimitive(PrimitiveType.Cube, "base", new Vector3(0, -0.16f, 0), new Vector3(0.5f, 0.01f, 0.08f),
                new Color(0.1f, 0.12f, 0.16f));
        }

        protected override void ApplyProps(JObject props)
        {
            _color = GetColor("color", new Color(0.4f, 0.8f, 1f));
            int count = Mathf.Clamp(GetInt("bars", 16), 4, 48);
            if (_bars == null || _bars.Length != count) Rebuild(count);

            var bands = GetArray("bands");
            if (bands != null)
                for (int i = 0; i < _heights.Length && i < bands.Count; i++)
                    _heights[i] = Mathf.Clamp01(bands[i].Value<float>());
        }

        private void Rebuild(int count)
        {
            if (_bars != null) foreach (var b in _bars) if (b != null) Destroy(b.gameObject);
            _bars = new Transform[count];
            _heights = new float[count];
            float width = 0.46f, step = width / count;
            for (int i = 0; i < count; i++)
            {
                float x = -width * 0.5f + step * (i + 0.5f);
                _bars[i] = CreatePrimitive(PrimitiveType.Cube, $"bar_{i}", new Vector3(x, -0.15f, 0f),
                    new Vector3(step * 0.7f, 0.01f, 0.05f), _color);
            }
        }

        private void Update()
        {
            if (_bars == null) return;
            if (_audio == null) _audio = FindObjectOfType<AmbientAudioStreamer>();
            float level = (_audio != null && _audio.Active) ? _audio.Level : -1f;

            for (int i = 0; i < _bars.Length; i++)
            {
                float target;
                if (level >= 0f)
                    target = Mathf.Clamp01(level * (0.6f + 0.8f * Mathf.PerlinNoise(i * 0.7f, Time.time * 3f)));
                else if (_heights[i] > 0f)
                    target = _heights[i];
                else
                    target = 0.2f + 0.3f * (Mathf.Sin(Time.time * 4f + i * 0.5f) * 0.5f + 0.5f);

                float h = Mathf.Lerp(_bars[i].localScale.y, Mathf.Max(0.01f, target * 0.3f), Time.deltaTime * 12f);
                var sc = _bars[i].localScale;
                _bars[i].localScale = new Vector3(sc.x, h, sc.z);
                _bars[i].localPosition = new Vector3(_bars[i].localPosition.x, -0.15f + h * 0.5f, 0f);
                SetColor(_bars[i], Color.Lerp(_color, Color.white, h));
            }
        }
    }
}
