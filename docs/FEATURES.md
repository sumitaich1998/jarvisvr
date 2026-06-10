# JarvisVR — Feature Set & Roadmap

This is the shared feature contract for the parallel build. Components implement features in their
owned directory and align on `docs/PROTOCOL.md` (v1.1). Priorities: **P0** = build now,
**P1** = build if time permits, **P2** = stubbed/roadmap. Owner key: `U`=unity-client,
`B`=agent-backend, `V`=voice-service, `H`=holo-tools, `I`=shared-protocol/infra.

## 1. Multimodal Perception — "Jarvis can see & hear your room" (P0, core)
| Feature | Owners | Notes |
| --- | --- | --- |
| **Color passthrough vision** — capture forward RGB camera, stream JPEG frames + pose | U, B, I | Meta Passthrough Camera API; `perception.vision_frame`; pull-based 1–3 fps |
| **Continuous ambient hearing** — listen to room audio beyond wake word | V, U, B | `perception.audio_scene`, ambient transcript + soundscape |
| **Sound-event detection** — doorbell, alarm, name called, phone, glass break… | V, B | `perception.audio_event` |
| **Gaze / attention** — know what the user is looking at | U, B | `perception.gaze` (eyes if available, else head ray) |
| **Realtime multimodal turns** — answer about current sight+sound | B | rolling perception buffer auto-attached to each utterance |
| **Vision Q&A / "what is this?"** | B, H | vision LLM; spawns `vision_annotation` |
| **OCR + read & translate signs/labels** | B, H, V | read text in view → `panel`/`live_caption` + TTS |
| **Object detection + 3D labels in the room** | B, U, H | `bounding_box_3d`, `vision_annotation`, world-anchored |
| **Spatial memory** — "where did I leave my keys?" remember seen objects + place | B | episodic memory keyed by anchor/pose |
| **Proactive perception** — Jarvis notices & offers help | B | gated by user opt-in; `agent.observation` |
| **Privacy controls** — capture only while streams active; on-device gating; indicators | U, B, I | `perception.request` start/stop/once; `perception.state` |

## 2. Agent Intelligence (P0–P1)
| Feature | Owners |
| --- | --- |
| Planning + tool-calling loop (plan→tools→observe→respond) | B |
| Vision-capable / multimodal LLM provider (OpenAI/Anthropic/local) + offline mock | B |
| Memory: short-term, long-term (notes/prefs), **episodic** (events), **semantic** (facts) | B |
| Web search / knowledge Q&A | B (P1) |
| Real-time translation & multilingual conversation | B, V |
| Personalization & user profile (name, preferences, routines) | B |
| Proactive reminders triggered by time **or** perception | B |
| Conversation barge-in / interruptibility | V, B |
| Multi-step task automation ("routines"/macros) | B (P1) |

## 3. Holographic UI & Widgets (P0–P1) — owner `H` (schemas) + `U` (renderers)
Existing (v1): `weather_orb, chart_3d, model_viewer, panel, text_label, button, timer,
media_player, map_3d, smart_home_panel, todo_list, image_board`.

New perception widgets (P0): `vision_annotation, bounding_box_3d, live_caption, vision_feed,
scene_label`.

New feature widgets (P1, add as many as feasible): `clock` / `world_clock`, `calendar`,
`stocks_ticker`, `news_feed`, `translator`, `recipe_card`, `whiteboard` (sketch), `sticky_note`,
`code_viewer`, `document_viewer`, `web_panel` (browser surface), `avatar` (Jarvis face/call),
`navigation_arrow` (wayfinding), `health_ring` (fitness), `music_visualizer`, `graph_3d`
(node/network), `data_table`, `measuring_tape` (spatial measure), `pomodoro`, `image_gen_viewer`
(AI images), `volumetric_globe`, `system_launcher` (app grid), `notification_toast`,
`settings_panel`.

UX (P0–P1, owner `U`): spatial anchoring & **persistence** across sessions (spatial anchors),
multi-window management, follow/anchor/world-lock modes, hand-menu / wrist UI, gaze+pinch+voice
multimodal interaction, grab/resize/throw physics, billboard & lazy-follow.

## 4. Voice & Audio (P0–P1) — owner `V`
Wake word "Jarvis" · streaming STT · natural TTS persona · **continuous ambient listening** ·
sound-event detection · VAD/endpointing · barge-in · multi-language · (P2) speaker diarization,
emotion/tone, voice biometrics.

## 5. Spatial OS & System (P1) — owners `U`, `B`
App/widget launcher & switcher · settings & profiles · notification center · session
persistence · "home space" layout save/restore · quick actions / wrist menu · onboarding ·
(P2) multi-user shared sessions, hand-off between devices.

## 6. Integrations (P1–P2) — owner `B` (pluggable, mock by default)
Smart home (lights/thermostat/locks) · calendar · email/messages summary · music/media ·
maps/navigation · web search · weather · stocks/news · (P2) phone notifications mirror,
generative images, 3D asset generation.

## 7. Privacy, Safety & Ops (P0 where noted)
Capture indicators + `perception.state` (P0) · stream consent via `perception.request.reason`
(P0) · in-memory-by-default perception (P0) · redaction/opt-in persistence (P1) · rate/thermal
guards on vision fps (P0, owner `U`/`B`) · graceful offline mock for **every** capability (P0).

## 8. Build-now checklist (this iteration)
- [ ] **U**: Passthrough Camera API capture + JPEG encode + `/vision` streaming; ambient mic; gaze; perception widget renderers; fps/thermal guard; privacy indicator.
- [ ] **B**: perception buffer; multimodal/vision LLM path (mock returns deterministic scene description offline); `perception.request` control; `agent.observation`; OCR/translate/vision-QA tools; spatial + episodic memory; many new widget tools.
- [ ] **V**: continuous ambient listening + sound-event detection + ambient transcript; barge-in; emit `perception.audio_*`.
- [ ] **H**: add 5 perception widgets + as many P1 feature widgets/tools as feasible (registry-driven, validated).
- [ ] **I**: v1.1 schemas/bindings for all `perception.*` + `agent.observation`; extend mock backend + e2e to drive a vision turn.
