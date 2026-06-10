using System.Collections.Generic;
using UnityEngine;
using Newtonsoft.Json.Linq;
using JarvisVR.Holograms;
using JarvisVR.Protocol;

namespace JarvisVR.Interaction
{
    /// <summary>
    /// Attached to every interactable hologram by the <see cref="HologramManager"/>. Exposes a
    /// small, input-source-agnostic surface (Tap/Grab/Drag/Slider/Toggle/Resize/Dwell) that any
    /// input backend can call:
    ///   • Meta Interaction SDK (poke/grab) via JarvisVR.Meta.MetaInteractionBridge,
    ///   • controllers (OVRInput) via the Meta bridge, or
    ///   • the in-editor mouse tester (Interaction/MouseInteractionTester).
    /// Each call is filtered against the per-object allowed interaction set and forwarded to the
    /// <see cref="InteractionRelay"/> as a <c>client.interaction</c> message.
    /// </summary>
    [DisallowMultipleComponent]
    public class HoloInteractable : MonoBehaviour
    {
        public HoloWidget Widget { get; private set; }

        private InteractionRelay _relay;
        private HashSet<string> _allowed;
        private bool _grabbed;

        public void Configure(HoloWidget widget, InteractionRelay relay, string[] interactions)
        {
            Widget = widget;
            _relay = relay;
            _allowed = new HashSet<string>(interactions ?? System.Array.Empty<string>());
            EnsureCollider();
        }

        /// <summary>If no allowed set was provided, all actions are permitted.</summary>
        public bool Allows(string action) => _allowed == null || _allowed.Count == 0 || _allowed.Contains(action);

        private void EnsureCollider()
        {
            if (GetComponent<Collider>() != null || GetComponentInChildren<Collider>() != null) return;
            var bc = gameObject.AddComponent<BoxCollider>();
            bc.size = Vector3.one * 0.2f;
            bc.isTrigger = false;
        }

        // ---- input entry points -------------------------------------------------------------

        public void Tap(string element = null, string hand = null)
        {
            if (Allows(InteractionActions.Tap)) Emit(InteractionActions.Tap, element, null, hand);
        }

        public void GrabBegin(string hand = null)
        {
            if (!Allows(InteractionActions.Grab)) return;
            _grabbed = true;
            Emit(InteractionActions.Grab, null, null, hand);
        }

        public void GrabEnd(string hand = null)
        {
            if (!_grabbed) return;
            _grabbed = false;
            Emit(InteractionActions.Release, null, PositionValue(transform.position), hand);
        }

        public void Drag(Vector3 worldPosition, string hand = null)
        {
            if (!Allows(InteractionActions.Drag)) return;
            transform.position = worldPosition; // local feedback; server is authoritative
            Emit(InteractionActions.Drag, null, PositionValue(worldPosition), hand);
        }

        public void Slider(float value01, string element = null, string hand = null)
        {
            if (Allows(InteractionActions.Slider))
                Emit(InteractionActions.Slider, element, new JObject { ["slider"] = Mathf.Clamp01(value01) }, hand);
        }

        public void Toggle(bool on, string element = null, string hand = null)
        {
            if (Allows(InteractionActions.Toggle))
                Emit(InteractionActions.Toggle, element, new JObject { ["on"] = on }, hand);
        }

        public void Resize(float scale, string hand = null)
        {
            if (!Allows(InteractionActions.Resize)) return;
            transform.localScale = Vector3.one * Mathf.Max(0.05f, scale);
            Emit(InteractionActions.Resize, null, new JObject { ["scale"] = scale }, hand);
        }

        public void Dwell(string element = null, string hand = null)
        {
            if (Allows(InteractionActions.Dwell)) Emit(InteractionActions.Dwell, element, null, hand);
        }

        private static JObject PositionValue(Vector3 v) => new JObject { ["position"] = new JArray(v.x, v.y, v.z) };

        private void Emit(string action, string element, JObject value, string hand)
        {
            if (Widget == null || _relay == null) return;
            _relay.Emit(Widget.ObjectId, Widget.WidgetType, action, element, value, hand);
        }
    }
}
