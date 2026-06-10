# infra

DevOps glue for JarvisVR: Docker Compose for the backend + voice services, dev
scripts, a self-contained **mock brain**, and an **end-to-end protocol-conformance
harness**. Covers **PROTOCOL v1.1 (Multimodal Perception)** — the mock serves a
`/vision` endpoint and a realtime vision turn, and the harness drives both the v1
conversation and a v1.1 multimodal scenario.

```
infra/
├── docker-compose.yml         # base stack: agent-backend (:8765) + voice-service
├── docker-compose.mock.yml    # override: swap agent-backend for the mock brain
├── docker-compose.gpu.yml     # override: GPU reservation for voice-service
├── .env.example               # copy to .env (git-ignored)
├── Makefile                   # up / down / mock / e2e / test / lint / fmt / config
├── mock-backend/              # WebSocket mock brain (implements PROTOCOL.md)
│   ├── server.py  · requirements.txt · Dockerfile
├── e2e/                       # conformance harness (pytest-wrapped)
│   ├── harness.py · holo_tools.py · conftest.py · test_conformance.py · requirements.txt
└── scripts/                   # dev_up · dev_down · mock · e2e · test · lint · fmt (+ _lib.sh)
```

## Prerequisites

- **Docker** (with `docker compose` v2 *or* legacy `docker-compose`) — for the stack.
- **Python 3.9+** — for the mock brain, harness, and the `jarvis-protocol` binding.
- **Node 18+** (optional) — only for the TypeScript protocol tests.

> The mock brain and the e2e harness run **without Docker** (pure Python venv), so
> you can validate protocol conformance even if the sibling images aren't built.

## Quickstart

### Option A — local mock + conformance (no Docker, fastest)

```bash
make e2e          # creates infra/.venv, starts the mock brain, runs the harness
```

You should see `RESULT: PASS ✅`. The harness exits non-zero on any violation.

### Option B — mock brain in Docker

```bash
make mock         # docker compose -f docker-compose.yml -f docker-compose.mock.yml up --build agent-backend
# in another shell:
JARVIS_BACKEND_URL=ws://127.0.0.1:8765/jarvis make e2e
```

### Option C — the real stack

```bash
make up           # docker compose up --build -d   (needs ../agent-backend, ../voice-service)
make down
```

## What the e2e harness does

`e2e/harness.py` is a mock WS client that connects (to the mock by default,
`--url`/`JARVIS_BACKEND_URL` for any backend) and drives a scripted conversation:

1. `client.hello` → `server.hello_ack` (captures the session)
2. `client.heartbeat` → `server.heartbeat`
3. **"show me the weather in tokyo"** → `agent.thinking*` + `agent.speech` + `holo.spawn` (weather_orb) → `client.ack`
4. **"start a 5 minute timer"** → `agent.thinking*` + `agent.speech` + `holo.spawn` (timer) → `client.ack`
5. **tap the timer** (`client.interaction`) → `holo.update`
6. `client.bye`

It then runs a **v1.1 multimodal scenario**:

1. opens `/vision` and sends one **§8.2 length-prefixed binary** vision frame
2. `client.hello` (with `camera_passthrough`) → `server.hello_ack`
3. streams `perception.vision_frame` (inline base64) + `perception.scene_objects`
4. **"what is this on my desk?"** (`user.voice_transcript`, `attach_perception:true`)
5. asserts the vision turn: `perception.request{start}` → `agent.thinking{perceiving}`
   → `agent.observation` → `holo.spawn vision_annotation` → `agent.speech`
   → `perception.request{stop}`

For **every received frame** it calls `jarvis_protocol.validate(...)` (the shared
binding → the JSON Schemas in `shared-protocol/schema`). For every `holo.spawn` it
also validates the object against `holo-tools/registry.json` **if present**:
`widget_type` membership is a hard check **except** for in-flight v1.1 perception
widgets (`vision_annotation`, `bounding_box_3d`, `live_caption`, `vision_feed`,
`scene_label`) — if one isn't in the registry yet it's a logged **note**, not a
failure (structural `holo_object` validation still applies). Props-schema
mismatches are warnings by default, or hard failures with `E2E_STRICT_PROPS=1`.

`pytest e2e/` wraps all of this — `conftest.py` boots the mock on a free port,
runs both scenarios, and asserts zero violations. `make e2e` runs both via the CLI.

## The mock brain

`mock-backend/server.py` is a dependency-light WebSocket server that implements
PROTOCOL.md on `/jarvis`. It **reuses the `jarvis_protocol` binding** to build and
**self-validate every frame before sending**, so it can never emit a
non-conformant message. It reads `holo-tools/registry.json` when available (to
pick known `widget_type`s) and otherwise falls back to built-in widgets.

