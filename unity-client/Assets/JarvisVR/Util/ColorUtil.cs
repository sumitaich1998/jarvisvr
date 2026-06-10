using UnityEngine;

namespace JarvisVR.Util
{
    /// <summary>Small helpers for parsing colors that arrive as strings in widget props.</summary>
    public static class ColorUtil
    {
        /// <summary>
        /// Parse "#RRGGBB", "#RRGGBBAA", "RRGGBB", or an HTML color name. Returns
        /// <paramref name="fallback"/> when the value is empty/unparseable.
        /// </summary>
        public static Color Parse(string s, Color fallback)
        {
            if (string.IsNullOrEmpty(s)) return fallback;
            var v = s.Trim();
            if (!v.StartsWith("#") && IsHex(v)) v = "#" + v;
            return ColorUtility.TryParseHtmlString(v, out var c) ? c : fallback;
        }

        private static bool IsHex(string s)
        {
            if (s.Length != 6 && s.Length != 8) return false;
            foreach (var ch in s)
            {
                bool ok = (ch >= '0' && ch <= '9') || (ch >= 'a' && ch <= 'f') || (ch >= 'A' && ch <= 'F');
                if (!ok) return false;
            }
            return true;
        }

        /// <summary>Perceptual-ish temperature ramp (cold blue → hot red) for °C in [-10, 40].</summary>
        public static Color Temperature(float celsius)
        {
            float t = Mathf.InverseLerp(-10f, 40f, celsius);
            return Color.Lerp(new Color(0.3f, 0.6f, 1f), new Color(1f, 0.4f, 0.2f), t);
        }
    }
}
