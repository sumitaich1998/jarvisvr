# Guide: Add a holographic widget

This is the end-to-end guide for adding a new **holographic widget** to JarvisVR — a
3D thing the AI agent can summon into the room (a chart, a panel, a gauge, a label
on a real object…).

A widget lives in **four** places, in dependency order:

1. **`holo-tools/registry.json`** — the single source of truth: the widget's
   `widget_type`, `props_schema`, `interactions`, `default_transform`, `prefab_id`,
   `events`, and an `example_props`.
2. **Derived artifacts** — `holo-tools/tools.json` (the agent tool schema) and
   `docs/HOLO_TOOLS.md` (the human catalog), both **regenerated** from the registry.
3. **`unity-client/`** — the renderer: a procedural `HoloWidget` C# behaviour (or a
   prefab) that maps `widget_type` → visuals.
4. **`agent-backend/`** — nothing to write in most cases: a `show_<widget>` spawn
   tool is generated automatically for every catalog widget, so the agent can
   summon it. You only add backend code for *richer* behaviour.

> The protocol contract for a widget is [`docs/PROTOCOL.md` §5.6 *The Holographic
> Object*](../PROTOCOL.md#56-the-holographic-object). Everything here conforms to it.

Throughout, we'll add a fictional **`gauge`** widget (a circular dial showing a
0–100 value) as the worked example.

---

## Conventions you must follow

These are enforced by tests and validators ([`holo-tools/holo_tools/validate.py`](../../holo-tools/holo_tools/validate.py)):

- **`widget_type`** and **all prop keys** are `snake_case`.
- **`props_schema`** is **JSON Schema draft 2020-12** with **`additionalProperties: false`**
  (so the agent can't hallucinate unknown props).
- **`prefab_id`** uses the `Holo_<PascalCase>` convention (e.g. `Holo_Gauge`).
- **Coordinates** are right-handed, **meters**, Unity convention (Y up):
  `position = [x, y, z]`, `rotation` = quaternion `[x, y, z, w]`, `scale = [x, y, z]`.
- **`anchor`** is one of `world` · `head` · `hand_left` · `hand_right` · `surface`.
- **`interactions`** are a subset of `tap` · `grab` · `release` · `drag` · `slider`
  · `toggle` · `resize` · `dwell`.
- **`category`** must be one of the registry's `categories` (`information`, `data`,
  `media`, `container`, `primitive`, `control`, `utility`, `productivity`,
  `perception`, `communication`, `navigation`, `health`, `system`, `developer`).

---

## Step 1 — Add the entry to `registry.json`

Open [`holo-tools/registry.json`](../../holo-tools/registry.json) and add a new
object to the top-level `widgets` array. Every existing widget (e.g. `weather_orb`,
`timer`, `vision_annotation`) is a complete template — copy the nearest one.

Here is the full shape, annotated with our `gauge` example:

```json
{
  "widget_type": "gauge",
  "title": "Gauge",
  "description": "A circular dial showing a single 0-100 value with a label and unit.",
  "category": "data",
  "prefab_id": "Holo_Gauge",
  "interactions": ["tap", "grab", "resize"],
  "default_transform": {
    "anchor": "head",
    "position": [0.0, 0.0, 1.0],
    "rotation": [0.0, 0.0, 0.0, 1.0],
    "scale": [1.0, 1.0, 1.0],
    "billboard": true
  },
  "events": [
    {
      "name": "inspect",
      "element": "dial",
      "action": "tap",
      "description": "User tapped the dial to reveal details.",
      "value_schema": null
    }
  ],
  "props_schema": {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "additionalProperties": false,
    "required": ["value", "label"],
    "properties": {
      "value":    { "type": "number", "minimum": 0, "maximum": 100, "description": "Dial value 0-100." },
      "label":    { "type": "string", "minLength": 1, "description": "What the gauge measures." },
      "unit":     { "type": "string", "description": "Unit suffix, e.g. '%'." },
      "color":    { "type": "string", "pattern": "^#([0-9a-fA-F]{6}|[0-9a-fA-F]{8})$", "description": "Hex color #RRGGBB or #RRGGBBAA." }
    }
  },
  "example_props": {
    "value": 72,
    "label": "CPU",
    "unit": "%",
    "color": "#4FC3F7"
  }
}
```

