using System.Collections.Generic;
using UnityEngine;
using JarvisVR.Net;

namespace JarvisVR.Tests.PlayMode
{
    /// <summary>Shared helpers for PlayMode wiring tests: spin up a JarvisConnection that has a live
    /// Router but never opens a socket (autoConnectOnStart=false), so we can drive controllers by
    /// routing envelopes directly.</summary>
    internal static class PlayModeTestUtil
    {
        public static JarvisConnection NewConnection(List<Object> track)
        {
            var go = new GameObject("conn");
            go.SetActive(false);                 // defer Awake/Start until configured
            var conn = go.AddComponent<JarvisConnection>();
            var cfg = ScriptableObject.CreateInstance<JarvisConfig>();
            conn.Config = cfg;
            conn.autoConnectOnStart = false;     // no real WebSocket
            go.SetActive(true);
            track.Add(go);
            track.Add(cfg);
            return conn;
        }

        public static T NewComponent<T>(string name, List<Object> track) where T : Component
        {
            var go = new GameObject(name);
            var c = go.AddComponent<T>();
            track.Add(go);
            return c;
        }

        public static void Cleanup(List<Object> track)
        {
            foreach (var o in track) if (o != null) Object.Destroy(o);
            track.Clear();
        }
    }
}
