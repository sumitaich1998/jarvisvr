# JarvisVR · voice-service

> Jarvis's **ears and mouth**: wake word → speech-to-text → (agent) → text-to-speech,
> **plus** continuous ambient hearing of your physical room (v1.1 perception).

This service is the **voice front-end** of [JarvisVR](../README.md). It listens for
the wake word **"Jarvis"**, transcribes what you say (STT), forwards the text to the
`agent-backend` over the [JarvisVR WebSocket protocol](../docs/PROTOCOL.md) (**v1.1**),
and speaks the agent's replies (TTS). With **v1.1 Multimodal Perception** it also
**hears the room continuously** — emitting an ambient/overheard transcript + soundscape
(`perception.audio_scene`) and sound events like doorbells and alarms
(`perception.audio_event`) — and supports **barge-in** (talk over Jarvis to interrupt).

Every stage is **pluggable** and ships with a **real engine** *and* an **offline/mock
fallback**, so the whole pipeline runs **headless with zero external services, models,
or audio hardware**. Add an extra to light up a real engine when you want quality.

---

## Highlights

- **5 pluggable stages** — wake word, STT, TTS, **sound events**, **ambient listening** —
  each behind a small interface, each with an offline fallback.
- **Continuous ambient hearing (v1.1)** — overheard speech + soundscape + loudness, plus
  low-latency sound-event detection, all separate from the wake/STT path.
- **Barge-in** — user speech while Jarvis is talking interrupts TTS and notifies the
  backend so the agent can stop.
- **Always-on fallbacks** — never hard-crashes on a missing model/engine/mic; it logs
  and falls back.
- **Run modes** — backend **sidecar** (`bridge`) + local CLI demos (`demo`, `ambient`).
- **Protocol-conformant (v1.1)** — `client.hello` (mic+speaker+ambient_audio), heartbeat,
  `user.voice_transcript`/`user.voice_partial` out, `agent.speech`/`agent.observation`
  spoken in, `perception.request` honored, `perception.audio_scene`/`audio_event` emitted.
- **Light base install** — only `websockets`, `numpy`, `python-dotenv`. Heavy engines
  are opt-in extras.

---

## Architecture

The mic stream fans out to **two** independent, frame-driven consumers: the
**wake/STT pipeline** (directed speech) and the **ambient listener** (everything else).

```
                          ┌───────────── VoicePipeline (wake/STT) ─────────────┐
                          │ LISTENING ─wake─▶ RECORDING ─(VAD endpoint)─▶ [STT] │──▶ transcript
   mic 16k PCM16 ─────┬──▶│  + barge-in: user speech during TTS ⇒ stop + notify │──▶ speak(text)
                      │   └────────────────────────────────────────────────────┘
                      │   ┌───────────── AmbientListener (v1.1) ───────────────┐
                      └──▶│ rolling window ─▶ VAD ─▶ [STT overheard transcript] │──▶ audio_scene
                          │ per-frame ─▶ SoundEventDetector ─▶ labels           │──▶ audio_event
                          └────────────────────────────────────────────────────┘
                                   │ callbacks                                   ▲ speak()
                                   ▼                                             │
                  ┌──────────────── VoiceBridge (WebSocket, v1.1) ──────────────┴────────┐
                  │ → client.hello {mic,speaker,ambient_audio} → client.heartbeat (5s)    │
   agent-backend ◀┤ → user.voice_(partial|transcript) · perception.audio_(scene|event)   │
   ws://host:8765 │ → client.barge_in (on interrupt)                                      │
        /jarvis   │ ← agent.speech / agent.observation ──▶ Speaker.speak()  (TTS)         │
                  │ ← perception.request{ambient_audio, start|stop|once} ──▶ ambient on/off│
                  └──────────────────────────────────────────────────────────────────────┘
```

### Package layout

