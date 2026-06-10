---
name: manage-climate
description: >-
  Adjust thermostats and climate — set temperature, raise/lower, and manage
  blinds for passive cooling — via a smart home panel. Use for "set it to 21",
  "make it warmer", "what's the thermostat at?", or "close the blinds".
  Triggers: temperature, thermostat, heating, cooling, AC, warmer, cooler,
  degrees, blinds, shades.
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
# Manage Climate

Render and drive `thermostat` (and `blind`) devices on a `smart_home_panel`.
Thermostats carry `temperature_c` and `on`; blinds use `level` (0–100 = position).

## Steps

1. **Resolve scope + intent.** Absolute ("set to 21") vs. relative ("2 degrees
   warmer", computed from current `temperature_c`).
2. **Render/refresh** the panel scoped to climate devices with `show_smart_home`.
3. **Apply & confirm** with `holo.update` and a short `agent.speech`.
4. **React** to slider/toggle controls from the panel.

## Output

`smart_home_panel`:

```json
{ "widget_type": "smart_home_panel",
  "props": { "room": "Bedroom",
             "devices": [
               { "id": "thermo_1", "name": "Thermostat", "type": "thermostat",
                 "state": { "on": true, "temperature_c": 21.5 }, "unit": "C" },
               { "id": "blind_1", "name": "Blinds", "type": "blind", "state": { "level": 100 } } ] },
  "interactions": ["tap","grab","toggle","slider"] }
```

Incoming control:

```json
{ "widget_type": "smart_home_panel", "action": "slider", "element": "device_slider",
  "value": { "device_id": "thermo_1", "level": 22.0 } }
```

→ map to `thermo_1.state.temperature_c = 22.0`, `holo.update`. `agent.speech`:
"Set the bedroom to 22 degrees."

## Edge cases

- **Units** → respect the device `unit` (C/F); convert spoken values to the
  device's unit before applying.
- **Out-of-range target** → clamp to the device's safe range and mention it.
- **"Make it comfortable"** → pick a sensible default (≈21 °C) and state it.
- **Passive cooling** → "it's hot" with no AC → offer blinds + fan if present.
- **Read-only query** ("what's it set to?") → answer from current state, no change.
- **Multi-device comfort routine** → `run-home-scene`.
