// Gaze + pinch selection: an index-finger pinch (OVRHand) selects whatever the user is gazing at
// (via GazeSelector → client.interaction tap). Compiled only with the Meta XR Core SDK.
#if HAS_META_CORE
using UnityEngine;
using JarvisVR.Interaction;

namespace JarvisVR.Meta
{
    public class GazePinchInteractor : MonoBehaviour
    {
        public OVRHand leftHand;
        public OVRHand rightHand;
        public GazeSelector selector;
        [Range(0f, 1f)] public float pinchThreshold = 0.7f;

        private bool _leftPinched;
        private bool _rightPinched;

        private void Awake()
        {
            if (selector == null) selector = FindObjectOfType<GazeSelector>();
        }

        private void Update()
        {
            CheckHand(rightHand, ref _rightPinched, "right");
            CheckHand(leftHand, ref _leftPinched, "left");
        }

        private void CheckHand(OVRHand hand, ref bool was, string label)
        {
            if (hand == null || !hand.IsTracked) { was = false; return; }
            bool now = hand.GetFingerIsPinching(OVRHand.HandFinger.Index)
                       || hand.GetFingerPinchStrength(OVRHand.HandFinger.Index) >= pinchThreshold;
            if (now && !was) selector?.SelectCurrent(label); // rising edge = a "click"
            was = now;
        }
    }
}
#endif