```
voice-service/
├── pyproject.toml          # packaging + optional-dependency extras
├── requirements.txt        # pinned base runtime
├── Dockerfile              # python:3.11-slim + audio libs (compose service: voice-service)
├── .env.example            # all config knobs (safe defaults)
├── README.md
├── jarvis_voice/
│   ├── __init__.py
│   ├── __main__.py         # CLI: demo | ambient | bridge | say | selftest | devices
│   ├── config.py           # env-driven Config (JARVIS_*), .env auto-load
│   ├── protocol.py         # self-contained v1.1 envelope + builders/parsers
│   ├── audio.py            # mic/playback + WAV/energy + dBFS/ZCR/spectral (import-guarded)
│   ├── wakeword.py         # WakeWordDetector + OpenWakeWord / Porcupine / EnergyFallback
│   ├── stt.py              # Transcriber + FasterWhisperSTT / VoskSTT / MockSTT
│   ├── tts.py              # Speaker + PiperTTS / Pyttsx3TTS / MockTTS (+ stop/barge-in)
│   ├── sound_events.py     # SoundEventDetector + YamnetSoundEvents / Heuristic / Null
│   ├── ambient.py          # AmbientListener: continuous room audio → scene + events
│   ├── pipeline.py         # VoicePipeline orchestrator (frame-driven; wake/STT + barge-in)
│   └── bridge.py           # VoiceBridge: pipeline + ambient ↔ agent-backend over WebSocket
└── tests/                  # pytest: protocol, pipeline, bridge, engines, sound_events,
                            #         ambient, barge_in (all headless via mocks)
```

---

## Engine matrix

Each stage tries your selected engine and **falls back** if it's unavailable. The
default selection is `auto` (prefer the real open engine, else fall back).

| Stage | Env (`auto` default) | Preferred (real) | Alt (real) | Fallback (always works) |
| ----- | -------------------- | ---------------- | ---------- | ----------------------- |
| Wake  | `JARVIS_WAKE`        | `openwakeword` (`hey_jarvis`) | `porcupine` (`jarvis` keyword) | `energy` — speech-onset detector |
| STT   | `JARVIS_STT`         | `faster-whisper` | `vosk` (streaming) | `mock` — canned/typed text |
| TTS   | `JARVIS_TTS`         | `piper` (offline neural) | `pyttsx3` (OS voices) | `mock` — logs text + tone WAV |
| **Sound events** | `JARVIS_SOUND_EVENTS` | `yamnet` (TF-Hub, 521 classes) | — | `heuristic` — loudness+spectral; `off` = disabled |
| **Ambient STT**  | `JARVIS_STT` (reused) | `faster-whisper` | `vosk` | `mock` |
| Audio | extra `[audio]`      | `sounddevice`    | —          | import-guarded no-op |

> The **`energy`** wake fallback can't recognize the literal word "Jarvis" (that needs a
> model) — it fires on a short burst of speech-level energy so the pipeline is still
> usable with zero models. The **`mock`** STT returns `JARVIS_MOCK_TRANSCRIPT` (or typed
> text in the demo), and **`mock`** TTS prints the text and synthesizes a valid tone WAV.
> The **`heuristic`** sound-event detector is an *approximation* (it maps loudness +
> dominant frequency + spectral flatness + zero-crossing rate to a plausible label such
> as `alarm`/`doorbell`/`glass_break`/`speech`/`music`) — not a trained classifier — so
> the perception pipeline runs fully headless.

### Enabling real engines

Install only what you need (extras are defined in `pyproject.toml`):

```bash
# Recommended open/offline stack: openWakeWord + faster-whisper + Piper + audio I/O
pip install -e ".[recommended]"

# Or pick à la carte:
pip install -e ".[wake-openwakeword]"      # openWakeWord (hey_jarvis)
pip install -e ".[wake-porcupine]"          # Picovoice Porcupine (needs access key)
pip install -e ".[stt-whisper]"             # faster-whisper
pip install -e ".[stt-vosk]"                # Vosk (set JARVIS_VOSK_MODEL=/path/to/model)
pip install -e ".[tts-piper]"               # Piper (set JARVIS_PIPER_MODEL=/path/voice.onnx)
pip install -e ".[tts-pyttsx3]"             # pyttsx3 (uses OS speech engine)
pip install -e ".[sound-yamnet]"            # YAMNet sound-event detection (TensorFlow Hub)
pip install -e ".[audio]"                   # sounddevice (mic + speaker)
```

Then select engines (or leave `auto`):

```bash
export JARVIS_WAKE=openwakeword JARVIS_STT=faster-whisper JARVIS_TTS=piper
export JARVIS_PIPER_MODEL=/models/en_US-amy-medium.onnx     # piper needs a voice
export JARVIS_PORCUPINE_ACCESS_KEY=...                       # only if JARVIS_WAKE=porcupine
```

---

## Install & run

Requires **Python 3.11+**.

```bash
cd voice-service
python3.11 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"          # base + pytest (add ,recommended for real engines)
```

### Commands

