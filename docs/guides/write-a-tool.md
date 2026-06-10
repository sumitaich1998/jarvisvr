# Guide: Write an agent tool

A **tool** is a named, JSON-schema-typed capability the LLM can call: get the
weather, start a timer, search the web, identify what the user is looking at. Each
tool returns two things:

- **structured `data`** — fed back to the LLM as the observation (and, for the mock
  provider, a `speech` line to say), and
- **holo directives** — what to spawn/update/destroy, which the agent turns into
  `holo.*` protocol messages with server-assigned `object_id`s.

Tools live in
[`agent-backend/jarvis_backend/agent/tools/`](../../agent-backend/jarvis_backend/agent/tools/).
This guide builds a new `flip_coin` tool end-to-end.

> The agent loop (plan → call tools → observe → respond) is in
> [`agent/agent.py`](../../agent-backend/jarvis_backend/agent/agent.py); the tool
> primitives are in [`agent/tools/base.py`](../../agent-backend/jarvis_backend/agent/tools/base.py).

---

## The anatomy of a tool

```python
@dataclass
class Tool:
    name: str                  # what the LLM calls, e.g. "flip_coin"
    description: str           # what it does (the LLM reads this to decide)
    parameters: dict           # JSON Schema for the call arguments
    handler: ToolHandler       # the function that runs it
```

A **handler** has this signature (it may be **sync or async**):

```python
def handler(args: dict[str, Any], ctx: ToolContext) -> ToolResult: ...
async def handler(args, ctx) -> ToolResult: ...   # also fine
```

**`ToolContext`** gives the handler everything it needs at call time:

| Field | What it is |
| ----- | ---------- |
| `ctx.config` | The runtime [`Config`](../../agent-backend/jarvis_backend/config.py) (env-driven). |
| `ctx.session` | Per-connection [`SessionState`](../../agent-backend/jarvis_backend/agent/state.py) (tracked objects, refs, a free-form `store`). |
| `ctx.catalog` | The widget catalog (validate/lookup widget types). |
| `ctx.longterm` | JSON key/value store that persists across sessions (notes, reminders). |
| `ctx.episodic` | Episodic/semantic/spatial memory (events, facts, "where did I leave my keys"). |
| `ctx.perception` | Shortcut to the session's rolling perception buffer (frames, sounds, gaze). |

**`ToolResult`** is what you return:

```python
@dataclass
class ToolResult:
    data: dict          # observation for the LLM; include "speech" for the mock to say
    directives: list    # SpawnDirective / UpdateDirective / DestroyDirective
    error: Optional[str] = None   # a protocol error code if it failed (e.g. "unknown_widget")
```

**Holo directives** describe render intent; the agent resolves `ref`s and assigns
`object_id`s:

| Directive | Fields |
| --------- | ------ |
| `SpawnDirective` | `widget_type`, `props`, `ref?`, `transform?`, `interactions?`, `interactable=True`, `ttl_ms=0` |
| `UpdateDirective` | `ref?` **or** `object_id?`, `props?`, `transform?` |
| `DestroyDirective` | `ref?` **or** `object_id?`, `fade_ms=300` |

`ref` is a **logical handle** (e.g. `"timer:ab12"`). Spawn with a `ref`, then later
turns/interactions can `UpdateDirective(ref=…)` or `DestroyDirective(ref=…)` the same
object. Re-spawning a live `ref` is treated as an update (idempotent).

---

## Step 1 — Write the handler

Add to an existing module (e.g.
[`builtins.py`](../../agent-backend/jarvis_backend/agent/tools/builtins.py)) or a new
one. Our `flip_coin` returns a result and shows it on a `panel`:

