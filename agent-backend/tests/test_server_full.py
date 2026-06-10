"""Integration: drive the real WebSocket server through every message type +
the /vision and /audio endpoints + lifecycle, asserting valid frames + no leaks."""

from __future__ import annotations

import asyncio
import json

import pytest
import websockets

from jarvis_backend import protocol
from jarvis_backend.agent import Agent
from jarvis_backend.agent.llm import MockLLM
from jarvis_backend.config import Config
from jarvis_backend.perception.buffer import encode_binary_vision_frame
from jarvis_backend.server import Connection, run_server, start_server
from tests.conftest import make_config


async def _recv(ws):
    return protocol.parse_inbound(await ws.recv())


async def _wait_for(ws, type_, timeout=6.0):
    async def loop():
        while True:
            env = await _recv(ws)
            if env.type == type_:
                return env

    return await asyncio.wait_for(loop(), timeout)


async def _drain(ws, seconds=1.0):
    out = []
    deadline = asyncio.get_event_loop().time() + seconds
    while asyncio.get_event_loop().time() < deadline:
        try:
            out.append(await asyncio.wait_for(_recv(ws), timeout=seconds))
        except asyncio.TimeoutError:
            break
    return out


async def _serve(config):
    server, agent = await start_server(config)
    port = server.sockets[0].getsockname()[1]
    return server, agent, port


async def _hello(ws, payload=None):
    await ws.send(protocol.make("client.hello", payload or {"device": "quest3"}).to_json())
    ack = await _wait_for(ws, "server.hello_ack")
    return ack


# --- handshake + capabilities ----------------------------------------------


async def test_hello_ack_capabilities(config):
    server, _agent, port = await _serve(config)
    try:
        async with websockets.connect(f"ws://127.0.0.1:{port}/jarvis") as ws:
            ack = await _hello(ws)
            p = ack.payload
            assert p["session"]
            assert p["orchestration"] is True
            assert p["tracing"] is True and p["authoring"] is True
            assert "get_weather" in p["tools"]
    finally:
        server.close()
        await server.wait_closed()


# --- a broad multi-message drive --------------------------------------------


async def test_dispatch_every_message_type(tmp_path):
    config = make_config(tmp_path, proactive=True, skills_dir=tmp_path / "skills")
    server, _agent, port = await _serve(config)
    try:
        async with websockets.connect(f"ws://127.0.0.1:{port}/jarvis") as ws:
            ack = await _hello(ws)
            sid = ack.payload["session"]

            def send(t, p):
                return ws.send(protocol.make(t, p, session=sid).to_json())

            # heartbeat
            await send("client.heartbeat", {})
            assert (await _wait_for(ws, "server.heartbeat"))

            # perception ingestion (quiet streams)
            await send("perception.scene_objects", {"objects": [{"label": "mug", "confidence": 0.8, "position": [0.3, 0.8, 0.7], "anchor": "world"}]})
            await send("perception.gaze", {"hit_object_id": "O1"})
            await send("perception.vision_frame", {"frame_id": "F1", "width": 8, "height": 8, "data": "QQ==", "seq": 1})
            await send("perception.state", {"vision": {"active": True}})
            await send("user.voice_partial", {"text": "ignore me"})  # ignored
            await send("client.ack", {})
            await send("client.error", {"message": "client side"})
            await send("totally.unknown", {"x": 1})  # ignored

            # a full orchestrated turn
            await send("user.text", {"text": "show weather in tokyo"})
            assert (await _wait_for(ws, "agent.speech")).payload

            # proactive audio event -> observation + speech
            await send("perception.audio_event", {"label": "doorbell", "confidence": 0.9})
            assert (await _wait_for(ws, "agent.observation"))
            await send("perception.audio_scene", {"ambient_transcript": "hi"})

            # an interaction on a spawned object
            await send("user.text", {"text": "set a 10 minute timer"})
            spawn = await _wait_for(ws, "holo.spawn")
            await send("client.interaction", {"object_id": spawn.payload["object_id"], "widget_type": "timer", "action": "tap"})
            assert (await _wait_for(ws, "holo.update"))

            # barge-in (idempotent no-op here)
            await send("client.barge_in", {"reason": "user spoke"})

            # scene store
            await send("client.scene", {"anchors": []})

            # settings get/update (no key leak)
            await send("client.settings_get", {})
            st = await _wait_for(ws, "server.settings")
            assert "api_key" not in json.dumps(st.payload)
            await send("client.settings_update", {"llm": {"provider": "openai", "api_key": "sk-secret"}})
            st2 = await _wait_for(ws, "server.settings")
            assert "sk-secret" not in json.dumps(st2.payload)

            # tracing
            await send("client.trace_subscribe", {"enabled": True})
            await send("user.text", {"text": "what's on my calendar"})
            ev = await _wait_for(ws, "orchestration.trace_event")
            plan_id = ev.payload["plan_id"]
            await send("client.trace_get", {"plan_id": plan_id})
            assert (await _wait_for(ws, "server.trace")).payload["entries"]

            # inspect + authoring
            await send("client.agent_inspect", {"role": "research-agent"})
            assert (await _wait_for(ws, "server.agent_info")).payload["role"] == "research-agent"
            await send("client.author_list", {})
            assert (await _wait_for(ws, "server.authoring")).payload["agents"]
            await send("client.author_skill", {"op": "create", "name": "habit", "category": "productivity", "agent": "productivity-agent", "description": "track", "body": "# h"})
            assert (await _wait_for(ws, "server.authoring"))
            await send("client.author_agent", {"op": "create", "role": "finance-agent", "name": "Finance"})
            assert (await _wait_for(ws, "server.authoring"))

            # authoring error -> server.error
            await send("client.author_skill", {"op": "create", "name": "../bad", "category": "x", "description": "d"})
            assert (await _wait_for(ws, "server.error")).payload["code"] in ("invalid_skill", "forbidden")

            await _drain(ws, 0.3)
            await send("client.bye", {})
    finally:
        server.close()
        await server.wait_closed()


