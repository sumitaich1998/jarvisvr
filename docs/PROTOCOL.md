# JarvisVR Wire Protocol (v1.1)

This is the **source of truth** for communication between the `unity-client` (Quest 3) and the
`agent-backend`. The `voice-service` and `shared-protocol` bindings also conform to it. If you
change a message shape, bump `PROTOCOL_VERSION` and update this file in the same change.

```
PROTOCOL_VERSION = "1.3.0"   # 1.3 adds Tracing & In-headset Authoring (§10); 1.2 = Orchestration (§9); 1.1 = Perception (§8); back-compatible
```

## 1. Transport

- **WebSocket**, JSON text frames (UTF-8). One client connection per headset session.
- Default endpoint: `ws://<host>:8765/jarvis`
- Binary audio (optional) may be sent on a parallel endpoint `ws://<host>:8765/audio` as raw
  16 kHz mono PCM16 frames; transcripts/speech text still flow as JSON on the main channel.
- **Vision (v1.1, optional)**: passthrough-camera frames may be sent on a parallel endpoint
  `ws://<host>:8765/vision` as length-prefixed binary frames (see §8.2), or inline as base64 on
  the main channel for low frame rates. Recommended: pull-based, 1–3 fps, JPEG q≈70, ≤1024².
- Heartbeat: client sends `client.heartbeat` every 5s; server echoes `server.heartbeat`.

## 2. Envelope

Every message is a JSON object with this envelope:

```jsonc
{
  "v": "1.0.0",            // protocol version (semver)
  "id": "uuid-v4",         // unique message id
  "type": "namespace.name",// see message catalog below
  "ts": 1733397600000,      // epoch milliseconds (sender clock)
  "session": "uuid-v4",    // session id (assigned in hello_ack); omitted on first hello
  "payload": { }            // type-specific object (may be {})
}
```

- Unknown `type` values MUST be ignored (forward-compatible).
- `reply_to` (optional, string id) may be set to correlate a response with a request.

## 3. Connection lifecycle

```
client ──client.hello──▶ server
client ◀─server.hello_ack── server   (assigns session, advertises capabilities)
... heartbeat both ways every 5s ...
client ──client.bye──▶ server (graceful close)
```

## 4. Message catalog

### 4.1 Client → Server

| `type`                   | Purpose                                              |
| ------------------------ | ---------------------------------------------------- |
| `client.hello`           | Handshake; device + capability advertisement         |
| `client.bye`             | Graceful disconnect                                   |
| `client.heartbeat`       | Keepalive                                             |
| `user.text`              | Typed/system text input from the user                |
| `user.voice_transcript`  | Final speech transcript (STT)                        |
| `user.voice_partial`     | Interim/streaming transcript (optional)              |
| `client.interaction`     | User interacted with a hologram (tap/grab/slider/…)  |
| `client.scene`           | Spatial scene update (anchors, surfaces, head pose)  |
| `client.ack`             | Acknowledge a render command (`reply_to` = cmd id)   |
| `client.error`           | Client-side error report                             |
| `client.barge_in`        | User spoke over Jarvis; cancel the current turn (v1.1)|
| `client.settings_get`    | Request current settings + provider catalog (v1.1)   |
| `client.settings_update` | Change settings, e.g. LLM provider/model/API key (v1.1)|
| `client.trace_subscribe` | Enable/disable live per-agent trace streaming (v1.3)  |
| `client.trace_get`       | Fetch the full trace for a past turn (v1.3)          |
| `client.agent_inspect`   | Inspect an agent: persona, skills, tools, memory (v1.3)|
| `client.author_list`     | List authorable agents & skills (v1.3)               |
| `client.author_skill`    | Create/update/delete a Skill from the headset (v1.3) |
| `client.author_agent`    | Create/update/delete an agent from the headset (v1.3)|

### 4.2 Server → Client