**v1.1 perception:** the mock also serves the **`/vision`** endpoint (ingests
§8.2 length-prefixed binary frames; validates each JSON header as a
`perception.vision_frame`) and accepts inline `perception.vision_frame` plus the
other `perception.*` messages on `/jarvis`, keeping a rolling per-connection
perception buffer. When the user asks a vision question (e.g. *"what is this?"*) —
or sends a turn with `attach_perception:true` and a buffered frame — it runs a
**multimodal turn**: `perception.request{vision,start}` →
`agent.thinking{perceiving}` → `agent.observation` (narration + annotation) →
`holo.spawn vision_annotation` (world-anchored, billboard) → `agent.speech` →
`perception.request{vision,stop}` (camera off for privacy/battery). `/vision`
shares port **8765** with `/jarvis`, so no extra port mapping is needed.

## Environment & ports

Copy `.env.example` → `.env` (the scripts do this automatically; `.env` is
git-ignored). Compose passes it to containers via `env_file`.

| Service        | Port (host:container) | Endpoint                       |
| -------------- | --------------------- | ------------------------------ |
| agent-backend  | `8765:8765`           | `ws://localhost:8765/jarvis` + `ws://localhost:8765/vision` (v1.1) |
| voice-service  | internal only         | dials `ws://agent-backend:8765/jarvis` |

> The v1.1 `/vision` binary transport is a **path on the same `8765` port**, so the
> existing `8765:8765` mapping already exposes it — no compose change required.

Key env vars (see `.env.example`): `JARVIS_HOST`, `JARVIS_PORT`, `JARVIS_WS_PATH`,
`JARVIS_LLM` (`mock`/`openai`/`anthropic`/`gemini`/… — 20+ providers), `OPENAI_API_KEY`,
`ANTHROPIC_API_KEY`, `JARVIS_HOLO_REGISTRY`, `JARVIS_VISION`, `JARVIS_BACKEND_URL`,
`JARVIS_WAKE`, `JARVIS_STT`, `JARVIS_TTS`.

## Make targets

| Target | Description |
| ------ | ----------- |
| `make up` / `make down` | Start / stop the real stack |
| `make mock`   | Start the mock brain in Docker |
| `make e2e`    | Start the mock locally and run the conformance harness |
| `make test`   | Run the shared-protocol test suites (Python + TypeScript) |
| `make lint`   | Lint / typecheck (ruff or byte-compile; `tsc --noEmit`) |
| `make fmt`    | Autoformat (ruff / prettier, if installed) |
| `make config` | Validate the compose files |
| `make clean`  | Remove `.venv` and TS build artifacts |

## GPU (optional)

Layer the GPU override (needs the NVIDIA Container Toolkit):

```bash
docker compose -f docker-compose.yml -f docker-compose.gpu.yml up --build
```

(or uncomment the `deploy:` block in `docker-compose.yml`).

## Troubleshooting

- **`docker compose` / `docker-compose` not found** — the local mock path
  (`make e2e`, `make test`) needs no Docker. To validate compose without the
  binary: `python -c "import yaml; yaml.safe_load(open('docker-compose.yml'))"`.
- **`compose up` fails to build** — the sibling Dockerfiles (`../agent-backend`,
  `../voice-service`) are owned by other teams and may not exist yet. Use
  `make mock` for a self-contained brain meanwhile.
- **Port 8765 already in use** — stop the other process, or point the harness
  elsewhere with `JARVIS_BACKEND_URL`. `make e2e` auto-picks a free port for the
  local mock.
- **`Could not locate shared-protocol/schema`** — set
  `JARVIS_PROTOCOL_SCHEMA_DIR=/abs/path/to/shared-protocol/schema` (the scripts
  export this for you).
- **holo-tools warnings in the harness** — if `holo-tools/registry.json` lacks a
  recognizable props schema for a widget, props validation is skipped with a
  warning (membership is still enforced).

## Integration notes / assumptions

- Targets the exact paths/names other teams committed to: service `agent-backend`
  (port `8765`, WS path `/jarvis`), service `voice-service`, and
  `holo-tools/registry.json`.
- `voice-service` uses `depends_on: condition: service_started` (not
  `service_healthy`) so it still starts if the sibling image lacks the Python TCP
  healthcheck baked into the base file.
- The mock's emitted props are aligned to `holo-tools/registry.json`
  (`weather_orb`, `timer`, `panel`). If that registry's prop schemas change,
  re-run `E2E_STRICT_PROPS=1 make e2e` to catch drift and update
  `mock-backend/server.py`.
