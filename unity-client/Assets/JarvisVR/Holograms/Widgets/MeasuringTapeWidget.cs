using UnityEngine;
using TMPro;
using Newtonsoft.Json.Linq;

namespace JarvisVR.Holograms.Widgets
{
    /// <summary>
    /// widget_type "measuring_tape". Draws a measured segment between two world points with a
    /// distance readout. Props: { start:[x,y,z], end:[x,y,z], unit:"m"|"cm"|"ft" }.
    /// </summary>
    public class MeasuringTapeWidget : HoloWidget
    {
        private Transform _line;
        private Transform _a;
        private Transform _b;
        private TextMeshPro _label;

        protected override void Build()
        {
            _line = CreatePrimitive(PrimitiveType.Cube, "line", Vector3.zero, new Vector3(0.01f, 0.01f, 1f),
                new Color(1f, 0.85f, 0.2f));
            _a = CreatePrimitive(PrimitiveType.Sphere, "a", Vector3.zero, Vector3.one * 0.03f, new Color(1f, 0.85f, 0.2f), keepCollider: true);
            _b = CreatePrimitive(PrimitiveType.Sphere, "b", Vector3.zero, Vector3.one * 0.03f, new Color(1f, 0.85f, 0.2f), keepCollider: true);
            _label = CreateText("label", "", 0.035f, Color.white, Vector3.zero,
                align: TextAlignmentOptions.Center, size: new Vector2(0.3f, 0.05f));
        }

        protected override void ApplyProps(JObject props)
        {
            Vector3 start = ReadVec("start", new Vector3(-0.25f, 0, 0));
            Vector3 end = ReadVec("end", new Vector3(0.25f, 0, 0));
            // start/end are anchor-local positions; place children accordingly.
            _a.localPosition = start;
            _b.localPosition = end;

            Vector3 dir = end - start;
            float len = dir.magnitude;
            _line.localPosition = (start + end) * 0.5f;
            _line.localRotation = len > 1e-4f ? Quaternion.LookRotation(dir) : Quaternion.identity;
            _line.localScale = new Vector3(0.008f, 0.008f, Mathf.Max(0.001f, len));

            _label.transform.localPosition = (start + end) * 0.5f + Vector3.up * 0.05f;
            _label.text = Format(len, GetString("unit", "m"));
        }

        private Vector3 ReadVec(string key, Vector3 def)
        {
            var a = GetArray(key);
            return (a != null && a.Count >= 3)
                ? new Vector3(a[0].Value<float>(), a[1].Value<float>(), a[2].Value<float>()) : def;
        }

        private static string Format(float meters, string unit)
        {
            switch (unit)
            {
                case "cm": return $"{meters * 100f:0} cm";
                case "ft": return $"{meters * 3.28084f:0.00} ft";
                default: return $"{meters:0.00} m";
            }
        }
    }
}
