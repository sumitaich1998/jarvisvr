---
name: clarify-intent
description: >-
  Ask one targeted clarifying question only when a goal is genuinely ambiguous
  AND that ambiguity blocks planning or routing. Use before task-decomposition
  when a request is under-specified (missing city, which device, which timer) or
  could map to very different plans. Triggers: ambiguous request, "it"/"that"
  with no referent, missing parameter, multiple plausible meanings, "do the
  thing".
license: MIT
compatibility: >-
  Requires the JarvisVR agent-backend orchestrator; surfaces questions via
  agent.speech (and optionally a notification_toast).
metadata:
  agent: jarvis
  category: orchestration
  version: "1.0"
  author: jarvisvr
allowed-tools: notify show_text
---
# Clarify Intent

Jarvis stays out of the user's way: **ask only when blocked.** A good clarifier
unblocks planning with the fewest words; a bad one interrogates the user for
detail you could reasonably assume.

## Decision rule

Ask **only if both** are true:

1. The goal is ambiguous (missing a required parameter, an unresolved referent,
   or two+ materially different interpretations), **and**
2. Guessing wrong is costly or irreversible (spending, unlocking, deleting,
   messaging the wrong person) — i.e. you can't safely pick a default.

Otherwise **assume a sensible default and proceed**, briefly stating the
assumption in the final reply (e.g. default city = current location).

## Steps

1. **Locate the gap.** Name the single missing slot (which room? which timer?
   what budget?).
2. **Offer choices** when the option set is small and known — easier than
   open-ended questions and great for a quick voice/tap answer.
3. **Ask once, narrowly**, via `agent.speech`. Optionally mirror it as a
   `notification_toast` with action buttons (`notify`) for tap selection.
4. **Resolve** the answer (`user.text` / `user.voice_transcript` /
   `client.interaction`), then continue to `task-decomposition` /
   `agent-routing`.

## Examples

Ambiguous (ask): user says "set a timer."

```json
{ "text": "Sure — how long should the timer run?", "final": true }
```

As a tappable toast (`notify` → `notification_toast`):

```json
{ "title": "Which room?", "body": "I can dim the lights — which room?",
  "severity": "info",
  "actions": [ { "id": "living", "label": "Living Room" },
               { "id": "bedroom", "label": "Bedroom" },
               { "id": "all", "label": "Whole home" } ],
  "auto_dismiss_ms": 0 }
```

The tap returns a `client.interaction{action:"tap", value:{action_id:"living"}}`
which resolves the slot.

Not ambiguous (don't ask): "what's the weather?" with a known location → assume
current location, answer, and note the assumption.

## Edge cases

- **Never chain clarifiers.** One question per turn; if still unclear after the
  answer, proceed with best effort and say so.
- **Don't clarify the obvious.** Units, formatting, and arrangement are your job,
  not the user's — pick reasonable defaults.
- **Gated actions always confirm** even when intent is clear (unlock, purchase) —
  that's consent, route it through the owning agent rather than this skill.
- **Perception referents** ("what's *this*?") are usually resolvable from gaze /
  the perception buffer — try perception first; only ask if nothing is in view.