```bash
jarvis-voice selftest            # headless end-to-end check (uses fallbacks)
jarvis-voice say "Jarvis online" # TTS smoke test (add --out out.wav to save WAV)
jarvis-voice demo                # local mic → wake → STT loop (auto-falls to a typed REPL)
jarvis-voice demo --simulate     # force the typed REPL (no mic needed)
jarvis-voice ambient             # continuous ambient listening + sound events (v1.1)
jarvis-voice ambient --simulate  # synthetic room audio + typed "overheard" REPL (no mic)
jarvis-voice bridge              # connect to the agent-backend and act as the voice client
jarvis-voice devices             # list audio devices (diagnostics)
```

Overrides work on either side of the subcommand:

```bash
jarvis-voice --stt mock say "hi"
jarvis-voice bridge --backend ws://localhost:8765/jarvis --no-mic
jarvis-voice ambient --sound-events heuristic --language es   # multi-language hook
```

**Demo (no mic):** each line you type is treated as a recognized utterance and echoed
back through TTS — a quick way to exercise the wake→STT→speak flow offline.

**Ambient (no mic):** generates synthetic room audio to emit a few `audio_scene`/
`audio_event` lines, then drops into a REPL where each typed line becomes an *overheard*
ambient transcript.

**Bridge:** runs mic capture in a background thread, fanning each frame to **both** the
wake/STT pipeline and (when active) the ambient listener; transcripts + perception events
are sent to the backend and `agent.speech`/`agent.observation` are spoken. With no mic it
becomes **speak-only** (still receives + speaks). It reconnects with exponential backoff.

---

## Continuous ambient listening · sound events · barge-in (v1.1)

These three perception features run **independently of the wake word** so the user can
chat about what Jarvis is hearing in the room.

### Continuous ambient listening → `perception.audio_scene`
`AmbientListener` (`ambient.py`) keeps a rolling **window** (`JARVIS_AMBIENT_WINDOW_MS`,
default 4 s) of room audio. Each window it emits one `perception.audio_scene`:

- **`ambient_transcript`** — if the window contains speech (≥ `JARVIS_AMBIENT_MIN_SPEECH_RATIO`
  voiced frames via the energy VAD) it is transcribed with the **same STT engine** as the
  pipeline (Mock fallback). This is *overheard* speech — speech **not** directed at Jarvis
  (wake-word-directed speech goes to the pipeline instead).
- **`speaker`** — `user | other | unknown` (`JARVIS_AMBIENT_SPEAKER`, default `other`;
  real diarization is a P2 follow-up).
- **`sounds`** — soundscape labels from the sound-event detector over the window.
- **`loudness_db`** — window loudness in dBFS · **`window_ms`** — the analysis window.

### Sound-event detection → `perception.audio_event`
`SoundEventDetector` (`sound_events.py`) analyzes short sub-windows
(`JARVIS_SOUND_EVENT_WINDOW_MS`, default 1 s) and emits low-latency
`perception.audio_event{label, confidence, loudness_db, ts}` for doorbell, alarm, phone,
knock, glass_break, music, speech, … The **`heuristic`** fallback needs no model; install
`[sound-yamnet]` and set `JARVIS_SOUND_EVENTS=yamnet` for the real classifier.

### Barge-in (interruptible TTS)
While Jarvis is speaking, the pipeline watches the mic for the user talking over it
(`JARVIS_BARGE_IN_THRESHOLD` energy sustained for `JARVIS_BARGE_IN_MIN_FRAMES`). On a
hit it **interrupts playback** (`Speaker.stop()` / `sounddevice.stop()`), clears the
speaking state, and the bridge sends **`client.barge_in`** so the agent can stop its turn.
Disable with `JARVIS_BARGE_IN=off`.

### Lifecycle (pull-based, privacy-aware)
Ambient listening is **negotiated**: the bridge advertises `ambient_audio` in
`client.hello`, then starts/stops on the backend's `perception.request{stream:"ambient_audio"}`
(`start` | `stop` | `once`). Set `JARVIS_AMBIENT=on` to autostart at connect, or `off` to
disable entirely (capability not advertised, requests refused). After each change the
bridge replies with `perception.state` reflecting what's active.

---

## Integration contract (with `agent-backend`)

The bridge is a **protocol client** of the backend's WebSocket server
(`ws://<host>:8765/jarvis`), conforming to [`docs/PROTOCOL.md`](../docs/PROTOCOL.md) **v1.1**.

