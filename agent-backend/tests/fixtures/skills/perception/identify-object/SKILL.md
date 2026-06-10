---
name: identify-object
description: >-
  Identify a real-world object the user is looking at or asking about, using the
  latest passthrough vision frame and gaze. Use for "what is this?", naming
  objects on a desk, or labeling things in the room.
license: MIT
metadata:
  agent: perception-agent
  category: perception
  version: "1.0"
allowed-tools: identify_object look read_text
---

# Identify object

1. Pull the most recent vision frame + gaze hit from the perception buffer.
2. Name the focused object and its salient detail (material, size).
3. Drop a `vision_annotation` on the object and narrate via `agent.observation`.
