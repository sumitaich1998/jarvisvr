using System.Collections;
using System.Collections.Generic;
using NUnit.Framework;
using UnityEngine;
using UnityEngine.TestTools;
using JarvisVR.Net;
using JarvisVR.Protocol;
using JarvisVR.Holograms;

namespace JarvisVR.Tests.PlayMode
{
    public class HologramManagerPlayTests
    {
        private readonly List<Object> _track = new List<Object>();

        [SetUp]
        public void SetUp() => LogAssert.ignoreFailingMessages = true;

        [TearDown]
        public void TearDown()
        {
            PlayModeTestUtil.Cleanup(_track);
            LogAssert.ignoreFailingMessages = false;
        }

        private static HologramObject Spawn(string id, string widget, Vector3 pos) => new HologramObject
        {
            ObjectId = id,
            WidgetType = widget,
            Transform = new HoloTransform { Anchor = Anchors.World, Position = new[] { pos.x, pos.y, pos.z }, Rotation = new[] { 0f, 0f, 0f, 1f }, Scale = new[] { 1f, 1f, 1f } },
            Interactable = false,
        };

        [UnityTest]
        public IEnumerator HoloSpawn_Update_Destroy_DrivesManager()
        {
            var conn = PlayModeTestUtil.NewConnection(_track);
            var mgr = PlayModeTestUtil.NewComponent<HologramManager>("mgr", _track);
            yield return null; // Awake/OnEnable/Start

            // spawn
            conn.Router.Route(EnvelopeSerializer.Build(MessageTypes.HoloSpawn, Spawn("O1", WidgetTypes.Panel, new Vector3(0, 1, 1)), "S", id: "cmd1"));
            Assert.AreEqual(1, mgr.Count, "spawn should add one hologram");
            Assert.IsTrue(mgr.TryGet("O1", out var w));
            Assert.AreEqual(WidgetTypes.Panel, w.WidgetType);

            // update transform
            conn.Router.Route(EnvelopeSerializer.Build(MessageTypes.HoloUpdate,
                new HoloUpdate { ObjectId = "O1", Transform = new HoloTransform { Position = new[] { 2f, 2f, 2f } } }, "S"));
            Assert.AreEqual(2f, w.transform.localPosition.x, 1e-3f);
            Assert.AreEqual(2f, w.transform.localPosition.y, 1e-3f);

            // destroy (fade 0 → removed from registry immediately)
            conn.Router.Route(EnvelopeSerializer.Build(MessageTypes.HoloDestroy, new HoloDestroy { ObjectId = "O1", FadeMs = 0 }, "S"));
            Assert.AreEqual(0, mgr.Count, "destroy should remove it from the registry");

            yield return null;
        }

        [UnityTest]
        public IEnumerator UnknownWidget_StillSpawnsPlaceholder()
        {
            var conn = PlayModeTestUtil.NewConnection(_track);
            var mgr = PlayModeTestUtil.NewComponent<HologramManager>("mgr", _track);
            yield return null;

            conn.Router.Route(EnvelopeSerializer.Build(MessageTypes.HoloSpawn, Spawn("U1", "totally_unknown", Vector3.zero), "S"));
            Assert.AreEqual(1, mgr.Count, "unknown widget_type falls back to a placeholder (does not drop)");
            yield return null;
        }

        [UnityTest]
        public IEnumerator UnknownMessageType_IsIgnored()
        {
            var conn = PlayModeTestUtil.NewConnection(_track);
            var mgr = PlayModeTestUtil.NewComponent<HologramManager>("mgr", _track);
            yield return null;

            Assert.DoesNotThrow(() => conn.Router.Route(EnvelopeSerializer.Build("future.message", new { x = 1 }, "S")));
            Assert.AreEqual(0, mgr.Count);
            yield return null;
        }
    }
}
