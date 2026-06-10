using Newtonsoft.Json;
using Newtonsoft.Json.Linq;

namespace JarvisVR.Protocol
{
    /// <summary>
    /// Spatial transform of a hologram (docs/PROTOCOL.md §5.6). All numeric arrays use the
    /// repo convention: right-handed meters, Unity Y-up. position=[x,y,z], rotation quaternion
    /// [x,y,z,w], scale=[x,y,z]. Every field is optional so the same type works for
    /// <c>holo.update</c> partial patches (omit unchanged keys).
    /// </summary>
    public class HoloTransform
    {
        // world | head | hand_left | hand_right | surface  (see Anchors)
        [JsonProperty("anchor", NullValueHandling = NullValueHandling.Ignore)]
        public string Anchor;

        [JsonProperty("position", NullValueHandling = NullValueHandling.Ignore)]
        public float[] Position;

        [JsonProperty("rotation", NullValueHandling = NullValueHandling.Ignore)]
        public float[] Rotation;

        [JsonProperty("scale", NullValueHandling = NullValueHandling.Ignore)]
        public float[] Scale;

        // If true, always face the user.
        [JsonProperty("billboard", NullValueHandling = NullValueHandling.Ignore)]
        public bool? Billboard;
    }

    /// <summary>
    /// The Holographic Object (docs/PROTOCOL.md §5.6). Used as the payload of <c>holo.spawn</c>
    /// and as the shape patched by <c>holo.update</c>.
    /// </summary>
    public class HologramObject
    {
        [JsonProperty("object_id")]
        public string ObjectId;

        // Must exist in holo-tools/registry.json (validated client-side against the registry/catalog).
        [JsonProperty("widget_type")]
        public string WidgetType;

        [JsonProperty("transform", NullValueHandling = NullValueHandling.Ignore)]
        public HoloTransform Transform;

        // Widget-specific; validated against the holo-tools schema. Kept raw for forward-compat.
        [JsonProperty("props", NullValueHandling = NullValueHandling.Ignore)]
        public JObject Props;

        [JsonProperty("interactable", NullValueHandling = NullValueHandling.Ignore)]
        public bool? Interactable;

        // Subset of the widget's supported interaction set.
        [JsonProperty("interactions", NullValueHandling = NullValueHandling.Ignore)]
        public string[] Interactions;

        // 0 = persists until destroyed.
        [JsonProperty("ttl_ms", NullValueHandling = NullValueHandling.Ignore)]
        public long? TtlMs;
    }
}
