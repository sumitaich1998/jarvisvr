using System.Collections.Generic;
using NUnit.Framework;
using UnityEngine;
using JarvisVR.Protocol;
using JarvisVR.Holograms;

namespace JarvisVR.Tests.EditMode
{
    public class AnchorServiceTests
    {
        private readonly List<GameObject> _created = new List<GameObject>();
        private AnchorService _anchors;
        private Transform _head, _left, _right, _world, _floor;

        [SetUp]
        public void SetUp()
        {
            _anchors = NewGo<AnchorService>("anchors");
            _head = NewGo("head");
            _left = NewGo("left");
            _right = NewGo("right");
            _world = NewGo("world");
            _floor = NewGo("floor");
            _anchors.head = _head;
            _anchors.leftHand = _left;
            _anchors.rightHand = _right;
            _anchors.worldOrigin = _world;
        }

        [TearDown]
        public void TearDown()
        {
            foreach (var go in _created) if (go != null) Object.DestroyImmediate(go);
            _created.Clear();
        }

        private Transform NewGo(string name)
        {
            var go = new GameObject(name);
            _created.Add(go);
            return go.transform;
        }

        private T NewGo<T>(string name) where T : Component
        {
            var go = new GameObject(name);
            _created.Add(go);
            return go.AddComponent<T>();
        }

        [Test]
        public void Resolve_MapsEachAnchorToItsTransform()
        {
            Assert.AreSame(_head, _anchors.Resolve(Anchors.Head));
            Assert.AreSame(_left, _anchors.Resolve(Anchors.HandLeft));
            Assert.AreSame(_right, _anchors.Resolve(Anchors.HandRight));
            Assert.AreSame(_world, _anchors.Resolve(Anchors.World));
        }

        [Test]
        public void Resolve_UnknownAnchor_FallsBackToWorldOrigin()
        {
            Assert.AreSame(_world, _anchors.Resolve("nonsense"));
        }

        [Test]
        public void Surface_RegisterAndResolve()
        {
            _anchors.RegisterSurface("floor", _floor);
            Assert.IsTrue(_anchors.TryGetSurface("floor", out var t));
            Assert.AreSame(_floor, t);
            Assert.AreSame(_floor, _anchors.Resolve(Anchors.Surface));
            Assert.AreSame(_floor, _anchors.PrimarySurface());
        }

        [Test]
        public void Surface_WithNoneRegistered_ResolvesToWorldOrigin()
        {
            Assert.AreSame(_world, _anchors.Resolve(Anchors.Surface));
        }

        [Test]
        public void RegisterSurface_IgnoresNullOrEmpty()
        {
            _anchors.RegisterSurface(null, _floor);
            _anchors.RegisterSurface("", _floor);
            _anchors.RegisterSurface("x", null);
            Assert.IsFalse(_anchors.TryGetSurface("x", out _));
        }

        [Test]
        public void FallbackHead_UsesMainCameraWhenHeadNull()
        {
            var camGo = new GameObject("cam");
            _created.Add(camGo);
            camGo.AddComponent<Camera>();
            camGo.tag = "MainCamera";

            _anchors.head = null;
            var head = _anchors.FallbackHead();

            Assert.IsNotNull(Camera.main, "test requires a main camera");
            Assert.AreSame(Camera.main.transform, head);
            Assert.AreSame(Camera.main.transform, _anchors.Resolve(Anchors.Head));
        }
    }
}
