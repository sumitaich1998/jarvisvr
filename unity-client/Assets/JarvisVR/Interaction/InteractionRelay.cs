using UnityEngine;
using Newtonsoft.Json.Linq;
using JarvisVR.Net;
using JarvisVR.Protocol;

namespace JarvisVR.Interaction
{
    /// <summary>
    /// Central sink for hand/controller interactions on holograms. Builds
    /// <c>client.interaction</c> messages (docs/PROTOCOL.md §5.11) and sends them to the backend.
    /// Widgets/interactables call <see cref="Emit"/> (or the typed helpers) — they never touch the
    /// socket directly, so the same widget code works in-editor, with controllers, or with hands.
    /// </summary>
    [DisallowMultipleComponent]
    public class InteractionRelay : MonoBehaviour
    {
        public JarvisConnection connection;

        private void Awake()
        {
            if (connection == null) connection = FindObjectOfType<JarvisConnection>();
        }

        public void Emit(string objectId, string widgetType, string action,
                         string element = null, JObject value = null, string hand = null)
        {
            if (connection == null || string.IsNullOrEmpty(objectId) || string.IsNullOrEmpty(action)) return;
            var payload = new ClientInteraction
            {
                ObjectId = objectId,
                WidgetType = widgetType,
                Action = action,
                Element = element,
                Value = value,
                Hand = hand,
            };
            connection.Send(MessageTypes.ClientInteraction, payload);
        }

        // ---- typed convenience wrappers (value shapes follow §5.11 examples) ----

        public void Tap(string id, string type, string element = null, string hand = null)
            => Emit(id, type, InteractionActions.Tap, element, null, hand);

        public void Grab(string id, string type, string hand = null)
            => Emit(id, type, InteractionActions.Grab, null, null, hand);

        public void Release(string id, string type, Vector3 position, string hand = null)
            => Emit(id, type, InteractionActions.Release, null, Vec(position), hand);

        public void Drag(string id, string type, Vector3 position, string hand = null)
            => Emit(id, type, InteractionActions.Drag, null, Vec(position), hand);

        public void Slider(string id, string type, float value01, string element = null, string hand = null)
            => Emit(id, type, InteractionActions.Slider, element, new JObject { ["slider"] = Mathf.Clamp01(value01) }, hand);

        public void Toggle(string id, string type, bool on, string element = null, string hand = null)
            => Emit(id, type, InteractionActions.Toggle, element, new JObject { ["on"] = on }, hand);

        public void Resize(string id, string type, float scale, string hand = null)
            => Emit(id, type, InteractionActions.Resize, null, new JObject { ["scale"] = scale }, hand);

        public void Dwell(string id, string type, string element = null, string hand = null)
            => Emit(id, type, InteractionActions.Dwell, element, null, hand);

        private static JObject Vec(Vector3 v) => new JObject { ["position"] = new JArray(v.x, v.y, v.z) };
    }
}
