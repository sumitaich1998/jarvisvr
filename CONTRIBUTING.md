# Contributing to JarvisVR

First off — **thank you!** 🙏 JarvisVR is an ambitious, open, spatial-AI project and it gets better
with every contributor. This guide covers how to set up each component, run its tests, and land a PR.

JarvisVR is a **monorepo** of independent components glued together by one versioned WebSocket
protocol. You can work on a single component in isolation — the whole stack runs **offline** on
deterministic mock providers, so you need no API keys and no Quest hardware to contribute.

- New here? Good first issues are labeled [`good first issue`](https://github.com/sumitaich1998/jarvisvr/issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22).
- Please be respectful — we follow the [Code of Conduct](./CODE_OF_CONDUCT.md).
- Security issue? Do **not** open a public issue — see [`SECURITY.md`](./SECURITY.md).

## Table of contents

- [Ways to contribute](#ways-to-contribute)
- [Repository layout](#repository-layout)
- [Prerequisites](#prerequisites)
- [Per-component dev setup & tests](#per-component-dev-setup--tests)
- [Run everything at once](#run-everything-at-once)
- [Protocol-first workflow](#protocol-first-workflow)
- [Adding a hologram widget](#adding-a-hologram-widget)
- [Coding style](#coding-style)
- [Pull request process](#pull-request-process)

## Ways to contribute

- 🐛 **Report bugs** and 💡 **request features** via the [issue templates](https://github.com/sumitaich1998/jarvisvr/issues/new/choose).
- 📝 **Improve docs** — `README.md`, `ARCHITECTURE.md`, and everything under `docs/`.
- 🧪 **Add tests** — especially protocol-conformance and widget-schema cases.
- 🪟 **Add a widget** to the catalog (see [below](#adding-a-hologram-widget)).
- 🔌 **Add an LLM provider** or voice/perception engine behind the existing interfaces.
- 🎨 **Build Unity prefabs / renderers** for widgets in `unity-client/`.

## Repository layout

| Path | Language | Test runner |
| ---- | -------- | ----------- |
| `agent-backend/` | Python 3.11 | `pytest` |
| `voice-service/` | Python 3.11 | `pytest` |
| `holo-tools/` | Python 3.9+ | `pytest` |
| `shared-protocol/python/` | Python 3.9+ | `pytest` |
| `shared-protocol/typescript/` | TypeScript (Node 20) | `vitest` |
| `infra/e2e/` | Python | `pytest` (drives the mock backend) |
| `unity-client/` | C# / Unity 2022 LTS | built **locally** (not in CI) |

## Prerequisites

- **Python 3.11** (the backend & voice service require ≥ 3.11; the protocol & holo-tools work on 3.9+).
- **Node.js 20** + npm (for the TypeScript protocol bindings).
- **Docker** (optional) — to run the stack via `infra/docker-compose.yml`.
- **Unity 2022.3 LTS** + the **Meta XR SDK** (only if you work on `unity-client/`).
- `make` and `bash` for the convenience scripts in `infra/`.

Each Python component is isolated in its own virtualenv. Create one per component you touch.

## Per-component dev setup & tests

### `agent-backend/` — the LLM agent "brain"

```bash
cd agent-backend
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"        # base deps + pytest + pytest-asyncio
pytest                          # the test suite (currently 89 tests)
```

Run the server locally (offline mock provider): `python -m jarvis_backend`. Configure a real LLM
provider with `jarvis-backend setup` (or copy `.env.example` → `.env`). Optional extras:
`pip install -e ".[openai]"`, `".[anthropic]"`, or `".[providers]"` (LiteLLM, unlocks ~all providers).

### `voice-service/` — wake word + STT + TTS + ambient hearing

```bash
cd voice-service
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"        # light base deps + pytest
pytest                          # the test suite (currently 73 tests)
```

Heavy engines are optional extras (`.[recommended]`, `.[stt-whisper]`, `.[tts-piper]`, …); the
service falls back to no-dependency offline engines so tests run headless.

### `holo-tools/` — widget catalog, tool schemas, validators

```bash
cd holo-tools
python -m venv .venv && source .venv/bin/activate
pip install -e ".[test]"       # + jsonschema + pytest
pytest                          # the test suite (currently 655 tests)
```

`registry.json` is the **single source of truth**. After editing it, regenerate the derived files
(see [Adding a hologram widget](#adding-a-hologram-widget)).

### `shared-protocol/python/` — Python protocol bindings

```bash
cd shared-protocol/python
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest                          # the test suite (currently 96 tests)
```

### `shared-protocol/typescript/` — TypeScript protocol bindings

```bash
cd shared-protocol/typescript
npm install
npm run typecheck               # tsc --noEmit
npm run build                   # tsc -> dist/
npm test                        # vitest run (currently 32 tests)
```

### `infra/e2e/` — end-to-end protocol conformance harness

The harness boots the dependency-light **mock backend** and drives a scripted conversation
(including a multimodal vision turn, barge-in, and settings), asserting every received frame is
protocol-conformant.

```bash
cd infra
make e2e                        # starts the mock + runs the harness (recommended)
```

…or run the pytest version directly:

```bash
cd infra
python -m venv .venv && source .venv/bin/activate
pip install -e "../shared-protocol/python[dev]"
pip install -r e2e/requirements.txt
export JARVIS_PROTOCOL_SCHEMA_DIR="$(pwd)/../shared-protocol/schema"
pytest e2e                       # currently 6 tests
```

### `unity-client/` — Quest 3 MR shell

Open the folder in **Unity 2022.3 LTS**, import the **Meta XR All-in-One SDK**, and follow
[`unity-client/README.md`](./unity-client/README.md). The client compiles even before the Meta SDK is
imported. **Unity is built locally and is intentionally not part of CI.** Point its `JarvisConfig`
asset at a running backend (`make install` / `docker compose up`, or the `infra` mock) and **Build &
Run** to a headset, or test in the editor over Quest Link.

## Run everything at once

From the repository root:

```bash
make test        # run every component's test suite (Python + TypeScript + e2e)
make lint        # lint / typecheck everything (best-effort)
make help        # list all targets
```

`infra/` also has its own targets — `make -C infra help` (`install`, `up`, `down`, `mock`, `e2e`,
`config`, …).

## Protocol-first workflow

The protocol is the contract every component obeys. When a change touches the wire format, do it in
this order so the components never drift:

1. **Spec** — edit [`docs/PROTOCOL.md`](./docs/PROTOCOL.md). If a message shape changes, bump
   `PROTOCOL_VERSION` in the same change.
2. **Schema & bindings** — update `shared-protocol/schema/` (the JSON Schema source of truth) and the
   Python / C# / TypeScript bindings to match.
3. **Catalog** — if the change is widget-related, update `holo-tools/registry.json` and regenerate
   `tools.json` + `docs/HOLO_TOOLS.md`.
4. **Components** — implement in `agent-backend/`, `voice-service/`, and/or `unity-client/`.
5. **Validate** — run `make -C infra e2e`; add/extend a conformance case in `infra/e2e/` for new
   message types. Keep `docs/ARCHITECTURE.md` and `docs/FEATURES.md` accurate.

## Adding a hologram widget

1. Add an entry to `holo-tools/registry.json` with a `props_schema` (JSON Schema draft 2020-12,
   `additionalProperties: false`) and a valid `example_props`.
2. Regenerate the derived artifacts from `holo-tools/`:

   ```bash
   python -c "import json, holo_tools as ht; open('tools.json','w').write(json.dumps(ht.derive_tools(ht.REGISTRY), indent=2, ensure_ascii=False) + '\n')"
   python scripts/generate_docs.py        # regenerates ../docs/HOLO_TOOLS.md
   ```

3. Add the TypeScript types in `holo-tools/ts/widgets.ts`.
4. Build the Unity prefab named by `prefab_id` in `unity-client/` (or rely on the procedural renderer).
5. `pytest` in `holo-tools/` — every schema and example must validate.

## Coding style

- **Python** — type hints, small focused functions, and `from __future__ import annotations`. We lint
  with **ruff** when available (`make -C infra lint`); please keep imports tidy and avoid dead code.
- **TypeScript** — strict `tsc` must pass (`npm run typecheck`); ESM modules; prefer explicit types at
  module boundaries.
- **C# / Unity** — follow standard Unity conventions; keep Meta-SDK-specific code behind the existing
  assembly defines so the project still compiles without the SDK.
- **Naming** — protocol `type`s, `widget_type`s, and all payload/prop keys are `snake_case`.
- **Comments** — explain *why*, not *what*. Don't narrate the code.
- **Commits** — present-tense, imperative subject lines (e.g. "add live_caption widget"). Keep them
  scoped and reviewable.

## Pull request process

1. **Fork** the repo and create a topic branch off `main`.
2. Make your change with tests. Run the affected component's suite **and** `make lint` locally.
3. If you touched the protocol, run `make -C infra e2e`.
4. Update docs/`CHANGELOG.md` if your change is user-facing.
5. Open a PR using the [template](./.github/PULL_REQUEST_TEMPLATE.md); link related issues and explain
   the *why*. Keep PRs focused — smaller is easier to review.
6. Ensure **CI is green** (every component job must pass). A maintainer will review and merge.

By contributing, you agree that your contributions are licensed under the project's
[MIT License](./LICENSE).

Happy hacking — and welcome to JarvisVR. 🚀
