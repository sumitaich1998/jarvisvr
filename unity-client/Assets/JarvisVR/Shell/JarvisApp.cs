using UnityEngine;
using JarvisVR.Net;
using JarvisVR.Holograms;
using JarvisVR.Interaction;
using JarvisVR.Audio;
using JarvisVR.Perception;

namespace JarvisVR.Shell
{
    /// <summary>
    /// One-stop bootstrap. Drop this on a GameObject in the Jarvis scene, assign a
    /// <see cref="JarvisConfig"/> (and optionally a <see cref="WidgetRegistry"/> and the rig's
    /// head/hand transforms), and it creates + wires every subsystem: connection, anchors,
    /// hologram manager, interaction relay, presence, scene reporter, and audio. Missing components
    /// are created as children; existing ones in the scene are reused.
    ///
    /// See Assets/JarvisVR/SETUP.md for the full scene recipe (passthrough, hand tracking, rig).
    /// </summary>
    [DefaultExecutionOrder(-100)]
    [DisallowMultipleComponent]
    public class JarvisApp : MonoBehaviour
    {
        [Header("Required")]
        public JarvisConfig config;

        [Header("Optional overrides")]
        public WidgetRegistry widgetRegistry;

        [Header("Rig transforms (auto: Camera.main / Meta rig binder)")]
        public Transform head;
        public Transform leftHand;
        public Transform rightHand;
        public Transform worldOrigin;

        [Header("Subsystems (auto-created if left empty)")]
        public JarvisConnection connection;
        public AnchorService anchors;
        public InteractionRelay relay;
        public HologramManager holograms;
        public JarvisPresence presence;
        public SceneReporter sceneReporter;
        public AudioChannel audioChannel;
        public MicStreamer mic;
        public SpeechPlayer speech;
        public SpatialMenu menu;

        [Header("Perception (v1.1) — auto-created if left empty")]
        public PassthroughCameraProvider cameraProvider;
        public VisionChannel visionChannel;
        public VisionStreamer visionStreamer;
        public AmbientAudioStreamer ambientAudio;
        public GazeProvider gaze;
        public PerceptionController perception;
        public GazeSelector gazeSelector;
        public HologramPersistence persistence;
        public WristMenu wristMenu;

        [Header("Settings (v1.1 §5.15) — auto-created if left empty")]
        public VrKeyboard keyboard;
        public SettingsController settingsController;

        [Header("Orchestration (v1.2 §9) — auto-created if left empty")]
        public OrchestrationController orchestration;

        [Header("Studio (v1.3 §10) — auto-created if left empty")]
        public StudioController studio;

