# FAQ

Practical questions and honest answers. For deeper dives, follow the links — and see
the [Glossary](./glossary.md) for any unfamiliar term.

---

## General

### What is JarvisVR?

An **AI agentic operating system for mixed reality** on the Meta Quest 3. You speak;
an LLM agent **plans, calls tools, and spawns interactive 3D holograms** into your
room (passthrough MR) that you grab with your hands. It can also **see** (color
passthrough camera), **hear** (ambient room audio), and sense **gaze** — so you can
ask about whatever you're looking at or hearing. See the
[Overview](./concepts/overview.md) and [`ARCHITECTURE.md`](../ARCHITECTURE.md).

### Is it really an OS?

It's a spatial AI **shell + brain**, not a kernel. The headset "shell"
(`unity-client`) and the AI "brain" (`agent-backend`) are decoupled across one
versioned [WebSocket protocol](./PROTOCOL.md), so you can swap the model, the voice,
or even the rendering engine. Think "conversational, agentic, spatial computing
layer."

### How is this different from a voice assistant like Alexa/Siri?

Three ways: it's **agentic** (an LLM that plans → calls tools → observes → responds,
not a fixed command parser), it's **spatial** (answers materialize as interactive
holograms in your room), and it's **multimodal-perceptive** (it can reason over what
you're currently seeing and hearing).

### What's the license? Is it affiliated with Marvel or Meta?

[MIT](../LICENSE). It is an **independent project, not affiliated with, endorsed by,
or sponsored by Marvel, Meta, or any third party**. "J.A.R.V.I.S." is referenced only
as cultural inspiration.

---

## Cost & offline

### Is it free?

The software is free and open source (MIT). Whether you pay anything depends on the
**LLM/voice provider you choose**: the default `mock` provider and the offline voice
fallbacks cost **nothing**; a hosted LLM (OpenAI, Anthropic, …) bills per their
pricing; a local model (Ollama/LM Studio/vLLM) is free but runs on your hardware.

### Can I run it completely offline / with no internet and no API key?

Yes. The **entire stack is demoable offline** on deterministic mock providers — no
key, no cloud, no headset. `cd infra && make e2e` drives a full scripted conversation
through the protocol on your laptop. For an offline *real* LLM, point it at a **local
model** (see below). The voice-service also ships no-dependency offline engines.

### Do I need a GPU?

No, for the mock/offline path and for hosted LLMs. A GPU helps if you run **local
LLMs** or the heavier **local voice engines** (Whisper STT, Piper TTS); the
`docker-compose.gpu.yml` override reserves a GPU for the voice-service.

---

## Hardware

### Do I need a Meta Quest 3?

**No, to try it.** You can run the whole backend + e2e harness on a laptop, and even
test the Unity client on the desktop (press Play, click holograms with the mouse).
**Yes, to actually use it** as a mixed-reality assistant — the holographic, hand-
tracked, passthrough experience needs a Quest 3 / 3S.

### Is there a prebuilt APK I can sideload?

