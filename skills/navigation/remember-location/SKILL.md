---
name: remember-location
description: >-
  Save a named place (parking spot, hotel, "home", a room) and recall or navigate
  back to it later. Use for "remember where I parked", "save this as home", "take
  me back to my seat", or pinning a spot to return to. Triggers: remember where I
  parked, save this place, mark this spot, where did I park, take me back, saved
  places.
license: MIT
compatibility: >-
  Requires JarvisVR agent-backend with spatial memory (and geolocation for
  outdoor places). Protocol v1.1 §8.
metadata:
  agent: navigation-agent
  category: navigation
  version: "1.0"
  author: jarvisvr
allowed-tools: remember_object find_object drop_scene_label show_map
---
# Remember Location

Persist places the user wants to return to, mark them in space and/or on a map,
and recall them on demand. (For finding misplaced *objects* in the room, that's
perception's `locate-remembered-object`; this skill is for *places*.)

## Save a place

1. Resolve position: current head/world position (`client.scene`) for an in-space
   spot, or `{lat, lon}` for an outdoor place.
2. `remember_object{name, position?, anchor?}` stores it in spatial memory and
   drops a marker. Use a clear name ("parking spot", "home", "my seat").
3. Optionally `drop_scene_label` a friendly pin at the spot.
4. Confirm: "Saved this as your parking spot."

`scene_label` pin (`drop_scene_label` → `scene_label`):

```json
{ "widget_type": "scene_label",
  "transform": { "anchor": "world", "billboard": true },
  "props": { "text": "Parking spot", "icon": "pin", "color": "#4FC3F7", "pin": true } }
```

## Recall / return

1. `find_object{name}` → returns the saved position and spawns a marker plus a
   `navigation_arrow` toward it.
2. For an outdoor place, also render `show_map` with a marker.
3. To actively guide there, hand off to `wayfind`.

`agent.observation`:

```json
{ "text": "Your parking spot is about 40 meters back, to your right — I've marked it.",
  "final": true,
  "annotations": [ { "label": "parking spot", "position": [12.0,0.0,-38.0], "anchor": "world" } ] }
```

## Edge cases

- **Name collision** ("home" already saved) → confirm overwrite or keep both with
  distinct names.
- **Not saved** → "I don't have a saved spot for that yet." Offer to save it now.
- **Stale / moved** → note how long ago it was saved; outdoor accuracy depends on
  geolocation.
- **Privacy** → saved places are personal; don't expose them in shared/observed
  contexts without intent.
- **Just show it** vs **guide me** → marker+map for "where is it", `wayfind` for
  "take me there".