```python
import random
from .base import SpawnDirective, ToolContext, ToolResult


def _flip_coin(args: dict, ctx: ToolContext) -> ToolResult:
    # Optional deterministic seed so demos/tests are reproducible.
    seed = args.get("seed")
    rng = random.Random(seed) if seed is not None else random
    result = rng.choice(["Heads", "Tails"])

    return ToolResult(
        data={
            "result": result,
            # The mock LLM speaks this; real LLMs see it as the tool observation.
            "speech": f"It's {result.lower()}.",
        },
        directives=[
            SpawnDirective(
                widget_type="panel",                       # any catalog widget
                props={"title": "Coin flip", "body": result},
                ref="coin_flip",                            # stable handle → updates re-use it
                interactions=["tap", "grab"],
            )
        ],
    )
```

Notes that matter:

- **Always put a `speech` string in `data`.** The mock provider builds its spoken
  reply by concatenating each tool result's `speech`
  ([`MockLLM._summarize_results`](../../agent-backend/jarvis_backend/agent/llm.py)).
  Real providers read the whole `data` blob as the observation.
- **Tools must never crash the loop.** The registry wraps every call and converts an
  exception into a `tool_failed` result — but prefer returning a clean
  `ToolResult(..., error="…")` yourself for expected failures.
- **Validation is automatic.** When the agent applies a `SpawnDirective`, it
  validates `widget_type` + `props` against the catalog and emits a
  `server.error` (`unknown_widget` / `invalid_props`) instead of a bad hologram, so
  keep your `props` conformant to the widget's schema in
  [`registry.json`](../../holo-tools/registry.json).

### Perception tools: emit an observation

