using UnityEngine;
using TMPro;
using Newtonsoft.Json.Linq;
using JarvisVR.Protocol;
using JarvisVR.Util;

namespace JarvisVR.Holograms
{
    /// <summary>
    /// Base class for every hologram behaviour. The <see cref="HologramManager"/> instantiates a
    /// widget, applies the protocol transform, then calls <see cref="Initialize"/>. Subclasses
    /// build procedural visuals in <see cref="Build"/> (once) and react to props in
    /// <see cref="ApplyProps"/> (on spawn and on every <c>holo.update</c> patch).
    /// </summary>
    [DisallowMultipleComponent]
    public abstract class HoloWidget : MonoBehaviour
    {
        public string ObjectId { get; private set; }
        public string WidgetType { get; private set; }
        public string[] Interactions { get; private set; }
        public bool Interactable { get; private set; }

        protected JObject Props { get; private set; } = new JObject();
        protected HologramManager Manager { get; private set; }

        private bool _built;

        public void Initialize(HologramManager manager, HologramObject obj)
        {
            Manager = manager;
            ObjectId = obj.ObjectId;
            WidgetType = obj.WidgetType;
            Interactions = obj.Interactions ?? System.Array.Empty<string>();
            Interactable = obj.Interactable ?? true;
            Props = obj.Props ?? new JObject();

            if (!_built) { Build(); _built = true; }
            ApplyProps(Props);
        }

        /// <summary>Build procedural visuals once. Override in subclasses.</summary>
        protected virtual void Build() { }

        /// <summary>Apply/refresh visuals from the full current props. Override in subclasses.</summary>
        protected virtual void ApplyProps(JObject props) { }

        /// <summary>Merge a partial props patch (holo.update) and re-apply.</summary>
        public void PatchProps(JObject patch)
        {
            if (patch == null) return;
            Props ??= new JObject();
            Props.Merge(patch, new JsonMergeSettings
            {
                MergeArrayHandling = MergeArrayHandling.Replace,
                MergeNullValueHandling = MergeNullValueHandling.Merge,
            });
            ApplyProps(Props);
        }

        public void EmitInteraction(string action, string element = null, JObject value = null, string hand = null)
            => Manager?.Relay?.Emit(ObjectId, WidgetType, action, element, value, hand);

        /// <summary>Capture the widget's current world placement + content for persistence
        /// (HologramPersistence). Anchor is normalized to world space.</summary>
        public HologramObject Snapshot() => new HologramObject
        {
            ObjectId = ObjectId,
            WidgetType = WidgetType,
            Transform = new HoloTransform
            {
                Anchor = Anchors.World,
                Position = transform.position.ToArray(),
                Rotation = transform.rotation.ToArray(),
                Scale = transform.localScale.ToArray(),
            },
            Props = Props,
            Interactable = Interactable,
            Interactions = Interactions,
        };

        // ---- prop readers (tolerant of missing keys / wrong types) --------------------------

        protected bool Has(string key) => Props != null && Props.TryGetValue(key, out var v) && v.Type != JTokenType.Null;

        protected string GetString(string key, string def = "")
            => Props != null && Props.TryGetValue(key, out var v) && v.Type != JTokenType.Null ? v.ToString() : def;

        protected float GetFloat(string key, float def = 0f)
            => Props != null && Props.TryGetValue(key, out var v) && (v.Type == JTokenType.Float || v.Type == JTokenType.Integer)
               ? v.Value<float>() : def;

        protected int GetInt(string key, int def = 0)
            => Props != null && Props.TryGetValue(key, out var v) && (v.Type == JTokenType.Integer || v.Type == JTokenType.Float)
               ? v.Value<int>() : def;

        protected bool GetBool(string key, bool def = false)
            => Props != null && Props.TryGetValue(key, out var v) && v.Type == JTokenType.Boolean ? v.Value<bool>() : def;

        protected JArray GetArray(string key)
            => Props != null && Props.TryGetValue(key, out var v) && v is JArray a ? a : null;

        protected JObject GetObject(string key)
            => Props != null && Props.TryGetValue(key, out var v) && v is JObject o ? o : null;

        protected Color GetColor(string key, Color def)
            => ColorUtil.Parse(GetString(key, null), def);

        // ---- procedural visual helpers ------------------------------------------------------

        protected Transform CreatePrimitive(PrimitiveType type, string name, Vector3 localPos,
            Vector3 localScale, Color color, Transform parent = null, bool keepCollider = false)
        {
            var go = GameObject.CreatePrimitive(type);
            go.name = name;
            if (!keepCollider)
            {
                var col = go.GetComponent<Collider>();
                if (col != null) Destroy(col);
            }
            var t = go.transform;
            t.SetParent(parent != null ? parent : transform, false);
            t.localPosition = localPos;
            t.localScale = localScale;
            var r = go.GetComponent<Renderer>();
            if (r != null) r.material = HoloMaterials.Solid(color);
            return t;
        }

        protected TextMeshPro CreateText(string name, string text, float fontSize, Color color,
            Vector3 localPos, Transform parent = null, TextAlignmentOptions align = TextAlignmentOptions.Center,
            Vector2 size = default)
        {
            var go = new GameObject(name);
            go.transform.SetParent(parent != null ? parent : transform, false);
            go.transform.localPosition = localPos;
            var tmp = go.AddComponent<TextMeshPro>();
            tmp.text = text ?? string.Empty;
            tmp.fontSize = fontSize;
            tmp.color = color;
            tmp.alignment = align;
            tmp.enableWordWrapping = true;
            tmp.rectTransform.sizeDelta = size == default ? new Vector2(0.5f, 0.25f) : size;
            return tmp;
        }

        protected static void SetColor(Transform t, Color color)
        {
            if (t == null) return;
            var r = t.GetComponent<Renderer>();
            if (r != null) HoloMaterials.SetAlbedo(r.material, color);
        }
    }
}
