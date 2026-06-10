# Guide: Testing

JarvisVR is a monorepo of independent components glued by one versioned protocol.
Each component has its own test suite, and the [`infra/`](../../infra/) **e2e
conformance harness** validates the whole stack against the mock backend. Everything
runs **offline** — no API keys, no Quest hardware.

This guide shows the real commands: the one-shot `make` targets, each component's
suite, and the e2e harness (against the mock *and* a real backend).

---

## TL;DR — run everything

From the repository root:

```bash
make test        # every component: agent-backend, holo-tools, voice-service,
                 #   shared-protocol (Py + TS), and the infra e2e conformance
make lint        # byte-compile Python + typecheck TypeScript
make help        # list all targets
```

`make test` fans out to per-component targets (below). The root
[`Makefile`](../../Makefile) defines them; [`infra/Makefile`](../../infra/Makefile)
has its own (`make -C infra help`).

| Component | Language | Runner | Root target |
| --------- | -------- | ------ | ----------- |
| `agent-backend/` | Python 3.11 | `pytest` | `make test-backend` |
| `holo-tools/` | Python 3.9+ | `pytest` | `make test-holo` |
| `voice-service/` | Python 3.11 | `pytest` | `make test-voice` |
| `shared-protocol/python/` | Python 3.9+ | `pytest` | `make test-protocol` |
| `shared-protocol/typescript/` | Node 20 | `vitest` | `make test-protocol-ts` |
| `infra/e2e/` | Python | `pytest` (drives the mock) | `make test-e2e` |
| `unity-client/` | C# / Unity 2022 LTS | built locally (**not in CI**) | — |

---

## Per-component suites

Each Python component is isolated in its own virtualenv — create one per component
you touch.

### agent-backend — the LLM "brain"

```bash
cd agent-backend
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"          # base deps + pytest + pytest-asyncio
pytest                            # currently 89 tests
```

Covers: protocol envelope round-trip + validation, the mock agent producing a valid
`holo.spawn` for "show weather in tokyo", heartbeat echo, unknown-type-ignored, a
full streamed turn over a real socket, bad-envelope errors, the tools, and **v1.1**:
a vision turn (`agent.observation` + valid `vision_annotation`), `/vision` binary
ingest over a real socket, `perception.request` emission, sound events, the
perception buffer + binary codec, barge-in, settings, and a conformance test that
runs **every** perception/knowledge tool against the canonical
`holo-tools/registry.json` asserting zero `server.error`.

```bash
pytest tests/test_perception.py        # one file
pytest -k weather                       # one keyword
pytest -ra                              # show extra test summary (the default addopts)
```

### holo-tools — widget catalog, tool schemas, validators

```bash
cd holo-tools
python -m venv .venv && source .venv/bin/activate
pip install -e ".[test]"         # jarvis-holo-tools + jsonschema + pytest
pytest                            # currently 655 tests
```

Checks every `props_schema` is a valid draft-2020-12 schema, every widget's
`example_props` validates, good/bad props are accepted/rejected, holo objects
validate, and every tool in `tools.json` references a real `widget_type`.

### voice-service — wake word + STT + TTS + ambient hearing

```bash
cd voice-service
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"          # light base deps + pytest
pytest                            # currently 73 tests
```

Heavy engines are optional extras (`.[recommended]`, `.[stt-whisper]`,
`.[tts-piper]`, …); the service falls back to **no-dependency offline engines**, so
the suite runs **headless** with no models or audio hardware.

### shared-protocol (Python) — `jarvis-protocol`

```bash
cd shared-protocol/python
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest                            # currently 96 tests
```

Round-trips + schema validation + the `PROTOCOL.md` §7 reference turn (and the §8.6
multimodal turn). The binding finds `../schema` automatically (or set
`JARVIS_PROTOCOL_SCHEMA_DIR`).

### shared-protocol (TypeScript) — `@jarvisvr/protocol`

```bash
cd shared-protocol/typescript
npm install
npm run typecheck                # tsc --noEmit
npm run build                    # tsc -> dist/
npm test                          # vitest run — currently 32 tests
```