### Field reference

| Field | Required | Purpose |
| ----- | -------- | ------- |
| `widget_type` | ✅ | `snake_case` id used on the wire (`holo.spawn.widget_type`). Must be unique. |
| `title` | ✅ | Human-readable name (used in `docs/HOLO_TOOLS.md`). |
| `description` | ✅ | One sentence; also becomes the agent **tool description**. |
| `category` | ✅ | One of the registry `categories`. |
| `prefab_id` | ✅ | The Unity prefab the client instantiates (`Holo_<PascalCase>`). |
| `interactions` | ✅ | The gestures this widget supports (a subset of the global set). |
| `default_transform` | ✅ | Where it appears when a tool doesn't override placement. |
| `events` | ✅ | The `client.interaction` events the widget emits: `name`, `element` (sub-part id), `action`, optional `value_schema`. |
| `props_schema` | ✅ | JSON Schema (draft 2020-12, closed) for `props`. |
| `example_props` | ✅ | A **valid** example — the test suite validates it against `props_schema`. |

> `events[].element` and `events[].action` are the exact ids the Unity client puts
> in the `client.interaction` message it sends back (see
> [`PROTOCOL.md` §5.11](../PROTOCOL.md#511-clientinteraction)). Keep them stable —
> the backend keys off them.

---

## Step 2 — Regenerate the derived artifacts

`registry.json` is the source of truth; **`tools.json` and `docs/HOLO_TOOLS.md` are
generated from it** and must be regenerated whenever you edit the registry.

```bash
cd holo-tools
python -m venv .venv && source .venv/bin/activate
pip install -e ".[test]"          # jarvis-holo-tools + jsonschema + pytest

# 1) Regenerate the agent tool/function schemas (tools.json):
python -c "import json, holo_tools as ht; \
open('tools.json','w').write(json.dumps(ht.derive_tools(ht.REGISTRY), indent=2, ensure_ascii=False) + '\n')"

# 2) Regenerate the human-readable catalog (docs/HOLO_TOOLS.md):
python scripts/generate_docs.py
```

This gives your widget a generated agent tool. By default the tool is named
`show_<widget_type>` (so `show_gauge`); a curated name can be set in
[`holo_tools/tools.py`](../../holo-tools/holo_tools/tools.py)'s `WIDGET_TOOL_NAMES`
map (e.g. `weather_orb` → `show_weather`, `timer` → `start_timer`). The tool's
`parameters` are your `props_schema` **plus** optional placement overrides
(`anchor`, `position`, `billboard`) and `x_widget_type` / `x_prefab_id` / `x_action`
extension keys.

> `docs/HOLO_TOOLS.md` is a **generated file** — never hand-edit it. The header
> says so. Re-run the two commands above instead.

---

## Step 3 — Add the TypeScript types (optional but recommended)

[`holo-tools/ts/widgets.ts`](../../holo-tools/ts/widgets.ts) is hand-written and
gives `shared-protocol/` and `infra/` type-safe widget props. Add an interface that
mirrors your `props_schema`, then wire it into the `WidgetType` union and
`WidgetPropsMap`:

```ts
export interface GaugeProps {
  value: number;          // 0-100
  label: string;
  unit?: string;
  color?: string;         // #RRGGBB or #RRGGBBAA
}
```

---

## Step 4 — Render it in `unity-client`

The client maps each `widget_type` to a renderer in
[`HologramManager.Spawn`](../../unity-client/Assets/JarvisVR/Holograms/HologramManager.cs).
Resolution order is:

1. A **prefab** registered in a `WidgetRegistry` asset
   ([`WidgetRegistry.cs`](../../unity-client/Assets/JarvisVR/Holograms/WidgetRegistry.cs)),
   keyed by `widget_type` — drop in custom art here to override the default.
2. Otherwise a **procedural behaviour** from
   [`WidgetCatalog.cs`](../../unity-client/Assets/JarvisVR/Holograms/WidgetCatalog.cs)
   (primitives + TextMeshPro, no external art).
3. Otherwise a labelled **placeholder** `PanelWidget` plus a
   `client.error: unknown_widget`.

### Option A — a procedural widget (no art needed)

Subclass [`HoloWidget`](../../unity-client/Assets/JarvisVR/Holograms/HoloWidget.cs).
Build visuals once in `Build()`; react to props in `ApplyProps()` (called on spawn
**and** on every `holo.update`). Use the tolerant prop readers (`GetFloat`,
`GetString`, `GetColor`, …).

```csharp
using UnityEngine;
using TMPro;
using Newtonsoft.Json.Linq;

namespace JarvisVR.Holograms.Widgets
{
    /// <summary>widget_type "gauge". A dial showing a 0-100 value.</summary>
    public class GaugeWidget : HoloWidget
    {
        private Transform _fill;
        private TextMeshPro _label;
        private TextMeshPro _value;

        protected override void Build()
        {
            CreatePrimitive(PrimitiveType.Cylinder, "ring", Vector3.zero,
                new Vector3(0.25f, 0.01f, 0.25f), new Color(0.2f, 0.25f, 0.3f));
            _fill = CreatePrimitive(PrimitiveType.Cylinder, "fill", Vector3.zero,
                new Vector3(0.2f, 0.012f, 0.2f), new Color(0.3f, 0.8f, 1f));
            _value = CreateText("value", "", 0.06f, Color.white, new Vector3(0f, 0.05f, 0f));
            _label = CreateText("label", "", 0.03f, new Color(0.85f, 0.9f, 1f), new Vector3(0f, -0.18f, 0f));
        }

        protected override void ApplyProps(JObject props)
        {
            float value = Mathf.Clamp(GetFloat("value", 0f), 0f, 100f);
            _value.text = $"{Mathf.RoundToInt(value)}{GetString("unit", "")}";
            _label.text = GetString("label", "");
            float s = Mathf.Lerp(0.05f, 0.22f, value / 100f);
            _fill.localScale = new Vector3(s, 0.012f, s);
            SetColor(_fill, GetColor("color", new Color(0.3f, 0.8f, 1f)));
        }
    }
}
```

Register it by adding one line to the `Map` in
[`WidgetCatalog.cs`](../../unity-client/Assets/JarvisVR/Holograms/WidgetCatalog.cs)
(and a matching constant in `Protocol/MessageTypes.cs` / `WidgetTypes`):

```csharp
{ WidgetTypes.Gauge, typeof(GaugeWidget) },
```

The `HologramManager` already handles spawn/update/destroy/layout, applies the
`transform`/`anchor`/`billboard`, configures the listed `interactions`, and replies
with `client.ack`. You don't touch any of that.

### Option B — a prefab

Build a prefab named by your `prefab_id` (`Holo_Gauge`), put a `HoloWidget`
subclass on its root, and add an entry to a **WidgetRegistry** asset
(*Create ▸ JarvisVR ▸ Widget Registry*) mapping `gauge` → that prefab. The manager
prefers the prefab over the procedural default.

---

## Step 5 — Have the backend spawn it

In most cases **there's nothing to do** — the backend reads the catalog at startup
([`catalog.py`](../../agent-backend/jarvis_backend/catalog.py)) and
[`widget_tools.py`](../../agent-backend/jarvis_backend/agent/tools/widget_tools.py)
auto-registers a `show_<widget>` spawn tool for **every** catalog widget that isn't
already claimed by a richer tool (the claimed set is `weather_orb`, `timer`,
`panel`). The LLM can then call `show_gauge({...})` and the agent emits a validated
`holo.spawn`.

Point the backend at your edited registry (it defaults to `../holo-tools/registry.json`):

```bash
cd agent-backend && source .venv/bin/activate
JARVIS_HOLO_REGISTRY=../holo-tools/registry.json python -m jarvis_backend
```

If the registry file is **absent**, the backend falls back to a small built-in
catalog in `catalog.py` (and merges any missing built-ins on top of the real
registry), so the stack is never blocked. For your widget to validate against the
*real* schema, make sure `registry.json` is present and on `JARVIS_HOLO_REGISTRY`.

### When you want richer behaviour

For state, side effects, or multi-widget responses, write a real tool that returns
a `SpawnDirective` instead of relying on the generated spawn tool. See the
[Write a tool](./write-a-tool.md) guide. A directive looks like:

```python
from jarvis_backend.agent.tools.base import SpawnDirective, ToolResult

return ToolResult(
    data={"speech": "CPU is at 72 percent."},
    directives=[
        SpawnDirective(
            widget_type="gauge",
            props={"value": 72, "label": "CPU", "unit": "%"},
            ref="gauge:cpu",                 # logical handle for later updates
            interactions=["tap", "grab"],
        )
    ],
)
```

The agent validates `widget_type` + `props` against the catalog
([`Agent._spawn`](../../agent-backend/jarvis_backend/agent/agent.py)) before
emitting `holo.spawn`, assigns the server-side `object_id`, and tracks the `ref` so
later turns/interactions can update or destroy it.

---

## Step 6 — Validate & test

### Validate props in Python

```python
import holo_tools as ht

ht.validate_widget("gauge", {"value": 72, "label": "CPU", "unit": "%"})
# raises UnknownWidgetError (code "unknown_widget") for a bad widget_type
# raises InvalidPropsError (code "invalid_props") for bad/extra props

# Validate a whole holographic object (PROTOCOL.md §5.6):
ht.validate_holo_object({
    "widget_type": "gauge",
    "transform": {"anchor": "head", "position": [0, 0, 1], "rotation": [0, 0, 0, 1], "scale": [1, 1, 1]},
    "props": {"value": 72, "label": "CPU"},
    "interactions": ["tap", "grab"],
})
```

Both raise `HoloValidationError` subclasses on failure; turn either into a
`server.error` payload with `err.to_error_payload()`.

### Run the test suites

```bash
# holo-tools: every props_schema is a valid draft-2020-12 schema, every
# example_props validates, and every tools.json tool maps to a real widget_type.
cd holo-tools && pytest

# agent-backend: spawning + catalog validation (run from its own venv).
cd ../agent-backend && pytest

# infra e2e: drives a real conversation and validates every frame on the wire.
cd ../infra && make e2e
```

If `example_props` doesn't validate against `props_schema`, the holo-tools suite
fails — that's the guardrail that keeps the catalog honest.

---

## Checklist

- [ ] Added the widget object to `holo-tools/registry.json` (`props_schema` closed +
      a valid `example_props`).
- [ ] Regenerated `tools.json` **and** `docs/HOLO_TOOLS.md` from the registry.
- [ ] (Optional) Added a TS interface in `holo-tools/ts/widgets.ts`.
- [ ] Added a `HoloWidget` subclass (+ `WidgetCatalog` entry) **or** a prefab in a
      `WidgetRegistry`.
- [ ] Confirmed the backend exposes `show_<widget>` (or wrote a richer tool).
- [ ] `pytest` passes in `holo-tools/` and `agent-backend/`, and `make -C infra e2e`
      is green.

---

## See also

- [Widget catalog (`docs/HOLO_TOOLS.md`)](../HOLO_TOOLS.md) — every widget's props,
  interactions, and tool schema.
- [Protocol reference (`docs/PROTOCOL.md`) §5.6](../PROTOCOL.md#56-the-holographic-object)
  — the Holographic Object on the wire.
- [holo-tools component deep-dive](../components/holo-tools.md) ·
  [unity-client deep-dive](../components/unity-client.md).
- [Write an agent tool](./write-a-tool.md) — give the widget richer behaviour.
- [`CONTRIBUTING.md` → Adding a hologram widget](../../CONTRIBUTING.md#adding-a-hologram-widget).
