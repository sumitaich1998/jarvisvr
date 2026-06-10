"""JarvisVR protocol-conformance harness.

A mock WS client that drives a scripted multi-turn conversation and asserts that
EVERY received frame validates against the shared-protocol JSON Schemas (via the
``jarvis_protocol`` binding), and that holo objects validate against
holo-tools/registry.json when it is available.

Scenario:
  1. client.hello                       -> server.hello_ack (capture session)
  2. client.heartbeat                   -> server.heartbeat
  3. "show me the weather in tokyo"     -> thinking* + speech + holo.spawn(weather)
  4. "start a 5 minute timer"           -> thinking* + speech + holo.spawn(timer)
  5. tap the timer                      -> holo.update
  6. client.bye

Exit code is non-zero on any violation.

Usage:
  python harness.py --url ws://127.0.0.1:8765/jarvis
  JARVIS_BACKEND_URL=ws://host:8765/jarvis python harness.py
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import logging
import os
import sys
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

import websockets

import jarvis_protocol as jp
from holo_tools import HoloToolsValidator

# A tiny but real JPEG SOI/APP0 magic, base64-encoded — enough for a fake frame.
_FAKE_JPEG = bytes([0xFF, 0xD8, 0xFF, 0xE0]) + b"\x00" * 28
_FAKE_JPEG_B64 = base64.b64encode(_FAKE_JPEG).decode("ascii")

LOG = logging.getLogger("jarvis.e2e")

MT = jp.MessageType


@dataclass
class Report:
    sent: int = 0
    received: int = 0
    violations: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    steps: List[str] = field(default_factory=list)
    seen_types: List[str] = field(default_factory=list)

    def ok(self) -> bool:
        return not self.violations


def _is_done(doc: Dict[str, Any]) -> bool:
    return doc.get("type") == MT.AGENT_THINKING and (doc.get("payload") or {}).get("stage") == "done"


def _first(docs: List[Dict[str, Any]], type_name: str) -> Optional[Dict[str, Any]]:
    return next((d for d in docs if d.get("type") == type_name), None)


class ConformanceClient:
    def __init__(self, ws, report: Report, holo: HoloToolsValidator, *, recv_timeout: float = 5.0):
        self.ws = ws
        self.report = report
        self.holo = holo
        self.recv_timeout = recv_timeout
        self.session: Optional[str] = None

    async def send(self, type_: str, payload: Any, *, reply_to: Optional[str] = None) -> Dict[str, Any]:
        msg = jp.new_message(type_, payload, session=self.session, reply_to=reply_to)
        # The client must be conformant too.
        for err in jp.iter_errors(msg):
            self.report.violations.append(f"OUTGOING {type_}: {err}")
        await self.ws.send(jp.encode(msg))
        self.report.sent += 1
        LOG.info("-> %s", type_)
        return jp.to_dict(msg)

    def _check(self, raw: Any) -> Dict[str, Any]:
        doc = jp.to_dict(raw)
        self.report.received += 1
        self.report.seen_types.append(doc.get("type", "?"))
        # 1) shared-protocol schema conformance (strict: known types only)
        for err in jp.iter_errors(doc, allow_unknown_types=False):
            self.report.violations.append(f"RECV {doc.get('type', '?')}: {err}")
        # 2) holo-tools conformance for spawned objects
        if doc.get("type") == MT.HOLO_SPAWN:
            errors, warnings = self.holo.validate_holo(doc.get("payload") or {})
            self.report.violations.extend(f"holo-tools: {m}" for m in errors)
            self.report.warnings.extend(f"holo-tools: {m}" for m in warnings)
        LOG.info("<- %s", doc.get("type"))
        return doc

    async def recv(self) -> Dict[str, Any]:
        raw = await asyncio.wait_for(self.ws.recv(), self.recv_timeout)
        return self._check(raw)

    async def recv_until(
        self, predicate: Callable[[Dict[str, Any]], bool], *, what: str, max_msgs: int = 25
    ) -> List[Dict[str, Any]]:
        docs: List[Dict[str, Any]] = []
        for _ in range(max_msgs):
            try:
                doc = await self.recv()
            except asyncio.TimeoutError:
                self.report.violations.append(f"timeout waiting for {what}")
                return docs
            docs.append(doc)
            if predicate(doc):
                return docs
        self.report.violations.append(f"did not observe {what} within {max_msgs} messages")
        return docs


async def run_conformance(url: str, *, strict_props: bool = False, recv_timeout: float = 5.0) -> Report:
    report = Report()
    holo = HoloToolsValidator.load(strict_props=strict_props)
    report.steps.append(f"holo-tools available: {holo.available}")
    LOG.info("connecting to %s", url)

    async with websockets.connect(url) as ws:
        client = ConformanceClient(ws, report, holo, recv_timeout=recv_timeout)

        # 1) handshake
        await client.send(MT.CLIENT_HELLO, jp.ClientHello(
            device="quest3",
            app_version="0.1.0",
            capabilities=jp.Capabilities(passthrough=True, hand_tracking=True, mic=True, speaker=True, scene_understanding=True),
            locale="en-US",
        ))
        acks = await client.recv_until(lambda d: d.get("type") == MT.SERVER_HELLO_ACK, what="server.hello_ack")
        hello_ack = _first(acks, MT.SERVER_HELLO_ACK)
        if hello_ack:
            client.session = (hello_ack.get("payload") or {}).get("session")
            report.steps.append(f"session = {client.session}")
        if not client.session:
            report.violations.append("server.hello_ack did not assign a session")

        # 2) heartbeat
        await client.send(MT.CLIENT_HEARTBEAT, jp.Heartbeat())
        await client.recv_until(lambda d: d.get("type") == MT.SERVER_HEARTBEAT, what="server.heartbeat")

        # 3) weather turn
        await client.send(MT.USER_VOICE_TRANSCRIPT, jp.TextInput(text="show me the weather in tokyo", confidence=0.96))
        weather = await client.recv_until(_is_done, what="weather turn (agent.thinking done)")
        if _first(weather, MT.AGENT_SPEECH) is None:
            report.violations.append("weather turn: no agent.speech")
        weather_spawn = _first(weather, MT.HOLO_SPAWN)
        if weather_spawn is None:
            report.violations.append("weather turn: no holo.spawn")
        else:
            report.steps.append(f"weather widget = {(weather_spawn.get('payload') or {}).get('widget_type')}")
            await client.send(MT.CLIENT_ACK, jp.Ack(), reply_to=weather_spawn["id"])

        # 4) timer turn
        await client.send(MT.USER_TEXT, jp.TextInput(text="start a 5 minute timer"))
        timer = await client.recv_until(_is_done, what="timer turn (agent.thinking done)")
        if _first(timer, MT.AGENT_SPEECH) is None:
            report.violations.append("timer turn: no agent.speech")
        timer_spawn = _first(timer, MT.HOLO_SPAWN)
        timer_object_id = None
        if timer_spawn is None:
            report.violations.append("timer turn: no holo.spawn")
        else:
            timer_object_id = (timer_spawn.get("payload") or {}).get("object_id")
            report.steps.append(f"timer widget = {(timer_spawn.get('payload') or {}).get('widget_type')}")
            await client.send(MT.CLIENT_ACK, jp.Ack(), reply_to=timer_spawn["id"])

        # 5) tap the timer
        if timer_object_id:
            await client.send(MT.CLIENT_INTERACTION, jp.ClientInteraction(
                object_id=timer_object_id, widget_type="timer", action="tap", element="pause_button", hand="right",
            ))
            tap = await client.recv_until(_is_done, what="interaction response (agent.thinking done)")
            if _first(tap, MT.HOLO_UPDATE) is None:
                report.violations.append("interaction: no holo.update")
        else:
            report.steps.append("skipped tap (no timer object id)")

        # 6) graceful bye
        await client.send(MT.CLIENT_BYE, jp.ClientBye(reason="conformance run complete"))

    return report


def _vision_url(url: str) -> str:
    """Derive the /vision endpoint from a /jarvis URL."""
    head = url.split("?", 1)[0].rstrip("/")
    if head.endswith("/jarvis"):
        head = head[: -len("/jarvis")]
    else:
        head = head.rsplit("/", 1)[0] if "/" in head.split("://", 1)[-1] else head
    return head + "/vision"


async def _exercise_vision_binary(url: str, report: Report) -> None:
    """Send one §8.2 length-prefixed binary vision frame on /vision."""
    header = {
        "frame_id": jp.new_id(),
        "camera": "rgb_center",
        "format": "jpeg",
        "width": 64,
        "height": 64,
        "transport": "binary",
        "seq": 1,
        "ts_capture": jp.now_ms(),
        "pose": {"position": [0, 1.6, 0], "rotation": [0, 0, 0, 1]},
    }
    # The binary header must itself be a conformant vision_frame payload.
    for err in jp.iter_errors(jp.new_message(MT.PERCEPTION_VISION_FRAME, header)):  # pragma: no cover
        report.violations.append(f"OUTGOING /vision header: {err}")  # defensive: header is built valid
    header_bytes = json.dumps(header).encode("utf-8")
    frame = len(header_bytes).to_bytes(4, "big") + header_bytes + _FAKE_JPEG
    vurl = _vision_url(url)
    try:
        async with websockets.connect(vurl, max_size=8 * 1024 * 1024) as vws:
            await vws.send(frame)
            await asyncio.sleep(0.15)  # let the server ingest before we close
        report.sent += 1
        report.steps.append(f"/vision: sent 1 length-prefixed binary frame ({len(frame)} bytes)")
    except Exception as exc:  # noqa: BLE001
        report.violations.append(f"/vision transport failed at {vurl}: {exc}")


async def run_multimodal_conformance(url: str, *, strict_props: bool = False, recv_timeout: float = 5.0) -> Report:
    """v1.1 scenario: stream a vision frame, ask 'what is this?', expect a vision turn."""
    report = Report()
    holo = HoloToolsValidator.load(strict_props=strict_props)
    report.steps.append(f"holo-tools available: {holo.available}")

    # 1) Exercise the /vision binary transport (separate connection, §8.2).
    await _exercise_vision_binary(url, report)

    # 2) The multimodal turn on the main /jarvis channel.
    async with websockets.connect(url, max_size=8 * 1024 * 1024) as ws:
        client = ConformanceClient(ws, report, holo, recv_timeout=recv_timeout)

        await client.send(MT.CLIENT_HELLO, jp.ClientHello(
            device="quest3",
            app_version="0.1.0",
            capabilities=jp.Capabilities(
                passthrough=True, hand_tracking=True, mic=True, speaker=True,
                camera_passthrough=True, ambient_audio=True, eye_tracking=False,
            ),
            locale="en-US",
        ))
        acks = await client.recv_until(lambda d: d.get("type") == MT.SERVER_HELLO_ACK, what="server.hello_ack")
        hello_ack = _first(acks, MT.SERVER_HELLO_ACK)
        if hello_ack:
            client.session = (hello_ack.get("payload") or {}).get("session")
        if not client.session:
            report.violations.append("server.hello_ack did not assign a session")

        # Client streams perception inline (no reply expected): a frame + detected objects.
        await client.send(MT.PERCEPTION_VISION_FRAME, jp.VisionFrame(
            frame_id=jp.new_id(), camera="rgb_center", format="jpeg", width=1024, height=1024,
            quality=70, transport="inline", data=_FAKE_JPEG_B64, seq=1, ts_capture=jp.now_ms(),
            pose=jp.Pose(position=[0, 1.6, 0], rotation=[0, 0, 0, 1]),
        ))
        await client.send(MT.PERCEPTION_SCENE_OBJECTS, jp.SceneObjects(objects=[
            jp.SceneObject(label="coffee mug", confidence=0.78, bbox=[120, 80, 64, 64], position=[0.3, 0.8, 0.7], anchor="world"),
        ]))

        # The user asks about the room; perception is auto-attached.
        await client.send(MT.USER_VOICE_TRANSCRIPT, jp.TextInput(
            text="hey jarvis, what is this on my desk?", confidence=0.95, attach_perception=True,
        ))

        # The vision turn ends with perception.request{action:stop}.
        def _is_vision_stop(d: Dict[str, Any]) -> bool:
            return d.get("type") == MT.PERCEPTION_REQUEST and (d.get("payload") or {}).get("action") == "stop"

        turn = await client.recv_until(_is_vision_stop, what="vision turn (perception.request stop)")

        # Assertions for the multimodal turn.
        if not any(d.get("type") == MT.PERCEPTION_REQUEST and (d.get("payload") or {}).get("action") == "start" for d in turn):
            report.violations.append("vision turn: no perception.request{start}")
        if not any(d.get("type") == MT.AGENT_THINKING and (d.get("payload") or {}).get("stage") == "perceiving" for d in turn):
            report.violations.append("vision turn: no agent.thinking{perceiving}")

        obs = _first(turn, MT.AGENT_OBSERVATION)
        if obs is None:
            report.violations.append("vision turn: no agent.observation")
        else:
            report.steps.append(f"observation = {(obs.get('payload') or {}).get('text')!r}")

        spawn = _first(turn, MT.HOLO_SPAWN)
        if spawn is None:
            report.violations.append("vision turn: no holo.spawn")
        else:
            widget = (spawn.get("payload") or {}).get("widget_type")
            report.steps.append(f"annotation widget = {widget}")
            if widget != "vision_annotation":
                report.violations.append(f"vision turn: expected holo.spawn vision_annotation, got {widget!r}")
            await client.send(MT.CLIENT_ACK, jp.Ack(), reply_to=spawn["id"])

        if _first(turn, MT.AGENT_SPEECH) is None:
            report.violations.append("vision turn: no agent.speech")

        await client.send(MT.CLIENT_BYE, jp.ClientBye(reason="multimodal run complete"))

    return report


async def run_barge_in_conformance(url: str, *, strict_props: bool = False, recv_timeout: float = 5.0) -> Report:
    """§5.14: send a user turn, then client.barge_in; the backend must stop
    gracefully (no protocol error / no server.error) and stay responsive."""
    report = Report()
    holo = HoloToolsValidator.load(strict_props=strict_props)
    report.steps.append(f"holo-tools available: {holo.available}")

    async with websockets.connect(url) as ws:
        client = ConformanceClient(ws, report, holo, recv_timeout=recv_timeout)

        await client.send(MT.CLIENT_HELLO, jp.ClientHello(
            device="quest3", app_version="0.1.0",
            capabilities=jp.Capabilities(mic=True, speaker=True),
            locale="en-US",
        ))
        acks = await client.recv_until(lambda d: d.get("type") == MT.SERVER_HELLO_ACK, what="server.hello_ack")
        hello_ack = _first(acks, MT.SERVER_HELLO_ACK)
        if hello_ack:
            client.session = (hello_ack.get("payload") or {}).get("session")
        if not client.session:
            report.violations.append("server.hello_ack did not assign a session")

        # Start a turn, then immediately interrupt it (user spoke over Jarvis).
        await client.send(MT.USER_VOICE_TRANSCRIPT, jp.TextInput(text="show me the weather in tokyo", confidence=0.95))
        await client.send(MT.CLIENT_BARGE_IN, jp.ClientBargeIn(reason="user_speech"))

        # The connection must remain healthy: a heartbeat still round-trips. The
        # recv loop drains + schema-validates any in-flight turn frames first, and
        # the server's outbox is FIFO so the heartbeat echo arrives last.
        await client.send(MT.CLIENT_HEARTBEAT, jp.Heartbeat())
        drained = await client.recv_until(
            lambda d: d.get("type") == MT.SERVER_HEARTBEAT,
            what="server.heartbeat after barge_in",
            max_msgs=40,
        )
        if any(d.get("type") == MT.SERVER_ERROR for d in drained):
            report.violations.append("barge_in produced a server.error")
        report.steps.append(f"frames drained after barge_in: {len(drained)}")

        await client.send(MT.CLIENT_BYE, jp.ClientBye(reason="barge_in run complete"))

    return report


async def run_settings_conformance(url: str, *, strict_props: bool = False, recv_timeout: float = 5.0) -> Report:
    """§5.15: settings_get returns a conformant catalog; settings_update changes
    the provider/model and reports key_set:true — and NO api_key ever appears in
    any received frame."""
    report = Report()
    holo = HoloToolsValidator.load(strict_props=strict_props)
    report.steps.append(f"holo-tools available: {holo.available}")
    secret = "sk-e2e-SECRET-key"  # what we send; must never come back
    all_docs: List[Dict[str, Any]] = []

    async with websockets.connect(url) as ws:
        client = ConformanceClient(ws, report, holo, recv_timeout=recv_timeout)

        await client.send(MT.CLIENT_HELLO, jp.ClientHello(
            device="quest3", app_version="0.1.0",
            capabilities=jp.Capabilities(mic=True, speaker=True), locale="en-US",
        ))
        acks = await client.recv_until(lambda d: d.get("type") == MT.SERVER_HELLO_ACK, what="server.hello_ack")
        all_docs += acks
        hello_ack = _first(acks, MT.SERVER_HELLO_ACK)
        if hello_ack:
            client.session = (hello_ack.get("payload") or {}).get("session")
        if not client.session:
            report.violations.append("server.hello_ack did not assign a session")

        # 1) settings_get -> server.settings catalog
        await client.send(MT.CLIENT_SETTINGS_GET, jp.ClientSettingsGet(section="llm"))
        got = await client.recv_until(lambda d: d.get("type") == MT.SERVER_SETTINGS, what="server.settings (get)")
        all_docs += got
        settings = _first(got, MT.SERVER_SETTINGS)
        if settings is None:
            report.violations.append("settings_get: no server.settings reply")
        else:
            llm = (settings.get("payload") or {}).get("llm") or {}
            if not llm.get("current") or not llm.get("providers"):
                report.violations.append("server.settings missing current/providers")
            else:
                ids = [p.get("id") for p in llm["providers"]]
                report.steps.append(f"settings catalog providers = {ids}")

        # 2) settings_update{provider, model, api_key} -> updated server.settings
        await client.send(MT.CLIENT_SETTINGS_UPDATE, jp.ClientSettingsUpdate(
            llm=jp.LlmSettingsUpdate(provider="openai", model="gpt-4o", api_key=secret),
        ))
        upd = await client.recv_until(lambda d: d.get("type") == MT.SERVER_SETTINGS, what="server.settings (update)")
        all_docs += upd
        updated = _first(upd, MT.SERVER_SETTINGS)
        if updated is None:
            report.violations.append("settings_update: no server.settings reply")
        else:
            cur = ((updated.get("payload") or {}).get("llm") or {}).get("current") or {}
            if cur.get("provider") != "openai":
                report.violations.append(f"settings_update: current.provider = {cur.get('provider')!r}, expected 'openai'")
            if cur.get("model") != "gpt-4o":
                report.violations.append(f"settings_update: current.model = {cur.get('model')!r}, expected 'gpt-4o'")
            if cur.get("key_set") is not True:
                report.violations.append("settings_update: current.key_set should be true after sending a key")
            report.steps.append(f"settings current = {cur.get('provider')}/{cur.get('model')} key_set={cur.get('key_set')}")

        # 3) SECURITY: the key must NEVER appear in any received frame.
        blob = json.dumps(all_docs)
        if secret in blob:
            report.violations.append("SECURITY: api key value leaked in a received frame!")
        if '"api_key"' in blob:
            report.violations.append("SECURITY: an 'api_key' field appeared in a received frame!")
        report.steps.append("verified no api_key in any received frame")

        await client.send(MT.CLIENT_BYE, jp.ClientBye(reason="settings run complete"))

    return report


def print_report(report: Report, title: str = "JarvisVR e2e conformance") -> None:
    print(f"\n=== {title} ===")
    for step in report.steps:
        print(f"  • {step}")
    print(f"  sent={report.sent} received={report.received}")
    print(f"  message types seen: {', '.join(report.seen_types)}")
    if report.warnings:
        print(f"  warnings ({len(report.warnings)}):")
        for w in report.warnings:
            print(f"    - {w}")
    if report.violations:
        print(f"  VIOLATIONS ({len(report.violations)}):")
        for v in report.violations:
            print(f"    ✗ {v}")
        print("RESULT: FAIL")
    else:
        print("RESULT: PASS ✅")


def main() -> int:
    parser = argparse.ArgumentParser(description="JarvisVR protocol-conformance harness")
    parser.add_argument("--url", default=os.environ.get("JARVIS_BACKEND_URL", "ws://127.0.0.1:8765/jarvis"))
    parser.add_argument(
        "--strict-props",
        action="store_true",
        default=os.environ.get("E2E_STRICT_PROPS", "") == "1",
        help="treat holo-tools props-schema mismatches as failures (default: warnings)",
    )
    parser.add_argument("--timeout", type=float, default=float(os.environ.get("E2E_RECV_TIMEOUT", "5")))
    args = parser.parse_args()

    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO").upper(),
        format="%(levelname)s %(name)s %(message)s",
    )

    try:
        v1 = asyncio.run(run_conformance(args.url, strict_props=args.strict_props, recv_timeout=args.timeout))
        multimodal = asyncio.run(run_multimodal_conformance(args.url, strict_props=args.strict_props, recv_timeout=args.timeout))
        barge_in = asyncio.run(run_barge_in_conformance(args.url, strict_props=args.strict_props, recv_timeout=args.timeout))
        settings = asyncio.run(run_settings_conformance(args.url, strict_props=args.strict_props, recv_timeout=args.timeout))
    except OSError as exc:
        print(f"ERROR: could not connect to {args.url}: {exc}", file=sys.stderr)
        return 2

    print_report(v1, title="v1 scripted conversation")
    print_report(multimodal, title="v1.1 multimodal turn")
    print_report(barge_in, title="v1.1 barge_in (§5.14)")
    print_report(settings, title="v1.1 settings (§5.15)")
    ok = v1.ok() and multimodal.ok() and barge_in.ok() and settings.ok()
    print("\nOVERALL:", "PASS ✅" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
