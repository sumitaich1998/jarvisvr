#if ENABLE_LEGACY_INPUT_MANAGER
using UnityEngine;

namespace JarvisVR.Interaction
{
    /// <summary>
    /// Editor/desktop convenience: left-click raycasts from the main camera and fires a Tap on the
    /// nearest <see cref="HoloInteractable"/>. Lets you exercise the protocol against the infra/
    /// mock backend without a headset. Only compiled when the legacy Input Manager is enabled
    /// (Project Settings &gt; Player &gt; Active Input Handling = "Both" or "Input Manager (Old)").
    /// On-device input comes from the Meta bridge instead.
    /// </summary>
    public class MouseInteractionTester : MonoBehaviour
    {
        public Camera sourceCamera;
        public float maxDistance = 20f;

        private void Awake()
        {
            if (sourceCamera == null) sourceCamera = Camera.main;
        }

        private void Update()
        {
            if (!Input.GetMouseButtonDown(0)) return;
            var cam = sourceCamera != null ? sourceCamera : Camera.main;
            if (cam == null) return;

            Ray ray = cam.ScreenPointToRay(Input.mousePosition);
            if (!Physics.Raycast(ray, out var hit, maxDistance)) return;

            var interactable = hit.collider.GetComponentInParent<HoloInteractable>();
            if (interactable != null)
            {
                // Report a sub-element name only when a named child collider was hit.
                string element = hit.collider.gameObject == interactable.gameObject
                    ? null : hit.collider.gameObject.name;
                interactable.Tap(element, "right");
            }
        }
    }
}
#endif
