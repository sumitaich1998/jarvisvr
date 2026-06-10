#!/usr/bin/env python3
"""Generate docs/HOLO_TOOLS.md from registry.json + tools.json.

The registry is the single source of truth; this keeps the human-readable catalog
in lock-step with it. Run from anywhere:

    python holo-tools/scripts/generate_docs.py

It writes ../../docs/HOLO_TOOLS.md relative to the repo root.
"""

from __future__ import annotations

import json
from pathlib import Path

import holo_tools as ht

HERE = Path(__file__).resolve()
REPO_ROOT = HERE.parents[2]
OUT_PATH = REPO_ROOT / "docs" / "HOLO_TOOLS.md"

REGISTRY = ht.load_registry()
TOOLS_DOC = ht.load_tools()
WIDGETS = REGISTRY["widgets"]
WIDGETS_BY_TYPE = {w["widget_type"]: w for w in WIDGETS}
TOOLS = TOOLS_DOC["tools"]


def esc(text: str) -> str:
    return str(text).replace("|", "\\|").replace("\n", " ")


def type_str(schema: dict) -> str:
    if "enum" in schema:
        return "enum"
    t = schema.get("type")
    if t == "array":
        items = schema.get("items", {})
        if "enum" in items:
            return "array&lt;enum&gt;"
        it = items.get("type")
        if it == "object":
            return "array&lt;object&gt;"
        if it:
            return f"array&lt;{it}&gt;"
        return "array"
    if isinstance(t, list):
        return " \\| ".join(t)
    return t or "any"


def constraints_str(schema: dict) -> str:
    parts = []
    if "enum" in schema:
        parts.append("one of: " + ", ".join(f"`{v}`" for v in schema["enum"]))
    numeric = [
        ("minimum", "min"),
        ("maximum", "max"),
        ("exclusiveMinimum", "> "),
        ("exclusiveMaximum", "< "),
        ("minLength", "minLen"),
        ("minItems", "minItems"),
        ("maxItems", "maxItems"),
    ]
    for key, label in numeric:
        if key in schema:
            parts.append(f"{label}{'' if label.endswith(' ') else ' '}{schema[key]}".strip())
    if "pattern" in schema:
        parts.append("hex/pattern")
    if "format" in schema:
        parts.append(f"format: {schema['format']}")
    items = schema.get("items", {}) if schema.get("type") == "array" else {}
    if items.get("type") == "object":
        keys = list(items.get("properties", {}))
        req = set(items.get("required", []))
        parts.append("items: {" + ", ".join((k + "*" if k in req else k) for k in keys) + "}")
    elif "enum" in items:
        parts.append("each: " + ", ".join(f"`{v}`" for v in items["enum"]))
    if schema.get("type") == "object" and schema.get("properties"):
        keys = list(schema["properties"])
        req = set(schema.get("required", []))
        parts.append("keys: {" + ", ".join((k + "*" if k in req else k) for k in keys) + "}")
    return esc("; ".join(parts))


def props_table(widget: dict) -> str:
    schema = widget["props_schema"]
    required = set(schema.get("required", []))
    rows = [
        "| Prop | Type | Required | Default | Constraints | Description |",
        "| ---- | ---- | :------: | ------- | ----------- | ----------- |",
    ]
    for name, prop in schema.get("properties", {}).items():
        default = prop.get("default", "")
        default = f"`{json.dumps(default)}`" if default != "" else ""
        rows.append(
            "| `{name}` | {type} | {req} | {default} | {constraints} | {desc} |".format(
                name=name,
                type=type_str(prop),
                req="yes" if name in required else "",
                default=default,
                constraints=constraints_str(prop) or "",
                desc=esc(prop.get("description", "")),
            )
        )
    return "\n".join(rows)


