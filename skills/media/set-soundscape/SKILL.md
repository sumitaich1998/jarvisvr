---
name: set-soundscape
description: >-
  Play looping ambient soundscapes for focus, relaxation, or sleep — rain, café,
  forest, white noise — with an optional audio-reactive visualizer. Use for "play
  some rain sounds", "café ambience", "white noise to focus", or "ocean waves to
  sleep". Triggers: ambience, soundscape, background sounds, rain sounds, white
  noise, focus sounds, calm, nature sounds.
license: MIT
compatibility: >-
  Requires JarvisVR agent-backend. Loops sample/ambient audio; live libraries use
  the configured provider.
metadata:
  agent: media-agent
  category: media
  version: "1.0"
  author: jarvisvr
allowed-tools: play_media show_music_visualizer
---
# Set Soundscape

Create a calm, looping background atmosphere with a low-key visual. Distinct from
`control-media-playback` (foreground tracks) — soundscapes are ambient, looped,
and quiet by default.

## Steps

1. **Map the mood** to a soundscape (rain, café, forest, ocean, white/brown
   noise, fireplace).
2. **Loop it** with `play_media` (`media_type:"audio"`, `loop:true`, gentle
   `volume`). Keep the player unobtrusive.
3. **Add a subtle visual** with `show_music_visualizer` (`style:"wave"` or
   `"particles"`) when the user wants something to look at.
4. **Pair with focus** — offer a Pomodoro (`productivity-agent`) for work
   sessions, or a sleep timer (`manage-timers`) to fade out.
5. **Control** like any media (volume, stop) via the player's events.

## Output

Looping ambience (`play_media` → `media_player`):

```json
{ "widget_type": "media_player",
  "transform": { "anchor": "world", "billboard": true },
  "props": { "title": "Rain", "source_url": "https://cdn.jarvisvr.app/audio/rain.mp3",
             "media_type": "audio", "state": "playing", "volume": 0.4, "loop": true } }
```

Calm visual (`show_music_visualizer`):

```json
{ "widget_type": "music_visualizer",
  "props": { "track": "Rain", "style": "wave", "amplitude": [0.2,0.3,0.25,0.35,0.3],
             "color": "#7FE7FF", "playing": true } }
```

`agent.speech`: `{ "text": "Rain sounds on, nice and low. Want a focus timer with that?", "final": true }`

## Edge cases

- **Too loud by default** → start quiet (≈0.4); soundscapes shouldn't startle.
- **Sleep request** → set a fade-out / stop via a `manage-timers` sleep timer.
- **Layering** → if a foreground track is already playing, ask before stacking
  audio; usually replace rather than mix.
- **Named song, not ambience** → that's `control-media-playback`.
- **Battery/thermal** → a static loop is cheap; drop the visualizer if
  `perception.state.thermal` is elevated.
