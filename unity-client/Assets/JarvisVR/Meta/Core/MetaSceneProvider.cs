// Feeds room surfaces + spatial anchors from the Meta Scene model into SceneReporter so the agent
// can reason about the user's space (client.scene §5.12). Requires Scene capture/permission on the
// headset. This assembly only compiles when the Meta XR Core SDK is present (HAS_META_CORE).
#if HAS_META_CORE
using System.Collections.Generic;
using UnityEngine;
using JarvisVR.Protocol;
using JarvisVR.Shell;
using JarvisVR.Util;

namespace JarvisVR.Meta
{
    public class MetaSceneProvider : MonoBehaviour, ISceneProvider
    {
        private void Start()
        {
            // Auto-wire into the reporter if present.
            var reporter = FindObjectOfType<SceneReporter>();
            if (reporter != null) reporter.provider = this;
        }

        public List<Surface> GetSurfaces()
        {
            var list = new List<Surface>();
            foreach (var plane in FindObjectsOfType<OVRScenePlane>())
            {
                var t = plane.transform;
                list.Add(new Surface
                {
                    Id = plane.name,
                    Type = Classify(plane.gameObject),
                    Center = t.position.ToArray(),
                    Normal = t.forward.ToArray(),
                });
            }
            return list;
        }

        public List<AnchorPose> GetAnchors()
        {
            var list = new List<AnchorPose>();
            foreach (var anchor in FindObjectsOfType<OVRSceneAnchor>())
            {
                var t = anchor.transform;
                list.Add(new AnchorPose
                {
                    Id = anchor.Uuid.ToString(),
                    Position = t.position.ToArray(),
                    Rotation = t.rotation.ToArray(),
                });
            }
            return list;
        }

        private static string Classify(GameObject go)
        {
            var sem = go.GetComponent<OVRSemanticClassification>();
            if (sem != null && sem.Labels != null && sem.Labels.Count > 0)
                return sem.Labels[0].ToLowerInvariant();
            return go.name.ToLowerInvariant();
        }
    }
}
#endif
