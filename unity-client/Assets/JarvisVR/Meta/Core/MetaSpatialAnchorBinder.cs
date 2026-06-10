// World-locks a hologram with a Meta Spatial Anchor (drift-free placement that survives head
// movement). Add to a hologram root. Opt-in via the HAS_META_ANCHORS scripting define (the
// save/load anchor API surface varies by SDK version). Cross-session UUID persistence can be layered
// on top of HologramPersistence / IAnchorStore as a follow-up.
#if HAS_META_ANCHORS
using UnityEngine;

namespace JarvisVR.Meta
{
    [DisallowMultipleComponent]
    public class MetaSpatialAnchorBinder : MonoBehaviour
    {
        private void OnEnable()
        {
            if (GetComponent<OVRSpatialAnchor>() == null)
                gameObject.AddComponent<OVRSpatialAnchor>(); // creates + localizes a world anchor here
        }
    }
}
#endif
