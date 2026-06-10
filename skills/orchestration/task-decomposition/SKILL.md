---
name: task-decomposition
description: >-
  Break a user's goal into a small DAG of sub-tasks for the JarvisVR specialist
  team, then emit it as an orchestration.plan. Use whenever a request needs more
  than one capability or agent, e.g. "what's on my desk and the weather in
  Tokyo, and start a 5-minute timer", multi-step errands, or any goal mixing
  perception, research, productivity, smart-home, navigation, media, comms, or
  stage work. Triggers: plan, decompose, break down, multi-step, "and also",
  "while you're at it", several things at once.
license: MIT
compatibility: >-
  Requires the JarvisVR agent-backend running the Jarvis orchestrator (protocol
  v1.2 orchestration.* messages, see docs/PROTOCOL.md §9).
metadata:
  agent: jarvis
  category: orchestration
  version: "1.0"
  author: jarvisvr
---
# Task Decomposition

You are **Jarvis**, the L0 orchestrator. This skill turns one user goal into a
small, dependency-aware plan that the specialist roster can execute. You never do
domain work here — you only plan and publish the plan as `orchestration.plan`.

## When to use

- Use when the goal needs **two or more** specialists, or one specialist across
  **sequential** steps with dependencies.
- Skip (single dispatch) when the goal is one obvious sub-task for one agent —
  hand straight to `agent-routing` instead.

## Steps

1. **Normalize the goal.** Strip filler, keep intent + entities (cities, device
   names, durations, people). If it is ambiguous *and* blocking, stop and run
   `clarify-intent` first.
2. **Enumerate atomic sub-tasks.** One verb + one object each ("get Tokyo
   weather", "start 5-minute timer", "identify object on desk").
3. **Assign a role** to each sub-task by matching it to the roster in
   `docs/ORCHESTRATION.md §3` (do the actual matching with `agent-routing`).
4. **Wire dependencies.** Mark which sub-tasks are independent (run in parallel)
   vs. which consume another's output (sequence them). Keep the graph shallow.
5. **Allocate agent ids.** `jarvis` is L0; L1 agents are `a1, a2, …`; sub-agents
   use dotted ids (`a1.1`). Keep depth ≤ 3.
6. **Emit `orchestration.plan`** once, up front, then let the dispatcher drive
   `orchestration.agent_status` per agent.

## Output: `orchestration.plan` (protocol §9.2)

For *"what's this on my desk, and the weather in Tokyo? Start a 5-minute timer."*

```json
{
  "plan_id": "uuid-v4",
  "goal": "identify the desk object, show Tokyo weather, start a 5-minute timer",
  "agents": [
    { "agent_id": "jarvis", "role": "orchestrator", "name": "Jarvis", "parent": null, "level": 0 },
    { "agent_id": "a1", "role": "perception-agent", "name": "Perception", "parent": "jarvis",
      "level": 1, "subtask": "identify the object on the desk", "skills": ["identify-object"] },
    { "agent_id": "a2", "role": "research-agent", "name": "Research", "parent": "jarvis",
      "level": 1, "subtask": "get current weather for Tokyo", "skills": ["web-research"] },
    { "agent_id": "a3", "role": "productivity-agent", "name": "Productivity", "parent": "jarvis",
      "level": 1, "subtask": "start a 5-minute timer", "skills": ["manage-timers"] },
    { "agent_id": "a4", "role": "stage-agent", "name": "Stage", "parent": "jarvis",
      "level": 1, "subtask": "lay the results out comfortably", "skills": ["compose-workspace"] }
  ],
  "edges": [
    { "from": "jarvis", "to": "a1" }, { "from": "jarvis", "to": "a2" },
    { "from": "jarvis", "to": "a3" }, { "from": "a1", "to": "a4" },
    { "from": "a2", "to": "a4" }, { "from": "a3", "to": "a4" }
  ]
}
```

`a1`–`a3` are independent and run **in parallel**; `a4` (stage) depends on all
three so it sequences **last**. Emit `agent.thinking{stage:"planning"}` before
the plan.

## Dependency patterns

- **Fan-out / parallel:** independent reads (weather + identify + timer).
- **Pipeline:** `research-agent` → `summarize-source` → `stage-agent present-data`.
- **Gather/synthesize:** always route the final compositing to one
  `stage-agent` node so holograms don't collide (see `result-synthesis`).

## Edge cases

- **Single capability** → don't emit a plan; dispatch one agent directly.
- **Unknown / unsupported sub-task** → drop it from the plan and note it for the
  spoken summary; never invent a role that isn't in the roster.
- **Destructive or gated actions** (unlock door, spend money) → keep them as
  their own node so consent can gate that step (perception/tool actions stay
  user-gated per v1.1).
- **Too many sub-tasks (>6)** → group related ones under one specialist subtask
  rather than spawning a wide, noisy graph.
- **Cyclic dependency** → you mis-modeled it; collapse the cycle into a single
  sequential node.

## Hand-off

Pass each `{agent_id, role, subtask}` to the dispatcher; per-step routing detail
lives in `agent-routing`, and the final spoken/visual merge lives in
`result-synthesis`.
