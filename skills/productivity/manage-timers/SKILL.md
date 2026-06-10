---
name: manage-timers
description: >-
  Start, stop, and run countdown timers and Pomodoro focus sessions, and react to
  the user's timer controls. Use for "set a 5-minute timer", "cancel the timer",
  "start a pomodoro", egg timers, focus sessions, and pause/resume/reset taps.
  Triggers: timer, countdown, set a timer, cancel timer, pomodoro, focus session,
  remind me in N minutes (short).
license: MIT
compatibility: >-
  Requires JarvisVR agent-backend (server tracks timer state in session.store).
metadata:
  agent: productivity-agent
  category: productivity
  version: "1.0"
  author: jarvisvr
allowed-tools: start_timer stop_timer start_pomodoro
---
# Manage Timers

Own the lifecycle of `timer` and `pomodoro` holograms: create them, cancel them,
and handle the control events they emit.

## Start a countdown

1. Parse the duration to seconds (e.g. "5 minutes" → 300; "an hour and a half" →
   5400).
2. Call `start_timer{duration_seconds, label?}`. The server tracks `ends_at_ms`
   and returns a `timer_ref` plus a `timer` directive.

`timer` props (registry.json; durations in **ms**):

```json
{ "widget_type": "timer",
  "transform": { "anchor": "head", "position": [-0.45,0.1,0.9], "billboard": true },
  "props": { "label": "Tea", "duration_ms": 300000, "remaining_ms": 300000,
             "state": "running", "mode": "countdown" },
  "interactions": ["tap","grab","resize"] }
```

`agent.speech`: `{ "text": "Timer started for 5 minutes.", "final": true }`

## Pomodoro

Call `start_pomodoro{task?}` → a `pomodoro` widget cycling `focus` →
`short_break` → … with `completed_sessions` tracking:

```json
{ "widget_type": "pomodoro",
  "props": { "phase": "focus", "remaining_ms": 1500000, "focus_ms": 1500000,
             "break_ms": 300000, "state": "running", "task": "Write report" } }
```

## Handle controls (`client.interaction`, protocol §5.11)

The widget emits events; react with `holo.update` (or `stop_timer`):

| Event (`name`) | element | Your action |
| -------------- | ------- | ----------- |
| `pause` | `pause_button` | recompute `remaining_ms`, `holo.update` `state:"paused"` |
| `resume` | `resume_button` | set new `ends_at`, `holo.update` `state:"running"` |
| `reset` | `reset_button` | `remaining_ms = duration_ms`, `state:"idle"` |
| `dismiss` | `close_button` | `stop_timer` → `holo.destroy` |

## Completion

When `remaining_ms` hits 0, set `state:"completed"` and fire a
`notification_toast` (via the system/notify path):

```json
{ "widget_type": "notification_toast",
  "props": { "title": "Timer finished", "body": "Your 5-minute tea timer is done.",
             "severity": "success", "source": "Timer", "actions": [ { "id": "snooze", "label": "Snooze" } ] } }
```

## Edge cases

- **No duration given** → `clarify-intent` ("how long?"). Don't default silently.
- **"Cancel the timer" with multiple** → cancel the most recent (`last_timer_ref`)
  or ask which; `stop_timer{timer_ref}` targets a specific one.
- **Very long timers / alarms at a clock time** → that's a `set-reminders` job,
  not a countdown.
- **Stopwatch** → `mode:"stopwatch"` counts up; omit a meaningful `duration_ms`.
