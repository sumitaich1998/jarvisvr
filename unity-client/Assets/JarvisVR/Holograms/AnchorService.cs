using System.Collections.Generic;
using UnityEngine;
using JarvisVR.Protocol;

namespace JarvisVR.Holograms
{
    /// <summary>
    /// Resolves the protocol's anchor enum (world | head | hand_left | hand_right | surface) to a
    /// Unity <see cref="Transform"/>. Holograms are parented to the resolved transform so their
    /// protocol-space position/rotation/scale is interpreted relative to that anchor.
    ///
    /// Assign <see cref="head"/>/<see cref="leftHand"/>/<see cref="rightHand"/> to the rig anchors
    /// (e.g. OVRCameraRig.centerEyeAnchor / hand anchors). With the Meta SDK present, this is wired
    /// automatically by JarvisVR.Meta.MetaRigBinder.
    /// </summary>
    [DisallowMultipleComponent]
    public class AnchorService : MonoBehaviour
    {
        [Tooltip("Head / center-eye transform (OVRCameraRig.centerEyeAnchor or Main Camera).")]
        public Transform head;
        public Transform leftHand;
        public Transform rightHand;
        [Tooltip("World origin (XR Origin / tracking space). If null, world anchor == scene root.")]
        public Transform worldOrigin;

        private readonly Dictionary<string, Transform> _surfaces = new Dictionary<string, Transform>();

        private void Awake() => FallbackHead();

        /// <summary>Returns the parent transform for an anchor (null == world space scene root).</summary>
        public Transform Resolve(string anchor)
        {
            switch (anchor)
            {
                case Anchors.Head: return head != null ? head : FallbackHead();
                case Anchors.HandLeft: return leftHand;
                case Anchors.HandRight: return rightHand;
                case Anchors.Surface: return PrimarySurface();
                case Anchors.World:
                default: return worldOrigin;
            }
        }

        public Transform FallbackHead()
        {
            if (head == null && Camera.main != null) head = Camera.main.transform;
            return head;
        }

        public void RegisterSurface(string id, Transform t)
        {
            if (!string.IsNullOrEmpty(id) && t != null) _surfaces[id] = t;
        }

        public bool TryGetSurface(string id, out Transform t) => _surfaces.TryGetValue(id, out t);

        public Transform PrimarySurface()
        {
            foreach (var kv in _surfaces)
                if (kv.Value != null) return kv.Value;
            return worldOrigin;
        }
    }
}
