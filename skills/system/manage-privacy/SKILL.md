---
name: manage-privacy
description: >-
  Control perception privacy — camera, microphone/ambient audio, and gaze — and
  show what's currently being captured. Use for "stop watching", "turn off the
  camera", "stop listening", "are you recording?", or "what can you see/hear?".
  Triggers: privacy, stop watching, turn off camera, stop listening, mute, mic
  off, are you recording, what can you see, disable perception.
license: MIT
compatibility: >-
  Requires JarvisVR agent-backend with perception (protocol v1.1 §8). Capture is
  user-initiated and on-device-gated.
metadata:
  agent: system-agent
  category: system
  version: "1.0"
  author: jarvisvr
allowed-tools: show_settings notify
---
# Manage Privacy

Give the user clear, immediate control over what Jarvis perceives. The user is
always in control: streams are negotiated and `perception.state` reflects exactly
what's active.

## Steps

1. **Report status** from `perception.state` (which of vision / ambient_audio /
   gaze are active, plus thermal/battery).
2. **Apply the change** with `perception.request` (server → client):
   - Stop a stream: `{stream:"vision", action:"stop"}` (or `ambient_audio`,
     `gaze`).
   - Start/snapshot only with a stated `reason` (for consent/UX).
3. **Render a privacy `settings_panel`** (`show_settings`) with toggles mirroring
   each stream's state.
4. **Confirm plainly** ("Camera off. I'm not seeing anything now.") and optionally
   a `notify` toast as a persistent indicator.

## Output

Stop the camera (`perception.request`, §8.4):

```json
{ "stream": "vision", "action": "stop" }
```

Privacy panel (`show_settings` → `settings_panel`):

```json
{ "widget_type": "settings_panel",
  "props": { "title": "Privacy",
             "sections": [ { "title": "Perception",
               "settings": [
                 { "id": "camera", "label": "Camera (vision)", "type": "toggle", "value": false },
                 { "id": "mic", "label": "Ambient audio", "type": "toggle", "value": true },
                 { "id": "gaze", "label": "Eye tracking", "type": "toggle", "value": false } ] } ] } }
```

`agent.speech`: `{ "text": "Camera's off — I'm not seeing anything now.", "final": true }`

## Edge cases

- **"Are you recording?"** → answer truthfully from `perception.state`; servers
  process in-memory and avoid persistence unless the user opted in.
- **Stop everything** → stop vision, ambient_audio, and gaze; confirm all are off.
- **Re-enable for a task** → only with a clear `reason`; a toggle back on should be
  explicit, not silent.
- **Capability not present** → if the device never advertised a stream, say it's
  unavailable rather than toggling.
- **Thermal/battery** → suggest lowering fps or pausing vision when
  `perception.state.thermal` is elevated (overlaps `run-diagnostics`).
