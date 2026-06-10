using UnityEngine;

namespace JarvisVR.Holograms
{
    /// <summary>
    /// "Lazy follow" body-lock: the hologram trails the user, easing to a spot in front of the head
    /// only when they move/turn beyond a deadzone (so it doesn't jitter). One of the UX placement
    /// modes (world-lock = none, follow = this, billboard = <see cref="Billboard"/>). Add/remove via
    /// <see cref="WidgetModes"/>.
    /// </summary>
    public class LazyFollow : MonoBehaviour
    {
        public Transform target;          // head
        public float distance = 0.8f;
        public float height = -0.1f;
        public float lerp = 3f;
        [Tooltip("Don't reposition until the target spot drifts more than this (meters).")]
        public float deadzone = 0.15f;

        private void Start()
        {
            if (target == null && Camera.main != null) target = Camera.main.transform;
        }

        private void LateUpdate()
        {
            if (target == null) return;
            Vector3 desired = target.position + target.forward * distance + Vector3.up * height;
            if (Vector3.Distance(transform.position, desired) > deadzone)
                transform.position = Vector3.Lerp(transform.position, desired, Time.deltaTime * lerp);

            Vector3 look = transform.position - target.position;
            if (look.sqrMagnitude > 1e-5f)
                transform.rotation = Quaternion.Slerp(transform.rotation, Quaternion.LookRotation(look), Time.deltaTime * lerp);
        }
    }

    /// <summary>Helpers to switch a hologram between world-lock / follow / billboard placement modes.</summary>
    public static class WidgetModes
    {
        public static void SetFollow(Component widget, Transform head, bool on)
        {
            var lf = widget.GetComponent<LazyFollow>();
            if (on) { if (lf == null) lf = widget.gameObject.AddComponent<LazyFollow>(); lf.target = head; lf.enabled = true; }
            else if (lf != null) lf.enabled = false;
        }

        public static void SetBillboard(Component widget, Transform head, bool on)
        {
            var bb = widget.GetComponent<Billboard>();
            if (on) { if (bb == null) bb = widget.gameObject.AddComponent<Billboard>(); bb.target = head; bb.enabled = true; }
            else if (bb != null) bb.enabled = false;
        }

        /// <summary>World-lock: stop following so the hologram stays put in the room.</summary>
        public static void SetWorldLock(Component widget)
        {
            var lf = widget.GetComponent<LazyFollow>();
            if (lf != null) lf.enabled = false;
        }
    }
}
