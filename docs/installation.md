# Installation

This page covers everything you need to install JarvisVR — from the five-minute
offline demo to a full build running on a real Meta Quest 3. If you just want to
*see it run*, the **[Getting Started](./getting-started.md)** guide is the
fast path; come back here when you want the complete prerequisites, per-OS notes,
optional extras, and the Unity-side setup.

JarvisVR is a multi-component system. You only need to install the pieces you
actually want to use:

| If you want to… | Install… |
| --- | --- |
| Run the offline demo / understand the protocol | **agent-backend** + **infra** (this page, §1–§3) |
| Hear and speak to it | add **voice-service** (§4) |
| Use a real LLM (OpenAI, Anthropic, local, …) | agent-backend + a key — see **[Configuration](./configuration.md)** |
| Run it in your room on a Quest 3 | add **unity-client** (§6) |

> **Honest status:** every component runs **fully offline** out of the box via
> deterministic mock providers. The Unity client is a complete project you build
> locally — there is **no prebuilt APK**, and the gallery imagery in the repo is a
> concept mockup, not a screenshot of a shipped build.

---

## 1. Prerequisites

| Tool | Version | Needed for | Notes |
| --- | --- | --- | --- |
| **Python** | **3.11+** | agent-backend, voice-service | The brain and ears/mouth are Python. |
| **Node.js** | **20+** | shared-protocol / infra TypeScript tests | Optional — only for the TS protocol bindings & tests. |
| **`make`** + POSIX shell | any | the `infra/` shortcuts | Preinstalled on macOS/Linux; on Windows use WSL2. |
| **Docker** + Compose v2 | recent | running the stack in containers | **Optional** — the mock brain & e2e harness run with no Docker. |
| **Unity** | **2022.3 LTS** (2022.3.40f1 used) | unity-client | With Android Build Support (OpenJDK + Android SDK & NDK). |
| **Meta XR SDK** | All-in-One (`com.meta.xr.sdk.all`) | unity-client | Imported from the Asset Store / Package Manager. |
| **Meta Quest 3 / 3S** | Developer Mode | deploying to device | USB debugging on, `adb` available. |

You do **not** need a GPU, an API key, or a headset for the offline demo.

---

## 2. Get the source

```bash
git clone https://github.com/sumitaich1998/jarvisvr.git jarvisVR
cd jarvisVR
```

The repository layout:

| Path | Component | Role |
| --- | --- | --- |
| `agent-backend/` | LLM agent brain | Plan → tools → perception → render |
| `voice-service/` | Wake word + STT + TTS + ambient hearing | Ears & mouth |
| `unity-client/` | Quest 3 Unity MR shell | Renders holograms, captures input/camera/mic |
| `holo-tools/` | 42-widget catalog + tool schemas | What Jarvis can show |
| `shared-protocol/` | Py / C# / TS protocol bindings | One contract, three languages |
| `infra/` | Compose, mock backend, e2e harness | Glue & conformance |
| `docs/` | Architecture, protocol, this documentation | Source-of-truth contracts |

---

## 3. The agent-backend (the brain)

This is the only component you need for the offline demo.

### Option A — one command from `infra/`

```bash
cd infra
make install      # creates the venv, installs agent-backend, runs the key wizard
```

The wizard asks which LLM provider to use and (if needed) your API key. **Choose
`mock`** to stay fully offline. See [Configuration](./configuration.md) for the
full wizard walkthrough.

### Option B — manual (more control)

```bash
cd agent-backend
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev,providers]"    # core + tests + the universal LiteLLM adapter
```

The `pip install` extras you can mix and match:

| Extra | Pulls in |
| --- | --- |
| *(none)* | Core server — runs the mock provider offline. |
| `[dev]` | The pytest suite and dev tooling. |
| `[providers]` | The **LiteLLM** universal adapter (Azure, Bedrock, Vertex, Cohere, + 100 more). |
| `[openai]` | The native OpenAI SDK path. |
| `[anthropic]` | The native Anthropic SDK path. |

> You can talk to **most** providers (OpenAI-compatible ones like Groq, Gemini,
> DeepSeek, Ollama, …) over plain `httpx` with **no extra SDK**. You only need
> `[providers]` for the LiteLLM-only providers, or `[openai]`/`[anthropic]` for
> their first-party SDKs. Details in [Configuration](./configuration.md).

### Configure & run

```bash
jarvis-backend setup        # interactive provider + key wizard (alias: init)
jarvis-backend providers    # list every supported provider
python -m jarvis_backend    # run the server
# -> JarvisVR agent-backend listening on ws://0.0.0.0:8765/jarvis
```

### Verify it works

```bash
cd infra && make e2e        # boots the mock locally + runs the conformance harness
# -> RESULT: PASS ✅
```

