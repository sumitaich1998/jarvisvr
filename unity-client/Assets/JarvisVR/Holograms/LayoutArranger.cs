using System.Collections.Generic;
using UnityEngine;
using JarvisVR.Protocol;

namespace JarvisVR.Holograms
{
    /// <summary>
    /// Arranges a set of holograms for <c>holo.layout</c> (docs/PROTOCOL.md §5.10):
    /// arc | grid | stack | free, relative to an anchor, spaced by <c>spacing</c> meters.
    /// </summary>
    public static class LayoutArranger
    {
        public static void Arrange(string arrangement, IList<HoloWidget> widgets, Transform anchor, float spacing)
        {
            if (widgets == null || widgets.Count == 0) return;
            if (spacing <= 0f) spacing = 0.25f;

            for (int i = 0; i < widgets.Count; i++)
            {
                var w = widgets[i];
                if (w == null) continue;
                if (anchor != null) w.transform.SetParent(anchor, false);

                switch (arrangement)
                {
                    case Arrangements.Grid:
                        w.transform.localPosition = GridPos(i, widgets.Count, spacing);
                        break;
                    case Arrangements.Stack:
                        w.transform.localPosition = new Vector3(0f, i * spacing, ForwardDistance(spacing));
                        break;
                    case Arrangements.Arc:
                        w.transform.localPosition = ArcPos(i, widgets.Count, spacing);
                        break;
                    case Arrangements.Free:
                    default:
                        // leave existing transform untouched
                        break;
                }
            }
        }

        private static float ForwardDistance(float spacing) => Mathf.Max(0.8f, spacing * 4f);

        private static Vector3 ArcPos(int i, int n, float spacing)
        {
            float dist = ForwardDistance(spacing);
            // total angular spread grows with count but is capped so it stays in front of the user.
            float spreadDeg = Mathf.Min(150f, spacing * 40f * Mathf.Max(1, n - 1));
            float t = n > 1 ? (i / (float)(n - 1)) - 0.5f : 0f; // -0.5..0.5
            float ang = t * spreadDeg * Mathf.Deg2Rad;
            return new Vector3(Mathf.Sin(ang) * dist, 0f, Mathf.Cos(ang) * dist);
        }

        private static Vector3 GridPos(int i, int n, float spacing)
        {
            int cols = Mathf.Max(1, Mathf.CeilToInt(Mathf.Sqrt(n)));
            int row = i / cols;
            int col = i % cols;
            float width = (cols - 1) * spacing;
            return new Vector3(col * spacing - width * 0.5f, -row * spacing, ForwardDistance(spacing));
        }
    }
}
