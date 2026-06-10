<!-- GENERATED FILE — do not edit by hand.
     Source of truth: holo-tools/registry.json + holo-tools/tools.json
     Regenerate with: python holo-tools/scripts/generate_docs.py -->

# JarvisVR Holographic Tools & Widget Catalog

> Catalog **version `1.1.0`** · protocol `1.1.0`

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

## Conventions

- **Coordinates:** right-handed, meters, Unity convention (Y up). `position = [x, y, z]`,
  `rotation` = quaternion `[x, y, z, w]`, `scale = [x, y, z]`.
- **Anchors:** `world` · `head` · `hand_left` · `hand_right` · `surface`.
- **Interactions:** `tap` · `grab` · `release` · `drag` · `slider` · `toggle` · `resize` · `dwell`.
- **Naming:** `widget_type` and all prop keys are `snake_case`.
- **Props validation:** each widget's `props` are validated strictly against its JSON Schema
  (draft 2020-12, `additionalProperties: false`). The surrounding holo-object envelope is validated
  leniently (unknown keys ignored) per the protocol's forward-compatibility rule.

## Widget index

| `widget_type` | Title | Category | Prefab | Interactions |
| ------------- | ----- | -------- | ------ | ------------ |
| [`weather_orb`](#weather_orb) | Weather Orb | `information` | `Holo_WeatherOrb` | `tap`, `grab`, `resize`, `dwell` |
| [`chart_3d`](#chart_3d) | 3D Chart | `data` | `Holo_Chart3D` | `tap`, `grab`, `drag`, `resize`, `dwell` |
| [`model_viewer`](#model_viewer) | 3D Model Viewer | `media` | `Holo_ModelViewer` | `tap`, `grab`, `drag`, `resize`, `dwell` |
| [`panel`](#panel) | Info Panel | `container` | `Holo_Panel` | `tap`, `grab`, `drag`, `resize` |
| [`text_label`](#text_label) | Text Label | `primitive` | `Holo_TextLabel` | `tap`, `grab` |
| [`button`](#button) | Button | `control` | `Holo_Button` | `tap`, `dwell` |
| [`timer`](#timer) | Timer | `utility` | `Holo_Timer` | `tap`, `grab`, `resize` |
| [`media_player`](#media_player) | Media Player | `media` | `Holo_MediaPlayer` | `tap`, `grab`, `resize`, `slider` |
| [`map_3d`](#map_3d) | 3D Map | `data` | `Holo_Map3D` | `tap`, `grab`, `drag`, `resize`, `slider` |
| [`smart_home_panel`](#smart_home_panel) | Smart Home Panel | `control` | `Holo_SmartHomePanel` | `tap`, `grab`, `toggle`, `slider` |
| [`todo_list`](#todo_list) | To-do List | `productivity` | `Holo_TodoList` | `tap`, `grab`, `resize`, `toggle`, `drag` |
| [`image_board`](#image_board) | Image Board | `media` | `Holo_ImageBoard` | `tap`, `grab`, `resize`, `drag`, `dwell` |
| [`vision_annotation`](#vision_annotation) | Vision Annotation | `perception` | `Holo_VisionAnnotation` | `tap`, `grab`, `dwell` |
| [`bounding_box_3d`](#bounding_box_3d) | 3D Bounding Box | `perception` | `Holo_BoundingBox3D` | `tap`, `dwell` |
| [`live_caption`](#live_caption) | Live Captions | `perception` | `Holo_LiveCaption` | `grab`, `tap`, `resize` |
| [`vision_feed`](#vision_feed) | Vision Feed | `perception` | `Holo_VisionFeed` | `grab`, `tap`, `resize`, `toggle` |
| [`scene_label`](#scene_label) | Scene Label | `perception` | `Holo_SceneLabel` | `tap`, `grab` |
| [`clock`](#clock) | Clock | `utility` | `Holo_Clock` | `grab`, `tap`, `resize` |
| [`world_clock`](#world_clock) | World Clock | `utility` | `Holo_WorldClock` | `grab`, `tap`, `resize`, `drag` |
| [`calendar`](#calendar) | Calendar | `productivity` | `Holo_Calendar` | `grab`, `tap`, `resize`, `drag`, `dwell` |
| [`stocks_ticker`](#stocks_ticker) | Stocks Ticker | `data` | `Holo_StocksTicker` | `grab`, `tap`, `resize`, `drag` |
| [`news_feed`](#news_feed) | News Feed | `information` | `Holo_NewsFeed` | `grab`, `tap`, `resize`, `drag`, `dwell` |
| [`translator`](#translator) | Translator | `communication` | `Holo_Translator` | `grab`, `tap`, `resize`, `toggle` |
| [`recipe_card`](#recipe_card) | Recipe Card | `information` | `Holo_RecipeCard` | `grab`, `tap`, `resize`, `drag` |
| [`whiteboard`](#whiteboard) | Whiteboard | `productivity` | `Holo_Whiteboard` | `grab`, `resize`, `drag`, `tap` |
| [`sticky_note`](#sticky_note) | Sticky Note | `productivity` | `Holo_StickyNote` | `grab`, `tap`, `resize`, `drag` |
| [`code_viewer`](#code_viewer) | Code Viewer | `developer` | `Holo_CodeViewer` | `grab`, `tap`, `resize`, `drag` |
| [`document_viewer`](#document_viewer) | Document Viewer | `media` | `Holo_DocumentViewer` | `grab`, `tap`, `resize`, `drag`, `slider` |
| [`web_panel`](#web_panel) | Web Panel | `media` | `Holo_WebPanel` | `grab`, `tap`, `resize`, `drag`, `slider` |
| [`avatar`](#avatar) | Jarvis Avatar | `communication` | `Holo_Avatar` | `grab`, `tap`, `dwell` |
| [`navigation_arrow`](#navigation_arrow) | Navigation Arrow | `navigation` | `Holo_NavigationArrow` | `tap`, `dwell` |
| [`health_ring`](#health_ring) | Health Rings | `health` | `Holo_HealthRing` | `grab`, `tap`, `resize`, `dwell` |
| [`music_visualizer`](#music_visualizer) | Music Visualizer | `media` | `Holo_MusicVisualizer` | `grab`, `tap`, `resize` |
| [`graph_3d`](#graph_3d) | Network Graph | `data` | `Holo_Graph3D` | `grab`, `tap`, `drag`, `resize`, `dwell` |
| [`data_table`](#data_table) | Data Table | `data` | `Holo_DataTable` | `grab`, `tap`, `resize`, `drag`, `slider` |
| [`measuring_tape`](#measuring_tape) | Measuring Tape | `utility` | `Holo_MeasuringTape` | `grab`, `tap`, `drag`, `dwell` |
| [`pomodoro`](#pomodoro) | Pomodoro Timer | `productivity` | `Holo_Pomodoro` | `grab`, `tap`, `resize` |
| [`image_gen_viewer`](#image_gen_viewer) | AI Image Viewer | `media` | `Holo_ImageGenViewer` | `grab`, `tap`, `resize`, `drag`, `dwell` |
| [`volumetric_globe`](#volumetric_globe) | Volumetric Globe | `data` | `Holo_VolumetricGlobe` | `grab`, `tap`, `drag`, `resize`, `dwell` |
| [`system_launcher`](#system_launcher) | System Launcher | `system` | `Holo_SystemLauncher` | `grab`, `tap`, `resize`, `drag`, `dwell` |
| [`notification_toast`](#notification_toast) | Notification Toast | `system` | `Holo_NotificationToast` | `tap`, `dwell` |
| [`settings_panel`](#settings_panel) | Settings Panel | `system` | `Holo_SettingsPanel` | `grab`, `tap`, `resize`, `toggle`, `slider`, `drag` |

## How the agent summons holograms

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

## Annotating the real world (v1.1 perception)

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
{
  "v": "1.1.0",
  "id": "msg-uuid",
  "type": "holo.spawn",
  "ts": 1733397600000,
  "session": "session-uuid",
  "payload": {
    "object_id": "object-uuid",
    "widget_type": "vision_annotation",
    "transform": {
      "anchor": "world",
      "position": [
        0.3,
        0.95,
        0.7
      ],
      "rotation": [
        0.0,
        0.0,
        0.0,
        1.0
      ],
      "scale": [
        1.0,
        1.0,
        1.0
      ],
      "billboard": true
    },
    "props": {
      "label": "coffee mug",
      "confidence": 0.78,
      "detail": "ceramic, ~350 ml",
      "leader_line": true,
      "target_position": [
        0.3,
        0.8,
        0.7
      ],
      "color": "#7FE7FF",
      "icon": "cup"
    },
    "interactable": true,
    "interactions": [
      "tap",
      "grab",
      "dwell"
    ],
    "ttl_ms": 0
  }
}
```

These are spawned by the tools `annotate_object`, `draw_bounding_box`, `drop_scene_label`,
`show_live_caption`, and `show_vision_feed`. **Privacy:** capture happens only while a
`perception.*` stream is active; `perception.state` reflects what is currently being captured.

## Agent tools

Group (a) widget tools (`x_action: spawn`) are derived from the registry; group (b) utility tools map to `holo.layout` / `holo.destroy` / `holo.update`. The `x_*` keys are JarvisVR extensions — strip them before sending to an LLM if your provider rejects unknown fields.

| Tool | Action | Produces | Required params |
| ---- | ------ | -------- | --------------- |
| `show_weather` | `spawn` | `weather_orb` | `city`, `temp_c`, `condition` |
| `show_chart` | `spawn` | `chart_3d` | `chart_type`, `series` |
| `open_model_viewer` | `spawn` | `model_viewer` | `model_url` |
| `show_panel` | `spawn` | `panel` | `title` |
| `show_text` | `spawn` | `text_label` | `text` |
| `show_button` | `spawn` | `button` | `label` |
| `start_timer` | `spawn` | `timer` | `duration_ms`, `remaining_ms`, `state` |
| `play_media` | `spawn` | `media_player` | `source_url`, `media_type` |
| `show_map` | `spawn` | `map_3d` | `center` |
| `show_smart_home` | `spawn` | `smart_home_panel` | `devices` |
| `show_todo_list` | `spawn` | `todo_list` | `items` |
| `show_image_board` | `spawn` | `image_board` | `images` |
| `annotate_object` | `spawn` | `vision_annotation` | `label` |
| `draw_bounding_box` | `spawn` | `bounding_box_3d` | `label`, `size` |
| `show_live_caption` | `spawn` | `live_caption` | `lines` |
| `show_vision_feed` | `spawn` | `vision_feed` | — |
| `drop_scene_label` | `spawn` | `scene_label` | `text` |
| `show_clock` | `spawn` | `clock` | — |
| `show_world_clock` | `spawn` | `world_clock` | `zones` |
| `show_calendar` | `spawn` | `calendar` | `events` |
| `show_stocks` | `spawn` | `stocks_ticker` | `symbols` |
| `show_news` | `spawn` | `news_feed` | `articles` |
| `show_translator` | `spawn` | `translator` | `source_lang`, `target_lang` |
| `show_recipe` | `spawn` | `recipe_card` | `title`, `ingredients`, `steps` |
| `open_whiteboard` | `spawn` | `whiteboard` | — |
| `show_sticky_note` | `spawn` | `sticky_note` | `text` |
| `show_code` | `spawn` | `code_viewer` | `code` |
| `show_document` | `spawn` | `document_viewer` | `url` |
| `show_web` | `spawn` | `web_panel` | `url` |
| `show_avatar` | `spawn` | `avatar` | — |
| `show_navigation` | `spawn` | `navigation_arrow` | `direction` |
| `show_health_ring` | `spawn` | `health_ring` | `rings` |
| `show_music_visualizer` | `spawn` | `music_visualizer` | — |
| `show_graph` | `spawn` | `graph_3d` | `nodes` |
| `show_data_table` | `spawn` | `data_table` | `columns`, `rows` |
| `measure` | `spawn` | `measuring_tape` | `points` |
| `start_pomodoro` | `spawn` | `pomodoro` | `phase`, `remaining_ms` |
| `show_generated_image` | `spawn` | `image_gen_viewer` | `prompt` |
| `show_globe` | `spawn` | `volumetric_globe` | — |
| `show_system_launcher` | `spawn` | `system_launcher` | `apps` |
| `notify` | `spawn` | `notification_toast` | `title` |
| `show_settings` | `spawn` | `settings_panel` | `sections` |
| `arrange_holograms` | `layout` | — | `arrangement`, `object_ids` |
| `close_hologram` | `destroy` | — | `object_id` |
| `update_hologram` | `update` | — | `object_id` |

## Widget catalog

<a id="weather_orb"></a>

### `weather_orb` — Weather Orb

A floating, glanceable orb showing current conditions for a city, with an optional multi-day forecast that expands on tap.

- **Category:** `information`
- **Prefab id:** `Holo_WeatherOrb`
- **Interactions:** `tap`, `grab`, `resize`, `dwell`

**Props**

| Prop | Type | Required | Default | Constraints | Description |
| ---- | ---- | :------: | ------- | ----------- | ----------- |
| `city` | string | yes |  | minLen 1 | City or location name to display. |
| `temp_c` | number | yes |  |  | Current temperature in degrees Celsius. |
| `condition` | enum | yes |  | one of: `clear`, `partly_cloudy`, `clouds`, `rain`, `snow`, `storm`, `fog`, `wind` | Current weather condition. |
| `humidity_pct` | integer |  |  | min 0; max 100 | Relative humidity percentage. |
| `wind_kph` | number |  |  | min 0 | Wind speed in km/h. |
| `unit` | enum |  | `"c"` | one of: `c`, `f` | Display unit for temperatures. |
| `forecast` | array&lt;object&gt; |  |  | items: {day*, high_c*, low_c*, condition*} | Optional multi-day forecast entries. |

**Events emitted** (sent back as `client.interaction`)

| Event | Element | Action | Value | Description |
| ----- | ------- | ------ | ----- | ----------- |
| `expand_forecast` | `orb` | `tap` |  | User tapped the orb to expand or collapse the forecast. |
| `inspect` | `orb` | `dwell` |  | User dwelled (gaze/hover) on the orb to reveal details. |

**Default transform**

```json
{
  "anchor": "head",
  "position": [
    0.45,
    0.1,
    0.9
  ],
  "rotation": [
    0.0,
    0.0,
    0.0,
    1.0
  ],
  "scale": [
    1.0,
    1.0,
    1.0
  ],
  "billboard": true
}
```

**Example `holo.spawn`**

```json
{
  "v": "1.1.0",
  "id": "msg-uuid",
  "type": "holo.spawn",
  "ts": 1733397600000,
  "session": "session-uuid",
  "payload": {
    "object_id": "object-uuid",
    "widget_type": "weather_orb",
    "transform": {
      "anchor": "head",
      "position": [
        0.45,
        0.1,
        0.9
      ],
      "rotation": [
        0.0,
        0.0,
        0.0,
        1.0
      ],
      "scale": [
        1.0,
        1.0,
        1.0
      ],
      "billboard": true
    },
    "props": {
      "city": "Tokyo",
      "temp_c": 18.0,
      "condition": "clouds",
      "humidity_pct": 64,
      "wind_kph": 12.5,
      "unit": "c",
      "forecast": [
        {
          "day": "Mon",
          "high_c": 19.0,
          "low_c": 11.0,
          "condition": "rain"
        },
        {
          "day": "Tue",
          "high_c": 22.0,
          "low_c": 13.0,
          "condition": "partly_cloudy"
        },
        {
          "day": "Wed",
          "high_c": 24.0,
          "low_c": 15.0,
          "condition": "clear"
        }
      ]
    },
    "interactable": true,
    "interactions": [
      "tap",
      "grab",
      "resize",
      "dwell"
    ],
    "ttl_ms": 0
  }
}
```

<a id="chart_3d"></a>

### `chart_3d` — 3D Chart

A volumetric data chart (bar, line, scatter, pie, or surface) with one or more series, axis labels, and selectable data points.

- **Category:** `data`
- **Prefab id:** `Holo_Chart3D`
- **Interactions:** `tap`, `grab`, `drag`, `resize`, `dwell`

**Props**

| Prop | Type | Required | Default | Constraints | Description |
| ---- | ---- | :------: | ------- | ----------- | ----------- |
| `chart_type` | enum | yes |  | one of: `bar`, `line`, `scatter`, `pie`, `surface` | Visual style of the chart. |
| `title` | string |  |  |  | Chart title. |
| `labels` | array&lt;string&gt; |  |  |  | Category labels for the primary axis. |
| `series` | array&lt;object&gt; | yes |  | minItems 1; items: {name*, values*, color} | One or more data series. |
| `x_axis_label` | string |  |  |  |  |
| `y_axis_label` | string |  |  |  |  |
| `z_axis_label` | string |  |  |  |  |
| `show_legend` | boolean |  | `true` |  |  |

**Events emitted** (sent back as `client.interaction`)

| Event | Element | Action | Value | Description |
| ----- | ------- | ------ | ----- | ----------- |
| `select_point` | `data_point` | `tap` | {series_index, point_index} | User tapped a data point/bar. |
| `rotate` | `chart` | `drag` |  | User dragged to rotate the chart. |

**Default transform**

```json
{
  "anchor": "world",
  "position": [
    0.0,
    1.3,
    1.2
  ],
  "rotation": [
    0.0,
    0.0,
    0.0,
    1.0
  ],
  "scale": [
    1.0,
    1.0,
    1.0
  ],
  "billboard": false
}
```

**Example `holo.spawn`**

```json
{
  "v": "1.1.0",
  "id": "msg-uuid",
  "type": "holo.spawn",
  "ts": 1733397600000,
  "session": "session-uuid",
  "payload": {
    "object_id": "object-uuid",
    "widget_type": "chart_3d",
    "transform": {
      "anchor": "world",
      "position": [
        0.0,
        1.3,
        1.2
      ],
      "rotation": [
        0.0,
        0.0,
        0.0,
        1.0
      ],
      "scale": [
        1.0,
        1.0,
        1.0
      ],
      "billboard": false
    },
    "props": {
      "chart_type": "bar",
      "title": "Quarterly Revenue",
      "labels": [
        "Q1",
        "Q2",
        "Q3",
        "Q4"
      ],
      "series": [
        {
          "name": "FY2025",
          "values": [
            12.0,
            18.0,
            9.0,
            22.0
          ],
          "color": "#4FC3F7"
        },
        {
          "name": "FY2026",
          "values": [
            14.0,
            20.0,
            15.0,
            26.0
          ],
          "color": "#FFB74D"
        }
      ],
      "x_axis_label": "Quarter",
      "y_axis_label": "Revenue ($M)",
      "show_legend": true
    },
    "interactable": true,
    "interactions": [
      "tap",
      "grab",
      "drag",
      "resize",
      "dwell"
    ],
    "ttl_ms": 0
  }
}
```

<a id="model_viewer"></a>

### `model_viewer` — 3D Model Viewer

Loads and displays a 3D model (glTF/GLB/OBJ/FBX) that the user can grab, spin, and scale; supports auto-rotate and named animations.

- **Category:** `media`
- **Prefab id:** `Holo_ModelViewer`
- **Interactions:** `tap`, `grab`, `drag`, `resize`, `dwell`

**Props**

| Prop | Type | Required | Default | Constraints | Description |
| ---- | ---- | :------: | ------- | ----------- | ----------- |
| `model_url` | string | yes |  | format: uri | URL of the 3D model asset. |
| `name` | string |  |  |  | Display name / caption for the model. |
| `format` | enum |  | `"glb"` | one of: `glb`, `gltf`, `obj`, `fbx` | Asset format hint for the loader. |
| `auto_rotate` | boolean |  | `false` |  | Continuously spin the model when idle. |
| `animation` | string |  |  |  | Name of an embedded animation clip to play. |
| `scale_factor` | number |  | `1.0` | > 0 | Uniform scale applied to the loaded model. |

**Events emitted** (sent back as `client.interaction`)

| Event | Element | Action | Value | Description |
| ----- | ------- | ------ | ----- | ----------- |
| `rotate` | `model` | `drag` |  | User dragged to rotate the model. |
| `select` | `model` | `tap` |  | User tapped the model. |

**Default transform**

```json
{
  "anchor": "world",
  "position": [
    0.0,
    1.2,
    1.0
  ],
  "rotation": [
    0.0,
    0.0,
    0.0,
    1.0
  ],
  "scale": [
    1.0,
    1.0,
    1.0
  ],
  "billboard": false
}
```

**Example `holo.spawn`**

```json
{
  "v": "1.1.0",
  "id": "msg-uuid",
  "type": "holo.spawn",
  "ts": 1733397600000,
  "session": "session-uuid",
  "payload": {
    "object_id": "object-uuid",
    "widget_type": "model_viewer",
    "transform": {
      "anchor": "world",
      "position": [
        0.0,
        1.2,
        1.0
      ],
      "rotation": [
        0.0,
        0.0,
        0.0,
        1.0
      ],
      "scale": [
        1.0,
        1.0,
        1.0
      ],
      "billboard": false
    },
    "props": {
      "model_url": "https://cdn.jarvisvr.app/models/v8_engine.glb",
      "name": "V8 Engine",
      "format": "glb",
      "auto_rotate": true,
      "animation": "idle_spin",
      "scale_factor": 1.0
    },
    "interactable": true,
    "interactions": [
      "tap",
      "grab",
      "drag",
      "resize",
      "dwell"
    ],
    "ttl_ms": 0
  }
}
```

<a id="panel"></a>

### `panel` — Info Panel

A flat glass/solid panel for rich text content organized into optional sections; the workhorse container for readable information.

- **Category:** `container`
- **Prefab id:** `Holo_Panel`
- **Interactions:** `tap`, `grab`, `drag`, `resize`

**Props**

| Prop | Type | Required | Default | Constraints | Description |
| ---- | ---- | :------: | ------- | ----------- | ----------- |
| `title` | string | yes |  | minLen 1 | Panel heading. |
| `body` | string |  |  |  | Primary body text (plain or lightweight markdown). |
| `sections` | array&lt;object&gt; |  |  | items: {heading*, text*} | Optional list of labelled sub-sections. |
| `width_m` | number |  | `0.6` | > 0 | Panel width in meters. |
| `height_m` | number |  | `0.4` | > 0 | Panel height in meters. |
| `background` | enum |  | `"glass"` | one of: `glass`, `solid`, `none` | Panel background style. |
| `scrollable` | boolean |  | `true` |  |  |

**Events emitted** (sent back as `client.interaction`)

| Event | Element | Action | Value | Description |
| ----- | ------- | ------ | ----- | ----------- |
| `select_section` | `section` | `tap` | {index} | User tapped a section. |

**Default transform**

```json
{
  "anchor": "world",
  "position": [
    0.0,
    1.4,
    1.1
  ],
  "rotation": [
    0.0,
    0.0,
    0.0,
    1.0
  ],
  "scale": [
    1.0,
    1.0,
    1.0
  ],
  "billboard": false
}
```

**Example `holo.spawn`**

```json
{
  "v": "1.1.0",
  "id": "msg-uuid",
  "type": "holo.spawn",
  "ts": 1733397600000,
  "session": "session-uuid",
  "payload": {
    "object_id": "object-uuid",
    "widget_type": "panel",
    "transform": {
      "anchor": "world",
      "position": [
        0.0,
        1.4,
        1.1
      ],
      "rotation": [
        0.0,
        0.0,
        0.0,
        1.0
      ],
      "scale": [
        1.0,
        1.0,
        1.0
      ],
      "billboard": false
    },
    "props": {
      "title": "Mission Briefing",
      "body": "Three objectives are outstanding for today's flight test.",
      "sections": [
        {
          "heading": "Objectives",
          "text": "Calibrate thrusters; verify telemetry uplink; run pre-flight checklist."
        },
        {
          "heading": "Weather",
          "text": "Clear skies, light wind from the west."
        }
      ],
      "width_m": 0.7,
      "height_m": 0.5,
      "background": "glass",
      "scrollable": true
    },
    "interactable": true,
    "interactions": [
      "tap",
      "grab",
      "drag",
      "resize"
    ],
    "ttl_ms": 0
  }
}
```

<a id="text_label"></a>

### `text_label` — Text Label

A lightweight floating text primitive for captions, headings, and annotations anchored in space.

- **Category:** `primitive`
- **Prefab id:** `Holo_TextLabel`
- **Interactions:** `tap`, `grab`

**Props**

| Prop | Type | Required | Default | Constraints | Description |
| ---- | ---- | :------: | ------- | ----------- | ----------- |
| `text` | string | yes |  | minLen 1 | Text to display. |
| `font_size_m` | number |  | `0.05` | > 0 | Cap height in meters. |
| `color` | string |  | `"#FFFFFF"` | hex/pattern | Hex text color. |
| `align` | enum |  | `"center"` | one of: `left`, `center`, `right` |  |
| `weight` | enum |  | `"regular"` | one of: `regular`, `bold` |  |

**Events emitted** (sent back as `client.interaction`)

| Event | Element | Action | Value | Description |
| ----- | ------- | ------ | ----- | ----------- |
| `select` | `label` | `tap` |  | User tapped the label. |

**Default transform**

```json
{
  "anchor": "head",
  "position": [
    0.0,
    0.2,
    1.0
  ],
  "rotation": [
    0.0,
    0.0,
    0.0,
    1.0
  ],
  "scale": [
    1.0,
    1.0,
    1.0
  ],
  "billboard": true
}
```

**Example `holo.spawn`**

```json
{
  "v": "1.1.0",
  "id": "msg-uuid",
  "type": "holo.spawn",
  "ts": 1733397600000,
  "session": "session-uuid",
  "payload": {
    "object_id": "object-uuid",
    "widget_type": "text_label",
    "transform": {
      "anchor": "head",
      "position": [
        0.0,
        0.2,
        1.0
      ],
      "rotation": [
        0.0,
        0.0,
        0.0,
        1.0
      ],
      "scale": [
        1.0,
        1.0,
        1.0
      ],
      "billboard": true
    },
    "props": {
      "text": "Welcome back, sir.",
      "font_size_m": 0.06,
      "color": "#7FE7FF",
      "align": "center",
      "weight": "bold"
    },
    "interactable": true,
    "interactions": [
      "tap",
      "grab"
    ],
    "ttl_ms": 0
  }
}
```

<a id="button"></a>

### `button` — Button

A pressable holographic button that emits an event on tap or dwell; used for confirmations and quick actions.

- **Category:** `control`
- **Prefab id:** `Holo_Button`
- **Interactions:** `tap`, `dwell`

**Props**

| Prop | Type | Required | Default | Constraints | Description |
| ---- | ---- | :------: | ------- | ----------- | ----------- |
| `label` | string | yes |  | minLen 1 | Button caption. |
| `icon` | string |  |  |  | Optional icon id from the client icon set. |
| `style` | enum |  | `"primary"` | one of: `primary`, `secondary`, `danger`, `ghost` |  |
| `action_id` | string |  |  |  | Semantic id echoed back in the press event so the agent knows what was invoked. |
| `enabled` | boolean |  | `true` |  |  |

**Events emitted** (sent back as `client.interaction`)

| Event | Element | Action | Value | Description |
| ----- | ------- | ------ | ----- | ----------- |
| `press` | `button` | `tap` | {action_id} | User pressed the button. |
| `dwell_select` | `button` | `dwell` | {action_id} | User selected the button via dwell. |

**Default transform**

```json
{
  "anchor": "head",
  "position": [
    0.0,
    -0.1,
    0.8
  ],
  "rotation": [
    0.0,
    0.0,
    0.0,
    1.0
  ],
  "scale": [
    1.0,
    1.0,
    1.0
  ],
  "billboard": true
}
```

**Example `holo.spawn`**

```json
{
  "v": "1.1.0",
  "id": "msg-uuid",
  "type": "holo.spawn",
  "ts": 1733397600000,
  "session": "session-uuid",
  "payload": {
    "object_id": "object-uuid",
    "widget_type": "button",
    "transform": {
      "anchor": "head",
      "position": [
        0.0,
        -0.1,
        0.8
      ],
      "rotation": [
        0.0,
        0.0,
        0.0,
        1.0
      ],
      "scale": [
        1.0,
        1.0,
        1.0
      ],
      "billboard": true
    },
    "props": {
      "label": "Confirm",
      "icon": "check",
      "style": "primary",
      "action_id": "confirm_order",
      "enabled": true
    },
    "interactable": true,
    "interactions": [
      "tap",
      "dwell"
    ],
    "ttl_ms": 0
  }
}
```

<a id="timer"></a>

### `timer` — Timer

A countdown or stopwatch with play/pause/reset controls; emits control events the agent reacts to.

- **Category:** `utility`
- **Prefab id:** `Holo_Timer`
- **Interactions:** `tap`, `grab`, `resize`

**Props**

| Prop | Type | Required | Default | Constraints | Description |
| ---- | ---- | :------: | ------- | ----------- | ----------- |
| `label` | string |  |  |  | Optional timer label, e.g. 'Tea'. |
| `duration_ms` | integer | yes |  | min 0 | Total configured duration in milliseconds. |
| `remaining_ms` | integer | yes |  | min 0 | Remaining time in milliseconds. |
| `state` | enum | yes |  | one of: `idle`, `running`, `paused`, `completed` | Current timer state. |
| `mode` | enum |  | `"countdown"` | one of: `countdown`, `stopwatch` |  |

**Events emitted** (sent back as `client.interaction`)

| Event | Element | Action | Value | Description |
| ----- | ------- | ------ | ----- | ----------- |
| `pause` | `pause_button` | `tap` |  | User paused the timer. |
| `resume` | `resume_button` | `tap` |  | User resumed the timer. |
| `reset` | `reset_button` | `tap` |  | User reset the timer. |
| `dismiss` | `close_button` | `tap` |  | User dismissed the timer. |

**Default transform**

```json
{
  "anchor": "head",
  "position": [
    -0.45,
    0.1,
    0.9
  ],
  "rotation": [
    0.0,
    0.0,
    0.0,
    1.0
  ],
  "scale": [
    1.0,
    1.0,
    1.0
  ],
  "billboard": true
}
```

**Example `holo.spawn`**

```json
{
  "v": "1.1.0",
  "id": "msg-uuid",
  "type": "holo.spawn",
  "ts": 1733397600000,
  "session": "session-uuid",
  "payload": {
    "object_id": "object-uuid",
    "widget_type": "timer",
    "transform": {
      "anchor": "head",
      "position": [
        -0.45,
        0.1,
        0.9
      ],
      "rotation": [
        0.0,
        0.0,
        0.0,
        1.0
      ],
      "scale": [
        1.0,
        1.0,
        1.0
      ],
      "billboard": true
    },
    "props": {
      "label": "Tea",
      "duration_ms": 300000,
      "remaining_ms": 142000,
      "state": "running",
      "mode": "countdown"
    },
    "interactable": true,
    "interactions": [
      "tap",
      "grab",
      "resize"
    ],
    "ttl_ms": 0
  }
}
```

<a id="media_player"></a>

### `media_player` — Media Player

Plays an audio or video source with transport controls and a scrubber; emits play/pause, seek, and volume events.

- **Category:** `media`
- **Prefab id:** `Holo_MediaPlayer`
- **Interactions:** `tap`, `grab`, `resize`, `slider`

**Props**

| Prop | Type | Required | Default | Constraints | Description |
| ---- | ---- | :------: | ------- | ----------- | ----------- |
| `title` | string |  |  |  | Title of the media. |
| `source_url` | string | yes |  | format: uri | URL of the audio/video source. |
| `media_type` | enum | yes |  | one of: `audio`, `video` | Kind of media. |
| `poster_url` | string |  |  | format: uri | Optional poster/thumbnail image URL. |
| `state` | enum |  | `"playing"` | one of: `playing`, `paused`, `stopped`, `buffering` |  |
| `position_ms` | integer |  | `0` | min 0 | Current playhead position in milliseconds. |
| `duration_ms` | integer |  |  | min 0 | Total media duration in milliseconds. |
| `volume` | number |  | `0.8` | min 0; max 1 |  |
| `loop` | boolean |  | `false` |  |  |

**Events emitted** (sent back as `client.interaction`)

| Event | Element | Action | Value | Description |
| ----- | ------- | ------ | ----- | ----------- |
| `play_pause` | `play_pause_button` | `tap` |  | User toggled play/pause. |
| `seek` | `scrubber` | `slider` | {position_ms} | User scrubbed the playhead. |
| `set_volume` | `volume_slider` | `slider` | {volume} | User changed the volume. |
| `stop` | `stop_button` | `tap` |  | User stopped playback. |

**Default transform**

```json
{
  "anchor": "world",
  "position": [
    0.0,
    1.3,
    1.2
  ],
  "rotation": [
    0.0,
    0.0,
    0.0,
    1.0
  ],
  "scale": [
    1.0,
    1.0,
    1.0
  ],
  "billboard": true
}
```

**Example `holo.spawn`**

```json
{
  "v": "1.1.0",
  "id": "msg-uuid",
  "type": "holo.spawn",
  "ts": 1733397600000,
  "session": "session-uuid",
  "payload": {
    "object_id": "object-uuid",
    "widget_type": "media_player",
    "transform": {
      "anchor": "world",
      "position": [
        0.0,
        1.3,
        1.2
      ],
      "rotation": [
        0.0,
        0.0,
        0.0,
        1.0
      ],
      "scale": [
        1.0,
        1.0,
        1.0
      ],
      "billboard": true
    },
    "props": {
      "title": "Lo-fi Beats",
      "source_url": "https://cdn.jarvisvr.app/audio/lofi.mp3",
      "media_type": "audio",
      "state": "playing",
      "position_ms": 35000,
      "duration_ms": 180000,
      "volume": 0.6,
      "loop": true
    },
    "interactable": true,
    "interactions": [
      "tap",
      "grab",
      "resize",
      "slider"
    ],
    "ttl_ms": 0
  }
}
```

<a id="map_3d"></a>

### `map_3d` — 3D Map

An interactive tilted 3D map centered on a coordinate, with markers, zoom, and pan; emits marker selection and navigation events.

- **Category:** `data`
- **Prefab id:** `Holo_Map3D`
- **Interactions:** `tap`, `grab`, `drag`, `resize`, `slider`

**Props**

| Prop | Type | Required | Default | Constraints | Description |
| ---- | ---- | :------: | ------- | ----------- | ----------- |
| `center` | object | yes |  | keys: {lat*, lon*} |  |
| `zoom` | number |  | `12` | min 0; max 22 |  |
| `style` | enum |  | `"streets"` | one of: `streets`, `satellite`, `terrain`, `dark` |  |
| `pitch_deg` | number |  | `45` | min 0; max 85 |  |
| `markers` | array&lt;object&gt; |  |  | items: {lat*, lon*, label, color} |  |

**Events emitted** (sent back as `client.interaction`)

| Event | Element | Action | Value | Description |
| ----- | ------- | ------ | ----- | ----------- |
| `select_marker` | `marker` | `tap` | {index} | User tapped a marker. |
| `pan` | `map` | `drag` |  | User panned the map. |
| `zoom` | `zoom_slider` | `slider` | {zoom} | User changed zoom level. |

**Default transform**

```json
{
  "anchor": "surface",
  "position": [
    0.0,
    0.05,
    0.0
  ],
  "rotation": [
    0.0,
    0.0,
    0.0,
    1.0
  ],
  "scale": [
    1.0,
    1.0,
    1.0
  ],
  "billboard": false
}
```

**Example `holo.spawn`**

```json
{
  "v": "1.1.0",
  "id": "msg-uuid",
  "type": "holo.spawn",
  "ts": 1733397600000,
  "session": "session-uuid",
  "payload": {
    "object_id": "object-uuid",
    "widget_type": "map_3d",
    "transform": {
      "anchor": "surface",
      "position": [
        0.0,
        0.05,
        0.0
      ],
      "rotation": [
        0.0,
        0.0,
        0.0,
        1.0
      ],
      "scale": [
        1.0,
        1.0,
        1.0
      ],
      "billboard": false
    },
    "props": {
      "center": {
        "lat": 35.6762,
        "lon": 139.6503
      },
      "zoom": 11,
      "style": "satellite",
      "pitch_deg": 50,
      "markers": [
        {
          "lat": 35.6586,
          "lon": 139.7454,
          "label": "Tokyo Tower",
          "color": "#FF5252"
        }
      ]
    },
    "interactable": true,
    "interactions": [
      "tap",
      "grab",
      "drag",
      "resize",
      "slider"
    ],
    "ttl_ms": 0
  }
}
```

<a id="smart_home_panel"></a>

### `smart_home_panel` — Smart Home Panel

Controls a group of smart-home devices (lights, thermostat, locks, plugs, etc.) with toggles and sliders; emits device control events.

- **Category:** `control`
- **Prefab id:** `Holo_SmartHomePanel`
- **Interactions:** `tap`, `grab`, `toggle`, `slider`

**Props**

| Prop | Type | Required | Default | Constraints | Description |
| ---- | ---- | :------: | ------- | ----------- | ----------- |
| `room` | string |  |  |  | Optional room/group name. |
| `devices` | array&lt;object&gt; | yes |  | minItems 1; items: {id*, name*, type*, state*, unit} | Devices shown and controllable in this panel. |

**Events emitted** (sent back as `client.interaction`)

| Event | Element | Action | Value | Description |
| ----- | ------- | ------ | ----- | ----------- |
| `toggle_device` | `device_toggle` | `toggle` | {device_id, on} | User toggled a device on/off. |
| `set_level` | `device_slider` | `slider` | {device_id, level} | User set a device level (brightness, temperature, volume). |
| `select_device` | `device_row` | `tap` | {device_id} | User selected a device row. |

**Default transform**

```json
{
  "anchor": "world",
  "position": [
    0.6,
    1.3,
    1.0
  ],
  "rotation": [
    0.0,
    0.0,
    0.0,
    1.0
  ],
  "scale": [
    1.0,
    1.0,
    1.0
  ],
  "billboard": true
}
```

**Example `holo.spawn`**

```json
{
  "v": "1.1.0",
  "id": "msg-uuid",
  "type": "holo.spawn",
  "ts": 1733397600000,
  "session": "session-uuid",
  "payload": {
    "object_id": "object-uuid",
    "widget_type": "smart_home_panel",
    "transform": {
      "anchor": "world",
      "position": [
        0.6,
        1.3,
        1.0
      ],
      "rotation": [
        0.0,
        0.0,
        0.0,
        1.0
      ],
      "scale": [
        1.0,
        1.0,
        1.0
      ],
      "billboard": true
    },
    "props": {
      "room": "Living Room",
      "devices": [
        {
          "id": "light_1",
          "name": "Ceiling Light",
          "type": "light",
          "state": {
            "on": true,
            "level": 80
          }
        },
        {
          "id": "thermo_1",
          "name": "Thermostat",
          "type": "thermostat",
          "state": {
            "on": true,
            "temperature_c": 21.5
          },
          "unit": "C"
        },
        {
          "id": "lock_1",
          "name": "Front Door",
          "type": "lock",
          "state": {
            "locked": true
          }
        }
      ]
    },
    "interactable": true,
    "interactions": [
      "tap",
      "grab",
      "toggle",
      "slider"
    ],
    "ttl_ms": 0
  }
}
```

<a id="todo_list"></a>

### `todo_list` — To-do List

A checkable list of tasks with optional priorities; emits toggle and selection events as the user checks items off.

- **Category:** `productivity`
- **Prefab id:** `Holo_TodoList`
- **Interactions:** `tap`, `grab`, `resize`, `toggle`, `drag`

**Props**

| Prop | Type | Required | Default | Constraints | Description |
| ---- | ---- | :------: | ------- | ----------- | ----------- |
| `title` | string |  |  |  | List heading. |
| `items` | array&lt;object&gt; | yes |  | items: {id*, text*, done, priority} | Task items. |

**Events emitted** (sent back as `client.interaction`)

| Event | Element | Action | Value | Description |
| ----- | ------- | ------ | ----- | ----------- |
| `toggle_item` | `item_checkbox` | `toggle` | {item_id, done} | User checked/unchecked an item. |
| `select_item` | `item_row` | `tap` | {item_id} | User selected an item row. |

**Default transform**

```json
{
  "anchor": "world",
  "position": [
    -0.6,
    1.3,
    1.0
  ],
  "rotation": [
    0.0,
    0.0,
    0.0,
    1.0
  ],
  "scale": [
    1.0,
    1.0,
    1.0
  ],
  "billboard": true
}
```

**Example `holo.spawn`**

```json
{
  "v": "1.1.0",
  "id": "msg-uuid",
  "type": "holo.spawn",
  "ts": 1733397600000,
  "session": "session-uuid",
  "payload": {
    "object_id": "object-uuid",
    "widget_type": "todo_list",
    "transform": {
      "anchor": "world",
      "position": [
        -0.6,
        1.3,
        1.0
      ],
      "rotation": [
        0.0,
        0.0,
        0.0,
        1.0
      ],
      "scale": [
        1.0,
        1.0,
        1.0
      ],
      "billboard": true
    },
    "props": {
      "title": "Today",
      "items": [
        {
          "id": "t1",
          "text": "Review PR #42",
          "done": false,
          "priority": "high"
        },
        {
          "id": "t2",
          "text": "Stretch break",
          "done": true,
          "priority": "low"
        },
        {
          "id": "t3",
          "text": "Prep flight test",
          "done": false,
          "priority": "medium"
        }
      ]
    },
    "interactable": true,
    "interactions": [
      "tap",
      "grab",
      "resize",
      "toggle",
      "drag"
    ],
    "ttl_ms": 0
  }
}
```

<a id="image_board"></a>

### `image_board` — Image Board

A grid, carousel, or stack of images with captions; emits selection/navigation events as the user browses.

- **Category:** `media`
- **Prefab id:** `Holo_ImageBoard`
- **Interactions:** `tap`, `grab`, `resize`, `drag`, `dwell`

**Props**

| Prop | Type | Required | Default | Constraints | Description |
| ---- | ---- | :------: | ------- | ----------- | ----------- |
| `title` | string |  |  |  |  |
| `images` | array&lt;object&gt; | yes |  | minItems 1; items: {url*, caption, alt} |  |
| `layout` | enum |  | `"grid"` | one of: `grid`, `carousel`, `stack` |  |
| `columns` | integer |  | `3` | min 1; max 6 |  |

**Events emitted** (sent back as `client.interaction`)

| Event | Element | Action | Value | Description |
| ----- | ------- | ------ | ----- | ----------- |
| `select_image` | `image_tile` | `tap` | {index} | User tapped an image tile. |
| `next` | `next_button` | `tap` |  | User advanced the carousel. |
| `prev` | `prev_button` | `tap` |  | User went back in the carousel. |

**Default transform**

```json
{
  "anchor": "world",
  "position": [
    0.0,
    1.4,
    1.2
  ],
  "rotation": [
    0.0,
    0.0,
    0.0,
    1.0
  ],
  "scale": [
    1.0,
    1.0,
    1.0
  ],
  "billboard": false
}
```

**Example `holo.spawn`**

```json
{
  "v": "1.1.0",
  "id": "msg-uuid",
  "type": "holo.spawn",
  "ts": 1733397600000,
  "session": "session-uuid",
  "payload": {
    "object_id": "object-uuid",
    "widget_type": "image_board",
    "transform": {
      "anchor": "world",
      "position": [
        0.0,
        1.4,
        1.2
      ],
      "rotation": [
        0.0,
        0.0,
        0.0,
        1.0
      ],
      "scale": [
        1.0,
        1.0,
        1.0
      ],
      "billboard": false
    },
    "props": {
      "title": "Mars Rover",
      "images": [
        {
          "url": "https://cdn.jarvisvr.app/img/mars1.jpg",
          "caption": "Sol 1000",
          "alt": "Martian landscape"
        },
        {
          "url": "https://cdn.jarvisvr.app/img/mars2.jpg",
          "caption": "Dust devil",
          "alt": "Dust devil on Mars"
        }
      ],
      "layout": "grid",
      "columns": 3
    },
    "interactable": true,
    "interactions": [
      "tap",
      "grab",
      "resize",
      "drag",
      "dwell"
    ],
    "ttl_ms": 0
  }
}
```

<a id="vision_annotation"></a>

### `vision_annotation` — Vision Annotation

A world-anchored callout that labels a real object Jarvis recognizes, with optional confidence, detail text, and a leader line to the target.

- **Category:** `perception`
- **Prefab id:** `Holo_VisionAnnotation`
- **Interactions:** `tap`, `grab`, `dwell`

**Props**

| Prop | Type | Required | Default | Constraints | Description |
| ---- | ---- | :------: | ------- | ----------- | ----------- |
| `label` | string | yes |  | minLen 1 | Name of the recognized object. |
| `confidence` | number |  |  | min 0; max 1 | Confidence 0.0-1.0. |
| `detail` | string |  |  |  | Optional extra description (material, size, etc.). |
| `leader_line` | boolean |  | `true` |  | Draw a line from the callout to the target. |
| `target_object_id` | string |  |  |  | Object/anchor id of the real object being annotated. |
| `target_position` | array&lt;number&gt; |  |  | minItems 3; maxItems 3 | World position of the target point (meters). |
| `color` | string |  |  | hex/pattern | Hex color (#RRGGBB or #RRGGBBAA). |
| `icon` | string |  |  |  |  |

**Events emitted** (sent back as `client.interaction`)

| Event | Element | Action | Value | Description |
| ----- | ------- | ------ | ----- | ----------- |
| `select` | `annotation` | `tap` | {label} | User tapped the annotation. |
| `inspect` | `annotation` | `dwell` |  | User dwelled to reveal more detail. |

**Default transform**

```json
{
  "anchor": "world",
  "position": [
    0.3,
    0.95,
    0.7
  ],
  "rotation": [
    0.0,
    0.0,
    0.0,
    1.0
  ],
  "scale": [
    1.0,
    1.0,
    1.0
  ],
  "billboard": true
}
```

**Example `holo.spawn`**

```json
{
  "v": "1.1.0",
  "id": "msg-uuid",
  "type": "holo.spawn",
  "ts": 1733397600000,
  "session": "session-uuid",
  "payload": {
    "object_id": "object-uuid",
    "widget_type": "vision_annotation",
    "transform": {
      "anchor": "world",
      "position": [
        0.3,
        0.95,
        0.7
      ],
      "rotation": [
        0.0,
        0.0,
        0.0,
        1.0
      ],
      "scale": [
        1.0,
        1.0,
        1.0
      ],
      "billboard": true
    },
    "props": {
      "label": "coffee mug",
      "confidence": 0.78,
      "detail": "ceramic, ~350 ml",
      "leader_line": true,
      "target_position": [
        0.3,
        0.8,
        0.7
      ],
      "color": "#7FE7FF",
      "icon": "cup"
    },
    "interactable": true,
    "interactions": [
      "tap",
      "grab",
      "dwell"
    ],
    "ttl_ms": 0
  }
}
```

<a id="bounding_box_3d"></a>

### `bounding_box_3d` — 3D Bounding Box

A volumetric box drawn around a detected real-world object, with a label and confidence.

- **Category:** `perception`
- **Prefab id:** `Holo_BoundingBox3D`
- **Interactions:** `tap`, `dwell`

**Props**

| Prop | Type | Required | Default | Constraints | Description |
| ---- | ---- | :------: | ------- | ----------- | ----------- |
| `label` | string | yes |  | minLen 1 |  |
| `confidence` | number |  |  | min 0; max 1 | Confidence 0.0-1.0. |
| `size` | array&lt;number&gt; | yes |  | minItems 3; maxItems 3 | Box extents [width, height, depth] in meters. |
| `color` | string |  |  | hex/pattern | Hex color (#RRGGBB or #RRGGBBAA). |
| `filled` | boolean |  | `false` |  | Render translucent faces instead of just edges. |
| `target_object_id` | string |  |  |  |  |

**Events emitted** (sent back as `client.interaction`)

| Event | Element | Action | Value | Description |
| ----- | ------- | ------ | ----- | ----------- |
| `select` | `box` | `tap` | {label} | User tapped the bounding box. |

**Default transform**

```json
{
  "anchor": "world",
  "position": [
    0.0,
    0.85,
    0.7
  ],
  "rotation": [
    0.0,
    0.0,
    0.0,
    1.0
  ],
  "scale": [
    1.0,
    1.0,
    1.0
  ],
  "billboard": false
}
```

**Example `holo.spawn`**

```json
{
  "v": "1.1.0",
  "id": "msg-uuid",
  "type": "holo.spawn",
  "ts": 1733397600000,
  "session": "session-uuid",
  "payload": {
    "object_id": "object-uuid",
    "widget_type": "bounding_box_3d",
    "transform": {
      "anchor": "world",
      "position": [
        0.0,
        0.85,
        0.7
      ],
      "rotation": [
        0.0,
        0.0,
        0.0,
        1.0
      ],
      "scale": [
        1.0,
        1.0,
        1.0
      ],
      "billboard": false
    },
    "props": {
      "label": "laptop",
      "confidence": 0.91,
      "size": [
        0.33,
        0.02,
        0.23
      ],
      "color": "#FFB74D",
      "filled": false
    },
    "interactable": true,
    "interactions": [
      "tap",
      "dwell"
    ],
    "ttl_ms": 0
  }
}
```

<a id="live_caption"></a>

### `live_caption` — Live Captions

A rolling caption panel that displays speech Jarvis hears in real time (ambient transcript / translation).

- **Category:** `perception`
- **Prefab id:** `Holo_LiveCaption`
- **Interactions:** `grab`, `tap`, `resize`

**Props**

| Prop | Type | Required | Default | Constraints | Description |
| ---- | ---- | :------: | ------- | ----------- | ----------- |
| `lines` | array&lt;string&gt; | yes |  |  | Caption lines, newest last. |
| `speaker` | enum |  | `"other"` | one of: `user`, `other`, `jarvis`, `unknown` | Who is currently speaking (PROTOCOL.md §8.4). |
| `max_lines` | integer |  | `3` | min 1; max 10 | How many lines to keep visible. |
| `language` | string |  |  |  | BCP-47 language tag of the captions. |
| `translated` | boolean |  | `false` |  | True if these captions are a translation. |

**Events emitted** (sent back as `client.interaction`)

| Event | Element | Action | Value | Description |
| ----- | ------- | ------ | ----- | ----------- |
| `toggle_autoscroll` | `caption` | `tap` |  | User toggled caption auto-scroll/pin. |

**Default transform**

```json
{
  "anchor": "head",
  "position": [
    0.0,
    -0.35,
    1.0
  ],
  "rotation": [
    0.0,
    0.0,
    0.0,
    1.0
  ],
  "scale": [
    1.0,
    1.0,
    1.0
  ],
  "billboard": true
}
```

**Example `holo.spawn`**

```json
{
  "v": "1.1.0",
  "id": "msg-uuid",
  "type": "holo.spawn",
  "ts": 1733397600000,
  "session": "session-uuid",
  "payload": {
    "object_id": "object-uuid",
    "widget_type": "live_caption",
    "transform": {
      "anchor": "head",
      "position": [
        0.0,
        -0.35,
        1.0
      ],
      "rotation": [
        0.0,
        0.0,
        0.0,
        1.0
      ],
      "scale": [
        1.0,
        1.0,
        1.0
      ],
      "billboard": true
    },
    "props": {
      "lines": [
        "Hello there.",
        "How can I help you today?"
      ],
      "speaker": "other",
      "max_lines": 3,
      "language": "en",
      "translated": false
    },
    "interactable": true,
    "interactions": [
      "grab",
      "tap",
      "resize"
    ],
    "ttl_ms": 0
  }
}
```

<a id="vision_feed"></a>

### `vision_feed` — Vision Feed

A small panel showing what Jarvis currently sees through the passthrough camera, with detection overlays and a freeze control.

- **Category:** `perception`
- **Prefab id:** `Holo_VisionFeed`
- **Interactions:** `grab`, `tap`, `resize`, `toggle`

**Props**

| Prop | Type | Required | Default | Constraints | Description |
| ---- | ---- | :------: | ------- | ----------- | ----------- |
| `title` | string |  | `"What Jarvis sees"` |  |  |
| `source` | enum |  | `"rgb_center"` | one of: `rgb_center`, `rgb_left`, `rgb_right` | Passthrough camera (PROTOCOL.md §8.4). |
| `frozen` | boolean |  | `false` |  | Freeze the currently displayed frame. |
| `fps` | number |  |  | min 0 | Current feed frame rate. |
| `frame_url` | string |  |  | format: uri | URL/data-uri of the latest frame snapshot. |
| `show_detections` | boolean |  | `true` |  | Overlay detected-object boxes. |

**Events emitted** (sent back as `client.interaction`)

| Event | Element | Action | Value | Description |
| ----- | ------- | ------ | ----- | ----------- |
| `freeze` | `freeze_toggle` | `toggle` | {frozen} | User froze/unfroze the feed. |
| `snapshot` | `feed` | `tap` |  | User captured a snapshot. |

**Default transform**

```json
{
  "anchor": "head",
  "position": [
    0.5,
    0.0,
    0.9
  ],
  "rotation": [
    0.0,
    0.0,
    0.0,
    1.0
  ],
  "scale": [
    1.0,
    1.0,
    1.0
  ],
  "billboard": true
}
```

**Example `holo.spawn`**

```json
{
  "v": "1.1.0",
  "id": "msg-uuid",
  "type": "holo.spawn",
  "ts": 1733397600000,
  "session": "session-uuid",
  "payload": {
    "object_id": "object-uuid",
    "widget_type": "vision_feed",
    "transform": {
      "anchor": "head",
      "position": [
        0.5,
        0.0,
        0.9
      ],
      "rotation": [
        0.0,
        0.0,
        0.0,
        1.0
      ],
      "scale": [
        1.0,
        1.0,
        1.0
      ],
      "billboard": true
    },
    "props": {
      "title": "What Jarvis sees",
      "source": "rgb_center",
      "frozen": false,
      "fps": 2.0,
      "show_detections": true
    },
    "interactable": true,
    "interactions": [
      "grab",
      "tap",
      "resize",
      "toggle"
    ],
    "ttl_ms": 0
  }
}
```

<a id="scene_label"></a>

### `scene_label` — Scene Label

A lightweight pin/label dropped at a point in the room (e.g. spatial-memory markers like 'keys last seen here').

- **Category:** `perception`
- **Prefab id:** `Holo_SceneLabel`
- **Interactions:** `tap`, `grab`

**Props**

| Prop | Type | Required | Default | Constraints | Description |
| ---- | ---- | :------: | ------- | ----------- | ----------- |
| `text` | string | yes |  | minLen 1 |  |
| `icon` | string |  |  |  |  |
| `color` | string |  |  | hex/pattern | Hex color (#RRGGBB or #RRGGBBAA). |
| `pin` | boolean |  | `true` |  | Show a pin/dot anchor under the label. |

**Events emitted** (sent back as `client.interaction`)

| Event | Element | Action | Value | Description |
| ----- | ------- | ------ | ----- | ----------- |
| `select` | `label` | `tap` |  | User tapped the scene label. |

**Default transform**

```json
{
  "anchor": "world",
  "position": [
    0.0,
    1.2,
    1.0
  ],
  "rotation": [
    0.0,
    0.0,
    0.0,
    1.0
  ],
  "scale": [
    1.0,
    1.0,
    1.0
  ],
  "billboard": true
}
```

**Example `holo.spawn`**

```json
{
  "v": "1.1.0",
  "id": "msg-uuid",
  "type": "holo.spawn",
  "ts": 1733397600000,
  "session": "session-uuid",
  "payload": {
    "object_id": "object-uuid",
    "widget_type": "scene_label",
    "transform": {
      "anchor": "world",
      "position": [
        0.0,
        1.2,
        1.0
      ],
      "rotation": [
        0.0,
        0.0,
        0.0,
        1.0
      ],
      "scale": [
        1.0,
        1.0,
        1.0
      ],
      "billboard": true
    },
    "props": {
      "text": "Keys (last seen here)",
      "icon": "pin",
      "color": "#FF5252",
      "pin": true
    },
    "interactable": true,
    "interactions": [
      "tap",
      "grab"
    ],
    "ttl_ms": 0
  }
}
```

<a id="clock"></a>

### `clock` — Clock

A floating analog or digital clock for a given timezone.

- **Category:** `utility`
- **Prefab id:** `Holo_Clock`
- **Interactions:** `grab`, `tap`, `resize`

**Props**

| Prop | Type | Required | Default | Constraints | Description |
| ---- | ---- | :------: | ------- | ----------- | ----------- |
| `timezone` | string |  |  |  | IANA timezone, e.g. 'America/New_York'. |
| `format` | enum |  | `"24h"` | one of: `12h`, `24h` |  |
| `style` | enum |  | `"digital"` | one of: `analog`, `digital` |  |
| `show_seconds` | boolean |  | `true` |  |  |
| `show_date` | boolean |  | `true` |  |  |
| `label` | string |  |  |  |  |

**Events emitted** (sent back as `client.interaction`)

| Event | Element | Action | Value | Description |
| ----- | ------- | ------ | ----- | ----------- |
| `toggle_format` | `clock` | `tap` |  | User toggled 12h/24h. |

**Default transform**

```json
{
  "anchor": "world",
  "position": [
    0.0,
    1.5,
    1.0
  ],
  "rotation": [
    0.0,
    0.0,
    0.0,
    1.0
  ],
  "scale": [
    1.0,
    1.0,
    1.0
  ],
  "billboard": true
}
```

**Example `holo.spawn`**

```json
{
  "v": "1.1.0",
  "id": "msg-uuid",
  "type": "holo.spawn",
  "ts": 1733397600000,
  "session": "session-uuid",
  "payload": {
    "object_id": "object-uuid",
    "widget_type": "clock",
    "transform": {
      "anchor": "world",
      "position": [
        0.0,
        1.5,
        1.0
      ],
      "rotation": [
        0.0,
        0.0,
        0.0,
        1.0
      ],
      "scale": [
        1.0,
        1.0,
        1.0
      ],
      "billboard": true
    },
    "props": {
      "timezone": "America/New_York",
      "format": "12h",
      "style": "digital",
      "show_seconds": true,
      "show_date": true,
      "label": "New York"
    },
    "interactable": true,
    "interactions": [
      "grab",
      "tap",
      "resize"
    ],
    "ttl_ms": 0
  }
}
```

<a id="world_clock"></a>

### `world_clock` — World Clock

Several clocks for different cities/timezones at a glance.

- **Category:** `utility`
- **Prefab id:** `Holo_WorldClock`
- **Interactions:** `grab`, `tap`, `resize`, `drag`

**Props**

| Prop | Type | Required | Default | Constraints | Description |
| ---- | ---- | :------: | ------- | ----------- | ----------- |
| `zones` | array&lt;object&gt; | yes |  | minItems 1; items: {label*, timezone*, format} |  |
| `style` | enum |  | `"list"` | one of: `list`, `row` |  |

**Events emitted** (sent back as `client.interaction`)

| Event | Element | Action | Value | Description |
| ----- | ------- | ------ | ----- | ----------- |
| `select_zone` | `zone_row` | `tap` | {index} | User tapped a timezone row. |

**Default transform**

```json
{
  "anchor": "world",
  "position": [
    0.0,
    1.5,
    1.1
  ],
  "rotation": [
    0.0,
    0.0,
    0.0,
    1.0
  ],
  "scale": [
    1.0,
    1.0,
    1.0
  ],
  "billboard": true
}
```

**Example `holo.spawn`**

```json
{
  "v": "1.1.0",
  "id": "msg-uuid",
  "type": "holo.spawn",
  "ts": 1733397600000,
  "session": "session-uuid",
  "payload": {
    "object_id": "object-uuid",
    "widget_type": "world_clock",
    "transform": {
      "anchor": "world",
      "position": [
        0.0,
        1.5,
        1.1
      ],
      "rotation": [
        0.0,
        0.0,
        0.0,
        1.0
      ],
      "scale": [
        1.0,
        1.0,
        1.0
      ],
      "billboard": true
    },
    "props": {
      "zones": [
        {
          "label": "SF",
          "timezone": "America/Los_Angeles",
          "format": "12h"
        },
        {
          "label": "London",
          "timezone": "Europe/London",
          "format": "24h"
        },
        {
          "label": "Tokyo",
          "timezone": "Asia/Tokyo",
          "format": "24h"
        }
      ],
      "style": "list"
    },
    "interactable": true,
    "interactions": [
      "grab",
      "tap",
      "resize",
      "drag"
    ],
    "ttl_ms": 0
  }
}
```

<a id="calendar"></a>

### `calendar` — Calendar

A calendar/agenda surface showing events for a day, week, or month.

- **Category:** `productivity`
- **Prefab id:** `Holo_Calendar`
- **Interactions:** `grab`, `tap`, `resize`, `drag`, `dwell`

**Props**

| Prop | Type | Required | Default | Constraints | Description |
| ---- | ---- | :------: | ------- | ----------- | ----------- |
| `title` | string |  |  |  |  |
| `view` | enum |  | `"agenda"` | one of: `day`, `week`, `month`, `agenda` |  |
| `date` | string |  |  | format: date | Focused date (ISO 8601). |
| `events` | array&lt;object&gt; | yes |  | items: {id*, title*, start*, end, location, color, all_day} |  |

**Events emitted** (sent back as `client.interaction`)

| Event | Element | Action | Value | Description |
| ----- | ------- | ------ | ----- | ----------- |
| `select_event` | `event` | `tap` | {event_id} | User tapped an event. |

**Default transform**

```json
{
  "anchor": "world",
  "position": [
    0.0,
    1.4,
    1.1
  ],
  "rotation": [
    0.0,
    0.0,
    0.0,
    1.0
  ],
  "scale": [
    1.0,
    1.0,
    1.0
  ],
  "billboard": true
}
```

**Example `holo.spawn`**

```json
{
  "v": "1.1.0",
  "id": "msg-uuid",
  "type": "holo.spawn",
  "ts": 1733397600000,
  "session": "session-uuid",
  "payload": {
    "object_id": "object-uuid",
    "widget_type": "calendar",
    "transform": {
      "anchor": "world",
      "position": [
        0.0,
        1.4,
        1.1
      ],
      "rotation": [
        0.0,
        0.0,
        0.0,
        1.0
      ],
      "scale": [
        1.0,
        1.0,
        1.0
      ],
      "billboard": true
    },
    "props": {
      "title": "Today",
      "view": "agenda",
      "date": "2026-06-05",
      "events": [
        {
          "id": "e1",
          "title": "Flight test",
          "start": "2026-06-05T14:00:00Z",
          "end": "2026-06-05T15:00:00Z",
          "location": "Hangar 3",
          "color": "#4FC3F7",
          "all_day": false
        }
      ]
    },
    "interactable": true,
    "interactions": [
      "grab",
      "tap",
      "resize",
      "drag",
      "dwell"
    ],
    "ttl_ms": 0
  }
}
```

<a id="stocks_ticker"></a>

### `stocks_ticker` — Stocks Ticker

A scrolling ticker of stock/crypto symbols with prices and percentage changes.

- **Category:** `data`
- **Prefab id:** `Holo_StocksTicker`
- **Interactions:** `grab`, `tap`, `resize`, `drag`

**Props**

| Prop | Type | Required | Default | Constraints | Description |
| ---- | ---- | :------: | ------- | ----------- | ----------- |
| `title` | string |  |  |  |  |
| `symbols` | array&lt;object&gt; | yes |  | minItems 1; items: {symbol*, price*, change_pct, currency} |  |
| `scroll` | boolean |  | `true` |  |  |

**Events emitted** (sent back as `client.interaction`)

| Event | Element | Action | Value | Description |
| ----- | ------- | ------ | ----- | ----------- |
| `select_symbol` | `ticker_item` | `tap` | {symbol} | User tapped a symbol. |

**Default transform**

```json
{
  "anchor": "head",
  "position": [
    0.0,
    0.55,
    1.2
  ],
  "rotation": [
    0.0,
    0.0,
    0.0,
    1.0
  ],
  "scale": [
    1.0,
    1.0,
    1.0
  ],
  "billboard": true
}
```

**Example `holo.spawn`**

```json
{
  "v": "1.1.0",
  "id": "msg-uuid",
  "type": "holo.spawn",
  "ts": 1733397600000,
  "session": "session-uuid",
  "payload": {
    "object_id": "object-uuid",
    "widget_type": "stocks_ticker",
    "transform": {
      "anchor": "head",
      "position": [
        0.0,
        0.55,
        1.2
      ],
      "rotation": [
        0.0,
        0.0,
        0.0,
        1.0
      ],
      "scale": [
        1.0,
        1.0,
        1.0
      ],
      "billboard": true
    },
    "props": {
      "title": "Watchlist",
      "symbols": [
        {
          "symbol": "AAPL",
          "price": 214.5,
          "change_pct": 1.2,
          "currency": "USD"
        },
        {
          "symbol": "TSLA",
          "price": 178.3,
          "change_pct": -0.8,
          "currency": "USD"
        }
      ],
      "scroll": true
    },
    "interactable": true,
    "interactions": [
      "grab",
      "tap",
      "resize",
      "drag"
    ],
    "ttl_ms": 0
  }
}
```

<a id="news_feed"></a>

### `news_feed` — News Feed

A scrollable feed of news headlines with sources and summaries.

- **Category:** `information`
- **Prefab id:** `Holo_NewsFeed`
- **Interactions:** `grab`, `tap`, `resize`, `drag`, `dwell`

**Props**

| Prop | Type | Required | Default | Constraints | Description |
| ---- | ---- | :------: | ------- | ----------- | ----------- |
| `title` | string |  |  |  |  |
| `category` | string |  |  |  |  |
| `articles` | array&lt;object&gt; | yes |  | minItems 1; items: {id*, headline*, source, summary, url, image_url, published_at} |  |

**Events emitted** (sent back as `client.interaction`)

| Event | Element | Action | Value | Description |
| ----- | ------- | ------ | ----- | ----------- |
| `open_article` | `article` | `tap` | {article_id} | User opened an article. |

**Default transform**

```json
{
  "anchor": "world",
  "position": [
    0.0,
    1.4,
    1.1
  ],
  "rotation": [
    0.0,
    0.0,
    0.0,
    1.0
  ],
  "scale": [
    1.0,
    1.0,
    1.0
  ],
  "billboard": true
}
```

**Example `holo.spawn`**

```json
{
  "v": "1.1.0",
  "id": "msg-uuid",
  "type": "holo.spawn",
  "ts": 1733397600000,
  "session": "session-uuid",
  "payload": {
    "object_id": "object-uuid",
    "widget_type": "news_feed",
    "transform": {
      "anchor": "world",
      "position": [
        0.0,
        1.4,
        1.1
      ],
      "rotation": [
        0.0,
        0.0,
        0.0,
        1.0
      ],
      "scale": [
        1.0,
        1.0,
        1.0
      ],
      "billboard": true
    },
    "props": {
      "title": "Top Stories",
      "category": "technology",
      "articles": [
        {
          "id": "a1",
          "headline": "Quest 4 announced",
          "source": "TechNews",
          "summary": "Meta unveils its next mixed-reality headset.",
          "url": "https://example.com/a1"
        }
      ]
    },
    "interactable": true,
    "interactions": [
      "grab",
      "tap",
      "resize",
      "drag",
      "dwell"
    ],
    "ttl_ms": 0
  }
}
```

<a id="translator"></a>

### `translator` — Translator

A live translation panel for text, conversation, or signs read from the camera.

- **Category:** `communication`
- **Prefab id:** `Holo_Translator`
- **Interactions:** `grab`, `tap`, `resize`, `toggle`

**Props**

| Prop | Type | Required | Default | Constraints | Description |
| ---- | ---- | :------: | ------- | ----------- | ----------- |
| `source_lang` | string | yes |  |  | BCP-47 source language or 'auto'. |
| `target_lang` | string | yes |  |  | BCP-47 target language. |
| `source_text` | string |  |  |  |  |
| `translated_text` | string |  |  |  |  |
| `mode` | enum |  | `"text"` | one of: `text`, `conversation`, `sign` |  |
| `listening` | boolean |  | `false` |  |  |

**Events emitted** (sent back as `client.interaction`)

| Event | Element | Action | Value | Description |
| ----- | ------- | ------ | ----- | ----------- |
| `toggle_listen` | `mic_toggle` | `toggle` | {listening} | User toggled live listening. |
| `swap_languages` | `swap_button` | `tap` |  | User swapped source/target languages. |

**Default transform**

```json
{
  "anchor": "head",
  "position": [
    0.0,
    0.0,
    1.0
  ],
  "rotation": [
    0.0,
    0.0,
    0.0,
    1.0
  ],
  "scale": [
    1.0,
    1.0,
    1.0
  ],
  "billboard": true
}
```

**Example `holo.spawn`**

```json
{
  "v": "1.1.0",
  "id": "msg-uuid",
  "type": "holo.spawn",
  "ts": 1733397600000,
  "session": "session-uuid",
  "payload": {
    "object_id": "object-uuid",
    "widget_type": "translator",
    "transform": {
      "anchor": "head",
      "position": [
        0.0,
        0.0,
        1.0
      ],
      "rotation": [
        0.0,
        0.0,
        0.0,
        1.0
      ],
      "scale": [
        1.0,
        1.0,
        1.0
      ],
      "billboard": true
    },
    "props": {
      "source_lang": "ja",
      "target_lang": "en",
      "source_text": "\u3053\u3093\u306b\u3061\u306f",
      "translated_text": "Hello",
      "mode": "sign",
      "listening": false
    },
    "interactable": true,
    "interactions": [
      "grab",
      "tap",
      "resize",
      "toggle"
    ],
    "ttl_ms": 0
  }
}
```

<a id="recipe_card"></a>

### `recipe_card` — Recipe Card

A step-by-step cooking card with ingredients, timings, and a current-step highlight.

- **Category:** `information`
- **Prefab id:** `Holo_RecipeCard`
- **Interactions:** `grab`, `tap`, `resize`, `drag`

**Props**

| Prop | Type | Required | Default | Constraints | Description |
| ---- | ---- | :------: | ------- | ----------- | ----------- |
| `title` | string | yes |  | minLen 1 |  |
| `servings` | integer |  |  | > 0 |  |
| `prep_min` | integer |  |  | min 0 |  |
| `cook_min` | integer |  |  | min 0 |  |
| `ingredients` | array&lt;string&gt; | yes |  | minItems 1 |  |
| `steps` | array&lt;string&gt; | yes |  | minItems 1 |  |
| `image_url` | string |  |  | format: uri |  |
| `current_step` | integer |  |  | min 0 |  |

**Events emitted** (sent back as `client.interaction`)

| Event | Element | Action | Value | Description |
| ----- | ------- | ------ | ----- | ----------- |
| `next_step` | `next_button` | `tap` |  | User advanced to the next step. |
| `prev_step` | `prev_button` | `tap` |  | User went to the previous step. |

**Default transform**

```json
{
  "anchor": "world",
  "position": [
    0.0,
    1.3,
    0.9
  ],
  "rotation": [
    0.0,
    0.0,
    0.0,
    1.0
  ],
  "scale": [
    1.0,
    1.0,
    1.0
  ],
  "billboard": true
}
```

**Example `holo.spawn`**

```json
{
  "v": "1.1.0",
  "id": "msg-uuid",
  "type": "holo.spawn",
  "ts": 1733397600000,
  "session": "session-uuid",
  "payload": {
    "object_id": "object-uuid",
    "widget_type": "recipe_card",
    "transform": {
      "anchor": "world",
      "position": [
        0.0,
        1.3,
        0.9
      ],
      "rotation": [
        0.0,
        0.0,
        0.0,
        1.0
      ],
      "scale": [
        1.0,
        1.0,
        1.0
      ],
      "billboard": true
    },
    "props": {
      "title": "Pancakes",
      "servings": 4,
      "prep_min": 10,
      "cook_min": 15,
      "ingredients": [
        "2 cups flour",
        "2 eggs",
        "1.5 cups milk"
      ],
      "steps": [
        "Mix dry ingredients",
        "Whisk in wet ingredients",
        "Cook on a hot griddle"
      ],
      "image_url": "https://cdn.jarvisvr.app/img/pancakes.jpg",
      "current_step": 0
    },
    "interactable": true,
    "interactions": [
      "grab",
      "tap",
      "resize",
      "drag"
    ],
    "ttl_ms": 0
  }
}
```

<a id="whiteboard"></a>

### `whiteboard` — Whiteboard

A free-form sketch surface the user can draw on with hand strokes.

- **Category:** `productivity`
- **Prefab id:** `Holo_Whiteboard`
- **Interactions:** `grab`, `resize`, `drag`, `tap`

**Props**

| Prop | Type | Required | Default | Constraints | Description |
| ---- | ---- | :------: | ------- | ----------- | ----------- |
| `title` | string |  |  |  |  |
| `width_m` | number |  | `1.2` | > 0 |  |
| `height_m` | number |  | `0.8` | > 0 |  |
| `background` | enum |  | `"white"` | one of: `white`, `dark`, `grid` |  |
| `strokes` | array&lt;object&gt; |  |  | items: {points*, color, width} |  |
| `editable` | boolean |  | `true` |  |  |

**Events emitted** (sent back as `client.interaction`)

| Event | Element | Action | Value | Description |
| ----- | ------- | ------ | ----- | ----------- |
| `draw_stroke` | `canvas` | `drag` | {points} | User drew a stroke. |
| `clear` | `clear_button` | `tap` |  | User cleared the board. |

**Default transform**

```json
{
  "anchor": "world",
  "position": [
    0.0,
    1.4,
    1.2
  ],
  "rotation": [
    0.0,
    0.0,
    0.0,
    1.0
  ],
  "scale": [
    1.0,
    1.0,
    1.0
  ],
  "billboard": false
}
```

**Example `holo.spawn`**

```json
{
  "v": "1.1.0",
  "id": "msg-uuid",
  "type": "holo.spawn",
  "ts": 1733397600000,
  "session": "session-uuid",
  "payload": {
    "object_id": "object-uuid",
    "widget_type": "whiteboard",
    "transform": {
      "anchor": "world",
      "position": [
        0.0,
        1.4,
        1.2
      ],
      "rotation": [
        0.0,
        0.0,
        0.0,
        1.0
      ],
      "scale": [
        1.0,
        1.0,
        1.0
      ],
      "billboard": false
    },
    "props": {
      "title": "Brainstorm",
      "width_m": 1.2,
      "height_m": 0.8,
      "background": "white",
      "strokes": [
        {
          "points": [
            [
              0.1,
              0.1
            ],
            [
              0.2,
              0.2
            ],
            [
              0.3,
              0.15
            ]
          ],
          "color": "#000000",
          "width": 0.01
        }
      ],
      "editable": true
    },
    "interactable": true,
    "interactions": [
      "grab",
      "resize",
      "drag",
      "tap"
    ],
    "ttl_ms": 0
  }
}
```

<a id="sticky_note"></a>

### `sticky_note` — Sticky Note

A colored sticky note that can be placed and pinned in space.

- **Category:** `productivity`
- **Prefab id:** `Holo_StickyNote`
- **Interactions:** `grab`, `tap`, `resize`, `drag`

**Props**

| Prop | Type | Required | Default | Constraints | Description |
| ---- | ---- | :------: | ------- | ----------- | ----------- |
| `text` | string | yes |  | minLen 1 |  |
| `color` | enum |  | `"yellow"` | one of: `yellow`, `pink`, `blue`, `green`, `orange` |  |
| `pinned` | boolean |  | `false` |  |  |
| `author` | string |  |  |  |  |

**Events emitted** (sent back as `client.interaction`)

| Event | Element | Action | Value | Description |
| ----- | ------- | ------ | ----- | ----------- |
| `edit` | `note` | `tap` |  | User tapped to edit the note. |

**Default transform**

```json
{
  "anchor": "world",
  "position": [
    0.0,
    1.3,
    0.8
  ],
  "rotation": [
    0.0,
    0.0,
    0.0,
    1.0
  ],
  "scale": [
    1.0,
    1.0,
    1.0
  ],
  "billboard": true
}
```

**Example `holo.spawn`**

```json
{
  "v": "1.1.0",
  "id": "msg-uuid",
  "type": "holo.spawn",
  "ts": 1733397600000,
  "session": "session-uuid",
  "payload": {
    "object_id": "object-uuid",
    "widget_type": "sticky_note",
    "transform": {
      "anchor": "world",
      "position": [
        0.0,
        1.3,
        0.8
      ],
      "rotation": [
        0.0,
        0.0,
        0.0,
        1.0
      ],
      "scale": [
        1.0,
        1.0,
        1.0
      ],
      "billboard": true
    },
    "props": {
      "text": "Buy milk",
      "color": "yellow",
      "pinned": true,
      "author": "You"
    },
    "interactable": true,
    "interactions": [
      "grab",
      "tap",
      "resize",
      "drag"
    ],
    "ttl_ms": 0
  }
}
```

<a id="code_viewer"></a>

### `code_viewer` — Code Viewer

A syntax-highlighted code panel with optional line highlighting and copy.

- **Category:** `developer`
- **Prefab id:** `Holo_CodeViewer`
- **Interactions:** `grab`, `tap`, `resize`, `drag`

**Props**

| Prop | Type | Required | Default | Constraints | Description |
| ---- | ---- | :------: | ------- | ----------- | ----------- |
| `code` | string | yes |  |  |  |
| `language` | string |  |  |  | Language id for highlighting, e.g. 'python'. |
| `title` | string |  |  |  |  |
| `theme` | enum |  | `"dark"` | one of: `dark`, `light` |  |
| `wrap` | boolean |  | `false` |  |  |
| `highlight_lines` | array&lt;integer&gt; |  |  |  |  |

**Events emitted** (sent back as `client.interaction`)

| Event | Element | Action | Value | Description |
| ----- | ------- | ------ | ----- | ----------- |
| `copy` | `copy_button` | `tap` |  | User copied the code. |

**Default transform**

```json
{
  "anchor": "world",
  "position": [
    0.0,
    1.4,
    1.1
  ],
  "rotation": [
    0.0,
    0.0,
    0.0,
    1.0
  ],
  "scale": [
    1.0,
    1.0,
    1.0
  ],
  "billboard": false
}
```

**Example `holo.spawn`**

```json
{
  "v": "1.1.0",
  "id": "msg-uuid",
  "type": "holo.spawn",
  "ts": 1733397600000,
  "session": "session-uuid",
  "payload": {
    "object_id": "object-uuid",
    "widget_type": "code_viewer",
    "transform": {
      "anchor": "world",
      "position": [
        0.0,
        1.4,
        1.1
      ],
      "rotation": [
        0.0,
        0.0,
        0.0,
        1.0
      ],
      "scale": [
        1.0,
        1.0,
        1.0
      ],
      "billboard": false
    },
    "props": {
      "code": "def greet(name):\n    print(f'Hello, {name}!')",
      "language": "python",
      "title": "hello.py",
      "theme": "dark",
      "wrap": false,
      "highlight_lines": [
        2
      ]
    },
    "interactable": true,
    "interactions": [
      "grab",
      "tap",
      "resize",
      "drag"
    ],
    "ttl_ms": 0
  }
}
```

<a id="document_viewer"></a>

### `document_viewer` — Document Viewer

A paged document viewer for PDFs, markdown, or text.

- **Category:** `media`
- **Prefab id:** `Holo_DocumentViewer`
- **Interactions:** `grab`, `tap`, `resize`, `drag`, `slider`

**Props**

| Prop | Type | Required | Default | Constraints | Description |
| ---- | ---- | :------: | ------- | ----------- | ----------- |
| `url` | string | yes |  | format: uri |  |
| `title` | string |  |  |  |  |
| `doc_type` | enum |  | `"pdf"` | one of: `pdf`, `markdown`, `text`, `docx` |  |
| `page` | integer |  | `1` | min 1 |  |
| `page_count` | integer |  |  | min 1 |  |

**Events emitted** (sent back as `client.interaction`)

| Event | Element | Action | Value | Description |
| ----- | ------- | ------ | ----- | ----------- |
| `goto_page` | `page_slider` | `slider` | {page} | User changed page. |
| `select` | `document` | `tap` |  | User tapped the document. |

**Default transform**

```json
{
  "anchor": "world",
  "position": [
    0.0,
    1.4,
    1.1
  ],
  "rotation": [
    0.0,
    0.0,
    0.0,
    1.0
  ],
  "scale": [
    1.0,
    1.0,
    1.0
  ],
  "billboard": false
}
```

**Example `holo.spawn`**

```json
{
  "v": "1.1.0",
  "id": "msg-uuid",
  "type": "holo.spawn",
  "ts": 1733397600000,
  "session": "session-uuid",
  "payload": {
    "object_id": "object-uuid",
    "widget_type": "document_viewer",
    "transform": {
      "anchor": "world",
      "position": [
        0.0,
        1.4,
        1.1
      ],
      "rotation": [
        0.0,
        0.0,
        0.0,
        1.0
      ],
      "scale": [
        1.0,
        1.0,
        1.0
      ],
      "billboard": false
    },
    "props": {
      "url": "https://cdn.jarvisvr.app/docs/manual.pdf",
      "title": "User Manual",
      "doc_type": "pdf",
      "page": 1,
      "page_count": 42
    },
    "interactable": true,
    "interactions": [
      "grab",
      "tap",
      "resize",
      "drag",
      "slider"
    ],
    "ttl_ms": 0
  }
}
```

<a id="web_panel"></a>

### `web_panel` — Web Panel

An interactive browser surface that renders a web page in space.

- **Category:** `media`
- **Prefab id:** `Holo_WebPanel`
- **Interactions:** `grab`, `tap`, `resize`, `drag`, `slider`

**Props**

| Prop | Type | Required | Default | Constraints | Description |
| ---- | ---- | :------: | ------- | ----------- | ----------- |
| `url` | string | yes |  | format: uri |  |
| `title` | string |  |  |  |  |
| `width_m` | number |  | `0.9` | > 0 |  |
| `height_m` | number |  | `0.6` | > 0 |  |
| `interactive` | boolean |  | `true` |  |  |
| `scroll_y` | number |  | `0` | min 0 |  |

**Events emitted** (sent back as `client.interaction`)

| Event | Element | Action | Value | Description |
| ----- | ------- | ------ | ----- | ----------- |
| `navigate` | `page` | `tap` | {href} | User tapped a link/element. |
| `scroll` | `scrollbar` | `slider` | {scroll_y} | User scrolled the page. |

**Default transform**

```json
{
  "anchor": "world",
  "position": [
    0.0,
    1.4,
    1.0
  ],
  "rotation": [
    0.0,
    0.0,
    0.0,
    1.0
  ],
  "scale": [
    1.0,
    1.0,
    1.0
  ],
  "billboard": false
}
```

**Example `holo.spawn`**

```json
{
  "v": "1.1.0",
  "id": "msg-uuid",
  "type": "holo.spawn",
  "ts": 1733397600000,
  "session": "session-uuid",
  "payload": {
    "object_id": "object-uuid",
    "widget_type": "web_panel",
    "transform": {
      "anchor": "world",
      "position": [
        0.0,
        1.4,
        1.0
      ],
      "rotation": [
        0.0,
        0.0,
        0.0,
        1.0
      ],
      "scale": [
        1.0,
        1.0,
        1.0
      ],
      "billboard": false
    },
    "props": {
      "url": "https://en.wikipedia.org/wiki/Mixed_reality",
      "title": "Wikipedia",
      "width_m": 0.9,
      "height_m": 0.6,
      "interactive": true,
      "scroll_y": 0
    },
    "interactable": true,
    "interactions": [
      "grab",
      "tap",
      "resize",
      "drag",
      "slider"
    ],
    "ttl_ms": 0
  }
}
```

<a id="avatar"></a>

### `avatar` — Jarvis Avatar

Jarvis's visual presence (orb/face/ring) that reflects agent state and emotion.

- **Category:** `communication`
- **Prefab id:** `Holo_Avatar`
- **Interactions:** `grab`, `tap`, `dwell`

**Props**

| Prop | Type | Required | Default | Constraints | Description |
| ---- | ---- | :------: | ------- | ----------- | ----------- |
| `name` | string |  | `"Jarvis"` |  |  |
| `state` | enum |  | `"idle"` | one of: `idle`, `listening`, `thinking`, `speaking` |  |
| `emotion` | enum |  | `"neutral"` | one of: `neutral`, `happy`, `concerned`, `alert` |  |
| `style` | enum |  | `"orb"` | one of: `orb`, `face`, `ring` |  |
| `speaking_text` | string |  |  |  |  |

**Events emitted** (sent back as `client.interaction`)

| Event | Element | Action | Value | Description |
| ----- | ------- | ------ | ----- | ----------- |
| `activate` | `avatar` | `tap` |  | User tapped to wake/activate Jarvis. |

**Default transform**

```json
{
  "anchor": "head",
  "position": [
    0.6,
    0.0,
    0.9
  ],
  "rotation": [
    0.0,
    0.0,
    0.0,
    1.0
  ],
  "scale": [
    1.0,
    1.0,
    1.0
  ],
  "billboard": true
}
```

**Example `holo.spawn`**

```json
{
  "v": "1.1.0",
  "id": "msg-uuid",
  "type": "holo.spawn",
  "ts": 1733397600000,
  "session": "session-uuid",
  "payload": {
    "object_id": "object-uuid",
    "widget_type": "avatar",
    "transform": {
      "anchor": "head",
      "position": [
        0.6,
        0.0,
        0.9
      ],
      "rotation": [
        0.0,
        0.0,
        0.0,
        1.0
      ],
      "scale": [
        1.0,
        1.0,
        1.0
      ],
      "billboard": true
    },
    "props": {
      "name": "Jarvis",
      "state": "speaking",
      "emotion": "neutral",
      "style": "orb",
      "speaking_text": "How can I help?"
    },
    "interactable": true,
    "interactions": [
      "grab",
      "tap",
      "dwell"
    ],
    "ttl_ms": 0
  }
}
```

<a id="navigation_arrow"></a>

### `navigation_arrow` — Navigation Arrow

A wayfinding arrow/beam pointing toward a destination, with distance and ETA.

- **Category:** `navigation`
- **Prefab id:** `Holo_NavigationArrow`
- **Interactions:** `tap`, `dwell`

**Props**

| Prop | Type | Required | Default | Constraints | Description |
| ---- | ---- | :------: | ------- | ----------- | ----------- |
| `target_label` | string |  |  |  |  |
| `direction` | array&lt;number&gt; | yes |  | minItems 3; maxItems 3 | Unit direction vector to the destination. |
| `distance_m` | number |  |  | min 0 |  |
| `eta_min` | number |  |  | min 0 |  |
| `color` | string |  |  | hex/pattern | Hex color (#RRGGBB or #RRGGBBAA). |
| `style` | enum |  | `"arrow"` | one of: `arrow`, `beam`, `path` |  |

**Events emitted** (sent back as `client.interaction`)

| Event | Element | Action | Value | Description |
| ----- | ------- | ------ | ----- | ----------- |
| `recenter` | `arrow` | `tap` |  | User recentered/recalculated the route. |

**Default transform**

```json
{
  "anchor": "world",
  "position": [
    0.0,
    1.2,
    1.2
  ],
  "rotation": [
    0.0,
    0.0,
    0.0,
    1.0
  ],
  "scale": [
    1.0,
    1.0,
    1.0
  ],
  "billboard": false
}
```

**Example `holo.spawn`**

```json
{
  "v": "1.1.0",
  "id": "msg-uuid",
  "type": "holo.spawn",
  "ts": 1733397600000,
  "session": "session-uuid",
  "payload": {
    "object_id": "object-uuid",
    "widget_type": "navigation_arrow",
    "transform": {
      "anchor": "world",
      "position": [
        0.0,
        1.2,
        1.2
      ],
      "rotation": [
        0.0,
        0.0,
        0.0,
        1.0
      ],
      "scale": [
        1.0,
        1.0,
        1.0
      ],
      "billboard": false
    },
    "props": {
      "target_label": "Kitchen",
      "direction": [
        0.0,
        0.0,
        1.0
      ],
      "distance_m": 8.5,
      "eta_min": 1.0,
      "color": "#4FC3F7",
      "style": "arrow"
    },
    "interactable": true,
    "interactions": [
      "tap",
      "dwell"
    ],
    "ttl_ms": 0
  }
}
```

<a id="health_ring"></a>

### `health_ring` — Health Rings

Activity/fitness rings showing progress toward daily goals.

- **Category:** `health`
- **Prefab id:** `Holo_HealthRing`
- **Interactions:** `grab`, `tap`, `resize`, `dwell`

**Props**

| Prop | Type | Required | Default | Constraints | Description |
| ---- | ---- | :------: | ------- | ----------- | ----------- |
| `title` | string |  |  |  |  |
| `rings` | array&lt;object&gt; | yes |  | minItems 1; items: {label*, value*, goal*, unit, color} |  |

**Events emitted** (sent back as `client.interaction`)

| Event | Element | Action | Value | Description |
| ----- | ------- | ------ | ----- | ----------- |
| `select_ring` | `ring` | `tap` | {index} | User tapped a ring. |

**Default transform**

```json
{
  "anchor": "head",
  "position": [
    -0.5,
    0.2,
    0.9
  ],
  "rotation": [
    0.0,
    0.0,
    0.0,
    1.0
  ],
  "scale": [
    1.0,
    1.0,
    1.0
  ],
  "billboard": true
}
```

**Example `holo.spawn`**

```json
{
  "v": "1.1.0",
  "id": "msg-uuid",
  "type": "holo.spawn",
  "ts": 1733397600000,
  "session": "session-uuid",
  "payload": {
    "object_id": "object-uuid",
    "widget_type": "health_ring",
    "transform": {
      "anchor": "head",
      "position": [
        -0.5,
        0.2,
        0.9
      ],
      "rotation": [
        0.0,
        0.0,
        0.0,
        1.0
      ],
      "scale": [
        1.0,
        1.0,
        1.0
      ],
      "billboard": true
    },
    "props": {
      "title": "Today",
      "rings": [
        {
          "label": "Move",
          "value": 420,
          "goal": 600,
          "unit": "kcal",
          "color": "#FF5252"
        },
        {
          "label": "Steps",
          "value": 7200,
          "goal": 10000,
          "unit": "steps",
          "color": "#4FC3F7"
        }
      ]
    },
    "interactable": true,
    "interactions": [
      "grab",
      "tap",
      "resize",
      "dwell"
    ],
    "ttl_ms": 0
  }
}
```

<a id="music_visualizer"></a>

### `music_visualizer` — Music Visualizer

An audio-reactive 3D visualizer with now-playing info.

- **Category:** `media`
- **Prefab id:** `Holo_MusicVisualizer`
- **Interactions:** `grab`, `tap`, `resize`

**Props**

| Prop | Type | Required | Default | Constraints | Description |
| ---- | ---- | :------: | ------- | ----------- | ----------- |
| `track` | string |  |  |  |  |
| `artist` | string |  |  |  |  |
| `style` | enum |  | `"bars"` | one of: `bars`, `wave`, `particles`, `sphere` |  |
| `amplitude` | array&lt;number&gt; |  |  |  | Spectrum bins, each 0.0-1.0. |
| `color` | string |  |  | hex/pattern | Hex color (#RRGGBB or #RRGGBBAA). |
| `playing` | boolean |  | `true` |  |  |

**Events emitted** (sent back as `client.interaction`)

| Event | Element | Action | Value | Description |
| ----- | ------- | ------ | ----- | ----------- |
| `toggle_play` | `visualizer` | `tap` |  | User toggled playback. |

**Default transform**

```json
{
  "anchor": "world",
  "position": [
    0.0,
    1.3,
    1.2
  ],
  "rotation": [
    0.0,
    0.0,
    0.0,
    1.0
  ],
  "scale": [
    1.0,
    1.0,
    1.0
  ],
  "billboard": true
}
```

**Example `holo.spawn`**

```json
{
  "v": "1.1.0",
  "id": "msg-uuid",
  "type": "holo.spawn",
  "ts": 1733397600000,
  "session": "session-uuid",
  "payload": {
    "object_id": "object-uuid",
    "widget_type": "music_visualizer",
    "transform": {
      "anchor": "world",
      "position": [
        0.0,
        1.3,
        1.2
      ],
      "rotation": [
        0.0,
        0.0,
        0.0,
        1.0
      ],
      "scale": [
        1.0,
        1.0,
        1.0
      ],
      "billboard": true
    },
    "props": {
      "track": "Lofi Beats",
      "artist": "Chillhop",
      "style": "bars",
      "amplitude": [
        0.2,
        0.6,
        0.9,
        0.4,
        0.7
      ],
      "color": "#7FE7FF",
      "playing": true
    },
    "interactable": true,
    "interactions": [
      "grab",
      "tap",
      "resize"
    ],
    "ttl_ms": 0
  }
}
```

<a id="graph_3d"></a>

### `graph_3d` — Network Graph

A 3D node/edge graph for relationships, networks, or knowledge graphs.

- **Category:** `data`
- **Prefab id:** `Holo_Graph3D`
- **Interactions:** `grab`, `tap`, `drag`, `resize`, `dwell`

**Props**

| Prop | Type | Required | Default | Constraints | Description |
| ---- | ---- | :------: | ------- | ----------- | ----------- |
| `title` | string |  |  |  |  |
| `nodes` | array&lt;object&gt; | yes |  | minItems 1; items: {id*, label, group, size, color} |  |
| `edges` | array&lt;object&gt; |  |  | items: {source*, target*, weight, label} |  |
| `layout` | enum |  | `"force"` | one of: `force`, `radial`, `grid` |  |
| `directed` | boolean |  | `false` |  |  |

**Events emitted** (sent back as `client.interaction`)

| Event | Element | Action | Value | Description |
| ----- | ------- | ------ | ----- | ----------- |
| `select_node` | `node` | `tap` | {node_id} | User tapped a node. |

**Default transform**

```json
{
  "anchor": "world",
  "position": [
    0.0,
    1.3,
    1.2
  ],
  "rotation": [
    0.0,
    0.0,
    0.0,
    1.0
  ],
  "scale": [
    1.0,
    1.0,
    1.0
  ],
  "billboard": false
}
```

**Example `holo.spawn`**

```json
{
  "v": "1.1.0",
  "id": "msg-uuid",
  "type": "holo.spawn",
  "ts": 1733397600000,
  "session": "session-uuid",
  "payload": {
    "object_id": "object-uuid",
    "widget_type": "graph_3d",
    "transform": {
      "anchor": "world",
      "position": [
        0.0,
        1.3,
        1.2
      ],
      "rotation": [
        0.0,
        0.0,
        0.0,
        1.0
      ],
      "scale": [
        1.0,
        1.0,
        1.0
      ],
      "billboard": false
    },
    "props": {
      "title": "Org Network",
      "nodes": [
        {
          "id": "n1",
          "label": "Jarvis",
          "group": "core",
          "size": 1.5,
          "color": "#4FC3F7"
        },
        {
          "id": "n2",
          "label": "Voice"
        },
        {
          "id": "n3",
          "label": "Vision"
        }
      ],
      "edges": [
        {
          "source": "n1",
          "target": "n2",
          "weight": 0.8
        },
        {
          "source": "n1",
          "target": "n3",
          "weight": 0.6,
          "label": "sees"
        }
      ],
      "layout": "force",
      "directed": false
    },
    "interactable": true,
    "interactions": [
      "grab",
      "tap",
      "drag",
      "resize",
      "dwell"
    ],
    "ttl_ms": 0
  }
}
```

<a id="data_table"></a>

### `data_table` — Data Table

A scrollable, sortable table of rows and columns.

- **Category:** `data`
- **Prefab id:** `Holo_DataTable`
- **Interactions:** `grab`, `tap`, `resize`, `drag`, `slider`

**Props**

| Prop | Type | Required | Default | Constraints | Description |
| ---- | ---- | :------: | ------- | ----------- | ----------- |
| `title` | string |  |  |  |  |
| `columns` | array&lt;object&gt; | yes |  | minItems 1; items: {key*, label, type} |  |
| `rows` | array&lt;object&gt; | yes |  | items: {} | Each row maps column key -> value (open object; keys match columns). |
| `sortable` | boolean |  | `true` |  |  |
| `page` | integer |  | `1` | min 1 |  |

**Events emitted** (sent back as `client.interaction`)

| Event | Element | Action | Value | Description |
| ----- | ------- | ------ | ----- | ----------- |
| `select_row` | `row` | `tap` | {index} | User tapped a row. |

**Default transform**

```json
{
  "anchor": "world",
  "position": [
    0.0,
    1.4,
    1.1
  ],
  "rotation": [
    0.0,
    0.0,
    0.0,
    1.0
  ],
  "scale": [
    1.0,
    1.0,
    1.0
  ],
  "billboard": false
}
```

**Example `holo.spawn`**

```json
{
  "v": "1.1.0",
  "id": "msg-uuid",
  "type": "holo.spawn",
  "ts": 1733397600000,
  "session": "session-uuid",
  "payload": {
    "object_id": "object-uuid",
    "widget_type": "data_table",
    "transform": {
      "anchor": "world",
      "position": [
        0.0,
        1.4,
        1.1
      ],
      "rotation": [
        0.0,
        0.0,
        0.0,
        1.0
      ],
      "scale": [
        1.0,
        1.0,
        1.0
      ],
      "billboard": false
    },
    "props": {
      "title": "Devices",
      "columns": [
        {
          "key": "name",
          "label": "Name",
          "type": "string"
        },
        {
          "key": "status",
          "label": "Status",
          "type": "string"
        },
        {
          "key": "watts",
          "label": "Watts",
          "type": "number"
        }
      ],
      "rows": [
        {
          "name": "Ceiling Light",
          "status": "on",
          "watts": 12
        },
        {
          "name": "Heater",
          "status": "off",
          "watts": 0
        }
      ],
      "sortable": true,
      "page": 1
    },
    "interactable": true,
    "interactions": [
      "grab",
      "tap",
      "resize",
      "drag",
      "slider"
    ],
    "ttl_ms": 0
  }
}
```

<a id="measuring_tape"></a>

### `measuring_tape` — Measuring Tape

A spatial measurement tool that reports distance, area, or angle between placed points.

- **Category:** `utility`
- **Prefab id:** `Holo_MeasuringTape`
- **Interactions:** `grab`, `tap`, `drag`, `dwell`

**Props**

| Prop | Type | Required | Default | Constraints | Description |
| ---- | ---- | :------: | ------- | ----------- | ----------- |
| `points` | array&lt;array&gt; | yes |  | minItems 2 | World-space points [x, y, z] in meters. |
| `unit` | enum |  | `"m"` | one of: `m`, `cm`, `ft`, `in` |  |
| `distance_m` | number |  |  | min 0 | Computed total distance in meters. |
| `mode` | enum |  | `"distance"` | one of: `distance`, `area`, `angle` |  |
| `label` | string |  |  |  |  |

**Events emitted** (sent back as `client.interaction`)

| Event | Element | Action | Value | Description |
| ----- | ------- | ------ | ----- | ----------- |
| `add_point` | `tape` | `tap` | {position} | User placed a measurement point. |
| `move_point` | `point` | `drag` | {index, position} | User moved a point. |

**Default transform**

```json
{
  "anchor": "world",
  "position": [
    0.0,
    1.0,
    0.8
  ],
  "rotation": [
    0.0,
    0.0,
    0.0,
    1.0
  ],
  "scale": [
    1.0,
    1.0,
    1.0
  ],
  "billboard": false
}
```

**Example `holo.spawn`**

```json
{
  "v": "1.1.0",
  "id": "msg-uuid",
  "type": "holo.spawn",
  "ts": 1733397600000,
  "session": "session-uuid",
  "payload": {
    "object_id": "object-uuid",
    "widget_type": "measuring_tape",
    "transform": {
      "anchor": "world",
      "position": [
        0.0,
        1.0,
        0.8
      ],
      "rotation": [
        0.0,
        0.0,
        0.0,
        1.0
      ],
      "scale": [
        1.0,
        1.0,
        1.0
      ],
      "billboard": false
    },
    "props": {
      "points": [
        [
          0.0,
          1.0,
          0.0
        ],
        [
          1.0,
          1.0,
          0.0
        ]
      ],
      "unit": "m",
      "distance_m": 1.0,
      "mode": "distance",
      "label": "Desk width"
    },
    "interactable": true,
    "interactions": [
      "grab",
      "tap",
      "drag",
      "dwell"
    ],
    "ttl_ms": 0
  }
}
```

<a id="pomodoro"></a>

### `pomodoro` — Pomodoro Timer

A focus/break Pomodoro timer with session tracking and controls.

- **Category:** `productivity`
- **Prefab id:** `Holo_Pomodoro`
- **Interactions:** `grab`, `tap`, `resize`

**Props**

| Prop | Type | Required | Default | Constraints | Description |
| ---- | ---- | :------: | ------- | ----------- | ----------- |
| `phase` | enum | yes |  | one of: `focus`, `short_break`, `long_break`, `idle` |  |
| `remaining_ms` | integer | yes |  | min 0 |  |
| `focus_ms` | integer |  | `1500000` | > 0 |  |
| `break_ms` | integer |  | `300000` | > 0 |  |
| `completed_sessions` | integer |  | `0` | min 0 |  |
| `state` | enum |  | `"idle"` | one of: `running`, `paused`, `idle` |  |
| `task` | string |  |  |  |  |

**Events emitted** (sent back as `client.interaction`)

| Event | Element | Action | Value | Description |
| ----- | ------- | ------ | ----- | ----------- |
| `pause` | `pause_button` | `tap` |  | User paused the timer. |
| `resume` | `resume_button` | `tap` |  | User resumed the timer. |
| `skip` | `skip_button` | `tap` |  | User skipped to the next phase. |
| `reset` | `reset_button` | `tap` |  | User reset the timer. |

**Default transform**

```json
{
  "anchor": "head",
  "position": [
    0.45,
    0.1,
    0.9
  ],
  "rotation": [
    0.0,
    0.0,
    0.0,
    1.0
  ],
  "scale": [
    1.0,
    1.0,
    1.0
  ],
  "billboard": true
}
```

**Example `holo.spawn`**

```json
{
  "v": "1.1.0",
  "id": "msg-uuid",
  "type": "holo.spawn",
  "ts": 1733397600000,
  "session": "session-uuid",
  "payload": {
    "object_id": "object-uuid",
    "widget_type": "pomodoro",
    "transform": {
      "anchor": "head",
      "position": [
        0.45,
        0.1,
        0.9
      ],
      "rotation": [
        0.0,
        0.0,
        0.0,
        1.0
      ],
      "scale": [
        1.0,
        1.0,
        1.0
      ],
      "billboard": true
    },
    "props": {
      "phase": "focus",
      "remaining_ms": 1200000,
      "focus_ms": 1500000,
      "break_ms": 300000,
      "completed_sessions": 2,
      "state": "running",
      "task": "Write report"
    },
    "interactable": true,
    "interactions": [
      "grab",
      "tap",
      "resize"
    ],
    "ttl_ms": 0
  }
}
```

<a id="image_gen_viewer"></a>

### `image_gen_viewer` — AI Image Viewer

Displays AI-generated images with the prompt, generation status, and progress.

- **Category:** `media`
- **Prefab id:** `Holo_ImageGenViewer`
- **Interactions:** `grab`, `tap`, `resize`, `drag`, `dwell`

**Props**

| Prop | Type | Required | Default | Constraints | Description |
| ---- | ---- | :------: | ------- | ----------- | ----------- |
| `prompt` | string | yes |  | minLen 1 |  |
| `status` | enum |  | `"done"` | one of: `queued`, `generating`, `done`, `error` |  |
| `images` | array&lt;object&gt; |  |  | items: {url*, seed} |  |
| `progress` | number |  |  | min 0; max 1 |  |
| `model` | string |  |  |  |  |
| `error` | string |  |  |  |  |

**Events emitted** (sent back as `client.interaction`)

| Event | Element | Action | Value | Description |
| ----- | ------- | ------ | ----- | ----------- |
| `select_image` | `image_tile` | `tap` | {index} | User selected a generated image. |

**Default transform**

```json
{
  "anchor": "world",
  "position": [
    0.0,
    1.4,
    1.1
  ],
  "rotation": [
    0.0,
    0.0,
    0.0,
    1.0
  ],
  "scale": [
    1.0,
    1.0,
    1.0
  ],
  "billboard": true
}
```

**Example `holo.spawn`**

```json
{
  "v": "1.1.0",
  "id": "msg-uuid",
  "type": "holo.spawn",
  "ts": 1733397600000,
  "session": "session-uuid",
  "payload": {
    "object_id": "object-uuid",
    "widget_type": "image_gen_viewer",
    "transform": {
      "anchor": "world",
      "position": [
        0.0,
        1.4,
        1.1
      ],
      "rotation": [
        0.0,
        0.0,
        0.0,
        1.0
      ],
      "scale": [
        1.0,
        1.0,
        1.0
      ],
      "billboard": true
    },
    "props": {
      "prompt": "a neon city skyline at night, synthwave",
      "status": "done",
      "images": [
        {
          "url": "https://cdn.jarvisvr.app/gen/neon1.png",
          "seed": 42
        }
      ],
      "progress": 1.0,
      "model": "diffusion-xl"
    },
    "interactable": true,
    "interactions": [
      "grab",
      "tap",
      "resize",
      "drag",
      "dwell"
    ],
    "ttl_ms": 0
  }
}
```

<a id="volumetric_globe"></a>

### `volumetric_globe` — Volumetric Globe

An interactive 3D Earth with markers and great-circle arcs.

- **Category:** `data`
- **Prefab id:** `Holo_VolumetricGlobe`
- **Interactions:** `grab`, `tap`, `drag`, `resize`, `dwell`

**Props**

| Prop | Type | Required | Default | Constraints | Description |
| ---- | ---- | :------: | ------- | ----------- | ----------- |
| `style` | enum |  | `"earth"` | one of: `earth`, `night`, `political`, `topographic` |  |
| `markers` | array&lt;object&gt; |  |  | items: {lat*, lon*, label, color} |  |
| `arcs` | array&lt;object&gt; |  |  | items: {from_lat*, from_lon*, to_lat*, to_lon*, color} |  |
| `rotation_speed` | number |  | `0.1` | min 0 |  |
| `auto_rotate` | boolean |  | `true` |  |  |
| `highlight_country` | string |  |  |  | ISO 3166-1 alpha-2/3 country code to highlight. |

**Events emitted** (sent back as `client.interaction`)

| Event | Element | Action | Value | Description |
| ----- | ------- | ------ | ----- | ----------- |
| `select_marker` | `marker` | `tap` | {index} | User tapped a marker. |
| `rotate` | `globe` | `drag` |  | User rotated the globe. |

**Default transform**

```json
{
  "anchor": "world",
  "position": [
    0.0,
    1.2,
    1.2
  ],
  "rotation": [
    0.0,
    0.0,
    0.0,
    1.0
  ],
  "scale": [
    1.0,
    1.0,
    1.0
  ],
  "billboard": false
}
```

**Example `holo.spawn`**

```json
{
  "v": "1.1.0",
  "id": "msg-uuid",
  "type": "holo.spawn",
  "ts": 1733397600000,
  "session": "session-uuid",
  "payload": {
    "object_id": "object-uuid",
    "widget_type": "volumetric_globe",
    "transform": {
      "anchor": "world",
      "position": [
        0.0,
        1.2,
        1.2
      ],
      "rotation": [
        0.0,
        0.0,
        0.0,
        1.0
      ],
      "scale": [
        1.0,
        1.0,
        1.0
      ],
      "billboard": false
    },
    "props": {
      "style": "earth",
      "markers": [
        {
          "lat": 35.68,
          "lon": 139.69,
          "label": "Tokyo",
          "color": "#FF5252"
        }
      ],
      "arcs": [
        {
          "from_lat": 35.68,
          "from_lon": 139.69,
          "to_lat": 40.71,
          "to_lon": -74.0,
          "color": "#4FC3F7"
        }
      ],
      "rotation_speed": 0.2,
      "auto_rotate": true
    },
    "interactable": true,
    "interactions": [
      "grab",
      "tap",
      "drag",
      "resize",
      "dwell"
    ],
    "ttl_ms": 0
  }
}
```

<a id="system_launcher"></a>

### `system_launcher` — System Launcher

An app/widget launcher grid for opening JarvisVR apps and tools.

- **Category:** `system`
- **Prefab id:** `Holo_SystemLauncher`
- **Interactions:** `grab`, `tap`, `resize`, `drag`, `dwell`

**Props**

| Prop | Type | Required | Default | Constraints | Description |
| ---- | ---- | :------: | ------- | ----------- | ----------- |
| `title` | string |  | `"Apps"` |  |  |
| `apps` | array&lt;object&gt; | yes |  | minItems 1; items: {id*, name*, icon, color, badge} |  |
| `columns` | integer |  | `4` | min 1; max 8 |  |
| `layout` | enum |  | `"grid"` | one of: `grid`, `ring`, `shelf` |  |

**Events emitted** (sent back as `client.interaction`)

| Event | Element | Action | Value | Description |
| ----- | ------- | ------ | ----- | ----------- |
| `launch_app` | `app_tile` | `tap` | {app_id} | User launched an app. |

**Default transform**

```json
{
  "anchor": "head",
  "position": [
    0.0,
    0.0,
    1.0
  ],
  "rotation": [
    0.0,
    0.0,
    0.0,
    1.0
  ],
  "scale": [
    1.0,
    1.0,
    1.0
  ],
  "billboard": true
}
```

**Example `holo.spawn`**

```json
{
  "v": "1.1.0",
  "id": "msg-uuid",
  "type": "holo.spawn",
  "ts": 1733397600000,
  "session": "session-uuid",
  "payload": {
    "object_id": "object-uuid",
    "widget_type": "system_launcher",
    "transform": {
      "anchor": "head",
      "position": [
        0.0,
        0.0,
        1.0
      ],
      "rotation": [
        0.0,
        0.0,
        0.0,
        1.0
      ],
      "scale": [
        1.0,
        1.0,
        1.0
      ],
      "billboard": true
    },
    "props": {
      "title": "Apps",
      "apps": [
        {
          "id": "weather",
          "name": "Weather",
          "icon": "cloud",
          "color": "#4FC3F7"
        },
        {
          "id": "music",
          "name": "Music",
          "icon": "note",
          "badge": 2
        },
        {
          "id": "calendar",
          "name": "Calendar",
          "icon": "calendar"
        }
      ],
      "columns": 4,
      "layout": "grid"
    },
    "interactable": true,
    "interactions": [
      "grab",
      "tap",
      "resize",
      "drag",
      "dwell"
    ],
    "ttl_ms": 0
  }
}
```

<a id="notification_toast"></a>

### `notification_toast` — Notification Toast

A transient notification banner with severity, optional actions, and auto-dismiss.

- **Category:** `system`
- **Prefab id:** `Holo_NotificationToast`
- **Interactions:** `tap`, `dwell`

**Props**

| Prop | Type | Required | Default | Constraints | Description |
| ---- | ---- | :------: | ------- | ----------- | ----------- |
| `title` | string | yes |  | minLen 1 |  |
| `body` | string |  |  |  |  |
| `severity` | enum |  | `"info"` | one of: `info`, `success`, `warning`, `error` |  |
| `icon` | string |  |  |  |  |
| `source` | string |  |  |  | Originating app/service. |
| `actions` | array&lt;object&gt; |  |  | items: {id*, label*} |  |
| `auto_dismiss_ms` | integer |  | `5000` | min 0 | 0 = sticky. |

**Events emitted** (sent back as `client.interaction`)

| Event | Element | Action | Value | Description |
| ----- | ------- | ------ | ----- | ----------- |
| `action` | `action_button` | `tap` | {action_id} | User tapped a notification action. |
| `dismiss` | `close_button` | `tap` |  | User dismissed the notification. |
| `expand` | `toast` | `dwell` |  | User dwelled to expand the notification. |

**Default transform**

```json
{
  "anchor": "head",
  "position": [
    0.0,
    0.45,
    1.0
  ],
  "rotation": [
    0.0,
    0.0,
    0.0,
    1.0
  ],
  "scale": [
    1.0,
    1.0,
    1.0
  ],
  "billboard": true
}
```

**Example `holo.spawn`**

```json
{
  "v": "1.1.0",
  "id": "msg-uuid",
  "type": "holo.spawn",
  "ts": 1733397600000,
  "session": "session-uuid",
  "payload": {
    "object_id": "object-uuid",
    "widget_type": "notification_toast",
    "transform": {
      "anchor": "head",
      "position": [
        0.0,
        0.45,
        1.0
      ],
      "rotation": [
        0.0,
        0.0,
        0.0,
        1.0
      ],
      "scale": [
        1.0,
        1.0,
        1.0
      ],
      "billboard": true
    },
    "props": {
      "title": "Timer finished",
      "body": "Your 5-minute tea timer is done.",
      "severity": "success",
      "icon": "check",
      "source": "Timer",
      "actions": [
        {
          "id": "snooze",
          "label": "Snooze"
        }
      ],
      "auto_dismiss_ms": 5000
    },
    "interactable": true,
    "interactions": [
      "tap",
      "dwell"
    ],
    "ttl_ms": 0
  }
}
```

<a id="settings_panel"></a>

### `settings_panel` — Settings Panel

A grouped settings surface with toggles, sliders, selects, and buttons.

- **Category:** `system`
- **Prefab id:** `Holo_SettingsPanel`
- **Interactions:** `grab`, `tap`, `resize`, `toggle`, `slider`, `drag`

**Props**

| Prop | Type | Required | Default | Constraints | Description |
| ---- | ---- | :------: | ------- | ----------- | ----------- |
| `title` | string |  | `"Settings"` |  |  |
| `sections` | array&lt;object&gt; | yes |  | minItems 1; items: {title*, settings*} |  |

**Events emitted** (sent back as `client.interaction`)

| Event | Element | Action | Value | Description |
| ----- | ------- | ------ | ----- | ----------- |
| `set_toggle` | `setting_toggle` | `toggle` | {setting_id, value} | User flipped a toggle setting. |
| `set_slider` | `setting_slider` | `slider` | {setting_id, value} | User changed a slider setting. |
| `activate` | `setting_button` | `tap` | {setting_id} | User activated a button/select setting. |

**Default transform**

```json
{
  "anchor": "world",
  "position": [
    0.0,
    1.4,
    1.0
  ],
  "rotation": [
    0.0,
    0.0,
    0.0,
    1.0
  ],
  "scale": [
    1.0,
    1.0,
    1.0
  ],
  "billboard": true
}
```

**Example `holo.spawn`**

```json
{
  "v": "1.1.0",
  "id": "msg-uuid",
  "type": "holo.spawn",
  "ts": 1733397600000,
  "session": "session-uuid",
  "payload": {
    "object_id": "object-uuid",
    "widget_type": "settings_panel",
    "transform": {
      "anchor": "world",
      "position": [
        0.0,
        1.4,
        1.0
      ],
      "rotation": [
        0.0,
        0.0,
        0.0,
        1.0
      ],
      "scale": [
        1.0,
        1.0,
        1.0
      ],
      "billboard": true
    },
    "props": {
      "title": "Settings",
      "sections": [
        {
          "title": "Display",
          "settings": [
            {
              "id": "brightness",
              "label": "Brightness",
              "type": "slider",
              "value": 80,
              "min": 0,
              "max": 100,
              "unit": "%"
            },
            {
              "id": "passthrough",
              "label": "Passthrough",
              "type": "toggle",
              "value": true
            }
          ]
        },
        {
          "title": "Privacy",
          "settings": [
            {
              "id": "camera",
              "label": "Allow camera",
              "type": "toggle",
              "value": false
            }
          ]
        }
      ]
    },
    "interactable": true,
    "interactions": [
      "grab",
      "tap",
      "resize",
      "toggle",
      "slider",
      "drag"
    ],
    "ttl_ms": 0
  }
}
```

---

_Generated from `holo-tools/registry.json` (42 widgets) and `holo-tools/tools.json` (45 tools) by `holo-tools/scripts/generate_docs.py`._
