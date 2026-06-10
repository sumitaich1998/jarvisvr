using UnityEngine;
using TMPro;
using Newtonsoft.Json.Linq;
using JarvisVR.Util;

namespace JarvisVR.Holograms.Widgets
{
    /// <summary>
    /// widget_type "navigation_arrow". A wayfinding arrow that points toward a bearing or a world
    /// target. Props: { bearing_deg, target:[x,y,z], distance_m, label, color }.
    /// </summary>
    public class NavigationArrowWidget : HoloWidget
    {
        private Transform _arrow;
        private TextMeshPro _label;
        private bool _hasTarget;
        private Vector3 _target;

        protected override void Build()
        {
            _arrow = new GameObject("arrow").transform;
            _arrow.SetParent(transform, false);
            // shaft + head, pointing along +Z
            CreatePrimitive(PrimitiveType.Cube, "shaft", new Vector3(0, 0, -0.04f), new Vector3(0.03f, 0.03f, 0.12f),
                new Color(0.2f, 0.8f, 1f), _arrow);
            var head = CreatePrimitive(PrimitiveType.Cube, "head", new Vector3(0, 0, 0.05f), new Vector3(0.08f, 0.08f, 0.08f),
                new Color(0.2f, 0.9f, 1f), _arrow, keepCollider: true);
            head.localRotation = Quaternion.Euler(0f, 45f, 45f);
            _label = CreateText("label", "", 0.03f, Color.white, new Vector3(0f, -0.09f, 0f),
                align: TextAlignmentOptions.Center, size: new Vector2(0.4f, 0.05f));
        }

        protected override void ApplyProps(JObject props)
        {
            var c = GetColor("color", new Color(0.2f, 0.85f, 1f));
            foreach (var r in _arrow.GetComponentsInChildren<Renderer>()) HoloMaterials.SetAlbedo(r.material, c);

            var t = GetArray("target");
            _hasTarget = t != null && t.Count >= 3;
            if (_hasTarget) _target = new Vector3(t[0].Value<float>(), t[1].Value<float>(), t[2].Value<float>());
            else if (Has("bearing_deg")) _arrow.localRotation = Quaternion.Euler(0f, GetFloat("bearing_deg"), 0f);

            string label = GetString("label", "");
            if (Has("distance_m")) label = string.IsNullOrEmpty(label) ? $"{GetFloat("distance_m"):0.0} m" : $"{label}  {GetFloat("distance_m"):0.0} m";
            _label.text = label;
        }

        private void Update()
        {
            if (!_hasTarget) return;
            Vector3 dir = _target - transform.position;
            if (dir.sqrMagnitude < 1e-4f) return;
            _arrow.rotation = Quaternion.Slerp(_arrow.rotation, Quaternion.LookRotation(dir), Time.deltaTime * 6f);
        }
    }
}
