# JarvisVR — Unity MR Client (Quest 3)

The **mixed-reality shell** for JarvisVR: a Unity 2022 LTS app for the Meta Quest 3 that connects
to the `agent-backend` over WebSocket, renders the holographic widgets the AI agent summons into
the room (passthrough MR), and routes hand/controller interactions back to the brain.

It implements the **v1.3** wire protocol in [`../docs/PROTOCOL.md`](../docs/PROTOCOL.md) exactly —
including **§8 Multimodal Perception** (Jarvis can *see*/*hear*/sense *gaze*), **§9 Multi-Agent
Orchestration** (a live MR view of Jarvis's agent team), and **§10 Tracing & In-headset Authoring**
(watch each agent think; compose your own agents & skills). Inbound versions are accepted, never
rejected. See [`ARCHITECTURE.md`](../ARCHITECTURE.md) for where this fits.

> This README covers prerequisites, configuring the backend host, building/deploying to Quest 3,
> and testing in-editor. For the **scene recipe** see
> [`Assets/JarvisVR/SETUP.md`](Assets/JarvisVR/SETUP.md); for the **code architecture** see
> [`Assets/JarvisVR/README.md`](Assets/JarvisVR/README.md).

---

## What it does

- Connects to `ws://<host>:8765/jarvis`, performs the `client.hello` / `server.hello_ack`
  handshake, heartbeats every 5 s, and auto-reconnects with backoff.
- Spawns / updates / destroys / arranges holograms from `holo.*` messages, mapping each
  `widget_type` to a prefab (or a built-in **procedural** widget so it works with no art).
- Reports `client.interaction` (tap / grab / release / drag / slider / toggle / resize / dwell).
- Shows a persistent **Jarvis presence** (orb + captions) reflecting `agent.thinking` /
  `agent.speech` / `agent.transcript`, plus a simple spatial menu.
- Periodically sends `client.scene` (head pose + optional surfaces/anchors).
- Optional mic streaming + TTS playback over the parallel `/audio` PCM16 channel.
- In-headset **Settings** to view/change the LLM **provider / model / API key** at any time (§5.15).
- Live **Agent Team** org-chart of Jarvis's multi-agent orchestration (§9) — see who's planning /
  working / delegating / done, with skills and progress.
- Per-agent **trace timeline** (§10.1): select an agent node to watch it think (memory/skill/tool/
  observation/delegation/speech events, with durations), live or for a past turn.
- In-headset **Studio** (§10.2): compose your own agents & Agent Skills (create/edit/delete).

**Perception (v1.1, §8):**
- **Sight** — captures the forward RGB passthrough camera and streams JPEG frames + camera pose
  (`perception.vision_frame`), length-prefixed binary on `/vision` or inline base64. Pull-based.
- **Hearing** — continuous ambient room audio to `/audio` (16 kHz PCM16) for the voice-service.
- **Gaze** — eye gaze (if permitted) or head ray, raycast against holograms (`perception.gaze`).
- **Control & privacy** — obeys `perception.request` (start/stop/once/set), reports
  `perception.state`, shows a visible **capture indicator** while recording, and a thermal/fps guard.
- Handles `agent.observation` (caption + on-device TTS) and spawns perception widgets.

Handled widget types: `weather_orb`, `timer`, `panel`, `chart_3d`, `model_viewer`, `media_player`,
`map_3d`, `smart_home_panel`, `text_label`, `button`, `todo_list`, `image_board`, plus v1.1
**perception** widgets `vision_annotation`, `bounding_box_3d`, `live_caption`, `vision_feed`,
`scene_label`, and **feature** widgets `clock`, `world_clock`, `calendar`, `sticky_note`,
`navigation_arrow`, `measuring_tape`, `system_launcher`, `notification_toast`, `settings_panel`,
`music_visualizer`, `data_table`, `pomodoro`, `health_ring`, `stocks_ticker`, `code_viewer`,
`graph_3d`. Unknown types still render a placeholder + `client.error: unknown_widget`.

---

## Prerequisites

| Requirement | Notes |
| --- | --- |
| **Unity 2022.3 LTS** (2022.3.40f1 used) | Install via Unity Hub with **Android Build Support** (incl. **OpenJDK** + **Android SDK & NDK**). |
| **Meta XR SDK** | "Meta XR All-in-One SDK" (`com.meta.xr.sdk.all`). Installed from the Asset Store / Package Manager (see below). |
| **Meta Quest 3** | In **Developer Mode**, USB debugging enabled, `adb` available. |
| **agent-backend** (or `infra/` mock) | The WebSocket server this client talks to. |

Packages pinned in [`Packages/manifest.json`](Packages/manifest.json): OpenXR, XR Management,
Input System, TextMeshPro, Newtonsoft JSON, and **NativeWebSocket** (UPM git
`https://github.com/endel/NativeWebSocket.git#upm`).

### Installing the Meta XR SDK

`manifest.json` references `com.meta.xr.sdk.all`. Meta distributes this via the **Asset Store**, so:

1. Open the project in Unity (let it resolve the registry packages first).
2. Open **Window ▸ Package Manager ▸ My Assets**, find **Meta XR All-in-One SDK**, **Download** +
   **Import**. This pins the real version in `manifest.json` (adjust the placeholder version there
   if Unity prompts).
3. Run **Meta ▸ Tools ▸ Project Setup Tool** and apply all recommended fixes for Android/Quest.

> The code is structured so it **compiles even before** the Meta SDK is imported — all Meta-specific
> integration lives in `Assets/JarvisVR/Meta/` behind assembly version-defines and lights up
> automatically once the SDK is present. TextMeshPro: when prompted, **Import TMP Essentials**.

---

## Configure the backend host

Backend connection settings live in a **`JarvisConfig`** asset (no code change needed):

1. **Assets ▸ Create ▸ JarvisVR ▸ Jarvis Config** → e.g. `Assets/JarvisVR/JarvisConfig.asset`.
2. Set **host** / **port** (default `8765`) / **path** (`/jarvis`).
   - In-editor against a local backend: `127.0.0.1`.
   - On a Quest over Wi-Fi: your dev machine's **LAN IP** (e.g. `192.168.1.50`).
   - `wss://` is supported via the **Use Tls** toggle.
3. Assign that asset to the **`JarvisApp`** component in the scene (see `SETUP.md`).

Other handy toggles: `logTraffic` (console-log every frame), `enableMicStreaming`,
`enableSceneReporting`, heartbeat/reconnect timings, and the **v1.1 perception** settings (vision
fps/quality/resolution, gaze rate, capture-indicator, thermal guard).

---

## Perception & privacy (v1.1)

Perception is **pull-based**: the client advertises `camera_passthrough` / `ambient_audio` /
`eye_tracking` in `client.hello` (auto-corrected to what the device actually supports), and the
backend turns streams on/off with `perception.request`. The camera/mic run **only while a stream is
active**, and a red **capture indicator** appears in view whenever they do.

- **Camera (sight)** — uses the Meta **Passthrough Camera API**, accessed as a `WebCamTexture` after
  the headset-camera permission is granted. Frames are downscaled (≤1024²), JPEG-encoded, and sent on
  `/vision` (binary) or inline. Pull-based 1–3 fps by default; a thermal/fps guard throttles when hot.
- **Microphone (hearing)** — continuous ambient audio (16 kHz PCM16) on `/audio`, separate from the
  wake-word/STT path.
- **Gaze** — eye gaze via `OVREyeGaze` when the eye-tracking permission is granted, else a head ray.
- **Privacy controls** — the **wrist menu** (left hand) has a **Stop capture** kill switch and
  Camera/Mic toggles; `perception.state` always reflects what's being captured.

**Required permissions (Android manifest + runtime):** the client requests these at runtime, but you
must also enable them in **Player Settings / the Meta Project Setup Tool**:

| Capability | Permission(s) |
| --- | --- |
| Passthrough camera | `horizonos.permission.HEADSET_CAMERA` **and** `android.permission.CAMERA` |
| Ambient audio | `android.permission.RECORD_AUDIO` |
| Eye-tracked gaze | `com.oculus.permission.EYE_TRACKING` |

> Optional accuracy: enable the **`HAS_META_PCA`** scripting define (and wire `MetaCameraPoseSource`)
> for exact camera pose/intrinsics, and **`HAS_META_ANCHORS`** for drift-free Spatial-Anchor
> world-locking. Both are off by default so the project compiles without those Meta APIs.

---

## Settings — change the LLM provider / model / API key in-headset (§5.15)

View and change the assistant's **LLM provider, model, and API key** at any time from a holographic
**Settings** panel — no rebuild or `.env` edit needed.

**Open it:** the **wrist menu** (left hand) → **⚙ Settings**, or the spatial menu → **⚙ Settings**.

**How it loads/saves:**
- On open it sends `client.settings_get{section:"llm"}` and renders the `server.settings` reply: a
  **provider** selector (‹ › to cycle the `providers[]` catalog, or ✎ to type a custom id), a
  **model** selector (cycle `models[]` or ✎ for a free-text override), a **base URL** field (shown
  only when the provider has `needs_base_url`), and an **API key** field showing **key set ✓ /
  not set** from `key_set` (the real key is never returned by the server).
- **Save** sends `client.settings_update{ llm:{ provider, model, base_url?, api_key? } }`. The
  `api_key` is included **only if you typed a new one** — leave it untouched to keep the existing key.
  The panel shows *Saving… → Applied ✓* from the `server.settings` reply and surfaces
  `invalid_settings` / `provider_unavailable` / `invalid_key` inline.
- **Fallback:** if no `server.settings` arrives (older/mock backend), it switches to a manual form
  (type provider id + model + base URL + key) that still emits `client.settings_update`.

**Entering the key (secure):** fields use a spatial keyboard — Unity `TouchScreenKeyboard`, which
brings up the **Meta system VR keyboard** on Quest with a **masked (secure)** mode for the key; in
the editor/desktop an on-panel keyboard is used. Optionally enable the **`HAS_META_KEYBOARD`** define
to use Meta's 3D `OVRVirtualKeyboard` for non-secure fields.

**Security:** the key is shown only as dots, **never logged** (sent via a redacted "sensitive" send),
and cleared from memory right after sending. Use `wss://` in production so it's encrypted in transit.

---

## Agent Team — visualize the multi-agent orchestration (§9)

When the backend runs as a **team** (an orchestrator *Jarvis* delegating to skill-specialized
agents, see `docs/ORCHESTRATION.md`), the client renders a live holographic **org-chart** off to the
side (it coexists with the centered presence orb + captions).

- On **`orchestration.plan`** it builds the chart: **Jarvis** at the root and the specialist nodes
  below, laid out by `level` with parent→child **edges** (line renderers). Each node card shows the
  role **name** and its **active skill**.
- On **`orchestration.agent_status`** each node animates by `state`: dim = *queued*, pulsing + a
  spinner = *planning/working/delegating*, a **progress** bar (0..1), amber = *waiting*, **green** =
  *done*, **red** = *failed* — plus the `label`/`skill` text.
- On **`orchestration.handoff`** the delegated **sub-agent** node is added (dotted ids like `a1.1`)
  and a new edge is drawn from the delegating agent.
- It **fades in** when a plan/turn starts and **out** a few seconds after every agent finishes.

**Toggle it** any time from the **wrist menu → Team** or the spatial menu → **Agent Team**
(`OrchestrationController.Toggle()`); opening it manually pins it open (no auto-hide). Everything is
procedural (primitives + TextMeshPro + line renderers) and additive — pre-v1.2 backends that never
send `orchestration.*` simply never show the board.

---

## Agent traces & Studio (§10)

**Per-agent trace timeline (§10.1).** The Agent Team view (above) doubles as a tracer: **select a
node** (tap / gaze / Meta poke) to open a scrollable **timeline** of that agent's
`orchestration.trace_event`s — a color-coded icon per `kind` (memory / skill / tool / result /
observation / delegation / speech / error), the `label`, the `skill`/`tool`, and `duration_ms`. The
view sends `client.trace_subscribe{enabled:true}` when it opens and `{false}` when it closes, and
renders events live. The timeline header has **Inspect** (→ `client.agent_inspect`, shows the
agent's persona / tools / skills / memory from `server.agent_info`), **Last** (→ `client.trace_get`
to load the most recent past turn as `server.trace`), and scroll **↑/↓**.

**Studio — compose agents & skills (§10.2).** Open **Studio** from the wrist/spatial menu. It sends
`client.author_list` and shows the catalog (agents + skills, badged **[builtin]** / **[user]**).
- **New/Edit Skill:** name, category (cycle), owning agent (cycle), description, instructions **body**
  (multi-line `VrKeyboard`), and a toggle list of **allowed tools** → `client.author_skill`
  (`create`/`update`; `delete` for user skills). Tapping a built-in **forks** it as a new user skill.
- **New/Edit Agent:** role id, name, persona, and toggle lists of **tools** + **skills** →
  `client.author_agent`.
- The server validates + hot-reloads and replies `server.authoring` (the panel refreshes and shows
  **Saved ✓**) or `server.error` (`invalid_skill` / `invalid_agent` / `name_conflict` / `forbidden`,
  shown inline). New agents appear in the Agent Team view on the next turn.

Both are procedural, reuse the masked `VrKeyboard`, and never log secrets (traces are redacted
server-side; authored text isn't logged).

---

## Run in the editor (Quest Link) against the mock backend

1. Start the backend: from the repo root, `cd infra && docker compose up --build` (provides the
   mock agent on `:8765`).
2. Set the `JarvisConfig` host to `127.0.0.1`.
3. Connect the Quest via **Quest Link** (or Air Link) so the editor renders to the headset; or just
   press **Play** on a desktop to validate networking/widgets without a headset.
4. **Desktop testing without a headset:** set **Project Settings ▸ Player ▸ Active Input Handling**
   to **Both**, then **left-click** holograms/menu items — the editor mouse tester sends real
   `client.interaction` / `user.text` messages. Enable `logTraffic` to watch the protocol in the
   Console.

---

## Build & deploy to Quest 3 (Android)

1. **File ▸ Build Settings ▸ Android ▸ Switch Platform.**
2. Texture compression **ASTC**; run **Meta ▸ Tools ▸ Project Setup Tool** and apply fixes.
3. **Player Settings** (most are applied by the Setup Tool):
   - Scripting Backend **IL2CPP**, Target Architectures **ARM64**.
   - Minimum API Level **Android 10 (API 29)** or higher.
   - **XR Plug-in Management ▸ Android ▸ OpenXR** enabled, with the **Meta Quest** feature group
     and **hand-tracking** + **passthrough** (+ **eye tracking** for gaze) features on.
4. **Perception permissions** (Meta Project Setup Tool or AndroidManifest): grant
   **Headset Camera** (`horizonos.permission.HEADSET_CAMERA` + `android.permission.CAMERA`),
   **Record Audio**, and (optional) **Eye Tracking** (`com.oculus.permission.EYE_TRACKING`). The
   app also requests these at runtime before capturing.
5. Add the **Jarvis** scene to **Scenes In Build**.
6. Connect the Quest (`adb devices` to confirm) → **Build And Run** (writes/installs an `.apk`).

CLI alternative: `adb install -r build/JarvisVR.apk`.

---

## Troubleshooting

- **Can't connect / instant reconnect loop** — wrong host/port, backend not running, or the Quest
  isn't on the same network as your dev machine. Use the LAN IP, not `127.0.0.1`, on device. Enable
  `logTraffic`.
- **Cleartext `ws://` blocked on device** — the manifest/Setup Tool must allow cleartext traffic, or
  use `wss://`. (For local dev, cleartext to a LAN IP is typical.)
- **Holograms invisible in a build** — add the URP/Standard shader used by `HoloMaterials` to
  **Project Settings ▸ Graphics ▸ Always Included Shaders** (see `SETUP.md`).
- **Text not rendering** — import **TMP Essentials** (Window ▸ TextMeshPro ▸ Import TMP Essential
  Resources).
- **No passthrough / black background** — enable Passthrough in OVRManager/OpenXR and set the
  camera clear to a transparent/solid color per `SETUP.md`.
- **No vision frames on device** — the headset-camera permission wasn't granted, or the device name
  hint (`visionCameraNameHint`) doesn't match; check the capture indicator and Console. In the editor
  the default webcam (or a synthetic frame) is used so the pipeline is still testable.
- **Capture indicator stuck on / camera won't stop** — the wrist menu's **Stop capture** is a hard
  privacy kill switch; capture also stops automatically when the backend sends `perception.request`
  stop or the thermal guard trips.

## Notes & assumptions

- `shared-protocol/` will publish canonical C# bindings; this client ships a **self-contained**
  protocol implementation (`Assets/JarvisVR/Protocol/`) so it isn't blocked — reconcile later
  (wire shapes are identical).
- `holo-tools/registry.json` is the authoritative widget catalog. Until it's wired in, the built-in
  `WidgetCatalog` renders the known types procedurally; drop prefabs into a `WidgetRegistry` asset to
  override any of them.
