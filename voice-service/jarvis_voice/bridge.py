"""WebSocket bridge: the voice front-end of the agent-backend.

Implements the JarvisVR v1.1 protocol (``docs/PROTOCOL.md``) as a *client*:

* sends ``client.hello`` advertising ``mic`` + ``speaker`` + ``ambient_audio``,
* keeps the connection alive with ``client.heartbeat`` every 5s,
* forwards STT results as ``user.voice_partial`` / ``user.voice_transcript``,
* speaks incoming ``agent.speech`` **and** ``agent.observation`` via TTS,
* starts/stops continuous ambient listening on ``perception.request`` and emits
  ``perception.audio_scene`` / ``perception.audio_event`` while active,
* signals ``client.barge_in`` when the user talks over Jarvis,
* ignores unknown message types (forward-compatible),
* reconnects with backoff.

The send/handle logic is decoupled from the transport so it is unit-testable with
a fake websocket (any object exposing async ``send`` + async iteration).
"""

from __future__ import annotations

import asyncio
import logging
import threading
from typing import Any, Optional

from . import protocol
from .ambient import AmbientCallbacks, AmbientListener, build_ambient
from .audio import audio_io_available
from .config import Config
from .pipeline import PipelineCallbacks, VoicePipeline, build_pipeline
from .protocol import Envelope, ProtocolError
from .tts import Speaker, create_speaker

log = logging.getLogger(__name__)


