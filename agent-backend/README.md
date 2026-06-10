# agent-backend — the JarvisVR "brain"

The LLM **agent orchestration server** for [JarvisVR](../README.md). It is the
WebSocket **protocol endpoint** the Quest 3 `unity-client` connects to: the user
speaks, an LLM agent plans, calls tools, streams `agent.thinking` + `agent.speech`,
and emits `holo.*` commands that render interactive 3D holograms in the room.

**v1.1 — Multimodal Perception:** Jarvis can now **see** (passthrough camera
frames), **hear** (ambient sound events), and know what the user is **looking at**
(gaze). It keeps a rolling perception buffer, auto-correlates it with each
utterance, answers questions like *"what is this?"* / *"read this sign"* /
*"where did I leave my keys?"*, and pins answers onto real objects with
`vision_annotation` holograms — all working **fully offline with no API keys** via
a deterministic **mock LLM + mock vision**.

> Conforms to [`docs/PROTOCOL.md`](../docs/PROTOCOL.md) **v1.1** (envelope `v` =
> `1.1.0`; §8 perception) and [`ARCHITECTURE.md`](../ARCHITECTURE.md). Listens on
> `0.0.0.0:8765`, path `/jarvis` (JSON) + `/vision` (binary frames).

---

## Quickstart

```bash
cd agent-backend
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev,providers]"   # core + tests + universal LiteLLM adapter

# Configure your LLM provider + API key (interactive; choose "mock" to skip).
jarvis-backend setup                 # asks which provider, then your API key (masked)

# Run the server (uses whatever setup wrote; mock if you skipped).
python -m jarvis_backend
# -> JarvisVR agent-backend listening on ws://0.0.0.0:8765/jarvis
```

Or do it all from the repo with one command:

```bash
cd infra && make install             # venv + install + setup wizard (asks for your key)
```

`jarvis-backend` is a console script with subcommands:

```bash
jarvis-backend            # run the server (default)
jarvis-backend setup      # configure provider + API key (alias: init)
jarvis-backend providers  # list every supported LLM provider
```

No key? Everything still runs offline on the deterministic **mock** provider.

### Talk to it (one-liners)