| `type`              | Purpose                                                       |
| ------------------- | ------------------------------------------------------------- |
| `server.hello_ack`  | Handshake response; session id + server capabilities          |
| `server.heartbeat`  | Keepalive echo                                                 |
| `agent.thinking`    | Status/stage update (e.g., "thinking", "calling get_weather") |
| `agent.speech`      | Text for Jarvis to speak (TTS) and/or caption                 |
| `agent.transcript`  | What the agent heard (echo of user input, for captions)       |
| `holo.spawn`        | Create a holographic object                                   |
| `holo.update`       | Patch properties/transform of an existing object              |
| `holo.destroy`      | Remove an object                                              |
| `holo.layout`       | Batch arrange/anchor multiple objects                         |
| `server.error`      | Server-side error                                            |
| `server.settings`   | Current settings + provider catalog (v1.1; never returns keys)|
| `orchestration.plan` | The agent team & plan Jarvis built for a goal (v1.2)         |
| `orchestration.agent_status` | A single agent's lifecycle/progress update (v1.2)    |
| `orchestration.handoff` | A delegation between agents / to a sub-agent (v1.2)       |

## 5. Payload schemas

### 5.1 `client.hello`
```jsonc
{
  "device": "quest3",
  "app_version": "0.1.0",
  "protocol_version": "1.1.0",
  "capabilities": {
    "passthrough": true,
    "hand_tracking": true,
    "controllers": true,
    "mic": true,
    "speaker": true,
    "scene_understanding": true,
    "camera_passthrough": true,   // v1.1: RGB passthrough camera frames (Passthrough Camera API)
    "ambient_audio": true,        // v1.1: continuous room-audio listening
    "eye_tracking": false,        // v1.1: gaze ray (if available on device)
    "on_device_vision": false,    // v1.1: client-side object detection
    "depth": false                // v1.1: depth / scene mesh available
  },
  "locale": "en-US"
}
```

### 5.2 `server.hello_ack`
```jsonc
{
  "session": "uuid-v4",
  "protocol_version": "1.1.0",
  "agent": { "name": "Jarvis", "model": "mock|gpt-…|claude-…" },
  "tools": ["get_weather", "start_timer", "..."],   // names only; full schemas in holo-tools
  "voice": { "tts": true, "wake_word": "jarvis" }
}
```

### 5.3 `user.text` / `user.voice_transcript` / `user.voice_partial`
```jsonc
{ "text": "show me the weather in Tokyo", "confidence": 0.97 }
```

### 5.4 `agent.thinking`
```jsonc
{ "stage": "planning|tool_call|rendering|done", "label": "Calling get_weather…", "tool": "get_weather" }
```

### 5.5 `agent.speech`
```jsonc
{ "text": "Here's the weather in Tokyo.", "final": true, "emotion": "neutral" }
```
Stream long replies as multiple `agent.speech` with `final:false`, ending with `final:true`.

### 5.6 The Holographic Object

A hologram is described by a single object used across `holo.spawn` / `holo.update`:

```jsonc
{
  "object_id": "uuid-v4",          // server-assigned, stable for the object's lifetime
  "widget_type": "weather_orb",    // must exist in holo-tools/registry.json
  "transform": {
    "anchor": "world",             // world | head | hand_left | hand_right | surface
    "position": [0.0, 1.4, 1.0],   // meters, relative to anchor
    "rotation": [0, 0, 0, 1],      // quaternion x,y,z,w
    "scale":    [1, 1, 1],
    "billboard": false              // if true, always face the user
  },
  "props": { },                    // widget-specific; validated against holo-tools schema
  "interactable": true,
  "interactions": ["grab", "tap", "resize"],  // subset of the widget's supported set
  "ttl_ms": 0                       // 0 = persists until destroyed
}
```

### 5.7 `holo.spawn`
Payload = a Holographic Object (5.6). Client SHOULD reply with `client.ack` (`reply_to` = msg id).

### 5.8 `holo.update`
```jsonc
{ "object_id": "uuid-v4", "transform": { }, "props": { } }  // partial patch; omit unchanged keys
```

