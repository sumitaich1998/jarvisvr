# Guide: Deploy JarvisVR

This guide covers running the JarvisVR backend for real — Docker Compose, the
services and ports, TLS (`wss://`) and authentication, and a **production hardening
checklist** that mirrors [`SECURITY.md`](../../SECURITY.md).

> **The Unity client ships as a device build, not a server.** There is **no prebuilt
> APK** — you build `unity-client/` in Unity and **Build & Run** to a Quest 3. So
> "deploying JarvisVR" means deploying the **backend** (and optionally the
> voice-service) that the headset connects to. See the
> [Unity device-build section](#the-unity-client-is-a-device-build) below.

---

## What you're deploying

| Service | Image / context | Port (host:container) | Endpoints |
| ------- | --------------- | --------------------- | --------- |
| `agent-backend` | [`agent-backend/Dockerfile`](../../agent-backend/Dockerfile) | `8765:8765` | `ws://host:8765/jarvis` (JSON) + `ws://host:8765/vision` (binary, v1.1) + `/audio` |
| `voice-service` | [`voice-service/Dockerfile`](../../voice-service/Dockerfile) | internal only | dials `ws://agent-backend:8765/jarvis` |

The `/vision` binary transport ([`PROTOCOL.md` §8.2](../PROTOCOL.md#82-vision-transport-vision))
is a **path on the same `8765` port**, so the one `8765:8765` mapping already exposes
it — no extra port. Compose files live in [`infra/`](../../infra/).

---

## Option 1 — Run the backend directly (no Docker)

Good for a single host or a dev box on your LAN.

```bash
cd agent-backend
python -m venv .venv && source .venv/bin/activate
pip install -e ".[providers]"        # core + LiteLLM (drop the extra for mock-only)

jarvis-backend setup                 # pick a provider, enter the API key (masked, → .env chmod 600)
python -m jarvis_backend             # ws://0.0.0.0:8765/jarvis
```

Bind/port/path are env-driven (`JARVIS_HOST`, `JARVIS_PORT`, `JARVIS_WS_PATH`); see
the [environment variables reference](../reference/env-vars.md). Run it under a
process supervisor (systemd, supervisord) so it restarts on failure.

---

## Option 2 — Docker Compose

From [`infra/`](../../infra/). Copy the env file first (the scripts do this for you):

```bash
cd infra
cp .env.example .env        # edit: JARVIS_LLM, provider keys, etc.
```

### The real stack (backend + voice)

```bash
make up        # docker compose up --build -d   (needs ../agent-backend, ../voice-service images)
make down      # stop it
docker compose ps
docker compose logs -f agent-backend
```

`docker-compose.yml` is the base. It sets `env_file: .env`, maps `8765:8765`, and has
a TCP healthcheck on the backend. `voice-service` reaches the brain over the compose
network at `ws://agent-backend:8765/jarvis`.

### Just the backend (mock brain, no sibling images)

For client/voice development you don't need the real images — run the self-contained
mock:

```bash
make mock      # docker compose -f docker-compose.yml -f docker-compose.mock.yml up --build agent-backend
```

### GPU for voice (STT/TTS acceleration)

Layer the GPU override (needs the NVIDIA Container Toolkit):

```bash
docker compose -f docker-compose.yml -f docker-compose.gpu.yml up --build
```

### Build the backend image yourself

```bash
cd agent-backend
docker build -t jarvisvr/agent-backend .
docker run --rm -p 8765:8765 \
  -e JARVIS_LLM=openai -e OPENAI_API_KEY=sk-… \
  -v "$PWD/.data:/data" \
  -v "$PWD/../holo-tools/registry.json:/holo-tools/registry.json:ro" \
  jarvisvr/agent-backend
```

The Dockerfile is `python:3.11-slim`, exposes `8765`, persists memory in the `/data`
volume, and defaults `JARVIS_HOLO_REGISTRY=/holo-tools/registry.json` (mount the real
catalog there, or the built-in fallback is used).

### Validate compose syntax

```bash
make config     # docker compose config for base + mock + gpu overrides
```

---

## TLS / `wss://` and authentication

> **Read this before exposing the backend beyond `localhost`.** Per
> [`SECURITY.md`](../../SECURITY.md): *the WebSocket protocol is **unauthenticated and
> unencrypted by default** for local development. Use `wss://` (TLS) and add
> authentication before exposing the backend beyond `localhost`.*

The agent-backend server speaks plain `ws://` and has **no built-in TLS or auth**.
Add both at a **reverse proxy** in front of it (nginx, Caddy, Traefik). This matters
especially because the in-headset settings flow sends the **LLM API key** over
`client.settings_update` ([`PROTOCOL.md` §5.15](../PROTOCOL.md#515-settings--clientsettings_get--clientsettings_update--serversettings-v11))
— that message must only travel over a secure channel.

### Example: terminate TLS with Caddy

Caddy auto-provisions certificates and proxies WebSockets transparently:

```caddy
jarvis.example.com {
    # Optional: gate access (e.g. an auth header / mTLS / forward-auth) before proxying.
    reverse_proxy 127.0.0.1:8765
}
```

Clients then connect to `wss://jarvis.example.com/jarvis` (and
`wss://jarvis.example.com/vision`). In Unity, set the `JarvisConfig` **Use Tls**
toggle and point `host` at your domain.

### Example: terminate TLS with nginx

```nginx
server {
    listen 443 ssl;
    server_name jarvis.example.com;
    ssl_certificate     /etc/letsencrypt/live/jarvis.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/jarvis.example.com/privkey.pem;

    location / {
        proxy_pass http://127.0.0.1:8765;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;     # WebSocket upgrade
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_read_timeout 600s;                    # keep long-lived sockets alive
    }
}
```

### Authentication

There is no auth in the server today, so enforce it at the proxy layer, for example:

- A bearer token / API key the client appends as a query param or header on connect
  (validate it in the proxy before upgrading).
- mTLS (client certificates) for a closed fleet of headsets.
- A forward-auth / OAuth2-proxy in front of the reverse proxy.

Whatever you choose, **also restrict the `/vision` and `/audio` endpoints** to
trusted clients — they carry camera frames and microphone audio.

---

## Production hardening checklist

Aligned with [`SECURITY.md` → "Hardening checklist for deployments"](../../SECURITY.md#hardening-checklist-for-deployments):

- [ ] **Terminate TLS (`wss://`)** in front of the backend (reverse proxy above).
- [ ] **Add authentication/authorization** on the WebSocket endpoints.
- [ ] **Restrict `/vision` and `/audio`** to trusted clients (camera/mic streams).
- [ ] **Run the backend as a non-root user** (the Dockerfile is a good base).
- [ ] **Rotate provider API keys** periodically; scope them minimally.

Security properties the backend already gives you (don't undo them):

- **API keys at rest** live in `agent-backend/.env` with **`0600`** permissions, are
  **never printed or logged** (only a masked `•••• (N chars)`), and are **never
  echoed back** — `server.settings` is a *closed* schema that structurally cannot
  contain an `api_key`.
- **Perception is opt-in, negotiated, and pull-based** (`perception.request`
  start/stop/once). Capture runs only while a stream is active; servers process
  in-memory and avoid persistence unless the user opts in. Proactive observations are
  off unless `JARVIS_PROACTIVE=1`.
- **No telemetry.** JarvisVR does not phone home; the only third-party calls are to
  the LLM/voice provider **you** configure.
- **Secrets hygiene**: `.env`, `*.key`, `*.pem` are gitignored — never commit real
  keys; use `jarvis-backend setup` or environment variables.

### Operational notes

- **Persist memory**: mount a volume at `/data` (notes, reminders, episodic/spatial
  memory) so it survives restarts.
- **Logs**: set `JARVIS_LOG_JSON=1` for one-line JSON logs that aggregate cleanly;
  tune verbosity with `JARVIS_LOG_LEVEL`.
- **Health**: the compose healthcheck is a TCP probe on `8765`; put the same behind
  your orchestrator's liveness check.
- **Catalog**: mount the canonical `holo-tools/registry.json` at the path in
  `JARVIS_HOLO_REGISTRY` so the deployed backend validates against the real widget
  schemas (otherwise the built-in fallback catalog is used).

---

## The Unity client is a device build

The headset app is **not** something you host — you build and install it on the Quest 3:

1. Open `unity-client/` in **Unity 2022.3 LTS** with the **Meta XR All-in-One SDK**.
2. Create/point a **`JarvisConfig`** asset at your backend: set `host` (your server's
   LAN IP or domain), `port` (`8765`), `path` (`/jarvis`), and the **Use Tls** toggle
   for `wss://`.
3. **Build & Run** to a Quest 3 in Developer Mode (or test in-editor over Quest
   Link). Full steps in the [unity-client README](../../unity-client/README.md).

On device over Wi-Fi, use your server's **LAN IP / domain — not `127.0.0.1`**. If you
serve plain `ws://`, the Android manifest must permit cleartext to that host (or use
`wss://`).

---

## See also

- [infra deep-dive](../components/infra.md) · [`infra/README.md`](../../infra/README.md).
- [Environment variables reference](../reference/env-vars.md) · [CLI reference](../reference/cli.md).
- [`SECURITY.md`](../../SECURITY.md) — reporting, posture, and the hardening checklist.
- [Add an LLM provider](./add-an-llm-provider.md) · [Troubleshooting](./troubleshooting.md).
