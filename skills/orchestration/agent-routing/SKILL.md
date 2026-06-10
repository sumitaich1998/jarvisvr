---
name: agent-routing
description: >-
  Route a single sub-task to the best specialist agent (or sub-agent) by matching
  it against the JarvisVR roster's roles, skill descriptions, and tool sets. Use
  after task-decomposition for each node, or directly for a one-shot request that
  clearly belongs to one specialist. Triggers: "who should handle this", route,
  dispatch, delegate, assign, pick an agent, fan out to sub-agents.
license: MIT
compatibility: >-
  Requires the JarvisVR agent-backend with the specialist roster loaded and
  skills grouped by metadata.agent (protocol v1.2).
metadata:
  agent: jarvis
  category: orchestration
  version: "1.0"
  author: jarvisvr
---
# Agent Routing

Map one sub-task to exactly one owning specialist (or decide to fan it out to
sub-agents). Routing is matching: sub-task intent → role + that role's skill
`description`s (which the loader indexed at startup, ~100 tokens/skill).

## The roster (docs/ORCHESTRATION.md §3)

| Role id | Use it for |
| ------- | ---------- |
| `perception-agent` | Seeing the room: identify objects, read/translate signs, describe surroundings, find remembered things. |
| `research-agent` | Knowledge, web, news, markets. |
| `productivity-agent` | Timers, reminders, notes, tasks, calendar. |
| `smart-home-agent` | Lights, climate, locks/cameras, scenes. |
| `navigation-agent` | Maps, wayfinding, measuring, spatial memory of places. |
| `media-agent` | Music/video playback, generated imagery, soundscapes. |
| `communication-agent` | Live translation, captions, drafting messages. |
| `stage-agent` | Spatial compositor: arrange/anchor/declutter holograms. |
| `system-agent` | Settings, LLM provider, privacy, diagnostics. |

## Steps

1. **Extract the action verb + object** from the sub-task.
2. **Score candidate roles** by matching against each role's skill descriptions
   and `allowed-tools`. Prefer the role whose skill `description` keywords match
   most directly (this is why descriptions carry trigger words).
3. **Pick the single best owner.** Ties → prefer the more specific specialist
   (e.g. `read-and-translate-sign` on `perception-agent` over generic research).
4. **Choose the skill** within that agent and attach it as `skills:[...]` on the
   plan node and `skill` on `orchestration.agent_status`.
5. **Decide on sub-agents** (see below) when the sub-task is naturally N parallel
   items.
6. **Emit `agent.thinking`** with `agent_id`, `role`, and `skill` attributed so
   the client can highlight who's active.

## Routing examples

| Sub-task | Role | Skill |
| -------- | ---- | ----- |
| "what is this mug?" | `perception-agent` | `identify-object` |
| "translate this sign" | `perception-agent` | `read-and-translate-sign` |
| "weather in Tokyo" | `research-agent` | `web-research` |
| "start a 5-min timer" | `productivity-agent` | `manage-timers` |
| "dim the living room" | `smart-home-agent` | `control-lighting` |
| "take me to the kitchen" | `navigation-agent` | `wayfind` |
| "play some lo-fi" | `media-agent` | `control-media-playback` |
| "caption this meeting" | `communication-agent` | `caption-conversation` |
| "tidy these windows" | `stage-agent` | `declutter-space` |
| "switch to a local model" | `system-agent` | `configure-llm` |

## Sub-agent fan-out (protocol §9.2 `orchestration.handoff`)

When a sub-task is "do X across N items" (e.g. summarize 3 sources), the owning
agent delegates to siblings with dotted ids and emits a handoff:

```json
{
  "plan_id": "uuid-v4",
  "from_agent": "a1",
  "to_agent": "a1.1",
  "to_role": "summarizer",
  "level": 2,
  "subtask": "summarize source 1 of 3",
  "reason": "parallel per-source summarization"
}
```

Prefer **parallel siblings** (a1.1, a1.2, a1.3) over deep chains; keep depth ≤ 3.

## Edge cases

- **Multi-role sub-task** → it wasn't atomic; send it back to
  `task-decomposition` to split.
- **No confident match** → route to `research-agent` (general knowledge) as a
  fallback, or `clarify-intent` if the gap is the user's intent, not the agent.
- **Rendering-only sub-task** (arrange/move/hide) → always `stage-agent`; other
  agents describe *what*, the stage decides *where*.
- **Gated capability** (camera, lock, spend) → route normally but mark the node
  so the executing agent requests consent before acting.