### 5.9 `holo.destroy`
```jsonc
{ "object_id": "uuid-v4", "fade_ms": 300 }
```

### 5.10 `holo.layout`
```jsonc
{
  "arrangement": "arc|grid|stack|free",
  "anchor": "head",
  "objects": ["object_id_1", "object_id_2"],
  "spacing": 0.25
}
```

### 5.11 `client.interaction`
```jsonc
{
  "object_id": "uuid-v4",
  "widget_type": "timer",
  "action": "tap",                 // tap | grab | release | drag | slider | toggle | resize | dwell
  "element": "pause_button",       // optional sub-element id within the widget
  "value": { },                    // action data, e.g. {"slider": 0.4} or {"position":[...]} 
  "hand": "right"
}
```

### 5.12 `client.scene`
```jsonc
{
  "head": { "position": [0,1.6,0], "rotation": [0,0,0,1] },
  "surfaces": [ { "id":"floor", "type":"floor", "center":[0,0,0], "normal":[0,1,0] } ],
  "anchors": [ { "id":"uuid", "position":[0,0,0], "rotation":[0,0,0,1] } ]
}
```

### 5.13 Errors — `server.error` / `client.error`
```jsonc
{ "code": "unknown_widget", "message": "widget_type 'foo' not in registry", "fatal": false }
```
Suggested codes: `bad_envelope`, `unsupported_version`, `unknown_type`, `unknown_widget`,
`invalid_props`, `tool_failed`, `internal`.

### 5.14 `client.barge_in` (v1.1)
```jsonc
{ "reason": "user_speech" }   // user started talking over Jarvis
```
Sent by the client / voice-service when the user interrupts active TTS. On receipt the server
SHOULD cancel the in-flight agent turn: stop streaming `agent.speech` / `agent.observation`, abort
pending tool calls where safe, and may emit `agent.thinking{stage:"done"}`. Idempotent — ignore if
no turn is active. (Forward-compatible: pre-v1.1 servers simply ignore it.)

### 5.15 Settings — `client.settings_get` / `client.settings_update` / `server.settings` (v1.1)

Lets the user view and change configuration — notably the **LLM provider / model / API key** —
from the in-headset **Settings** panel at any time, not just at install.

`client.settings_get` (client → server)
```jsonc
{ "section": "llm" }   // omit or "all" for everything
```

`client.settings_update` (client → server)
```jsonc
{
  "llm": {
    "provider": "openai",          // any supported provider id (see server.settings.llm.providers)
    "model": "gpt-4o",
    "base_url": null,               // for openai-compatible / local / custom; null otherwise
    "api_key": "sk-…"               // OPTIONAL — send only to set/replace; omit to keep existing
  }
}
```
Sensitive: `api_key` travels only on this message — use `wss://` in production. The server stores it
securely (e.g. `.env`, mode 0600), applies it by **hot-swapping** the active provider, and MUST NOT
ever echo the key back.

`server.settings` (server → client) — current config + catalog; sent in reply to
`client.settings_get` and `client.settings_update`, and MAY be pushed when settings change.
```jsonc
{
  "llm": {
    "current": { "provider": "openai", "model": "gpt-4o", "base_url": null, "key_set": true },
    "providers": [
      { "id": "openai", "name": "OpenAI", "default_model": "gpt-4o",
        "models": ["gpt-4o", "gpt-4o-mini"], "needs_key": true, "needs_base_url": false,
        "key_set": true, "capabilities": { "tools": true, "vision": true } },
      { "id": "anthropic", "name": "Anthropic", "default_model": "claude-3-7-sonnet",
        "needs_key": true, "needs_base_url": false, "key_set": false,
        "capabilities": { "tools": true, "vision": true } },
      { "id": "ollama", "name": "Ollama (local)", "default_model": "llama3.1",
        "needs_key": false, "needs_base_url": true, "key_set": false,
        "capabilities": { "tools": true, "vision": false } }
      // … one entry per supported provider
    ]
  }
}
```
`key_set` is a boolean only — the actual key is never returned. Errors use `server.error` with code
`invalid_settings`, `provider_unavailable`, or `invalid_key`.

