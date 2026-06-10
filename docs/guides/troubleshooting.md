# Guide: Troubleshooting

Common problems and fixes, grouped by area. JarvisVR is built to **degrade
gracefully** — a missing key, SDK, registry, or device feature logs a warning and
falls back to an offline path rather than crashing. So most "it's not working"
moments are really "it quietly fell back to the mock/offline behavior." This page
tells you how to spot and fix each one.

> Quick triage: read the backend startup line and `config.summary()` in the logs —
> they show the resolved `llm`, `model`, `vision`, `registry`, and `data_dir`.

---

## LLM provider & keys

### "It answers, but with canned/deterministic replies" (no API key → mock fallback)

**Cause:** with no provider configured, `JARVIS_LLM` defaults to `mock` — a
deterministic offline planner. That's by design (the whole stack is demoable with no
key), but it's not a real LLM.

**Fix:** configure a provider. The startup log shows `LLM provider: mock` when you're
on the mock.

```bash
jarvis-backend setup                 # pick a provider, enter the key (masked)
# or:
JARVIS_LLM=openai OPENAI_API_KEY=sk-… python -m jarvis_backend
```

### Provider falls back to mock even though I set `JARVIS_LLM`

The server **never crashes** on a bad provider — it logs a warning and uses `mock`.
Look for:

```
provider 'openai' unavailable (OPENAI_API_KEY not set); falling back to mock.
```

Common causes and fixes:

| Symptom in the log | Cause | Fix |
| ------------------ | ----- | --- |
| `<KEY> not set` | The provider's key env var is empty | Set `OPENAI_API_KEY` / `GROQ_API_KEY` / … (or `JARVIS_LLM_API_KEY`) |
| `openai SDK not installed` | Native SDK missing | `pip install -e ".[openai]"` (or `.[anthropic]`) |
| `litellm not installed (pip install '.[providers]')` | LiteLLM-only provider without the extra | `pip install -e ".[providers]"` |
| `base_url is required` | Local/custom provider with no base URL | Set `JARVIS_<ID>_BASE_URL` (e.g. `JARVIS_OLLAMA_BASE_URL`) |

Confirm a key works before launching:

```bash
jarvis-backend setup --provider openai --validate     # makes one tiny live call
```

If validation prints `fell back to mock (missing key/SDK — install '.[providers]'?)`,
you're missing the extra or the key.

### LiteLLM-only providers (`azure`, `bedrock`, `vertex`, `cohere`) don't work

These route **only** through the LiteLLM universal adapter, which is an optional
dependency:

```bash
pip install -e ".[providers]"      # a.k.a. ".[llm]"
```

`bedrock` uses AWS credentials in the environment; `vertex` uses Google ADC; `azure`
needs `AZURE_API_KEY` + a base URL. Without the extra they fall back to mock.

### In-headset settings update returns an error

`client.settings_update` can return a `server.error` with:

- `provider_unavailable` — unknown provider id (see
  `server.settings.llm.providers[]`).
- `invalid_settings` — malformed payload (e.g. non-string `model`).
- `invalid_key` — only when live validation is on (`JARVIS_SETTINGS_VALIDATE=1`) and
  the key looks like an auth failure.

The provider still **hot-swaps** between turns; if the new provider is missing its
key/SDK it silently uses mock (and `key_set` reflects whether a key is *stored*, not
whether it works).

---

## Networking & connection

### Port 8765 is already in use

```
OSError: [Errno 48] Address already in use
```

**Fix:** stop the other process, or move the port.

```bash
# Find & stop whatever holds 8765:
lsof -i :8765            # macOS/Linux — note the PID, then: kill <PID>

# …or run the backend on a different port:
JARVIS_PORT=8788 python -m jarvis_backend
```

For the e2e harness this is a non-issue — `make e2e` auto-picks a **free port** for
the local mock. To point the harness at a backend on another port, use
`JARVIS_BACKEND_URL=ws://127.0.0.1:<port>/jarvis`.

### Unity client can't connect / instant reconnect loop

Almost always the **host/port** or **network**:

- On a Quest over Wi-Fi, use your dev machine's **LAN IP** (e.g. `192.168.1.50`),
  **not** `127.0.0.1`. In-editor over Quest Link, `127.0.0.1` is fine.
- Set `host`/`port`/`path` on the **`JarvisConfig`** asset (default port `8765`,
  path `/jarvis`).
- Make sure the backend is actually running and reachable: `python -m jarvis_backend`
  binds `0.0.0.0:8765` by default. Test from the headset's network with
  `websocat ws://<host>:8765/jarvis`.
- Enable **`logTraffic`** on `JarvisConfig` to log every inbound/outbound envelope to
  the Unity Console.

### Cleartext `ws://` blocked on device

