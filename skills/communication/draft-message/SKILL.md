---
name: draft-message
description: >-
  Draft a message, email, or reply in the user's voice and show it for review
  before anything is sent. Use for "text Sarah that I'm running late", "draft an
  email to the team", "reply saying yes", or composing a note to someone.
  Triggers: text, message, email, reply, draft, tell them, send a note, write to.
license: MIT
compatibility: >-
  Requires JarvisVR agent-backend. Drafting works offline; actually sending
  requires a configured messaging integration and is user-confirmed.
metadata:
  agent: communication-agent
  category: communication
  version: "1.0"
  author: jarvisvr
allowed-tools: show_panel show_text notify
---
# Draft Message

Compose a clear, appropriately-toned message and present it for the user to
review. **Drafting is safe; sending is a gated action** — never send without an
explicit confirmation tap.

## Steps

1. **Capture intent:** recipient, channel (text/email/chat), key points, and
   desired tone (casual/formal). Infer tone from the relationship if unstated.
2. **Compose** a concise draft in the user's voice. For email include a subject;
   for chat keep it short.
3. **Render the draft** on a `panel` (`show_panel`) with the recipient + body so
   the user can read it back.
4. **Offer to send** via a confirmation `notification_toast` (`notify`) with
   Send / Edit / Cancel. Only a `confirm_send` tap triggers an actual send
   (integration permitting); otherwise it stays a draft to copy.
5. **Revise** on "make it shorter / friendlier" and re-render.

## Output

Draft (`show_panel` → `panel`):

```json
{ "widget_type": "panel",
  "props": { "title": "Draft → Sarah (text)",
             "body": "Hey Sarah — running ~15 min late, be there soon!",
             "sections": [ { "heading": "To", "text": "Sarah" }, { "heading": "Channel", "text": "SMS" } ] },
  "interactions": ["tap","grab","resize"] }
```

Send confirmation (`notify` → `notification_toast`):

```json
{ "widget_type": "notification_toast",
  "props": { "title": "Send this message?", "body": "To Sarah · SMS", "severity": "info",
             "actions": [ { "id": "confirm_send", "label": "Send" },
                          { "id": "edit", "label": "Edit" }, { "id": "cancel", "label": "Cancel" } ],
             "auto_dismiss_ms": 0 } }
```

`agent.speech`: `{ "text": "Here's a draft to Sarah — want me to send it?", "final": true }`

## Edge cases

- **No integration to send** → present the draft and say it's ready to copy/send
  manually; don't claim it was sent.
- **Missing recipient** → ask who (`clarify-intent`).
- **Sensitive content** (money, commitments) → always confirm; reflect the user's
  wording, don't overstate.
- **Wrong tone** → revise on request; default to matching the recipient's
  formality.
- **Long email** → use a `document_viewer` for very long bodies; keep the panel
  for short messages.
