---
name: create-image
description: >-
  Generate images from a text prompt and display them with prompt, status, and
  progress. Use for "make an image of…", "generate a picture of…", "imagine…", or
  visualizing a concept/mood. Triggers: generate image, make a picture, draw,
  imagine, create art, render an image, AI image, visualize this.
license: MIT
compatibility: >-
  Requires JarvisVR agent-backend with an image-generation provider configured;
  offline shows queued/placeholder state.
metadata:
  agent: media-agent
  category: media
  version: "1.0"
  author: jarvisvr
allowed-tools: show_generated_image
---
# Create Image

Turn a prompt into one or more images shown in an `image_gen_viewer`, reflecting
the live generation lifecycle (`queued → generating → done`).

## Steps

1. **Refine the prompt.** Keep the user's intent; you may add concise style hints
   ("synthwave, high detail") but don't override their request.
2. **Spawn the viewer** with `show_generated_image` in `queued`/`generating`
   state and a `progress` value.
3. **Stream progress** with `holo.update` as generation advances, then set
   `status:"done"` with the resulting `images`.
4. **Speak** a short confirmation; offer variations or a save.

## Output

`image_gen_viewer` (`show_generated_image`, props per registry.json):

While generating:

```json
{ "widget_type": "image_gen_viewer",
  "transform": { "anchor": "world", "billboard": true },
  "props": { "prompt": "a neon city skyline at night, synthwave",
             "status": "generating", "progress": 0.4, "model": "diffusion-xl" },
  "interactions": ["tap","grab","resize","drag","dwell"] }
```

When done (`holo.update`):

```json
{ "object_id": "O_imggen",
  "props": { "status": "done", "progress": 1.0,
             "images": [ { "url": "https://cdn.jarvisvr.app/gen/neon1.png", "seed": 42 } ] } }
```

`agent.speech`: `{ "text": "Here's your synthwave skyline.", "final": true }`

## Edge cases

- **No provider / generation fails** → set `status:"error"` with an `error`
  message; don't spawn fake image URLs.
- **Unsafe / disallowed prompt** → decline briefly and offer a safe reframe.
- **Multiple variations** → return several `images`; user taps `select_image`.
- **Use as cover art / texture** → hand the URL to `control-media-playback`
  (poster) or a `model_viewer`/`image_board` via the stage.
- **Very slow gen** → keep streaming `progress`; let the user keep talking.
