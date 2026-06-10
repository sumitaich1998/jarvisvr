---
name: manage-calendar
description: >-
  Show the user's schedule and answer agenda questions — today's events, what's
  next, free time. Use for "what's on my calendar?", "what's my next meeting?",
  "am I free at 3?", or a daily briefing's agenda section. Triggers: calendar,
  agenda, schedule, my day, next meeting, what's next, am I free, events today.
license: MIT
compatibility: >-
  Requires JarvisVR agent-backend. Offline returns deterministic sample events;
  live calendars need a configured integration.
metadata:
  agent: productivity-agent
  category: productivity
  version: "1.0"
  author: jarvisvr
allowed-tools: get_calendar show_calendar
---
# Manage Calendar

Surface the agenda and answer quick schedule questions, rendering a `calendar`
the user can scan and tap.

## Steps

1. **Scope the query.** Day vs. week; "next" vs. "free at 3pm".
2. **Call `get_calendar{date?}`.** Returns `data.events` ({id, title, start, end,
   location}) and a `calendar` directive (agenda view).
3. **Answer the specific question** in `agent.speech` (next event, free/busy),
   then render the `calendar` for the visual.
4. **Drill-down:** a tapped event (`select_event{event_id}`) can expand details or
   start `wayfind` to its `location`.

## Output

`calendar` (`show_calendar` / `get_calendar`, props per registry.json):

```json
{ "widget_type": "calendar",
  "transform": { "anchor": "world", "billboard": true },
  "props": { "title": "Today", "view": "agenda", "date": "2026-06-09",
             "events": [
               { "id": "e1", "title": "Standup", "start": "2026-06-09T09:00:00Z",
                 "end": "2026-06-09T09:15:00Z", "location": "Hangar 3" },
               { "id": "e2", "title": "Design review", "start": "2026-06-09T12:00:00Z",
                 "end": "2026-06-09T13:00:00Z", "location": "Lab" } ] },
  "interactions": ["grab","tap","resize","drag","dwell"] }
```

`agent.speech`:

```json
{ "text": "You have 3 events today. Next up: Standup at 9:00 in Hangar 3.", "final": true }
```

## Edge cases

- **No events** → "Your calendar's clear today." Offer to block focus time
  (`manage-timers`) or add a reminder.
- **Free/busy** ("am I free at 3?") → compute from event windows; answer yes/no
  with the conflicting event if busy.
- **Create/modify events** → only if a write integration is configured; otherwise
  say it's read-only and offer a reminder instead.
- **Travel to an event** → hand the `location` to `navigation-agent` (`wayfind`).
- **Time zones** → render in the user's locale; a multi-zone view is a
  `world_clock` job.
