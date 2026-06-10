// Feeds Meta eye-tracking (OVREyeGaze) into JarvisVR's GazeProvider so perception.gaze uses true
// eye gaze instead of the head ray. Requires the eye-tracking permission
// (com.oculus.permission.EYE_TRACKING). Compiled only with the Meta XR Core SDK (HAS_META_CORE).
#if HAS_META_CORE
using UnityEngine;
using JarvisVR.Perception;

namespace JarvisVR.Meta
{
    public class MetaEyeGazeSource : MonoBehaviour, IGazeSource
    {
        public OVREyeGaze leftEye;
        public OVREyeGaze rightEye;

        private void Awake()
        {
            var gp = FindObjectOfType<GazeProvider>();
            if (gp != null) gp.eyeSource = this;
        }

        public bool IsAvailable => IsActive(rightEye) || IsActive(leftEye);

        private static bool IsActive(OVREyeGaze e) => e != null && e.enabled && e.EyeTrackingEnabled;

        public bool TryGetRay(out Vector3 origin, out Vector3 direction)
        {
            var eye = IsActive(rightEye) ? rightEye : (IsActive(leftEye) ? leftEye : null);
            if (eye == null) { origin = Vector3.zero; direction = Vector3.forward; return false; }
            origin = eye.transform.position;
            direction = eye.transform.forward;
            return true;
        }
    }
}
#endif
