using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using JarvisVR.Net;
using JarvisVR.Protocol;
using JarvisVR.Interaction;
using JarvisVR.Holograms.Widgets;
using JarvisVR.Util;

namespace JarvisVR.Holograms
{
    /// <summary>
    /// Owns the lifecycle of holographic objects. Subscribes to <c>holo.spawn/update/destroy/layout</c>
    /// (docs/PROTOCOL.md §5.7–5.10), instantiates a prefab (from <see cref="WidgetRegistry"/>) or a
    /// procedural widget (from <see cref="WidgetCatalog"/>), applies the protocol transform/anchor,
    /// and replies with <c>client.ack</c> for spawns.
    /// </summary>
    [DisallowMultipleComponent]
    public class HologramManager : MonoBehaviour
    {
        public JarvisConnection connection;
        public AnchorService anchors;
        public WidgetRegistry registry;
        public InteractionRelay relay;

        public InteractionRelay Relay => relay;
        public AnchorService Anchors => anchors;
        public int Count => _objects.Count;
        public IEnumerable<HoloWidget> All => _objects.Values;

        private readonly Dictionary<string, HoloWidget> _objects = new Dictionary<string, HoloWidget>();

        private void Awake()
        {
            if (connection == null) connection = FindObjectOfType<JarvisConnection>();
            if (anchors == null) anchors = FindObjectOfType<AnchorService>();
            if (relay == null) relay = FindObjectOfType<InteractionRelay>();
        }

        private void OnEnable()
        {
            if (connection == null) return;
            connection.Router.On(MessageTypes.HoloSpawn, HandleSpawn);
            connection.Router.On(MessageTypes.HoloUpdate, HandleUpdate);
            connection.Router.On(MessageTypes.HoloDestroy, HandleDestroy);
            connection.Router.On(MessageTypes.HoloLayout, HandleLayout);
        }

        private void OnDisable()
        {
            if (connection == null) return;
            connection.Router.Off(MessageTypes.HoloSpawn, HandleSpawn);
            connection.Router.Off(MessageTypes.HoloUpdate, HandleUpdate);
            connection.Router.Off(MessageTypes.HoloDestroy, HandleDestroy);
            connection.Router.Off(MessageTypes.HoloLayout, HandleLayout);
        }

        // ---- message handlers ---------------------------------------------------------------

        private void HandleSpawn(Envelope env)
        {
            var obj = env.PayloadAs<HologramObject>();
            if (obj == null || string.IsNullOrEmpty(obj.ObjectId))
            {
                connection.SendError(ErrorCodes.BadEnvelope, "holo.spawn missing object_id");
                return;
            }
            Spawn(obj);
            connection.Ack(env.Id); // client.ack, reply_to = the spawn command id
        }

        private void HandleUpdate(Envelope env)
        {
            var patch = env.PayloadAs<HoloUpdate>();
            if (patch == null || string.IsNullOrEmpty(patch.ObjectId)) return;
            if (!_objects.TryGetValue(patch.ObjectId, out var widget) || widget == null) return;
            if (patch.Transform != null) ApplyTransform(widget.transform, patch.Transform, isSpawn: false);
            if (patch.Props != null) widget.PatchProps(patch.Props);
        }

        private void HandleDestroy(Envelope env)
        {
            var d = env.PayloadAs<HoloDestroy>();
            if (d == null || string.IsNullOrEmpty(d.ObjectId)) return;
            if (!_objects.TryGetValue(d.ObjectId, out var widget) || widget == null) return;
            _objects.Remove(d.ObjectId);
            StartCoroutine(FadeAndDestroy(widget.gameObject, Mathf.Max(0, d.FadeMs) / 1000f));
        }

        private void HandleLayout(Envelope env)
        {
            var layout = env.PayloadAs<HoloLayout>();
            if (layout == null || layout.Objects == null) return;
            var anchorT = anchors != null ? anchors.Resolve(layout.Anchor) : null;
            var list = new List<HoloWidget>();
            foreach (var id in layout.Objects)
                if (_objects.TryGetValue(id, out var w) && w != null) list.Add(w);
            LayoutArranger.Arrange(layout.Arrangement, list, anchorT, layout.Spacing);
        }

        // ---- spawn / instantiate ------------------------------------------------------------

