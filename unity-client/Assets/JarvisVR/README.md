# JarvisVR Client — Code Architecture

This folder is the Unity client source. It's organized into focused namespaces/assemblies that map
directly onto the v1 protocol ([`/docs/PROTOCOL.md`](../../../docs/PROTOCOL.md)).

## Assemblies

| Assembly | Folder | Depends on | Purpose |
| --- | --- | --- | --- |
| `JarvisVR.Protocol` | `Protocol/` | Newtonsoft.Json | Pure, engine-free wire types + (de)serialization + router. |
| `JarvisVR` | `Net/`, `Holograms/`, `Interaction/`, `Shell/`, `Audio/`, `Perception/`, `Util/` | Protocol, NativeWebSocket, TextMeshPro | All runtime behaviour (MonoBehaviours). |
| `JarvisVR.Meta` | `Meta/Core/` | JarvisVR, Oculus.VR | Rig binding + Scene API. `defineConstraints: HAS_META_CORE` → assembly is skipped entirely (no unresolved refs) when the SDK is absent. |
| `JarvisVR.Meta.Interaction` | `Meta/Interaction/` | JarvisVR, Oculus.Interaction | Interaction-SDK bridge. `defineConstraints: HAS_META_INTERACTION`. |

## Data flow

```
agent-backend ──(JSON over WS)──▶ JarvisConnection ──▶ MessageRouter ──▶ handlers
                                        ▲                                   │
   client.* (hello/heartbeat/ack/       │                                   ├─ HologramManager   (holo.*)
   interaction/scene/text/error) ◀──────┘                                   ├─ JarvisPresence    (agent.*)
                                                                            └─ SceneReporter     (timer → client.scene)
hands / controllers / mouse ──▶ HoloInteractable ──▶ InteractionRelay ──▶ client.interaction
```

## Protocol layer (`Protocol/`)

- **`Envelope`** — the `{v,id,type,ts,session,reply_to,payload}` frame (§2). `payload` stays a raw
  `JObject` so we dispatch by `type` first and only deserialize the strongly-typed DTO when needed —
  this is what makes unknown types/keys safely ignorable (§6, forward-compatible).
- **`EnvelopeSerializer`** — `Build`/`BuildJson`/`TryDeserialize`; `NullValueHandling.Ignore` (so a
  first `client.hello` omits `session`) + `MissingMemberHandling.Ignore`.
- **`MessageRouter`** — `On(type, handler)` / `Route(env)`; unknown types go to `OnUnhandled`.
- **`MessageTypes` / `Anchors` / `Arrangements` / `InteractionActions` / `ThinkingStages` /
  `WidgetTypes` / `ErrorCodes`** — string constants from the spec.
- **`HologramObject` / `HoloTransform`** (§5.6) and **`Payloads.cs`** — DTOs for every message
  (hello, hello_ack, text, thinking, speech, holo.update/destroy/layout, interaction, scene, errors).
  Numeric transforms are `float[]` on the wire; `Util/ProtocolMath` converts to Vector3/Quaternion.

> Self-contained on purpose (see header comment in `ProtocolConstants.cs`) — reconcile with
> `shared-protocol/` C# bindings later; the wire shapes are identical.

## Net layer (`Net/`)

- **`JarvisConfig`** (ScriptableObject) — host/port/path/tls, advertised capabilities, heartbeat &
  reconnect timings, audio/scene toggles. `MainUrl` / `AudioUrl` helpers.
- **`JarvisConnection`** (MonoBehaviour) — the §3 lifecycle: connect → `client.hello` → store
  session from `server.hello_ack` → 5 s `client.heartbeat` → auto-reconnect (exponential backoff).
  Drains NativeWebSocket on the main thread (`DispatchMessageQueue`) so all handlers are main-thread
  safe. Public `Send/Ack/SendText/SendError`, events (`OnReady`, `OnStateChanged`, …) and `Router`.

## Holograms (`Holograms/`)

- **`HologramManager`** — subscribes to `holo.spawn/update/destroy/layout`; instantiates a prefab
  from `WidgetRegistry` or a procedural widget from `WidgetCatalog`; applies transform + anchor +
  billboard; replies `client.ack` to spawns; fades on destroy; expires on `ttl_ms`.