## 6. Conformance checklist (for every component)
- [ ] Sends/accepts the v1 envelope exactly (`v,id,type,ts,session,payload`).
- [ ] Ignores unknown `type` and unknown payload keys.
- [ ] Implements heartbeat + reconnect.
- [ ] Uses meters + quaternions + the anchor enum above.
- [ ] Validates `widget_type` + `props` against `holo-tools/registry.json`.

## 7. Reference example (one turn)
```jsonc
// client → server
{"v":"1.0.0","id":"a1","type":"user.voice_transcript","ts":1,"session":"S","payload":{"text":"weather in tokyo"}}
// server → client
{"v":"1.0.0","id":"b1","type":"agent.thinking","ts":2,"session":"S","payload":{"stage":"tool_call","tool":"get_weather"}}
{"v":"1.0.0","id":"b2","type":"agent.speech","ts":3,"session":"S","payload":{"text":"Here's Tokyo.","final":true}}
{"v":"1.0.0","id":"b3","type":"holo.spawn","ts":4,"session":"S","payload":{"object_id":"O1","widget_type":"weather_orb","transform":{"anchor":"head","position":[0.3,0,0.8],"rotation":[0,0,0,1],"scale":[1,1,1],"billboard":true},"props":{"city":"Tokyo","temp_c":18,"condition":"clouds"},"interactable":true,"interactions":["grab","tap"]}}
// client → server
{"v":"1.0.0","id":"c1","type":"client.ack","ts":5,"session":"S","reply_to":"b3","payload":{}}
```

## 8. Multimodal Perception (v1.1 — additive, optional, negotiated)

v1.1 gives Jarvis **sight** (RGB color passthrough cameras), **hearing** (continuous ambient room
audio), and **attention** (gaze) so the user can converse about what they are seeing and hearing
in their physical space. All perception streams are **optional and negotiated**: the client
advertises them in `client.hello.capabilities`, and the server turns them on/off with
`perception.request` (pull-based) to manage bandwidth, battery, and privacy. The backend keeps a
short rolling **perception buffer** (recent frames + ambient audio + gaze) and automatically
correlates it with each user utterance, enabling realtime multimodal turns such as
*"Jarvis, what is this?"*, *"read this sign and translate it"*, or *"what was that sound?"*.

> **Privacy:** camera/microphone capture is user-initiated and on-device-gated. Frames/audio are
> sent only while a stream is active; servers SHOULD process in-memory and avoid persistence
> unless the user opts in. `perception.state` always reflects what is currently being captured.

### 8.1 Capabilities (advertised in `client.hello`)
`camera_passthrough`, `ambient_audio`, `eye_tracking`, `on_device_vision`, `depth` (all booleans).
On Quest 3 / 3S, `camera_passthrough` uses Meta's **Passthrough Camera API** (forward RGB stream).

### 8.2 Vision transport (`/vision`)
Binary frames on `ws://<host>:8765/vision` are length-prefixed:

```
[4-byte big-endian uint32 = headerLen][headerLen bytes UTF-8 JSON header][image bytes...]
```
The JSON header equals the `perception.vision_frame` payload (§8.4) **without** `data`, with
`transport:"binary"`. For low frame rates a client MAY instead send `perception.vision_frame`
inline on the main channel with `transport:"inline"` and base64 `data`.

### 8.3 Message catalog (v1.1)

Client → Server:

