---
name: describe-surroundings
description: >-
  Describe the user's surroundings from the passthrough camera — the main objects
  and layout of the space — and label a few of them in place. Use for "what's
  around me?", "describe this room", "what's on my desk?", scene overviews, or
  accessibility narration. Triggers: describe, what's around me, what's here,
  look around, what's on the desk, scan the room.
license: MIT
compatibility: >-
  Requires JarvisVR agent-backend with perception enabled (camera_passthrough).
  Protocol v1.1 §8.
metadata:
  agent: perception-agent
  category: perception
  version: "1.0"
  author: jarvisvr
allowed-tools: describe_view annotate_object show_vision_feed
---
# Describe Surroundings

Give a concise, useful overview of what Jarvis currently sees and pin labels on
the most relevant few objects (the backend caps annotations at ~3 so the view
stays readable).

## Steps

1. **Ensure a fresh frame.** If vision is active the buffer already has one; for a
   cold start request `perception.request{stream:"vision", action:"once",
   reason:"user asked to describe the room"}`.
2. **Call `describe_view`.** Returns `data.speech`, `data.objects` (top labels),
   and an `observation{text, annotations}` plus up to three `vision_annotation`
   directives. It also records what it saw to episodic memory (so
   `locate-remembered-object` can recall it later).
3. **Narrate** the scene with `agent.observation`; render the labels.
4. **Optionally open `show_vision_feed`** ("show me what you see") so the user can
   confirm the camera view with detection overlays.

## Output

`agent.observation` with spatial annotations:

```json
{ "text": "I can see a coffee mug, a laptop, and a notebook on your desk.",
  "final": true,
  "annotations": [
    { "label": "coffee mug", "position": [0.3,0.8,0.7], "anchor": "world" },
    { "label": "laptop", "position": [0.0,0.78,0.65], "anchor": "world" },
    { "label": "notebook", "position": [-0.25,0.79,0.7], "anchor": "world" }
  ] }
```

Each annotation is realized as a `vision_annotation` `holo.spawn`
(`annotate_object`). Optional feed (`show_vision_feed` → `vision_feed`):

```json
{ "widget_type": "vision_feed",
  "props": { "title": "What Jarvis sees", "source": "rgb_center", "show_detections": true, "fps": 2.0 } }
```

## Edge cases

- **Empty / featureless view** → "It's pretty bare from here — I mostly see a wall
  and the floor."
- **Too cluttered** → describe categories ("a desk covered in cables and a few
  mugs") rather than enumerating everything; cap labels at ~3.
- **Specific subset asked** ("just the desk") → describe only objects near the
  named surface from `client.scene.surfaces`.
- **Single object focus** → use `identify-object` instead.
- **Privacy/battery** → stop a `once` stream when finished; honor `perception.state`
  thermal/battery hints by lowering fps.
