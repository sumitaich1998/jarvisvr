---
name: compose-workspace
description: >-
  Arrange multiple holograms into a comfortable spatial layout — anchor, space,
  and orient them so nothing overlaps or blocks the user. Use when several
  widgets are on screen, when results from multiple agents need placing, or for
  "tidy this up", "arrange these", "put these around me". Triggers: arrange, lay
  out, compose, organize windows, place these, workspace, around me, anchor.
license: MIT
compatibility: >-
  Requires JarvisVR agent-backend stage runtime; emits holo.layout / holo.update
  (protocol §5.8, §5.10).
metadata:
  agent: stage-agent
  category: stage
  version: "1.0"
  author: jarvisvr
allowed-tools: arrange_holograms update_hologram close_hologram
---
# Compose Workspace

You are the **spatial compositor**. Other agents say *what* to show; you decide
*where* and *how*. Turn a set of `object_id`s into a clean arrangement using
`holo.layout` and per-object `holo.update`.

## Layout model (protocol §5.6, §5.10)

- **Anchors:** `world` (stays put), `head` (follows gaze, good for glanceable
  HUD), `hand_left|hand_right`, `surface` (sits on a table/floor).
- **Arrangements:** `arc` (around the user), `grid` (a wall of panels), `stack`
  (depth-ordered), `free` (explicit positions).
- Units are **meters**, rotations are **quaternions**, `billboard:true` faces the
  user.

## Steps

1. **Inventory** the live objects + their `widget_type`s and sizes.
2. **Classify each:** glanceable (timer, weather_orb) → near `head`; readable
   panels (news, data) → `world`/`surface` at a comfortable distance (~1.0–1.4 m);
   maps/models → a `surface`.
3. **Choose an arrangement** for the set; pick spacing (~0.25 m) to avoid overlap.
4. **Emit `holo.layout`** (`arrange_holograms`); nudge individuals with
   `holo.update` transforms as needed.
5. **Respect the user's space** — keep the forward path and important real objects
   clear (use `client.scene.surfaces`).

## Output

`holo.layout` (`arrange_holograms`, protocol §5.10):

```json
{ "arrangement": "arc", "anchor": "head", "spacing": 0.25,
  "objects": ["O_weather_orb", "O_news_feed", "O_timer"] }
```

Per-object nudge (`update_hologram` → `holo.update`):

```json
{ "object_id": "O_news_feed",
  "transform": { "anchor": "world", "position": [0.0,1.4,1.2], "billboard": true } }
```

## Edge cases

- **Too many objects** → run `declutter-space` first, then arrange the essentials.
- **Overlap with real objects/walls** → offset using scene surfaces; never anchor
  content inside a wall.
- **Single object** → just place it at a comfortable default; no layout needed.
- **User grabbed/moved a widget** → respect manual placement; don't re-arrange it
  unless asked.
- **Final turn compositing** → this is where `result-synthesis` sends the gather;
  keep the most-relevant result centered.
