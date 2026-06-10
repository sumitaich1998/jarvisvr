"""The agent orchestration loop.

``Agent`` holds the connection-independent resources (config, LLM provider, tool
registry, widget catalog, long-term memory). For each connected headset it mints
an ``AgentSession`` bound to that connection's ``emit`` callback and per-session
state.

The loop is the classic agentic cycle:

    plan -> call tools -> observe -> respond

emitting ``agent.thinking`` stage updates, translating tool results into
``holo.*`` render commands (assigning server-side ``object_id``s), and finishing
with a streamed ``agent.speech``. ``client.interaction`` events are routed back
into the same tool layer (or the LLM) so holograms stay live.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any, Awaitable, Callable, Optional

from .. import protocol
from ..catalog import CatalogError, WidgetCatalog
from ..config import Config
from ..skills import SkillRegistry, load_skills
from .agent_memory import PerAgentMemory
from .agents import (
    TOOL_TO_ROLE,
    build_roster,
    display_name as _builtin_display_name,
    get_spec as _builtin_get_spec,
    role_for_tool as _builtin_role_for_tool,
    roster_roles,
)
from .llm import ImageInput, LLMMessage, LLMProvider
from .memory import ConversationMemory, EpisodicMemory, LongTermStore
from .orchestrator import Orchestrator
from .persona import build_system_prompt
from .trace import Tracer
from .user_roster import UserAgent, load_user_agents, save_user_agents
from .state import SessionState
from .tools import (
    DestroyDirective,
    SpawnDirective,
    ToolContext,
    ToolRegistry,
    UpdateDirective,
)

log = logging.getLogger("jarvis.agent")

# emit(type, payload=None, *, reply_to=None) -> awaitable
EmitFn = Callable[..., Awaitable[None]]

# Tools that involve "looking" (drive the agent.thinking 'looking' stage).
_VISION_TOOLS = {
    "describe_view", "identify_object", "read_text", "translate_view",
    "find_object", "remember_object",
}

# Heuristic: does this utterance want current sight/sound attached?
_PERCEPTION_HINT = re.compile(
    r"\b(what (?:is|'s) this|what am i looking at|what do you see|what can you see|"
    r"describe (?:the )?(?:room|view|scene|this|surroundings)|look (?:at|around)|"
    r"take a look|read (?:this|the|that|it)|what does (?:this|it|that) say|"
    r"translate (?:this|the|that|it)|where (?:did i leave|is|are|'?s)|find (?:my|the)|"
    r"have you seen|what was that (?:sound|noise)|measure|how far|how (?:wide|tall|big))\b",
    re.I,
)

_WATCH_START = re.compile(
    r"\b(start watching|keep watching|watch (?:the |my )?room|keep an eye|"
    r"enable (?:your )?(?:vision|camera|sight)|turn on (?:your )?(?:vision|camera|sight)|"
    r"start (?:your )?camera)\b",
    re.I,
)
_WATCH_STOP = re.compile(
    r"\b(stop watching|stop looking|turn off (?:your )?(?:vision|camera|sight)|"
    r"disable (?:your )?(?:vision|camera)|look away|stop (?:your )?camera)\b",
    re.I,
)

# Sounds worth a proactive heads-up when proactive mode is enabled.
_NOTABLE_SOUNDS = {
    "doorbell", "alarm", "smoke_alarm", "fire_alarm", "phone", "phone_ringing",
    "ringtone", "glass_break", "baby_cry", "knock", "name_called", "siren", "timer",
}


class Agent:
    """Shared agent resources; creates a session per connection."""

    def __init__(
        self,
        config: Config,
        llm: LLMProvider,
        registry: ToolRegistry,
        catalog: WidgetCatalog,
        longterm: LongTermStore,
        episodic: Optional[EpisodicMemory] = None,
        skills: Optional[SkillRegistry] = None,
    ):
        self.config = config
        self.llm = llm
        self.registry = registry
        self.catalog = catalog
        self.longterm = longterm
        self.episodic = episodic or EpisodicMemory(longterm)
        # v1.2: Agent Skills registry + the specialist roster (skills auto-assigned).
        self.skills = skills if skills is not None else SkillRegistry()
        self.roster = build_roster(registry, self.skills)
        # v1.3: per-agent memory namespaces + the user-authored agent roster.
        self.per_agent_memory = PerAgentMemory(longterm)
        self._builtin_roles = set(roster_roles())
        self.user_agents: dict[str, UserAgent] = load_user_agents(config.user_agents_file)
        self._user_tool_to_role: dict[str, str] = {}
        self._rebuild_routing()

    @classmethod
    def build(cls, config: Config, llm: LLMProvider) -> "Agent":
        from .tools import build_default_registry

        catalog = WidgetCatalog.load(config.holo_registry_path)
        registry = build_default_registry(
            catalog=catalog, tools_json_path=config.tools_json_path
        )
        longterm = LongTermStore(config.memory_file)
        episodic = EpisodicMemory(longterm)
        skills = load_skills(config.skills_dir)
        return cls(config, llm, registry, catalog, longterm, episodic, skills)

    def tool_names(self) -> list[str]:
        return self.registry.names()

    def agent_roles(self) -> list[str]:
        """The specialist role roster advertised in server.hello_ack (§9/§10)."""
        return list(roster_roles()) + sorted(self.user_agents)

    # -- roster (builtin + user agents) -------------------------------------

    def get_spec(self, role: str):
        ua = self.user_agents.get(role)
        if ua is not None:
            return ua.to_spec()
        return _builtin_get_spec(role)

    def display_name(self, role: str) -> str:
        ua = self.user_agents.get(role)
        return ua.name if ua is not None else _builtin_display_name(role)

    def role_for_tool(self, tool: str) -> str:
        """Route a tool to its owning role (user agents may own *new* tools)."""
        if tool in self._user_tool_to_role:
            return self._user_tool_to_role[tool]
        return _builtin_role_for_tool(tool)

    def is_builtin_role(self, role: str) -> bool:
        return role in self._builtin_roles

    # -- v1.3 authoring hot-reload ------------------------------------------

    def reload_skills(self) -> None:
        """Re-scan the skills root after authoring; re-attach skills to agents."""
        self.skills = load_skills(self.config.skills_dir)
        self.roster = build_roster(self.registry, self.skills)

    def register_user_agent(self, ua: UserAgent) -> None:
        self.user_agents[ua.role] = ua
        self._rebuild_routing()
        save_user_agents(self.config.user_agents_file, self.user_agents)

    def remove_user_agent(self, role: str) -> None:
        self.user_agents.pop(role, None)
        self._rebuild_routing()
        save_user_agents(self.config.user_agents_file, self.user_agents)

    def _rebuild_routing(self) -> None:
        # User agents may claim *new* tool ids; never steal a built-in tool's route.
        mapping: dict[str, str] = {}
        for ua in self.user_agents.values():
            for tool in ua.tools:
                if tool not in TOOL_TO_ROLE:
                    mapping[tool] = ua.role
        self._user_tool_to_role = mapping

    def set_llm(self, llm: LLMProvider) -> None:
        """Hot-swap the live LLM (runtime settings change, §5.15).

        ``AgentSession.llm`` reads ``agent.llm`` per turn, so every existing and
        future session uses the new provider/model on its next turn — no
        reconnect needed. The tool registry/persona are unchanged.
        """
        self.llm = llm

    def create_session(self, session_id: str, emit: EmitFn) -> "AgentSession":
        return AgentSession(self, session_id, emit)


class AgentSession:
    def __init__(self, agent: Agent, session_id: str, emit: EmitFn):
        self.agent = agent
        self.session_id = session_id
        self.emit = emit
        self.state = SessionState(session_id=session_id, memory=ConversationMemory())
        self.system_prompt = build_system_prompt(tool_names=agent.tool_names())
        # Barge-in (§5.14): the task running the current turn + a per-turn cancel
        # flag so we stop emitting agent.speech/agent.observation immediately.
        self._active_turn: Optional["asyncio.Task"] = None
        self._cancelled: bool = False
        # v1.2: the multi-agent orchestrator (decompose → route → execute → synthesize).
        self.orchestrator = Orchestrator(self)
        # v1.3: per-turn tracer (records traces; live streaming gated by subscribe).
        self.tracer = Tracer(self.emit, enabled=agent.config.trace_enabled)

    # -- convenience refs ---------------------------------------------------

    @property
    def config(self) -> Config:
        return self.agent.config

    @property
    def llm(self) -> LLMProvider:
        return self.agent.llm

    @property
    def registry(self) -> ToolRegistry:
        return self.agent.registry

    @property
    def catalog(self) -> WidgetCatalog:
        return self.agent.catalog

    def _tool_context(self) -> ToolContext:
        return ToolContext(
            config=self.config,
            session=self.state,
            catalog=self.catalog,
            longterm=self.agent.longterm,
            episodic=self.agent.episodic,
        )

    # ------------------------------------------------------------------
    # Turn lifecycle + barge-in (PROTOCOL §5.14)
    # ------------------------------------------------------------------

    async def run_turn(self, coro: Awaitable[None]) -> None:
        """Run a user-driven turn, tracking its task so ``barge_in`` can cancel it.

        The server wraps every ``handle_user_text`` / ``handle_interaction`` turn
        in this so a ``client.barge_in`` can interrupt it cleanly.
        """
        self._active_turn = asyncio.current_task()
        self._cancelled = False
        try:
            await coro
        finally:
            self._active_turn = None

    async def barge_in(self, reason: Optional[str] = None) -> bool:
        """Cancel the in-flight turn (user spoke over Jarvis, §5.14).

        Stops further ``agent.speech`` / ``agent.observation`` for the turn and
        aborts the in-flight tool/generation loop where feasible. Idempotent: a
        no-op (returns ``False``) when no turn is active.
        """
        task = self._active_turn
        if task is None or task.done():
            log.debug("barge_in: no active turn (reason=%s); no-op", reason)
            return False
        log.info("barge_in: cancelling active turn (reason=%s)", reason)
        self._cancelled = True  # stop emitting speech/observation right away
        task.cancel()  # interrupt any in-flight await (LLM call, tool, etc.)
        # Optional courtesy signal that the turn ended (§5.14).
        try:
            await self._emit_thinking("done", "Interrupted")
        except Exception:  # noqa: BLE001 - never let barge-in itself fail
            log.debug("barge_in: failed to emit thinking{done}", exc_info=True)
        return True

    # ------------------------------------------------------------------
    # Inbound: user text / transcript
    # ------------------------------------------------------------------

    async def handle_user_text(
        self, text: str, *, echo: bool = True, attach_perception: Optional[bool] = None
    ) -> None:
        text = (text or "").strip()
        if not text:
            return
        if echo:
            await self.emit(protocol.MsgType.AGENT_TRANSCRIPT, {"text": text})

        # Explicit perception stream control ("watch the room" / "stop watching").
        if self.config.perception_enabled and await self._maybe_perception_control(text):
            return

        # v1.2: route the turn through the multi-agent orchestrator (default on).
        # A trivial goal yields a 1-agent plan, preserving the single-turn UX.
        if self.config.orchestration_enabled:
            await self.orchestrator.run(text, attach_perception=attach_perception)
            return

        memory = self.state.memory
        memory.add_user(text)

        attach = self._resolve_attach(text, attach_perception)
        started_vision = False
        if attach:
            # Turn the camera on for this turn (PROTOCOL §8.6: start … stop),
            # unless we're already in continuous "watch the room" mode.
            started_vision = await self._begin_perception_for_turn()
            await self._emit_thinking("perceiving", "Perceiving…")
        else:
            await self._emit_thinking("planning", "Thinking…")

        note = self._perception_note() if attach else None
        images = self._perception_images() if attach else None

        spawned_this_turn: list[str] = []
        final_text: Optional[str] = None
        responded = False

        for step in range(self.config.max_tool_steps):
            if self._cancelled:  # barged-in (§5.14): abort the tool/generation loop
                break
            messages = memory.as_context(self.system_prompt)
            if note:
                messages.insert(1, LLMMessage(role="system", content=note))
            try:
                result = await self.llm.complete(
                    messages,
                    self.registry.specs(),
                    images=(images if step == 0 else None),
                )
            except Exception as exc:  # noqa: BLE001 - never crash the connection
                log.exception("LLM completion failed")
                await self._emit_error(protocol.ErrorCode.INTERNAL, f"LLM error: {exc}")
                final_text = "Sorry, I hit a problem thinking that through."
                responded = True
                break

            if result.tool_calls:
                memory.add_assistant(result.content, result.tool_calls)
                for call in result.tool_calls:
                    stage, label = self._tool_stage(call.name)
                    await self._emit_thinking(stage, label, tool=call.name)
                    tool_result = await self.registry.run(
                        call.name, call.arguments, self._tool_context()
                    )
                    ids: list[str] = []
                    if tool_result.directives:
                        await self._emit_thinking("rendering", "Rendering…")
                        ids = await self._apply_directives(tool_result.directives)
                        spawned_this_turn += ids
                    obs = (
                        tool_result.data.get("observation")
                        if isinstance(tool_result.data, dict)
                        else None
                    )
                    if obs:
                        await self._emit_observation(obs, ids)
                    memory.add_tool_result(
                        call.id, call.name, json.dumps(tool_result.data, default=str)
                    )
                continue

            # No tool calls -> final spoken answer.
            final_text = result.content or "Done."
            memory.add_assistant(final_text)
            responded = True
            break

        if self._cancelled:
            # Barged-in: drop the rest of the turn (no layout/speech/done).
            # The camera was turned on just for us, so turn it back off.
            if started_vision:
                await self._end_perception_for_turn()
            return

        if not responded:
            final_text = "I've done what I can for now."

        # Arrange multiple new holograms (before speaking the confirmation).
        if len(spawned_this_turn) >= 2:
            await self.emit(
                protocol.MsgType.HOLO_LAYOUT,
                protocol.HoloLayout(
                    arrangement="arc",
                    anchor="head",
                    objects=spawned_this_turn,
                    spacing=0.35,
                ),
            )

        if final_text:
            await self._stream_speech(final_text)

        await self._emit_thinking("done", "Done")
        # Privacy/battery: stop the one-shot camera stream we started (§8.6).
        if started_vision:
            await self._end_perception_for_turn()
        memory.maybe_summarize()  # summarization hook (heuristic in offline mode)

    # ------------------------------------------------------------------
    # Perception: inbound stream ingestion + control + context
    # ------------------------------------------------------------------

    def ingest_vision_frame(self, payload: dict[str, Any], raw: Optional[bytes] = None) -> None:
        self.state.perception.add_vision_frame(payload, raw)

    def ingest_gaze(self, payload: dict[str, Any]) -> None:
        self.state.perception.set_gaze(payload)

    def ingest_scene_objects(self, payload: dict[str, Any]) -> None:
        self.state.perception.set_scene_objects(payload)
        # Auto-index detected objects so "where did I leave my X" can recall them.
        for o in payload.get("objects", []) or []:
            if o.get("label") and o.get("position"):
                self.agent.episodic.remember_object(
                    o["label"],
                    position=o.get("position"),
                    anchor=o.get("anchor", "world"),
                    source="detection",
                    confidence=o.get("confidence"),
                )

    def ingest_state(self, payload: dict[str, Any]) -> None:
        self.state.perception.set_state(payload)

    async def handle_audio_event(self, payload: dict[str, Any]) -> None:
        self.state.perception.add_audio_event(payload)
        label = (payload.get("label") or "").lower()
        if self.config.proactive and label in _NOTABLE_SOUNDS:
            text = f"I heard {label.replace('_', ' ')}."
            await self._apply_directives(
                [
                    SpawnDirective(
                        widget_type="live_caption",
                        props={"lines": [f"Heard: {label}"], "speaker": "other"},
                        ref="live_caption",
                    )
                ]
            )
            await self._emit_observation({"text": text, "annotations": []}, [])
            await self._stream_speech(text)
            self.agent.episodic.record_event("audio", text)

    async def handle_audio_scene(self, payload: dict[str, Any]) -> None:
        self.state.perception.add_audio_scene(payload)

    async def _maybe_perception_control(self, text: str) -> bool:
        if _WATCH_START.search(text):
            self.state.perception.vision_active = True
            self.state.perception.watching = True  # continuous mode (no per-turn stop)
            await self._emit_perception_request(
                "vision", "start", fps=self.config.vision_default_fps,
                reason="user asked Jarvis to keep watching",
            )
            await self._emit_thinking("perceiving", "Watching…")
            await self._stream_speech("Okay, I'm watching your room now.")
            await self._emit_thinking("done", "Done")
            return True
        if _WATCH_STOP.search(text):
            self.state.perception.vision_active = False
            self.state.perception.watching = False
            await self._emit_perception_request("vision", "stop")
            await self._stream_speech("Okay, I've stopped watching.")
            await self._emit_thinking("done", "Done")
            return True
        return False

    def _resolve_attach(self, text: str, attach_perception: Optional[bool]) -> bool:
        if not self.config.perception_enabled:
            return False
        if attach_perception is not None:
            return bool(attach_perception)
        if self.state.perception.vision_active:
            return True
        return bool(_PERCEPTION_HINT.search(text))

    async def _begin_perception_for_turn(self) -> bool:
        """Turn the camera on for a one-shot perception turn (PROTOCOL §8.6).

        Returns ``True`` if we started a stream just for this turn (so the caller
        stops it again afterwards). In continuous "watch the room" mode the camera
        is already streaming, so we leave it on and return ``False``.
        """
        if self.state.perception.watching:
            return False
        await self._emit_perception_request(
            "vision",
            "start",
            fps=self.config.vision_default_fps,
            reason="answering a question about what you see",
        )
        return True

    async def _end_perception_for_turn(self) -> None:
        # Privacy/battery: turn the camera off once the question is answered (§8.6).
        await self._emit_perception_request("vision", "stop")

    async def _emit_perception_request(
        self,
        stream: str,
        action: str,
        *,
        fps: Optional[int] = None,
        reason: Optional[str] = None,
        duration_ms: int = 0,
    ) -> None:
        await self.emit(
            protocol.MsgType.PERCEPTION_REQUEST,
            protocol.PerceptionRequest(
                stream=stream, action=action, fps=fps, reason=reason, duration_ms=duration_ms
            ),
        )

    def _perception_note(self) -> Optional[str]:
        cd = self.state.perception.current_context()
        if not (cd["has_vision"] or cd["objects"] or cd["sounds"] or cd["gaze"]):
            return None
        lines = ["[Perception context — what you currently sense]"]
        frame = cd.get("frame")
        if frame:
            lines.append(
                f"- Camera frame: {frame['width']}x{frame['height']} {frame['format']} "
                f"(seq {frame['seq']})."
            )
        objs = cd.get("objects") or []
        if objs:
            lines.append(
                "- Detected objects: "
                + ", ".join(f"{o.get('label')} ({float(o.get('confidence', 0)):.0%})" for o in objs[:6])
            )
        gaze = cd.get("gaze")
        if gaze:
            target = gaze.get("hit_object_id") or "forward"
            lines.append(f"- Gaze: looking at {target}.")
        if cd.get("sounds"):
            lines.append("- Recent sounds: " + ", ".join(s.get("label", "?") for s in cd["sounds"][-5:]))
        ambient = cd.get("ambient")
        if ambient and ambient.get("ambient_transcript"):
            lines.append(f"- Overheard: \"{ambient['ambient_transcript']}\"")
        return "\n".join(lines)

    def _perception_images(self) -> Optional[list[ImageInput]]:
        # Only real providers consume raw pixels; the mock "sees" via tools.
        if self.llm.name not in ("openai", "anthropic"):
            return None
        imgs = self.state.perception.images_for_llm(1)
        if not imgs:
            return None
        return [ImageInput(b64=b, media_type=m) for b, m in imgs]

    def _tool_stage(self, name: str) -> tuple[str, str]:
        if name in _VISION_TOOLS:
            return "looking", f"Looking ({name})…"
        if name == "identify_sound":
            return "perceiving", "Listening…"
        return "tool_call", f"Calling {name}…"

    async def _emit_observation(self, obs: dict[str, Any], spawned_ids: list[str]) -> None:
        if self._cancelled:  # barged-in (§5.14): stop streaming observations
            return
        # Map labels of holograms we just spawned to their object_ids so the
        # observation's annotations can reference them.
        label_map: dict[Any, str] = {}
        for oid in spawned_ids:
            o = self.state.get_object(oid)
            if o is not None:
                label_map.setdefault(o.props.get("label"), oid)
        annotations = []
        for a in obs.get("annotations") or []:
            annotations.append(
                protocol.Annotation(
                    label=a.get("label", "object"),
                    object_id=a.get("object_id") or label_map.get(a.get("label")),
                    position=a.get("position", [0.0, 1.2, 0.8]),
                    anchor=a.get("anchor", "world"),
                )
            )
        await self.emit(
            protocol.MsgType.AGENT_OBSERVATION,
            protocol.AgentObservation(
                text=obs.get("text", ""),
                final=bool(obs.get("final", True)),
                annotations=annotations,
            ),
        )

    # ------------------------------------------------------------------
    # Inbound: hologram interaction
    # ------------------------------------------------------------------

    async def handle_interaction(self, payload: dict[str, Any]) -> None:
        inter = protocol.ClientInteraction.model_validate(payload)
        obj = self.state.get_object(inter.object_id)
        widget_type = inter.widget_type or (obj.widget_type if obj else None)
        log.info(
            "interaction object=%s widget=%s action=%s element=%s",
            inter.object_id,
            widget_type,
            inter.action,
            inter.element,
        )

        handled = False
        if widget_type == "timer":
            handled = await self._interact_timer(inter, obj)
        elif widget_type in {
            "panel", "weather_orb", "vision_annotation", "live_caption",
            "scene_label", "bounding_box_3d", "vision_feed", "translator",
        }:
            handled = await self._interact_panel(inter, obj)
        elif widget_type == "media_player":
            handled = await self._interact_media(inter, obj)

        if handled:
            # Every turn (incl. interactions) ends with agent.thinking{done} so
            # clients/harness can detect turn completion (PROTOCOL §5.4 / §7).
            await self._emit_thinking("done", "Done")
            return

        # Unhandled interaction -> route back into the agent/LLM as context so it
        # can decide how to update the holograms (per protocol §4 / ARCHITECTURE).
        element = f" ({inter.element})" if inter.element else ""
        synthetic = (
            f"I just {inter.action}ed the {widget_type or 'widget'} hologram{element}."
        )
        await self.handle_user_text(synthetic, echo=False)

    async def _interact_timer(self, inter, obj) -> bool:
        if obj is None:
            return False
        intent = self._timer_intent(inter)

        # Find the server-side timer metadata (carries ends_at_ms, which is not a
        # catalog prop) via the logical ref mapped to this object.
        ref = next(
            (
                r
                for r, oid in self.state.refs.items()
                if oid == obj.object_id and r.startswith("timer:")
            ),
            None,
        )
        meta = self.state.store.get("timers", {}).get(ref) if ref else None

        if intent == "cancel":
            await self._destroy_object(obj.object_id)
            if ref:
                self.state.store.get("timers", {}).pop(ref, None)
            await self._stream_speech("Timer cancelled.")
            return True

        state = (meta or {}).get("state") or obj.props.get("state", "running")
        running = state == "running"
        now = protocol.now_ms()
        do_pause = intent == "pause" or (intent == "toggle" and running)

        if do_pause:
            if meta and running:
                remaining_ms = max(0, int(meta.get("ends_at_ms", now)) - now)
            else:
                remaining_ms = int(obj.props.get("remaining_ms", 0))
            if meta:
                meta.update({"state": "paused", "remaining_ms": remaining_ms})
            await self._update_object(
                obj.object_id, props={"state": "paused", "remaining_ms": remaining_ms}
            )
            await self._stream_speech("Timer paused.")
        else:
            remaining_ms = int((meta or {}).get("remaining_ms", obj.props.get("remaining_ms", 0)))
            if meta:
                meta.update({"state": "running", "ends_at_ms": now + remaining_ms})
            await self._update_object(
                obj.object_id, props={"state": "running", "remaining_ms": remaining_ms}
            )
            await self._stream_speech("Timer resumed.")
        return True

    @staticmethod
    def _timer_intent(inter) -> str:
        el = (inter.element or "").lower()
        if any(k in el for k in ("cancel", "close", "stop", "dismiss")):
            return "cancel"
        if "pause" in el:
            return "pause"
        if any(k in el for k in ("resume", "play", "start")):
            return "resume"
        if inter.action == "toggle":
            return "toggle"
        return "toggle"

    async def _interact_panel(self, inter, obj) -> bool:
        el = (inter.element or "").lower()
        if obj is not None and any(k in el for k in ("close", "dismiss", "x")):
            await self._destroy_object(obj.object_id)
            await self._stream_speech("Closed.")
            return True
        return False

    async def _interact_media(self, inter, obj) -> bool:
        if obj is None:
            return False
        state = obj.props.get("state", "paused")
        new_state = "paused" if state == "playing" else "playing"
        await self._update_object(obj.object_id, props={"state": new_state})
        await self._stream_speech("Paused." if new_state == "paused" else "Playing.")
        return True

    # ------------------------------------------------------------------
    # Directive -> protocol translation
    # ------------------------------------------------------------------

    async def _apply_directives(self, directives) -> list[str]:
        spawned: list[str] = []
        for d in directives:
            if isinstance(d, SpawnDirective):
                oid = await self._spawn(d)
                if oid:
                    spawned.append(oid)
            elif isinstance(d, UpdateDirective):
                object_id = d.object_id or (self.state.resolve(d.ref) if d.ref else None)
                if object_id:
                    await self._update_object(object_id, props=d.props, transform=d.transform)
            elif isinstance(d, DestroyDirective):
                object_id = d.object_id or (self.state.resolve(d.ref) if d.ref else None)
                if object_id:
                    await self._destroy_object(object_id, fade_ms=d.fade_ms)
        return spawned

    async def _spawn(self, d: SpawnDirective) -> Optional[str]:
        # Validate widget + props against the catalog (conformance checklist).
        try:
            self.catalog.validate(d.widget_type, d.props)
        except CatalogError as exc:
            log.warning("rejecting spawn of %s: %s", d.widget_type, exc.message)
            await self._emit_error(exc.code, exc.message)
            return None

        # Idempotent re-spawn: if the ref is already live, update instead.
        if d.ref:
            existing = self.state.resolve(d.ref)
            if existing and self.state.get_object(existing):
                await self._update_object(existing, props=d.props, transform=d.transform)
                return None

        transform = dict(self.catalog.default_transform(d.widget_type))
        if d.transform:
            transform.update(d.transform)
        interactions = (
            d.interactions
            if d.interactions is not None
            else self.catalog.supported_interactions(d.widget_type)
        )
        obj = protocol.HoloObject(
            object_id=protocol.new_id(),
            widget_type=d.widget_type,
            transform=protocol.Transform(**transform) if transform else protocol.Transform(),
            props=d.props,
            interactable=d.interactable,
            interactions=interactions,
            ttl_ms=d.ttl_ms,
        )
        self.state.track(obj, d.ref)
        await self.emit(protocol.MsgType.HOLO_SPAWN, obj)
        return obj.object_id

    async def _update_object(
        self,
        object_id: str,
        *,
        props: Optional[dict] = None,
        transform: Optional[dict] = None,
    ) -> None:
        obj = self.state.get_object(object_id)
        if obj is not None:
            if props:
                obj.props.update(props)
            if transform:
                merged = obj.transform.model_dump()
                merged.update(transform)
                obj.transform = protocol.Transform(**merged)
        await self.emit(
            protocol.MsgType.HOLO_UPDATE,
            protocol.HoloUpdate(object_id=object_id, props=props, transform=transform),
        )

    async def _destroy_object(self, object_id: str, *, fade_ms: int = 300) -> None:
        await self.emit(
            protocol.MsgType.HOLO_DESTROY,
            protocol.HoloDestroy(object_id=object_id, fade_ms=fade_ms),
        )
        self.state.untrack(object_id)

    # ------------------------------------------------------------------
    # Outbound speech / status helpers
    # ------------------------------------------------------------------

    async def _emit_thinking(
        self,
        stage: str,
        label: Optional[str] = None,
        *,
        tool: Optional[str] = None,
        agent_id: Optional[str] = None,
        role: Optional[str] = None,
        skill: Optional[str] = None,
    ) -> None:
        await self.emit(
            protocol.MsgType.AGENT_THINKING,
            protocol.AgentThinking(
                stage=stage, label=label, tool=tool,
                agent_id=agent_id, role=role, skill=skill,
            ),
        )

    async def _stream_speech(self, text: str) -> None:
        text = (text or "").strip()
        if not text:
            return
        sentences = _split_sentences(text)
        for i, sentence in enumerate(sentences):
            if self._cancelled:  # barged-in (§5.14): stop streaming speech
                return
            await self.emit(
                protocol.MsgType.AGENT_SPEECH,
                protocol.AgentSpeech(text=sentence, final=(i == len(sentences) - 1)),
            )

    async def _emit_error(self, code: str, message: str, *, fatal: bool = False) -> None:
        await self.emit(
            protocol.MsgType.SERVER_ERROR,
            protocol.ErrorPayload(code=code, message=message, fatal=fatal),
        )


def _split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [p.strip() for p in parts if p.strip()]


__all__ = ["Agent", "AgentSession"]
