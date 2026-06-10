---
name: control-media-playback
description: >-
  Play, pause, seek, and adjust audio or video, and react to transport controls.
  Use for "play some music", "pause", "skip ahead 30 seconds", "turn it up", or
  "play that video". Triggers: play, pause, resume, stop, skip, seek, rewind,
  volume, louder, quieter, next track, music, video.
license: MIT
compatibility: >-
  Requires JarvisVR agent-backend. Media sources resolve via the configured
  provider; offline uses sample media.
metadata:
  agent: media-agent
  category: media
  version: "1.0"
  author: jarvisvr
allowed-tools: play_media show_music_visualizer
---
# Control Media Playback

Drive a `media_player` (and, for music, an optional `music_visualizer`) and
handle its transport events.

## Steps

1. **Resolve the source.** A named track/video → resolve a `source_url` +
   `media_type` (`audio|video`). "Play music" with no title → a default playlist.
2. **Start with `play_media`.** Spawns a `media_player` (`state:"playing"`).
3. **For music, add ambience** with `show_music_visualizer` (audio-reactive).
4. **Handle controls** (`client.interaction`, §5.11) with `holo.update`:
   - `play_pause` → toggle `state`.
   - `seek{position_ms}` → set `position_ms`.
   - `set_volume{volume}` → set `volume` (0–1).
   - `stop` → `state:"stopped"` or `holo.destroy`.
5. **Map speech to actions:** "turn it up" → `volume += 0.1`; "skip 30s" →
   `position_ms += 30000`.

## Output

`media_player` (`play_media`, props per registry.json):

```json
{ "widget_type": "media_player",
  "transform": { "anchor": "world", "billboard": true },
  "props": { "title": "Lo-fi Beats", "source_url": "https://cdn.jarvisvr.app/audio/lofi.mp3",
             "media_type": "audio", "state": "playing", "position_ms": 0,
             "duration_ms": 180000, "volume": 0.6, "loop": true },
  "interactions": ["tap","grab","resize","slider"] }
```

`music_visualizer` (`show_music_visualizer`):

```json
{ "widget_type": "music_visualizer",
  "props": { "track": "Lo-fi Beats", "artist": "Chillhop", "style": "bars",
             "amplitude": [0.2,0.6,0.9,0.4,0.7], "color": "#7FE7FF", "playing": true } }
```

## Edge cases

- **Source not found** → say so; offer alternatives, don't fabricate a URL.
- **Nothing playing** ("pause") → no-op with a gentle note.
- **Volume bounds** → clamp to 0.0–1.0.
- **Video vs audio** → video uses a larger `world`-anchored player; keep it out of
  the user's path (defer placement to `stage-agent`).
- **Ambient background loop** (rain, café) → that's `set-soundscape`.
- **Generate cover art / imagery** → `create-image`.