No. The `unity-client` is a **complete Unity project you build locally** with Unity
2022.3 LTS + the Meta XR SDK and **Build & Run** to your headset. There is
intentionally no shipped APK. See the [unity-client README](../unity-client/README.md)
and the [Deploy guide](./guides/deploy.md#the-unity-client-is-a-device-build).

### What do I need to develop on it?

Python 3.11 (backend, voice), Node 20 (TypeScript protocol bindings), `make` + a
POSIX shell, Docker (optional), and Unity 2022.3 LTS + Meta XR SDK only if you touch
the client. See [Installation](./installation.md) and
[`CONTRIBUTING.md`](../CONTRIBUTING.md).

---

## LLM providers

### Which providers are supported?

About **20**, reached three ways: **native SDK** (OpenAI, Anthropic), **generic
OpenAI-compatible** over plain HTTP (Gemini, Groq, Mistral, Together, OpenRouter,
DeepSeek, xAI, Perplexity, Fireworks, Ollama, LM Studio, vLLM, custom), and the
**LiteLLM** universal adapter (Azure, Bedrock, Vertex, Cohere, +100s). Run
`jarvis-backend providers` for the live list. Details:
[Add an LLM provider](./guides/add-an-llm-provider.md).

### Can I self-host the LLM / use a local model?

Yes. `JARVIS_LLM=ollama` (or `lmstudio` / `vllm` / `custom`) points the brain at a
**local OpenAI-compatible server** — usually no key, just a `base_url`. This keeps
inference on your machine and fully offline.

```bash
JARVIS_LLM=ollama JARVIS_OLLAMA_BASE_URL=http://localhost:11434/v1 python -m jarvis_backend
```

### Can I switch providers without restarting?

Yes — from the in-headset **Settings** panel ([§5.15](./PROTOCOL.md#515-settings--clientsettings_get--clientsettings_update--serversettings-v11)).
It hot-swaps the active LLM so the **next turn** uses it; no reconnect, no rebuild.
You can also re-run `jarvis-backend setup` anytime.

### What's the "mock" provider?

A **deterministic, offline planner** (keyword/intent → tool calls) plus mock vision.
It needs no key, always produces the same output, and lets the whole stack run and be
tested offline. It's the default.

### What happens if my key or SDK is missing?

The server **logs a warning and falls back to `mock`** — it never crashes. The
startup log and `jarvis-backend setup --validate` tell you what's missing. See
[Troubleshooting](./guides/troubleshooting.md#provider-falls-back-to-mock-even-though-i-set-jarvis_llm).

---

## Privacy & security

### Is my API key safe?

Yes, by design:

- Stored in `agent-backend/.env` with **`0600`** (owner-only) permissions.
- **Never printed or logged** — you only ever see a masked `•••• (N chars)`.
- **Never echoed back** to the client — `server.settings` is a *closed* schema that
  structurally cannot contain an `api_key`.
- When set in-headset it travels only on `client.settings_update`, so use `wss://` in
  production.

See [`SECURITY.md`](../SECURITY.md).

### Does Jarvis record me? Is the camera/mic always on?

No. Perception is **opt-in, negotiated, and pull-based**: the camera/mic run **only
while a stream is active**, which the server turns on with `perception.request` (e.g.
for one vision question, then off again). `perception.state` always reflects what's
live, the headset shows a **capture indicator**, and there's a **Stop capture** kill
switch. Servers process frames/audio **in-memory by default** and avoid persistence
unless you opt in. Proactive observations are **off** unless `JARVIS_PROACTIVE=1`. See
[Perception](./concepts/perception.md) and [`ARCHITECTURE.md` §7](../ARCHITECTURE.md#7-multimodal-perception-v11).

### Does it phone home / send telemetry?

No. JarvisVR has **no telemetry**. The only third-party calls are to the LLM/voice
provider **you** configure.

### Where is my data stored?

Locally. Notes, reminders, and episodic/spatial memory live in a JSON store under
`JARVIS_DATA_DIR` (default `agent-backend/.data`). Nothing goes to a cloud unless your
chosen provider requires it for inference.

### Is it safe to expose the backend to the internet?

Not as-is. The protocol is **unauthenticated and unencrypted by default** for local
dev. Before exposing it beyond `localhost`, terminate **TLS (`wss://`)** and add
**authentication** at a reverse proxy, and restrict `/vision` and `/audio`. Follow the
[Deploy hardening checklist](./guides/deploy.md#production-hardening-checklist).

---

## Perception & capabilities

### What can Jarvis actually see and hear?

With v1.1 perception: the **forward RGB passthrough camera** (pull-based 1–3 fps,
JPEG), **continuous ambient room audio** (overheard transcript + soundscape) and
**sound events** (doorbell, alarm…), and **gaze**. It correlates this with each
utterance so you can ask *"what is this?"*, *"read this sign and translate it"*, or
*"what was that sound?"*. See [Perception](./concepts/perception.md).

### Does vision need a paid vision model?

No. The `mock` vision path "sees" deterministically offline, so vision Q&A works with
no key. For real image understanding set `JARVIS_VISION=openai` (or `anthropic`) and
use a vision-capable model.

---

## Voice

### Does voice require the cloud?

No. The voice-service ships a **real engine and an offline fallback** for every stage
(wake word, STT, TTS, sound events, ambient listening), so the pipeline runs
**headless with no external services or audio hardware**. Add an extra (e.g.
`.[stt-whisper]`, `.[tts-piper]`) for higher quality. See the
[voice-service README](../voice-service/README.md).

### Can I interrupt Jarvis (barge-in)?

Yes. Talking over Jarvis sends `client.barge_in`, which cancels the in-flight turn
(stops speech/observations, aborts pending work). See [Voice](./concepts/voice.md) and
[§5.14](./PROTOCOL.md#514-clientbarge_in-v11).

---

## Extending & contributing

### Can I add my own holograms / tools / providers?

Yes — that's the point. See [Add a widget](./guides/add-a-widget.md),
[Write a tool](./guides/write-a-tool.md), and
[Add an LLM provider](./guides/add-an-llm-provider.md).

### Can multiple people share a session? What languages are supported?

Multi-user shared sessions and device hand-off are on the **roadmap (P2)** — today
it's one client session per headset. The default locale is `en-US`; there are
translation tools and multi-language voice support, with broader multilingual work
ongoing. See [`docs/FEATURES.md`](./FEATURES.md).

### Are the integrations (weather, news, stocks, calendar, smart home) real?

They're **mock-by-default** so everything runs offline, with real-API paths slotting
in behind the same interface (e.g. `get_weather` uses OpenWeatherMap when
`JARVIS_WEATHER_API_KEY` is set, else deterministic mock data). Many integrations are
believable stubs on the [roadmap](./FEATURES.md).

### How do I report a bug or a security issue?

File a [bug report or feature request](https://github.com/sumitaich1998/jarvisvr/issues/new/choose).
For vulnerabilities, **do not** open a public issue — follow
[`SECURITY.md`](../SECURITY.md).

---

## See also

- [Getting Started](./getting-started.md) · [Installation](./installation.md) ·
  [Configuration](./configuration.md)
- [Glossary](./glossary.md) · [Troubleshooting](./guides/troubleshooting.md)
- [Concepts](./concepts/overview.md) · [Protocol](./PROTOCOL.md) ·
  [Features & roadmap](./FEATURES.md)
