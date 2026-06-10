"""The JarvisVR WebSocket server — the protocol endpoint for the Quest 3 client.

Listens on ``ws://<host>:<port><ws_path>`` (default ``0.0.0.0:8765/jarvis``),
speaks the v1 envelope from ``docs/PROTOCOL.md``, assigns the ``session`` in
``server.hello_ack``, echoes heartbeats, ignores unknown message types, and runs
one :class:`AgentSession` per connection.

Outbound messages are streamed through a per-connection queue + writer task so
frames never interleave even when background tasks (e.g. a timer interaction)
emit concurrently with an agent turn.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Coroutine, Optional
from urllib.parse import parse_qs, urlsplit

import websockets
from websockets.exceptions import ConnectionClosed
from websockets.server import WebSocketServerProtocol

from . import protocol
from .agent import Agent
from .agent.llm import create_llm
from .config import Config
from .perception import decode_binary_vision_frame

log = logging.getLogger("jarvis.server")


def _query_param(raw_path: str, key: str) -> Optional[str]:
    values = parse_qs(urlsplit(raw_path).query).get(key)
    return values[0] if values else None


class Connection:
    """Per-headset connection: envelope routing, session, outbound streaming."""

    def __init__(
        self,
        ws: WebSocketServerProtocol,
        agent: Agent,
        sessions: Optional[dict[str, "Connection"]] = None,
    ):
        self.ws = ws
        self.agent = agent
        # Shared registry so the parallel /vision endpoint can route frames here.
        self._sessions = sessions if sessions is not None else {}
        self.session_id: Optional[str] = None
        self.agent_session = None
        self._outbox: asyncio.Queue = asyncio.Queue()
        self._writer_task: Optional[asyncio.Task] = None
        self._tasks: set[asyncio.Task] = set()
        self._agent_lock = asyncio.Lock()
        self._closing = False

    # -- outbound -----------------------------------------------------------

    async def emit(self, type: str, payload: Any = None, *, reply_to: Optional[str] = None) -> None:
        env = protocol.make(type, payload, session=self.session_id, reply_to=reply_to)
        await self._outbox.put(env)

    async def _writer(self) -> None:
        try:
            while True:
                env = await self._outbox.get()
                if env is None:  # shutdown sentinel
                    return
                await self.ws.send(env.to_json())
        except ConnectionClosed:
            return
        except Exception:  # noqa: BLE001
            log.exception("writer task error")

    # -- session ------------------------------------------------------------

    def ensure_session(self):
        if self.session_id is None:
            self.session_id = protocol.new_id()
            self.agent_session = self.agent.create_session(self.session_id, self.emit)
            self._sessions[self.session_id] = self
            log.info("created session %s", self.session_id)
        return self.agent_session

    # -- lifecycle ----------------------------------------------------------

    async def run(self) -> None:
        self._writer_task = asyncio.create_task(self._writer())
        try:
            async for raw in self.ws:
                await self._dispatch(raw)
        except ConnectionClosed:
            pass
        finally:
            await self._shutdown()

    async def _shutdown(self) -> None:
        self._closing = True
        if self.session_id:
            self._sessions.pop(self.session_id, None)
        for task in list(self._tasks):
            task.cancel()
        await self._outbox.put(None)  # stop writer
        if self._writer_task is not None:
            try:
                await self._writer_task
            except Exception:  # noqa: BLE001
                pass
        log.info("session %s disconnected", self.session_id)

    async def close(self) -> None:
        if not self._closing:
            try:
                await self.ws.close()
            except Exception:  # noqa: BLE001
                pass

    def _spawn(self, coro: Coroutine) -> None:
        task = asyncio.create_task(self._guard(coro))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def _guard(self, coro: Coroutine) -> None:
        try:
            await coro
        except ConnectionClosed:
            pass
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001
            log.exception("agent task failed")

    # -- dispatch -----------------------------------------------------------

    async def _dispatch(self, raw: str | bytes) -> None:
        try:
            env = protocol.parse_inbound(raw)
        except protocol.BadEnvelope as exc:
            await self.emit(
                protocol.MsgType.SERVER_ERROR,
                protocol.ErrorPayload(
                    code=protocol.ErrorCode.BAD_ENVELOPE, message=str(exc)
                ),
            )
            return

        if not protocol.is_compatible_version(env.v):
            log.warning("incompatible protocol version %r (we are %s)", env.v, protocol.PROTOCOL_VERSION)

        t = env.type
        MT = protocol.MsgType

        if t == MT.CLIENT_HELLO:
            await self._on_hello(env)
        elif t == MT.CLIENT_HEARTBEAT:
            await self.emit(MT.SERVER_HEARTBEAT, {}, reply_to=env.id)
        elif t == MT.CLIENT_BYE:
            await self.close()
        elif t in (MT.USER_TEXT, MT.USER_VOICE_TRANSCRIPT):
            self._spawn(self._on_user_text(env))
        elif t == MT.USER_VOICE_PARTIAL:
            pass  # interim transcripts are ignored (final transcript drives the agent)
        elif t == MT.CLIENT_INTERACTION:
            self._spawn(self._on_interaction(env))
        elif t == MT.CLIENT_BARGE_IN:
            # User spoke over Jarvis (§5.14): cancel the active turn. Handled
            # inline (not behind the agent lock, which the live turn holds) so it
            # can interrupt immediately; idempotent when nothing is running.
            await self._on_barge_in(env)
        elif t == MT.CLIENT_SCENE:
            self._on_scene(env)
        # --- v1.1 perception (§8.3). Quiet, frequent streams update the buffer
        # inline; ones that may produce output run as guarded tasks. ---
        elif t == MT.PERCEPTION_VISION_FRAME:
            self.ensure_session().ingest_vision_frame(env.payload)
        elif t == MT.PERCEPTION_GAZE:
            self.ensure_session().ingest_gaze(env.payload)
        elif t == MT.PERCEPTION_SCENE_OBJECTS:
            self.ensure_session().ingest_scene_objects(env.payload)
        elif t == MT.PERCEPTION_STATE:
            self.ensure_session().ingest_state(env.payload)
        elif t == MT.PERCEPTION_AUDIO_EVENT:
            self.ensure_session()
            self._spawn(self.agent_session.handle_audio_event(env.payload))
        elif t == MT.PERCEPTION_AUDIO_SCENE:
            self.ensure_session()
            self._spawn(self.agent_session.handle_audio_scene(env.payload))
        # --- v1.1 settings (§5.15). Read is lock-free; update serializes with the
        # agent lock so it's safe even while a turn is in progress. ---
        elif t == MT.CLIENT_SETTINGS_GET:
            self._spawn(self._on_settings_get(env))
        elif t == MT.CLIENT_SETTINGS_UPDATE:
            self._spawn(self._on_settings_update(env))
        # --- v1.3 tracing + authoring (§10). Subscribe is a quick flag flip;
        # reads are lock-free; authoring writes serialize with the agent lock. ---
        elif t == MT.CLIENT_TRACE_SUBSCRIBE:
            self._on_trace_subscribe(env)
        elif t == MT.CLIENT_TRACE_GET:
            self._spawn(self._on_trace_get(env))
        elif t == MT.CLIENT_AGENT_INSPECT:
            self._spawn(self._on_agent_inspect(env))
        elif t == MT.CLIENT_AUTHOR_LIST:
            self._spawn(self._on_author_list(env))
        elif t == MT.CLIENT_AUTHOR_SKILL:
            self._spawn(self._on_author_skill(env))
        elif t == MT.CLIENT_AUTHOR_AGENT:
            self._spawn(self._on_author_agent(env))
        elif t == MT.CLIENT_ACK:
            log.debug("ack for %s", env.reply_to)
        elif t == MT.CLIENT_ERROR:
            log.warning("client error: %s", env.payload)
        else:
            # Forward-compatible: unknown types MUST be ignored (PROTOCOL §2).
            log.debug("ignoring unknown message type %r", t)

    async def _on_hello(self, env: protocol.Envelope) -> None:
        self.ensure_session()
        try:
            hello = protocol.ClientHello.model_validate(env.payload)
        except Exception:  # noqa: BLE001 - tolerate partial hellos
            hello = protocol.ClientHello()
        ack = protocol.HelloAck(
            session=self.session_id or protocol.new_id(),
            protocol_version=protocol.PROTOCOL_VERSION,
            agent=protocol.AgentInfo(name="Jarvis", model=self.agent.llm.model),
            tools=self.agent.tool_names(),
            voice=protocol.VoiceInfo(tts=True, wake_word="jarvis"),
            perception=protocol.PerceptionSupport(),  # v1.1 multimodal support
            widgets=self.agent.catalog.names(),
            orchestration=self.agent.config.orchestration_enabled,  # v1.2 multi-agent
            agents=self.agent.agent_roles(),
            tracing=self.agent.config.trace_enabled,  # v1.3 per-agent tracing
            authoring=True,  # v1.3 in-headset authoring
        )
        await self.emit(protocol.MsgType.SERVER_HELLO_ACK, ack, reply_to=env.id)
        log.info(
            "session %s hello device=%s locale=%s",
            self.session_id,
            hello.device,
            hello.locale,
        )

    async def _on_user_text(self, env: protocol.Envelope) -> None:
        session = self.ensure_session()
        try:
            payload = protocol.UserText.model_validate(env.payload)
        except Exception as exc:  # noqa: BLE001
            await self.emit(
                protocol.MsgType.SERVER_ERROR,
                protocol.ErrorPayload(code=protocol.ErrorCode.BAD_ENVELOPE, message=str(exc)),
            )
            return
        async with self._agent_lock:
            await session.run_turn(
                session.handle_user_text(
                    payload.text, attach_perception=payload.attach_perception
                )
            )

    async def _on_interaction(self, env: protocol.Envelope) -> None:
        session = self.ensure_session()
        async with self._agent_lock:
            await session.run_turn(session.handle_interaction(env.payload))

    async def _on_barge_in(self, env: protocol.Envelope) -> None:
        # No session yet -> nothing to cancel (idempotent no-op, §5.14).
        session = self.agent_session
        if session is None:
            return
        reason = env.payload.get("reason") if isinstance(env.payload, dict) else None
        await session.barge_in(reason)

    def _on_scene(self, env: protocol.Envelope) -> None:
        session = self.ensure_session()
        session.state.store["scene"] = env.payload

    # -- settings (§5.15) ---------------------------------------------------

    async def _on_settings_get(self, env: protocol.Envelope) -> None:
        from .settings_service import build_server_settings

        self.ensure_session()
        await self.emit(
            protocol.MsgType.SERVER_SETTINGS,
            build_server_settings(self.agent.config),
            reply_to=env.id,
        )

    async def _on_settings_update(self, env: protocol.Envelope) -> None:
        from .settings_service import SettingsError, apply_settings_update

        self.ensure_session()
        config = self.agent.config
        # Serialize with turns: hot-swap only happens between turns (safe), and
        # waiting here doesn't block the read loop (this runs as a guarded task).
        async with self._agent_lock:
            try:
                settings = apply_settings_update(
                    self.agent,
                    env.payload if isinstance(env.payload, dict) else {},
                    env_path=config.env_path,
                    do_validate=config.settings_validate,
                )
            except SettingsError as exc:
                await self.emit(
                    protocol.MsgType.SERVER_ERROR,
                    protocol.ErrorPayload(code=exc.code, message=exc.message),
                    reply_to=env.id,
                )
                return
            except Exception as exc:  # noqa: BLE001 - never crash the connection
                log.exception("settings_update failed")
                await self.emit(
                    protocol.MsgType.SERVER_ERROR,
                    protocol.ErrorPayload(
                        code=protocol.ErrorCode.INTERNAL, message=f"settings error: {exc}"
                    ),
                    reply_to=env.id,
                )
                return
        await self.emit(protocol.MsgType.SERVER_SETTINGS, settings, reply_to=env.id)

    # -- tracing + authoring (§10) ------------------------------------------

    def _on_trace_subscribe(self, env: protocol.Envelope) -> None:
        session = self.ensure_session()
        enabled = True
        if isinstance(env.payload, dict):
            enabled = bool(env.payload.get("enabled", True))
        session.tracer.subscribed = enabled
        log.debug("session %s trace streaming=%s", self.session_id, enabled)

    async def _on_trace_get(self, env: protocol.Envelope) -> None:
        session = self.ensure_session()
        plan_id = env.payload.get("plan_id") if isinstance(env.payload, dict) else None
        trace = session.tracer.get(plan_id)
        if trace is None:
            payload = protocol.ServerTrace(plan_id=plan_id or "", goal="", agents=[], entries=[])
        else:
            payload = trace.to_server_trace()
        await self.emit(protocol.MsgType.SERVER_TRACE, payload, reply_to=env.id)

    async def _on_agent_inspect(self, env: protocol.Envelope) -> None:
        from .agent.authoring import AuthoringError, agent_info

        session = self.ensure_session()
        p = env.payload if isinstance(env.payload, dict) else {}
        try:
            info = agent_info(
                self.agent, role=p.get("role"), agent_id=p.get("agent_id"), tracer=session.tracer
            )
        except AuthoringError as exc:
            await self.emit(
                protocol.MsgType.SERVER_ERROR,
                protocol.ErrorPayload(code=exc.code, message=exc.message),
                reply_to=env.id,
            )
            return
        await self.emit(protocol.MsgType.SERVER_AGENT_INFO, info, reply_to=env.id)

    async def _on_author_list(self, env: protocol.Envelope) -> None:
        from .agent.authoring import build_server_authoring

        self.ensure_session()
        await self.emit(
            protocol.MsgType.SERVER_AUTHORING, build_server_authoring(self.agent), reply_to=env.id
        )

    async def _on_author_skill(self, env: protocol.Envelope) -> None:
        from .agent.authoring import author_skill

        await self._author(env, author_skill)

    async def _on_author_agent(self, env: protocol.Envelope) -> None:
        from .agent.authoring import author_agent

        await self._author(env, author_agent)

    async def _author(self, env: protocol.Envelope, fn) -> None:
        from .agent.authoring import AuthoringError

        self.ensure_session()
        payload = env.payload if isinstance(env.payload, dict) else {}
        # Serialize authoring with turns: it mutates the registry/roster.
        async with self._agent_lock:
            try:
                result = fn(self.agent, payload)
            except AuthoringError as exc:
                await self.emit(
                    protocol.MsgType.SERVER_ERROR,
                    protocol.ErrorPayload(code=exc.code, message=exc.message),
                    reply_to=env.id,
                )
                return
            except Exception as exc:  # noqa: BLE001 - never crash the connection
                log.exception("authoring failed")
                await self.emit(
                    protocol.MsgType.SERVER_ERROR,
                    protocol.ErrorPayload(
                        code=protocol.ErrorCode.INTERNAL, message=f"authoring error: {exc}"
                    ),
                    reply_to=env.id,
                )
                return
        await self.emit(protocol.MsgType.SERVER_AUTHORING, result, reply_to=env.id)


def _make_handler(agent: Agent, config: Config):
    audio_path = "/audio"
    vision_path = "/vision"
    jarvis_path = config.ws_path
    # Shared session registry: lets the /vision endpoint route frames to the
    # matching /jarvis connection's perception buffer.
    sessions: dict[str, Connection] = {}

    async def handler(ws: WebSocketServerProtocol) -> None:
        raw_path = getattr(ws, "path", jarvis_path) or jarvis_path
        path = raw_path.split("?", 1)[0]
        if path.startswith(vision_path):
            await _handle_vision(ws, raw_path, sessions)
            return
        if path.startswith(audio_path):
            await _handle_audio(ws)
            return
        if path.rstrip("/") not in {jarvis_path.rstrip("/"), ""}:
            log.warning("connection on unexpected path %r; serving as %s", path, jarvis_path)
        conn = Connection(ws, agent, sessions)
        await conn.run()

    return handler


async def _handle_audio(ws: WebSocketServerProtocol) -> None:
    # Optional binary PCM endpoint (PROTOCOL §1). Not implemented here; the JSON
    # main channel carries transcripts/speech. Drain frames so the client's
    # connection stays healthy.
    log.info("audio endpoint connected (binary PCM not implemented; draining)")
    try:
        async for _ in ws:
            pass
    except ConnectionClosed:
        pass


async def _handle_vision(
    ws: WebSocketServerProtocol, raw_path: str, sessions: dict[str, Connection]
) -> None:
    """Ingest length-prefixed binary vision frames (PROTOCOL §8.2).

    The session is identified by ``?session=<id>`` on the URL, an initial JSON
    text frame ``{"session": "<id>"}``, or a ``session`` field in each binary
    frame's header. Frames are pushed into that session's perception buffer.
    """
    session_id = _query_param(raw_path, "session")
    frames = 0
    log.info("vision endpoint connected (session=%s)", session_id)
    try:
        async for msg in ws:
            if isinstance(msg, str):
                # Control/attach frame.
                try:
                    obj = json.loads(msg)
                except (ValueError, TypeError):
                    continue
                if isinstance(obj, dict) and obj.get("session"):
                    session_id = obj["session"]
                continue
            try:
                header, image = decode_binary_vision_frame(msg)
            except Exception as exc:  # noqa: BLE001
                log.warning("dropping malformed vision frame (%s)", exc)
                continue
            sid = header.get("session") or session_id
            conn = sessions.get(sid) if sid else None
            if conn is None or conn.agent_session is None:
                continue  # no matching /jarvis session yet -> drop
            header.setdefault("transport", "binary")
            try:
                conn.agent_session.ingest_vision_frame(header, image)
                frames += 1
            except Exception:  # noqa: BLE001
                log.exception("failed to ingest vision frame")
    except ConnectionClosed:
        pass
    log.info("vision endpoint disconnected (%d frames, session=%s)", frames, session_id)


async def start_server(config: Config, agent: Optional[Agent] = None):
    """Start the server and return ``(server, agent)`` without blocking.

    Useful for tests. ``run_server`` wraps this for the CLI entrypoint.
    """
    if agent is None:
        llm = create_llm(config)
        agent = Agent.build(config, llm)
    handler = _make_handler(agent, config)
    server = await websockets.serve(
        handler,
        config.host,
        config.port,
        ping_interval=20,
        ping_timeout=20,
        max_size=2**20,
    )
    return server, agent


async def run_server(config: Config) -> None:
    """Start the server and run until cancelled (CLI entrypoint)."""
    server, agent = await start_server(config)
    sockets = list(server.sockets or [])
    if sockets:
        host, port = sockets[0].getsockname()[:2]
    else:  # pragma: no cover - a bound server always has sockets
        host, port = config.host, config.port
    log.info("JarvisVR agent-backend listening on ws://%s:%s%s", host, port, config.ws_path)
    log.info("agent model=%s | tools=%s", agent.llm.model, ", ".join(agent.tool_names()))
    log.info("config: %s", config.summary())
    try:
        await asyncio.Future()  # run forever
    finally:
        server.close()
        await server.wait_closed()


__all__ = ["Connection", "start_server", "run_server"]
