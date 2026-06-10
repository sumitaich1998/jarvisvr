using UnityEngine;
using TMPro;
using Newtonsoft.Json.Linq;
using JarvisVR.Util;

namespace JarvisVR.Holograms.Widgets
{
    /// <summary>
    /// widget_type "weather_orb". A glowing sphere tinted by temperature/condition with city +
    /// temp + condition captions. Props: { city, temp_c, condition, humidity }.
    /// </summary>
    public class WeatherOrbWidget : HoloWidget
    {
        private Transform _orb;
        private TextMeshPro _city;
        private TextMeshPro _temp;
        private TextMeshPro _cond;

        protected override void Build()
        {
            _orb = CreatePrimitive(PrimitiveType.Sphere, "orb", Vector3.zero,
                Vector3.one * 0.22f, new Color(0.4f, 0.7f, 1f));

            _city = CreateText("city", "", 0.04f, Color.white, new Vector3(0f, 0.18f, 0f),
                align: TextAlignmentOptions.Center, size: new Vector2(0.4f, 0.06f));
            _temp = CreateText("temp", "", 0.07f, Color.white, new Vector3(0f, 0f, -0.12f),
                align: TextAlignmentOptions.Center, size: new Vector2(0.4f, 0.1f));
            _cond = CreateText("cond", "", 0.035f, new Color(0.85f, 0.9f, 1f), new Vector3(0f, -0.18f, 0f),
                align: TextAlignmentOptions.Center, size: new Vector2(0.4f, 0.06f));
        }

        protected override void ApplyProps(JObject props)
        {
            string city = GetString("city", "");
            string condition = GetString("condition", "clear").ToLowerInvariant();
            bool hasTemp = Has("temp_c");
            float temp = GetFloat("temp_c", 20f);

            _city.text = city;
            _temp.text = hasTemp ? $"{Mathf.RoundToInt(temp)}\u00B0C" : "";
            _cond.text = Has("humidity") ? $"{condition}  •  {GetInt("humidity")}%" : condition;

            // Blend a condition base color with a temperature tint.
            Color baseCol = ConditionColor(condition);
            Color tint = hasTemp ? ColorUtil.Temperature(temp) : baseCol;
            SetColor(_orb, Color.Lerp(baseCol, tint, 0.5f));
        }

        private static Color ConditionColor(string condition)
        {
            switch (condition)
            {
                case "clear":
                case "sunny": return new Color(1f, 0.82f, 0.3f);
                case "clouds":
                case "cloudy":
                case "overcast": return new Color(0.6f, 0.65f, 0.72f);
                case "rain":
                case "rainy":
                case "drizzle": return new Color(0.35f, 0.55f, 0.9f);
                case "snow": return new Color(0.9f, 0.95f, 1f);
                case "storm":
                case "thunderstorm": return new Color(0.5f, 0.4f, 0.8f);
                case "fog":
                case "mist": return new Color(0.7f, 0.72f, 0.75f);
                default: return new Color(0.5f, 0.75f, 1f);
            }
        }
    }
}
