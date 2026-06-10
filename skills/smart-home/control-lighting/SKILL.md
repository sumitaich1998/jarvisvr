---
name: control-lighting
description: >-
  Control smart lights — on/off, brightness, and grouping by room — via a smart
  home panel. Use for "turn on the lights", "dim the living room to 30%", "lights
  off", or "warm up the bedroom lights". Triggers: lights, lamp, brightness, dim,
  brighten, turn on/off lights, set lights to.
license: MIT
compatibility: >-
  Requires JarvisVR agent-backend with a smart-home integration (mock devices
  offline).
metadata:
  agent: smart-home-agent
  category: smart-home
  version: "1.0"
  author: jarvisvr
allowed-tools: show_smart_home
---
# Control Lighting

Render and drive `light` devices on a `smart_home_panel`. Lights use a boolean
`on` and a 0–100 `level` (brightness).

## Steps

1. **Resolve scope.** Which room/group? Use the named room or the user's current
   room (from `client.scene`). If unclear and it matters, `clarify-intent`.
2. **Compute the target state.** "On" → `on:true`; "dim to 30%" → `level:30`;
   "off" → `on:false`. "Warm/cool" maps to a `color_temp`-style key if the device
   supports it (state allows device-specific keys).
3. **Render/refresh** the panel with `show_smart_home`, scoped to lights.
4. **Apply & confirm** — emit `holo.update` reflecting the new states and a short
   `agent.speech`.
5. **React to manual control** events from the panel.

## Output

`smart_home_panel` (`show_smart_home`, props per registry.json):

```json
{ "widget_type": "smart_home_panel",
  "transform": { "anchor": "world", "billboard": true },
  "props": { "room": "Living Room",
             "devices": [
               { "id": "light_1", "name": "Ceiling Light", "type": "light", "state": { "on": true, "level": 30 } },
               { "id": "light_2", "name": "Lamp", "type": "light", "state": { "on": false, "level": 0 } } ] },
  "interactions": ["tap","grab","toggle","slider"] }
```

Incoming control (`client.interaction`, §5.11):

```json
{ "object_id": "O_home", "widget_type": "smart_home_panel", "action": "slider",
  "element": "device_slider", "value": { "device_id": "light_1", "level": 55 } }
```

→ update `light_1.state.level`, `holo.update`. `agent.speech`: "Living room dimmed
to 30%."

## Edge cases

- **No lights in scope** → say none were found for that room; list known rooms.
- **"All lights"** → include every `light` device across rooms.
- **Brightness on an off light** → setting `level>0` implies `on:true`.
- **Unsupported color/temp** → set what's supported, mention what isn't.
- **Climate / locks** → not this skill: use `manage-climate` / `secure-home`.
- **Whole-mood change** ("movie night") → that's `run-home-scene`.
