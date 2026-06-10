---
name: result-synthesis
description: >-
  Merge the specialists' results into one coherent spoken reply and coordinate
  the final spatial layout, closing out a multi-agent turn. Use after the team's
  sub-tasks finish (or partially fail) to produce a single agent.speech{final}
  and hand compositing to the stage-agent. Triggers: synthesize, summarize the
  results, wrap up, combine answers, final reply, "put it all together".
license: MIT
compatibility: >-
  Requires the JarvisVR agent-backend orchestrator; coordinates stage-agent for
  holo.* layout (protocol v1.2).
metadata:
  agent: jarvis
  category: orchestration
  version: "1.0"
  author: jarvisvr
allowed-tools: arrange_holograms
---
# Result Synthesis

Close the loop on an `orchestration.plan`: gather each agent's result, resolve
conflicts, speak **one** answer, and make sure the holograms they spawned are
arranged comfortably (not piled on top of each other).

## Inputs

- The `plan_id` and the per-agent results (each agent's `data` + the `holo.spawn`
  objects it produced, addressed by `object_id`).
- The final `orchestration.agent_status{state:"done"|"failed"}` for every node.

## Steps

1. **Collect & order results** in the order most useful to the user (usually:
   what they asked first → supporting detail). Use each tool's `data.speech`
   suggestion as raw material, not verbatim.
2. **Reconcile conflicts / dedupe.** If two agents answered overlapping
   questions, keep the higher-confidence / more specific one.
3. **Compose one spoken reply.** Stream long answers as multiple
   `agent.speech{final:false}` and end with a single `agent.speech{final:true}`.
   Keep it conversational; don't read JSON aloud.
4. **Coordinate the layout.** Prefer delegating to the `stage-agent`
   (`compose-workspace`) so it decides anchoring/arrangement. For a quick gather
   you may emit `holo.layout` yourself via `arrange_holograms`.
5. **Mark the turn done** — emit `agent.thinking{stage:"done"}` after the final
   speech.

## Output examples

Spoken synthesis (after perception + research + productivity finished):

```json
{ "text": "That's your coffee mug. Tokyo is 18° and cloudy, and your 5-minute timer is running.",
  "final": true, "emotion": "neutral" }
```

Final layout via the stage compositor (`arrange_holograms` → `holo.layout`,
protocol §5.10):

```json
{ "arrangement": "arc", "anchor": "head", "spacing": 0.25,
  "objects": ["O_vision_annotation", "O_weather_orb", "O_timer"] }
```

## Partial failure

If a node reports `state:"failed"`, synthesize around it honestly — report what
succeeded and name what didn't, without dropping the whole turn:

```json
{ "text": "Tokyo is 18° and cloudy and your timer's set. I couldn't get a clear
  look at the desk object though — want me to try again?", "final": true }
```

## Edge cases

- **Nothing succeeded** → one apologetic `agent.speech{final:true}` + an optional
  `notify` toast; do not spawn data widgets.
- **Too many holograms** → ask `stage-agent` to run `declutter-space` before the
  final arrangement.
- **Barge-in** (`client.barge_in`, §5.14) arrived mid-synthesis → stop streaming
  speech, keep already-spawned holograms, end the turn.
- **Streaming order** → never emit `final:true` until every kept result is voiced.
