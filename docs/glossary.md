# Glossary

Key JarvisVR terms, defined concisely. Links point to the authoritative doc for each.
See also the [FAQ](./faq.md) and the [Overview](./concepts/overview.md).

---

### agent / agent loop
The reasoning core in `agent-backend`. The loop is the agentic cycle **plan → call
tools → observe → respond**: an LLM decides what to do, calls [tools](#tool--tool-call),
turns results into holograms, and streams speech back. See
[The agent loop](./concepts/agent-loop.md).

### agent-backend ("the brain")
The Python WebSocket server that hosts the agent, LLM provider, tools, widget catalog,
and memory. It's the protocol endpoint the headset connects to. See the
[deep-dive](./components/agent-backend.md).

### ambient hearing / ambient audio
Continuous understanding of the room's audio **beyond** the wake word — an overheard
transcript + soundscape (`perception.audio_scene`) and discrete
[sound events](#sound-event). Distinct from directed wake-word/STT. See
[Perception](./concepts/perception.md).

### anchor
What a hologram's position is relative to. One of `world` (fixed in the room), `head`
(follows the user), `hand_left` / `hand_right`, or `surface` (a detected plane).
[PROTOCOL §5.6](./PROTOCOL.md#56-the-holographic-object).

### barge-in
Talking over Jarvis to interrupt it. The client sends `client.barge_in`; the server
cancels the in-flight turn (stops `agent.speech`/`agent.observation`, aborts pending
work). [PROTOCOL §5.14](./PROTOCOL.md#514-clientbarge_in-v11).

### billboard
A transform flag — when `true`, the hologram always turns to face the user (handy for
labels and orbs). Part of the [transform](#transform).

### capabilities
What a client advertises in `client.hello` (passthrough, hand tracking, mic, speaker,
and v1.1 `camera_passthrough`, `ambient_audio`, `eye_tracking`, …). The server uses
them to decide which [perception](#perception) streams to request.
[PROTOCOL §5.1](./PROTOCOL.md#51-clienthello).

### catalog (widget catalog)
The set of widgets the agent can summon, defined by
[`holo-tools/registry.json`](../holo-tools/registry.json) and consumed by both backend
(validation + tool schemas) and client (`widget_type` → prefab). Human-readable form:
[`docs/HOLO_TOOLS.md`](./HOLO_TOOLS.md).

### envelope
The outer JSON wrapper on every message: `{ v, id, type, ts, session, payload }`
(+ optional `reply_to`). [PROTOCOL §2](./PROTOCOL.md#2-envelope).

### episodic memory
Long-term memory of **events** (with timestamp + pose/anchor) and **semantic facts**,
plus a [spatial index](#spatial-memory) of seen objects. Lets Jarvis answer "where did
I leave my keys?". Persisted under `JARVIS_DATA_DIR`.

### gaze
The user's eye- or head-ray, with dwell and the object it hits (`perception.gaze`).
Tells the agent **what** the user is looking at. [PROTOCOL §8.4](./PROTOCOL.md#84-payload-schemas).

### generic OpenAI-compatible
A provider routing kind: any server exposing an OpenAI `/chat/completions` endpoint,
reached over plain `httpx` with **no extra SDK** (Groq, Gemini, Ollama, vLLM, custom…).
See [Add an LLM provider](./guides/add-an-llm-provider.md).

### heartbeat
A keepalive: the client sends `client.heartbeat` every 5 s; the server echoes
`server.heartbeat`. Proves the connection is alive. [PROTOCOL §3](./PROTOCOL.md#3-connection-lifecycle).

### holographic object
The single data structure describing a hologram on the wire: `object_id`,
`widget_type`, [transform](#transform), [props](#props--props_schema), `interactable`,
`interactions`, `ttl_ms`. Payload of `holo.spawn`/`holo.update`.
[PROTOCOL §5.6](./PROTOCOL.md#56-the-holographic-object).

### Hologram Manager
The Unity component that owns hologram lifecycle — it handles `holo.spawn`/`update`/
`destroy`/`layout`, maps each `widget_type` to a prefab or procedural
[widget](#widget--widget_type), applies the transform, and replies with `client.ack`.

### holo-tools
The package that defines the widget catalog, the agent tool/function schemas
(`tools.json`, derived from the registry), validators, and TypeScript types. See the
[deep-dive](./components/holo-tools.md).

### hot-swap
Changing the active LLM provider/model **at runtime** without a reconnect or restart.
A `client.settings_update` persists the change and the agent uses it on the **next
turn**. [PROTOCOL §5.15](./PROTOCOL.md#515-settings--clientsettings_get--clientsettings_update--serversettings-v11).

### interaction
A user action on a hologram (`tap`, `grab`, `release`, `drag`, `slider`, `toggle`,
`resize`, `dwell`) reported as `client.interaction`. The agent reacts (e.g. pause a
timer). [PROTOCOL §5.11](./PROTOCOL.md#511-clientinteraction).

### LiteLLM
An optional universal adapter (`pip install -e ".[providers]"`) that routes to 100+
providers via one interface — used for `azure`, `bedrock`, `vertex`, `cohere`, and any
provider when `JARVIS_USE_LITELLM=1`.

### LLM provider
The pluggable model backend behind a single interface. JarvisVR ships ~20 in a
[registry](../agent-backend/jarvis_backend/providers.py); the default is the
[mock](#mock-provider--mock-mode). See [Add an LLM provider](./guides/add-an-llm-provider.md).

### Meta XR SDK
Meta's Unity SDK ("Meta XR All-in-One SDK") providing passthrough, hand tracking, the
Passthrough Camera API, anchors, etc. Required to build the `unity-client` for a Quest.

### mock provider / mock mode
The deterministic, **offline** default LLM (`JARVIS_LLM=mock`): a keyword/intent
planner that maps text → tool calls and synthesizes spoken replies from tool results,
plus deterministic mock vision. Needs no key — the whole stack is demoable offline.

### mixed reality (MR)
Digital content composited onto a live view of the real world. On Quest 3 this is
**passthrough MR** — holograms appear in your actual room.

### object_id
The server-assigned UUID for a spawned hologram, stable for its lifetime; used by
`holo.update`/`holo.destroy` and `client.interaction`. (Internally, a tool may give a
hologram a logical `ref` that the agent maps to the `object_id`.)

### OpenXR
The cross-vendor open standard for VR/AR runtimes. The `unity-client` targets OpenXR
with the Meta Quest feature group (passthrough, hand tracking, eye tracking).

### passthrough (color passthrough)
The Quest 3's video feed of the real world shown behind the holograms, so the room
stays visible. "Color passthrough" = the RGB (not grayscale) feed.

### Passthrough Camera API
Meta's API exposing the forward **RGB passthrough camera** frames to the app (accessed
as a `WebCamTexture`). JarvisVR streams these as `perception.vision_frame` so the agent
can **see**. Requires the headset-camera permission.

### perception
v1.1 multimodal input: **sight** (passthrough camera), **hearing** (ambient audio +
sound events), and **attention** (gaze), correlated with each utterance. Opt-in,
negotiated, pull-based. [PROTOCOL §8](./PROTOCOL.md#8-multimodal-perception-v11--additive-optional-negotiated)
· [Perception concept](./concepts/perception.md).

### perception buffer
The backend's short, rolling per-session store of recent frames, audio events/scenes,
gaze, and detected objects. Its "current context" is auto-attached to a turn so the
LLM reasons over what Jarvis currently senses.

### perception.request (pull-based)
The server's control message to **start/stop/snapshot (`once`)/adjust (`set`)** a
perception stream. "Pull-based" = capture runs only while the server has asked for it
(privacy/battery). [PROTOCOL §8.4](./PROTOCOL.md#84-payload-schemas).

### prefab / prefab_id
A reusable Unity GameObject template. Each widget names a `prefab_id` (e.g.
`Holo_WeatherOrb`); the client instantiates that prefab — or falls back to a built-in
**procedural** renderer if none is registered.

### props / props_schema
A widget's data (`props`) and the **JSON Schema** that validates it (`props_schema`,
draft 2020-12, closed with `additionalProperties:false`). The backend validates props
before spawning. See [Add a widget](./guides/add-a-widget.md).

### protocol (wire protocol)
The versioned WebSocket contract every component conforms to
([`docs/PROTOCOL.md`](./PROTOCOL.md)). `PROTOCOL_VERSION = "1.1.0"` (1.0.0 clients
still supported). The [shared-protocol](#shared-protocol) bindings implement it.

### Quest 3 / Quest 3S
Meta's mixed-reality headsets with color passthrough, hand tracking, and the
Passthrough Camera API — JarvisVR's target devices.

### quaternion
The 4-number `[x, y, z, w]` rotation format used for every hologram's orientation
(no gimbal lock). Part of the [transform](#transform).

### ref (logical handle)
A tool-assigned name for a hologram (e.g. `timer:ab12`) so later turns/interactions
can update or destroy the same object. The agent maps each `ref` to a server
`object_id`. See [Write a tool](./guides/write-a-tool.md).

### registry.json
The single source of truth for the widget catalog. `tools.json`, `ts/widgets.ts`, and
`docs/HOLO_TOOLS.md` are kept in sync with it (and `tools.json` is generated from it).

### session
A per-connection identity assigned by the server in `server.hello_ack` and echoed in
the [envelope](#envelope). One session per headset connection.

### settings (in-headset)
The v1.1 flow to view/change the LLM **provider / model / API key** at runtime from a
holographic panel (`client.settings_get` / `client.settings_update` /
`server.settings`). The key is write-only and never echoed back.
[PROTOCOL §5.15](./PROTOCOL.md#515-settings--clientsettings_get--clientsettings_update--serversettings-v11).

### shared-protocol
The canonical protocol bindings in Python, C#, and TypeScript, plus the JSON Schemas
in `schema/` that are the single source of truth for validation. See the
[deep-dive](./components/shared-protocol.md).

### shell (the unity-client)
The headset side of the system — rendering + input. It renders holograms and captures
hands/gaze/camera/mic, decoupled from the [brain](#agent-backend-the-brain) across the
protocol.

### sound event
A discrete detected sound (doorbell, alarm, glass break, name called…) reported as
`perception.audio_event`. Can trigger a proactive heads-up when `JARVIS_PROACTIVE=1`.

### spatial memory
A name → pose/anchor index of objects Jarvis has seen (auto-indexed from detections),
enabling "where did I leave my X?" recall with a marker + navigation arrow. Part of
[episodic memory](#episodic-memory).

### STT (speech-to-text)
Transcribing the user's speech to text in the [voice-service](#voice-service); the
final transcript drives a turn as `user.voice_transcript`.

### tool / tool-call
A named, schema-typed capability the LLM can invoke (get weather, start a timer,
identify an object). A tool returns structured `data` + **holo directives**; the agent
turns directives into `holo.*` messages. See [Write a tool](./guides/write-a-tool.md).

### transform
A hologram's spatial placement: [`anchor`](#anchor), `position` (meters, `[x,y,z]`),
`rotation` ([quaternion](#quaternion)), `scale`, and [`billboard`](#billboard).
[PROTOCOL §5.6](./PROTOCOL.md#56-the-holographic-object).

### TTS (text-to-speech)
Speaking the agent's reply (`agent.speech`) aloud in the
[voice-service](#voice-service), in the "Jarvis" voice.

### unity-client
The Quest 3 Unity (2022 LTS) mixed-reality app — the [shell](#shell-the-unity-client).
See the [deep-dive](./components/unity-client.md) and [README](../unity-client/README.md).

### VAD (voice activity detection)
Detecting when speech starts/stops, used to endpoint an utterance (and to trigger
barge-in) in the voice-service.

### vision frame
A passthrough RGB image + camera pose sent as `perception.vision_frame` — inline
base64 on the main channel, or **length-prefixed binary** on the `/vision` endpoint
(`[4-byte len][JSON header][JPEG bytes]`). [PROTOCOL §8.2](./PROTOCOL.md#82-vision-transport-vision).

### voice-service
Jarvis's "ears and mouth": wake word + STT + TTS + ambient hearing + sound events,
with offline fallbacks. See the [deep-dive](./components/voice-service.md).

### wake word
The trigger phrase ("Jarvis") that starts listening for a command, detected in the
voice-service before STT runs.

### widget / widget_type
A type of hologram in the catalog (e.g. `weather_orb`, `timer`, `vision_annotation`),
identified by its `snake_case` `widget_type`. See the
[catalog](./HOLO_TOOLS.md) and [Add a widget](./guides/add-a-widget.md).

### wss:// / TLS
The encrypted WebSocket scheme. The protocol is plain `ws://` by default for local
dev; use `wss://` (TLS, terminated at a reverse proxy) before exposing the backend —
especially because the settings flow carries the API key. See
[Deploy](./guides/deploy.md#tls--wss-and-authentication).

---

## See also

- [FAQ](./faq.md) · [Overview](./concepts/overview.md) · [Architecture](../ARCHITECTURE.md)
- [Protocol reference](./PROTOCOL.md) · [Message index](./reference/message-index.md)
- [Widget catalog](./HOLO_TOOLS.md) · [Guides](./README.md#guides-how-to)
