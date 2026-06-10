"""End-to-end WebSocket server tests (real sockets, ephemeral port)."""

from __future__ import annotations

import asyncio

import websockets

from jarvis_backend import protocol
from jarvis_backend.server import start_server


async def _recv_env(ws) -> protocol.Envelope:
    return protocol.parse_inbound(await ws.recv())


async def _wait_for(ws, type_: str, timeout: float = 5.0) -> protocol.Envelope:
    async def loop():
        while True:
            env = await _recv_env(ws)
            if env.type == type_:
                return env

    return await asyncio.wait_for(loop(), timeout)


async def _start(config):
    server, _agent = await start_server(config)
    port = server.sockets[0].getsockname()[1]
    return server, f"ws://127.0.0.1:{port}/jarvis"


async def test_handshake_assigns_session(config):
    server, uri = await _start(config)
    try:
        async with websockets.connect(uri) as ws:
            await ws.send(protocol.make("client.hello", {"device": "quest3"}).to_json())
            ack = await _wait_for(ws, "server.hello_ack")
            assert ack.payload["session"]
            assert ack.payload["protocol_version"] == protocol.PROTOCOL_VERSION
            assert ack.payload["agent"]["name"] == "Jarvis"
            assert "get_weather" in ack.payload["tools"]
    finally:
        server.close()
        await server.wait_closed()


async def test_heartbeat_echo(config):
    server, uri = await _start(config)
    try:
        async with websockets.connect(uri) as ws:
            await ws.send(protocol.make("client.hello", {}).to_json())
            ack = await _wait_for(ws, "server.hello_ack")
            session = ack.payload["session"]
            await ws.send(
                protocol.make("client.heartbeat", {}, session=session).to_json()
            )
            hb = await _wait_for(ws, "server.heartbeat")
            assert hb.type == "server.heartbeat"
    finally:
        server.close()
        await server.wait_closed()


async def test_unknown_type_ignored_and_connection_alive(config):
    server, uri = await _start(config)
    try:
        async with websockets.connect(uri) as ws:
            await ws.send(protocol.make("client.hello", {}).to_json())
            ack = await _wait_for(ws, "server.hello_ack")
            session = ack.payload["session"]

            # Unknown type must be ignored (no error, no crash).
            await ws.send(
                protocol.make("totally.unknown", {"x": 1}, session=session).to_json()
            )
            # Then a normal request should still be answered -> proves liveness.
            await ws.send(
                protocol.make(
                    "user.text", {"text": "show weather in tokyo"}, session=session
                ).to_json()
            )

            spawn = await _wait_for(ws, "holo.spawn", timeout=6.0)
            obj = protocol.HoloObject.model_validate(spawn.payload)
            assert obj.widget_type == "weather_orb"
    finally:
        server.close()
        await server.wait_closed()


async def test_full_turn_streams_speech_and_spawn(config):
    server, uri = await _start(config)
    try:
        async with websockets.connect(uri) as ws:
            await ws.send(protocol.make("client.hello", {}).to_json())
            ack = await _wait_for(ws, "server.hello_ack")
            session = ack.payload["session"]

            await ws.send(
                protocol.make(
                    "user.voice_transcript",
                    {"text": "weather in tokyo"},
                    session=session,
                ).to_json()
            )

            got_final_speech = False
            spawns = []
            errors = []
            deadline = asyncio.get_event_loop().time() + 6.0
            while asyncio.get_event_loop().time() < deadline:
                try:
                    env = await asyncio.wait_for(_recv_env(ws), timeout=2.0)
                except asyncio.TimeoutError:
                    break
                if env.type == "agent.speech" and env.payload.get("final"):
                    got_final_speech = True
                elif env.type == "holo.spawn":
                    spawns.append(env)
                elif env.type == "server.error":
                    errors.append(env)
                if got_final_speech and spawns:
                    break

            assert not errors, f"unexpected server.error(s): {errors}"
            assert got_final_speech, "did not receive final agent.speech"
            assert spawns, "did not receive holo.spawn"
            assert protocol.HoloObject.model_validate(spawns[0].payload).widget_type == "weather_orb"
    finally:
        server.close()
        await server.wait_closed()


async def test_bad_envelope_returns_error(config):
    server, uri = await _start(config)
    try:
        async with websockets.connect(uri) as ws:
            await ws.send("this is not json")
            err = await _wait_for(ws, "server.error")
            assert err.payload["code"] == "bad_envelope"
    finally:
        server.close()
        await server.wait_closed()
