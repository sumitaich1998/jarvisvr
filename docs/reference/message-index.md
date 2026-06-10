# Message index

A quick lookup of **every** message type in the JarvisVR wire protocol (v1.1) — one
line each, with a link to the authoritative section in
[`docs/PROTOCOL.md`](../PROTOCOL.md). The protocol is the source of truth; this page
is the index.

- **Transport:** WebSocket, JSON text frames, `ws://<host>:8765/jarvis` (+ binary
  `/vision` and `/audio` on the same port). See [§1 Transport](../PROTOCOL.md#1-transport).
- **Envelope:** every message is `{ v, id, type, ts, session, payload }` (+ optional
  `reply_to`). See [§2 Envelope](../PROTOCOL.md#2-envelope).
- **Version:** `PROTOCOL_VERSION = "1.1.0"` (1.0.0 clients still supported). Unknown
  `type` values **must be ignored** (forward-compatible).
- **Type constants** in code: [`agent-backend` `protocol.MsgType`](../../agent-backend/jarvis_backend/protocol.py)
  and the [`shared-protocol` bindings](../../shared-protocol/README.md).

---

## Client → Server

| `type` | Since | Purpose | Spec |
| ------ | ----- | ------- | ---- |
| `client.hello` | 1.0 | Handshake; advertise device + capabilities (passthrough, mic, camera…). | [§5.1](../PROTOCOL.md#51-clienthello) |
| `client.bye` | 1.0 | Graceful disconnect. | [§3](../PROTOCOL.md#3-connection-lifecycle) |
| `client.heartbeat` | 1.0 | Keepalive (every 5 s); server echoes `server.heartbeat`. | [§3](../PROTOCOL.md#3-connection-lifecycle) |
| `user.text` | 1.0 | Typed/system text input from the user. | [§5.3](../PROTOCOL.md#53-usertext--uservoice_transcript--uservoice_partial) |
| `user.voice_transcript` | 1.0 | Final speech transcript (STT) — drives the agent turn. | [§5.3](../PROTOCOL.md#53-usertext--uservoice_transcript--uservoice_partial) |
| `user.voice_partial` | 1.0 | Interim/streaming transcript (optional; ignored by the agent). | [§5.3](../PROTOCOL.md#53-usertext--uservoice_transcript--uservoice_partial) |
| `client.interaction` | 1.0 | User interacted with a hologram (tap/grab/slider/toggle/resize/dwell…). | [§5.11](../PROTOCOL.md#511-clientinteraction) |
| `client.scene` | 1.0 | Spatial scene update (head pose, surfaces, anchors). | [§5.12](../PROTOCOL.md#512-clientscene) |
| `client.ack` | 1.0 | Acknowledge a render command (`reply_to` = the command's id). | [§5.7](../PROTOCOL.md#57-holospawn) |
| `client.error` | 1.0 | Client-side error report (`code` + `message`). | [§5.13](../PROTOCOL.md#513-errors--servererror--clienterror) |
| `client.barge_in` | **1.1** | User spoke over Jarvis — cancel the in-flight turn. | [§5.14](../PROTOCOL.md#514-clientbarge_in-v11) |
| `client.settings_get` | **1.1** | Request current settings + the provider catalog. | [§5.15](../PROTOCOL.md#515-settings--clientsettings_get--clientsettings_update--serversettings-v11) |
| `client.settings_update` | **1.1** | Change settings (LLM provider/model/API key). Carries the key — use `wss://`. | [§5.15](../PROTOCOL.md#515-settings--clientsettings_get--clientsettings_update--serversettings-v11) |

### Client → Server — perception (v1.1)

| `type` | Purpose | Spec |
| ------ | ------- | ---- |
| `perception.vision_frame` | A passthrough RGB camera frame + camera pose (inline base64 or binary on `/vision`). | [§8.4](../PROTOCOL.md#84-payload-schemas) |
| `perception.audio_event` | A detected ambient sound event (doorbell, alarm, name called…). | [§8.4](../PROTOCOL.md#84-payload-schemas) |
| `perception.audio_scene` | Ambient audio understanding (overheard speech + soundscape + loudness). | [§8.4](../PROTOCOL.md#84-payload-schemas) |
| `perception.gaze` | Gaze/attention ray, dwell, and hit object. | [§8.4](../PROTOCOL.md#84-payload-schemas) |
| `perception.scene_objects` | Client-side detected objects with 3D positions (optional). | [§8.4](../PROTOCOL.md#84-payload-schemas) |
| `perception.state` | Which perception streams are active + thermal/battery. | [§8.4](../PROTOCOL.md#84-payload-schemas) |

---

## Server → Client

| `type` | Since | Purpose | Spec |
| ------ | ----- | ------- | ---- |
| `server.hello_ack` | 1.0 | Handshake response; assigns `session`, advertises capabilities/tools/widgets. | [§5.2](../PROTOCOL.md#52-serverhello_ack) |
| `server.heartbeat` | 1.0 | Keepalive echo of `client.heartbeat`. | [§3](../PROTOCOL.md#3-connection-lifecycle) |
| `agent.thinking` | 1.0 | Status/stage update (`planning` / `tool_call` / `rendering` / `perceiving` / `looking` / `done`). | [§5.4](../PROTOCOL.md#54-agentthinking) |
| `agent.speech` | 1.0 | Text for Jarvis to speak (TTS) and/or caption; streamed with `final:false…true`. | [§5.5](../PROTOCOL.md#55-agentspeech) |
| `agent.transcript` | 1.0 | Echo of what the agent heard (for captions). | [§4.2](../PROTOCOL.md#42-server--client) |
| `holo.spawn` | 1.0 | Create a holographic object (the Holographic Object payload). | [§5.7](../PROTOCOL.md#57-holospawn) |
| `holo.update` | 1.0 | Patch props/transform of an existing object (partial). | [§5.8](../PROTOCOL.md#58-holoupdate) |
| `holo.destroy` | 1.0 | Remove an object (with `fade_ms`). | [§5.9](../PROTOCOL.md#59-holodestroy) |
| `holo.layout` | 1.0 | Batch arrange/anchor multiple objects (arc/grid/stack/free). | [§5.10](../PROTOCOL.md#510-hololayout) |
| `server.error` | 1.0 | Server-side error (`code` + human `message`). | [§5.13](../PROTOCOL.md#513-errors--servererror--clienterror) |
| `server.settings` | **1.1** | Current settings + provider catalog. **Never** returns an API key (`key_set` boolean only). | [§5.15](../PROTOCOL.md#515-settings--clientsettings_get--clientsettings_update--serversettings-v11) |

### Server → Client — perception (v1.1)

| `type` | Purpose | Spec |
| ------ | ------- | ---- |
| `perception.request` | Start/stop/snapshot (`once`)/adjust (`set`) a perception stream — pull-based, privacy-gated. | [§8.4](../PROTOCOL.md#84-payload-schemas) |
| `agent.observation` | What Jarvis perceives, with optional spatial `annotations` (realized as perception widgets). | [§8.4](../PROTOCOL.md#84-payload-schemas) |

---

## Error codes

Carried in `server.error` / `client.error` (`{ code, message, fatal }`):

| Code | When |
| ---- | ---- |
| `bad_envelope` | Frame isn't a valid v1 envelope. |
| `unsupported_version` | Incompatible major protocol version. |
| `unknown_type` | Unrecognized `type` (normally ignored, not errored). |
| `unknown_widget` | `widget_type` not in the catalog. |
| `invalid_props` | Props failed schema validation. |
| `tool_failed` | A tool raised during a turn. |
| `internal` | Unexpected server error. |
| `invalid_settings` · `provider_unavailable` · `invalid_key` | Settings update failures (v1.1, §5.15). |

See [§5.13](../PROTOCOL.md#513-errors--servererror--clienterror) and the
[`ErrorCode`](../../agent-backend/jarvis_backend/protocol.py) constants.

---

## Notes

- **A turn ends with `agent.thinking{stage:"done"}`** so clients/harness can detect
  completion (see the [§7 reference turn](../PROTOCOL.md#7-reference-example-one-turn)).
- **Anchors** are `world | head | hand_left | hand_right | surface`; **interactions**
  are `tap | grab | release | drag | slider | toggle | resize | dwell`
  ([§5.6](../PROTOCOL.md#56-the-holographic-object)).
- **Perception is negotiated**: the client advertises capabilities in `client.hello`,
  the server pulls streams with `perception.request`
  ([§8](../PROTOCOL.md#8-multimodal-perception-v11--additive-optional-negotiated)).

## See also

- [Protocol reference (`docs/PROTOCOL.md`)](../PROTOCOL.md) — the full contract.
- [shared-protocol](../components/shared-protocol.md) — Python/C#/TS bindings + schemas.
- [Widget catalog (`docs/HOLO_TOOLS.md`)](../HOLO_TOOLS.md) — payloads for `holo.spawn`.
- [Concepts: the agent loop](../concepts/agent-loop.md) · [perception](../concepts/perception.md).
