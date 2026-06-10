---
name: annotate-reality
description: >-
  Place world-anchored labels, callouts, pins, and boxes onto real objects and
  locations so information sticks to the physical world. Use for labeling things
  in the room, pinning a spot, boxing a detected object, or step-by-step "point at
  the X" guidance. Triggers: label this, pin here, mark that, point to, highlight,
  call out, annotate, put a label on.
license: MIT
compatibility: >-
  Requires JarvisVR agent-backend stage runtime; world anchoring benefits from
  perception/scene data. Perception widgets per PROTOCOL.md §8.5.
metadata:
  agent: stage-agent
  category: stage
  version: "1.0"
  author: jarvisvr
allowed-tools: annotate_object drop_scene_label draw_bounding_box show_text
---
# Annotate Reality

Anchor information to the physical world. The perception-agent decides *what* a
real thing is; you render the spatial label/box/pin in the right place.

## Pick the annotation

| Goal | Widget | Tool |
| ---- | ------ | ---- |
| Name a real object with a callout | `vision_annotation` | `annotate_object` |
| Box a detected object's extent | `bounding_box_3d` | `draw_bounding_box` |
| Drop a pin/marker at a spot | `scene_label` | `drop_scene_label` |
| Free-floating heading/caption | `text_label` | `show_text` |

## Steps

1. **Get the target position** (world meters) from the perception annotation,
   gaze hit point, or a scene surface.
2. **Choose the widget** from the table; keep labels short.
3. **Anchor in `world`** with `billboard:true` so the label faces the user; lift
   the callout slightly above the object (e.g. +0.15 m in Y) with a `leader_line`.
4. **Spawn**, then keep it anchored as the user moves (world anchor handles this).
5. **Clean up** stale annotations via `close_hologram` when no longer relevant.

## Output

`vision_annotation` (`annotate_object`, props per registry.json):

```json
{ "widget_type": "vision_annotation",
  "transform": { "anchor": "world", "position": [0.3,0.95,0.7], "billboard": true },
  "props": { "label": "coffee mug", "confidence": 0.78, "detail": "ceramic, ~350 ml",
             "leader_line": true, "target_position": [0.3,0.8,0.7], "color": "#7FE7FF" },
  "interactions": ["tap","grab","dwell"] }
```

`bounding_box_3d` (`draw_bounding_box`):

```json
{ "widget_type": "bounding_box_3d",
  "props": { "label": "laptop", "confidence": 0.91, "size": [0.33,0.02,0.23], "color": "#FFB74D" } }
```

`scene_label` (`drop_scene_label`):

```json
{ "widget_type": "scene_label",
  "props": { "text": "Keys (last seen here)", "icon": "pin", "color": "#FF5252", "pin": true } }
```

## Edge cases

- **No reliable position** → fall back to a `head`-anchored `text_label` and say
  you couldn't pin it precisely.
- **Many annotations** → cap to the relevant few; over-labeling clutters reality
  (hand to `declutter-space`).
- **Moving target** → annotations are static once placed; re-place if the object
  moves.
- **Confidence honesty** → carry the real `confidence` so the UI can style
  uncertainty.
- **Steps/tour** → sequence pins and advance as the user completes each.
