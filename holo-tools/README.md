# holo-tools — JarvisVR Holographic Widget Catalog

This package is the **bridge between the AI agent and what the user sees**. It defines the
catalog of 3D holographic widgets the agent can summon, their `props` schemas, supported
interactions, and the agent-facing tool/function-calling schemas.

**Catalog version 1.1.0** — 42 widgets: the 12 v1.0 widgets, 5 **perception** widgets that let
Jarvis annotate the real world (PROTOCOL.md §8.5), and 25 feature widgets. See the
["annotating the real world"](../docs/HOLO_TOOLS.md#annotating-the-real-world-v11-perception)
section of the docs.

It is consumed by:

- **`agent-backend/`** — to expose tools to the LLM and to **validate** `widget_type` + `props`
  before sending `holo.spawn` / `holo.update` (PROTOCOL.md §6 conformance).
- **`unity-client/`** — to map each `widget_type` → a Unity **prefab** (`prefab_id`) and to know
  which interactions/events each widget supports.
- **`shared-protocol/` / `infra/`** — TypeScript types for tooling and the e2e harness.

Everything conforms to [`docs/PROTOCOL.md`](../docs/PROTOCOL.md) §5.6 *The Holographic Object*
(and §8 *Multimodal Perception* for the perception widgets). The human-readable catalog lives in
[`docs/HOLO_TOOLS.md`](../docs/HOLO_TOOLS.md).

## Layout

```
holo-tools/
├── registry.json        # ← single source of truth: the widget catalog
├── tools.json           # agent tool/function schemas (derived from registry.json)
├── holo_tools/          # importable Python package (pip install -e .)
│   ├── __init__.py      #   parsed catalog + validators, re-exported
│   ├── loader.py        #   load_registry() / load_tools()
│   ├── validate.py      #   validate_widget() / validate_holo_object()
│   └── tools.py         #   derive tool schemas from the registry
├── ts/
│   └── widgets.ts       # hand-written TypeScript types matching the catalog
├── scripts/
│   └── generate_docs.py # regenerates docs/HOLO_TOOLS.md from the registry
├── tests/               # pytest suite (registry, validation, tools)
├── pyproject.toml       # package: jarvis-holo-tools
└── README.md
```

`registry.json` is the **single source of truth**. `tools.json`, `ts/widgets.ts`, and
`docs/HOLO_TOOLS.md` are all kept consistent with it (and `tools.json` is literally generated
from it — see below).

## registry.json shape

```jsonc
{
  "version": "1.0.0",
  "protocol_version": "1.0.0",
  "anchors": ["world", "head", "hand_left", "hand_right", "surface"],
  "interactions": ["tap", "grab", "release", "drag", "slider", "toggle", "resize", "dwell"],
  "categories": ["information", "data", "media", ...],
  "widgets": [
    {
      "widget_type": "weather_orb",          // snake_case id (used on the wire)
      "title": "Weather Orb",
      "description": "...",
      "category": "information",
      "prefab_id": "Holo_WeatherOrb",         // Unity prefab to instantiate
      "interactions": ["tap", "grab", "resize", "dwell"],
      "default_transform": {                   // PROTOCOL.md conventions
        "anchor": "head", "position": [0.45, 0.1, 0.9],
        "rotation": [0, 0, 0, 1], "scale": [1, 1, 1], "billboard": true
      },
      "events": [ { "name": "expand_forecast", "element": "orb", "action": "tap", ... } ],
      "props_schema": { /* JSON Schema draft 2020-12 for this widget's props */ },
      "example_props": { /* a valid props example */ }
    }
    // ... 42 widgets total (12 v1.0 + 5 perception + 25 feature)
  ]
}
```

## Consume from Python (`agent-backend`, `voice-service`)

```bash
cd holo-tools
python -m venv .venv && source .venv/bin/activate
pip install -e .            # installs jarvis-holo-tools + jsonschema
```

```python
import holo_tools as ht

ht.WIDGET_TYPES            # ['weather_orb', 'chart_3d', 'model_viewer', ...]
ht.WIDGETS_BY_TYPE["timer"]["prefab_id"]   # 'Holo_Timer'
ht.TOOLS_BY_NAME["show_weather"]            # OpenAI/Anthropic-style tool schema

# Validate before sending holo.spawn (raises with a protocol error code on failure)
ht.validate_widget("weather_orb", {"city": "Tokyo", "temp_c": 18, "condition": "clouds"})

# Validate a whole holographic object (PROTOCOL.md §5.6)
ht.validate_holo_object({
    "widget_type": "timer",
    "transform": {"anchor": "head", "position": [0, 0, 1], "rotation": [0, 0, 0, 1], "scale": [1, 1, 1]},
    "props": {"duration_ms": 300000, "remaining_ms": 300000, "state": "running"},
    "interactions": ["tap", "grab"],
})
```

On failure the validators raise `UnknownWidgetError` (code `unknown_widget`) or
`InvalidPropsError` (code `invalid_props`). Turn either into a `server.error` payload:

```python
try:
    ht.validate_widget(widget_type, props)
except ht.HoloValidationError as e:
    send(e.to_error_payload())   # {"code": "...", "message": "...", "fatal": False}
```

## Consume from Unity (`unity-client`, C#)

The client treats `registry.json` as read-only data:

1. Load `registry.json` at startup (ship a copy in `Resources/` or fetch it).
2. Build a `Dictionary<string, GameObject>` mapping `widget_type` → the prefab named by
   `prefab_id` (e.g. `weather_orb` → `Holo_WeatherOrb`).
3. On `holo.spawn`, instantiate the prefab, apply `transform` (meters, quaternion `[x,y,z,w]`,
   `billboard`), and hand `props` to the prefab's controller.
4. Only enable the gestures listed in the object's `interactions` (a subset of the widget's
   supported set), and emit `client.interaction` using the `events[].element` / `action`
   identifiers from the catalog.

## Consume from TypeScript (`shared-protocol`, `infra`)

```ts
import type { HoloObject, WeatherOrbProps, WidgetType } from "../holo-tools/ts/widgets";
import registry from "../holo-tools/registry.json";   // resolveJsonModule: true
```

`ts/widgets.ts` provides per-widget props interfaces, the `WidgetType` union, a
`WidgetPropsMap`, and a discriminated `HoloObject` union for type-safe message construction.

## Regenerating `tools.json`

`tools.json` is derived from `registry.json`. After editing the registry, regenerate it:

```bash
python -c "import json, holo_tools as ht; \
open('tools.json','w').write(json.dumps(ht.derive_tools(ht.REGISTRY), indent=2, ensure_ascii=False) + '\n')"
```

And regenerate the human-readable catalog (`docs/HOLO_TOOLS.md`) the same way:

```bash
python scripts/generate_docs.py
```

## Tests

```bash
cd holo-tools
python -m venv .venv && source .venv/bin/activate
pip install -e ".[test]"      # jarvis-holo-tools + jsonschema + pytest
pytest                        # runs tests/
```

The suite checks that every `props_schema` is a valid draft 2020-12 schema, every widget's
`example_props` validates, good/bad props are accepted/rejected, holo objects validate, and
every tool in `tools.json` references a real `widget_type`.

## Adding a widget

See the **"How to add a new widget"** guide in [`docs/HOLO_TOOLS.md`](../docs/HOLO_TOOLS.md).
In short: add an entry to `registry.json` (with `props_schema` + `example_props`), regenerate
`tools.json`, add the TS types, build the Unity prefab named by `prefab_id`, and run `pytest`.