With [`websocat`](https://github.com/vi/websocat):

```bash
# 1) handshake, then ask for the weather; you'll see agent.* and holo.spawn frames
printf '%s\n%s\n' \
  '{"v":"1.0.0","id":"1","type":"client.hello","ts":1,"payload":{"device":"quest3"}}' \
  '{"v":"1.0.0","id":"2","type":"user.text","ts":2,"payload":{"text":"show weather in tokyo"}}' \
  | websocat ws://127.0.0.1:8765/jarvis
```

With `wscat` (`npm i -g wscat`):

```bash
wscat -c ws://127.0.0.1:8765/jarvis
> {"v":"1.0.0","id":"1","type":"client.hello","ts":1,"payload":{"device":"quest3"}}
> {"v":"1.0.0","id":"2","type":"user.text","ts":2,"payload":{"text":"show weather in tokyo and start a 5 minute timer"}}
```

A scripted Python smoke client lives at [`scripts/smoke_client.py`](scripts/smoke_client.py):

```bash
python scripts/smoke_client.py "show weather in tokyo"
python scripts/smoke_client.py "what is this on my desk?"   # vision turn
```

A **perception** turn (vision Q&A) — feed detected objects + ask:

```bash
printf '%s\n%s\n%s\n' \
 '{"v":"1.1.0","id":"1","type":"client.hello","ts":1,"payload":{"device":"quest3","capabilities":{"camera_passthrough":true}}}' \
 '{"v":"1.1.0","id":"2","type":"perception.scene_objects","ts":2,"payload":{"objects":[{"label":"coffee mug","confidence":0.8,"position":[0.3,0.8,0.7],"anchor":"world"}]}}' \
 '{"v":"1.1.0","id":"3","type":"user.text","ts":3,"payload":{"text":"what is this on my desk?","attach_perception":true}}' \
 | websocat ws://127.0.0.1:8765/jarvis
# -> agent.observation + holo.spawn vision_annotation{label:"coffee mug"}
```

Binary passthrough frames go to the parallel endpoint
`ws://127.0.0.1:8765/vision?session=<id>` (length-prefixed, §8.2).

The `infra/` mock client / e2e harness drives this same protocol against the
server at `agent-backend:8765` (see `infra/`).

---

## How it works

```
user.text ─▶ AgentSession.handle_user_text
                │  emit agent.transcript (echo)
                │  emit agent.thinking{planning}
                ▼
        ┌──────────────── agent loop (plan → call tools → observe → respond) ────────────────┐
        │  llm.complete(messages, tool_specs)                                                  │
        │     ├─ tool_calls? → for each: emit agent.thinking{tool_call} ; run tool ;           │
        │     │                          translate ToolResult.directives → holo.spawn/update/  │
        │     │                          destroy (server-assigned object_id) ; observe         │
        │     └─ final text? → stream agent.speech{final:false…final:true}                     │
        └──────────────────────────────────────────────────────────────────────────────────┘
                │  (≥2 new holograms? emit holo.layout{arc})
                ▼
        emit agent.thinking{done}  ; memory.maybe_summarize()
```

* **LLM providers** (`agent/llm.py`) — one `LLMProvider` interface, three impls:
  * **`MockLLM`** (default): deterministic, keyword/intent-driven planner. It maps
    user text → tool calls, runs them, then synthesizes the spoken reply from the
    tools' structured results. No network, fully reproducible — perfect for demos
    and tests.
  * **`OpenAILLM`** / **`AnthropicLLM`**: real function/tool-calling. Selected via
    `JARVIS_LLM`. If the key or SDK is missing, the server logs a warning and
    **falls back to mock** instead of crashing.
* **Tools** (`agent/tools/`) — a registry of network-free tools, each returning
  structured `data` (the LLM observation) **and** holo *directives*: `start_timer`,
  `stop_timer`, `get_time`, `take_note` / `list_notes`, `set_reminder`,
  `show_panel` / `show_text`, `open_widget` (generic), and `get_weather`
  (deterministic mock unless `JARVIS_WEATHER_API_KEY` is set → live OpenWeatherMap).
* **Holograms** (`catalog.py`) — loads the widget catalog from
  `holo-tools/registry.json` when present; otherwise uses a **built-in fallback
  catalog** (`weather_orb`, `timer`, `panel`, `chart_3d`, `model_viewer`,
  `media_player`, `map_3d`, `smart_home_panel`). `widget_type` + `props` are
  validated against the catalog before spawning. The agent assigns each object a
  UUID `object_id`, a transform (anchor/position/rotation/scale) and interactions.
* **Memory** (`agent/memory.py`) — short-term conversation history (with a
  summarization hook that folds old turns once it grows) + a JSON long-term
  key/value store for notes/reminders that persists across sessions.
* **Interactions** — `client.interaction` (e.g. tap the timer) is routed back into
  the tool layer to update holograms (`holo.update`/`holo.destroy`); unhandled
  interactions are fed back to the agent/LLM so it can decide.

> **Note on `shared-protocol/`:** the canonical Python protocol bindings will be
> published there later. `protocol.py` is implemented self-contained (mirroring
> `docs/PROTOCOL.md` exactly) so this service isn't blocked; reconcile when
> `shared-protocol` lands.

---

## Multimodal perception (v1.1)

```
/vision (binary frames) ┐
perception.scene_objects ┤   ┌─ PerceptionBuffer (rolling: frames, sounds, gaze,
perception.gaze          ┼──▶│   detected objects, state) ── current_context()
perception.audio_event   ┤   └─ deterministic mock "vision" (offline scene desc)
perception.vision_frame  ┘
        │
user.text{attach_perception:true} ─▶ agent: perception.request(once/start/stop)
        │   emit agent.thinking{perceiving|looking}
        ▼   run vision tool → emit agent.observation{text, annotations}
        spawn vision_annotation / bounding_box_3d on the real object
```

* **Transports**: binary length-prefixed frames on `ws://host:8765/vision`
  (`[4-byte BE len][JSON header][JPEG bytes]`, §8.2) routed to the session via
  `?session=<id>`; or inline `perception.vision_frame` (base64) on `/jarvis`.
* **Perception buffer** (`perception/buffer.py`): per-session rolling store of the
  latest N frames (+ decoded size/thumbnail metadata), audio events/scenes, latest
  gaze, and detected `scene_objects`; exposes "current perception context".
* **Multimodal LLM** (`agent/llm.py`): `complete(..., images=…)`. Real providers
  (OpenAI/Anthropic) get image content blocks; **MockLLM** "sees" deterministically
  via the perception buffer + a synthesized scene description, so vision Q&A works
  offline. The current perception context is auto-attached to a turn when
  `attach_perception` is set (default true while vision is active or the utterance
  is clearly about sight/sound).
* **Control loop** (`agent/agent.py`): decides when to enable sight/hearing, emits
  `perception.request` (`start`/`once`/`stop` — privacy/battery), emits
  `agent.observation` (narration + spatial annotations), and stops streams when
  done. *"watch the room"* / *"stop watching"* toggle continuous vision.
* **Privacy**: cameras/mics are only requested while a stream is active;
  `perception.state` is tracked; proactive observations are **opt-in**
  (`JARVIS_PROACTIVE=1`).

### Perception & feature tools

`describe_view`/`look`, `identify_object`/`what_is_this`, `read_text` (OCR),
`translate_text`, `translate_view`, `remember_object` + `find_object` (spatial
recall), `identify_sound`, `measure`, plus knowledge/integrations `web_search`,
`get_news`, `get_stocks`, `get_calendar`, `navigate_to` — all mock-friendly. On
top of these, a `show_<widget>` **spawn tool is generated for every catalog
widget** (loaded from `holo-tools/tools.json` + `registry.json`, with a built-in
fallback), so the agent can summon any of the 40+ widgets.

### Memory (v1.1)

`agent/memory.py` adds **episodic** memory (events with ts + pose/anchor),
**semantic** facts (key/value), and a **spatial index** of seen objects keyed by
name → pose/anchor. Detected `scene_objects` are auto-indexed so *"where did I
leave my keys?"* recalls a place and drops a marker + navigation arrow.

---

## Multi-agent orchestration (v1.2)

JarvisVR is a **hierarchical multi-agent OS** (see
[`docs/ORCHESTRATION.md`](../docs/ORCHESTRATION.md), PROTOCOL §9). **Jarvis** (L0,
`agent/orchestrator.py`) never does domain work — it **conducts**:

```
decompose → route → execute (parallel where independent) → synthesize
```

1. **Decompose** the goal into tool calls — offline `MockLLM` uses the deterministic
   keyword planner (`plan_tool_calls`); real providers use tool/function-calling.
2. **Route** each call to the owning **specialist** (`agent/agents.py`): `perception-`,
   `research-`, `productivity-`, `smart-home-`, `navigation-`, `media-`, `communication-`,
   `stage-`, `system-agent` — grouped by `agents.role_for_tool`.
3. **Execute** specialists concurrently (`asyncio.gather`); each is a thin wrapper that
   runs its tools (reusing the existing registry/holo/perception layers) and activates
   its **Skills**. `research-agent` can spawn **summarizer sub-agents** (dotted ids
   `a1.1`) — multi-level delegation.
4. The **stage-agent** composes the final spatial layout; **Jarvis synthesizes** one
   `agent.speech`.

It emits the v1.2 wire messages: `orchestration.plan` (once), `orchestration.agent_status`
(`queued → working → [delegating] → done/failed`), `orchestration.handoff` (sub-agents),
and tags `agent.thinking` with `agent_id`/`role`/`skill`. `server.hello_ack` advertises
`orchestration: true` + the `agents` roster. A trivial goal yields a 1-agent plan, so the
single-turn UX is unchanged. Toggle with `JARVIS_ORCHESTRATION` (default on).

### Agent Skills (agentskills.io)

`skills/loader.py` scans `JARVIS_SKILLS_DIR` (default `<repo>/skills`) for
`<category>/<name>/SKILL.md` (YAML frontmatter + Markdown body) with **progressive
disclosure**: discovery parses only `name`+`description`+`metadata` (~100 tokens/skill);
`activate(skill)` loads the full body on demand. Skills are grouped by `metadata.agent`
and auto-assigned to that specialist. A missing `skills/` dir is fine — agents fall back
to built-in tool mappings, and the registry simply enriches behavior when present.

---

## Per-agent memory, tracing & authoring (v1.3)

**Per-agent memory** (`agent/agent_memory.py`): every specialist role gets an isolated
memory namespace — persisted long-term under `agent_mem:<role>` (survives restarts) plus a
per-turn short-term scratch. Agents read/write **only** their own namespace; the
orchestrator recalls before acting and stores results after, emitting `memory_read` /
`memory_write` trace events. Inspect any agent with `client.agent_inspect` →
`server.agent_info` (persona, tools, skills, memory summary + recent items).

**Tracing** (`agent/trace.py`): the orchestrator records a per-turn **Trace** keyed by
`plan_id` — ordered, secret-**redacted** entries (`memory_read`, `memory_write`,
`skill_activated`, `tool_call`, `tool_result`, `observation`, `delegated`, `speech`,
`error`) with `agent_id`/`role`/`parent`/`level`/`ts`/`duration_ms`. A bounded ring buffer
keeps recent turns; `client.trace_get` → `server.trace` fetches a full turn. Live
`orchestration.trace_event` streams **only when subscribed** (`client.trace_subscribe`),
default off. API keys and raw frames/audio are never traced — only short summaries.
Toggle recording with `JARVIS_TRACE` (default on).

**In-headset authoring** (`agent/authoring.py`): create/update/delete agents and Skills at
runtime. `client.author_list` → `server.authoring` lists agents + skills (each
`source: builtin|user`), categories, and pickable tool ids. `client.author_skill` writes a
sanitized `SKILL.md` under the skills root (with `metadata.source: user`) and **hot-reloads**
the registry so the owning agent gains it next turn. `client.author_agent` registers a user
role (persisted to `.data/user_agents.json`) that immediately joins routing. **Safety:**
agentskills.io name rules reject path traversal/reserved names, writes are confined to the
skills root, and **built-ins are immutable** — only `source:user` items are editable. Errors
come back as `server.error` (`invalid_skill` | `invalid_agent` | `name_conflict` |
`forbidden`).

---

## Configuration

All via environment (or an `.env` file — see [`.env.example`](.env.example)). Every
value has a safe default.

| Env var | Default | Purpose |
| --- | --- | --- |
| `JARVIS_HOST` | `0.0.0.0` | Bind host |
| `JARVIS_PORT` | `8765` | Bind port |
| `JARVIS_WS_PATH` | `/jarvis` | WebSocket path |
| `JARVIS_LLM` | `mock` | `mock` \| `openai` \| `anthropic` |
| `JARVIS_OPENAI_MODEL` | `gpt-4o-mini` | OpenAI model |
| `JARVIS_ANTHROPIC_MODEL` | `claude-3-5-sonnet-latest` | Anthropic model |
| `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` | — | Provider keys |
| `JARVIS_VISION` | `mock` | Vision provider: `mock` \| `openai` \| `anthropic` |
| `JARVIS_PERCEPTION` | `1` | Master switch for perception |
| `JARVIS_PROACTIVE` | `0` | Proactive observations on notable sounds (opt-in) |
| `JARVIS_VISION_FPS` | `2` | Default fps requested when enabling vision |
| `JARVIS_VISION_BUFFER` | `8` | Recent frames kept in the perception buffer |
| `JARVIS_HOLO_REGISTRY` | `../holo-tools/registry.json` | Widget catalog (+ built-in fallback merge) |
| `JARVIS_WEATHER_API_KEY` | — | Optional live weather (OpenWeatherMap) |
| `JARVIS_DATA_DIR` | `.data` | Long-term / episodic / spatial memory dir |
| `JARVIS_ORCHESTRATION` | `1` | v1.2 multi-agent orchestration (0 = single-agent loop) |
| `JARVIS_SKILLS_DIR` | `../skills` | Agent Skills dir + in-headset authoring root (missing is fine) |
| `JARVIS_TRACE` | `1` | v1.3 per-turn tracing (streaming gated by trace_subscribe) |
| `JARVIS_MAX_STEPS` | `6` | Max plan→tool→observe iterations / turn |
| `JARVIS_LOG_LEVEL` | `INFO` | Log level |
| `JARVIS_LOG_JSON` | `0` | `1` = one-line JSON logs |

### Universal multi-provider support

JarvisVR works with **effectively any** LLM provider. A registry
([`providers.py`](jarvis_backend/providers.py)) describes each one — id, display
name, key env var, default model(s), base_url, and capabilities (tools/vision).
Pick one with `JARVIS_LLM=<id>` (or, easier, `jarvis-backend setup`).

| How it's reached | Providers |
| --- | --- |
| **Native SDK** | `openai`, `anthropic` |
| **Generic OpenAI-compatible** (plain `httpx`, no extra SDK) | `gemini`, `groq`, `openrouter`, `deepseek`, `xai`, `mistral`, `together`, `perplexity`, `fireworks`, `ollama`, `lmstudio`, `vllm`, `custom` |
| **LiteLLM universal adapter** (`pip install '.[providers]'`) | the above **plus** `azure`, `bedrock`, `vertex`, `cohere`, and 100+ more |

Force everything through LiteLLM with `JARVIS_USE_LITELLM=1`. Run
`jarvis-backend providers` for the full list with key vars + defaults.

Key resolution precedence: the provider's conventional env var (e.g.
`OPENAI_API_KEY`, `GEMINI_API_KEY`, `GROQ_API_KEY`) → generic `JARVIS_LLM_API_KEY`.