Or run the backend's own test suite:

```bash
cd agent-backend && source .venv/bin/activate
pip install -e ".[dev]" && pytest
```

---

## 4. The voice-service (ears & mouth) — optional

The voice front-end listens for the wake word "Jarvis", transcribes speech (STT),
forwards it to the backend, and speaks replies (TTS). Like the brain, it runs
**fully headless** with mock/offline engines — no microphone or models required.

```bash
cd voice-service
python3.11 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"           # light base + pytest

jarvis-voice selftest             # headless end-to-end check (uses fallbacks)
jarvis-voice bridge               # connect to the backend as the voice client
```

To light up **real** engines, install the extras you want (each stage falls back
gracefully if its engine is missing):

```bash
pip install -e ".[recommended]"   # openWakeWord + faster-whisper + Piper + audio I/O
# or à la carte:
pip install -e ".[wake-openwakeword]"   # wake word (hey_jarvis)
pip install -e ".[stt-whisper]"         # faster-whisper STT
pip install -e ".[tts-piper]"           # Piper neural TTS  (set JARVIS_PIPER_MODEL)
pip install -e ".[sound-yamnet]"        # YAMNet sound-event detection
pip install -e ".[audio]"               # sounddevice (mic + speaker)
```

The full engine matrix and every knob live in the
[voice-service README](../voice-service/README.md) and the
[Voice concept doc](./concepts/voice.md).

---

## 5. Running the whole stack with Docker — optional

If you'd rather run the services in containers, `infra/` has Compose files:

```bash
cd infra
make mock                  # mock brain only, in Docker (no sibling images needed)
# or the real stack:
make up                    # agent-backend + voice-service via docker compose
make down                  # stop it
```

`make config` validates the Compose files. The base stack exposes the backend on
`8765:8765` (both `/jarvis` and the v1.1 `/vision` path share that port). Full
details: the [infra README](../infra/README.md).

> **No Docker?** You don't need it. `make e2e` and `make test` run the mock brain
> and harness in a plain Python venv.

---

## 6. The unity-client (Quest 3 shell)

This is the mixed-reality app that renders holograms in your room. **There is no
prebuilt APK** — you build it locally with Unity + the Meta XR SDK.

### 6.1 Install Unity + the Meta XR SDK

1. Install **Unity 2022.3 LTS** via Unity Hub, with **Android Build Support**
   (including **OpenJDK** and the **Android SDK & NDK**).
2. Open `unity-client/` in Unity and let it resolve the registry packages first.
   Pinned in `Packages/manifest.json`: OpenXR, XR Management, Input System,
   TextMeshPro, Newtonsoft JSON, and **NativeWebSocket**.
3. Install the **Meta XR All-in-One SDK** (`com.meta.xr.sdk.all`): open
   **Window ▸ Package Manager ▸ My Assets**, find **Meta XR All-in-One SDK**, then
   **Download** + **Import**.
4. Run **Meta ▸ Tools ▸ Project Setup Tool** and apply all recommended fixes for
   Android/Quest. When prompted, **Import TMP Essentials**.

> The C# is structured to **compile even before** the Meta SDK is imported — all
> Meta-specific integration lives behind assembly version-defines and lights up
> automatically once the SDK is present.

### 6.2 Build the scene

Follow the exact, ~5-minute scene recipe in
[`unity-client/Assets/JarvisVR/SETUP.md`](../unity-client/Assets/JarvisVR/SETUP.md).
In short: create a `JarvisConfig` asset, build a new scene with the Meta camera rig
(passthrough + hand tracking), add an empty `Jarvis` object, and attach the
`JarvisApp` component. `JarvisApp` wires up every subsystem — connection, hologram
manager, presence orb, audio, and the whole v1.1 perception stack — automatically.

### 6.3 Point it at your backend

Backend connection settings live in the **`JarvisConfig`** asset (no code change):

- **Assets ▸ Create ▸ JarvisVR ▸ Jarvis Config**, then set **host** / **port**
  (`8765`) / **path** (`/jarvis`).
- In the **editor** against a local backend: host `127.0.0.1`.
- On a **Quest over Wi-Fi**: your dev machine's **LAN IP** (e.g. `192.168.1.50`),
  and make sure the headset is on the same network.
- `wss://` (TLS) is supported via the **Use Tls** toggle.

See [Configuration](./configuration.md) for in-headset settings (including changing
the LLM provider/model/key without rebuilding).

### 6.4 Test in the editor (no build)

1. Start a backend (e.g. `cd infra && make mock`, or `python -m jarvis_backend`).
2. Set `JarvisConfig` host to `127.0.0.1`.
3. Connect the Quest via **Quest Link** / **Air Link**, or just press **Play** on
   desktop to validate networking and widgets without a headset.