def events_table(widget: dict) -> str:
    if not widget["events"]:
        return "_None._"
    rows = [
        "| Event | Element | Action | Value | Description |",
        "| ----- | ------- | ------ | ----- | ----------- |",
    ]
    for ev in widget["events"]:
        vs = ev.get("value_schema")
        if vs and vs.get("properties"):
            value = "{" + ", ".join(vs["properties"].keys()) + "}"
        else:
            value = ""
        rows.append(
            "| `{name}` | `{element}` | `{action}` | {value} | {desc} |".format(
                name=ev["name"],
                element=ev.get("element", ""),
                action=ev["action"],
                value=esc(value),
                desc=esc(ev.get("description", "")),
            )
        )
    return "\n".join(rows)


def example_spawn(widget: dict) -> dict:
    return {
        "v": REGISTRY["version"],
        "id": "msg-uuid",
        "type": "holo.spawn",
        "ts": 1733397600000,
        "session": "session-uuid",
        "payload": {
            "object_id": "object-uuid",
            "widget_type": widget["widget_type"],
            "transform": widget["default_transform"],
            "props": widget["example_props"],
            "interactable": True,
            "interactions": widget["interactions"],
            "ttl_ms": 0,
        },
    }


def widget_section(widget: dict) -> str:
    wt = widget["widget_type"]
    transform = json.dumps(widget["default_transform"], indent=2)
    example = json.dumps(example_spawn(widget), indent=2)
    return f"""<a id="{wt}"></a>

### `{wt}` — {widget['title']}

{widget['description']}

- **Category:** `{widget['category']}`
- **Prefab id:** `{widget['prefab_id']}`
- **Interactions:** {', '.join(f'`{i}`' for i in widget['interactions'])}

**Props**

{props_table(widget)}

**Events emitted** (sent back as `client.interaction`)

{events_table(widget)}

**Default transform**

```json
{transform}
```

**Example `holo.spawn`**

```json
{example}
```
"""


def perception_section() -> str:
    example = json.dumps(example_spawn(WIDGETS_BY_TYPE["vision_annotation"]), indent=2)
    return f"""## Annotating the real world (v1.1 perception)

PROTOCOL v1.1 gives Jarvis **sight, hearing, and attention** (PROTOCOL.md §8). When the user asks
about their surroundings ("what is this?", "read this sign"), the backend:

1. enables a perception stream with `perception.request` (pull-based, privacy-gated);
2. receives `perception.vision_frame` / `perception.audio_scene` / `perception.gaze`;
3. reasons over the rolling perception buffer and replies with `agent.observation`
   (spoken narration + spatial `annotations`);
4. realizes those annotations as **perception holograms** via `holo.spawn`.

`agent.observation.annotations[]` (`label` / `object_id` / `position` / `anchor`, PROTOCOL.md §8.4)
map directly onto perception widgets:

| Annotation intent | Widget | Notes |
| ----------------- | ------ | ----- |
| Point at / name a real object | `vision_annotation` | world-anchored, billboarded callout with a leader line |
| Outline a detected object | `bounding_box_3d` | volumetric box sized in meters around the object |
| Drop a spatial-memory pin | `scene_label` | e.g. "keys last seen here" |
| Caption what Jarvis hears | `live_caption` | rolling transcript / translation |
| Show what Jarvis sees | `vision_feed` | passthrough preview with detection overlays |

Perception holograms are typically **world-anchored** at the detected `position` (meters) with
`billboard: true` so labels face the user. Example (mirrors PROTOCOL.md §8.6):

```json
{example}
```

These are spawned by the tools `annotate_object`, `draw_bounding_box`, `drop_scene_label`,
`show_live_caption`, and `show_vision_feed`. **Privacy:** capture happens only while a
`perception.*` stream is active; `perception.state` reflects what is currently being captured.
"""


def summary_table() -> str:
    rows = [
        "| `widget_type` | Title | Category | Prefab | Interactions |",
        "| ------------- | ----- | -------- | ------ | ------------ |",
    ]
    for w in WIDGETS:
        rows.append(
            "| [`{wt}`](#{anchor}) | {title} | `{cat}` | `{prefab}` | {inter} |".format(
                wt=w["widget_type"],
                anchor=w["widget_type"],
                title=esc(w["title"]),
                cat=w["category"],
                prefab=w["prefab_id"],
                inter=", ".join(f"`{i}`" for i in w["interactions"]),
            )
        )
    return "\n".join(rows)