```bash
# Examples (or just run `jarvis-backend setup`):
jarvis-backend setup --provider openai            # prompts for OPENAI_API_KEY (masked)
JARVIS_LLM=groq        GROQ_API_KEY=gsk-…   python -m jarvis_backend
JARVIS_LLM=gemini      GEMINI_API_KEY=…     python -m jarvis_backend   # OpenAI-compatible
JARVIS_LLM=ollama      JARVIS_OLLAMA_BASE_URL=http://localhost:11434/v1 python -m jarvis_backend
JARVIS_LLM=custom      JARVIS_CUSTOM_BASE_URL=https://my-host/v1 JARVIS_LLM_API_KEY=… python -m jarvis_backend
pip install -e ".[providers]"; JARVIS_LLM=bedrock python -m jarvis_backend   # via LiteLLM + AWS creds
```

Tool/function-calling and vision/multimodal image blocks are preserved across
providers that support them, and degrade gracefully otherwise. Missing key/SDK →
automatic fallback to `mock` (logged), **never** a crash.

### `jarvis-backend setup` — the install-time key prompt

The wizard lists providers, lets you pick one, prompts for the **API key with
masked, non-echoing input** (`getpass`), the model (sensible default per
provider), and a `base_url` for custom/local endpoints. It can optionally
validate the key with a tiny live call (skippable/offline), then writes/updates
`.env`:

