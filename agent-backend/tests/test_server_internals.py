"""Connection internals: writer/shutdown/guard + error-handler branches."""

from __future__ import annotations

import asyncio

import pytest
from websockets.exceptions import ConnectionClosed

from jarvis_backend import protocol
from jarvis_backend.agent import Agent
from jarvis_backend.agent.llm import MockLLM
from jarvis_backend.server import Connection
from tests.conftest import make_config


class FakeWS:
    def __init__(self, send_exc=None):
        self.sent = []
        self.send_exc = send_exc
        self.closed = False
        self.path = "/jarvis"

    async def send(self, data):
        if self.send_exc is not None:
            raise self.send_exc
        self.sent.append(data)

    async def close(self):
        self.closed = True


def _conn(tmp_path, ws=None) -> Connection:
    return Connection(ws or FakeWS(), Agent.build(make_config(tmp_path), MockLLM()))


async def _drain_outbox(conn):
    out = []
    while not conn._outbox.empty():
        out.append(await conn._outbox.get())
    return out


# --- writer -----------------------------------------------------------------


async def test_writer_sends_then_stops_on_sentinel(tmp_path):
    conn = _conn(tmp_path)
    await conn.emit("agent.thinking", {"stage": "planning"})
    await conn._outbox.put(None)  # shutdown sentinel
    await conn._writer()
    assert conn.ws.sent  # sent the queued frame before stopping


async def test_writer_handles_connection_closed(tmp_path):
    conn = _conn(tmp_path, FakeWS(send_exc=ConnectionClosed(None, None)))
    await conn.emit("agent.thinking", {"stage": "planning"})
    await conn._writer()  # must return cleanly, not raise


async def test_writer_handles_generic_exception(tmp_path):
    conn = _conn(tmp_path, FakeWS(send_exc=ValueError("boom")))
    await conn.emit("agent.thinking", {"stage": "planning"})
    await conn._writer()  # logged + returns


# --- guard ------------------------------------------------------------------


async def test_guard_swallows_value_error(tmp_path):
    async def boom():
        raise ValueError("x")

    await _conn(tmp_path)._guard(boom())  # no raise


async def test_guard_swallows_connection_closed(tmp_path):
    async def cc():
        raise ConnectionClosed(None, None)

    await _conn(tmp_path)._guard(cc())  # no raise


async def test_guard_reraises_cancelled(tmp_path):
    async def cancel():
        raise asyncio.CancelledError

    with pytest.raises(asyncio.CancelledError):
        await _conn(tmp_path)._guard(cancel())


# --- shutdown + close -------------------------------------------------------


async def test_shutdown_cancels_tasks_and_stops_writer(tmp_path):
    conn = _conn(tmp_path)
    conn.ensure_session()
    conn._writer_task = asyncio.create_task(conn._writer())

    async def forever():
        await asyncio.sleep(100)

    conn._spawn(forever())
    await asyncio.sleep(0)  # let the task register
    await conn._shutdown()
    assert conn._closing is True
    assert conn.session_id not in conn._sessions


async def test_close_idempotent(tmp_path):
    ws = FakeWS()
    conn = _conn(tmp_path, ws)
    await conn.close()
    assert ws.closed is True
    conn._closing = True
    ws.closed = False
    await conn.close()  # already closing -> skip
    assert ws.closed is False


# --- dispatch error-handler branches ----------------------------------------


async def test_settings_update_internal_error(tmp_path, monkeypatch):
    conn = _conn(tmp_path)
    conn.ensure_session()
    monkeypatch.setattr(
        "jarvis_backend.settings_service.apply_settings_update",
        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("crash")),
    )
    env = protocol.make("client.settings_update", {"llm": {"provider": "openai"}})
    await conn._on_settings_update(env)
    errs = [e for e in await _drain_outbox(conn) if e.type == "server.error"]
    assert errs and errs[0].payload["code"] == "internal"


async def test_agent_inspect_error_branch(tmp_path):
    conn = _conn(tmp_path)
    conn.ensure_session()
    await conn._on_agent_inspect(protocol.make("client.agent_inspect", {"role": "ghost-agent"}))
    errs = [e for e in await _drain_outbox(conn) if e.type == "server.error"]
    assert errs and errs[0].payload["code"] == "not_found"


async def test_author_internal_error(tmp_path, monkeypatch):
    conn = _conn(tmp_path)
    conn.ensure_session()

    def boom(agent, payload):
        raise RuntimeError("crash")

    env = protocol.make("client.author_skill", {"op": "create", "name": "x"})
    await conn._author(env, boom)
    errs = [e for e in await _drain_outbox(conn) if e.type == "server.error"]
    assert errs and errs[0].payload["code"] == "internal"


