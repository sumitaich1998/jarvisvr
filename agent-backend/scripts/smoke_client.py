#!/usr/bin/env python3
"""Tiny smoke client: connect, handshake, drive one turn, print the frames.

Usage:
    python scripts/smoke_client.py "show weather in tokyo"
    JARVIS_URL=ws://127.0.0.1:8765/jarvis python scripts/smoke_client.py "set a 5 minute timer"

Requires the `websockets` package (a dependency of jarvis-backend).
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
import uuid

import websockets

URL = os.getenv("JARVIS_URL", "ws://127.0.0.1:8765/jarvis")
PROTOCOL_VERSION = "1.1.0"

# Words that imply the user is asking about what they see/hear.
_VISUAL = ("see", "this", "look", "read", "translate", "sound", "noise", "where", "measure", "identify")

# A canned desk scene so the offline demo can annotate real objects.
_DEMO_SCENE = {
    "objects": [
        {"label": "coffee mug", "confidence": 0.82, "position": [0.3, 0.8, 0.7], "anchor": "world"},
        {"label": "laptop", "confidence": 0.91, "position": [0.0, 0.8, 0.7], "anchor": "world"},
    ]
}


def envelope(type_: str, payload: dict, session: str | None = None) -> str:
    env = {
        "v": PROTOCOL_VERSION,
        "id": str(uuid.uuid4()),
        "type": type_,
        "ts": int(time.time() * 1000),
        "payload": payload,
    }
    if session:
        env["session"] = session
    return json.dumps(env)


async def main() -> None:
    text = " ".join(sys.argv[1:]) or "show weather in tokyo and start a 5 minute timer"
    print(f"connecting to {URL}")
    async with websockets.connect(URL) as ws:
        await ws.send(
            envelope(
                "client.hello",
                {"device": "quest3", "locale": "en-US",
                 "capabilities": {"camera_passthrough": True, "ambient_audio": True, "eye_tracking": True}},
            )
        )
        ack = json.loads(await ws.recv())
        session = ack.get("payload", {}).get("session")
        print(f"<- {ack['type']}  session={session}  perception={ack['payload'].get('perception')}")
        print(f"   tools={len(ack['payload'].get('tools', []))}  widgets={len(ack['payload'].get('widgets', []))}")

        visual = any(w in text.lower() for w in _VISUAL)
        if visual:
            # Provide detected objects so the offline demo can annotate them.
            await ws.send(envelope("perception.scene_objects", _DEMO_SCENE, session))

        await ws.send(
            envelope("user.text", {"text": text, "attach_perception": visual}, session)
        )
        print(f"-> user.text: {text!r}  (attach_perception={visual})\n")

        # Read frames until we see the final agent.speech (or time out).
        deadline = asyncio.get_event_loop().time() + 8.0
        while asyncio.get_event_loop().time() < deadline:
            try:
                msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=3.0))
            except asyncio.TimeoutError:
                break
            t = msg["type"]
            p = msg.get("payload", {})
            if t == "agent.thinking":
                print(f"   .. thinking[{p.get('stage')}] {p.get('label') or ''} {p.get('tool') or ''}".rstrip())
            elif t == "perception.request":
                print(f"<- perception.request: stream={p.get('stream')} action={p.get('action')} reason={p.get('reason')}")
            elif t == "agent.observation":
                labels = [a.get("label") for a in p.get("annotations", [])]
                print(f"<- OBSERVATION: {p.get('text')}  annotations={labels}")
            elif t == "agent.speech":
                tag = "FINAL" if p.get("final") else "...."
                print(f"<- speech[{tag}]: {p.get('text')}")
            elif t == "holo.spawn":
                print(f"<- holo.spawn {p.get('widget_type')} object_id={p.get('object_id')[:8]} props={p.get('props')}")
                # Be a good client: ack the render command.
                await ws.send(envelope("client.ack", {}, session))
            elif t in ("holo.update", "holo.destroy", "holo.layout"):
                print(f"<- {t}: {p}")
            elif t == "server.error":
                print(f"<- server.error: {p}")
            else:
                print(f"<- {t}: {p}")
            if t == "agent.speech" and p.get("final"):
                break
        print("\ndone.")


if __name__ == "__main__":
    asyncio.run(main())