* **The key is never printed or logged** — only a masked `•••• (N chars)`
  confirmation. `.env` is written atomically and **`chmod 600`**.
* Idempotent + re-runnable: reconfigure, add more providers, switch the default.
* Non-interactive for CI: `jarvis-backend setup --non-interactive --provider openai --api-key "$OPENAI_API_KEY"`.

---

## Testing

```bash
pip install -e ".[dev]"
pytest
```

The suite covers: protocol envelope round-trip + validation, the mock agent
producing a valid `holo.spawn` for "show weather in tokyo", heartbeat echo,
unknown-type-ignored, a full streamed turn over a real socket, bad-envelope
errors, and the tools. **v1.1**: a vision turn ("what is this on my desk?" →
`agent.observation` + valid `vision_annotation`), `/vision` binary ingest over a
real socket, `perception.request` emission, sound-event handling, the perception
buffer + binary codec, and a conformance test that runs **every** perception/
knowledge tool against the **canonical** `holo-tools/registry.json` (closed
schemas) asserting zero `server.error`.

---

## Docker

```bash
docker build -t jarvisvr/agent-backend .
docker run --rm -p 8765:8765 jarvisvr/agent-backend
```

`infra/docker-compose.yml` references this image as service **`agent-backend`** on
port **8765**. Mount the catalog at `/holo-tools/registry.json` (or set
`JARVIS_HOLO_REGISTRY`) to use the canonical catalog; otherwise the built-in
fallback is used.