| `type`                     | Purpose                                                     |
| -------------------------- | ---------------------------------------------------------- |
| `perception.vision_frame`  | A passthrough RGB camera frame + camera pose               |
| `perception.audio_event`   | A detected ambient sound event (doorbell, alarm, name…)    |
| `perception.audio_scene`   | Ambient audio understanding (overheard speech, soundscape) |
| `perception.gaze`          | Gaze/attention ray, dwell, and hit object                  |
| `perception.scene_objects` | Client-side detected objects with 3D positions (optional)  |
| `perception.state`         | Which perception streams are active + thermal/battery      |

Server → Client:

| `type`                | Purpose                                                       |
| --------------------- | ------------------------------------------------------------ |
| `perception.request`  | Start/stop/snapshot/adjust a perception stream (pull-based)   |
| `agent.observation`   | What Jarvis perceives, with optional spatial annotations      |

Additive optional fields: `user.text` / `user.voice_transcript` MAY carry
`"attach_perception": true` (default true while vision is active) so the agent considers current
sight/sound. `agent.thinking.stage` gains `"perceiving"` and `"looking"`.

### 8.4 Payload schemas

`perception.vision_frame`
```jsonc
{
  "frame_id": "uuid-v4",
  "camera": "rgb_center",         // rgb_left | rgb_right | rgb_center
  "format": "jpeg",               // jpeg | png | rgb24
  "width": 1024, "height": 1024,
  "quality": 70,
  "transport": "inline",          // inline (base64 in `data`) | binary (on /vision)
  "data": "<base64…>",            // present iff transport=inline
  "seq": 1234,                     // monotonic per stream
  "ts_capture": 1733397600000,
  "pose": { "position": [0,1.6,0], "rotation": [0,0,0,1] },   // camera pose in world
  "intrinsics": { "fx": 720, "fy": 720, "cx": 512, "cy": 512 } // optional, for unprojection
}
```

`perception.audio_event`
```jsonc
{ "label": "doorbell", "confidence": 0.82, "ts": 1733397600000, "loudness_db": -22.0 }
```

`perception.audio_scene`
```jsonc
{
  "ambient_transcript": "…overheard speech, not directed at Jarvis…",
  "speaker": "other",             // user | other | unknown
  "sounds": [ { "label": "music", "confidence": 0.6 } ],
  "loudness_db": -30.0,
  "window_ms": 4000
}
```

`perception.gaze`
```jsonc
{
  "source": "eyes",               // eyes | head
  "origin": [0,1.6,0], "direction": [0,0,1],
  "hit_object_id": "uuid-or-null",
  "hit_point": [0.2,1.3,0.9],
  "dwell_ms": 600
}
```

`perception.scene_objects`
```jsonc
{
  "frame_id": "uuid-v4",
  "objects": [
    { "label": "coffee mug", "confidence": 0.78, "bbox": [120, 80, 64, 64],
      "position": [0.3,0.8,0.7], "anchor": "world" }
  ]
}
```

`perception.state`
```jsonc
{
  "vision": { "active": true, "fps": 2, "resolution": "1024x1024", "camera": "rgb_center" },
  "ambient_audio": { "active": true },
  "gaze": { "active": false },
  "thermal": "nominal",           // nominal | fair | serious | critical
  "battery": 0.74
}
```

`perception.request` (server → client)
```jsonc
{
  "stream": "vision",             // vision | ambient_audio | gaze | scene_objects
  "action": "start",              // start | stop | once (single snapshot) | set
  "fps": 2,                        // for vision/gaze
  "max_resolution": "1024x1024",
  "quality": 70,
  "duration_ms": 0,                // 0 = until stopped
  "reason": "user asked about the room"   // optional, surfaced for consent/UX
}
```

`agent.observation` (server → client)
```jsonc
{
  "text": "I can see a coffee mug and a laptop on your desk.",
  "final": true,
  "annotations": [
    { "label": "coffee mug", "object_id": "O9", "position": [0.3,0.8,0.7], "anchor": "world" }
  ]
}
```
Spatial annotations are typically realized as `vision_annotation` / `bounding_box_3d` holograms
via `holo.spawn`; `agent.observation` carries the spoken/captioned narration.