If your tool reasons about what Jarvis *sees/hears*, also return an `observation`
block and the agent emits an `agent.observation` (narration + spatial annotations,
[`PROTOCOL.md` §8.4](../PROTOCOL.md#84-payload-schemas)). See
[`perception_tools.py`](../../agent-backend/jarvis_backend/agent/tools/perception_tools.py):

```python
return ToolResult(
    data={
        "speech": "That's a coffee mug.",
        "observation": {"text": "That's a coffee mug.",
                        "annotations": [{"label": "coffee mug", "position": [0.3, 0.8, 0.7], "anchor": "world"}]},
    },
    directives=[SpawnDirective(widget_type="vision_annotation",
                              props={"label": "coffee mug", "confidence": 0.78},
                              transform={"anchor": "world", "position": [0.3, 0.95, 0.7], "billboard": True})],
)
```

---

## Step 2 — Register it

Register the tool on the `ToolRegistry` with a JSON-schema for its arguments. Add a
call inside the relevant `register_*` function (built-ins live in
[`builtins.py`](../../agent-backend/jarvis_backend/agent/tools/builtins.py)'s
`_register_builtin_tools`):

```python
reg.add(
    "flip_coin",
    "Flip a coin and show the result on a panel.",
    {
        "type": "object",
        "properties": {
            "seed": {"type": "integer", "description": "Optional seed for a reproducible flip."}
        },
    },
    _flip_coin,
)
```

The full registry is composed in `build_default_registry()`:

```python
reg = ToolRegistry()
_register_builtin_tools(reg)        # weather, timer, notes, reminders, panel, open_widget…
register_perception_tools(reg)      # vision / OCR / translate / spatial / sound
register_knowledge_tools(reg)       # web_search / news / stocks / calendar / navigate
register_widget_tools(reg, catalog, tools_json_path)   # auto show_<widget> per catalog widget
```

If you're adding a whole new family of tools, write a `register_my_tools(reg)` and
call it here.

---

## Step 3 — Expose it to the LLM

There's nothing extra to do for **real** providers: every registered tool's
`spec()` is passed to `llm.complete(messages, self.registry.specs())` each turn, so
the model can call it (OpenAI/Anthropic/LiteLLM get it as a function/tool schema).

The **mock** provider is different: it's a deterministic keyword planner
([`plan_tool_calls`](../../agent-backend/jarvis_backend/agent/llm.py)) that only
calls a tool if it has a matching rule. To make the offline mock invoke `flip_coin`,
add a rule (guarded by `want("flip_coin")`, which checks the tool is registered):

```python
# in plan_tool_calls(...)
if want("flip_coin") and re.search(r"\bflip a coin\b|\bcoin flip\b|\bheads or tails\b", low):
    calls.append(_new_call("flip_coin", {}))
```

Without a mock rule, the tool still works with real LLMs and via the fallback
`open_widget` path — it just won't be triggered by the offline planner.

---

## Step 4 — Test it

### Unit test (pytest)

Add a case to [`tests/test_tools.py`](../../agent-backend/tests/test_tools.py). A
tool test is simple because handlers are plain functions:

```python
import asyncio
from jarvis_backend.agent.tools import build_default_registry
from jarvis_backend.agent.tools.base import ToolContext
# build a ToolContext from a Config + SessionState (see conftest.py helpers)

def test_flip_coin_is_deterministic_with_seed(tool_ctx):
    reg = build_default_registry(catalog=tool_ctx.catalog)
    res = asyncio.run(reg.run("flip_coin", {"seed": 1}, tool_ctx))
    assert res.ok
    assert res.data["result"] in {"Heads", "Tails"}
    assert res.directives[0].widget_type == "panel"
```

Then:

```bash
cd agent-backend && source .venv/bin/activate
pip install -e ".[dev]"
pytest tests/test_tools.py
```

### End-to-end smoke test (a real socket)

Start the server and drive a turn with the bundled smoke client:

```bash
python -m jarvis_backend &                          # ws://0.0.0.0:8765/jarvis (mock)
python scripts/smoke_client.py "flip a coin"        # if you added the mock rule
```

Or talk to it directly with `websocat`/`wscat`:

```bash
printf '%s\n%s\n' \
  '{"v":"1.1.0","id":"1","type":"client.hello","ts":1,"payload":{"device":"quest3"}}' \
  '{"v":"1.1.0","id":"2","type":"user.text","ts":2,"payload":{"text":"flip a coin"}}' \
  | websocat ws://127.0.0.1:8765/jarvis
# -> agent.thinking{tool_call} -> holo.spawn{panel} -> agent.speech{"It's heads."}
```

You'll see `agent.thinking{stage:"tool_call", tool:"flip_coin"}`, then the
`holo.spawn`, then the streamed `agent.speech`.

---

## How a tool call flows through a turn

```
user.text ─▶ AgentSession.handle_user_text
   └─ llm.complete(messages, registry.specs())     # plan
        └─ tool_calls? for each call:
             emit agent.thinking{tool_call, tool=name}
             registry.run(name, args, ctx)          # YOUR handler
             apply directives → holo.spawn/update/destroy (server assigns object_id)
             data["observation"]? → emit agent.observation
             feed json(data) back to the LLM as the tool result
   └─ no more tool calls → stream agent.speech{final:true}
   └─ ≥2 new holograms? emit holo.layout{arc}; then agent.thinking{done}
```

The loop is bounded by `JARVIS_MAX_STEPS` (default 6) so a tool can't loop forever.

---

## Tips & conventions

- **Return data the LLM can summarize.** Put the key facts in `data` (numbers,
  labels, lists), not just prose — real providers reason over it for the final reply.
- **Use a `ref`** for anything you'll update later (timers, panels, feeds). Store
  server-only metadata you can't put in catalog props in `ctx.session.store` (that's
  how `start_timer` tracks `ends_at_ms`).
- **Persist with `ctx.longterm` / `ctx.episodic`** for notes/reminders/seen-objects;
  they survive reconnects (`JARVIS_DATA_DIR`).
- **Keep it offline-friendly.** Built-in tools return believable mock data with a
  real-API path gated on a key (see `get_weather` → OpenWeatherMap when
  `JARVIS_WEATHER_API_KEY` is set, else deterministic mock). This keeps the whole
  stack demoable with no network.
- **Names + keys are `snake_case`** (tool names, arg keys, prop keys).

---

## See also

- [Add a holographic widget](./add-a-widget.md) — give your tool something new to render.
- [agent-backend deep-dive](../components/agent-backend.md) ·
  [The agent loop](../concepts/agent-loop.md).
- [Protocol reference](../PROTOCOL.md) — `holo.*`, `agent.*`, `agent.observation`.
- [Message index](../reference/message-index.md) — every message type at a glance.
