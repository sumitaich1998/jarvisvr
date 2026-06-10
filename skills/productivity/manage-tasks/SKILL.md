---
name: manage-tasks
description: >-
  Maintain a checkable to-do list — add, complete, reprioritize, and review tasks
  — as an interactive hologram. Use for "add a task", "what's on my list?", "mark
  X done", "show my to-dos", or planning the day. Triggers: task, to-do, todo,
  add to my list, mark done, check off, my tasks, what's left.
license: MIT
compatibility: >-
  Requires JarvisVR agent-backend. Task list persists in long-term store.
metadata:
  agent: productivity-agent
  category: productivity
  version: "1.0"
  author: jarvisvr
allowed-tools: show_todo_list
---
# Manage Tasks

Render and maintain a `todo_list` the user can check off by hand. You own the
list's contents; the widget emits toggle/select events you respond to.

## Steps

1. **Load or build the list.** Keep stable `id`s per item so toggles map back.
2. **Apply the change:** add → append an item; complete → set `done:true`;
   reprioritize → set `priority` (`low|medium|high`); remove → drop the item.
3. **Render** with `show_todo_list` (full list, with the current item states).
4. **React to interactions** (`client.interaction`, §5.11) and persist:
   - `toggle_item{item_id, done}` → update that item's `done`, `holo.update`.
   - `select_item{item_id}` → focus/expand or offer actions.
5. **Voice a short status** ("3 tasks, 1 done").

## Output

`todo_list` (props per registry.json):

```json
{ "widget_type": "todo_list",
  "transform": { "anchor": "world", "billboard": true },
  "props": { "title": "Today",
             "items": [
               { "id": "t1", "text": "Review PR #42", "done": false, "priority": "high" },
               { "id": "t2", "text": "Stretch break", "done": true, "priority": "low" },
               { "id": "t3", "text": "Prep flight test", "done": false, "priority": "medium" } ] },
  "interactions": ["tap","grab","resize","toggle","drag"] }
```

Toggle handling (incoming):

```json
{ "object_id": "O_todo", "widget_type": "todo_list", "action": "toggle",
  "element": "item_checkbox", "value": { "item_id": "t1", "done": true } }
```

→ respond with a `holo.update` carrying the updated `items` array.

## Edge cases

- **Empty list** → render with an encouraging empty state and offer to add the
  first task.
- **Vague task** → capture it verbatim; don't over-structure ("buy stuff").
- **Task with a deadline** → also offer `set-reminders`; with a focus block →
  `manage-timers` pomodoro.
- **Reordering** (`drag`) → persist the new order.
- **"Clear completed"** → drop `done:true` items and `holo.update`.
