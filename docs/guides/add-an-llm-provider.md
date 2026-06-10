# Guide: Add (or switch) an LLM provider

JarvisVR's "brain" talks to an LLM behind one small interface, so you can run it on
**effectively any** provider — OpenAI, Anthropic, Gemini, Groq, a local Ollama, a
self-hosted vLLM, or anything OpenAI-compatible — and hot-swap between them. The
default is a deterministic, **offline `mock`** that needs no key.

This guide covers both:

- **Using** an existing provider (pick one, set a key, test it).
- **Adding** a brand-new provider to the registry.

The single source of truth is the provider registry in
[`agent-backend/jarvis_backend/providers.py`](../../agent-backend/jarvis_backend/providers.py).
For every `JARVIS_*` variable mentioned here, see the
[Environment variables reference](../reference/env-vars.md).

---

## How providers are reached (three routes)

Each provider declares a **`kind`** that decides how it reaches a real model:

| `kind` | How it's reached | Extra dependency? | Example providers |
| ------ | ---------------- | ----------------- | ----------------- |
| `native_openai` / `native_anthropic` | First-party SDK | `.[openai]` / `.[anthropic]` (optional) | `openai`, `anthropic` |
| `openai_compatible` | Any OpenAI `/chat/completions` endpoint over plain `httpx` | **none** | `gemini`, `groq`, `openrouter`, `deepseek`, `xai`, `mistral`, `together`, `perplexity`, `fireworks`, `ollama`, `lmstudio`, `vllm`, `custom` |
| `litellm_only` | The **LiteLLM** universal adapter | `.[providers]` (a.k.a. `.[llm]`) | `azure`, `bedrock`, `vertex`, `cohere` |
| `mock` | Built-in deterministic planner | none | `mock` (default) |

Any provider can *also* be forced through LiteLLM with `JARVIS_USE_LITELLM=1`.
[`create_llm()`](../../agent-backend/jarvis_backend/agent/llm.py) builds the right
provider and, if a key/SDK is missing, **logs a warning and falls back to `mock`**
— it never crashes.

Install the optional deps you need:

```bash
cd agent-backend && source .venv/bin/activate
pip install -e ".[openai]"       # native OpenAI SDK
pip install -e ".[anthropic]"    # native Anthropic SDK
pip install -e ".[providers]"    # LiteLLM — unlocks azure/bedrock/vertex/cohere + 100s more
# (generic OpenAI-compatible providers need NO extra — plain httpx)
```

---

## Part A — Use an existing provider

### 1. List what's available

```bash
jarvis-backend providers
```

