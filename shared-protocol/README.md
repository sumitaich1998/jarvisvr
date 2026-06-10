# shared-protocol

Canonical bindings for the **JarvisVR wire protocol (v1.1)** — the WebSocket
contract from [`docs/PROTOCOL.md`](../docs/PROTOCOL.md). One set of JSON Schemas
is the **single source of truth**; the Python, C#, and TypeScript bindings are
thin, hand-written mirrors plus validators that load those exact schemas.

> **v1.1 adds Multimodal Perception (§8)** — sight/hearing/attention. It is
> additive and backward-compatible: the wire `v` accepts both `"1.1.0"` and
> `"1.0.0"`, so v1.0 clients keep working. See [v1.1 Multimodal Perception](#v11-multimodal-perception) below.

```
shared-protocol/
├── schema/        # JSON Schema (draft 2020-12) — THE SOURCE OF TRUTH
├── python/        # pip package `jarvis-protocol` (pydantic v2 + jsonschema)
├── csharp/        # JarvisVR.Protocol DTOs + Newtonsoft (de)serializer (Unity drop-in)
├── typescript/    # npm package `@jarvisvr/protocol` (types + Ajv validators)
└── README.md
```

`protocol.version` is **`1.1.0`** (accepts `1.0.0` too) — pinned in
`schema/version.json` (`protocol_version` + `supported_versions`),
`jarvis_protocol.PROTOCOL_VERSION` / `SUPPORTED_VERSIONS`,
`JarvisVR.Protocol.Protocol.Version` / `SupportedVersions`, and
`PROTOCOL_VERSION` / `SUPPORTED_VERSIONS` (TS). Bump all in lock-step with the schemas.

## Why schemas first

Every component (`unity-client`, `agent-backend`, `voice-service`, the e2e
harness) validates against the **same** files in `schema/`. Each binding:

1. Locates `schema/` (env var `JARVIS_PROTOCOL_SCHEMA_DIR`, else an upward search).
2. Registers every schema by its `$id` so cross-file `$ref`s resolve
   (`common.schema.json#/$defs/transform`, `holo.spawn` → `holo_object`, …).
3. Validates a message in two steps: the **envelope** (`schema/envelope.schema.json`,
   strict — `additionalProperties:false`) then the **payload** against the schema
   for that `type` (see `schema/<type>.schema.json`).

### Validation semantics (identical across languages)

| Rule | Behavior |
| ---- | -------- |
| Envelope | Exactly `v,id,type,ts,payload` (+ optional `session`, `reply_to`). `v` is `enum ["1.0.0","1.1.0"]`. |
| `id` / `session` / `object_id` | Any non-empty string (the §7 example uses `"a1"`, `"S"`, `"O1"` — **not** UUIDs), so UUID format is **not** enforced. |
| Payload fields | Required/typed fields enforced; **extra keys allowed** (PROTOCOL.md §2: receivers ignore unknown payload keys). |
| Unknown `type` | Tolerated by default (forward-compatible). Pass `allow_unknown_types=False` / `{ allowUnknownTypes: false }` to flag them. |
| Decode | Lenient (drops unknown envelope keys). Use `validate()` for the strict gate. |

## Schema files

`envelope` · `common` (`$defs`: vec3, quat, bbox, anchor, interaction, pose, camera,
vision_format, perception_stream, thermal, transform, text_input) · `holo_object` ·
`client.hello` · `server.hello_ack` · `user.text` / `user.voice_transcript` /
`user.voice_partial` · `agent.thinking` · `agent.speech` · `agent.transcript` ·
`holo.spawn` / `holo.update` / `holo.destroy` / `holo.layout` · `client.interaction` ·
`client.scene` · `client.ack` · `client.bye` · `client.barge_in` · `heartbeat` ·
`error` (shared by `server.error` + `client.error`).

**v1.1 perception:** `perception.vision_frame` · `perception.audio_event` ·
`perception.audio_scene` · `perception.gaze` · `perception.scene_objects` ·
`perception.state` · `perception.request` · `agent.observation`.

## v1.1 Multimodal Perception

v1.1 (PROTOCOL.md §8) gives Jarvis sight/hearing/attention. Additions, all
mirrored across Python/C#/TS and validated by the schemas:

- **Envelope**: `v` now accepts `"1.1.0"` and `"1.0.0"`.
- **`client.hello.capabilities`**: `camera_passthrough`, `ambient_audio`,
  `eye_tracking`, `on_device_vision`, `depth`.
- **`agent.thinking.stage`**: adds `perceiving`, `looking`.
- **`user.text` / `user.voice_transcript`**: optional `attach_perception` (bool).
- **New messages**: `perception.vision_frame` (RGB frame + pose),
  `perception.audio_event`, `perception.audio_scene`, `perception.gaze`,
  `perception.scene_objects`, `perception.state` (client→server);
  `perception.request` (start/stop/once/set a stream) and `agent.observation`
  (narration + spatial `annotations`) (server→client).
- **New enums**: `Camera` (`rgb_left|rgb_right|rgb_center`), `VisionFormat`,
  `VisionTransport` (`inline|binary`), `PerceptionStream`, `PerceptionAction`,
  `GazeSource`, `Speaker`, `Thermal`.
- **`/vision` binary transport (§8.2)**: `[4B BE len][JSON header][image bytes]`,
  where the header is a `perception.vision_frame` payload with `transport:"binary"`
  and no `data`. The bindings validate that header object like any other payload;
  the framing itself is handled by transports (see `infra/mock-backend`).

```python
from jarvis_protocol import new_message, validate, MessageType, VisionFrame, Pose, AgentObservation, Annotation
frame = new_message(MessageType.PERCEPTION_VISION_FRAME,
    VisionFrame(frame_id="F1", camera="rgb_center", format="jpeg", transport="inline",
                data="/9j/4AAQ", pose=Pose(position=[0,1.6,0], rotation=[0,0,0,1])), session="S")
validate(frame)   # conformant
```

The §8.6 realtime multimodal turn is validated end-to-end in both Python
(`tests/test_perception.py`) and TS (`test/perception.test.ts`).

---

## Python — `jarvis-protocol`

```bash
pip install -e shared-protocol/python[dev]   # editable; finds ../schema automatically
pytest shared-protocol/python                # round-trip + schema + §7 reference
```

```python
from jarvis_protocol import (
    new_message, encode, decode, validate, is_valid, parse_payload,
    MessageType, AgentSpeech, HoloObject, Transform, ProtocolValidationError,
)

msg  = new_message(MessageType.AGENT_SPEECH, AgentSpeech(text="Here's Tokyo.", final=True), session="S")
wire = encode(msg)        # compact JSON text frame; None fields omitted
validate(wire)            # raises ProtocolValidationError(.errors=[...]) if non-conformant
env  = decode(wire)       # -> Envelope
speech = parse_payload(env.type, env.payload)   # -> AgentSpeech
```

- `new_message(type, payload, session=None, *, reply_to=None, id=None, ts=None)` —
  fresh uuid `id`, epoch-ms `ts`; `payload` may be a dict or a pydantic model.
- `validate(msg)` / `is_valid(msg)` / `iter_errors(msg)` accept an `Envelope`, dict,
  JSON `str`, or `bytes`.

## C# — `JarvisVR.Protocol` (Unity)

Drop the `csharp/JarvisVR.Protocol/` folder into a Unity project that has
Newtonsoft.Json (`com.unity.nuget.newtonsoft-json`). No build step here; the DTOs
mirror the Python models.

```csharp
using JarvisVR.Protocol;

var spawn = new HoloObject {
    ObjectId = "O1", WidgetType = "weather_orb",
    Transform = new Transform { Anchor = Anchors.Head,
        Position = new[]{0.3f,0f,0.8f}, Rotation = new[]{0f,0f,0f,1f}, Scale = new[]{1f,1f,1f}, Billboard = true },
    Interactable = true, Interactions = new[]{ Interactions.Grab, Interactions.Tap },
};

Envelope msg = JarvisProtocol.NewMessage(MessageTypes.HoloSpawn, spawn, session: "S");
string wire  = JarvisProtocol.Encode(msg);                 // System.Guid id + epoch-ms ts
Envelope env = JarvisProtocol.Decode(wire);
HoloObject p = env.PayloadAs<HoloObject>();
```

`JarvisProtocol.Settings` omits nulls and ignores unknown members (forward-compatible).

## TypeScript — `@jarvisvr/protocol`

```bash
cd shared-protocol/typescript && npm install
npm test         # vitest: round-trip + §7 reference
npm run build    # tsc -> dist/
```

```ts
import { newMessage, encode, decode, validate, isValid, MessageType, type AgentSpeech } from "@jarvisvr/protocol";

const msg  = newMessage<AgentSpeech>(MessageType.AGENT_SPEECH, { text: "Here's Tokyo.", final: true }, "S");
const wire = encode(msg);
validate(wire);                 // throws ProtocolValidationError(.errors) if non-conformant
const env  = decode<AgentSpeech>(wire);
```

The validator is **Ajv** running the JSON Schemas directly (chosen over zod so the
schemas stay the single source of truth). Node reads the schemas from `../schema`
(or `JARVIS_PROTOCOL_SCHEMA_DIR`).

---

## Conformance & the e2e harness

`infra/e2e` imports the **Python** binding and calls `validate()` on every frame
of a scripted conversation, so the bindings here are exercised end-to-end against
`infra/mock-backend`. See [`../infra/README.md`](../infra/README.md).
