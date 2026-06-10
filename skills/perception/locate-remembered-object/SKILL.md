---
name: locate-remembered-object
description: >-
  Remember where an object is, and later recall its last-seen location with a
  marker and a navigation arrow. Use for "remember where my keys are", "where did
  I leave my phone?", "where are my glasses?", or pinning a spot for later.
  Triggers: where did I leave, where are my, remember where, find my, last seen,
  mark this spot.
license: MIT
compatibility: >-
  Requires JarvisVR agent-backend with episodic/spatial memory; perception
  improves auto-capture of object locations. Protocol v1.1 §8.
metadata:
  agent: perception-agent
  category: perception
  version: "1.0"
  author: jarvisvr
allowed-tools: remember_object find_object drop_scene_label show_navigation
---
# Locate Remembered Object

Two directions: **store** a spatial memory ("remember my keys are here") and
**recall** one ("where did I leave my keys?"). Locations come from explicit user
intent, gaze hit point, or a focused object in the current frame.

## Remember (store)

1. Resolve the position: explicit `position`, else `perception.gaze.hit_point`,
   else the focused object in view.
2. Call `remember_object{name, position?, anchor?}`. It writes to spatial memory
   and drops a `vision_annotation`/`scene_label` marker at the spot.
3. Confirm: "Got it — I'll remember where your keys are. I marked the spot."

Marker (`drop_scene_label` → `scene_label`):

```json
{ "widget_type": "scene_label",
  "transform": { "anchor": "world", "position": [1.2,0.95,0.4], "billboard": true },
  "props": { "text": "Keys", "icon": "pin", "color": "#FF5252", "pin": true } }
```

## Recall (find)

1. Call `find_object{name}`. If found, it returns the position and spawns a
   marker **plus** a `navigation_arrow` pointing to it; if not, it says it hasn't
   seen the item recently.
2. Narrate via `agent.observation`, render the marker + arrow.

`agent.observation` + `navigation_arrow` (`show_navigation`):

```json
{ "text": "Your keys should be right here — I've marked the spot.", "final": true,
  "annotations": [ { "label": "keys", "position": [1.2,0.95,0.4], "anchor": "world" } ] }
```

```json
{ "widget_type": "navigation_arrow",
  "props": { "target_label": "keys", "direction": [0.75,0.0,0.66], "distance_m": 2.4, "style": "arrow" } }
```

## Edge cases

- **Never seen / not remembered** → "I haven't seen your keys recently." Offer to
  start watching ("tell me when you set them down").
- **Stale memory** → mention how long ago it was last seen; offer a fresh look via
  `describe-surroundings`.
- **Ambiguous name** ("my bag" but two are known) → ask which, or list known
  matches (use `clarify-intent`).
- **Position unknown but item known** → confirm you remember it without a marker:
  "I remember your keys, but I didn't note exactly where."
- **Travel, not in-room** → if the destination is a place not an object, hand to
  `navigation-agent` (`wayfind` / `remember-location`).
