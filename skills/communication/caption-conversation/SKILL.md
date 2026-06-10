---
name: caption-conversation
description: >-
  Show live, rolling captions of speech Jarvis hears — for accessibility, noisy
  rooms, or meetings — with optional translation. Use for "caption this", "turn on
  subtitles", "caption what they're saying", or "subtitle this meeting".
  Triggers: caption, captions, subtitles, transcribe live, what are they saying,
  accessibility, hard of hearing, meeting transcript.
license: MIT
compatibility: >-
  Requires JarvisVR agent-backend with ambient audio (perception.audio_scene).
  Protocol v1.1 §8.
metadata:
  agent: communication-agent
  category: communication
  version: "1.0"
  author: jarvisvr
allowed-tools: show_live_caption
---
# Caption Conversation

Render a `live_caption` panel that scrolls speech Jarvis hears in real time,
tagged by speaker, optionally translated.

## Steps

1. **Ensure ambient audio is on:** `perception.request{stream:"ambient_audio",
   action:"start", reason:"user asked for live captions"}`.
2. **Open `show_live_caption`** with an empty/seed `lines` array and the right
   `speaker` and `max_lines`.
3. **Per audio window:** append `perception.audio_scene.ambient_transcript` to
   `lines` (newest last), set `speaker` (`user|other|jarvis|unknown`), and
   `holo.update`. Trim to `max_lines`.
4. **Translate (optional):** if a target language is requested, translate each
   line, set `translated:true` and `language` (pair with `live-translate`).
5. **Stop** captions and the audio stream when the user is done.

## Output

`live_caption` (`show_live_caption`, props per registry.json):

```json
{ "widget_type": "live_caption",
  "transform": { "anchor": "head", "position": [0.0,-0.35,1.0], "billboard": true },
  "props": { "lines": [ "Hello there.", "How can I help you today?" ],
             "speaker": "other", "max_lines": 3, "language": "en", "translated": false },
  "interactions": ["grab","tap","resize"] }
```

Update as speech arrives (`holo.update`):

```json
{ "object_id": "O_caption",
  "props": { "lines": [ "How can I help you today?", "I'd like the window seat." ], "speaker": "other" } }
```

## Edge cases

- **Multiple speakers** → tag turns by `speaker`; "unknown" when diarization is
  uncertain.
- **Background noise / no speech** → keep the panel idle; don't caption music or
  ambient sounds (that's perception `identify_sound`).
- **Long sessions** → cap visible `lines` (`max_lines` ≤ 10); the full transcript
  can be saved as a note.
- **Translated captions** → set `translated:true`; consider a two-line layout
  (original + translation) via `live-translate`.
- **Privacy** → captioning others' speech is sensitive; it's user-initiated and
  `perception.state` reflects active capture. Stop promptly when asked.
