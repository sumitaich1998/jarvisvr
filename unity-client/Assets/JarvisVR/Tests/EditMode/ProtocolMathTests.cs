using NUnit.Framework;
using UnityEngine;
using JarvisVR.Util;

namespace JarvisVR.Tests.EditMode
{
    public class ProtocolMathTests
    {
        [Test]
        public void ToVector3_ParsesXyz()
        {
            var v = new[] { 1f, 2f, 3f }.ToVector3();
            Assert.AreEqual(new Vector3(1, 2, 3), v);
        }

        [Test]
        public void ToVector3_NullOrShort_ReturnsFallback()
        {
            Assert.AreEqual(new Vector3(9, 9, 9), ((float[])null).ToVector3(new Vector3(9, 9, 9)));
            Assert.AreEqual(Vector3.zero, new[] { 1f, 2f }.ToVector3());
        }

        [Test]
        public void ToQuaternion_ParsesXyzw()
        {
            var q = new[] { 0f, 0f, 0f, 1f }.ToQuaternion();
            Assert.Less(Quaternion.Angle(Quaternion.identity, q), 0.01f);
        }

        [Test]
        public void ToQuaternion_NullOrShort_ReturnsIdentity()
        {
            Assert.AreEqual(Quaternion.identity, ((float[])null).ToQuaternion());
            Assert.AreEqual(Quaternion.identity, new[] { 0f, 0f, 1f }.ToQuaternion());
        }

        [Test]
        public void ToArray_Vector3_RoundTrips()
        {
            var arr = new Vector3(0.3f, -1.5f, 2f).ToArray();
            Assert.AreEqual(3, arr.Length);
            Assert.AreEqual(0.3f, arr[0], 1e-5f);
            Assert.AreEqual(-1.5f, arr[1], 1e-5f);
            Assert.AreEqual(2f, arr[2], 1e-5f);
            Assert.AreEqual(new Vector3(0.3f, -1.5f, 2f), arr.ToVector3());
        }

        [Test]
        public void ToArray_Quaternion_RoundTrips()
        {
            var q = Quaternion.Euler(10, 20, 30);
            var arr = q.ToArray();
            Assert.AreEqual(4, arr.Length);
            Assert.Less(Quaternion.Angle(q, arr.ToQuaternion()), 0.01f);
        }

        [Test]
        public void ToPosePayload_ReadsTransform()
        {
            var go = new GameObject("posetest");
            try
            {
                go.transform.position = new Vector3(1, 2, 3);
                go.transform.rotation = Quaternion.Euler(0, 90, 0);
                var pose = ProtocolMath.ToPosePayload(go.transform);
                Assert.AreEqual(1f, pose.Position[0], 1e-4f);
                Assert.AreEqual(2f, pose.Position[1], 1e-4f);
                Assert.AreEqual(3f, pose.Position[2], 1e-4f);
                Assert.Less(Quaternion.Angle(go.transform.rotation, pose.Rotation.ToQuaternion()), 0.01f);
            }
            finally { Object.DestroyImmediate(go); }
        }
    }
}
