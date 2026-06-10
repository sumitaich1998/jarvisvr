// Binds the Meta OVRCameraRig anchors into JarvisVR's AnchorService so world/head/hand anchoring
// "just works" on device. This whole assembly only compiles when the Meta XR Core SDK is present
// (asmdef defineConstraints: HAS_META_CORE).
#if HAS_META_CORE
using UnityEngine;
using JarvisVR.Holograms;

namespace JarvisVR.Meta
{
    [DefaultExecutionOrder(-50)] // after JarvisApp creates AnchorService, before holograms spawn
    public class MetaRigBinder : MonoBehaviour
    {
        public AnchorService anchors;
        public OVRCameraRig rig;

        private void Start()
        {
            if (anchors == null) anchors = FindObjectOfType<AnchorService>();
            if (rig == null) rig = FindObjectOfType<OVRCameraRig>();
            if (anchors == null || rig == null)
            {
                Debug.LogWarning("[Jarvis/Meta] MetaRigBinder could not find AnchorService or OVRCameraRig.");
                return;
            }

            anchors.head = rig.centerEyeAnchor;
            anchors.worldOrigin = rig.trackingSpace;
            anchors.leftHand = rig.leftHandAnchor;
            anchors.rightHand = rig.rightHandAnchor;
        }
    }
}
#endif