| Direction | When | Message | Payload |
| --------- | ---- | ------- | ------- |
| → out | on connect | `client.hello` | `capabilities.{mic,speaker,ambient_audio}=true`, `protocol_version=1.1.0`, `locale` |
| → out | every 5s | `client.heartbeat` | `{}` |
| → out | interim STT | `user.voice_partial` | `{ text, confidence }` |
| → out | **final STT** | **`user.voice_transcript`** | `{ text, confidence }` |
| → out | ambient window | **`perception.audio_scene`** | `{ ambient_transcript, speaker, sounds[], loudness_db, window_ms }` |
| → out | sound detected | **`perception.audio_event`** | `{ label, confidence, loudness_db, ts }` |
| → out | user interrupts TTS | **`client.barge_in`** | `{ reason }` (forward-compatible extension) |
| → out | after request | `perception.state` | `{ ambient_audio:{active}, vision, gaze, thermal }` |
| → out | on close | `client.bye` | `{}` |
| ← in | session start | `server.hello_ack` | stores `session` (echoed on later frames) |
| ← in | **agent reply** | **`agent.speech`** | `{ text, final }` → **spoken via TTS** |
| ← in | **what Jarvis perceives** | **`agent.observation`** | `{ text, final, annotations? }` → **spoken via TTS** |
| ← in | **stream control** | **`perception.request`** | `{ stream:"ambient_audio", action:start\|stop\|once }` → ambient on/off |
| ← in | status | `agent.thinking` / `agent.transcript` | logged |
| ← in | any unknown (`holo.*`, `perception.request{stream:"vision"}`, …) | — | **ignored** (forward-compatible) |

**Core mappings:** STT → `user.voice_transcript` · ambient → `perception.audio_scene`/
`audio_event` · `agent.speech`/`agent.observation` → `Speaker.speak()` ·
`perception.request{ambient_audio}` → start/stop ambient.

Every message uses the v1.1 envelope `{ v, id, type, ts, session, payload }` (with optional
`reply_to`). `session` is omitted on the first hello and included afterward. Bad frames are
dropped with a `client.error{code:"bad_envelope"}`; incompatible major versions are logged.
v1.1 is additive: 1.0 backends simply never send `perception.request` and ignore the
`perception.*` / `client.barge_in` frames.

> `protocol.py` is a self-contained implementation of the v1 envelope. When
> `shared-protocol/` ships canonical Python bindings, this module can be swapped for them
> without touching the pipeline/bridge.

### Optional raw-audio channel

Transcripts/speech text always flow as JSON on the main channel. The optional parallel
`ws://<host>:8765/audio` PCM16 16 kHz channel (`JARVIS_AUDIO_URL`) is reserved for raw
audio; `Speaker.synthesize(text) -> wav bytes` and `audio.wav_to_pcm16()` provide the
bytes for it. (Streaming raw audio is a follow-up; JSON transcripts/speech are complete.)

---

## Configuration

All knobs are environment variables (auto-loaded from `.env` if present). See
[`.env.example`](./.env.example) for the full annotated list. Most-used:

| Variable | Default | Purpose |
| -------- | ------- | ------- |
| `JARVIS_BACKEND_URL` | `ws://localhost:8765/jarvis` | Backend WebSocket endpoint |
| `JARVIS_WAKE` / `JARVIS_STT` / `JARVIS_TTS` | `auto` | Engine selection |
| `JARVIS_WAKE_WORD` | `jarvis` | Wake word |
| `JARVIS_SAMPLE_RATE` / `JARVIS_FRAME_MS` | `16000` / `30` | Audio framing (PCM16 mono) |
| `JARVIS_SILENCE_MS` | `800` | Trailing silence that ends an utterance (VAD) |
| `JARVIS_VAD_THRESHOLD` | `300` | RMS energy threshold for "speech vs silence" |
| `JARVIS_WHISPER_MODEL` | `base.en` | faster-whisper model size/path |
| `JARVIS_VOSK_MODEL` | — | Path to a Vosk model dir (required for Vosk) |
| `JARVIS_PIPER_MODEL` | — | Path to a Piper voice `.onnx` (required for Piper) |
| `JARVIS_PORCUPINE_ACCESS_KEY` | — | Required for Porcupine |
| `JARVIS_MOCK_TRANSCRIPT` | `jarvis what is the weather in tokyo` | MockSTT canned text |
| `JARVIS_AMBIENT` | `auto` | Ambient listening: `auto` (on request) \| `on` (autostart) \| `off` |
| `JARVIS_AMBIENT_WINDOW_MS` | `4000` | One `perception.audio_scene` per window |
| `JARVIS_AMBIENT_SPEAKER` | `other` | Speaker tag for overheard speech (`user\|other\|unknown`) |
| `JARVIS_SOUND_EVENTS` | `auto` | Sound events: `auto` \| `yamnet` \| `heuristic` \| `off` |
| `JARVIS_SOUND_EVENT_THRESHOLD` | `0.5` | Min confidence to emit a sound event |
| `JARVIS_BARGE_IN` | `true` | Interrupt TTS when the user talks over Jarvis |
| `JARVIS_BARGE_IN_THRESHOLD` | `1500` | RMS energy for barge-in (above VAD to resist TTS bleed) |
| `JARVIS_STT_LANGUAGE` / `JARVIS_TTS_LANGUAGE` | `en` / — | Multi-language hooks (best-effort) |
| `JARVIS_LOG_LEVEL` | `INFO` | Logging level |