def tools_table() -> str:
    rows = [
        "| Tool | Action | Produces | Required params |",
        "| ---- | ------ | -------- | --------------- |",
    ]
    for t in TOOLS:
        produces = t.get("x_widget_type", "—")
        req = ", ".join(f"`{r}`" for r in t["parameters"].get("required", [])) or "—"
        rows.append(
            "| `{name}` | `{action}` | {produces} | {req} |".format(
                name=t["name"],
                action=t.get("x_action", ""),
                produces=f"`{produces}`" if produces != "—" else "—",
                req=req,
            )
        )
    return "\n".join(rows)


HEADER = f"""<!-- GENERATED FILE — do not edit by hand.
     Source of truth: holo-tools/registry.json + holo-tools/tools.json
     Regenerate with: python holo-tools/scripts/generate_docs.py -->

# JarvisVR Holographic Tools & Widget Catalog

> Catalog **version `{REGISTRY['version']}`** · protocol `{REGISTRY['protocol_version']}`

This is the human-readable companion to [`holo-tools/registry.json`](../holo-tools/registry.json)
(the machine-readable single source of truth) and [`holo-tools/tools.json`](../holo-tools/tools.json)
(the agent tool/function schemas). It conforms to [`docs/PROTOCOL.md`](./PROTOCOL.md) §5.6
*The Holographic Object*.

- **`agent-backend/`** uses the catalog to expose tools to the LLM and to **validate**
  `widget_type` + `props` before emitting `holo.spawn` / `holo.update`.
- **`unity-client/`** maps each `widget_type` → the Unity prefab named by `prefab_id`, applies the
  `transform`, hands `props` to the prefab controller, and routes the listed `interactions` back as
  `client.interaction` using the event `element`/`action` ids below.

**v1.1 (Multimodal Perception):** adds 5 **perception widgets** that let Jarvis annotate the real
world (`vision_annotation`, `bounding_box_3d`, `live_caption`, `vision_feed`, `scene_label`) plus a
broad set of feature widgets. See [_Annotating the real world_](#annotating-the-real-world-v11-perception).
"""

CONVENTIONS = """## Conventions

- **Coordinates:** right-handed, meters, Unity convention (Y up). `position = [x, y, z]`,
  `rotation` = quaternion `[x, y, z, w]`, `scale = [x, y, z]`.
- **Anchors:** `world` · `head` · `hand_left` · `hand_right` · `surface`.
- **Interactions:** `tap` · `grab` · `release` · `drag` · `slider` · `toggle` · `resize` · `dwell`.
- **Naming:** `widget_type` and all prop keys are `snake_case`.
- **Props validation:** each widget's `props` are validated strictly against its JSON Schema
  (draft 2020-12, `additionalProperties: false`). The surrounding holo-object envelope is validated
  leniently (unknown keys ignored) per the protocol's forward-compatibility rule.
"""

