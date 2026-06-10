// Supplies accurate passthrough camera pose + intrinsics to the VisionStreamer (so vision frames
// carry the real camera pose for unprojection, not just the head pose). Opt-in via the HAS_META_PCA
// scripting define once you've added Meta's Passthrough Camera API utilities.
//
// Wiring: drive `cameraAnchor` from the PCA-reported pose and set the intrinsics from
// PassthroughCameraUtils, e.g.:
//     var pose = PassthroughCameraUtils.GetCameraPoseInWorld(PassthroughCameraEye.Left);
//     cameraAnchor.SetPositionAndRotation(pose.position, pose.rotation);
//     var ci = PassthroughCameraUtils.GetCameraIntrinsics(PassthroughCameraEye.Left);
//     fx = ci.FocalLength.x; fy = ci.FocalLength.y; cx = ci.PrincipalPoint.x; cy = ci.PrincipalPoint.y;
// (kept out of this file so the project compiles without the PCA sample assembly).
#if HAS_META_PCA
using UnityEngine;
using JarvisVR.Perception;
using JarvisVR.Protocol;

namespace JarvisVR.Meta
{
    public class MetaCameraPoseSource : MonoBehaviour, ICameraPoseSource
    {
        [Tooltip("Transform driven from PassthroughCameraUtils.GetCameraPoseInWorld each frame.")]
        public Transform cameraAnchor;
        public string cameraId = CameraIds.RgbCenter;

        [Header("Intrinsics at the reference width (scaled to the encoded frame)")]
        public float fx = 720f, fy = 720f, cx = 512f, cy = 512f;
        public int intrinsicsReferenceWidth = 1024;

        private void Awake()
        {
            var provider = FindObjectOfType<PassthroughCameraProvider>();
            if (provider != null) provider.poseSource = this;
        }

        public string CameraId => cameraId;

        public bool TryGetPose(out Vector3 position, out Quaternion rotation)
        {
            if (cameraAnchor == null) { position = Vector3.zero; rotation = Quaternion.identity; return false; }
            position = cameraAnchor.position;
            rotation = cameraAnchor.rotation;
            return true;
        }

        public CameraIntrinsics GetIntrinsics(int width, int height)
        {
            float s = intrinsicsReferenceWidth > 0 ? width / (float)intrinsicsReferenceWidth : 1f;
            return new CameraIntrinsics { Fx = fx * s, Fy = fy * s, Cx = cx * s, Cy = cy * s };
        }
    }
}
#endif
