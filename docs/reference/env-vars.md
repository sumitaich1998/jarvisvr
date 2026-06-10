# Environment variables reference

Every JarvisVR `agent-backend` setting is environment-driven, and **every value has
a safe default** — the server boots with zero configuration and runs fully offline on
the `mock` provider. This page is the exhaustive list.

**Where config comes from** (later wins is *not* the rule — see note): on startup
[`Config.from_env()`](../../agent-backend/jarvis_backend/config.py) loads
`agent-backend/.env`, then the process environment, with **process env taking
precedence** over `.env` (`override=False`). The friendly way to write `.env` is
`jarvis-backend setup`; the annotated template is
[`agent-backend/.env.example`](../../agent-backend/.env.example).

> Booleans accept `1/true/yes/on` (case-insensitive); anything else is false.
> Integers fall back to the default if unparseable.

---

## Server

| Variable | Default | Description |
| -------- | ------- | ----------- |
| `JARVIS_HOST` | `0.0.0.0` | Bind host for the WebSocket server. |
| `JARVIS_PORT` | `8765` | Bind port (serves `/jarvis`, `/vision`, `/audio`). |
| `JARVIS_WS_PATH` | `/jarvis` | Main WebSocket path. |

---

## LLM provider selection

The active provider is chosen by `JARVIS_LLM`; the rest are generic overrides applied
to whichever provider is active. See [Add an LLM provider](../guides/add-an-llm-provider.md)
for how these resolve.