        public HoloWidget Spawn(HologramObject obj)
        {
            // Re-spawn of an existing id behaves like an update.
            if (_objects.TryGetValue(obj.ObjectId, out var existing) && existing != null)
            {
                if (obj.Transform != null) ApplyTransform(existing.transform, obj.Transform, isSpawn: false);
                if (obj.Props != null) existing.PatchProps(obj.Props);
                return existing;
            }

            GameObject instance;
            HoloWidget widget;

            var prefab = registry != null ? registry.GetPrefab(obj.WidgetType) : null;
            if (prefab != null)
            {
                instance = Instantiate(prefab);
                widget = instance.GetComponent<HoloWidget>();
                if (widget == null) widget = instance.AddComponent<PanelWidget>();
            }
            else if (WidgetCatalog.TryResolve(obj.WidgetType, out var type))
            {
                instance = new GameObject();
                widget = (HoloWidget)instance.AddComponent(type);
            }
            else
            {
                // widget_type not in registry/catalog: report and show a labelled placeholder.
                connection?.SendError(ErrorCodes.UnknownWidget, $"widget_type '{obj.WidgetType}' not in registry");
                instance = new GameObject();
                widget = instance.AddComponent<PanelWidget>();
            }

            instance.name = $"holo:{obj.WidgetType}:{ShortId(obj.ObjectId)}";

            // Apply transform before init so widgets that read scale, etc. see final values.
            ApplyTransform(widget.transform, obj.Transform, isSpawn: true);
            widget.Initialize(this, obj);
            ConfigureInteraction(widget, obj);

            _objects[obj.ObjectId] = widget;

            if (obj.TtlMs.HasValue && obj.TtlMs.Value > 0)
                StartCoroutine(ExpireAfter(obj.ObjectId, obj.TtlMs.Value / 1000f));

            return widget;
        }

        // ---- transform / anchor -------------------------------------------------------------

        private void ApplyTransform(Transform t, HoloTransform ht, bool isSpawn)
        {
            if (ht == null)
            {
                if (isSpawn) PlaceDefault(t);
                return;
            }

            if (!string.IsNullOrEmpty(ht.Anchor))
            {
                var parent = anchors != null ? anchors.Resolve(ht.Anchor) : null;
                t.SetParent(parent, worldPositionStays: false);
            }

            if (ht.Position != null) t.localPosition = ht.Position.ToVector3(t.localPosition);
            if (ht.Rotation != null) t.localRotation = ht.Rotation.ToQuaternion();
            if (ht.Scale != null) t.localScale = ht.Scale.ToVector3(isSpawn ? Vector3.one : t.localScale);

            if (ht.Billboard.HasValue)
            {
                var bb = t.GetComponent<Billboard>();
                if (ht.Billboard.Value)
                {
                    if (bb == null) bb = t.gameObject.AddComponent<Billboard>();
                    bb.enabled = true;
                    bb.target = anchors != null ? anchors.FallbackHead() : null;
                }
                else if (bb != null)
                {
                    bb.enabled = false;
                }
            }
        }

        private void PlaceDefault(Transform t)
        {
            // No transform supplied: float ~1m in front of the head at eye-ish height.
            var head = anchors != null ? anchors.FallbackHead() : (Camera.main != null ? Camera.main.transform : null);
            if (head != null) t.position = head.position + head.forward * 1.0f;
            else t.position = new Vector3(0f, 1.4f, 1.0f);
        }

        private void ConfigureInteraction(HoloWidget widget, HologramObject obj)
        {
            if (relay == null) return;
            bool interactable = obj.Interactable ?? true;
            var hi = widget.GetComponent<HoloInteractable>();
            if (interactable)
            {
                if (hi == null) hi = widget.gameObject.AddComponent<HoloInteractable>();
                hi.enabled = true;
                hi.Configure(widget, relay, obj.Interactions);
            }
            else if (hi != null)
            {
                hi.enabled = false;
            }
        }

        // ---- destroy / expire ---------------------------------------------------------------

        private IEnumerator ExpireAfter(string objectId, float seconds)
        {
            yield return new WaitForSeconds(seconds);
            if (_objects.TryGetValue(objectId, out var w) && w != null)
            {
                _objects.Remove(objectId);
                StartCoroutine(FadeAndDestroy(w.gameObject, 0.3f));
            }
        }

        private IEnumerator FadeAndDestroy(GameObject go, float seconds)
        {
            if (go != null && seconds > 0f)
            {
                var renderers = go.GetComponentsInChildren<Renderer>();
                float elapsed = 0f;
                while (elapsed < seconds && go != null)
                {
                    elapsed += Time.deltaTime;
                    float a = Mathf.Clamp01(1f - elapsed / seconds);
                    foreach (var r in renderers)
                    {
                        if (r == null) continue;
                        foreach (var m in r.materials)
                        {
                            var c = HoloMaterials.GetAlbedo(m, Color.white);
                            c.a = a;
                            HoloMaterials.SetAlbedo(m, c);
                        }
                    }
                    yield return null;
                }
            }
            if (go != null) Destroy(go);
        }

        public bool TryGet(string objectId, out HoloWidget widget) => _objects.TryGetValue(objectId, out widget);

        public void DestroyAll()
        {
            foreach (var w in _objects.Values)
                if (w != null) Destroy(w.gameObject);
            _objects.Clear();
        }

        private static string ShortId(string id)
            => string.IsNullOrEmpty(id) ? "?" : id.Substring(0, System.Math.Min(8, id.Length));
    }
}
