using System;
using UnityEngine;
using JarvisVR.Net;
using JarvisVR.Protocol;
using JarvisVR.Holograms;
using JarvisVR.Util;

namespace JarvisVR.Perception
{
    /// <summary>
    /// Optional eye-gaze source (Meta OVREyeGaze). Implemented by JarvisVR.Meta when present + the
    /// eye-tracking permission is granted; otherwise <see cref="GazeProvider"/> falls back to a head ray.
    /// </summary>
    public interface IGazeSource
    {
        bool IsAvailable { get; }
        bool TryGetRay(out Vector3 origin, out Vector3 direction);
    }

    /// <summary>
    /// Emits <c>perception.gaze</c> (§8.4) at ~5–10 Hz: eye ray when available, else head ray. Raycasts
    /// holograms to fill <c>hit_object_id</c>/<c>hit_point</c> and accumulates dwell. Exposes the current
    /// gaze target so gaze+pinch/voice selection can use it. Pull-based: only runs while active.
    /// </summary>
    [DisallowMultipleComponent]
    public class GazeProvider : MonoBehaviour
    {
        public JarvisConfig config;
        public JarvisConnection connection;
        public AnchorService anchors;
        public IGazeSource eyeSource;   // optional (Meta)

        public bool Active { get; private set; }
        public string CurrentHitObjectId { get; private set; }
        public HoloWidget CurrentHitWidget { get; private set; }
        public event Action<HoloWidget> OnDwell;

        private float _accum;
        private string _lastHit;
        private float _dwellStart;
        private bool _dwellFired;

        private void Awake()
        {
            if (connection == null) connection = FindObjectOfType<JarvisConnection>();
            if (anchors == null) anchors = FindObjectOfType<AnchorService>();
        }

        public void StartStream() { Active = true; }
        public void StopStream() { Active = false; CurrentHitObjectId = null; CurrentHitWidget = null; }

        public bool UsingEyes => eyeSource != null && eyeSource.IsAvailable
                                 && config != null && config.capEyeTracking;

        private void Update()
        {
            if (!Active) return;
            float hz = config != null ? Mathf.Clamp(config.gazeHz, 1f, 20f) : 8f;
            _accum += Time.deltaTime;
            if (_accum < 1f / hz) return;
            _accum = 0f;
            Sample();
        }

        private void Sample()
        {
            if (!ResolveRay(out var origin, out var dir, out bool eyes)) return;

            string hitId = null;
            Vector3? hitPoint = null;
            CurrentHitWidget = null;

            float maxDist = config != null ? config.gazeMaxDistance : 12f;
            if (Physics.Raycast(origin, dir, out var hit, maxDist))
            {
                var widget = hit.collider.GetComponentInParent<HoloWidget>();
                if (widget != null) { hitId = widget.ObjectId; CurrentHitWidget = widget; hitPoint = hit.point; }
            }
            CurrentHitObjectId = hitId;

            int dwellMs = UpdateDwell(hitId);

            var payload = new GazePayload
            {
                Source = eyes ? GazeSources.Eyes : GazeSources.Head,
                Origin = origin.ToArray(),
                Direction = dir.normalized.ToArray(),
                HitObjectId = hitId,
                HitPoint = hitPoint.HasValue ? hitPoint.Value.ToArray() : null,
                DwellMs = dwellMs,
            };
            connection?.Send(MessageTypes.PerceptionGaze, payload);
        }

        private int UpdateDwell(string hitId)
        {
            if (hitId != _lastHit)
            {
                _lastHit = hitId;
                _dwellStart = Time.time;
                _dwellFired = false;
                return 0;
            }
            if (string.IsNullOrEmpty(hitId)) return 0;

            int dwellMs = Mathf.RoundToInt((Time.time - _dwellStart) * 1000f);
            int threshold = config != null ? config.gazeDwellThresholdMs : 400;
            if (!_dwellFired && dwellMs >= threshold)
            {
                _dwellFired = true;
                if (CurrentHitWidget != null) OnDwell?.Invoke(CurrentHitWidget);
            }
            return dwellMs;
        }

        private bool ResolveRay(out Vector3 origin, out Vector3 direction, out bool eyes)
        {
            if (UsingEyes && eyeSource.TryGetRay(out origin, out direction))
            {
                eyes = true;
                return true;
            }
            eyes = false;
            var head = anchors != null ? anchors.FallbackHead() : (Camera.main != null ? Camera.main.transform : null);
            if (head == null) { origin = Vector3.zero; direction = Vector3.forward; return false; }
            origin = head.position;
            direction = head.forward;
            return true;
        }
    }
}