Android blocks cleartext by default. Either allow cleartext to your host (the Meta
Project Setup Tool / AndroidManifest), or use **`wss://`** (set the **Use Tls**
toggle on `JarvisConfig` and terminate TLS at a reverse proxy — see
[Deploy](./deploy.md#tls--wss-and-authentication)). Cleartext to a LAN IP is typical
for local dev.

---

## Perception (camera, audio, gaze)

### No vision frames on device / "what is this?" sees nothing

- **Camera permission not granted.** The passthrough camera needs
  `horizonos.permission.HEADSET_CAMERA` **and** `android.permission.CAMERA`, granted
  at runtime and enabled in Player Settings / the Meta Project Setup Tool. Check the
  **capture indicator** and the Unity Console.
- **Wrong camera device.** The `visionCameraNameHint` on `JarvisConfig` (default
  `"passthrough"`) must match the device name. In the editor the default webcam (or a
  synthetic frame) is used so the pipeline is still testable.
- **Perception disabled on the backend.** `JARVIS_PERCEPTION=0` turns the whole
  feature off — set it back to `1` (the default).

The **mock** vision path always "sees" deterministically offline (it synthesizes a
scene description), so vision Q&A works with no camera at all when you feed
`perception.scene_objects` or run the e2e multimodal scenario.

### Capture indicator stuck on / camera won't turn off

Capture is **pull-based** and privacy-gated. It stops when the backend sends
`perception.request{stop}` (it does this after a one-shot vision turn), when the
thermal/fps guard trips, or via the wrist menu's **Stop capture** kill switch. If
you said *"watch the room"*, you're in **continuous** mode — say *"stop watching"*.

### Headless / CI: audio engine errors

The voice-service is built to run **headless with no audio hardware**. If you see
errors about microphones, speakers, or missing engines:

- You don't need the heavy extras to run tests — the base install falls back to
  **no-dependency offline engines** (`EnergyFallback` wake word, `MockSTT`, `MockTTS`,
  heuristic sound events). `pip install -e ".[dev]"` + `pytest` runs fully headless.
- The audio I/O extra (`.[audio]`, `sounddevice`) is **optional** — only install it
  when you actually have a mic/speaker. Without it the service still imports and the
  bridge runs.
- Real engines are opt-in: `.[recommended]`, `.[stt-whisper]`, `.[tts-piper]`,
  `.[wake-openwakeword]`, `.[sound-yamnet]`.

---

## Holograms & rendering (Unity)

| Symptom | Fix |
| ------- | --- |
| Holograms invisible in a build | Add the URP/Standard shader used by `HoloMaterials` to **Project Settings ▸ Graphics ▸ Always Included Shaders** (see `unity-client/Assets/JarvisVR/SETUP.md`). |
| Text not rendering | Import **TMP Essentials** (Window ▸ TextMeshPro ▸ Import TMP Essential Resources). |
| No passthrough / black background | Enable Passthrough in OVRManager/OpenXR and set the camera clear to transparent per `SETUP.md`. |
| A widget shows as a labelled placeholder + `unknown_widget` | The `widget_type` isn't in the client's `WidgetRegistry` or procedural `WidgetCatalog`. Add a renderer — see [Add a widget](./add-a-widget.md). |

### Backend rejects a spawn with `invalid_props` / `unknown_widget`

The agent validates `widget_type` + `props` against the catalog before emitting
`holo.spawn`. An `unknown_widget` means the type isn't in `registry.json` (or the
fallback); `invalid_props` means the props don't match the widget's closed schema
(wrong type, missing required key, or an extra key). Fix the tool's `props` to match
[`holo-tools/registry.json`](../../holo-tools/registry.json), or validate locally:

```python
import holo_tools as ht
ht.validate_widget("weather_orb", {"city": "Tokyo", "temp_c": 18, "condition": "clouds"})
```

---

## Catalog & schema

### Backend logs "registry.json not found; using built-in fallback catalog"

The backend couldn't find `holo-tools/registry.json`, so it's using a smaller
built-in catalog. That's fine for demos, but to validate against the **real** widget
schemas, point it at the file:

```bash
JARVIS_HOLO_REGISTRY=../holo-tools/registry.json python -m jarvis_backend
```

In Docker, mount the catalog at `/holo-tools/registry.json` (the Dockerfile default).

### "Could not locate shared-protocol/schema"

The protocol bindings find the schemas by upward search; pin them explicitly:

```bash
export JARVIS_PROTOCOL_SCHEMA_DIR=/abs/path/to/shared-protocol/schema
```

The `infra/` scripts export this for you automatically.

---

## Docker & infra

| Symptom | Cause / fix |
| ------- | ----------- |
| `docker compose` / `docker-compose` not found | The local mock path needs **no Docker** — use `make e2e` / `make test`. To just syntax-check compose: `python -c "import yaml; yaml.safe_load(open('docker-compose.yml'))"`. |
| `compose up` fails to build | The sibling Dockerfiles (`../agent-backend`, `../voice-service`) may not be built yet. Use `make mock` for a self-contained brain. |
| Port 8765 in use under compose | Stop the other process, or change the host mapping in `docker-compose.yml`. |
| e2e harness prints holo-tools **warnings** | If a widget lacks a recognizable props schema, props validation is skipped with a warning (membership is still enforced). Use `E2E_STRICT_PROPS=1` to turn drift into a hard failure. |

---

## Still stuck?

- Turn up logging: `JARVIS_LOG_LEVEL=DEBUG` (and `JARVIS_LOG_JSON=1` for structured
  logs).
- Reproduce on the **mock** to isolate whether it's the provider, the protocol, or
  the client.
- Check the component READMEs and the [FAQ](../faq.md).
- File a [bug report](https://github.com/sumitaich1998/jarvisvr/issues/new/choose) (replace
  `sumitaich1998/jarvisvr`); for security issues see [`SECURITY.md`](../../SECURITY.md).

## See also

- [Add an LLM provider](./add-an-llm-provider.md) · [Deploy](./deploy.md) ·
  [Testing](./testing.md)
- [Environment variables reference](../reference/env-vars.md) · [CLI reference](../reference/cli.md)
- [unity-client README troubleshooting](../../unity-client/README.md#troubleshooting) ·
  [infra README troubleshooting](../../infra/README.md#troubleshooting)