| Variable | Default | Description |
| -------- | ------- | ----------- |
| `JARVIS_LLM` | `mock` | Provider id. One of: `mock`, `openai`, `anthropic`, `gemini`, `vertex`, `azure`, `bedrock`, `mistral`, `cohere`, `groq`, `together`, `openrouter`, `deepseek`, `xai`, `perplexity`, `fireworks`, `ollama`, `lmstudio`, `vllm`, `custom`. |
| `JARVIS_MODEL` | *(provider default)* | Generic model override for the active provider (highest precedence). |
| `JARVIS_LLM_BASE_URL` | *(provider default)* | Generic base URL for custom/self-hosted/OpenAI-compatible endpoints. (`JARVIS_BASE_URL` is also accepted.) |
| `JARVIS_LLM_API_KEY` | — | Generic API-key fallback (used when the provider's conventional key var is unset; handy for `custom`/local). |
| `JARVIS_USE_LITELLM` | `0` | `1` routes **everything** through the LiteLLM universal adapter (needs `pip install -e ".[providers]"`). |
| `JARVIS_OPENAI_MODEL` | `gpt-4o-mini` | OpenAI model (legacy per-provider override). |
| `JARVIS_ANTHROPIC_MODEL` | `claude-3-5-sonnet-latest` | Anthropic model (legacy per-provider override). |

**Model precedence:** `JARVIS_MODEL` → provider-specific (`JARVIS_OPENAI_MODEL` /
`JARVIS_ANTHROPIC_MODEL` / `JARVIS_<ID>_MODEL`) → the registry default.
**Base-URL precedence:** `JARVIS_<ID>_BASE_URL` → `JARVIS_LLM_BASE_URL` →
(`OPENAI_BASE_URL` for OpenAI) → the registry default.
**Key precedence:** the provider's conventional key var → `JARVIS_LLM_API_KEY`.

### Per-provider overrides (pattern)

For any provider id `<ID>` (uppercased), these are read in addition to the generic
overrides above:

| Pattern | Example | Description |
| ------- | ------- | ----------- |
| `JARVIS_<ID>_MODEL` | `JARVIS_GROQ_MODEL=llama-3.3-70b-versatile` | Model for that specific provider. |
| `JARVIS_<ID>_BASE_URL` | `JARVIS_OLLAMA_BASE_URL=http://localhost:11434/v1` | Base URL for that specific provider. |
| `OPENAI_BASE_URL` | `OPENAI_BASE_URL=https://…` | Special-cased base URL for the native OpenAI provider. |

---

## Provider API-key variables

Set **only** the key(s) for the provider you use; leave the rest blank for `mock`. The
"Needs base URL" column flags local/custom providers that also need a base URL.

| Provider (`JARVIS_LLM`) | Key env var | Default model | Reached via | Needs base URL |
| ----------------------- | ----------- | ------------- | ----------- | -------------- |
| `mock` | *(none)* | `mock` | built-in | — |
| `openai` | `OPENAI_API_KEY` | `gpt-4o-mini` | native SDK | no |
| `anthropic` | `ANTHROPIC_API_KEY` | `claude-3-5-sonnet-latest` | native SDK | no |
| `gemini` | `GEMINI_API_KEY` | `gemini-1.5-flash` | OpenAI-compatible | no (default set) |
| `vertex` | *(Google ADC)* | `gemini-1.5-pro` | LiteLLM | no |
| `azure` | `AZURE_API_KEY` | `gpt-4o-mini` | LiteLLM | **yes** |
| `bedrock` | *(AWS creds)* | `anthropic.claude-3-5-sonnet-20240620-v1:0` | LiteLLM | no |
| `mistral` | `MISTRAL_API_KEY` | `mistral-large-latest` | OpenAI-compatible | no (default set) |
| `cohere` | `COHERE_API_KEY` | `command-r-plus` | LiteLLM | no |
| `groq` | `GROQ_API_KEY` | `llama-3.3-70b-versatile` | OpenAI-compatible | no (default set) |
| `together` | `TOGETHER_API_KEY` | `meta-llama/Llama-3.3-70B-Instruct-Turbo` | OpenAI-compatible | no (default set) |
| `openrouter` | `OPENROUTER_API_KEY` | `openrouter/auto` | OpenAI-compatible | no (default set) |
| `deepseek` | `DEEPSEEK_API_KEY` | `deepseek-chat` | OpenAI-compatible | no (default set) |
| `xai` | `XAI_API_KEY` | `grok-2-latest` | OpenAI-compatible | no (default set) |
| `perplexity` | `PERPLEXITY_API_KEY` | `llama-3.1-sonar-large-128k-online` | OpenAI-compatible (no tools) | no (default set) |
| `fireworks` | `FIREWORKS_API_KEY` | `accounts/fireworks/models/llama-v3p3-70b-instruct` | OpenAI-compatible | no (default set) |
| `ollama` | *(none)* | `llama3.2` | OpenAI-compatible | **yes** (`http://localhost:11434/v1`) |
| `lmstudio` | *(none)* | `local-model` | OpenAI-compatible | **yes** (`http://localhost:1234/v1`) |
| `vllm` | *(none)* | `meta-llama/Llama-3.1-8B-Instruct` | OpenAI-compatible | **yes** (`http://localhost:8000/v1`) |
| `custom` | `JARVIS_LLM_API_KEY` (optional) | `gpt-3.5-turbo` | OpenAI-compatible | **yes** |

> Native SDK paths need an extra: `pip install -e ".[openai]"` / `".[anthropic]"`.
> LiteLLM providers need `pip install -e ".[providers]"`. Generic OpenAI-compatible
> providers need **no** extra (plain `httpx`). Run `jarvis-backend providers` for the
> live list.

---

## Perception (v1.1 — sight / hearing / gaze)

| Variable | Default | Description |
| -------- | ------- | ----------- |
| `JARVIS_PERCEPTION` | `1` | Master switch for perception (vision/audio/gaze correlation + tools). `0` disables it. |
| `JARVIS_VISION` | `mock` | Which provider "sees" passthrough frames: `mock` \| `openai` \| `anthropic`. `mock` synthesizes a deterministic scene offline. |
| `JARVIS_PROACTIVE` | `0` | `1` lets Jarvis proactively comment on notable sounds (doorbell, alarm…). Opt-in for privacy. |
| `JARVIS_VISION_FPS` | `2` | Default frames-per-second requested when Jarvis turns the camera on. |
| `JARVIS_VISION_BUFFER` | `8` | How many recent frames to keep in the rolling perception buffer. |

---

## Holograms, tools & memory

| Variable | Default | Description |
| -------- | ------- | ----------- |
| `JARVIS_HOLO_REGISTRY` | `../holo-tools/registry.json` | Path to the canonical widget catalog. If absent, a built-in fallback catalog is used. Relative paths resolve against the repo root. |
| `JARVIS_WEATHER_API_KEY` | — | Optional live weather (OpenWeatherMap) for `get_weather`; without it, deterministic mock data is returned. (`OPENWEATHER_API_KEY` is also accepted.) |
| `JARVIS_DATA_DIR` | `.data` | Directory for long-term / episodic / spatial memory (notes, reminders, seen objects). Relative paths resolve against `agent-backend/`. |
| `JARVIS_ENV_FILE` | `agent-backend/.env` | Where runtime settings changes (`client.settings_update`) are persisted (`chmod 600`). |
| `JARVIS_MAX_STEPS` | `6` | Max plan → tool → observe iterations per user turn (safety bound). |

---

## Settings (v1.1, §5.15)

| Variable | Default | Description |
| -------- | ------- | ----------- |
| `JARVIS_SETTINGS_VALIDATE` | `0` | `1` makes the server best-effort **live-validate** a new API key on `client.settings_update` (off by default so it's offline-safe). |

---

## Logging

| Variable | Default | Description |
| -------- | ------- | ----------- |
| `JARVIS_LOG_LEVEL` | `INFO` | Log verbosity (`DEBUG`, `INFO`, `WARNING`, …). |
| `JARVIS_LOG_JSON` | `0` | `1` emits one-line JSON logs (useful in Docker / log aggregation). |

---

## Protocol-binding & schema (tooling)

Used by the shared-protocol bindings, the mock backend, and the e2e harness — not by
the agent-backend server itself.

| Variable | Default | Description |
| -------- | ------- | ----------- |
| `JARVIS_PROTOCOL_SCHEMA_DIR` | *(upward search)* | Absolute path to `shared-protocol/schema`. Set it if the bindings can't locate the schemas. The `infra/` scripts export it for you. |
| `E2E_STRICT_PROPS` | `0` | `1` makes the e2e harness fail on widget props-schema mismatches (vs warn). |
| `JARVIS_BACKEND_URL` | *(mock)* | Backend ws URL the e2e harness / voice-service connect to, e.g. `ws://127.0.0.1:8765/jarvis`. |

---

## Other components

These belong to sibling services; listed here for completeness.

**voice-service** (`jarvis-voice`) — see the
[voice-service README](../../voice-service/README.md): `JARVIS_BACKEND_URL`,
`WAKE_WORD`, `STT_ENGINE`, `TTS_ENGINE`, plus engine-specific knobs.

**infra compose** — [`infra/.env.example`](../../infra/.env.example) provides
best-effort defaults passed to containers via `env_file` (e.g. `LOG_LEVEL`,
`PROTOCOL_VERSION`, and the `JARVIS_HOST`/`JARVIS_PORT`/`JARVIS_WS_PATH` the backend
reads). To select the backend provider in `infra/.env`, set **`JARVIS_LLM`** (the
agent-backend reads `JARVIS_LLM`, not `LLM_PROVIDER`), plus the relevant key var.

---

## Quick `.env` examples

```bash
# Fully offline (default — no key needed)
JARVIS_LLM=mock

# OpenAI
JARVIS_LLM=openai
OPENAI_API_KEY=sk-…
JARVIS_OPENAI_MODEL=gpt-4o

# Local Ollama (no key, custom base URL)
JARVIS_LLM=ollama
JARVIS_OLLAMA_BASE_URL=http://localhost:11434/v1
JARVIS_MODEL=llama3.2

# Groq, with a real weather API and JSON logs
JARVIS_LLM=groq
GROQ_API_KEY=gsk-…
JARVIS_WEATHER_API_KEY=…
JARVIS_LOG_JSON=1
```

## See also

- [CLI reference](./cli.md) · [Configuration](../configuration.md).
- [Add an LLM provider](../guides/add-an-llm-provider.md) · [Deploy](../guides/deploy.md).
- The annotated [`agent-backend/.env.example`](../../agent-backend/.env.example).