SUMMONING = """## How the agent summons holograms

The agent never speaks the wire protocol directly — it calls **tools** (see
[`tools.json`](../holo-tools/tools.json)). The backend turns each tool call into a `holo.*`
command and validates it against this catalog before it goes out.

```
1. user speaks            "Jarvis, show me the weather in Tokyo"
2. LLM calls a tool       show_weather({ city: "Tokyo", temp_c: 18, condition: "clouds" })
3. backend validates      validate_widget("weather_orb", props)   # holo-tools
4. backend assigns id     object_id = uuid4()
5. backend → client       holo.spawn { widget_type: "weather_orb", transform, props, ... }
6. client instantiates    Holo_WeatherOrb prefab, applies transform, renders props
7. user interacts ✋       taps the orb
8. client → backend       client.interaction { widget_type: "weather_orb", action: "tap", element: "orb" }
9. backend reacts         maybe show_chart(...) or update_hologram(...)
```

Every message is wrapped in the v1 envelope (`v, id, type, ts, session, payload`); the payload of a
`holo.spawn` is exactly the *Holographic Object* (PROTOCOL.md §5.6). A tool's optional `anchor` /
`position` / `billboard` params override the widget's `default_transform`.

### Utility tools

- **`arrange_holograms`** → `holo.layout`: arrange existing objects (`arc` / `grid` / `stack` / `free`).
- **`close_hologram`** → `holo.destroy`: remove an object (with `fade_ms`).
- **`update_hologram`** → `holo.update`: patch the `props` / `transform` of a live object.

### Validation & error codes

`validate_widget(widget_type, props)` and `validate_holo_object(obj)` raise errors whose `code`
matches the protocol (PROTOCOL.md §5.13):

- **`unknown_widget`** — the `widget_type` is not in this registry.
- **`invalid_props`** — props (or the holo-object structure) failed schema validation.

Convert an error to a `server.error` payload with `err.to_error_payload()`.
"""

ADD_GUIDE = """## How to add a new widget

1. **Add a registry entry** to [`registry.json`](../holo-tools/registry.json) under `widgets[]`:
   - `widget_type` (`snake_case`), `title`, `description`, `category` (one of the catalog
     `categories`).
   - `props_schema` — a JSON Schema (draft 2020-12), `type: object`, `additionalProperties: false`,
     with `required` and `properties` (use `snake_case` keys).
   - `interactions` — a subset of the global interaction set.
   - `default_transform` — `anchor` + `position` + `rotation` (quaternion) + `scale` + `billboard`.
   - `prefab_id` — the Unity prefab name (convention: `Holo_PascalCase`).
   - `events` — interaction events the widget emits, each with `name`, `element`, `action`
     (must be one of the widget's `interactions`), and an optional `value_schema`.
   - `example_props` — a valid example (the test-suite validates it).
2. **Regenerate `tools.json`** (it is derived from the registry):
   `python -c "import json, holo_tools as ht; open('tools.json','w').write(json.dumps(ht.derive_tools(ht.REGISTRY), indent=2, ensure_ascii=False) + '\\n')"`
3. **Add TypeScript types** to [`ts/widgets.ts`](../holo-tools/ts/widgets.ts): a `…Props` interface,
   an entry in `WidgetPropsMap`, `WIDGET_TYPES`, and `PREFAB_IDS`.
4. **Build the Unity prefab** named by `prefab_id` and register it in the client's
   `widget_type → prefab` map.
5. **Run the tests:** `pytest` (validates schema, example, tools, and consistency).
6. **Regenerate this doc:** `python holo-tools/scripts/generate_docs.py`.

> Bump `version` in `registry.json` when you change the catalog (semver).
"""


def main() -> None:
    parts = [
        HEADER,
        CONVENTIONS,
        "## Widget index\n\n" + summary_table() + "\n",
        SUMMONING,
        perception_section(),
        "## Agent tools\n\n"
        + "Group (a) widget tools (`x_action: spawn`) are derived from the registry; group (b) "
        + "utility tools map to `holo.layout` / `holo.destroy` / `holo.update`. The `x_*` keys are "
        + "JarvisVR extensions — strip them before sending to an LLM if your provider rejects "
        + "unknown fields.\n\n"
        + tools_table()
        + "\n",
        "## Widget catalog\n\n" + "\n".join(widget_section(w) for w in WIDGETS),
        f"---\n\n_Generated from `holo-tools/registry.json` ({len(WIDGETS)} widgets) and "
        f"`holo-tools/tools.json` ({len(TOOLS)} tools) by `holo-tools/scripts/generate_docs.py`._\n",
    ]
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text("\n".join(parts), encoding="utf-8")
    print(f"wrote {OUT_PATH} ({OUT_PATH.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
