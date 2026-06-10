# JarvisVR Agent Skills

This directory is the **Agent Skills library** that specializes every agent in the
JarvisVR multi-agent OS. It follows the open
[Agent Skills](https://agentskills.io/specification) standard
([agentskills.io](https://agentskills.io)) verbatim, with a thin JarvisVR
convention layer (`metadata.agent`) so the backend can group skills by the
specialist that owns them.

Skills are *how agents are specialized*: instead of one giant prompt, each
specialist is equipped only with the skills (and tools) relevant to its job, so it
stays focused, debuggable, and swappable. See
[`../docs/ORCHESTRATION.md`](../docs/ORCHESTRATION.md) for the full design (roster
§3, skills system §5) and [`../docs/PROTOCOL.md`](../docs/PROTOCOL.md) for the wire
messages referenced throughout the skill bodies.

## What a skill is (the agentskills.io format)

A skill is a **directory** whose name equals the skill `name`, containing a
`SKILL.md` (YAML frontmatter + Markdown instructions), plus optional resource
folders:

```
skills/<category>/<skill-name>/
├── SKILL.md          # required: frontmatter + instructions
├── scripts/          # optional: runnable helpers
├── references/       # optional: deep-dive docs loaded on demand
└── assets/           # optional: templates / resources
```

`SKILL.md` frontmatter (fields per the spec):

```yaml
---
name: identify-object              # required; 1–64 chars; [a-z0-9-]; matches the parent dir
description: >-                     # required; ≤1024 chars; what it does + WHEN to use it (keywords!)
  Identify a real-world object the user is looking at or asking about …
license: MIT                       # optional
compatibility: Requires JarvisVR agent-backend with perception enabled   # optional, ≤500 chars
metadata:                          # optional, string → string
  agent: perception-agent          # JarvisVR convention: the owning specialist role id
  category: perception
  version: "1.0"
  author: jarvisvr
allowed-tools: identify_object annotate_object read_text   # optional; real JarvisVR tool ids
---
# <Title>
… step-by-step instructions, input/output examples using real tools/widgets/
protocol messages, and edge cases …
```

### The `metadata.agent` convention

`metadata.agent` declares the **owning specialist role id** (one of the roster in
`../docs/ORCHESTRATION.md §3`, or `jarvis` for orchestrator meta-skills). This is
how the backend assigns skills to agents: every skill whose `metadata.agent`
matches an agent's role id becomes part of that agent's skill set.
`metadata.category` mirrors the `skills/<category>/` folder for humans, and
`allowed-tools` lists the real JarvisVR tool ids (from `../holo-tools/tools.json`
plus the backend tools in `../agent-backend/.../agent/tools/`) the skill expects.

## How the backend loads skills (progressive disclosure)

Per `../docs/ORCHESTRATION.md §5.3`:

1. **Discovery (startup):** the loader scans `skills/`, parses only `name` +
   `description` + `metadata` for each skill (~100 tokens each), and groups them by
   `metadata.agent`.
2. **Activation (per sub-task):** when an agent picks up a sub-task, it loads the
   **full `SKILL.md` body** of the matching skill(s) into context.
3. **Execution:** the agent follows the instructions, calling its `allowed-tools`
   and loading `references/` / `scripts/` / `assets/` only as needed.

A machine-readable index of every skill (`{name, agent, category, description,
path}`) is generated at [`index.json`](./index.json).

## Catalog

38 skills across 10 agents.

| Skill | Agent | What it does |
| ----- | ----- | ------------ |
| `task-decomposition` | `jarvis` | Break a goal into a sub-task DAG and emit `orchestration.plan`. |
| `agent-routing` | `jarvis` | Route each sub-task to the best specialist (or fan out to sub-agents). |
| `result-synthesis` | `jarvis` | Merge specialists' results into one spoken reply + final layout. |
| `clarify-intent` | `jarvis` | Ask one clarifying question only when genuinely blocked. |
| `identify-object` | `perception-agent` | Name the object the user is looking at and label it in place. |
| `read-and-translate-sign` | `perception-agent` | OCR and translate a sign/menu/label from the camera. |
| `describe-surroundings` | `perception-agent` | Describe the room and pin labels on a few objects. |
| `locate-remembered-object` | `perception-agent` | Remember and recall where an object was last seen. |
| `web-research` | `research-agent` | Look something up and present a sourced answer. |
| `summarize-source` | `research-agent` | Condense one URL / document / text into key points. |
| `news-digest` | `research-agent` | Pull current headlines into a news feed. |
| `market-briefing` | `research-agent` | Quotes for a watchlist plus an optional trend chart. |
| `manage-timers` | `productivity-agent` | Start/stop countdowns and Pomodoro focus sessions. |
| `set-reminders` | `productivity-agent` | Set time/context reminders and fire them when due. |
| `capture-note` | `productivity-agent` | Capture notes fast; pin sticky notes in space. |
| `manage-tasks` | `productivity-agent` | Maintain a checkable to-do list hologram. |
| `manage-calendar` | `productivity-agent` | Show the agenda and answer schedule questions. |
| `control-lighting` | `smart-home-agent` | Lights on/off, brightness, grouped by room. |
| `manage-climate` | `smart-home-agent` | Adjust thermostats and blinds. |
| `secure-home` | `smart-home-agent` | Locks/cameras/sensors, with confirmation to unlock. |
| `run-home-scene` | `smart-home-agent` | Apply a named multi-device scene/routine. |
| `show-map` | `navigation-agent` | Interactive 3D map or globe with markers. |
| `wayfind` | `navigation-agent` | Directions with a navigation arrow + ETA. |
| `measure-space` | `navigation-agent` | Measure real-world distances/areas with a tape. |
| `remember-location` | `navigation-agent` | Save and return to named places. |
| `control-media-playback` | `media-agent` | Play/pause/seek audio and video. |
| `create-image` | `media-agent` | Generate images from a text prompt. |
| `set-soundscape` | `media-agent` | Looping ambient soundscapes for focus/sleep. |
| `live-translate` | `communication-agent` | Real-time two-way conversation translation. |
| `caption-conversation` | `communication-agent` | Live rolling captions of speech Jarvis hears. |
| `draft-message` | `communication-agent` | Draft a message for review before sending. |
| `compose-workspace` | `stage-agent` | Arrange holograms into a comfortable layout. |
| `present-data` | `stage-agent` | Pick the right viz (table/chart/graph/globe) and place it. |
| `annotate-reality` | `stage-agent` | World-anchored labels/boxes/pins on real things. |
| `declutter-space` | `stage-agent` | Tidy, close, and consolidate holograms. |
| `configure-llm` | `system-agent` | View/change the LLM provider, model, API key (hot-swap). |
| `manage-privacy` | `system-agent` | Control camera/mic/gaze capture; show what's active. |
| `run-diagnostics` | `system-agent` | Health check: connection, perception, thermal, tools. |

### Per-agent breakdown

| Agent | Skills |
| ----- | ------ |
| `jarvis` | 4 |
| `perception-agent` | 4 |
| `research-agent` | 4 |
| `productivity-agent` | 5 |
| `smart-home-agent` | 4 |
| `navigation-agent` | 4 |
| `media-agent` | 3 |
| `communication-agent` | 3 |
| `stage-agent` | 4 |
| `system-agent` | 3 |
| **Total** | **38** |

## Bundled resource examples

A few skills demonstrate the optional resource folders:

- **`scripts/`** — `research/market-briefing/scripts/build_ticker.py` (build
  `stocks_ticker` props from quote pairs) and
  `navigation/measure-space/scripts/distance.py` (Euclidean distance → tape
  props). Both are pure-stdlib and runnable: `python3 <script> --help`.
- **`references/`** — `communication/live-translate/references/language-codes.md`
  (BCP-47 quick reference, loaded on demand).
- **`assets/`** — `smart-home/run-home-scene/assets/scenes.example.json` (starter
  scene definitions to clone per home).

## Extending

- **Add a skill:** create `skills/<category>/<name>/SKILL.md` with
  `metadata.agent` set; the loader auto-assigns it (see
  `../docs/ORCHESTRATION.md §7`). Keep the body under ~300 lines and push deep
  material into `references/`.
- **Add an agent:** register the new role in the backend; it automatically
  receives every skill whose `metadata.agent` matches its role id.
