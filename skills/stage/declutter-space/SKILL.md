---
name: declutter-space
description: >-
  Tidy the user's space by closing, collapsing, or consolidating holograms that
  are stale, duplicated, or in the way. Use for "clean this up", "close
  everything", "too much clutter", "hide these", or auto-tidying before a new
  layout. Triggers: declutter, clean up, close all, hide, dismiss, too many
  windows, clear the space, minimize.
license: MIT
compatibility: >-
  Requires JarvisVR agent-backend stage runtime; emits holo.destroy / holo.update
  / holo.layout (protocol §5.8–5.10).
metadata:
  agent: stage-agent
  category: stage
  version: "1.0"
  author: jarvisvr
allowed-tools: close_hologram update_hologram arrange_holograms
---
# Declutter Space

Reduce visual load: remove what's done, consolidate duplicates, and tuck the rest
into a tidy arrangement — without destroying anything the user still wants.

## Steps

1. **Inventory** live objects: type, age/TTL, whether the user is interacting,
   and duplicates.
2. **Classify each:** *expired/finished* (a completed timer, an old toast) →
   close; *duplicate* (two weather orbs for the same city) → keep one; *idle but
   wanted* → keep, maybe shrink/move; *active/user-grabbed* → leave alone.
3. **Act:**
   - Close with a graceful fade: `close_hologram` → `holo.destroy{fade_ms:300}`.
   - Shrink/relocate keepers: `update_hologram` (scale down, move to periphery).
   - Re-tidy survivors: `arrange_holograms` (e.g. `stack` to one side).
4. **Confirm scope** for destructive bulk actions ("close everything?") before
   wiping the space.

## Output

Close a finished widget (`close_hologram` → `holo.destroy`):

```json
{ "object_id": "O_old_timer", "fade_ms": 300 }
```

Shrink + move a keeper (`update_hologram` → `holo.update`):

```json
{ "object_id": "O_weather_orb",
  "transform": { "anchor": "head", "position": [0.7,0.3,1.0], "scale": [0.7,0.7,0.7], "billboard": true } }
```

Tidy survivors (`arrange_holograms` → `holo.layout`):

```json
{ "arrangement": "stack", "anchor": "world", "spacing": 0.1,
  "objects": ["O_news_feed", "O_todo_list"] }
```

## Edge cases

- **"Close everything"** → confirm first (it's bulk + irreversible), then destroy
  all non-essential objects.
- **Active interaction / grabbed** → never close or move a widget the user is
  touching.
- **Pinned content** (sticky notes, saved annotations) → keep unless explicitly
  asked.
- **Avatar / system widgets** → don't remove Jarvis's presence or critical alerts.
- **Before a new layout** → declutter, then hand to `compose-workspace`.
