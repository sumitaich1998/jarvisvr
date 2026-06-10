---
name: wayfind
description: >-
  Give wayfinding directions to a destination and show a navigation arrow with
  distance and ETA. Use for "take me to…", "how do I get to…?", "directions to
  the kitchen", or guiding to a saved place or calendar event location.
  Triggers: take me to, directions, how do I get to, navigate to, guide me, which
  way to, route to.
license: MIT
compatibility: >-
  Requires JarvisVR agent-backend. Live routing uses the configured provider;
  offline returns a deterministic direction + distance.
metadata:
  agent: navigation-agent
  category: navigation
  version: "1.0"
  author: jarvisvr
allowed-tools: navigate_to show_navigation show_map
---
# Wayfind

Point the user toward a destination with a `navigation_arrow` (direction +
distance + ETA), optionally backed by a `map_3d` overview.

## Steps

1. **Resolve the destination.** A place name, a saved location
   (`remember-location`), or a calendar event's `location`.
2. **Call `navigate_to{destination}`.** Returns `data.direction`,
   `data.distance_m`, and a `navigation_arrow` directive.
3. **Speak the cue** ("Head left for about 120 meters") and render the arrow.
4. **Optional overview:** add a `map_3d` with start + destination markers for
   longer routes.
5. **Re-route** on `recenter` taps or when the user clearly went the other way.

## Output

`navigation_arrow` (`show_navigation` / `navigate_to`, props per registry.json):

```json
{ "widget_type": "navigation_arrow",
  "transform": { "anchor": "world" },
  "props": { "target_label": "Kitchen", "direction": [0.0,0.0,1.0],
             "distance_m": 8.5, "eta_min": 1.0, "style": "arrow", "color": "#4FC3F7" },
  "interactions": ["tap","dwell"] }
```

`agent.speech`:

```json
{ "text": "Head straight ahead for about 8 meters to reach the kitchen.", "final": true }
```

## Edge cases

- **Unknown destination** → ask where exactly, or offer saved places.
- **In-room object vs. place** → finding `keys` is perception's
  `locate-remembered-object`; `wayfind` is for places you travel to.
- **Arrived** (`distance_m ≈ 0`) → confirm arrival and `holo.destroy` the arrow.
- **Indoor multi-floor** → mention the floor change; arrow shows local heading.
- **No route** → say so; offer a `map_3d` so the user can navigate manually.
- **Style** → use `beam`/`path` for continuous guidance, `arrow` for a glance.