# --- error handling ---------------------------------------------------------


async def test_bad_envelope(config):
    server, _agent, port = await _serve(config)
    try:
        async with websockets.connect(f"ws://127.0.0.1:{port}/jarvis") as ws:
            await ws.send("this is not json")
            err = await _wait_for(ws, "server.error")
            assert err.payload["code"] == "bad_envelope"
    finally:
        server.close()
        await server.wait_closed()


async def test_user_text_bad_payload_errors(config):
    server, _agent, port = await _serve(config)
    try:
        async with websockets.connect(f"ws://127.0.0.1:{port}/jarvis") as ws:
            sid = (await _hello(ws)).payload["session"]
            # text must be a string; an int fails validation -> server.error
            await ws.send(protocol.make("user.text", {"text": 123}, session=sid).to_json())
            err = await _wait_for(ws, "server.error")
            assert err.payload["code"] == "bad_envelope"
    finally:
        server.close()
        await server.wait_closed()


async def test_incompatible_version_warns_but_serves(config):
    server, _agent, port = await _serve(config)
    try:
        async with websockets.connect(f"ws://127.0.0.1:{port}/jarvis") as ws:
            env = protocol.make("client.hello", {})
            raw = json.loads(env.to_json())
            raw["v"] = "9.9.9"  # incompatible major -> warning, still served
            await ws.send(json.dumps(raw))
            assert (await _wait_for(ws, "server.hello_ack"))
    finally:
        server.close()
        await server.wait_closed()


# --- /vision + /audio endpoints + path routing ------------------------------


async def test_vision_endpoint_ingests_frames(config):
    server, _agent, port = await _serve(config)
    try:
        async with websockets.connect(f"ws://127.0.0.1:{port}/jarvis") as ws:
            sid = (await _hello(ws)).payload["session"]
            vuri = f"ws://127.0.0.1:{port}/vision?session={sid}"
            async with websockets.connect(vuri) as vws:
                await vws.send("{not valid json")  # malformed control frame -> ignored
                await vws.send(json.dumps({"session": sid}))  # control frame
                await vws.send(encode_binary_vision_frame({"frame_id": "F", "seq": 1}, b"\xff\xd8jpeg"))
                await vws.send(b"\x00")  # malformed (too short) -> dropped
                await vws.send(encode_binary_vision_frame({"frame_id": "G", "session": "ghost"}, b"x"))  # unknown session
                await asyncio.sleep(0.2)
            # main session still healthy
            await ws.send(protocol.make("client.heartbeat", {}, session=sid).to_json())
            assert (await _wait_for(ws, "server.heartbeat"))
    finally:
        server.close()
        await server.wait_closed()


async def test_audio_endpoint_drains(config):
    server, _agent, port = await _serve(config)
    try:
        async with websockets.connect(f"ws://127.0.0.1:{port}/audio") as aws:
            await aws.send(b"\x00\x01\x02")
            await asyncio.sleep(0.1)
    finally:
        server.close()
        await server.wait_closed()


async def test_unexpected_path_served_as_jarvis(config):
    server, _agent, port = await _serve(config)
    try:
        async with websockets.connect(f"ws://127.0.0.1:{port}/somethingelse") as ws:
            assert (await _hello(ws))  # still handled as the main channel
    finally:
        server.close()
        await server.wait_closed()


# --- lifecycle: run_server + start_server building its own agent -------------


async def test_start_server_builds_agent_when_none(config):
    server, agent = await start_server(config)  # agent=None -> create_llm + build
    try:
        assert isinstance(agent, Agent)
    finally:
        server.close()
        await server.wait_closed()


async def test_run_server_runs_until_cancelled(tmp_path):
    config = make_config(tmp_path)
    task = asyncio.create_task(run_server(config))
    await asyncio.sleep(0.3)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task


async def test_connection_emit_without_session(tmp_path):
    # emit before a session exists uses session=None (covers that branch).
    class _WS:
        async def send(self, data):
            return None

    conn = Connection(_WS(), Agent.build(make_config(tmp_path), MockLLM()))
    await conn.emit("agent.thinking", {"stage": "planning"})
    env = await conn._outbox.get()
    assert env.session is None