class VoiceBridge:
    """Bridges the local voice pipeline to the agent-backend over WebSocket."""

    def __init__(
        self,
        config: Config,
        pipeline: Optional[VoicePipeline] = None,
        speaker: Optional[Speaker] = None,
        connect: Optional[Any] = None,
    ) -> None:
        self.config = config
        self.pipeline = pipeline
        # Speaker used for agent.speech. Reuse the pipeline's if present.
        self.speaker = speaker or (pipeline.tts if pipeline else None) or create_speaker(config)
        self.session: Optional[str] = None
        self._connect = connect  # injectable for tests; defaults to websockets.connect
        self._outbox: "asyncio.Queue[Envelope]" = asyncio.Queue()
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        # v1.1 ambient perception
        self._ambient: Optional[AmbientListener] = None
        self._ambient_active = False

    # --- low-level send -----------------------------------------------------
    async def send(self, ws: Any, env: Envelope) -> None:
        await ws.send(env.to_json())

    async def send_hello(self, ws: Any) -> None:
        env = protocol.client_hello(
            mic=True,
            speaker=True,
            ambient_audio=not self.config.ambient_disabled,
            device=self.config.device_name,
            app_version=self.config.app_version,
            locale=self.config.locale,
        )
        log.info("→ client.hello (mic+speaker+ambient_audio)")
        await self.send(ws, env)

    def _enqueue(self, env: Envelope) -> None:
        """Queue an outbound envelope from any thread (mic/ambient callbacks)."""
        loop = self._loop
        if loop is not None and loop.is_running():
            loop.call_soon_threadsafe(self._outbox.put_nowait, env)
        else:  # tests / synchronous context: queue directly
            self._outbox.put_nowait(env)

    async def send_heartbeat(self, ws: Any) -> None:
        await self.send(ws, protocol.client_heartbeat(self.session))

    async def send_bye(self, ws: Any) -> None:
        try:
            await self.send(ws, protocol.client_bye(self.session))
        except Exception:  # pragma: no cover - best effort on shutdown
            pass

    async def send_transcript(
        self, ws: Any, text: str, confidence: float = 1.0, final: bool = True
    ) -> None:
        """Emit ``user.voice_transcript`` (final) or ``user.voice_partial``."""
        if not text:
            return
        if final:
            env = protocol.voice_transcript(text, confidence, session=self.session)
            log.info("→ user.voice_transcript %r (conf=%.2f)", text, confidence)
        else:
            env = protocol.voice_partial(text, confidence, session=self.session)
            log.debug("→ user.voice_partial %r", text)
        await self.send(ws, env)

    # --- inbound handling ---------------------------------------------------
    async def handle_raw(self, ws: Any, raw: Any) -> Optional[Envelope]:
        """Parse + dispatch one inbound frame. Returns the Envelope (or None)."""
        try:
            env = Envelope.from_json(raw)
        except ProtocolError as exc:
            log.warning("dropping bad frame: %s", exc)
            try:
                await self.send(ws, protocol.client_error(exc.code, str(exc), session=self.session))
            except Exception:  # pragma: no cover
                pass
            return None

        if not env.is_version_compatible():
            log.warning("incompatible protocol version %s (ignoring)", env.v)

        t = env.type
        if t == protocol.SERVER_HELLO_ACK:
            self.session = env.payload.get("session")
            agent = env.payload.get("agent", {})
            log.info(
                "← server.hello_ack (session=%s, agent=%s)",
                self.session,
                agent.get("name") if isinstance(agent, dict) else agent,
            )
        elif t == protocol.SERVER_HEARTBEAT:
            log.debug("← server.heartbeat")
        elif t == protocol.AGENT_SPEECH:
            await self._handle_speech(env, kind="agent.speech")
        elif t == protocol.AGENT_OBSERVATION:
            await self._handle_speech(env, kind="agent.observation")
        elif t == protocol.PERCEPTION_REQUEST:
            await self._handle_perception_request(ws, env)
        elif t == protocol.AGENT_THINKING:
            log.info(
                "← agent.thinking: %s",
                env.payload.get("label") or env.payload.get("stage"),
            )
        elif t == protocol.AGENT_TRANSCRIPT:
            log.debug("← agent.transcript: %s", env.text)
        elif t == protocol.SERVER_ERROR:
            log.warning("← server.error: %s", env.payload)
        else:
            # Unknown types (e.g. holo.*) are not our concern — ignore per spec.
            log.debug("ignoring %s", t)
        return env

    async def _handle_speech(self, env: Envelope, kind: str = "agent.speech") -> None:
        """Speak ``agent.speech`` or ``agent.observation`` text via TTS."""
        text = env.text or ""
        final = bool(env.payload.get("final", True))
        log.info("← %s %r (final=%s)", kind, text, final)
        if not text:
            return
        # TTS may block (synthesis/playback) — run it off the event loop.
        loop = asyncio.get_running_loop()
        target = self.pipeline.speak if self.pipeline else self.speaker.speak
        await loop.run_in_executor(None, target, text)

    async def _handle_perception_request(self, ws: Any, env: Envelope) -> None:
        """Start/stop/snapshot the ambient_audio stream (other streams ignored)."""
        stream = env.payload.get("stream")
        action = str(env.payload.get("action", "")).lower()
        if stream != "ambient_audio":
            # vision/gaze/scene_objects belong to the unity-client — not us.
            log.debug("ignoring perception.request for stream=%s", stream)
            return
        if self.config.ambient_disabled:
            log.info("perception.request ambient_audio ignored (JARVIS_AMBIENT=off)")
            await self.send(ws, protocol.perception_state(ambient_audio_active=False,
                                                          session=self.session))
            return

        reason = env.payload.get("reason")
        if action in ("start", "set"):
            self.start_ambient()
            log.info("← perception.request: ambient_audio START (%s)", reason or "")
        elif action == "stop":
            self.stop_ambient()
            log.info("← perception.request: ambient_audio STOP")
        elif action == "once":
            log.info("← perception.request: ambient_audio ONCE (%s)", reason or "")
            self._emit_ambient_snapshot()
        else:
            log.warning("perception.request: unknown action %r", action)

        await self.send(ws, protocol.perception_state(
            ambient_audio_active=self._ambient_active, session=self.session))

    # --- ambient listening --------------------------------------------------
    def _ensure_ambient(self) -> AmbientListener:
        if self._ambient is None:
            cb = AmbientCallbacks(
                on_audio_scene=lambda sc: self._enqueue(
                    protocol.audio_scene(
                        sc.ambient_transcript, sc.speaker, sc.sounds,
                        sc.loudness_db, sc.window_ms, session=self.session,
                    )
                ),
                on_audio_event=lambda ev: self._enqueue(
                    protocol.audio_event(
                        ev.label, ev.confidence, ev.loudness_db, ev.ts,
                        session=self.session,
                    )
                ),
            )
            self._ambient = build_ambient(self.config, cb)
        return self._ambient

    def start_ambient(self) -> None:
        self._ensure_ambient()
        self._ambient_active = True
        if not audio_io_available():
            log.warning("ambient listening active but no mic backend; awaiting frames")

    def stop_ambient(self) -> None:
        self._ambient_active = False

    def _emit_ambient_snapshot(self) -> None:
        self._ensure_ambient().snapshot()

    # --- loops --------------------------------------------------------------
    async def recv_loop(self, ws: Any) -> None:
        async for raw in ws:
            await self.handle_raw(ws, raw)

    async def heartbeat_loop(self, ws: Any) -> None:
        try:
            while True:
                await asyncio.sleep(protocol.HEARTBEAT_INTERVAL_S)
                await self.send_heartbeat(ws)
        except asyncio.CancelledError:  # pragma: no cover - shutdown path
            raise

    async def sender_loop(self, ws: Any) -> None:
        """Drain queued outbound envelopes (transcripts) produced by the pipeline."""
        while True:
            env = await self._outbox.get()
            try:
                await self.send(ws, env)
            finally:
                self._outbox.task_done()

    async def capture_loop(self, ws: Any) -> None:
        """Run mic capture in a thread, feeding the pipeline; enqueue transcripts.

        No-op (idles) if there's no pipeline or no audio backend; the bridge can
        still receive + speak ``agent.speech`` in that case.
        """
        if self.pipeline is None:
            return
        if not audio_io_available():
            log.warning("no audio backend; voice capture disabled (speak-only bridge)")
            return

        from .audio import MicStream  # local import keeps base import light

        stop = threading.Event()

        # Pipeline -> backend wiring (transcripts + barge-in), enqueued thread-safely.
        self.pipeline.cb.on_partial = lambda text: self._enqueue(
            protocol.voice_partial(text, 0.0, session=self.session)
        )
        self.pipeline.cb.on_transcript = lambda res: self._enqueue(
            protocol.voice_transcript(res.text, res.confidence, session=self.session)
        )
        self.pipeline.cb.on_barge_in = lambda: self._enqueue(
            protocol.client_barge_in(session=self.session)
        )

        def _run_mic() -> None:
            try:
                with MicStream(
                    sample_rate=self.config.sample_rate,
                    frame_samples=self.config.samples_per_frame,
                    input_device=self.config.input_device,
                ) as mic:
                    # Fan each frame out to the wake/STT pipeline and (when active)
                    # the ambient listener, so both hear the room simultaneously.
                    for frame in mic:
                        if stop.is_set():  # pragma: no cover - shutdown path
                            break
                        self.pipeline.process_frame(frame)
                        amb = self._ambient
                        if amb is not None and self._ambient_active:
                            amb.process_frame(frame)
            except Exception as exc:  # pragma: no cover - hardware dependent
                log.warning("mic capture stopped: %s", exc)

        loop = asyncio.get_running_loop()
        try:
            await loop.run_in_executor(None, _run_mic)
        except asyncio.CancelledError:  # pragma: no cover - shutdown path
            # Disconnect/shutdown: signal the mic thread to wind down cleanly so
            # it doesn't leak across reconnects.
            stop.set()
            raise

    async def run(self, ws: Any) -> None:
        """Handshake then run until the socket closes (recv_loop returns).

        The session lifetime is tied to ``recv_loop``; heartbeat/sender/capture are
        *support* tasks. (A speak-only bridge has no mic, so ``capture_loop`` returns
        immediately — it must not be allowed to end the session.)
        """
        self._loop = asyncio.get_running_loop()
        await self.send_hello(ws)
        if self.config.ambient_autostart:
            log.info("ambient listening autostart (JARVIS_AMBIENT=on)")
            self.start_ambient()
        support = [
            asyncio.create_task(self.heartbeat_loop(ws), name="heartbeat"),
            asyncio.create_task(self.sender_loop(ws), name="sender"),
            asyncio.create_task(self.capture_loop(ws), name="capture"),
        ]
        try:
            await self.recv_loop(ws)  # ends when the socket closes
        finally:
            for task in support:
                task.cancel()
            await asyncio.gather(*support, return_exceptions=True)
            await self.send_bye(ws)

    async def connect_and_run(self, max_retries: int = 0) -> None:
        """Connect to the backend and run, reconnecting with backoff.

        ``max_retries=0`` means retry forever. Used by the ``bridge`` CLI command.
        """
        connect = self._connect
        if connect is None:
            try:
                import websockets  # base dependency
            except Exception as exc:  # pragma: no cover - base dep should exist
                raise RuntimeError(f"websockets not installed: {exc}") from exc
            connect = websockets.connect

        url = self.config.backend_url
        attempt = 0
        backoff = 1.0
        while True:
            attempt += 1
            try:
                log.info("connecting to %s (attempt %d)…", url, attempt)
                async with connect(url) as ws:
                    backoff = 1.0  # reset on success
                    await self.run(ws)
                log.info("disconnected from backend")
            except asyncio.CancelledError:  # pragma: no cover - shutdown
                raise
            except Exception as exc:
                log.warning("bridge connection error: %s", exc)
            if max_retries and attempt >= max_retries:
                log.error("giving up after %d attempts", attempt)
                return
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 30.0)


def build_bridge(config: Config, with_capture: bool = True) -> VoiceBridge:
    """Build a bridge (and its pipeline) from config."""
    pipeline = build_pipeline(config) if with_capture else None
    return VoiceBridge(config, pipeline=pipeline)
