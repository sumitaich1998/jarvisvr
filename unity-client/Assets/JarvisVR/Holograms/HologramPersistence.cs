using System.Collections.Generic;
using UnityEngine;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;
using JarvisVR.Protocol;
using JarvisVR.Util;

namespace JarvisVR.Holograms
{
    /// <summary>
    /// Optional precise world-anchor backend (Meta Spatial Anchors). Implemented by
    /// JarvisVR.Meta.MetaSpatialAnchorBinder when enabled; otherwise placements persist as world
    /// poses in PlayerPrefs.
    /// </summary>
    public interface IAnchorStore
    {
        void Save(string key, Vector3 position, Quaternion rotation);
        bool TryLoad(string key, out Vector3 position, out Quaternion rotation);
        void Erase(string key);
    }

    /// <summary>
    /// Saves/restores the user's hologram layout across sessions (FEATURES §3/§5 "home space" /
    /// session persistence). Stores each hologram's widget_type, world pose and props in PlayerPrefs;
    /// if an <see cref="IAnchorStore"/> (Meta Spatial Anchors) is present, the saved pose is upgraded
    /// to a re-localizable spatial anchor for drift-free placement.
    /// </summary>
    [DisallowMultipleComponent]
    public class HologramPersistence : MonoBehaviour
    {
        public HologramManager manager;
        public string layoutKey = "default";
        public IAnchorStore anchorStore; // optional (Meta)

        private const string PrefPrefix = "jarvis.layout.";

        private class Entry
        {
            public string id;
            public string widget_type;
            public float[] pos;
            public float[] rot;
            public float[] scale;
            public string props; // serialized JObject
        }

        private class Layout { public List<Entry> items = new List<Entry>(); }

        private void Awake()
        {
            if (manager == null) manager = FindObjectOfType<HologramManager>();
        }

        public void SaveLayout()
        {
            if (manager == null) return;
            var layout = new Layout();
            foreach (var w in manager.All)
            {
                if (w == null) continue;
                var snap = w.Snapshot();
                layout.items.Add(new Entry
                {
                    id = snap.ObjectId,
                    widget_type = snap.WidgetType,
                    pos = snap.Transform.Position,
                    rot = snap.Transform.Rotation,
                    scale = snap.Transform.Scale,
                    props = snap.Props != null ? snap.Props.ToString(Formatting.None) : null,
                });
                anchorStore?.Save(snap.ObjectId, snap.Transform.Position.ToVector3(), snap.Transform.Rotation.ToQuaternion());
            }
            PlayerPrefs.SetString(PrefPrefix + layoutKey, JsonConvert.SerializeObject(layout));
            PlayerPrefs.Save();
            Debug.Log($"[Jarvis] saved layout '{layoutKey}' ({layout.items.Count} holograms).");
        }

        /// <summary>Recreate the saved layout locally (offline-capable). Returns count restored.</summary>
        public int RestoreLayout()
        {
            if (manager == null) return 0;
            string json = PlayerPrefs.GetString(PrefPrefix + layoutKey, null);
            if (string.IsNullOrEmpty(json)) return 0;

            Layout layout;
            try { layout = JsonConvert.DeserializeObject<Layout>(json); }
            catch { return 0; }
            if (layout?.items == null) return 0;

            int n = 0;
            foreach (var e in layout.items)
            {
                Vector3 pos = e.pos.ToVector3();
                Quaternion rot = e.rot.ToQuaternion();
                if (anchorStore != null && anchorStore.TryLoad(e.id, out var ap, out var ar)) { pos = ap; rot = ar; }

                var obj = new HologramObject
                {
                    ObjectId = e.id,
                    WidgetType = e.widget_type,
                    Transform = new HoloTransform
                    {
                        Anchor = Anchors.World,
                        Position = pos.ToArray(),
                        Rotation = rot.ToArray(),
                        Scale = e.scale,
                    },
                    Props = string.IsNullOrEmpty(e.props) ? null : SafeParse(e.props),
                    Interactable = true,
                };
                manager.Spawn(obj);
                n++;
            }
            Debug.Log($"[Jarvis] restored layout '{layoutKey}' ({n} holograms).");
            return n;
        }

        public void ClearLayout()
        {
            PlayerPrefs.DeleteKey(PrefPrefix + layoutKey);
            PlayerPrefs.Save();
        }

        private static JObject SafeParse(string s)
        {
            try { return JObject.Parse(s); } catch { return null; }
        }
    }
}