### 8.5 Perception widgets (schemas owned by `holo-tools` v1.1)
`vision_annotation` (world-anchored callout/label on a real object), `bounding_box_3d`,
`live_caption` (rolling captions of speech Jarvis hears), `vision_feed` (a panel showing what
Jarvis currently sees), `scene_label`. Full `props` schemas live in `holo-tools/registry.json`.

### 8.6 Realtime multimodal turn (example)
```jsonc
// server enables sight when the user starts asking about the room
{"v":"1.1.0","id":"r1","type":"perception.request","ts":1,"session":"S","payload":{"stream":"vision","action":"start","fps":2,"reason":"user asked what they're looking at"}}
// client streams frames (binary on /vision, or inline as below)
{"v":"1.1.0","id":"f1","type":"perception.vision_frame","ts":2,"session":"S","payload":{"frame_id":"F1","camera":"rgb_center","format":"jpeg","width":1024,"height":1024,"transport":"inline","data":"/9j/4AAQ…","seq":1,"ts_capture":2,"pose":{"position":[0,1.6,0],"rotation":[0,0,0,1]}}}
// user (voice) — perception auto-attached
{"v":"1.1.0","id":"u1","type":"user.voice_transcript","ts":3,"session":"S","payload":{"text":"hey jarvis, what is this on my desk?","attach_perception":true}}
// agent perceives, answers, and annotates the real object
{"v":"1.1.0","id":"o1","type":"agent.observation","ts":4,"session":"S","payload":{"text":"That's a ceramic coffee mug.","final":true,"annotations":[{"label":"coffee mug","position":[0.3,0.8,0.7],"anchor":"world"}]}}
{"v":"1.1.0","id":"o2","type":"holo.spawn","ts":5,"session":"S","payload":{"object_id":"O9","widget_type":"vision_annotation","transform":{"anchor":"world","position":[0.3,0.95,0.7],"rotation":[0,0,0,1],"scale":[1,1,1],"billboard":true},"props":{"label":"coffee mug","confidence":0.78},"interactable":true,"interactions":["tap"]}}
{"v":"1.1.0","id":"o3","type":"agent.speech","ts":6,"session":"S","payload":{"text":"Looks like your coffee mug — want me to set a reminder to refill it?","final":true}}
// server stops the camera when done (privacy/battery)
{"v":"1.1.0","id":"r2","type":"perception.request","ts":7,"session":"S","payload":{"stream":"vision","action":"stop"}}
```

## 9. Multi-Agent Orchestration (v1.2 — additive, optional)

In v1.2, JarvisVR is a **multi-agent OS**: an orchestrator named **Jarvis** decomposes a goal and
delegates to a team of **skill-specialized agents**, which may themselves delegate to sub-agents
(a multi-level hierarchy). These messages expose the live team so the client can visualize who is
doing what. They are **additive and optional** — a client may ignore them and still behaves exactly
as in v1.1; conversation, perception, and holograms are unchanged. Full design:
[`docs/ORCHESTRATION.md`](./ORCHESTRATION.md).

### 9.1 Message catalog (v1.2)

Server → Client:

| `type`                       | Purpose                                                     |
| ---------------------------- | ---------------------------------------------------------- |
| `orchestration.plan`         | The team & plan Jarvis built for a goal (agents + edges)   |
| `orchestration.agent_status` | A single agent's lifecycle/progress update                 |
| `orchestration.handoff`      | A delegation from one agent to another (or to a sub-agent) |
| `orchestration.trace_event`  | One live per-agent trace entry (v1.3)                       |
| `server.trace`               | Full trace for a turn (reply to `client.trace_get`, v1.3)   |
| `server.agent_info`          | An agent's persona/skills/tools/memory (v1.3)               |
| `server.authoring`           | Authorable agents & skills catalog (v1.3)                   |

Additive fields: `agent.thinking` MAY carry `agent_id`, `role`, and `skill` to attribute a step to
a specific agent. `server.hello_ack` MAY include `"orchestration": true` and an `"agents"` array of
role ids.

