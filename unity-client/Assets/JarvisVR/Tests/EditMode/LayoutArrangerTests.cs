using System.Collections.Generic;
using NUnit.Framework;
using UnityEngine;
using JarvisVR.Protocol;
using JarvisVR.Holograms;
using JarvisVR.Holograms.Widgets;

namespace JarvisVR.Tests.EditMode
{
    public class LayoutArrangerTests
    {
        private readonly List<GameObject> _created = new List<GameObject>();
        private const float Spacing = 0.25f;
        private const float Fwd = 1.0f; // ForwardDistance = max(0.8, 0.25*4) = 1.0

        [TearDown]
        public void TearDown()
        {
            foreach (var go in _created) if (go != null) Object.DestroyImmediate(go);
            _created.Clear();
        }

        private List<HoloWidget> MakeWidgets(int n)
        {
            var list = new List<HoloWidget>();
            for (int i = 0; i < n; i++)
            {
                var go = new GameObject($"w{i}");
                _created.Add(go);
                list.Add(go.AddComponent<PanelWidget>());
            }
            return list;
        }

        private static void AssertPos(Vector3 expected, Transform t, float tol = 1e-3f)
        {
            Assert.AreEqual(expected.x, t.localPosition.x, tol, "x");
            Assert.AreEqual(expected.y, t.localPosition.y, tol, "y");
            Assert.AreEqual(expected.z, t.localPosition.z, tol, "z");
        }

        [Test]
        public void Stack_StacksVerticallyInFront()
        {
            var w = MakeWidgets(3);
            LayoutArranger.Arrange(Arrangements.Stack, w, null, Spacing);
            AssertPos(new Vector3(0, 0 * Spacing, Fwd), w[0].transform);
            AssertPos(new Vector3(0, 1 * Spacing, Fwd), w[1].transform);
            AssertPos(new Vector3(0, 2 * Spacing, Fwd), w[2].transform);
        }

        [Test]
        public void Grid_PlacesInCenteredRowsAndColumns()
        {
            var w = MakeWidgets(4); // cols = ceil(sqrt(4)) = 2; width = (2-1)*0.25 = 0.25
            LayoutArranger.Arrange(Arrangements.Grid, w, null, Spacing);
            AssertPos(new Vector3(-0.125f, 0f, Fwd), w[0].transform);     // row0 col0
            AssertPos(new Vector3(0.125f, 0f, Fwd), w[1].transform);      // row0 col1
            AssertPos(new Vector3(-0.125f, -0.25f, Fwd), w[2].transform); // row1 col0
            AssertPos(new Vector3(0.125f, -0.25f, Fwd), w[3].transform);  // row1 col1
        }

        [Test]
        public void Arc_PlacesOnArcAtForwardDistance()
        {
            var w = MakeWidgets(5);
            LayoutArranger.Arrange(Arrangements.Arc, w, null, Spacing);
            for (int i = 0; i < w.Count; i++)
            {
                var p = w[i].transform.localPosition;
                float radial = Mathf.Sqrt(p.x * p.x + p.z * p.z);
                Assert.AreEqual(Fwd, radial, 1e-3f, $"widget {i} should sit on the arc radius");
                Assert.AreEqual(0f, p.y, 1e-3f, "arc is horizontal");
            }
            // odd count → middle item is straight ahead
            AssertPos(new Vector3(0f, 0f, Fwd), w[2].transform);
        }

        [Test]
        public void Free_LeavesPositionsUnchanged()
        {
            var w = MakeWidgets(2);
            w[0].transform.localPosition = new Vector3(5, 6, 7);
            w[1].transform.localPosition = new Vector3(-1, -2, -3);
            LayoutArranger.Arrange(Arrangements.Free, w, null, Spacing);
            AssertPos(new Vector3(5, 6, 7), w[0].transform);
            AssertPos(new Vector3(-1, -2, -3), w[1].transform);
        }

        [Test]
        public void Arrange_WithAnchor_ReparentsWidgets()
        {
            var anchorGo = new GameObject("anchor");
            _created.Add(anchorGo);
            var w = MakeWidgets(2);
            LayoutArranger.Arrange(Arrangements.Stack, w, anchorGo.transform, Spacing);
            Assert.AreSame(anchorGo.transform, w[0].transform.parent);
            Assert.AreSame(anchorGo.transform, w[1].transform.parent);
        }

        [Test]
        public void Arrange_NullOrEmpty_DoesNotThrow()
        {
            Assert.DoesNotThrow(() => LayoutArranger.Arrange(Arrangements.Arc, null, null, Spacing));
            Assert.DoesNotThrow(() => LayoutArranger.Arrange(Arrangements.Arc, new List<HoloWidget>(), null, Spacing));
        }

        [Test]
        public void Arrange_NonPositiveSpacing_FallsBackToDefault()
        {
            var w = MakeWidgets(2);
            LayoutArranger.Arrange(Arrangements.Stack, w, null, 0f); // spacing<=0 → 0.25 default
            AssertPos(new Vector3(0, 0.25f, Fwd), w[1].transform);
        }
    }
}
