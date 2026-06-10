---
name: secure-home
description: >-
  Check and control home security — locks, cameras, and sensors — with explicit
  confirmation for anything that reduces security. Use for "lock the front door",
  "is the door locked?", "show the front camera", or "arm the house". Triggers:
  lock, unlock, door, security, camera, sensor, arm, disarm, is it locked.
license: MIT
compatibility: >-
  Requires JarvisVR agent-backend with a smart-home integration. Security
  actions are user-gated (consent required) per the v1.1 control model.
metadata:
  agent: smart-home-agent
  category: smart-home
  version: "1.0"
  author: jarvisvr
allowed-tools: show_smart_home notify
---
# Secure Home

Manage `lock`, `camera`, and `sensor` devices on a `smart_home_panel`. Security
is sensitive: **locking is safe to do directly; unlocking/disarming always
requires explicit confirmation.**

## Steps

1. **Classify the request.** Read (status), increase-security (lock/arm), or
   reduce-security (unlock/disarm).
2. **Status / lock / arm** → apply directly, render the panel, confirm.
3. **Unlock / disarm** → do **not** act yet: raise a confirmation
   `notification_toast` (`notify`) and only proceed on the user's explicit tap.
4. **Render** the security devices with `show_smart_home`; **react** to controls.

## Output

`smart_home_panel` (security scope):

```json
{ "widget_type": "smart_home_panel",
  "props": { "room": "Entry",
             "devices": [
               { "id": "lock_1", "name": "Front Door", "type": "lock", "state": { "locked": true } },
               { "id": "cam_1", "name": "Front Camera", "type": "camera", "state": { "on": true } },
               { "id": "sensor_1", "name": "Garage Sensor", "type": "sensor", "state": { "on": true } } ] },
  "interactions": ["tap","grab","toggle"] }
```

Confirmation gate before unlocking (`notify` → `notification_toast`):

```json
{ "widget_type": "notification_toast",
  "props": { "title": "Unlock front door?", "body": "This will unlock the front door.",
             "severity": "warning", "source": "Security",
             "actions": [ { "id": "confirm_unlock", "label": "Unlock" }, { "id": "cancel", "label": "Cancel" } ],
             "auto_dismiss_ms": 0 } }
```

Only a `client.interaction{value:{action_id:"confirm_unlock"}}` performs the
unlock (`holo.update` `locked:false`).

## Edge cases

- **Unlock without confirmation** → never. Re-prompt if the tap times out.
- **Status query** → answer from state, no change ("The front door is locked.").
- **Camera view** → a live `camera` feed beyond status overlaps perception's
  `vision_feed`; here just report on/off unless a stream integration exists.
- **"Arm the house"** → set sensors/cameras on and lock doors as a secure scene
  (`run-home-scene` with a "leaving" scene).
- **Alarm/sensor tripped** → raise an `error`-severity toast immediately.