### 9.2 Payloads

`orchestration.plan`
```jsonc
{
  "plan_id": "uuid-v4",
  "goal": "show the weather in Tokyo and start a 5-minute timer",
  "agents": [
    { "agent_id": "jarvis", "role": "orchestrator", "name": "Jarvis", "parent": null, "level": 0 },
    { "agent_id": "a1", "role": "research-agent", "name": "Research", "parent": "jarvis",
      "level": 1, "subtask": "get current weather for Tokyo", "skills": ["web-research"] },
    { "agent_id": "a2", "role": "productivity-agent", "name": "Productivity", "parent": "jarvis",
      "level": 1, "subtask": "start a 5-minute timer", "skills": ["manage-timers"] }
  ],
  "edges": [ { "from": "jarvis", "to": "a1" }, { "from": "jarvis", "to": "a2" } ]
}
```

`orchestration.agent_status`
```jsonc
{
  "plan_id": "uuid-v4",
  "agent_id": "a1",
  "role": "research-agent",
  "parent": "jarvis",
  "level": 1,
  "state": "working",        // queued | planning | working | delegating | waiting | done | failed
  "skill": "web-research",   // active skill id (optional)
  "label": "Looking up Tokyo weather…",
  "progress": 0.5             // optional, 0..1
}
```

`orchestration.handoff`
```jsonc
{
  "plan_id": "uuid-v4",
  "from_agent": "a1",
  "to_agent": "a1.1",
  "to_role": "summarizer",
  "level": 2,
  "subtask": "summarize the 3 sources into one forecast",
  "reason": "delegating summarization to a sub-agent"
}
```

### 9.3 Turn lifecycle (with orchestration)
```
agent.thinking{planning}
  → orchestration.plan                       (the team for this goal)
  → per agent: orchestration.agent_status{queued → working … → done}
       (+ orchestration.handoff when an agent spawns a sub-agent)
  → agents' work surfaces as the usual holo.* / agent.observation / tool effects
  → agent.speech{final}                      (Jarvis synthesizes the result)
```
`agent_id` values are stable within a `plan_id`; sub-agents use dotted ids (`a1.1`) by convention.
Roles correspond to the specialist agents in `docs/ORCHESTRATION.md` (e.g. `research-agent`,
`perception-agent`, `smart-home-agent`, `stage-agent`, …).

## 10. Per-Agent Tracing & In-Headset Authoring (v1.3 — additive, optional)

Two additive feature sets, both back-compatible (clients may ignore them):
**(a)** per-agent memory + a live **trace** of everything each agent does, and **(b)** **authoring**
— composing your own agents and Agent Skills from inside the headset.

### 10.1 Per-agent memory & tracing

Each specialist keeps its own memory namespace; the orchestrator records a **trace** of every turn
(skill activations, tool calls, observations, memory reads/writes, delegations). Traces stream live
as `orchestration.trace_event` (gated by `client.trace_subscribe`); a full trace is fetchable with
`client.trace_get` → `server.trace`. Inspect an agent with `client.agent_inspect` → `server.agent_info`.

`client.trace_subscribe` (client → server)
```jsonc
{ "enabled": true }   // turn live trace_event streaming on/off (default off; the trace view enables it)
```

`orchestration.trace_event` (server → client)
```jsonc
{
  "plan_id": "uuid-v4", "seq": 7, "ts": 1733397600000,
  "agent_id": "a1", "role": "research-agent", "parent": "jarvis", "level": 1,
  "kind": "tool_call",   // memory_read | memory_write | skill_activated | tool_call | tool_result | observation | delegated | speech | error
  "label": "get_weather(city=Tokyo)",
  "skill": "web-research",     // optional
  "tool": "get_weather",       // optional
  "detail": "…short, secret-redacted summary…",  // optional
  "duration_ms": 120            // optional
}
```

