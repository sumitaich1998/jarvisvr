---
name: measure-space
description: >-
  Measure real-world distances, spans, areas, or angles between points in the
  room and show a measuring tape. Use for "how far is that?", "how wide is this
  desk?", "measure the wall", or "what's the distance between these?". Triggers:
  measure, how far, how wide, how tall, distance between, dimensions, span, area.
license: MIT
compatibility: >-
  Requires JarvisVR agent-backend with perception/scene data for point positions
  (camera/depth improves accuracy). Protocol v1.1 §8.
metadata:
  agent: navigation-agent
  category: navigation
  version: "1.0"
  author: jarvisvr
allowed-tools: measure
---
# Measure Space

Report a spatial measurement and render a `measuring_tape` between the relevant
world points. Points come from detected objects, gaze hits, or user-placed taps.

## Steps

1. **Determine the endpoints.** Two detected objects, two gaze/tap points, or a
   span the user indicates. `measure` will pick two scene points if none given.
2. **Call `measure`.** Returns `data.distance_m`, `from`, `to`, and a
   `measuring_tape` directive (`mode:"distance"`).
3. **Speak the result** with sensible units; render the tape.
4. **Refine interactively:** `add_point` / `move_point` events extend or adjust
   the measurement → recompute and `holo.update`.
5. For `area`/`angle`, set the tape `mode` accordingly with 3+ points.

## Helper script

To compute distance from raw coordinates without a live scene (tests, planning),
use the bundled stdlib helper:

```
python3 scripts/distance.py 0,1,0.5 0,1,1.2          # -> 0.70 m
python3 scripts/distance.py --unit cm 0,1,0 1,1,0    # -> 100.0 cm
```

It mirrors the backend's Euclidean distance so props match what `measure` emits.

## Output

`measuring_tape` (`measure`, props per registry.json):

```json
{ "widget_type": "measuring_tape",
  "transform": { "anchor": "world" },
  "props": { "points": [ [0.0,1.0,0.0], [1.0,1.0,0.0] ], "unit": "m",
             "distance_m": 1.0, "mode": "distance", "label": "Desk width" },
  "interactions": ["grab","tap","drag","dwell"] }
```

`agent.speech`: `{ "text": "That's about 1.0 meter across.", "final": true }`

## Bundled resources

- `scripts/distance.py` — pure-stdlib distance/area helper for `x,y,z` points.

## Edge cases

- **Too few points** → `measure` falls back to a span in front of the user; tell
  the user to look at / tap the two endpoints for accuracy.
- **No depth** → estimates are rougher; say "about" and offer to refine with taps.
- **Unit conversion** → present in the unit the user asked (`m|cm|ft|in`); store
  `distance_m` canonically.
- **Geographic distance** (between cities) → that's `show-map`/`wayfind`, not a
  tape measure.
