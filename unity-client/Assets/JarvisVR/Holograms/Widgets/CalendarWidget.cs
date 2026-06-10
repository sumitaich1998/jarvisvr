using System;
using System.Collections.Generic;
using UnityEngine;
using TMPro;
using Newtonsoft.Json.Linq;

namespace JarvisVR.Holograms.Widgets
{
    /// <summary>
    /// widget_type "calendar". A month grid with today highlighted and event days marked.
    /// Props: { month (1-12), year, today (day), events:[int | {day,title}] }.
    /// </summary>
    public class CalendarWidget : HoloWidget
    {
        private const float W = 0.56f;
        private TextMeshPro _title;
        private Transform _grid;

        protected override void Build()
        {
            CreatePrimitive(PrimitiveType.Cube, "bg", Vector3.zero, new Vector3(W, 0.5f, 0.01f),
                new Color(0.07f, 0.08f, 0.12f, 0.96f));
            _title = CreateText("title", "", 0.034f, new Color(0.7f, 0.85f, 1f), new Vector3(0f, 0.21f, -0.011f),
                align: TextAlignmentOptions.Center, size: new Vector2(W, 0.05f));
            _grid = new GameObject("grid").transform;
            _grid.SetParent(transform, false);
        }

        protected override void ApplyProps(JObject props)
        {
            var now = DateTime.UtcNow;
            int month = Mathf.Clamp(GetInt("month", now.Month), 1, 12);
            int year = GetInt("year", now.Year);
            if (year < 1) year = now.Year;
            int today = GetInt("today", (month == now.Month && year == now.Year) ? now.Day : -1);

            var events = ReadEventDays();
            foreach (Transform c in _grid) Destroy(c.gameObject);
            _title.text = new DateTime(year, month, 1).ToString("MMMM yyyy");

            string[] dow = { "S", "M", "T", "W", "T", "F", "S" };
            float cell = W / 7f * 0.92f;
            float x0 = -W * 0.5f + cell * 0.6f;
            float y0 = 0.14f;

            for (int c = 0; c < 7; c++)
                CreateText($"h{c}", dow[c], 0.024f, new Color(0.6f, 0.65f, 0.75f),
                    new Vector3(x0 + c * cell, y0, -0.011f), _grid, TextAlignmentOptions.Center, new Vector2(cell, 0.03f));

            int first = (int)new DateTime(year, month, 1).DayOfWeek; // 0=Sun
            int days = DateTime.DaysInMonth(year, month);
            for (int d = 1; d <= days; d++)
            {
                int idx = first + d - 1;
                int row = idx / 7, col = idx % 7;
                float x = x0 + col * cell;
                float y = y0 - 0.045f - row * 0.045f;

                bool isToday = d == today;
                bool hasEvent = events.Contains(d);
                if (isToday)
                    CreatePrimitive(PrimitiveType.Cube, $"hl{d}", new Vector3(x, y, -0.009f),
                        new Vector3(cell * 0.9f, 0.04f, 0.004f), new Color(0.2f, 0.5f, 0.95f), _grid);

                var col2 = isToday ? Color.white : (hasEvent ? new Color(1f, 0.8f, 0.3f) : new Color(0.85f, 0.88f, 0.95f));
                CreateText($"d{d}", hasEvent ? $"{d}•" : d.ToString(), 0.024f, col2,
                    new Vector3(x, y, -0.012f), _grid, TextAlignmentOptions.Center, new Vector2(cell, 0.04f));
            }
        }

        private HashSet<int> ReadEventDays()
        {
            var set = new HashSet<int>();
            var arr = GetArray("events");
            if (arr == null) return set;
            foreach (var e in arr)
            {
                if (e.Type == JTokenType.Integer) set.Add(e.Value<int>());
                else if (e is JObject o && o.TryGetValue("day", out var dv) && dv.Type == JTokenType.Integer) set.Add(dv.Value<int>());
            }
            return set;
        }
    }
}
