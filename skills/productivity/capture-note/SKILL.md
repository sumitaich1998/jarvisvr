---
name: capture-note
description: >-
  Quickly capture a note to long-term memory and show it back, or pin a sticky
  note in space. Use for "note that…", "take a note", "remember that…", "what
  are my notes?", or jotting an idea hands-free. Triggers: note, take a note,
  jot down, remember that, save this, my notes, sticky note.
license: MIT
compatibility: >-
  Requires JarvisVR agent-backend (notes persist in long-term store).
metadata:
  agent: productivity-agent
  category: productivity
  version: "1.0"
  author: jarvisvr
allowed-tools: take_note list_notes show_sticky_note
---
# Capture Note

Frictionless capture: save what the user says, confirm briefly, and show it. Use
a spatial `sticky_note` when they want it pinned somewhere they'll see it.

## Steps

1. **Capture path:**
   - "note that X" / "remember that X" → `take_note{text}` → updates the notes
     `panel`; reply "Noted."
   - "what are my notes?" → `list_notes` → shows the notes `panel`.
   - "put a sticky note here saying X" → `show_sticky_note` → a placeable
     `sticky_note`.
2. **Keep confirmations tiny** so capture stays fast (one word is fine).

## Output

Notes panel (`take_note` / `list_notes` → `panel`):

```json
{ "widget_type": "panel",
  "props": { "title": "Notes", "body": "• Idea: holographic recipe cards\n• Buy oat milk" },
  "interactions": ["grab","tap","resize"] }
```

Sticky note (`show_sticky_note` → `sticky_note`, props per registry.json):

```json
{ "widget_type": "sticky_note",
  "transform": { "anchor": "world", "billboard": true },
  "props": { "text": "Buy milk", "color": "yellow", "pinned": true, "author": "You" },
  "interactions": ["grab","tap","resize","drag"] }
```

`agent.speech`: `{ "text": "Noted.", "final": true }`

## Edge cases

- **Empty note** → ask what to note ("What would you like me to note?").
- **No notes yet** ("what are my notes?") → "You don't have any notes yet."
- **Actionable note** ("buy milk", "finish report") → offer to make it a task
  (`manage-tasks`) or a timed `set-reminders`.
- **Long capture** → store verbatim; render on a scrollable `panel`, not a sticky.
- **Edit/delete** → a tapped sticky (`edit` event) lets the user revise; reflect
  changes with `holo.update`.