4. **Desktop without a headset:** set **Project Settings ▸ Player ▸ Active Input
   Handling** to **Both**, then left-click holograms — the editor mouse tester
   sends real `client.interaction` / `user.text` messages. Turn on `logTraffic`
   to watch the protocol in the Console.

### 6.5 Build & deploy to the Quest 3 (Android)

1. **File ▸ Build Settings ▸ Android ▸ Switch Platform.**
2. Texture compression **ASTC**; run the **Meta Project Setup Tool** and apply
   fixes.
3. **Player Settings:** Scripting Backend **IL2CPP**, Target Architectures
   **ARM64**, Minimum API Level **Android 10 (API 29)+**, and **XR Plug-in
   Management ▸ Android ▸ OpenXR** with the **Meta Quest** feature group +
   **hand-tracking** + **passthrough** (+ **eye tracking** for gaze).
4. Grant **perception permissions** (Setup Tool or AndroidManifest):

   | Capability | Permission(s) |
   | --- | --- |
   | Passthrough camera | `horizonos.permission.HEADSET_CAMERA` **and** `android.permission.CAMERA` |
   | Ambient audio | `android.permission.RECORD_AUDIO` |
   | Eye-tracked gaze | `com.oculus.permission.EYE_TRACKING` |

5. Add the **Jarvis** scene to **Scenes In Build**.
6. Connect the Quest (`adb devices` to confirm) → **Build And Run**.

CLI alternative once built: `adb install -r build/JarvisVR.apk`.

The full device guide, optional scripting defines (`HAS_META_PCA`,
`HAS_META_ANCHORS`, `HAS_META_KEYBOARD`), and troubleshooting are in the
[unity-client README](../unity-client/README.md).

---

## 7. Per-OS notes

### macOS

- Install Python 3.11 with [Homebrew](https://brew.sh): `brew install python@3.11`,
  or via [pyenv](https://github.com/pyenv/pyenv).
- `make`, `bash`, and `git` come with the Xcode Command Line Tools:
  `xcode-select --install`.
- Docker Desktop is optional. For the voice-service's real audio engines you may
  need PortAudio: `brew install portaudio` before `pip install -e ".[audio]"`.
- Unity Hub and the Meta XR SDK both run on macOS, including Apple Silicon.

### Linux

- Use your distro's Python 3.11 (`apt install python3.11 python3.11-venv`,
  `dnf install python3.11`, …) and `build-essential` / `make`.
- For real audio engines: `apt install libportaudio2` (or the distro equivalent).
- Docker Engine + the Compose v2 plugin work natively; for the optional GPU voice
  path you'll also want the NVIDIA Container Toolkit (see `infra/docker-compose.gpu.yml`).
- Unity Editor for Linux is supported for development; device builds target Android
  the same way.

### Windows

- The Python services run on Windows, but the `infra/` shortcuts assume a POSIX
  shell (`make`, `bash`). The smoothest path is **WSL2** (Ubuntu): install Python,
  `make`, and Docker Desktop with the WSL2 backend there, then follow the Linux
  notes.
- If you stay in native Windows, use **Git Bash** or run the underlying commands
  directly (e.g. `python -m venv .venv`, `pip install -e ".[dev,providers]"`,
  `python -m jarvis_backend`) instead of `make`.
- Unity, Unity Hub, and the Meta XR SDK are first-class on Windows, and `adb`
  ships with the Android SDK installed by Unity Hub.

---

## 8. Optional extras at a glance

| Extra | Where | Why |
| --- | --- | --- |
| `agent-backend` `.[providers]` | `pip install -e ".[providers]"` | Universal LiteLLM adapter (Azure/Bedrock/Vertex/Cohere/100+). |
| `agent-backend` `.[openai]` / `.[anthropic]` | same | Native first-party SDK paths. |
| `voice-service` `.[recommended]` | `pip install -e ".[recommended]"` | The open offline voice stack (wake + STT + TTS + audio). |
| `voice-service` `.[sound-yamnet]` | same | Real 521-class sound-event detection. |
| `infra` Node 20 + `make test` | `infra/` | Run the TypeScript protocol tests. |
| `infra/docker-compose.gpu.yml` | `infra/` | GPU reservation for heavy voice models. |

---

## Next steps

- **[Configuration](./configuration.md)** — pick a real LLM provider, set keys, and tune perception/ports/logging.
- **[Getting Started](./getting-started.md)** — run the offline demo and trace a full conversation.
- **[Overview](./concepts/overview.md)** — understand the shell ↔ brain architecture.
- **[Deploy JarvisVR](./guides/deploy.md)** — Docker, TLS/`wss://`, auth, and production hardening.
- **[Troubleshooting](./guides/troubleshooting.md)** — common install issues and fixes.
