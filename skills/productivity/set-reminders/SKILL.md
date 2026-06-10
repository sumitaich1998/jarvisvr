---
name: set-reminders
description: >-
  Set time- or context-based reminders and surface them when due. Use for "remind
  me to…", "at 6pm remind me…", "in 20 minutes remind me…", or "when I get home,
  remind me…". Triggers: remind me, reminder, don't let me forget, at <time>, in
  <duration>, when I <context>.
license: MIT
compatibility: >-
  Requires JarvisVR agent-backend (reminders persist in long-term store).
metadata:
  agent: productivity-agent
  category: productivity
  version: "1.0"
  author: jarvisvr
allowed-tools: set_reminder notify
---
# Set Reminders

Capture *what* to remember and *when*, persist it, and confirm with a reminder
card; when it fires, raise a notification.

## Steps

1. **Extract `text` + timing.** Relative ("in 20 minutes") → `in_seconds`;
   absolute ("at 18:00") → `at`. Context ("when I get home") → store the trigger
   text and let the scene/perception layer fire it.
2. **Call `set_reminder{text, in_seconds?, at?}`.** Persists it and spawns a
   reminder `panel` card.
3. **Confirm** naturally: "I'll remind you to call Mom at 6 PM."
4. **On due** (server scheduler), raise a `notification_toast` via `notify`.

## Output

Confirmation card (`set_reminder` → `panel`):

```json
{ "widget_type": "panel",
  "props": { "title": "Reminder", "body": "Call Mom at 18:00" },
  "interactions": ["grab","tap"] }
```

`agent.speech`: `{ "text": "I'll remind you to call Mom at 6 PM.", "final": true }`

Due notification (`notify` → `notification_toast`):

```json
{ "widget_type": "notification_toast",
  "props": { "title": "Reminder", "body": "Call Mom", "severity": "info", "source": "Reminders",
             "actions": [ { "id": "done", "label": "Done" }, { "id": "snooze", "label": "Snooze 10m" } ],
             "auto_dismiss_ms": 0 } }
```

## Edge cases

- **No time given** → store it as an untimed reminder and say it's a note-to-self,
  or ask once if timing clearly matters.
- **Ambiguous time** ("at 6" — am/pm? today/tomorrow?) → assume the next sensible
  occurrence and state your assumption; only `clarify-intent` if costly.
- **Short countdowns** ("remind me in 2 minutes") → equivalent to a labelled
  countdown; you may use `manage-timers` instead.
- **Recurring** ("every morning") → store recurrence in the text; note that
  recurring scheduling depends on backend support.
- **Snooze** → re-arm with a new `in_seconds`; **Done** → mark complete and stop.
