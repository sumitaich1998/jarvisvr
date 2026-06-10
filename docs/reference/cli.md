# CLI reference — `jarvis-backend`

`jarvis-backend` is the command-line entry point for the
[`agent-backend`](../components/agent-backend.md) — the multi-provider LLM "brain".
It is installed as a console script (`pip install -e agent-backend`) and is
equivalent to `python -m jarvis_backend`.

```
jarvis-backend [COMMAND] [OPTIONS]
```

Source: [`agent-backend/jarvis_backend/__main__.py`](../../agent-backend/jarvis_backend/__main__.py).

| Command | Purpose |
| ------- | ------- |
| [`serve`](#serve-default) | Run the WebSocket server. **This is the default** (running `jarvis-backend` with no command serves). |
| [`setup`](#setup--init) / `init` | Interactive wizard: pick an LLM provider + enter the API key (masked); writes `.env` (`chmod 600`). |
| [`providers`](#providers) | List every supported LLM provider and exit. |

Run `jarvis-backend -h` (or `jarvis-backend <command> -h`) for built-in help.

---

## `serve` (default)

Runs the JarvisVR WebSocket server — the protocol endpoint the Quest 3 client
connects to. Listens on `ws://<host>:<port><ws_path>` (default
`ws://0.0.0.0:8765/jarvis`), plus the parallel `/vision` (binary frames) and
`/audio` paths on the same port.

```bash
jarvis-backend            # serve (default — same as `jarvis-backend serve`)
jarvis-backend serve      # explicit
python -m jarvis_backend  # equivalent
```

**Options:** none. `serve` takes **no flags** — it is configured entirely by
**environment variables** (and `agent-backend/.env`). Host, port, path, provider,
perception, logging, etc. are all `JARVIS_*` vars — see the
[Environment variables reference](./env-vars.md).

```bash
# Examples (configure via env):
JARVIS_PORT=8788 JARVIS_LOG_LEVEL=DEBUG jarvis-backend
JARVIS_LLM=openai OPENAI_API_KEY=sk-… jarvis-backend
```

On start it logs the version, the resolved model and tool list, and a one-line
`config.summary()` (host/port/path, llm, model, vision, perception, registry,
data_dir). Stops cleanly on `Ctrl-C` (`KeyboardInterrupt`). Exit code `0`.

---

## `setup` / `init`

Interactive wizard to connect an LLM provider. Lists every provider, prompts you to
pick one, asks for the **API key with masked, non-echoing input** (`getpass`), then
writes/updates `agent-backend/.env` **atomically** with mode **`0600`**. Idempotent
and re-runnable. `init` is an alias for `setup`.

```bash
jarvis-backend setup                                  # full interactive wizard
jarvis-backend setup --provider openai                # prompts only for OPENAI_API_KEY (masked)
jarvis-backend init                                   # alias
```

The key is **never printed or logged** (only a masked `•••• (N chars)` confirmation),
and `server.settings` can never echo it back. See
[Configuration](../configuration.md) and
[Add an LLM provider](../guides/add-an-llm-provider.md) for the full flow.

### Options

| Flag | Argument | Default | Description |
| ---- | -------- | ------- | ----------- |
| `--provider` | id | *(prompt)* | Provider id, e.g. `openai`, `anthropic`, `gemini`, `groq`, `ollama` (see `jarvis-backend providers`). |
| `--model` | name | provider default | Model name; defaults to the provider's default model. |
| `--base-url` | url | provider default | Custom/local OpenAI-compatible base URL (for `custom`/`ollama`/`lmstudio`/`vllm`/`azure`). |
| `--api-key` | key | *(prompt)* | API key. **Avoid on shared shells** — prefer interactive (masked) entry or an env var. |
| `--env-file` | path | `agent-backend/.env` | Path to the `.env` file to write. |
| `--non-interactive`, `--ci` | — | off | No prompts — for CI/automation (reads the key from `--api-key` or the env). |
| `--yes`, `-y` | — | off | Don't ask to validate; accept defaults. |
| `--validate` | — | off | Validate the key with one tiny live API call. |
| `--no-validate` | — | off | Never attempt validation. |

> If `--validate` and `--no-validate` are both given, `--no-validate` wins (validation
> is forced off). In interactive mode without either flag, the wizard *asks* whether
> to validate (when a key was entered).

### Examples

```bash
# Interactive, validate the key as part of setup:
jarvis-backend setup --provider openai --validate

# Non-interactive (CI) — key from the environment, no prompts, no validation:
jarvis-backend setup --non-interactive --provider openai --api-key "$OPENAI_API_KEY"

# Local OpenAI-compatible server (no key, custom base URL):
jarvis-backend setup --provider ollama --base-url http://localhost:11434/v1

# Write to a non-default env file:
jarvis-backend setup --provider groq --env-file ./prod.env
```

### Exit codes

| Code | Meaning |
| ---- | ------- |
| `0` | Setup completed (config written). |
| `130` | Cancelled with `Ctrl-C`. |

---

## `providers`

Lists every supported LLM provider with its key env var, default model, base URL, and
capabilities (tools/vision), then exits.

```bash
jarvis-backend providers
```

**Options:** none.

Example output (abridged):

```
JarvisVR — supported LLM providers (set JARVIS_LLM=<id>):

  mock         Mock (offline, no API key)
     key_env=(none)   default_model=mock   base_url=-   caps=tools,vision
  openai       OpenAI
     key_env=OPENAI_API_KEY   default_model=gpt-4o-mini   base_url=-   caps=tools,vision
  ollama       Ollama (local)
     key_env=(none)   default_model=llama3.2   base_url=required   caps=tools
  …

Run `jarvis-backend setup` to configure one (it will ask for your API key).
```

Pick one with `JARVIS_LLM=<id>` or `jarvis-backend setup`. The full provider registry
(and how each is reached) is documented in
[Add an LLM provider](../guides/add-an-llm-provider.md).

---

## Notes

- **No command ⇒ `serve`.** `jarvis-backend` with no arguments runs the server.
- **`serve` is env-only.** All server settings are `JARVIS_*` variables (or `.env`),
  not flags — see [env-vars](./env-vars.md). Only `setup` takes flags.
- The wizard reads/writes `agent-backend/.env` by default; override with `--env-file`
  or the `JARVIS_ENV_FILE` env var.

## Related CLIs

- **`jarvis-voice`** — the [voice-service](../components/voice-service.md) CLI:
  `demo | ambient | bridge | say | selftest | devices`. See the
  [voice-service README](../../voice-service/README.md).
- **`make`** targets — repo-root and `infra/` convenience tasks (`install`, `mock`,
  `e2e`, `test`, `up`/`down`). See [Testing](../guides/testing.md) and
  [Deploy](../guides/deploy.md).

## See also

- [Environment variables reference](./env-vars.md) — every `JARVIS_*` + provider key var.
- [Configuration](../configuration.md) · [agent-backend deep-dive](../components/agent-backend.md).
- [Add an LLM provider](../guides/add-an-llm-provider.md).
