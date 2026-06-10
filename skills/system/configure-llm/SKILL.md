---
name: configure-llm
description: >-
  View and change the active LLM provider, model, and API key, and hot-swap
  between providers from the in-headset settings. Use for "switch to GPT-4o", "use
  a local model", "change the model", "set my API key", or "which model are you?".
  Triggers: model, provider, LLM, switch model, API key, use local, ollama,
  openai, anthropic, change AI.
license: MIT
compatibility: >-
  Requires JarvisVR agent-backend settings service (protocol v1.1 §5.15). API
  keys travel only on client.settings_update; use wss:// in production.
metadata:
  agent: system-agent
  category: system
  version: "1.0"
  author: jarvisvr
allowed-tools: show_settings
---
# Configure LLM

Manage the model that powers Jarvis via the settings protocol (§5.15). The server
stores keys securely and **hot-swaps** the active provider; keys are never echoed
back (`key_set` is a boolean only).

## Steps

1. **Read current config + catalog:** request `client.settings_get{section:"llm"}`
   → `server.settings.llm` (`current` + `providers`).
2. **Render** a `settings_panel` (`show_settings`) with a provider `select`, a
   model `select`, and a key entry/button — reflecting `key_set` and each
   provider's `needs_key` / `needs_base_url` / `capabilities`.
3. **Apply changes** with `client.settings_update` — send only what changed; omit
   `api_key` to keep the existing key, include it to set/replace.
4. **Confirm** from the returned `server.settings` (don't read keys aloud).

## Output

`settings_panel` (`show_settings`, props per registry.json):

```json
{ "widget_type": "settings_panel",
  "props": { "title": "Model",
             "sections": [ { "title": "LLM",
               "settings": [
                 { "id": "provider", "label": "Provider", "type": "select",
                   "value": "openai", "options": ["openai","anthropic","ollama"] },
                 { "id": "model", "label": "Model", "type": "select",
                   "value": "gpt-4o", "options": ["gpt-4o","gpt-4o-mini"] },
                 { "id": "api_key", "label": "API key", "type": "button", "value": "set" } ] } ] },
  "interactions": ["tap","grab","resize","toggle","slider"] }
```

`client.settings_update` (client → server, §5.15):

```json
{ "llm": { "provider": "ollama", "model": "llama3.1", "base_url": "http://localhost:11434" } }
```

`agent.speech`: `{ "text": "Switched to Llama 3.1 running locally.", "final": true }`

## Edge cases

- **Missing key for a key-required provider** → prompt for it; report
  `invalid_key` from `server.error` clearly.
- **Provider unavailable / offline** → `provider_unavailable`; offer the mock or a
  local provider as fallback.
- **Capability mismatch** (e.g. no vision) → warn if the user relies on perception
  with a non-vision model.
- **Never reveal keys** — only `key_set` true/false; redact in speech and UI.
- **Local provider needs base_url** → require it when `needs_base_url` is true.
