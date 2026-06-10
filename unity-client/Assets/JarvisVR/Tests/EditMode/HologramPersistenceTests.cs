using System;
using System.Collections.Generic;
using NUnit.Framework;
using UnityEngine;
using UnityEngine.TestTools;
using JarvisVR.Protocol;
using JarvisVR.Holograms;

namespace JarvisVR.Tests.EditMode
{
    /// <summary>SaveLayout (PlayerPrefs) → RestoreLayout into a fresh manager reproduces the holograms
    /// with their widget_type and world pose. Runs in EditMode (manager.Spawn works without play; no
    /// connection/anchors/relay needed for known widget types).</summary>
    public class HologramPersistenceTests
    {
        private readonly List<GameObject> _toDestroy = new List<GameObject>();
        private string _key;
        private HologramPersistence _persist;

        [SetUp]
        public void SetUp()
        {
            LogAssert.ignoreFailingMessages = true; // TMP/shader noise in a bare project
            _key = "test_" + Guid.NewGuid().ToString("N");
        }

        [TearDown]
        public void TearDown()
        {
            if (_persist != null) _persist.ClearLayout();
            foreach (var go in _toDestroy) if (go != null) Object.DestroyImmediate(go);
            _toDestroy.Clear();
            LogAssert.ignoreFailingMessages = false;
        }

        private HologramManager NewManager()
        {
            var go = new GameObject("manager");
            _toDestroy.Add(go);
            return go.AddComponent<HologramManager>();
        }

        private static HologramObject Obj(string id, string widget, Vector3 pos) => new HologramObject
        {
            ObjectId = id,
            WidgetType = widget,
            Transform = new HoloTransform
            {
                Anchor = Anchors.World,
                Position = new[] { pos.x, pos.y, pos.z },
                Rotation = new[] { 0f, 0f, 0f, 1f },
                Scale = new[] { 1f, 1f, 1f },
            },
            Interactable = true,
        };

        [Test]
        public void SaveThenRestore_RebuildsHologramsWithPose()
        {
            var src = NewManager();
            src.Spawn(Obj("O1", WidgetTypes.Panel, new Vector3(0, 1, 1)));
            src.Spawn(Obj("O2", WidgetTypes.Timer, new Vector3(1, 1, 1)));
            foreach (var w in src.All) _toDestroy.Add(w.gameObject);

            var persistGo = new GameObject("persist");
            _toDestroy.Add(persistGo);
            _persist = persistGo.AddComponent<HologramPersistence>();
            _persist.layoutKey = _key;
            _persist.manager = src;
            _persist.SaveLayout();

            // restore into a fresh manager
            var dst = NewManager();
            _persist.manager = dst;
            int restored = _persist.RestoreLayout();
            foreach (var w in dst.All) _toDestroy.Add(w.gameObject);

            Assert.AreEqual(2, restored);
            Assert.AreEqual(2, dst.Count);

            Assert.IsTrue(dst.TryGet("O1", out var w1));
            Assert.AreEqual(WidgetTypes.Panel, w1.WidgetType);
            AssertApprox(new Vector3(0, 1, 1), w1.transform.localPosition);

            Assert.IsTrue(dst.TryGet("O2", out var w2));
            Assert.AreEqual(WidgetTypes.Timer, w2.WidgetType);
            AssertApprox(new Vector3(1, 1, 1), w2.transform.localPosition);
        }

        [Test]
        public void RestoreLayout_NoSavedKey_ReturnsZero()
        {
            var mgr = NewManager();
            var persistGo = new GameObject("persist");
            _toDestroy.Add(persistGo);
            _persist = persistGo.AddComponent<HologramPersistence>();
            _persist.layoutKey = _key; // nothing saved under this fresh key
            _persist.manager = mgr;
            Assert.AreEqual(0, _persist.RestoreLayout());
        }

        private static void AssertApprox(Vector3 expected, Vector3 actual, float tol = 1e-3f)
        {
            Assert.AreEqual(expected.x, actual.x, tol, "x");
            Assert.AreEqual(expected.y, actual.y, tol, "y");
            Assert.AreEqual(expected.z, actual.z, tol, "z");
        }
    }
}
