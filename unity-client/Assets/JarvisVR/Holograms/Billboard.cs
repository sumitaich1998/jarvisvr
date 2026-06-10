using UnityEngine;

namespace JarvisVR.Holograms
{
    /// <summary>
    /// Makes an object face the user. Added/removed automatically by <see cref="HologramManager"/>
    /// when a hologram's transform sets <c>billboard:true</c> (docs/PROTOCOL.md §5.6).
    /// </summary>
    public class Billboard : MonoBehaviour
    {
        [Tooltip("Usually the head/center-eye transform. Falls back to Camera.main.")]
        public Transform target;

        [Tooltip("Keep upright (yaw-only) instead of full free rotation.")]
        public bool yawOnly = false;

        private void LateUpdate()
        {
            var cam = target != null ? target : (Camera.main != null ? Camera.main.transform : null);
            if (cam == null) return;
            if (TryFaceRotation(transform.position, cam.position, yawOnly, out var rot))
                transform.rotation = rot;
        }

        /// <summary>Pure facing math (testable): the rotation that points an object at the camera.
        /// Returns false (and identity) when the object is coincident with the camera.</summary>
        internal static bool TryFaceRotation(Vector3 objectPos, Vector3 cameraPos, bool yawOnly, out Quaternion rotation)
        {
            Vector3 dir = objectPos - cameraPos;
            if (yawOnly) dir.y = 0f;
            if (dir.sqrMagnitude < 1e-6f) { rotation = Quaternion.identity; return false; }
            rotation = Quaternion.LookRotation(dir.normalized, Vector3.up);
            return true;
        }
    }
}
