---
name: show-map
description: >-
  Show an interactive 3D map centered on a place, with markers, or a volumetric
  globe for world-scale views. Use for "show me a map of…", "where is…?", "put
  Tokyo on a map", or plotting multiple locations. Triggers: map, show me where,
  on a map, location of, globe, plot these places, where is.
license: MIT
compatibility: >-
  Requires JarvisVR agent-backend. Map tiles/geocoding use the configured
  provider; offline uses sample coordinates.
metadata:
  agent: navigation-agent
  category: navigation
  version: "1.0"
  author: jarvisvr
allowed-tools: show_map show_globe
---
# Show Map

Render a `map_3d` (local/regional) or a `volumetric_globe` (world-scale) centered
on the requested place with optional markers.

## Steps

1. **Geocode the place(s)** to `{lat, lon}` (provider; offline use known
   coordinates).
2. **Pick the widget:** city/region → `map_3d`; multiple far-flung places or
   "the world" → `volumetric_globe` with markers/arcs.
3. **Choose zoom + style** (`streets|satellite|terrain|dark`) to fit the content.
4. **Render** with `show_map` / `show_globe`; the map prefers a `surface` anchor
   so it sits on a table.
5. **React** to `select_marker` / `zoom` / `pan` events.

## Output

`map_3d` (`show_map`, props per registry.json):

```json
{ "widget_type": "map_3d",
  "transform": { "anchor": "surface", "position": [0.0,0.05,0.0] },
  "props": { "center": { "lat": 35.6762, "lon": 139.6503 }, "zoom": 11, "style": "satellite",
             "pitch_deg": 50,
             "markers": [ { "lat": 35.6586, "lon": 139.7454, "label": "Tokyo Tower", "color": "#FF5252" } ] },
  "interactions": ["tap","grab","drag","resize","slider"] }
```

World view (`show_globe` → `volumetric_globe`):

```json
{ "widget_type": "volumetric_globe",
  "props": { "style": "earth",
             "markers": [ { "lat": 35.68, "lon": 139.69, "label": "Tokyo", "color": "#FF5252" } ],
             "arcs": [ { "from_lat": 35.68, "from_lon": 139.69, "to_lat": 40.71, "to_lon": -74.0, "color": "#4FC3F7" } ],
             "auto_rotate": true } }
```

## Edge cases

- **Geocode fails** → ask for a more specific place; don't guess coordinates.
- **Many markers** → cluster or raise zoom-out; keep labels legible.
- **"How do I get there?"** → that's `wayfind`, not just a map.
- **Indoor / room-scale** → maps are for geographic places; use measuring /
  spatial memory for in-room layout.
- **Surface available?** → if no horizontal surface in `client.scene`, fall back
  to a `world`-anchored map in front of the user.
