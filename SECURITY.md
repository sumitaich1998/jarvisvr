# Security Policy

Thanks for helping keep **JarvisVR** and its users safe.

## Supported versions

JarvisVR is pre-1.0 and moves fast. Security fixes land on the latest `main` and
the most recent tagged release.

| Version | Supported |
| ------- | --------- |
| latest `main` / newest release | ✅ |
| older tags | ❌ |

## Reporting a vulnerability

**Please do not open a public issue for security vulnerabilities.**

Instead, report privately via one of:

- GitHub's **[Private vulnerability reporting](https://github.com/sumitaich1998/jarvisvr/security/advisories/new)**
  (Security → Report a vulnerability), or
- Email **aich.1998@gmail.com** (replace with your contact before publishing).

Please include: a description, affected component(s) (`unity-client`,
`agent-backend`, `voice-service`, `holo-tools`, `shared-protocol`, `infra`),
reproduction steps or a proof-of-concept, and the impact you foresee.

We aim to acknowledge reports within **72 hours**, provide an initial assessment
within a week, and coordinate a fix and disclosure timeline with you. We're
happy to credit you in the release notes unless you prefer to remain anonymous.

## Security posture & expectations

JarvisVR handles sensitive inputs (LLM API keys, camera/microphone perception),
so a few design notes:

- **API keys** are stored in `agent-backend/.env` with `0600` (owner-only)
  permissions, are **never printed or logged** (only a masked `•••• (N chars)`
  confirmation), and are **never echoed back** to the client — the `server.settings`
  message is a *closed* schema that structurally cannot contain an `api_key`.
- **Transport**: the WebSocket protocol is unauthenticated and unencrypted by
  default for local development. **Use `wss://` (TLS) and add authentication
  before exposing the backend beyond `localhost`.** The `client.settings_update`
  message carries the key, so it must only travel over a secure channel.
- **Perception (camera / mic / gaze)** is **opt-in, negotiated, and pull-based**
  (`perception.request` start/stop/once). Capture runs only while a stream is
  active, `perception.state` always reflects what is live, and servers should
  process frames/audio in-memory and avoid persistence unless the user opts in.
- **No telemetry.** JarvisVR does not phone home. Any third-party calls are to
  the LLM/voice provider *you* configure.
- **Secrets hygiene**: `.env`, `*.key`, and `*.pem` are gitignored. Never commit
  real keys; use the `jarvis-backend setup` wizard or environment variables.

## Hardening checklist for deployments

- [ ] Terminate TLS (`wss://`) in front of the backend.
- [ ] Add authentication/authorization on the WebSocket endpoints.
- [ ] Restrict `/vision` and `/audio` to trusted clients.
- [ ] Run the backend as a non-root user (the Dockerfile is a good base).
- [ ] Rotate provider API keys periodically; scope them minimally.
