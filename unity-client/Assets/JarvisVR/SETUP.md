# Jarvis Scene Setup

`.unity` scenes are awkward to hand-author, so this is the exact recipe to build the **`Jarvis`**
scene. It takes ~5 minutes. The C# is structured so a single **`JarvisApp`** component wires up every
subsystem — you mostly assemble the XR rig and drop two components.

> Prereqs done: project opens, Meta XR All-in-One SDK imported, **TMP Essentials** imported,
> ran **Meta ▸ Tools ▸ Project Setup Tool** (apply all Android/Quest fixes).

---

## 1. Create the config asset

1. **Assets ▸ Create ▸ JarvisVR ▸ Jarvis Config** → name it `JarvisConfig`.
2. Set **host**/**port** to your backend (see `unity-client/README.md`). Leave the rest at defaults.

## 2. New scene + XR rig (passthrough + hands)

1. **File ▸ New Scene** → save as `Assets/JarvisVR/Scenes/Jarvis.unity`. Delete the default
   `Main Camera` (the rig provides one).
2. Add the Meta rig: **GameObject ▸ Meta ▸ Building Blocks** and add **Camera Rig**, or drag the
   `OVRCameraRig`/`[BuildingBlock] Camera Rig` prefab in. Confirm an `OVRManager` exists.
3. On `OVRManager`:
   - **Quest Features ▸ General ▸ Hand Tracking Support** = *Controllers and Hands*.
   - **Insight Passthrough ▸ Enable Passthrough** = on.
4. Add passthrough rendering: add an **OVRPassthroughLayer** (Underlay) to the rig, and set the
   center-eye **Camera ▸ Clear Flags = Solid Color** with **color alpha = 0** (so the room shows
   through). The Building Blocks "Passthrough" block does this for you.
5. Add hands: **GameObject ▸ Meta ▸ Building Blocks ▸ Hand Tracking** (adds `OVRHand` +
   interactor visuals under the left/right hand anchors), and the **Interaction ▸ Poke/Grab**
   blocks if you want hand interaction out of the box.

## 3. Add Jarvis

1. Create an empty GameObject named **`Jarvis`** at the origin.
2. **Add Component ▸ `JarvisApp`**.
3. In the inspector:
   - **Config** → your `JarvisConfig` asset. *(required)*
   - **Widget Registry** → optional (see §5).
   - **Head** → `OVRCameraRig/TrackingSpace/CenterEyeAnchor`.
   - **Left/Right Hand** → the rig's `LeftHandAnchor` / `RightHandAnchor`.
   - **World Origin** → `OVRCameraRig/TrackingSpace`.
4. *(Recommended)* Also add **`MetaRigBinder`** to the `Jarvis` object — it auto-binds the rig
   anchors at runtime, so the fields above are filled even if you leave them empty.

That's it: on Play, `JarvisApp` creates the connection, hologram manager, interaction relay,
presence orb, scene reporter, audio endpoints, **and the v1.1 perception stack** (passthrough camera
provider, vision streamer + `/vision` channel, ambient-audio streamer, gaze provider, perception
controller + capture indicator, gaze selector, layout persistence, wrist menu) as children.

## 3b. Perception (v1.1) — sight, hearing, gaze

The perception subsystems are created and wired automatically by `JarvisApp`. To make them work on
device you mainly need permissions + a couple of optional Meta sources.

1. **Permissions** (Meta **Project Setup Tool** or edit the AndroidManifest), also requested at runtime:
   - **Headset camera**: `horizonos.permission.HEADSET_CAMERA` **and** `android.permission.CAMERA`.
   - **Ambient audio**: `android.permission.RECORD_AUDIO`.
   - **Eye tracking** (optional, for gaze): `com.oculus.permission.EYE_TRACKING`, and enable the
     OpenXR **Eye Gaze Interaction** / Meta eye-tracking feature.
2. **Eye gaze (optional)** → add **`MetaEyeGazeSource`** to the rig and assign the left/right
   `OVREyeGaze` components. Without it, gaze falls back to the head ray automatically.
3. **Accurate camera pose (optional)** → enable the **`HAS_META_PCA`** scripting define
   (Player ▸ Scripting Define Symbols), add **`MetaCameraPoseSource`**, and drive its `cameraAnchor`
   from `PassthroughCameraUtils` (see the file's header). Without it, frames use the head pose.
4. **Gaze + pinch** → add **`GazePinchInteractor`** and assign the `OVRHand`s; an index pinch selects
   the gazed hologram. (Voice selection and gaze-dwell are also supported.)
5. **Privacy** → a red **capture indicator** shows whenever the camera/mic are active; the **wrist
   menu** (left hand) has **Stop capture** + Camera/Mic toggles. Streams are pull-based — nothing
   captures until the backend sends `perception.request` (or you toggle it in the wrist menu).
6. **Test it**: set the `JarvisConfig` capability toggles, then drive the mock backend to send
   `perception.request {stream:"vision", action:"start"}`; watch frames go out (enable `logTraffic`)
   and the indicator appear. In the editor the default webcam (or a synthetic frame) stands in for the
   passthrough camera.

## 4. Optional extras

- **Room scanning** → add **`MetaSceneProvider`** to `Jarvis` to stream room surfaces/anchors in
  `client.scene` (requires Scene permission; run room setup on the headset once).
- **Mic streaming / TTS playback** → toggle `enableMicStreaming` on the config. `JarvisApp` already
  creates `MicStreamer` + `SpeechPlayer` + `AudioChannel` (the `/audio` PCM16 endpoint).
- **Desktop mouse testing** → set **Player ▸ Active Input Handling = Both**, add the
  **`MouseInteractionTester`** component anywhere; left-click holograms to send interactions.

## 5. Custom widget prefabs (optional — procedural by default)

Every `widget_type` already renders procedurally, so this is only to swap in nicer art:

1. **Assets ▸ Create ▸ JarvisVR ▸ Widget Registry** → assign it to `JarvisApp ▸ Widget Registry`.
2. For a type (e.g. `weather_orb`), build a prefab whose **root** has your subclass of
   `HoloWidget`, add a row to the registry mapping `widget_type → prefab`.
3. For hand interaction on a custom prefab, add a **`HoloInteractable`** + **`MetaInteractionBridge`**
   and wire the Interaction SDK's `PointableUnityEventWrapper` to it (poke/grab).

## 6. Graphics gotchas (important for device builds)

- `HoloMaterials` resolves a shader at runtime (URP/Lit → Standard → unlit). For **builds**, add the
  shader your pipeline uses to **Project Settings ▸ Graphics ▸ Always Included Shaders** so
  procedural widgets render on device.
- Keep **passthrough** working: don't add a skybox/clear that paints over the camera.

## 7. Smoke test

1. Start the backend (`infra/` mock or `agent-backend`).
2. Press **Play** (or Build And Run). The presence orb should turn from grey (offline) to blue
   (connected). With `logTraffic` on you'll see `client.hello` → `server.hello_ack`.
3. Drive the mock so it sends a `holo.spawn` (e.g. a `weather_orb`); it should appear in front of
   you. Click/poke it and watch a `client.interaction` go out.
