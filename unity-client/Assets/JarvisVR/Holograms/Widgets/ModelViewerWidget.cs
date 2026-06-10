using UnityEngine;
using TMPro;
using Newtonsoft.Json.Linq;

namespace JarvisVR.Holograms.Widgets
{
    /// <summary>
    /// widget_type "model_viewer". Procedural placeholder for a 3D model (a real build would stream
    /// glTF from props.url via a loader package). Props: { model, url, color, spin, spin_speed }.
    /// Reports drag/grab so the user can reposition it.
    /// </summary>
    public class ModelViewerWidget : HoloWidget
    {
        private Transform _model;
        private Transform _accent;
        private TextMeshPro _caption;
        private bool _spin = true;
        private float _spinSpeed = 30f;

        protected override void Build()
        {
            _model = CreatePrimitive(PrimitiveType.Cube, "model", Vector3.zero,
                Vector3.one * 0.16f, new Color(0.6f, 0.7f, 0.9f), keepCollider: true);
            _accent = CreatePrimitive(PrimitiveType.Sphere, "accent", new Vector3(0.06f, 0.1f, -0.06f),
                Vector3.one * 0.08f, new Color(0.9f, 0.6f, 0.3f), _model);
            _caption = CreateText("caption", "", 0.03f, Color.white, new Vector3(0f, -0.16f, 0f),
                align: TextAlignmentOptions.Center, size: new Vector2(0.4f, 0.05f));
        }

        protected override void ApplyProps(JObject props)
        {
            string name = Has("model") ? GetString("model") : GetString("url", "model");
            _caption.text = name;
            _spin = GetBool("spin", true);
            _spinSpeed = GetFloat("spin_speed", 30f);
            var c = GetColor("color", new Color(0.6f, 0.7f, 0.9f));
            SetColor(_model, c);
        }

        private void Update()
        {
            if (_spin && _model != null)
                _model.Rotate(Vector3.up, _spinSpeed * Time.deltaTime, Space.Self);
        }
    }
}
