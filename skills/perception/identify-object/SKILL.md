---
name: identify-object
description: >-
  Identify a real-world object the user is looking at or pointing to, using the
  latest passthrough vision frame and gaze, then label it in place. Use for
  "what is this?", "what am I holding?", naming an object on a surface, or
  labeling a single thing in the room. Triggers: what is this, what's that,
  identify, name this, what am I holding, this thing.
license: MIT
compatibility: >-
  Requires JarvisVR agent-backend with perception enabled (camera_passthrough;
  eye_tracking improves targeting). Protocol v1.1 §8.
metadata:
  agent: perception-agent
  category: perception
  version: "1.0"
  author: jarvisvr
allowed-tools: identify_object annotate_object draw_bounding_box describe_view
---
# Identify Object

Answer "what is this?" by focusing the most likely target (gaze hit → object in
view), naming it, and spawning a `vision_annotation` callout on the real object.

## Inputs you rely on

- The session **perception buffer**: most recent `perception.vision_frame` and
  `perception.gaze` (hit point / dwell). The backend auto-correlates these with
  the utterance, so you usually don't request a frame yourself.
- If vision is cold, ask the orchestrator/system to warm it with a single
  snapshot: `perception.request{stream:"vision", action:"once", reason:"user
  asked what they're looking at"}` (protocol §8.4).

## Steps

1. **Resolve the target.** Prefer the `perception.gaze.hit_point`; else the
   highest-confidence object in the current frame (`identify_object` does this
   focus selection for you).
2. **Call `identify_object`.** It returns `data.object`, `data.confidence`, and
   an `observation{text, annotations}` plus a `vision_annotation` directive.
3. **Narrate** via `agent.observation` (the spoken/captioned narration) and let
   the annotation render via `holo.spawn`.
4. **Optionally box it** with `draw_bounding_box` when the user wants extent
   ("how big is it?") or there are look-alikes nearby.
5. **Offer a follow-up** in `agent.speech` (set a reminder, look it up, measure).

## Output

`agent.observation` (protocol §8.4):

```json
{ "text": "That's a ceramic coffee mug.", "final": true,
  "annotations": [ { "label": "coffee mug", "position": [0.3,0.8,0.7], "anchor": "world" } ] }
```

The `vision_annotation` hologram (`annotate_object` → `holo.spawn`, props per
holo-tools/registry.json):

```json
{ "widget_type": "vision_annotation",
  "transform": { "anchor": "world", "position": [0.3,0.95,0.7], "billboard": true },
  "props": { "label": "coffee mug", "confidence": 0.78, "detail": "ceramic, ~350 ml",
             "leader_line": true, "target_position": [0.3,0.8,0.7], "color": "#7FE7FF" },
  "interactions": ["tap","grab","dwell"] }
```

When boxing, `draw_bounding_box` → `bounding_box_3d` needs `label` + `size`:

```json
{ "widget_type": "bounding_box_3d",
  "props": { "label": "laptop", "confidence": 0.91, "size": [0.33,0.02,0.23], "color": "#FFB74D" } }
```

## Edge cases

- **Nothing in view / can't identify** → say so plainly ("I don't see anything I
  can identify right now."), spawn no annotation.
- **Low confidence (<0.5)** → hedge ("looks like…") and keep `confidence` honest
  in props so the UI can style uncertainty.
- **Multiple candidates** → identify the gaze target; if no gaze, pick the most
  central/confident and mention there are others (or hand to
  `describe-surroundings`).
- **Privacy** → frames are processed in-memory; after a `once` snapshot, ensure
  the stream is stopped (`perception.request{action:"stop"}`).
- **Remember it** → if the user says "remember this is here", hand to
  `locate-remembered-object`.
