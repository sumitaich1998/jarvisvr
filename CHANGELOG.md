# Changelog

All notable changes to JarvisVR are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

- Community health files, CI, and a trending-grade README for the public launch.

## [0.1.0] — 2026-06-08

First public scaffold of JarvisVR — an AI agentic operating system for mixed
reality on the Meta Quest 3. All components run **fully offline** out of the box
via deterministic mock providers, and integrate over one versioned WebSocket
protocol.

### Added — Core v1

- **`unity-client/`** — Quest 3 Unity (2022 LTS) mixed-reality shell: passthrough
  MR, WebSocket client with heartbeat + reconnect, a Hologram Manager that
  spawns/updates/destroys widgets from `holo.*` messages, hand/controller
  interaction routing, and a persistent "Jarvis presence" (orb + captions).
- **`agent-backend/`** — the Python "brain": a WebSocket server hosting an LLM
  agent loop (plan → call tools → observe → respond) that streams
  `agent.thinking` / `agent.speech` and emits `holo.*` render commands. Ships a
  deterministic **MockLLM** so the whole stack is demoable with no API key.
- **`voice-service/`** — wake word ("Jarvis") + streaming STT + TTS pipeline,
  every stage pluggable with an offline fallback (energy wake / mock STT / tone
  TTS) so it runs headless with no models or audio hardware.
- **`holo-tools/`** — the holographic widget catalog. **12 v1 widgets**
  (`weather_orb`, `chart_3d`, `model_viewer`, `panel`, `text_label`, `button`,
  `timer`, `media_player`, `map_3d`, `smart_home_panel`, `todo_list`,
  `image_board`) with strict JSON-Schema `props` validation, agent tool/function
  schemas, and Python/TypeScript bindings.
- **`shared-protocol/`** — JSON Schema as the single source of truth plus
  hand-written Python, C#, and TypeScript bindings + validators.
- **`infra/`** — `docker-compose` for the backend + voice services, a
  dependency-light **mock brain**, and an **end-to-end conformance harness** that
  drives a scripted conversation and validates every frame.
- **`docs/`** — `ARCHITECTURE.md`, `docs/PROTOCOL.md`, `docs/HOLO_TOOLS.md`, and
  `docs/FEATURES.md`.

### Added — Multimodal Perception (protocol v1.1)

- **Sight** — `unity-client` captures the forward RGB **passthrough camera**
  (Meta Passthrough Camera API) and streams JPEG frames + camera pose
  (`perception.vision_frame`), pull-based at 1–3 fps, binary on `/vision` or
  inline base64.
- **Hearing** — `voice-service` adds **continuous ambient listening**
  (`perception.audio_scene`) and **sound-event detection**
  (`perception.audio_event`: doorbell, alarm, glass break, …) separate from the
  wake-word/STT path, plus **barge-in** (`client.barge_in`).
- **Attention** — gaze / head-ray (`perception.gaze`) tells the agent what the
  user is looking at.
- **Reasoning** — `agent-backend` keeps a rolling **perception buffer**,
  auto-correlates it with each utterance, answers vision questions
  (*"what is this?"*, *"read this sign"*, *"where did I leave my keys?"*) via a
  multimodal/vision LLM path (deterministic offline mock), and pins answers onto
  real objects with `agent.observation` + `vision_annotation` holograms.
- **Privacy** — all perception streams are **optional, negotiated, and
  pull-based** (`perception.request` start/stop/once); capture runs only while a
  stream is active and `perception.state` always reflects what's live.
- **Protocol** — bumped to `1.1.0` (additive; `1.0.0` clients still supported):
  new `perception.*` messages, `agent.observation`, the `/vision` length-prefixed
  binary transport (§8.2), and the `client.barge_in` / settings messages.

### Added — Widget catalog → 42 widgets

- Grew the catalog from 12 to **42 widgets**: the 12 v1 widgets, **5 perception
  widgets** (`vision_annotation`, `bounding_box_3d`, `live_caption`,
  `vision_feed`, `scene_label`), and **25 feature widgets** (`clock`,
  `world_clock`, `calendar`, `stocks_ticker`, `news_feed`, `translator`,
  `recipe_card`, `whiteboard`, `sticky_note`, `code_viewer`, `document_viewer`,
  `web_panel`, `avatar`, `navigation_arrow`, `health_ring`, `music_visualizer`,
  `graph_3d`, `data_table`, `measuring_tape`, `pomodoro`, `image_gen_viewer`,
  `volumetric_globe`, `system_launcher`, `notification_toast`, `settings_panel`).

### Added — Universal LLM provider support

- Pluggable **20+ LLM providers** behind one interface: OpenAI, Anthropic,
  Google Gemini, Groq, OpenRouter, Mistral, DeepSeek, xAI/Grok, Together,
  Perplexity, Fireworks, Azure, AWS Bedrock, Vertex, Cohere, and local
  Ollama/LM Studio/vLLM, any OpenAI-compatible endpoint, or `mock` for offline.
  Reached natively, via a generic OpenAI-compatible client, or through the
  LiteLLM universal adapter.
- **Install-time key wizard** (`jarvis-backend setup`): pick a provider, enter
  the API key with masked input; the key is written to `agent-backend/.env`
  (`chmod 600`) and never printed or logged.
- **Runtime key config**: change the provider / model / API key in-headset via
  the Settings panel (`client.settings_update` / `server.settings`, §5.15) with
  hot-swapping; keys are never echoed back.

[Unreleased]: https://github.com/sumitaich1998/jarvisvr/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/sumitaich1998/jarvisvr/releases/tag/v0.1.0