- **`AnchorService`** — resolves `world|head|hand_left|hand_right|surface` → a `Transform` (parents
  holograms so their coords are anchor-relative).
- **`HoloWidget`** (abstract base) — `Build()` once + `ApplyProps()` on spawn/update; `PatchProps`
  merges partial `holo.update` patches; tolerant prop readers + primitive/TMP helpers.
- **`WidgetRegistry`** (prefab overrides) + **`WidgetCatalog`** (built-in `widget_type → behaviour`).
- **`LayoutArranger`** (arc/grid/stack/free), **`Billboard`**, **`LazyFollow`** + **`WidgetModes`**
  (world-lock / follow / billboard placement), **`HoloMaterials`** (pipeline-agnostic materials).
- **`HologramPersistence`** (+`IAnchorStore`) — saves/restores the hologram layout across sessions
  (PlayerPrefs world poses, upgradable to Meta Spatial Anchors). `HoloWidget.Snapshot()` captures a
  widget's placement + props.
- **`Widgets/`** — 33 procedural widgets. v1 (12): weather_orb, timer, panel, chart_3d, model_viewer,
  media_player, map_3d, smart_home_panel, text_label, button, todo_list, image_board. v1.1 perception
  (5): vision_annotation, bounding_box_3d, live_caption, vision_feed, scene_label. v1.1 feature (16):
  clock, world_clock, calendar, sticky_note, navigation_arrow, measuring_tape, system_launcher,
  notification_toast, settings_panel, music_visualizer, data_table, pomodoro, health_ring,
  stocks_ticker, code_viewer, graph_3d. Interactive sub-elements use **named child colliders**
  (e.g. `pause_button`, `app_<id>`, `set_<id>`, `node_<id>`) which become the `element` in
  `client.interaction`.

## Interaction (`Interaction/`)

- **`HoloInteractable`** — input-agnostic API (`Tap/GrabBegin/GrabEnd/Drag/Slider/Toggle/Resize/
  Dwell`) filtered by the object's allowed interaction set.
- **`InteractionRelay`** — turns those into `client.interaction` (§5.11) with typed `value` shapes.
- **`GazeSelector`** — gaze + pinch/voice/dwell selection: taps whatever `GazeProvider` reports.
- **`MouseInteractionTester`** — editor/desktop click-to-tap (legacy-input only). On device, the
  Meta bridges drive the same `HoloInteractable`.

## Shell (`Shell/`)

- **`JarvisApp`** — the bootstrap: creates + wires every subsystem from one inspector slot.
- **`JarvisPresence`** — orb + captions reflecting `agent.thinking` / `agent.speech` /
  `agent.transcript` and connection state.
- **`SceneReporter`** (+`ISceneProvider`) — periodic `client.scene` (head pose; surfaces/anchors via
  a provider).
- **`SpatialMenu`** — quick commands sent as `user.text`.
- **`WristMenu`** — left-hand privacy + spatial-OS actions (Stop capture, Camera/Mic toggles,
  Save/Restore layout, **⚙ Settings**).
- **`SettingsController`** — in-headset **LLM settings** (§5.15): loads via `client.settings_get`,
  renders `server.settings` (provider/model/base_url/key_set), saves via `client.settings_update`
  (api_key only when newly typed, sent redacted), with a manual fallback.
- **`VrKeyboard`** (+`IVrKeyboardBackend`) — spatial text entry: `TouchScreenKeyboard` (Meta system
  keyboard, masked secure mode) → on-panel procedural keyboard fallback; optional Meta 3D backend.
- **`OrchestrationController`** — live **Agent Team** org-chart (§9): builds nodes+edges from
  `orchestration.plan`, animates each node by `orchestration.agent_status` state (queued/working/
  done/failed + skill + progress), adds sub-agents on `orchestration.handoff`, and auto fades
  in/out around a turn. Also folds in the **per-agent trace timeline** (§10.1): selecting a node
  shows its `orchestration.trace_event`s (gated by `client.trace_subscribe`), with Inspect
  (`client.agent_inspect`→`server.agent_info`) and Last (`client.trace_get`→`server.trace`).
