---
name: run-home-scene
description: >-
  Apply a named multi-device scene that sets several devices at once (lights,
  climate, blinds, locks) to a mood or routine. Use for "movie night", "good
  morning", "I'm leaving", "bedtime", or any one-word routine that should change
  the whole room. Triggers: scene, movie night, good morning, bedtime, I'm
  leaving, focus mode, party, routine, set the mood.
license: MIT
compatibility: >-
  Requires JarvisVR agent-backend with a smart-home integration. Scenes that
  change locks/security require confirmation (see secure-home).
metadata:
  agent: smart-home-agent
  category: smart-home
  version: "1.0"
  author: jarvisvr
allowed-tools: show_smart_home notify
---
# Run Home Scene

Apply a scene = a named bundle of target device states across the room, in one
gesture. Then show the resulting `smart_home_panel` so the user can fine-tune.

## Steps

1. **Resolve the scene** from the request to a definition. Built-in examples live
   in `assets/scenes.example.json` (load and adapt; users may override).
2. **Expand** the scene into concrete device target states (lights `on`/`level`,
   thermostat `temperature_c`, blinds `level`, etc.).
3. **Gate sensitive steps.** If the scene changes a `lock` toward *unlocked* or
   disarms security, confirm via `notify` first (see `secure-home`).
4. **Apply** each device target and **render** the panel reflecting the new
   states with `show_smart_home`; confirm with a short `agent.speech`.

## Scene definition (from `assets/scenes.example.json`)

```json
{ "id": "movie_night", "name": "Movie Night",
  "devices": [
    { "id": "light_1", "type": "light", "state": { "on": true, "level": 15 } },
    { "id": "blind_1", "type": "blind", "state": { "level": 0 } },
    { "id": "thermo_1", "type": "thermostat", "state": { "on": true, "temperature_c": 21 } } ] }
```

## Output

Resulting `smart_home_panel`:

```json
{ "widget_type": "smart_home_panel",
  "props": { "room": "Living Room",
             "devices": [
               { "id": "light_1", "name": "Ceiling Light", "type": "light", "state": { "on": true, "level": 15 } },
               { "id": "blind_1", "name": "Blinds", "type": "blind", "state": { "level": 0 } },
               { "id": "thermo_1", "name": "Thermostat", "type": "thermostat",
                 "state": { "on": true, "temperature_c": 21 }, "unit": "C" } ] } }
```

`agent.speech`: `{ "text": "Movie night — lights down, blinds closed.", "final": true }`

## Bundled resources

- `assets/scenes.example.json` — starter scenes (`movie_night`, `good_morning`,
  `leaving`, `bedtime`) you can clone and tweak per home.

## Edge cases

- **Unknown scene** → offer the closest match or list available scenes.
- **Missing devices** → apply what exists; mention what the scene expected but
  couldn't find.
- **Security in a scene** ("leaving" locks the door & arms sensors) → the
  *increase-security* parts are safe to apply; never auto-unlock.
- **Partial failure** → report which devices didn't respond; leave the rest set.
- **Custom scene creation** → capture the current panel state as a new scene the
  user can name and reuse.
