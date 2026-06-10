"""client.barge_in (PROTOCOL §5.14): cancelling the in-flight agent turn.

The user speaks over Jarvis; the server SHOULD stop streaming the current turn
(agent.speech / agent.observation), abort the in-flight tool/generation loop, and
do nothing if no turn is active (idempotent).
"""

from __future__ import annotations

import asyncio

import pytest
import websockets

from jarvis_backend import protocol
from jarvis_backend.agent import Agent
from jarvis_backend.agent.llm import LLMProvider, LLMResult
from jarvis_backend.server import start_server


class Recorder:
    """Captures emitted messages exactly as the server would build them."""

    def __init__(self):
        self.sent: list[protocol.Envelope] = []

    async def emit(self, type, payload=None, *, reply_to=None):
        self.sent.append(protocol.make(type, payload, session="S", reply_to=reply_to))

    def of(self, type: str) -> list[protocol.Envelope]:
        return [e for e in self.sent if e.type == type]


class BlockingLLM(LLMProvider):
    """An LLM whose completion blocks until released, so a turn stays in-flight
    long enough for ``barge_in`` to cancel it deterministically."""

    name = "blocking"
    model = "blocking"
    supports_vision = False

    def __init__(self):
        self.entered = asyncio.Event()
        self.release = asyncio.Event()
        self.calls = 0

    async def complete(self, messages, tools, *, images=None):
        self.calls += 1
        self.entered.set()
        await self.release.wait()  # park here until released (or cancelled)
        return LLMResult(content="All done with your request.")


# --- in-process cancellation ------------------------------------------------


async def test_barge_in_cancels_active_turn(config):
    llm = BlockingLLM()
    agent = Agent.build(config, llm)
    rec = Recorder()
    session = agent.create_session("S", rec.emit)

    task = asyncio.create_task(
        session.run_turn(session.handle_user_text("show me the weather in tokyo"))
    )
    # Wait until the turn is parked inside the (blocking) LLM call.
    await asyncio.wait_for(llm.entered.wait(), timeout=2.0)

    cancelled = await session.barge_in("user_speech")
    assert cancelled is True

    # The turn task unwinds via CancelledError (the in-flight LLM call is aborted).
    with pytest.raises(asyncio.CancelledError):
        await task

    # Nothing further was streamed for the cancelled turn.
    assert not rec.of("agent.speech"), "no speech should follow a barge_in"
    assert not rec.of("holo.spawn"), "no holograms should follow a barge_in"
    # barge_in emitted a courtesy agent.thinking{done}.
    assert any(e.payload.get("stage") == "done" for e in rec.of("agent.thinking"))
    # Turn tracking was cleaned up.
    assert session._active_turn is None


async def test_barge_in_is_noop_when_idle(agent):
    rec = Recorder()
    session = agent.create_session("S", rec.emit)
    # No turn running -> barge_in is a no-op that emits nothing.
    assert await session.barge_in("user_speech") is False
    assert rec.sent == []


async def test_barge_in_after_turn_completes_is_noop(agent):
    rec = Recorder()
    session = agent.create_session("S", rec.emit)
    await session.run_turn(session.handle_user_text("show weather in tokyo"))
    n_before = len(rec.sent)
    assert await session.barge_in("user_speech") is False
    assert len(rec.sent) == n_before  # the no-op emitted nothing


async def test_run_turn_completes_normally_when_not_barged(config):
    """Wrapping a turn in run_turn must not change normal completion."""
    llm = BlockingLLM()
    agent = Agent.build(config, llm)
    rec = Recorder()
    session = agent.create_session("S", rec.emit)

    task = asyncio.create_task(
        session.run_turn(session.handle_user_text("hello jarvis"))
    )
    await asyncio.wait_for(llm.entered.wait(), timeout=2.0)
    llm.release.set()  # let the LLM finish -> the turn completes normally
    await asyncio.wait_for(task, timeout=2.0)

    assert rec.of("agent.speech"), "a normal turn still streams speech"
    assert any(e.payload.get("stage") == "done" for e in rec.of("agent.thinking"))
    assert session._active_turn is None


# --- over a real socket -----------------------------------------------------


async def _recv(ws) -> protocol.Envelope:
    return protocol.parse_inbound(await ws.recv())


async def _wait_for(ws, type_: str, timeout: float = 5.0) -> protocol.Envelope:
    async def loop():
        while True:
            env = await _recv(ws)
            if env.type == type_:
                return env

    return await asyncio.wait_for(loop(), timeout)


async def test_server_barge_in_is_graceful_and_keeps_connection_alive(config):
    server, _agent = await start_server(config)
    port = server.sockets[0].getsockname()[1]
    uri = f"ws://127.0.0.1:{port}/jarvis"
    try:
        async with websockets.connect(uri) as ws:
            await ws.send(protocol.make("client.hello", {"device": "quest3"}).to_json())
            ack = await _wait_for(ws, "server.hello_ack")
            session = ack.payload["session"]

            # Start a turn, then interrupt it.
            await ws.send(
                protocol.make(
                    "user.text", {"text": "show me the weather in tokyo"}, session=session
                ).to_json()
            )
            await ws.send(
                protocol.make(
                    "client.barge_in", {"reason": "user_speech"}, session=session
                ).to_json()
            )

            # Drain frames briefly; none may be a server.error.
            errors = []
            deadline = asyncio.get_event_loop().time() + 3.0
            while asyncio.get_event_loop().time() < deadline:
                try:
                    env = await asyncio.wait_for(_recv(ws), timeout=1.0)
                except asyncio.TimeoutError:
                    break
                if env.type == "server.error":
                    errors.append(env)
            assert not errors, f"barge_in produced server.error(s): {errors}"

            # The connection is still alive and serving: a heartbeat round-trips.
            await ws.send(
                protocol.make("client.heartbeat", {}, session=session).to_json()
            )
            hb = await _wait_for(ws, "server.heartbeat")
            assert hb.type == "server.heartbeat"
    finally:
        server.close()
        await server.wait_closed()