async def test_trace_get_no_trace_returns_empty(tmp_path):
    conn = _conn(tmp_path)
    conn.ensure_session()
    await conn._on_trace_get(protocol.make("client.trace_get", {"plan_id": "nope"}))
    traces = [e for e in await _drain_outbox(conn) if e.type == "server.trace"]
    assert traces and traces[0].payload["entries"] == []


async def test_barge_in_without_session_is_noop(tmp_path):
    conn = _conn(tmp_path)  # no ensure_session -> agent_session None
    await conn._on_barge_in(protocol.make("client.barge_in", {"reason": "x"}))
    assert conn.agent_session is None


async def test_trace_subscribe_non_dict_payload(tmp_path):
    conn = _conn(tmp_path)
    conn.ensure_session()
    conn._on_trace_subscribe(protocol.make("client.trace_subscribe", None))  # payload not a dict
    assert conn.agent_session.tracer.subscribed is True  # defaults to enabled


async def test_run_handles_connection_closed(tmp_path):
    class _CCWS(FakeWS):
        def __aiter__(self):
            return self

        async def __anext__(self):
            raise ConnectionClosed(None, None)

    conn = _conn(tmp_path, _CCWS())
    await conn.run()  # ConnectionClosed during iteration -> caught -> shutdown
    assert conn._closing is True


async def test_close_swallows_error(tmp_path):
    class _BadCloseWS(FakeWS):
        async def close(self):
            raise RuntimeError("close failed")

    conn = _conn(tmp_path, _BadCloseWS())
    await conn.close()  # error swallowed


async def test_shutdown_awaits_writer_that_errors(tmp_path):
    conn = _conn(tmp_path)

    async def bad_writer():
        raise RuntimeError("writer crashed")

    conn._writer_task = asyncio.create_task(bad_writer())
    await asyncio.sleep(0)
    await conn._shutdown()  # the await-writer except branch is exercised


async def test_start_server_with_existing_agent(config):
    from jarvis_backend.server import start_server

    agent = Agent.build(make_config_for(config), MockLLM())
    server, returned = await start_server(config, agent=agent)
    try:
        assert returned is agent  # provided agent reused (build branch skipped)
    finally:
        server.close()
        await server.wait_closed()


def make_config_for(config):
    return config


# --- _on_hello tolerant validation + raw handler functions ------------------


async def test_hello_tolerates_bad_payload(tmp_path):
    conn = _conn(tmp_path)
    await conn._on_hello(protocol.make("client.hello", {"capabilities": "not-a-dict"}))
    acks = [e for e in await _drain_outbox(conn) if e.type == "server.hello_ack"]
    assert acks  # validation failed -> default ClientHello, ack still emitted


async def test_shutdown_without_writer_task(tmp_path):
    conn = _conn(tmp_path)
    conn.ensure_session()
    await conn._shutdown()  # _writer_task is None -> skip-await branch
    assert conn._closing is True


async def test_handle_audio_connection_closed(tmp_path):
    from jarvis_backend.server import _handle_audio

    class _CC:
        def __aiter__(self):
            return self

        async def __anext__(self):
            raise ConnectionClosed(None, None)

    await _handle_audio(_CC())  # drains until close, swallows ConnectionClosed


async def test_handle_vision_paths(tmp_path):
    import json as _json

    from jarvis_backend.perception.buffer import encode_binary_vision_frame
    from jarvis_backend.server import _handle_vision

    conn = _conn(tmp_path)
    conn.ensure_session()

    def boom(*a, **k):
        raise RuntimeError("ingest failed")

    conn.agent_session.ingest_vision_frame = boom  # exercise the ingest-error branch
    sessions = {"S1": conn}

    class _Iter:
        def __init__(self, items):
            self.items = list(items)

        def __aiter__(self):
            return self

        async def __anext__(self):
            if self.items:
                return self.items.pop(0)
            raise StopAsyncIteration

    items = [
        _json.dumps({"foo": "no session field"}),  # dict control frame w/o session -> continue
        b"\x00",  # malformed binary -> dropped
        encode_binary_vision_frame({"frame_id": "F", "session": "S1"}, b"x"),  # -> ingest raises
        encode_binary_vision_frame({"frame_id": "G", "session": "unknown"}, b"x"),  # no matching session
    ]
    await _handle_vision(_Iter(items), "/vision?session=S1", sessions)  # must not raise


async def test_handle_vision_connection_closed(tmp_path):
    from jarvis_backend.server import _handle_vision

    class _CC:
        def __aiter__(self):
            return self

        async def __anext__(self):
            raise ConnectionClosed(None, None)

    await _handle_vision(_CC(), "/vision?session=S", {})  # outer ConnectionClosed handler
