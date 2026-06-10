using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using JarvisVR.Net;
using JarvisVR.Protocol;
using JarvisVR.Holograms;
using JarvisVR.Util;

namespace JarvisVR.Shell
{
    /// <summary>
    /// Optional source of spatial scene data (surfaces/anchors) for <see cref="SceneReporter"/>.
    /// Implemented by JarvisVR.Meta.MetaSceneProvider when the Meta Scene API is available;
    /// otherwise the reporter just sends head pose.
    /// </summary>
    public interface ISceneProvider
    {
        List<Surface> GetSurfaces();
        List<AnchorPose> GetAnchors();
    }

    /// <summary>
    /// Periodically sends <c>client.scene</c> (docs/PROTOCOL.md §5.12): head pose plus, when a
    /// provider is present, room surfaces and spatial anchors.
    /// </summary>
    [DisallowMultipleComponent]
    public class SceneReporter : MonoBehaviour
    {
        public JarvisConnection connection;
        public AnchorService anchors;
        [Min(0.5f)] public float interval = 2f;

        /// <summary>Optional; assign a Meta scene provider to include surfaces/anchors.</summary>
        public ISceneProvider provider;

        private void Awake()
        {
            if (connection == null) connection = FindObjectOfType<JarvisConnection>();
            if (anchors == null) anchors = FindObjectOfType<AnchorService>();
            if (provider == null) provider = GetComponent<ISceneProvider>();
        }

        private void OnEnable() => StartCoroutine(ReportLoop());

        private IEnumerator ReportLoop()
        {
            var wait = new WaitForSeconds(Mathf.Max(0.5f, interval));
            while (true)
            {
                yield return wait;
                Report();
            }
        }

        public void Report()
        {
            if (connection == null || connection.State != ConnectionState.Connected) return;
            var head = anchors != null ? anchors.FallbackHead() : (Camera.main != null ? Camera.main.transform : null);
            if (head == null) return;

            var scene = new ClientScene
            {
                Head = new PosePayload { Position = head.position.ToArray(), Rotation = head.rotation.ToArray() },
            };

            if (provider != null)
            {
                scene.Surfaces = provider.GetSurfaces();
                scene.Anchors = provider.GetAnchors();
            }

            connection.Send(MessageTypes.ClientScene, scene);
        }
    }
}