`client.trace_get` (client → server) → `server.trace` (server → client)
```jsonc
// request:
{ "plan_id": "uuid-v4" }            // omit for the most recent turn
// reply:
{
  "plan_id": "uuid-v4", "goal": "…",
  "agents": [ { "agent_id": "a1", "role": "research-agent", "parent": "jarvis", "level": 1 } ],
  "entries": [ /* array of orchestration.trace_event payloads, in order */ ]
}
```

`client.agent_inspect` (client → server) → `server.agent_info` (server → client)
```jsonc
// request:
{ "role": "research-agent" }        // or { "agent_id": "a1" }
// reply:
{
  "role": "research-agent", "name": "Research", "source": "builtin",   // builtin | user
  "persona": "…",
  "tools": ["web_search", "get_weather", "get_news"],
  "skills": [ { "name": "web-research", "description": "…", "source": "builtin" } ],
  "memory": { "summary": "…", "items": 12, "recent": [ { "ts": 1, "text": "…" } ] }
}
```

### 10.2 In-headset authoring (compose your own agents & skills)

Users can create/edit/delete agents and Agent Skills from the headset. The server validates against
the [agentskills.io](https://agentskills.io) rules + the roster, persists them (Skills as `SKILL.md`
under the skills root; agents in a user roster file), and **hot-reloads** so new capabilities are
usable immediately — no restart.

> **Safety (server MUST):** sanitize `name`/`category` (agentskills.io `name` rules; reject path
> traversal), confine writes to the skills root, and refuse to overwrite built-ins (only
> user-authored items may be updated/deleted). Authored items SHOULD carry `source: "user"` (skills
> via `metadata.source: user`).

`client.author_list` (client → server) `{}` → `server.authoring` (server → client)
```jsonc
{
  "agents": [ { "role": "research-agent", "name": "Research", "source": "builtin",
               "skills": ["web-research", "…"], "tools": ["web_search", "…"] } ],
  "skills": [ { "name": "web-research", "agent": "research-agent", "category": "research",
               "source": "builtin", "description": "…" } ],
  "categories": ["perception", "research", "productivity", "…"],
  "tools": ["get_weather", "start_timer", "annotate_object", "…"]   // pickable tool ids
}
```

`client.author_skill` (client → server)
```jsonc
{
  "op": "create",                 // create | update | delete
  "name": "track-habit",          // agentskills.io name rules; becomes the dir name
  "category": "productivity",
  "agent": "productivity-agent",  // owning role (metadata.agent)
  "description": "Track a daily habit and show the streak. Use for 'track my…', 'did I … today?'.",
  "body": "# Track a habit\n## Steps\n1. …",   // the SKILL.md Markdown body
  "allowed_tools": ["take_note", "show_panel"],  // optional
  "license": "MIT",                // optional
  "compatibility": "…"             // optional
}
```
→ reply `server.authoring` (updated) or `server.error` (`invalid_skill` | `name_conflict` | `forbidden`).

`client.author_agent` (client → server)
```jsonc
{
  "op": "create",                 // create | update | delete
  "role": "finance-agent",        // lowercase id; new specialist role
  "name": "Finance",
  "persona": "You are a meticulous finance specialist…",
  "tools": ["get_stocks", "show_chart"],   // optional subset of available tools
  "skills": ["market-briefing"]            // optional skill names to attach
}
```
→ reply `server.authoring` (updated) or `server.error` (`invalid_agent` | `name_conflict` | `forbidden`).

### 10.3 Handshake & lifecycle
- `server.hello_ack` MAY include `"tracing": true` and `"authoring": true`.
- Authoring a skill writes its `SKILL.md` and reloads the registry; the owning agent gains it on its
  next turn. Authoring an agent registers a new role immediately — it joins routing and shows up in
  the Agent Team view (§9) and `orchestration.plan`.
- Traces are keyed by `plan_id`; secret values (API keys, raw frames/audio) are **never** included —
  only short redacted summaries.

