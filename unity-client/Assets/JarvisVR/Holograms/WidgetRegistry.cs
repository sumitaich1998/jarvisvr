using System;
using System.Collections.Generic;
using UnityEngine;

namespace JarvisVR.Holograms
{
    /// <summary>
    /// Serializable mapping of <c>widget_type</c> → prefab (Create &gt; JarvisVR &gt; Widget Registry).
    /// This is the client's view of holo-tools/registry.json: drop a custom prefab here to override
    /// the procedural default for a widget type. Prefabs should have a <see cref="HoloWidget"/>
    /// (or subclass) on the root. If a type has no prefab, the manager falls back to the built-in
    /// procedural widget from <see cref="WidgetCatalog"/>.
    /// </summary>
    [CreateAssetMenu(fileName = "WidgetRegistry", menuName = "JarvisVR/Widget Registry", order = 1)]
    public class WidgetRegistry : ScriptableObject
    {
        [Serializable]
        public class Entry
        {
            public string widgetType;
            public GameObject prefab;
        }

        public List<Entry> entries = new List<Entry>();

        private Dictionary<string, GameObject> _map;

        public GameObject GetPrefab(string widgetType)
        {
            if (string.IsNullOrEmpty(widgetType)) return null;
            if (_map == null)
            {
                _map = new Dictionary<string, GameObject>();
                foreach (var e in entries)
                    if (e != null && !string.IsNullOrEmpty(e.widgetType) && e.prefab != null)
                        _map[e.widgetType] = e.prefab;
            }
            return _map.TryGetValue(widgetType, out var p) ? p : null;
        }

        /// <summary>Call after editing <see cref="entries"/> at runtime to rebuild the lookup.</summary>
        public void Invalidate() => _map = null;
    }
}
