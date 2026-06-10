using UnityEngine;
using JarvisVR.Protocol;
using JarvisVR.Holograms;
using JarvisVR.Perception;

namespace JarvisVR.Interaction
{
    /// <summary>
    /// Gaze + pinch/voice selection (FEATURES §3 multimodal interaction). Tracks the gazed hologram
    /// via <see cref="GazeProvider"/> and taps it when triggered:
    ///   • a Meta hand pinch (JarvisVR.Meta.GazePinchInteractor calls <see cref="SelectCurrent"/>),
    ///   • a voice command routed by the agent, or
    ///   • optional gaze dwell (accessibility; off by default).
    /// Emits a normal <c>client.interaction</c> tap so widgets/back-end treat it uniformly.
    /// </summary>
    [DisallowMultipleComponent]
    public class GazeSelector : MonoBehaviour
    {
        public GazeProvider gaze;
        public InteractionRelay relay;
        [Tooltip("Auto-select after gaze dwell (accessibility). Off by default to avoid 'Midas touch'.")]
        public bool dwellSelect = false;

        private void Awake()
        {
            if (gaze == null) gaze = FindObjectOfType<GazeProvider>();
            if (relay == null) relay = FindObjectOfType<InteractionRelay>();
        }

        private void OnEnable() { if (gaze != null) gaze.OnDwell += OnDwell; }
        private void OnDisable() { if (gaze != null) gaze.OnDwell -= OnDwell; }

        private void OnDwell(HoloWidget w) { if (dwellSelect) Select(w, "gaze"); }

        /// <summary>Select whatever the user is currently gazing at (called by pinch/voice).</summary>
        public void SelectCurrent(string hand) => Select(gaze != null ? gaze.CurrentHitWidget : null, hand);

        private void Select(HoloWidget w, string hand)
        {
            if (w == null || relay == null) return;
            relay.Emit(w.ObjectId, w.WidgetType, InteractionActions.Tap, null, null, hand);
        }
    }
}