The validator is **Ajv** running the JSON Schemas directly (so the schemas stay the
single source of truth).

---

## End-to-end conformance harness

The harness in [`infra/e2e/`](../../infra/e2e/) boots the dependency-light **mock
backend** and drives scripted conversations, asserting **every received frame** is
protocol-conformant (it calls `jarvis_protocol.validate()` against the schemas in
`shared-protocol/schema`, and validates each `holo.spawn` against
`holo-tools/registry.json` when present).

### Run it (recommended)

```bash
cd infra
make e2e          # creates infra/.venv, starts the mock on a free port, runs the harness
```

You should see `RESULT: PASS ✅`. The harness exits non-zero on any violation.

### Run the pytest version directly

```bash
cd infra
python -m venv .venv && source .venv/bin/activate
pip install -e "../shared-protocol/python[dev]"
pip install -r e2e/requirements.txt
export JARVIS_PROTOCOL_SCHEMA_DIR="$(pwd)/../shared-protocol/schema"
pytest e2e                        # currently 6 tests; conftest boots the mock on a free port
```

The pytest suite ([`e2e/test_conformance.py`](../../infra/e2e/test_conformance.py))
runs four scenarios: the **scripted conversation** (weather + timer + a tap), a
**v1.1 multimodal vision turn** (`perception.request` → `agent.observation` →
`holo.spawn vision_annotation` → `agent.speech`), **barge-in** (§5.14), and
**settings** (§5.15, asserting no `api_key` ever leaks).

### What the scripted conversation does

1. `client.hello` → `server.hello_ack` (captures the session)
2. `client.heartbeat` → `server.heartbeat`
3. *"show me the weather in tokyo"* → `agent.thinking*` + `agent.speech` +
   `holo.spawn` (weather_orb) → `client.ack`
4. *"start a 5 minute timer"* → `agent.thinking*` + `agent.speech` + `holo.spawn`
   (timer) → `client.ack`
5. **tap the timer** (`client.interaction`) → `holo.update`
6. `client.bye`

### Strict props mode

By default a props-schema mismatch against `holo-tools/registry.json` is a warning.
Make it a hard failure to catch drift:

```bash
E2E_STRICT_PROPS=1 make e2e
```

### Against a real backend (not the mock)

Point the harness at any running backend with `--url` / `JARVIS_BACKEND_URL`:

```bash
# Terminal 1 — run a backend (real or the mock in Docker):
cd infra && make mock                 # or: cd agent-backend && python -m jarvis_backend

# Terminal 2 — drive the harness against it:
JARVIS_BACKEND_URL=ws://127.0.0.1:8765/jarvis make e2e
# or directly:
python infra/e2e/harness.py --url ws://127.0.0.1:8765/jarvis
```

This is the same harness used in CI and is the recommended check after any
protocol-touching change.

### Just the protocol suites (Py + TS)

```bash
make -C infra test        # runs shared-protocol Python (+ TypeScript if npm is present)
```

---

## Unity client

`unity-client/` is C# built **locally in Unity 2022.3 LTS** and is **intentionally
not part of CI**. The code compiles even before the Meta XR SDK is imported. To test
behavior, point its `JarvisConfig` at a running backend (`make mock` or the e2e
mock), press **Play** in the editor (desktop, no headset needed — left-click
holograms to send real `client.interaction`/`user.text`), or **Build & Run** to a
Quest. See the [unity-client README](../../unity-client/README.md).

---

## Continuous integration

CI runs every component job; a PR must be green to merge. If your change touches the
wire format, also run the e2e harness (`make -C infra e2e`) and add/extend a
conformance case in `infra/e2e/`. See the
[protocol-first workflow](../../CONTRIBUTING.md#protocol-first-workflow) in
`CONTRIBUTING.md`.

---

## See also

- [`CONTRIBUTING.md`](../../CONTRIBUTING.md) — per-component dev setup + the PR process.
- [infra deep-dive](../components/infra.md) · [`infra/README.md`](../../infra/README.md).
- [Troubleshooting](./troubleshooting.md) — when a suite or the harness won't start.
- [Message index](../reference/message-index.md) · [Protocol reference](../PROTOCOL.md).