---

## Docker

The image installs the light base by default (small, always runnable). `infra/`'s
`docker-compose` references this path with service name **`voice-service`**.

```bash
# from voice-service/
docker build -t jarvisvr-voice .
docker run --rm -e JARVIS_BACKEND_URL=ws://agent-backend:8765/jarvis jarvisvr-voice

# bake in real engines:
docker build --build-arg EXTRAS="[recommended]" -t jarvisvr-voice .
```

The build runs `jarvis-voice selftest`, and the container `HEALTHCHECK` re-runs it.
Default `CMD` is `jarvis-voice bridge`. (Mic capture in a container needs device
passthrough; the typical container role is **speak-only** + receiving `agent.speech`.)

---

## Testing

```bash
pytest -q
```

Tests are fully **headless** (no mic, no models) using the Mock/Energy/Heuristic engines
and a fake websocket. They cover:

- **protocol** — envelope build/parse, round-trip, first-hello omits `session`, unknown
  types parse, version compat (now `1.1.0`), malformed-frame errors, and the v1.1
  builders (`client.hello.ambient_audio`, `audio_scene`, `audio_event`, `perception_state`,
  `perception.request` parse, `client_barge_in`).
- **pipeline** — the wake → record → STT state machine, streaming partials, silence/
  max-length/no-speech endpointing, the `speak()` path, callback-error resilience.
- **bridge** — hello advertises mic+speaker+ambient_audio, STT → `user.voice_transcript`/
  `user.voice_partial`, `agent.speech` **and** `agent.observation` → TTS, `hello_ack`
  session capture, `perception.request` start/stop (+`perception.state`), non-ambient
  streams ignored, ambient → `perception.audio_scene`/`audio_event` enqueued, unknown-type
  ignoring, and bad-frame `client.error`.
- **sound_events** — heuristic fires on loud audio / silent on silence, window feeding,
  canned-label rotation, factory `auto`→heuristic / `off`→null.
- **ambient** — `analyze_window` produces transcript+soundscape with speech (none on
  silence), `process_frame` emits scenes + events, configurable speaker tag, simulate/snapshot.
- **barge_in** — user speech during (blocking) TTS interrupts playback (`tts.stop`) and
  fires `on_barge_in`; no false trigger when idle; can be disabled.
- **engines** — every factory falls back correctly when an engine/model is missing.

---

## Design notes / assumptions

- Everything is **frame-driven** (`process_frame(pcm16)`) — the pipeline *and* the ambient
  listener — so the whole system is unit-testable by feeding synthetic frames, no audio
  stack required. The mic thread fans each frame out to both.
- Endpointing + ambient speech-presence + barge-in all use a simple **energy VAD/dBFS**
  (configurable, dependency-free); swap in WebRTC/Silero VAD later behind the same hook.
- **Overheard vs directed speech:** wake-word-directed speech → the pipeline
  (`user.voice_transcript`); everything else the room produces → ambient
  (`perception.audio_scene`, `speaker=other` by default). Speaker diarization (user vs
  other) is a P2 follow-up.
- The heuristic sound-event detector is an **approximation**, not a trained model; it
  exists so perception runs offline. Use `[sound-yamnet]` for real classification.
- Barge-in is **best-effort** across engines: it calls `Speaker.stop()` (which stops
  `sounddevice` playback / `pyttsx3`); with the headless Mock speaker there's nothing to
  cut, so the unit test drives the real concurrent flow with a blocking fake speaker.
- `client.hello` advertises `mic` + `speaker` + `ambient_audio` as **true** (this
  front-end's role), independent of whether a local audio device is currently attached.
- **Multi-language** is wired as hooks (`Config.stt_language`/`tts_language`,
  `Pipeline/STT/TTS.set_language`, `--language`): Whisper uses per-call language, pyttsx3
  best-effort voice match; full quality needs language-specific models.
- **Follow-ups:** stream raw audio over the `/audio` channel; true streaming partials for
  Whisper (final-only today; Vosk streams); speaker diarization + emotion/tone; WebRTC/
  Silero VAD; YAMNet/PANNs as the default once models are provisioned.
```
