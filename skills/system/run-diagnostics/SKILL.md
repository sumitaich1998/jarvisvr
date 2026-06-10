---
name: run-diagnostics
description: >-
  Check JarvisVR's health — connection, perception streams, thermal/battery,
  active model, and available tools — and surface problems. Use for "run
  diagnostics", "is everything working?", "why is it slow/laggy?", "check the
  connection", or "system status". Triggers: diagnostics, status, health check,
  is it working, why is it slow, connection, battery, thermal, troubleshoot.
license: MIT
compatibility: >-
  Requires JarvisVR agent-backend. Reads perception.state, session/heartbeat
  health, and the tool/provider catalog (protocol v1.1/§5.2).
metadata:
  agent: system-agent
  category: system
  version: "1.0"
  author: jarvisvr
allowed-tools: show_settings show_data_table notify
---
# Run Diagnostics

Produce a quick, honest health report and flag anything that needs attention.

## Checks

1. **Connection:** heartbeat health (client/server `*.heartbeat` every 5s),
   protocol version, session id.
2. **Model/provider:** active `agent.model` (from `server.hello_ack`) and provider
   reachability (see `configure-llm`).
3. **Perception:** `perception.state` — which streams are active, `fps`,
   `resolution`, `thermal` (`nominal|fair|serious|critical`), `battery`.
4. **Capabilities/tools:** advertised `tools` and `client.hello.capabilities`
   (passthrough, mic, eye_tracking, depth).
5. **Stage:** count of live holograms (clutter is a common "slow/laggy" cause).

## Steps

1. Gather the signals above.
2. Render a `data_table` (or `settings_panel`) summarizing component → status.
3. **Diagnose** the user's complaint (e.g. lag → high hologram count + serious
   thermal → suggest `declutter-space` and lower vision fps).
4. Raise a `notification_toast` (`notify`) for anything `warning`/`error`.

## Output

`data_table` (`show_data_table`, props per registry.json):

```json
{ "widget_type": "data_table",
  "props": { "title": "Diagnostics",
             "columns": [ { "key": "component", "label": "Component", "type": "string" },
                          { "key": "status", "label": "Status", "type": "string" },
                          { "key": "detail", "label": "Detail", "type": "string" } ],
             "rows": [
               { "component": "Connection", "status": "ok", "detail": "v1.2, heartbeat 5s" },
               { "component": "Model", "status": "ok", "detail": "gpt-4o" },
               { "component": "Vision", "status": "fair", "detail": "2 fps, thermal: fair" },
               { "component": "Battery", "status": "ok", "detail": "74%" },
               { "component": "Holograms", "status": "warn", "detail": "11 live — consider declutter" } ],
             "sortable": true } }
```

Issue alert (`notify` → `notification_toast`):

```json
{ "widget_type": "notification_toast",
  "props": { "title": "Thermal: serious", "body": "Lowering vision to 1 fps to cool down.",
             "severity": "warning", "source": "Diagnostics" } }
```

`agent.speech`: `{ "text": "All green except the headset's warming up — I dropped the camera to 1 fps.", "final": true }`

## Edge cases

- **Disconnected** → if heartbeats stopped, advise reconnect; queue the report.
- **Critical thermal/low battery** → recommend pausing vision (`manage-privacy`)
  and reducing holograms (`declutter-space`).
- **Provider unreachable** → point to `configure-llm`; offer the offline mock.
- **Everything nominal** → a one-line "all systems nominal" beats a wall of green.
- **Capability missing** → report as "unavailable", not "failed".
