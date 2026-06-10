"""End-to-end v1.3 over real sockets: hello flags, trace stream/fetch, inspect, authoring."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import websockets

from jarvis_backend import protocol
from jarvis_backend.agent import Agent
from jarvis_backend.agent.llm import MockLLM
from jarvis_backend.config import Config
from jarvis_backend.server import start_server


def _cfg(tmp_path: Path) -> Config:
    return Config(
        host="127.0.0.1", port=0, ws_path="/jarvis", llm_provider="mock",
        holo_registry_path=None, data_dir=Path(tmp_path), skills_dir=Path(tmp_path) / "skills",
    )


async def _recv(ws):
    return protocol.parse_inbound(await ws.recv())


async def _wait_for(ws, type_, timeout=6.0):
    async def loop():
        while True:
            env = await _recv(ws)
            if env.type == type_:
                return env

    return await asyncio.wait_for(loop(), timeout)


async def _start(config):
    server, _agent = await start_server(config)
    return server, server.sockets[0].getsockname()[1]


async def test_v13_end_to_end(tmp_path):
    server, port = await _start(_cfg(tmp_path))
    uri = f"ws://127.0.0.1:{port}/jarvis"
    try:
        async with websockets.connect(uri) as ws:
            await ws.send(protocol.make("client.hello", {"device": "quest3"}).to_json())
            ack = await _wait_for(ws, "server.hello_ack")
            session = ack.payload["session"]
            assert ack.payload["tracing"] is True
            assert ack.payload["authoring"] is True
            assert ack.payload["orchestration"] is True

            # Subscribe to live traces, then run a multi-agent turn.
            await ws.send(protocol.make("client.trace_subscribe", {"enabled": True}, session=session).to_json())
            await ws.send(protocol.make(
                "user.text",
                {"text": "show weather in tokyo and start a 5 minute timer"},
                session=session,
            ).to_json())

            trace_kinds: set[str] = set()
            plan_id = None
            deadline = asyncio.get_event_loop().time() + 8.0
            while asyncio.get_event_loop().time() < deadline:
                try:
                    env = await asyncio.wait_for(_recv(ws), timeout=3.0)
                except asyncio.TimeoutError:
                    break
                if env.type == "orchestration.plan":
                    plan_id = env.payload["plan_id"]
                elif env.type == "orchestration.trace_event":
                    trace_kinds.add(env.payload["kind"])
                elif env.type == "agent.thinking" and env.payload.get("stage") == "done":
                    break  # the 'speech' trace_event is emitted just before 'done'

            assert plan_id is not None
            assert {"memory_read", "tool_call", "tool_result", "speech"} <= trace_kinds

            # Fetch the full trace for that turn.
            await ws.send(protocol.make("client.trace_get", {"plan_id": plan_id}, session=session).to_json())
            trace = await _wait_for(ws, "server.trace")
            assert trace.payload["plan_id"] == plan_id
            assert trace.payload["entries"]

            # Inspect an agent.
            await ws.send(protocol.make("client.agent_inspect", {"role": "research-agent"}, session=session).to_json())
            info = await _wait_for(ws, "server.agent_info")
            assert info.payload["role"] == "research-agent"
            assert "get_weather" in info.payload["tools"]

            # Author a skill from the headset; it appears in the catalog as source:user.
            await ws.send(protocol.make("client.author_skill", {
                "op": "create", "name": "track-habit", "category": "productivity",
                "agent": "productivity-agent", "description": "Track a daily habit.",
                "body": "# Track\n1. note", "allowed_tools": ["take_note"],
            }, session=session).to_json())
            authoring = await _wait_for(ws, "server.authoring")
            assert any(
                s["name"] == "track-habit" and s["source"] == "user"
                for s in authoring.payload["skills"]
            )

            # Authoring an invalid skill yields a server.error, not a crash.
            await ws.send(protocol.make("client.author_skill", {
                "op": "create", "name": "../escape", "category": "productivity", "description": "x",
            }, session=session).to_json())
            err = await _wait_for(ws, "server.error")
            assert err.payload["code"] in ("invalid_skill", "forbidden")

            # No secret material ever appears on the wire (we never sent one, but assert anyway).
            blob = " ".join(json.dumps(e.payload) for e in [trace, info, authoring])
            assert "api_key" not in blob.lower()
    finally:
        server.close()
        await server.wait_closed()
