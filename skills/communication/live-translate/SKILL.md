---
name: live-translate
description: >-
  Translate a live two-way conversation between two languages in real time,
  showing both sides on a translator panel. Use for "translate this
  conversation", "help me talk to them in Spanish", or interpreting back-and-forth
  speech. Triggers: translate conversation, interpret, talk to them in, live
  translation, two-way translate, help me communicate.
license: MIT
compatibility: >-
  Requires JarvisVR agent-backend with ambient audio (perception.audio_scene)
  for live capture. Static signs/menus go to perception read-and-translate-sign.
metadata:
  agent: communication-agent
  category: communication
  version: "1.0"
  author: jarvisvr
allowed-tools: show_translator translate_text
---
# Live Translate

Run a conversational interpreter: capture each speaker's utterance, translate it,
and keep both sides visible on a `translator` in `conversation` mode.

## Steps

1. **Set the language pair.** `source_lang`/`target_lang` (BCP-47; `auto` detects
   the source). See `references/language-codes.md` for codes and notes.
2. **Open the translator** (`show_translator`, `mode:"conversation"`,
   `listening:true`).
3. **Per utterance:** take the `perception.audio_scene.ambient_transcript`
   (`speaker:"other"`) or the user's speech, `translate_text` it, and
   `holo.update` the panel's `source_text`/`translated_text`. Speak the
   translation aloud if the user wants voiced interpreting.
4. **Swap direction** on `swap_languages`; toggle capture on `toggle_listen`.

## Output

`translator` (`show_translator`, props per registry.json):

```json
{ "widget_type": "translator",
  "transform": { "anchor": "head", "position": [0.0,0.0,1.0], "billboard": true },
  "props": { "source_lang": "es", "target_lang": "en", "mode": "conversation",
             "source_text": "¿Dónde está la estación?", "translated_text": "Where is the station?",
             "listening": true },
  "interactions": ["tap","grab","resize","toggle"] }
```

`agent.speech` (voiced interpreting): `{ "text": "They asked: where is the station?", "final": true }`

## Bundled resources

- `references/language-codes.md` — BCP-47 quick reference + detection/RTL notes,
  loaded on demand when resolving an unusual language.

## Edge cases

- **Static sign/menu** (not a conversation) → perception's
  `read-and-translate-sign`.
- **Unknown/auto language** → set `source_lang:"auto"`; confirm if detection is
  low-confidence.
- **Overlapping speakers** → caption the dominant speaker; pair with
  `caption-conversation` for full transcript.
- **Privacy** → ambient capture is user-initiated; stop listening
  (`toggle_listen` off, `perception.request{stream:"ambient_audio", action:"stop"}`)
  when done.
- **Profanity / sensitive content** → translate faithfully and neutrally.
