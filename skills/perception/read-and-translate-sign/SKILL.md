---
name: read-and-translate-sign
description: >-
  Read text visible in the passthrough camera (a sign, menu, label, or document)
  and optionally translate it into the user's language. Use for "read this",
  "what does this say", "translate this sign/menu", or OCR of something in view.
  Triggers: read this, what does this say, translate this sign, menu, label,
  OCR, foreign text.
license: MIT
compatibility: >-
  Requires JarvisVR agent-backend with perception enabled (camera_passthrough).
  Protocol v1.1 §8.
metadata:
  agent: perception-agent
  category: perception
  version: "1.0"
  author: jarvisvr
allowed-tools: translate_view read_text translate_text show_translator
---
# Read & Translate Sign

OCR text from the current view, then (if a target language is implied or asked)
translate it, surfacing both on a `translator` panel in `sign` mode.

## Steps

1. **Pick the path:**
   - *Read only* ("what does this say?") → `read_text` → shows a `panel`.
   - *Read + translate* ("translate this sign") → `translate_view` (does OCR +
     translation in one call) → shows a `translator`.
   - *Translate provided text* (not from camera) → `translate_text`.
2. **Determine target language.** Default to the session `locale` from
   `client.hello`; honor explicit "…into French".
3. **Call the tool.** `translate_view` returns `data.source_text`,
   `data.translated`, `data.target_lang`, an `observation`, and a `translator`
   directive.
4. **Narrate** with `agent.observation`/`agent.speech` and render the panel.

## Output

`agent.observation`:

```json
{ "text": "The sign reads: 非常口. In English: Emergency Exit.", "final": true, "annotations": [] }
```

`translator` hologram (`show_translator`, props per registry.json):

```json
{ "widget_type": "translator",
  "transform": { "anchor": "head", "position": [0.0,0.0,1.0], "billboard": true },
  "props": { "source_lang": "auto", "target_lang": "en",
             "source_text": "非常口", "translated_text": "Emergency Exit", "mode": "sign" },
  "interactions": ["tap","grab","resize","toggle"] }
```

Read-only path uses a `panel`:

```json
{ "widget_type": "panel", "props": { "title": "Read", "body": "Gate B12 — Boarding 14:05" } }
```

## Edge cases

- **No legible text** → "I can't make out any text from here — move a little
  closer or steady the view." Spawn nothing.
- **Mixed languages / long passages** → translate the dominant language; for long
  documents suggest `document_viewer` instead of a translator panel.
- **Live two-way conversation** (not a static sign) → hand to
  `communication-agent`'s `live-translate`.
- **Source == target language** → skip translation, just read it back.
- **Numbers/codes** (gate, room, price) → preserve verbatim; don't "translate"
  digits.
- **Privacy** → if you warmed the camera with `perception.request{action:"once"}`,
  stop it when done.