Prints every provider with its key env var, default model, base URL, and
capabilities. Browse the [supported provider table in the README](../../README.md#-supported-llm-providers).

### 2. Configure it (the wizard)

The friendly path is the install-time wizard — it prompts for the **API key with
masked, non-echoing input** and writes `agent-backend/.env` (`chmod 600`):

```bash
jarvis-backend setup                       # interactive: pick a provider, enter the key
jarvis-backend setup --provider openai     # prompts only for OPENAI_API_KEY (masked)
```

See the [CLI reference](../reference/cli.md#setup--init) for every flag, and the
[Configuration page](../configuration.md) for the full tour.

### 3. …or configure it by hand

Set `JARVIS_LLM=<id>` and the provider's key env var (in `.env` or the environment):

```bash
# Native SDK
JARVIS_LLM=openai     OPENAI_API_KEY=sk-…           python -m jarvis_backend
JARVIS_LLM=anthropic  ANTHROPIC_API_KEY=sk-ant-…    python -m jarvis_backend

# Generic OpenAI-compatible (no extra SDK)
JARVIS_LLM=groq       GROQ_API_KEY=gsk-…            python -m jarvis_backend
JARVIS_LLM=gemini     GEMINI_API_KEY=…              python -m jarvis_backend

# Local OpenAI-compatible server (usually no key — set a base_url)
JARVIS_LLM=ollama     JARVIS_OLLAMA_BASE_URL=http://localhost:11434/v1 python -m jarvis_backend

# Any custom endpoint
JARVIS_LLM=custom     JARVIS_CUSTOM_BASE_URL=https://my-host/v1  JARVIS_LLM_API_KEY=…  python -m jarvis_backend

# LiteLLM-only providers need the extra + their creds
pip install -e ".[providers]"
JARVIS_LLM=bedrock    python -m jarvis_backend     # uses AWS credentials in the environment
```

### Resolution precedence (what wins)

`resolve()` in `providers.py` turns your config + environment into a concrete
provider/model/key/base_url:

- **Key**: the provider's conventional env var (e.g. `OPENAI_API_KEY`,
  `GROQ_API_KEY`) → generic `JARVIS_LLM_API_KEY`.
- **Model**: `JARVIS_MODEL` (generic) → provider-specific (`JARVIS_OPENAI_MODEL` /
  `JARVIS_ANTHROPIC_MODEL` / `JARVIS_<ID>_MODEL`) → the registry default.
- **Base URL**: `JARVIS_<ID>_BASE_URL` → `JARVIS_LLM_BASE_URL` → (`OPENAI_BASE_URL`
  for OpenAI) → the registry default.

### 4. Switch at runtime (in-headset, no restart)

The LLM is **hot-swappable** via the settings protocol
([`PROTOCOL.md` §5.15](../PROTOCOL.md#515-settings--clientsettings_get--clientsettings_update--serversettings-v11)):
the Quest 3 Settings panel sends `client.settings_update{ llm:{ provider, model,
base_url?, api_key? } }`, the server persists it (same `chmod 600` `.env` writer)
and calls `set_llm()` so the **next turn** uses it — no reconnect. The key travels
only on that message, so use `wss://` in production. The server **never echoes the
key back** (`server.settings` reports only a `key_set` boolean).

---

## Part B — Add a new provider to the registry

### If it's OpenAI-compatible (the common case)

Most new providers expose an OpenAI `/chat/completions` endpoint. Just append a
`ProviderInfo` to `_PROVIDERS` in
[`providers.py`](../../agent-backend/jarvis_backend/providers.py) — **no new client
code needed**, because `GenericOpenAILLM` (plain `httpx`) already handles it:

```python
ProviderInfo(
    id="acme",                                   # JARVIS_LLM=acme
    display_name="Acme AI",
    kind=KIND_OPENAI_COMPATIBLE,
    default_models=["acme-large", "acme-mini"],  # default_models[0] is the default
    env_var="ACME_API_KEY",                      # conventional key var (None = keyless/local)
    default_base_url="https://api.acme.ai/v1",
    litellm_prefix="acme/",                       # used only if routed via LiteLLM
    supports_tools=True,
    supports_vision=False,                        # advertise true only if the model sees images
),
```

That's it — `jarvis-backend providers` lists it, the wizard offers it, and
`JARVIS_LLM=acme ACME_API_KEY=… python -m jarvis_backend` runs it.

### If it needs LiteLLM (cloud creds, bespoke routing)

For providers that aren't a plain OpenAI endpoint (e.g. cloud-credential auth), use
`kind=KIND_LITELLM_ONLY` and a `litellm_prefix`. The wizard sets
`JARVIS_USE_LITELLM=1` for these automatically:

```python
ProviderInfo(
    id="acme_cloud", display_name="Acme Cloud", kind=KIND_LITELLM_ONLY,
    default_models=["acme-cloud-pro"], env_var=None,        # uses ambient cloud creds
    litellm_prefix="acme_cloud/", supports_vision=True,
    notes="Uses Acme Cloud credentials; via LiteLLM.",
),
```

Routing produces a LiteLLM model string of `f"{litellm_prefix}{model}"` (e.g.
`acme_cloud/acme-cloud-pro`). Requires `pip install -e ".[providers]"`.

### If it needs a brand-new native SDK path

Only if the provider isn't OpenAI-compatible **and** you don't want LiteLLM:

1. Add a new routing `kind` constant and a `ProviderInfo` with it.
2. Implement an `LLMProvider` subclass in
   [`agent/llm.py`](../../agent-backend/jarvis_backend/agent/llm.py) (model the
   `OpenAILLM` / `AnthropicLLM` classes: an `async def complete(messages, tools, *,
   images=None) -> LLMResult` that maps tool calls + vision content blocks). Raise
   `LLMUnavailable` if the key/SDK is missing.
3. Wire it into `_build_native()` so `create_llm()` can construct it.
4. Add the SDK as an optional extra in
   [`pyproject.toml`](../../agent-backend/pyproject.toml).

---

## `ProviderInfo` field reference

| Field | Meaning |
| ----- | ------- |
| `id` | The `JARVIS_LLM` value, lowercase. |
| `display_name` | Human label (wizard, `providers` listing, `server.settings`). |
| `kind` | One of the routing kinds above. |
| `default_models` | List; `[0]` is the default model. |
| `env_var` | Conventional API-key env var. `None` ⇒ keyless (local/cloud-cred). |
| `needs_base_url` | If true, the wizard prompts for a base URL (local/custom). |
| `default_base_url` | Used when the user doesn't supply one. |
| `litellm_prefix` | Prepended to the model for LiteLLM routing. |
| `supports_tools` | Tool/function calling available (most true; `perplexity` is false). |
| `supports_vision` | Model can consume image inputs (drives v1.1 vision). |
| `notes` | Shown in the wizard. |

### Capabilities: tools & vision

- **Tools** — when `supports_tools` is true, the agent's tool schemas are sent as
  OpenAI-style `tools` with `tool_choice:"auto"`. A provider with no tool support
  (e.g. Perplexity) just gets a plain chat completion and answers directly.
- **Vision** — when `supports_vision` is true, v1.1 perception attaches passthrough
  image content blocks to the user turn (OpenAI `image_url` / Anthropic `image`
  blocks). The `mock` provider "sees" deterministically offline via the perception
  buffer, so vision Q&A works with no key. See
  [`ARCHITECTURE.md` §7](../../ARCHITECTURE.md#7-multimodal-perception-v11).

Capabilities are surfaced to clients in `server.settings.llm.providers[].capabilities`.

---

## Test your provider with the key wizard

The wizard can make one tiny live call to confirm a key works (it never blocks
setup or logs the key):

```bash
jarvis-backend setup --provider openai --validate              # interactive, validate the key
jarvis-backend setup --provider acme --api-key "$ACME_API_KEY" --validate --non-interactive
```

Under the hood this calls `validate_provider()` in
[`setup_wizard.py`](../../agent-backend/jarvis_backend/setup_wizard.py), which builds
the provider and sends a `"ping"`. If it returns
`fell back to mock (missing key/SDK — install '.[providers]'?)`, you're missing the
extra or the key. Then run the server and confirm the startup log shows your
provider, not `mock`:

```bash
python -m jarvis_backend
# look for:  LLM provider: acme model=acme-large base_url=https://api.acme.ai/v1
```

You can also run the provider unit tests:

```bash
cd agent-backend && pytest tests/test_providers.py
```

---

## Gotchas

- **No key/SDK ⇒ silent mock.** If you see `mock` when you expected a real model,
  the key or extra is missing. The startup log and `jarvis-backend setup --validate`
  tell you which. (See [Troubleshooting](./troubleshooting.md).)
- **LiteLLM-only providers** (`azure`, `bedrock`, `vertex`, `cohere`) require
  `pip install -e ".[providers]"`. Without it they fall back to mock.
- **Local servers** (`ollama`, `lmstudio`, `vllm`) usually need **no key** but **do**
  need a `base_url` — set `JARVIS_<ID>_BASE_URL` or accept the registry default.
- **Generic OpenAI-compatible needs no SDK** — `GenericOpenAILLM` is pure `httpx`.

---

## See also

- [Environment variables reference](../reference/env-vars.md) — every `JARVIS_*` and
  provider key var.
- [CLI reference](../reference/cli.md) — `setup`, `providers`, `serve`.
- [Configuration](../configuration.md) · [agent-backend deep-dive](../components/agent-backend.md).
- [Troubleshooting](./troubleshooting.md) — "provider falls back to mock".
