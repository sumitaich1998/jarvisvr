using NUnit.Framework;
using UnityEngine;
using JarvisVR.Holograms;

namespace JarvisVR.Tests.EditMode
{
    public class BillboardTests
    {
        [Test]
        public void FaceRotation_CameraBehind_FacesForward()
        {
            // object at origin, camera 1m behind (−Z) → object should face +Z (identity look)
            bool ok = Billboard.TryFaceRotation(Vector3.zero, new Vector3(0, 0, -1), false, out var rot);
            Assert.IsTrue(ok);
            Assert.Less(Quaternion.Angle(Quaternion.identity, rot), 0.1f);
        }

        [Test]
        public void FaceRotation_CameraInFront_TurnsAround()
        {
            // camera at +Z → object faces −Z (≈180° about Y)
            bool ok = Billboard.TryFaceRotation(Vector3.zero, new Vector3(0, 0, 1), false, out var rot);
            Assert.IsTrue(ok);
            Assert.AreEqual(180f, Quaternion.Angle(Quaternion.identity, rot), 0.5f);
        }

        [Test]
        public void FaceRotation_YawOnly_IgnoresVerticalOffset()
        {
            // camera below and behind; yawOnly flattens the vertical component → identity look
            bool ok = Billboard.TryFaceRotation(Vector3.zero, new Vector3(0, -1, -1), true, out var rot);
            Assert.IsTrue(ok);
            Assert.Less(Quaternion.Angle(Quaternion.identity, rot), 0.1f);
            // resulting forward should have no pitch (y ≈ 0)
            Assert.AreEqual(0f, (rot * Vector3.forward).y, 1e-3f);
        }

        [Test]
        public void FaceRotation_Coincident_ReturnsFalse()
        {
            bool ok = Billboard.TryFaceRotation(Vector3.one, Vector3.one, false, out var rot);
            Assert.IsFalse(ok);
            Assert.AreEqual(Quaternion.identity, rot);
        }
    }
}
