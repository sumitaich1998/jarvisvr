<div align="center">

<img src="./assets/logo.png" alt="JarvisVR" width="120" />

# JarvisVR Documentation

**An AI agentic operating system for mixed reality on the Meta Quest 3.**

</div>

Welcome! This is the documentation hub for **JarvisVR**. Whether you want to run
the demo in five minutes, understand how the agent *sees and hears* your room, or
add your own holographic widget, start here.

> New here? Jump to **[Getting Started](./getting-started.md)** → then skim the
> **[Overview](./concepts/overview.md)**.

---

## 🧭 Documentation map

### Start here
- **[Getting Started](./getting-started.md)** — install, run the offline demo, and have your first conversation with Jarvis.
- **[Installation](./installation.md)** — prerequisites and detailed setup for each OS, plus Quest 3 device setup.
- **[Configuration](./configuration.md)** — environment variables, the LLM key wizard, runtime settings, and provider selection.

### Concepts (how it works)
- **[Overview](./concepts/overview.md)** — the mental model: shell ↔ brain, the protocol, and the perceive→plan→render loop.
- **[Perception: sight, hearing & gaze](./concepts/perception.md)** — color passthrough vision, ambient audio, sound events, gaze, and the privacy model.
- **[The agent loop](./concepts/agent-loop.md)** — planning, tool-calling, memory, and how tool results become holograms.
- **[Multi-agent orchestration](./ORCHESTRATION.md)** — Jarvis + the skill-specialized agent team, the hierarchy, and the Agent Skills (agentskills.io) system.
- **[Holograms & interaction](./concepts/holograms.md)** — the widget system, anchoring, transforms, and hand/gaze interaction.
- **[Voice](./concepts/voice.md)** — wake word, STT, TTS, ambient listening, and barge-in.
- **[Architecture](../ARCHITECTURE.md)** — the system-level design contract.

### Component deep-dives
- **[unity-client](./components/unity-client.md)** — the Quest 3 mixed-reality shell.
- **[agent-backend](./components/agent-backend.md)** — the LLM agent "brain".
- **[voice-service](./components/voice-service.md)** — ears & mouth.
- **[holo-tools](./components/holo-tools.md)** — the 42-widget catalog + tool schemas.
- **[shared-protocol](./components/shared-protocol.md)** — Python/C#/TypeScript bindings.
- **[infra](./components/infra.md)** — Docker, mock backend, and the e2e conformance harness.

### Guides (how to…)
- **[Add a holographic widget](./guides/add-a-widget.md)** — registry → schema → renderer → tool.
- **[Add an LLM provider](./guides/add-an-llm-provider.md)** — native, OpenAI-compatible, or via LiteLLM.
- **[Write an agent tool](./guides/write-a-tool.md)** — give Jarvis a new capability.
- **[Deploy JarvisVR](./guides/deploy.md)** — Docker, TLS/`wss://`, auth, and production hardening.
- **[Testing](./guides/testing.md)** — run every suite + the end-to-end conformance harness.
- **[Troubleshooting](./guides/troubleshooting.md)** — common issues and fixes.

### Reference
- **[Protocol reference](./PROTOCOL.md)** — the v1.1 WebSocket message contract (source of truth).
- **[Widget catalog](./HOLO_TOOLS.md)** — every widget's props, interactions, and tool schema.
- **[CLI reference](./reference/cli.md)** — `jarvis-backend` commands and flags.
- **[Environment variables](./reference/env-vars.md)** — every `JARVIS_*` and provider key var.
- **[Message index](./reference/message-index.md)** — quick lookup of every protocol message type.
- **[Feature roadmap](./FEATURES.md)** — what exists and what's next.

### Project
- **[FAQ](./faq.md)** · **[Glossary](./glossary.md)**
- **[Contributing](../CONTRIBUTING.md)** · **[Code of Conduct](../CODE_OF_CONDUCT.md)** · **[Security](../SECURITY.md)**
- **[Changelog](../CHANGELOG.md)** · **[Publishing checklist](./PUBLISHING.md)**

---

## 🗺️ Repository at a glance

| Path | Component | Docs |
| ---- | --------- | ---- |
| `unity-client/` | Quest 3 Unity MR shell | [deep-dive](./components/unity-client.md) |
| `agent-backend/` | LLM agent brain | [deep-dive](./components/agent-backend.md) |
| `voice-service/` | Wake word + STT + TTS + ambient | [deep-dive](./components/voice-service.md) |
| `holo-tools/` | 42-widget catalog + tool schemas | [deep-dive](./components/holo-tools.md) |
| `shared-protocol/` | Py / C# / TS protocol bindings | [deep-dive](./components/shared-protocol.md) |
| `infra/` | Compose, mock backend, e2e harness | [deep-dive](./components/infra.md) |

## ⚡ TL;DR

```bash
# Run the whole stack offline (no API key, no headset needed):
cd infra && make install      # installs the brain + runs the LLM key wizard (pick "mock")
make mock                      # or: start the offline mock backend
make e2e                       # drive a scripted multimodal conversation through the protocol
```

Then open `unity-client/` in Unity 2022 LTS with the Meta XR SDK and build to a
Quest 3. See **[Getting Started](./getting-started.md)** for the full walkthrough.

---

<sub>Found a docs gap? <a href="../CONTRIBUTING.md">PRs welcome.</a></sub>