        private void Awake()
        {
            if (config == null)
            {
                Debug.LogError("[Jarvis] JarvisApp needs a JarvisConfig assigned. Disabling.");
                enabled = false;
                return;
            }

            // 1) anchors first (everything else resolves spatial parents through it).
            anchors = Ensure(anchors, "Anchors");
            if (head == null && Camera.main != null) head = Camera.main.transform;
            if (head != null) anchors.head = head;
            if (leftHand != null) anchors.leftHand = leftHand;
            if (rightHand != null) anchors.rightHand = rightHand;
            if (worldOrigin != null) anchors.worldOrigin = worldOrigin;

            // 2) connection (auto-connects in its Start()).
            connection = Ensure(connection, "Connection");
            connection.Config = config;

            // 3) interaction relay.
            relay = Ensure(relay, "InteractionRelay");
            relay.connection = connection;

            // 4) optional audio channel + endpoints.
            audioChannel = Ensure(audioChannel, "AudioChannel");
            audioChannel.config = config;

            // 5) hologram manager.
            holograms = Ensure(holograms, "HologramManager");
            holograms.connection = connection;
            holograms.anchors = anchors;
            holograms.relay = relay;
            holograms.registry = widgetRegistry;

            // 6) speech playback + mic capture (both optional / config-gated).
            speech = Ensure(speech, "SpeechPlayer");
            speech.channel = audioChannel;
            speech.config = config;

            mic = Ensure(mic, "MicStreamer");
            mic.config = config;
            mic.channel = audioChannel;

            // 7) scene reporter.
            sceneReporter = Ensure(sceneReporter, "SceneReporter");
            sceneReporter.connection = connection;
            sceneReporter.anchors = anchors;
            sceneReporter.interval = config.sceneReportInterval;
            sceneReporter.enabled = config.enableSceneReporting;
            if (sceneReporter.provider == null) sceneReporter.provider = FindSceneProvider();

            // 8) presence + spatial menu (own transforms so they can move independently).
            presence = EnsureChild(presence, "JarvisPresence");
            presence.connection = connection;
            presence.follow = anchors.head;

            menu = EnsureChild(menu, "SpatialMenu");
            menu.connection = connection;
            menu.follow = anchors.head;

            // 9) perception (v1.1): camera + vision streamer, ambient audio, gaze, controller.
            cameraProvider = Ensure(cameraProvider, "PassthroughCamera");
            cameraProvider.config = config;
            cameraProvider.anchors = anchors;

            visionChannel = Ensure(visionChannel, "VisionChannel");
            visionChannel.config = config;

            visionStreamer = Ensure(visionStreamer, "VisionStreamer");
            visionStreamer.config = config;
            visionStreamer.connection = connection;
            visionStreamer.provider = cameraProvider;
            visionStreamer.visionChannel = visionChannel;

            ambientAudio = Ensure(ambientAudio, "AmbientAudioStreamer");
            ambientAudio.config = config;
            ambientAudio.channel = audioChannel;

            gaze = Ensure(gaze, "GazeProvider");
            gaze.config = config;
            gaze.connection = connection;
            gaze.anchors = anchors;

            perception = Ensure(perception, "PerceptionController");
            perception.config = config;
            perception.connection = connection;
            perception.vision = visionStreamer;
            perception.ambientAudio = ambientAudio;
            perception.gaze = gaze;
            perception.cameraProvider = cameraProvider;
            perception.follow = anchors.head;

            gazeSelector = Ensure(gazeSelector, "GazeSelector");
            gazeSelector.gaze = gaze;
            gazeSelector.relay = relay;

            persistence = Ensure(persistence, "HologramPersistence");
            persistence.manager = holograms;

            // 10) wrist menu (privacy + layout), anchored to the left hand.
            wristMenu = EnsureChild(wristMenu, "WristMenu");
            wristMenu.hand = anchors.leftHand;
            wristMenu.perception = perception;
            wristMenu.persistence = persistence;

            // 11) settings (v1.1 §5.15): VR keyboard + LLM settings panel.
            keyboard = EnsureChild(keyboard, "VrKeyboard");
            keyboard.follow = anchors.head;

            settingsController = EnsureChild(settingsController, "SettingsController");
            settingsController.connection = connection;
            settingsController.keyboard = keyboard;
            settingsController.follow = anchors.head;

            wristMenu.settings = settingsController;
            menu.settings = settingsController;

            // 12) agent-team orchestration view (v1.2 §9), to the side of the presence/captions.
            orchestration = EnsureChild(orchestration, "OrchestrationController");
            orchestration.connection = connection;
            orchestration.follow = anchors.head;
            wristMenu.orchestration = orchestration;
            menu.orchestration = orchestration;

            // 13) Studio — in-headset agent/skill composer (v1.3 §10.2). Reuses the VR keyboard.
            studio = EnsureChild(studio, "StudioController");
            studio.connection = connection;
            studio.keyboard = keyboard;
            studio.follow = anchors.head;
            wristMenu.studio = studio;
            menu.studio = studio;

            // on-device TTS for spoken observations
            presence.speech = speech;
        }

        // ---- helpers ------------------------------------------------------------------------

        private T Ensure<T>(T current, string name) where T : Component
        {
            if (current != null) return current;
            var found = FindObjectOfType<T>();
            if (found != null) return found;
            return EnsureChild<T>(null, name);
        }

        private T EnsureChild<T>(T current, string name) where T : Component
        {
            if (current != null) return current;
            var go = new GameObject(name);
            go.transform.SetParent(transform, false);
            return go.AddComponent<T>();
        }

        private static ISceneProvider FindSceneProvider()
        {
            foreach (var mb in FindObjectsOfType<MonoBehaviour>())
                if (mb is ISceneProvider p) return p;
            return null;
        }
    }
}