- **`StudioController`** — in-headset **agent/skill composer** (§10.2): `client.author_list` →
  catalog; `client.author_skill` / `client.author_agent` (create/update/delete) → `server.authoring`;
  errors shown inline. Reuses `VrKeyboard` (multiline) for bodies/personas.

## Audio (`Audio/`)

- **`AudioChannel`** — optional binary WS on `/audio` (16 kHz mono PCM16, §1).
- **`MicStreamer`** — captures mic → PCM16 → `/audio` (opt-in, wake/STT path).
- **`SpeechPlayer`** — plays inbound TTS PCM16, and `Speak(text)` on-device TTS (Android
  TextToSpeech) for `agent.observation` narration.

## Perception (`Perception/`, v1.1 §8)

- **`PassthroughCameraProvider`** — captures the forward RGB camera (Meta PCA via `WebCamTexture`;
  editor webcam / synthetic fallback), JPEG-encodes downscaled frames; pluggable `ICameraPoseSource`.
- **`VisionStreamer`** + **`VisionChannel`** — pull-based `perception.vision_frame`: length-prefixed
  binary on `/vision` (§8.2) or inline base64; honors fps/quality/resolution; capture only while active.
- **`AmbientAudioStreamer`** — continuous room audio → 16 kHz PCM16 on `/audio`; exposes RMS level.
- **`GazeProvider`** (+`IGazeSource`) — `perception.gaze` at ~8 Hz: eye ray (Meta) or head ray,
  raycasts holograms for `hit_object_id` + dwell.
- **`PerceptionController`** — handles `perception.request` (start/stop/once/set), emits
  `perception.state` (active streams + thermal + battery), draws the **capture indicator**, runs the
  thermal/fps guard, and advertises camera/audio/eye capabilities truthfully in the hello.

## Meta (`Meta/`, optional, gated by `defineConstraints`)

Each Meta assembly compiles **only** when its package define is present, so the project builds with
or without the Meta SDK installed (no unresolved-reference errors before import).

- **`MetaRigBinder`** (`Meta/Core/`, `HAS_META_CORE`) — binds OVRCameraRig anchors into `AnchorService`.
- **`MetaSceneProvider`** (`Meta/Core/`, `HAS_META_CORE`) — Meta Scene surfaces/anchors → `SceneReporter`.
- **`MetaEyeGazeSource`** (`Meta/Core/`, `HAS_META_CORE`) — OVREyeGaze → `GazeProvider` (eye ray).
- **`GazePinchInteractor`** (`Meta/Core/`, `HAS_META_CORE`) — OVRHand pinch → `GazeSelector` (gaze+pinch).
- **`MetaCameraPoseSource`** (`Meta/Core/`, `HAS_META_PCA`) — accurate passthrough camera pose +
  intrinsics → `VisionStreamer` (opt-in define).
- **`MetaSpatialAnchorBinder`** (`Meta/Core/`, `HAS_META_ANCHORS`) — drift-free Spatial-Anchor
  world-locking (opt-in define).
- **`MetaVirtualKeyboard`** (`Meta/Core/`, `HAS_META_KEYBOARD`) — Meta 3D `OVRVirtualKeyboard`
  backend for `VrKeyboard` (non-secure fields; opt-in define).
- **`MetaInteractionBridge`** (`Meta/Interaction/`, `HAS_META_INTERACTION`) — Interaction SDK
  poke/grab → `HoloInteractable`.

## Conformance checklist (PROTOCOL.md §6 + §8)

- [x] Sends/accepts the v1.1 envelope exactly (`v=1.1.0`, `id,type,ts,session,payload`, optional `reply_to`).
- [x] Ignores unknown `type` (router) and unknown payload keys (Newtonsoft `MissingMemberHandling`).
- [x] Heartbeat (5 s) + reconnect (backoff).
- [x] Meters + quaternions + the anchor enum.
- [x] Validates `widget_type` against the registry/catalog (else `client.error: unknown_widget`).
- [x] §8 perception is pull-based (capture only while a stream is active), advertises capabilities
      truthfully, `/vision` binary framing per §8.2, and shows a capture indicator + `perception.state`.