---

## File tree

```
agent-backend/
├── pyproject.toml            # packaging, pinned deps, [project.scripts] jarvis-backend
├── Dockerfile                # python:3.11-slim, exposes 8765
├── .env.example
├── README.md
├── scripts/
│   └── smoke_client.py       # connect + drive one turn end-to-end
├── jarvis_backend/
│   ├── __main__.py           # entrypoint (python -m jarvis_backend)
│   ├── config.py             # env-driven config (+ vision/perception toggles)
│   ├── logging_setup.py      # structured logging
│   ├── protocol.py           # v1.1 envelope + payload models (incl. perception.*)
│   ├── catalog.py            # widget catalog: registry + fallback merge + validation
│   ├── server.py             # WebSocket server: /jarvis + /vision + perception routing
│   ├── perception/
│   │   ├── buffer.py         # rolling PerceptionBuffer + /vision binary codec
│   │   └── vision.py         # deterministic offline scene desc / OCR / translate
│   └── agent/
│       ├── agent.py          # orchestration loop + perception control + observations
│       ├── llm.py            # LLMProvider(+images), MockLLM, OpenAILLM, AnthropicLLM
│       ├── memory.py         # short-term + long-term + episodic/semantic/spatial
│       ├── persona.py        # "You are Jarvis…" (perception-aware) system prompt
│       ├── state.py          # per-session state (objects/refs/store/perception)
│       └── tools/
│           ├── base.py            # Tool, ToolRegistry, ToolResult, holo directives
│           ├── builtins.py        # built-in tools (weather/timer/notes/…)
│           ├── perception_tools.py# vision/OCR/translate/spatial/sound tools
│           ├── knowledge_tools.py # web_search/news/stocks/calendar/navigate
│           └── widget_tools.py    # dynamic show_<widget> spawn tools
└── tests/                    # pytest suite (incl. test_perception.py)
```
