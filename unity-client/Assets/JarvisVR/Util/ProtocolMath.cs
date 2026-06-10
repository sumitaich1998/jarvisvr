using UnityEngine;
using JarvisVR.Protocol;

namespace JarvisVR.Util
{
    /// <summary>
    /// Conversions between the protocol's float[] wire arrays and Unity's Vector3/Quaternion.
    /// Convention (README/ARCHITECTURE §5): right-handed meters, Y-up. position=[x,y,z],
    /// rotation quaternion=[x,y,z,w], scale=[x,y,z].
    /// </summary>
    public static class ProtocolMath
    {
        public static Vector3 ToVector3(this float[] a, Vector3 fallback = default)
            => (a != null && a.Length >= 3) ? new Vector3(a[0], a[1], a[2]) : fallback;

        public static Quaternion ToQuaternion(this float[] a)
            => (a != null && a.Length >= 4) ? new Quaternion(a[0], a[1], a[2], a[3]) : Quaternion.identity;

        public static float[] ToArray(this Vector3 v) => new[] { v.x, v.y, v.z };

        public static float[] ToArray(this Quaternion q) => new[] { q.x, q.y, q.z, q.w };

        public static PosePayload ToPosePayload(Transform t)
            => new PosePayload { Position = t.position.ToArray(), Rotation = t.rotation.ToArray() };
    }
}
