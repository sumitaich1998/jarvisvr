"""JarvisVR mock brain — a self-contained WebSocket server implementing PROTOCOL.md (v1.1).

It lets the unity-client and voice-service be developed/tested without the real
agent-backend. Every outgoing frame is built with the shared ``jarvis_protocol``
binding and self-validated before sending, so the mock can never emit a
non-conformant message.

Endpoints:
  * /jarvis  — main JSON channel (v1 + v1.1 perception messages, inline vision frames)
  * /vision  — v1.1 length-prefixed binary frames ([4B BE len][JSON header][image bytes])

Behavior (PROTOCOL.md):
  * client.hello                  -> server.hello_ack (assigns a session)
  * client.heartbeat             -> server.heartbeat (echo)
  * user.text / user.voice_*     -> weather/timer/panel turn, or a multimodal VISION turn
  * client.interaction           -> holo.update (+ agent.speech) + agent.thinking(done)
  * perception.*                  -> buffered in a rolling per-connection perception buffer
  * client.bye                   -> close
  * unknown types                -> ignored (forward-compatible)

Multimodal vision turn (when the user asks "what is this" or perception is attached):
  perception.request{vision,start} -> agent.thinking{perceiving} -> agent.observation
  -> holo.spawn vision_annotation -> agent.speech -> agent.thinking{done}
  -> perception.request{vision,stop}

Run:  JARVIS_HOST=0.0.0.0 JARVIS_PORT=8765 python server.py
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import signal
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import websockets

import jarvis_protocol as jp
from jarvis_protocol import AgentSpeech, AgentThinking  # most-used models; others via jp.*

LOG = logging.getLogger("jarvis.mock")

HOST = os.environ.get("JARVIS_HOST", "0.0.0.0")
PORT = int(os.environ.get("JARVIS_PORT", "8765"))
WS_PATH = os.environ.get("JARVIS_WS_PATH", "/jarvis")
VISION_PATH = os.environ.get("JARVIS_VISION_PATH", "/vision")

# Built-in widget catalog used when holo-tools/registry.json is absent.
BUILTIN_WIDGETS = ("weather_orb", "timer", "panel", "vision_annotation")
DEFAULT_TOOLS = ["get_weather", "start_timer", "describe_scene", "identify_object"]

# Utterances that should trigger a multimodal (vision) turn.
VISION_TRIGGERS = (
    "what is this", "what's this", "what is that", "what's that",
    "what am i looking at", "what do you see", "what can you see",
    "on my desk", "in front of me", "look at this", "identify", "describe what",
)


# --------------------------------------------------------------------------- #
# holo-tools registry (optional)                                              #
# --------------------------------------------------------------------------- #

def _find_registry() -> Optional[Path]:
    env = os.environ.get("HOLO_TOOLS_REGISTRY")
    if env and Path(env).is_file():
        return Path(env)
    here = Path(__file__).resolve()
    for parent in here.parents:
        cand = parent / "holo-tools" / "registry.json"
        if cand.is_file():
            return cand
    return None


def _registry_widget_types(registry: Any) -> set[str]:
    """Best-effort extraction of known widget_type names from an unknown shape."""
    types: set[str] = set()

    def add_from_entry(entry: Any) -> None:
        if isinstance(entry, dict):
            for key in ("widget_type", "type", "id", "name"):
                val = entry.get(key)
                if isinstance(val, str):
                    types.add(val)
                    return

    if isinstance(registry, dict):
        container = registry.get("widgets", registry)
        if isinstance(container, dict):
            for key, val in container.items():
                if isinstance(key, str) and not key.startswith("$"):
                    types.add(key)
        elif isinstance(container, list):
            for entry in container:
                add_from_entry(entry)
    elif isinstance(registry, list):
        for entry in registry:
            add_from_entry(entry)
    return {t for t in types if t}


def load_known_widgets() -> set[str]:
    path = _find_registry()
    if not path:
        LOG.info("no holo-tools/registry.json found; using built-in widgets %s", BUILTIN_WIDGETS)
        return set(BUILTIN_WIDGETS)
    try:
        registry = json.loads(path.read_text(encoding="utf-8"))
        known = _registry_widget_types(registry)
        if known:
            LOG.info("loaded %d widget types from %s", len(known), path)
            return known
        LOG.warning("registry %s had no recognizable widget types; using built-ins", path)
    except Exception as exc:  # noqa: BLE001
        LOG.warning("failed to read registry %s: %s; using built-ins", path, exc)
    return set(BUILTIN_WIDGETS)


KNOWN_WIDGETS = load_known_widgets()


def pick_widget(preferred: str) -> str:
    """Use ``preferred`` if the registry knows it (or no registry); else fall back."""
    if preferred in KNOWN_WIDGETS or not KNOWN_WIDGETS:
        return preferred
    for fallback in BUILTIN_WIDGETS:
        if fallback in KNOWN_WIDGETS:
            return fallback
    return sorted(KNOWN_WIDGETS)[0]


# --------------------------------------------------------------------------- #
# tiny "NLU"                                                                  #
# --------------------------------------------------------------------------- #

def parse_city(text: str) -> str:
    m = re.search(r"\bin\s+([a-zA-Z][a-zA-Z\s]*?)(?:\s+and\b|[.?!]|$)", text)
    # A successful match always yields at least one letter, so .title() is safe.
    return m.group(1).strip().title() if m else "Tokyo"


def parse_minutes(text: str) -> int:
    m = re.search(r"(\d+)", text)
    return int(m.group(1)) if m else 5


def is_vision_query(text: str) -> bool:
    lowered = text.lower()
    return any(trigger in lowered for trigger in VISION_TRIGGERS)


# --------------------------------------------------------------------------- #
# per-connection state (session + spawned objects + perception buffer)        #
# --------------------------------------------------------------------------- #

class ConnState:
    def __init__(self) -> None:
        self.session: Optional[str] = None
        self.objects: Dict[str, Dict[str, Any]] = {}
        self.perception: Dict[str, Any] = {}   # last vision_frame / scene_objects / gaze / audio_*
        self.vision_active: bool = False        # server-requested vision stream state
        # v1.1 §5.15 runtime settings (in-memory; the key is NEVER stored/echoed).
        self.settings: Dict[str, Any] = {"provider": "mock", "model": "mock", "base_url": None}
        self.keys_set: set[str] = set()         # provider ids that have a key configured


# A small provider catalog the mock advertises (PROTOCOL.md §5.15).
MOCK_PROVIDERS = [
    {"id": "mock", "name": "Mock (offline)", "default_model": "mock", "models": ["mock"],
     "needs_key": False, "needs_base_url": False, "tools": True, "vision": True},
    {"id": "openai", "name": "OpenAI", "default_model": "gpt-4o", "models": ["gpt-4o", "gpt-4o-mini"],
     "needs_key": True, "needs_base_url": False, "tools": True, "vision": True},
    {"id": "anthropic", "name": "Anthropic", "default_model": "claude-3-5-sonnet-latest",
     "models": ["claude-3-5-sonnet-latest", "claude-3-5-haiku-latest"],
     "needs_key": True, "needs_base_url": False, "tools": True, "vision": True},
    {"id": "ollama", "name": "Ollama (local)", "default_model": "llama3.1", "models": ["llama3.1"],
     "needs_key": False, "needs_base_url": True, "tools": True, "vision": False},
]
_MOCK_PROVIDER_IDS = {p["id"] for p in MOCK_PROVIDERS}


def _default_model(provider_id: str) -> str:
    for p in MOCK_PROVIDERS:
        if p["id"] == provider_id:
            return str(p["default_model"])
    return "mock"


def build_server_settings(state: ConnState) -> "jp.ServerSettings":
    """Build a conformant server.settings — key_set booleans only, never a key."""
    cur = state.settings
    current = jp.CurrentLlm(
        provider=cur["provider"], model=cur["model"],
        base_url=cur.get("base_url"), key_set=cur["provider"] in state.keys_set,
    )
    providers = [
        jp.ProviderEntry(
            id=p["id"], name=p["name"], default_model=p["default_model"], models=p["models"],
            needs_key=p["needs_key"], needs_base_url=p["needs_base_url"],
            key_set=p["id"] in state.keys_set,
            capabilities=jp.ProviderCapabilities(tools=p["tools"], vision=p["vision"]),
        )
        for p in MOCK_PROVIDERS
    ]
    return jp.ServerSettings(llm=jp.LlmSettings(current=current, providers=providers))


async def handle_settings_update(ws, state: ConnState, payload: Dict[str, Any]) -> None:
    """Apply a settings_update in-memory; echo back server.settings (never a key)."""
    llm = payload.get("llm")
    if not isinstance(llm, dict):
        await send(ws, state.session, jp.MessageType.SERVER_ERROR,
                   jp.ProtocolError(code="invalid_settings", message="missing 'llm' object", fatal=False))
        return
    provider = llm.get("provider")
    if provider is not None and provider not in _MOCK_PROVIDER_IDS:
        await send(ws, state.session, jp.MessageType.SERVER_ERROR,
                   jp.ProtocolError(code="provider_unavailable", message=f"unknown provider {provider!r}", fatal=False))
        return
    if provider:
        state.settings["provider"] = provider
        state.settings["model"] = _default_model(provider)
    if llm.get("model"):
        state.settings["model"] = llm["model"]
    if "base_url" in llm:
        state.settings["base_url"] = llm["base_url"]
    if llm.get("api_key"):  # mark configured; NEVER store or echo the key
        state.keys_set.add(state.settings["provider"])
        LOG.info("settings_update: key set for provider=%s (not stored/logged)", state.settings["provider"])
    await send(ws, state.session, jp.MessageType.SERVER_SETTINGS, build_server_settings(state))


# --------------------------------------------------------------------------- #
# widget builders -> jarvis_protocol.HoloObject                               #
# --------------------------------------------------------------------------- #

def _transform(position, billboard=True) -> jp.Transform:
    return jp.Transform(
        anchor="head",
        position=position,
        rotation=[0.0, 0.0, 0.0, 1.0],
        scale=[1.0, 1.0, 1.0],
        billboard=billboard,
    )


def build_weather_orb(city: str) -> jp.HoloObject:
    # props mirror holo-tools/registry.json weather_orb.props_schema.
    return jp.HoloObject(
        object_id=jp.new_id(),
        widget_type=pick_widget("weather_orb"),
        transform=_transform([0.45, 0.1, 0.9]),
        props={"city": city, "temp_c": 18.0, "condition": "clouds", "humidity_pct": 64, "wind_kph": 12.5, "unit": "c"},
        interactable=True,
        interactions=["grab", "tap"],
        ttl_ms=0,
    )


def build_timer(minutes: int) -> jp.HoloObject:
    # props mirror holo-tools/registry.json timer.props_schema (milliseconds!).
    duration_ms = minutes * 60 * 1000
    return jp.HoloObject(
        object_id=jp.new_id(),
        widget_type=pick_widget("timer"),
        transform=_transform([-0.45, 0.1, 0.9]),
        props={
            "label": f"{minutes} minute timer",
            "duration_ms": duration_ms,
            "remaining_ms": duration_ms,
            "state": "running",
            "mode": "countdown",
        },
        interactable=True,
        interactions=["tap", "grab"],
        ttl_ms=0,
    )


def build_panel(title: str, body: str) -> jp.HoloObject:
    # props mirror holo-tools/registry.json panel.props_schema (`body`, not `text`).
    return jp.HoloObject(
        object_id=jp.new_id(),
        widget_type=pick_widget("panel"),
        transform=_transform([0.0, 0.0, 1.0]),
        props={"title": title, "body": body},
        interactable=True,
        interactions=["grab", "tap"],
        ttl_ms=0,
    )


def build_vision_annotation(label: str, confidence: float, target_pos: List[float], detail: Optional[str] = None) -> jp.HoloObject:
    # props mirror holo-tools/registry.json vision_annotation.props_schema (v1.1).
    callout = [target_pos[0], target_pos[1] + 0.15, target_pos[2]]
    props: Dict[str, Any] = {"label": label, "confidence": confidence, "leader_line": True, "target_position": target_pos}
    if detail:
        props["detail"] = detail
    return jp.HoloObject(
        object_id=jp.new_id(),
        widget_type=pick_widget("vision_annotation"),
        transform=jp.Transform(anchor="world", position=callout, rotation=[0, 0, 0, 1], scale=[1, 1, 1], billboard=True),
        props=props,
        interactable=True,
        interactions=["tap"],
        ttl_ms=0,
    )


# --------------------------------------------------------------------------- #
# connection handling                                                        #
# --------------------------------------------------------------------------- #

def _ws_path(ws) -> str:
    request = getattr(ws, "request", None)
    if request is not None and getattr(request, "path", None):
        return request.path
    return getattr(ws, "path", "/")


async def send(ws, session: Optional[str], type_: str, payload, reply_to: Optional[str] = None):
    """Build, self-validate, and send a conformant frame."""
    msg = jp.new_message(type_, payload, session=session, reply_to=reply_to)
    errors = jp.iter_errors(msg)
    if errors:
        LOG.error("refusing to send non-conformant %s: %s", type_, errors)
        return None
    await ws.send(jp.encode(msg))
    LOG.debug("-> %s", type_)
    return msg


def pick_perceived_object(state: ConnState) -> Tuple[str, float, List[float]]:
    """Choose what Jarvis "sees" from the perception buffer (deterministic mock)."""
    scene = state.perception.get("scene_objects")
    if isinstance(scene, dict) and scene.get("objects"):
        obj = scene["objects"][0]
        label = str(obj.get("label", "object"))
        conf = float(obj.get("confidence", 0.78) or 0.78)
        pos = list(obj.get("position") or [0.3, 0.8, 0.7])
        if len(pos) != 3:
            pos = [0.3, 0.8, 0.7]
        return label, conf, pos
    return "coffee mug", 0.78, [0.3, 0.8, 0.7]


async def handle_vision_turn(ws, state: ConnState, text: str) -> None:
    LOG.info("vision turn: %r (buffered frame=%s)", text, "vision_frame" in state.perception)
    # Pull-based: turn the camera on if it isn't already streaming.
    if not state.vision_active:
        await send(ws, state.session, jp.MessageType.PERCEPTION_REQUEST,
                   jp.PerceptionRequest(stream="vision", action="start", fps=2, max_resolution="1024x1024", quality=70,
                                        reason="user asked what they're looking at"))
        state.vision_active = True

    await send(ws, state.session, jp.MessageType.AGENT_THINKING, AgentThinking(stage="perceiving", label="Looking at your space"))

    label, conf, pos = pick_perceived_object(state)
    detail = "ceramic, ~350 ml" if "mug" in label.lower() else None

    await send(ws, state.session, jp.MessageType.AGENT_OBSERVATION, jp.AgentObservation(
        text=f"I can see a {label} on your desk.",
        final=True,
        annotations=[jp.Annotation(label=label, position=pos, anchor="world")],
    ))

    anno = build_vision_annotation(label, conf, pos, detail)
    spawn = await send(ws, state.session, jp.MessageType.HOLO_SPAWN, anno)
    if spawn is not None:
        state.objects[anno.object_id] = {"widget_type": anno.widget_type, "props": dict(anno.props)}

    await send(ws, state.session, jp.MessageType.AGENT_SPEECH,
               AgentSpeech(text=f"That looks like a {label}. Want me to remember where it is?", final=True))
    await send(ws, state.session, jp.MessageType.AGENT_THINKING, AgentThinking(stage="done"))

    # Privacy / battery: stop the camera once the question is answered.
    await send(ws, state.session, jp.MessageType.PERCEPTION_REQUEST, jp.PerceptionRequest(stream="vision", action="stop"))
    state.vision_active = False


async def handle_turn(ws, state: ConnState, text: str, attach_perception: bool) -> None:
    LOG.info("turn: %r (attach_perception=%s)", text, attach_perception)

    # Multimodal: a vision question, or perception explicitly attached with a buffered frame.
    if is_vision_query(text) or (attach_perception and state.perception.get("vision_frame")):
        await handle_vision_turn(ws, state, text)
        return

    lowered = text.lower()
    await send(ws, state.session, jp.MessageType.AGENT_THINKING, AgentThinking(stage="planning", label="Understanding your request"))

    if "weather" in lowered:
        city = parse_city(lowered)
        await send(ws, state.session, jp.MessageType.AGENT_THINKING, AgentThinking(stage="tool_call", tool="get_weather", label=f"Calling get_weather({city})"))
        holo = build_weather_orb(city)
        await send(ws, state.session, jp.MessageType.AGENT_SPEECH, AgentSpeech(text=f"Here's the weather in {city}.", final=True))
    elif "timer" in lowered or "alarm" in lowered:
        minutes = parse_minutes(lowered)
        await send(ws, state.session, jp.MessageType.AGENT_THINKING, AgentThinking(stage="tool_call", tool="start_timer", label=f"Calling start_timer({minutes}m)"))
        holo = build_timer(minutes)
        await send(ws, state.session, jp.MessageType.AGENT_SPEECH, AgentSpeech(text=f"Started a {minutes} minute timer.", final=True))
    else:
        holo = build_panel("Jarvis", f"You said: {text}")
        await send(ws, state.session, jp.MessageType.AGENT_SPEECH, AgentSpeech(text="Here you go.", final=True))

    await send(ws, state.session, jp.MessageType.AGENT_THINKING, AgentThinking(stage="rendering", label="Materializing hologram"))
    spawn = await send(ws, state.session, jp.MessageType.HOLO_SPAWN, holo)
    if spawn is not None:
        state.objects[holo.object_id] = {"widget_type": holo.widget_type, "props": dict(holo.props)}
    await send(ws, state.session, jp.MessageType.AGENT_THINKING, AgentThinking(stage="done"))


async def handle_interaction(ws, state: ConnState, payload: Dict[str, Any]) -> None:
    object_id = payload.get("object_id", "")
    action = payload.get("action", "tap")
    element = payload.get("element")
    known = state.objects.get(object_id)
    LOG.info("interaction: object=%s action=%s element=%s", object_id, action, element)

    if known is None:
        await send(ws, state.session, jp.MessageType.SERVER_ERROR, jp.ProtocolError(code="unknown_widget", message=f"unknown object_id {object_id!r}", fatal=False))
        await send(ws, state.session, jp.MessageType.AGENT_THINKING, AgentThinking(stage="done"))
        return

    widget_type = known["widget_type"]
    new_props: Dict[str, Any] = {}
    speech: Optional[str] = None

    if widget_type == "timer" or (element and "pause" in str(element)) or action in ("toggle",):
        paused = known["props"].get("state") != "paused"
        new_props = {"state": "paused" if paused else "running"}
        known["props"].update(new_props)
        speech = "Timer paused." if paused else "Timer resumed."
    else:
        new_props = {"highlighted": True}
        known["props"].update(new_props)
        speech = "Got it."

    await send(ws, state.session, jp.MessageType.HOLO_UPDATE, jp.HoloUpdate(object_id=object_id, props=new_props))
    await send(ws, state.session, jp.MessageType.AGENT_SPEECH, AgentSpeech(text=speech, final=True))
    await send(ws, state.session, jp.MessageType.AGENT_THINKING, AgentThinking(stage="done"))


# perception.* messages we simply buffer (rolling perception buffer per connection).
PERCEPTION_BUFFER_KEYS = {
    jp.MessageType.PERCEPTION_VISION_FRAME: "vision_frame",
    jp.MessageType.PERCEPTION_SCENE_OBJECTS: "scene_objects",
    jp.MessageType.PERCEPTION_GAZE: "gaze",
    jp.MessageType.PERCEPTION_AUDIO_EVENT: "audio_event",
    jp.MessageType.PERCEPTION_AUDIO_SCENE: "audio_scene",
    jp.MessageType.PERCEPTION_STATE: "state",
}


async def main_handler(ws, state: ConnState) -> None:
    async for raw in ws:
        if isinstance(raw, (bytes, bytearray)):
            LOG.debug("ignoring binary frame on %s (use /vision)", WS_PATH)
            continue
        try:
            env = jp.decode(raw)
        except Exception as exc:  # noqa: BLE001
            LOG.warning("bad frame: %s", exc)
            await send(ws, state.session, jp.MessageType.SERVER_ERROR, jp.ProtocolError(code="bad_envelope", message="could not parse frame", fatal=False))
            continue

        mtype = env.type
        payload = env.payload or {}
        LOG.debug("<- %s", mtype)

        if mtype == jp.MessageType.CLIENT_HELLO:
            state.session = jp.new_id()
            await send(ws, state.session, jp.MessageType.SERVER_HELLO_ACK, jp.ServerHelloAck(
                session=state.session,
                agent=jp.AgentInfo(name="Jarvis", model="mock"),
                tools=DEFAULT_TOOLS,
                voice=jp.VoiceInfo(tts=True, wake_word="jarvis"),
            ))
        elif mtype == jp.MessageType.CLIENT_HEARTBEAT:
            await send(ws, state.session, jp.MessageType.SERVER_HEARTBEAT, jp.Heartbeat())
        elif mtype in (jp.MessageType.USER_TEXT, jp.MessageType.USER_VOICE_TRANSCRIPT, jp.MessageType.USER_VOICE_PARTIAL):
            if mtype == jp.MessageType.USER_VOICE_PARTIAL:
                continue  # interim transcript: no agent turn
            if state.session is None:
                state.session = jp.new_id()
            await handle_turn(ws, state, str(payload.get("text", "")), bool(payload.get("attach_perception", False)))
        elif mtype in PERCEPTION_BUFFER_KEYS:
            # Ingest into the rolling perception buffer (pull-based; no reply).
            state.perception[PERCEPTION_BUFFER_KEYS[mtype]] = payload
            LOG.info("buffered %s", mtype)
        elif mtype == jp.MessageType.CLIENT_INTERACTION:
            if state.session is None:
                state.session = jp.new_id()
            await handle_interaction(ws, state, payload)
        elif mtype == jp.MessageType.CLIENT_SETTINGS_GET:
            if state.session is None:
                state.session = jp.new_id()
            await send(ws, state.session, jp.MessageType.SERVER_SETTINGS, build_server_settings(state))
        elif mtype == jp.MessageType.CLIENT_SETTINGS_UPDATE:
            if state.session is None:
                state.session = jp.new_id()
            await handle_settings_update(ws, state, payload)
        elif mtype in (jp.MessageType.CLIENT_SCENE, jp.MessageType.CLIENT_ACK):
            pass  # acknowledged silently
        elif mtype == jp.MessageType.CLIENT_BYE:
            LOG.info("client said bye")
            break
        else:
            LOG.debug("ignoring unknown type %s (forward-compatible)", mtype)


def parse_vision_frame(message: bytes) -> Tuple[bool, str]:
    """Parse a §8.2 length-prefixed binary vision frame; validate its JSON header."""
    if len(message) < 4:
        return False, "frame shorter than 4-byte length prefix"
    header_len = int.from_bytes(message[:4], "big")
    if 4 + header_len > len(message):
        return False, f"header length {header_len} exceeds frame size {len(message)}"
    try:
        header = json.loads(message[4:4 + header_len].decode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        return False, f"header is not valid JSON: {exc}"
    image = message[4 + header_len:]
    # Validate the header as a perception.vision_frame payload (binary transport, no data).
    env = jp.new_message(jp.MessageType.PERCEPTION_VISION_FRAME, header, session=None)
    errors = jp.iter_errors(env)
    if errors:
        return False, f"invalid vision_frame header: {errors}"
    return True, f"camera={header.get('camera')} {header.get('width')}x{header.get('height')} seq={header.get('seq')} image_bytes={len(image)}"


async def vision_handler(ws) -> None:
    """Ingest §8.2 length-prefixed binary vision frames on /vision."""
    LOG.info("vision client connected on %s", VISION_PATH)
    count = 0
    try:
        async for message in ws:
            if isinstance(message, (bytes, bytearray)):
                ok, info = parse_vision_frame(bytes(message))
                if ok:
                    count += 1
                    LOG.info("/vision frame #%d ok: %s", count, info)
                else:
                    LOG.warning("/vision rejected frame: %s", info)
            else:
                LOG.debug("/vision: ignoring text frame")
    except websockets.ConnectionClosed:
        pass
    finally:
        LOG.info("/vision client disconnected (%d frame(s) ingested)", count)


def _is_vision_path(path: str) -> bool:
    base = path.split("?", 1)[0].rstrip("/")
    target = VISION_PATH.rstrip("/")
    return bool(target) and (base == target or base.endswith(target))


async def handler(ws) -> None:
    path = _ws_path(ws)
    if _is_vision_path(path):
        await vision_handler(ws)
        return
    LOG.info("client connected on %s", path)
    state = ConnState()
    try:
        await main_handler(ws, state)
    except websockets.ConnectionClosed:
        LOG.info("client disconnected")
    finally:
        LOG.info("connection closed (session=%s)", state.session)


async def main() -> None:
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    stop = asyncio.get_running_loop().create_future()
    try:
        asyncio.get_running_loop().add_signal_handler(signal.SIGTERM, lambda: stop.set_result(None))
        asyncio.get_running_loop().add_signal_handler(signal.SIGINT, lambda: stop.set_result(None))
    except (NotImplementedError, RuntimeError):  # pragma: no cover (e.g. Windows)
        pass

    async with websockets.serve(handler, HOST, PORT, max_size=8 * 1024 * 1024):
        LOG.info("JarvisVR mock brain (v%s) on ws://%s:%d  [%s + %s]", jp.PROTOCOL_VERSION, HOST, PORT, WS_PATH, VISION_PATH)
        print(f"MOCK_BACKEND_LISTENING ws://{HOST}:{PORT}{WS_PATH}", flush=True)
        await stop


if __name__ == "__main__":  # pragma: no cover
    asyncio.run(main())
