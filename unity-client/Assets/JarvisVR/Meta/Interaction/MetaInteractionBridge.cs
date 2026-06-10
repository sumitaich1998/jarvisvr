// Bridges Meta Interaction SDK pointer events (poke / grab / ray) to a JarvisVR HoloInteractable.
// Add this alongside a HoloInteractable (e.g. on a custom widget prefab) and assign the
// PointableUnityEventWrapper that the Interaction SDK drives. This assembly only compiles when the
// Interaction SDK is present (asmdef defineConstraints: HAS_META_INTERACTION). The same
// HoloInteractable API is also driven by controllers / the editor tester, so widget code stays
// input-agnostic.
#if HAS_META_INTERACTION
using UnityEngine;
using Oculus.Interaction;
using JarvisVR.Interaction;

namespace JarvisVR.Meta
{
    [RequireComponent(typeof(HoloInteractable))]
    public class MetaInteractionBridge : MonoBehaviour
    {
        [Tooltip("Driven by the Interaction SDK (PokeInteractable / GrabInteractable / RayInteractable).")]
        public PointableUnityEventWrapper pointable;

        private HoloInteractable _target;

        private void Awake()
        {
            _target = GetComponent<HoloInteractable>();
        }

        private void OnEnable()
        {
            if (pointable == null) return;
            pointable.WhenSelect.AddListener(OnSelect);
            pointable.WhenUnselect.AddListener(OnUnselect);
            pointable.WhenMove.AddListener(OnMove);
        }

        private void OnDisable()
        {
            if (pointable == null) return;
            pointable.WhenSelect.RemoveListener(OnSelect);
            pointable.WhenUnselect.RemoveListener(OnUnselect);
            pointable.WhenMove.RemoveListener(OnMove);
        }

        private void OnSelect(PointerEvent evt)
        {
            // Treat a select as the start of a grab (no-op if the object isn't grabbable).
            _target?.GrabBegin(HandOf(evt));
        }

        private void OnUnselect(PointerEvent evt)
        {
            if (_target == null) return;
            // A select→unselect reads as a tap; also close any grab.
            _target.Tap(null, HandOf(evt));
            _target.GrabEnd(HandOf(evt));
        }

        private void OnMove(PointerEvent evt)
        {
            _target?.Drag(evt.Pose.position, HandOf(evt));
        }

        // Interaction SDK doesn't expose handedness directly on PointerEvent; left null unless a
        // project convention (e.g. interactor naming) is added.
        private static string HandOf(PointerEvent evt) => null;
    }
}
#endif
