"""The Jarvis orchestrator (L0) — docs/ORCHESTRATION.md §2 / §6, PROTOCOL §9.

Jarvis never does domain work; it **conducts**:

    decompose → route → execute (parallel where independent) → synthesize

It reuses the existing :class:`AgentSession` machinery (tool registry, holo
directive translation, perception buffer, observation/speech helpers) — each
specialist is a thin wrapper that selects a subset of tools + activates skills.

Offline (MockLLM) the decomposition+routing are deterministic (keyword/intent via
``plan_tool_calls``); real providers use tool/function-calling to produce the same
shape (a list of tool calls), which is then grouped by owning specialist role.

It emits the v1.2 messages: ``orchestration.plan`` (once), ``orchestration.agent_status``
(queued→working→[delegating]→done/failed), ``orchestration.handoff`` (sub-agents),
and tags ``agent.thinking`` with ``agent_id``/``role``/``skill``.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Optional

from .. import protocol
from . import agents
from .llm import LLMMessage, ToolCall, plan_tool_calls

if TYPE_CHECKING:  # avoid an import cycle; the session is duck-typed at runtime.
    from .agent import AgentSession

log = logging.getLogger("jarvis.orchestrator")

_DECOMPOSE_PROMPT = (
    "You are Jarvis, an orchestrator that conducts a team of specialist agents. "
    "Given the user's goal, call the tools needed to accomplish it. Each tool call "
    "is routed to the specialist that owns it and may run in parallel. Do not answer "
    "directly unless it's pure small talk."
)


@dataclass
class SubTask:
    agent_id: str
    role: str
    name: str
    label: str
    calls: list[ToolCall]
    skills: list[str] = field(default_factory=list)


@dataclass
class AgentResult:
    agent_id: str
    role: str
    text: str
    spawned: list[str] = field(default_factory=list)
    ok: bool = True


class Orchestrator:
    def __init__(self, session: "AgentSession"):
        self.session = session
        self.agent = session.agent

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    async def run(self, goal: str, *, attach_perception: Optional[bool] = None) -> None:
        goal = (goal or "").strip()
        if not goal:
            return
        session = self.session
        plan_id = protocol.new_id()
        self._goal = goal
        self.agent.per_agent_memory.begin_turn()  # v1.3: fresh short-term per turn

        await self._think("planning", "Decomposing your request…")

        calls, direct = await self._decompose(goal)
        subtasks = self._build_subtasks(goal, calls)
        session.state.memory.add_user(goal)

        needs_stage = len(subtasks) >= 2
        stage_id = f"a{len(subtasks) + 1}" if needs_stage else None

        # Turn the camera on once if a perception specialist is involved (§8.6).
        attach = session._resolve_attach(goal, attach_perception)
        started_vision = False
        if attach and any(st.role == "perception-agent" for st in subtasks):
            started_vision = await session._begin_perception_for_turn()

        await self._emit_plan(plan_id, goal, subtasks, stage_id)

        # v1.3: open a trace for this turn (ring-buffered; streamed if subscribed).
        session.tracer.start(plan_id, goal)
        session.tracer.set_agents(self._trace_agents(subtasks, stage_id))

        for st in subtasks:
            await self._status(plan_id, st.agent_id, st.role, "queued", label="Queued")
        if stage_id:
            await self._status(plan_id, stage_id, "stage-agent", "queued", label="Queued")

        # Run independent specialists concurrently.
        results: list[AgentResult] = []
        if subtasks:
            results = list(
                await asyncio.gather(*(self._run_specialist(plan_id, st) for st in subtasks))
            )
        all_spawned = [oid for r in results for oid in r.spawned]

        # The stage-agent composes the final layout (depends on the specialists).
        if stage_id:
            await self._run_stage(plan_id, stage_id, all_spawned, goal)

        final_text = self._synthesize(results, direct)
        if final_text:
            await session._stream_speech(final_text)
            await self._trace("speech", agent_id=agents.ORCHESTRATOR_ID,
                              role=agents.ORCHESTRATOR_ROLE, level=0, parent=None,
                              label="synthesized reply", detail=final_text)
        session.state.memory.add_assistant(final_text)

        await self._think("done", "Done")
        if started_vision:
            await session._end_perception_for_turn()
        session.state.memory.maybe_summarize()

    # ------------------------------------------------------------------
    # Decompose + route
    # ------------------------------------------------------------------

    async def _decompose(self, goal: str) -> tuple[list[ToolCall], Optional[str]]:
        available = set(self.session.registry.names())
        if getattr(self.session.llm, "name", "") == "mock":
            return plan_tool_calls(goal, available)
        # Real providers: tool/function-calling decomposition (same output shape).
        messages = [
            LLMMessage(role="system", content=_DECOMPOSE_PROMPT),
            LLMMessage(role="user", content=goal),
        ]
        try:
            result = await self.session.llm.complete(messages, self.session.registry.specs())
        except Exception as exc:  # noqa: BLE001 - fall back deterministically
            log.warning("LLM decomposition failed (%s); using deterministic planner", exc)
            return plan_tool_calls(goal, available)
        if result.tool_calls:
            return result.tool_calls, None
        return [], result.content

    def _build_subtasks(self, goal: str, calls: list[ToolCall]) -> list[SubTask]:
        groups: dict[str, list[ToolCall]] = {}
        for c in calls:
            groups.setdefault(self.agent.role_for_tool(c.name), []).append(c)
        subtasks: list[SubTask] = []
        for i, (role, rcalls) in enumerate(groups.items(), start=1):
            spec = self.agent.get_spec(role)
            subtasks.append(
                SubTask(
                    agent_id=f"a{i}",
                    role=role,
                    name=spec.name if spec else self.agent.display_name(role),
                    label=agents.label_for(role, [c.name for c in rcalls]),
                    calls=rcalls,
                    skills=self._skills_for(role, goal),
                )
            )
        return subtasks

    def _skills_for(self, role: str, text: str) -> list[str]:
        sr = self.agent.skills
        if not sr or len(sr) == 0:
            return []
        return [s.name for s in sr.match(role, text)][:2]

    # ------------------------------------------------------------------
    # Execute specialists
    # ------------------------------------------------------------------

    async def _run_specialist(self, plan_id: str, st: SubTask) -> AgentResult:
        session = self.session
        mem = self.agent.per_agent_memory.for_role(st.role)  # v1.3: isolated namespace
        active_skill = st.skills[0] if st.skills else None
        if active_skill:
            self.agent.skills.activate(active_skill)  # progressive disclosure: load body
        try:
            await self._status(
                plan_id, st.agent_id, st.role, "working",
                skill=active_skill, label=f"{st.label.capitalize()}…", progress=0.1,
            )
            # Per-agent memory recall (own namespace only) — traced.
            recalled = mem.recall(self._goal, n=3)
            await self._trace(
                "memory_read", agent_id=st.agent_id, role=st.role,
                label=f"recalled {len(recalled)} prior item(s)",
                detail="; ".join(r.get("text", "") for r in recalled) or "no prior memory",
            )
            if active_skill:
                await self._trace(
                    "skill_activated", agent_id=st.agent_id, role=st.role,
                    skill=active_skill, label=f"activated skill '{active_skill}'",
                )
            spawned: list[str] = []
            speeches: list[str] = []
            for call in st.calls:
                if session._cancelled:
                    break
                stage, tlabel = session._tool_stage(call.name)
                await self._think(stage, tlabel, tool=call.name, agent_id=st.agent_id,
                                  role=st.role, skill=active_skill)
                await self._trace("tool_call", agent_id=st.agent_id, role=st.role,
                                  skill=active_skill, tool=call.name, label=_call_label(call))
                t0 = time.monotonic()
                tool_result = await session.registry.run(
                    call.name, call.arguments, session._tool_context()
                )
                dur_ms = int((time.monotonic() - t0) * 1000)
                ids: list[str] = []
                if tool_result.directives:
                    ids = await session._apply_directives(tool_result.directives)
                    spawned += ids
                data = tool_result.data if isinstance(tool_result.data, dict) else {}
                detail = data.get("speech") or data.get("observation") or (
                    f"{len(ids)} hologram(s)" if ids else "ok"
                )
                await self._trace("tool_result", agent_id=st.agent_id, role=st.role,
                                  skill=active_skill, tool=call.name,
                                  label=f"{call.name} → ok", detail=str(detail), duration_ms=dur_ms)
                if data.get("observation"):
                    await session._emit_observation(data["observation"], ids)
                    await self._trace("observation", agent_id=st.agent_id, role=st.role,
                                      label="narrated observation", detail=str(data["observation"]))
                if data.get("speech"):
                    speeches.append(str(data["speech"]))
                # Multi-level delegation: research fans out per-source summarizers.
                if st.role == "research-agent" and call.name in ("web_search", "get_news"):
                    digest = await self._delegate_summarizers(plan_id, st, data)
                    if digest:
                        speeches.append(digest)
            text = " ".join(speeches).strip()
            if text:
                mem.remember(f"{st.label}: {text}", kind="result")  # persist to own namespace
                await self._trace("memory_write", agent_id=st.agent_id, role=st.role,
                                  label="stored result to memory", detail=text)
            await self._status(plan_id, st.agent_id, st.role, "done",
                               skill=active_skill, label="Done", progress=1.0)
            return AgentResult(st.agent_id, st.role, text, spawned)
        except Exception as exc:  # noqa: BLE001 - one agent failing must not crash the team
            log.exception("specialist %s (%s) failed", st.agent_id, st.role)
            await self._trace("error", agent_id=st.agent_id, role=st.role,
                              label="agent failed", detail=str(exc))
            await self._status(plan_id, st.agent_id, st.role, "failed", label=f"Failed: {exc}")
            return AgentResult(st.agent_id, st.role, "", [], ok=False)

    async def _delegate_summarizers(self, plan_id: str, st: SubTask, data: dict) -> str:
        items = list(data.get("results") or data.get("articles") or [])[:2]
        if not items:
            return ""
        await self._status(plan_id, st.agent_id, st.role, "delegating",
                           label="Delegating to summarizers…", progress=0.5)
        titles: list[str] = []
        for k, item in enumerate(items, start=1):
            sub_id = f"{st.agent_id}.{k}"
            title = (
                (item.get("title") or item.get("headline") or f"source {k}")
                if isinstance(item, dict) else f"source {k}"
            )
            await self.session.emit(
                protocol.MsgType.ORCHESTRATION_HANDOFF,
                protocol.OrchestrationHandoff(
                    plan_id=plan_id, from_agent=st.agent_id, to_agent=sub_id,
                    to_role="summarizer", level=2, subtask=f"summarize: {title}",
                    reason="delegating summarization to a sub-agent",
                ),
            )
            self.session.tracer.add_agent(
                {"agent_id": sub_id, "role": "summarizer", "parent": st.agent_id, "level": 2}
            )
            await self._trace("delegated", agent_id=st.agent_id, role=st.role,
                              label=f"delegated to sub-agent {sub_id}", detail=f"summarize: {title}")
            await self._status(plan_id, sub_id, "summarizer", "working",
                               parent=st.agent_id, level=2, label=f"Summarizing {title}…")
            await self._think("tool_call", f"Summarizing {title}…",
                              agent_id=sub_id, role="summarizer")
            await self._trace("tool_result", agent_id=sub_id, role="summarizer", parent=st.agent_id,
                              level=2, label="summarized source", detail=str(title))
            await self._status(plan_id, sub_id, "summarizer", "done",
                               parent=st.agent_id, level=2, label="Done", progress=1.0)
            titles.append(str(title))
        await self._status(plan_id, st.agent_id, st.role, "working",
                           label="Merging summaries…", progress=0.85)
        return f"I reviewed {len(titles)} sources and pulled out the key points."

    async def _run_stage(self, plan_id: str, stage_id: str, spawned: list[str], goal: str) -> None:
        skills = self._skills_for("stage-agent", goal)
        skill = skills[0] if skills else None
        if skill:
            self.agent.skills.activate(skill)
        await self._status(plan_id, stage_id, "stage-agent", "working",
                           skill=skill, label="Composing your space…", progress=0.5)
        if spawned:
            await self._think("rendering", "Arranging holograms…",
                              agent_id=stage_id, role="stage-agent", skill=skill)
            await self.session.emit(
                protocol.MsgType.HOLO_LAYOUT,
                protocol.HoloLayout(
                    arrangement="arc", anchor="head", objects=spawned, spacing=0.35
                ),
            )
            await self._trace("tool_result", agent_id=stage_id, role="stage-agent", skill=skill,
                              label="composed layout", detail=f"arranged {len(spawned)} object(s)")
        await self._status(plan_id, stage_id, "stage-agent", "done", label="Done", progress=1.0)

    # ------------------------------------------------------------------
    # Synthesize
    # ------------------------------------------------------------------

    @staticmethod
    def _synthesize(results: list[AgentResult], direct: Optional[str]) -> str:
        texts = [r.text for r in results if r.text]
        if texts:
            return " ".join(texts)
        return direct or "Done."

    # ------------------------------------------------------------------
    # Emit helpers
    # ------------------------------------------------------------------

    async def _emit_plan(self, plan_id: str, goal: str, subtasks: list[SubTask], stage_id: Optional[str]) -> None:
        plan_agents = [
            protocol.OrchestrationAgent(
                agent_id=agents.ORCHESTRATOR_ID, role=agents.ORCHESTRATOR_ROLE,
                name="Jarvis", parent=None, level=0,
            )
        ]
        edges: list[dict[str, str]] = []
        for st in subtasks:
            plan_agents.append(
                protocol.OrchestrationAgent(
                    agent_id=st.agent_id, role=st.role, name=st.name,
                    parent=agents.ORCHESTRATOR_ID, level=1, subtask=st.label,
                    skills=st.skills or None,
                )
            )
            edges.append({"from": agents.ORCHESTRATOR_ID, "to": st.agent_id})
        if stage_id:
            plan_agents.append(
                protocol.OrchestrationAgent(
                    agent_id=stage_id, role="stage-agent", name="Stage",
                    parent=agents.ORCHESTRATOR_ID, level=1, subtask="compose the workspace",
                    skills=self._skills_for("stage-agent", goal) or None,
                )
            )
            edges.append({"from": agents.ORCHESTRATOR_ID, "to": stage_id})
        await self.session.emit(
            protocol.MsgType.ORCHESTRATION_PLAN,
            protocol.OrchestrationPlan(plan_id=plan_id, goal=goal, agents=plan_agents, edges=edges),
        )

    async def _status(
        self, plan_id: str, agent_id: str, role: str, state: str, *,
        parent: str = agents.ORCHESTRATOR_ID, level: int = 1,
        skill: Optional[str] = None, label: Optional[str] = None,
        progress: Optional[float] = None,
    ) -> None:
        await self.session.emit(
            protocol.MsgType.ORCHESTRATION_AGENT_STATUS,
            protocol.OrchestrationAgentStatus(
                plan_id=plan_id, agent_id=agent_id, role=role, parent=parent,
                level=level, state=state, skill=skill, label=label, progress=progress,
            ),
        )

    async def _think(
        self, stage: str, label: Optional[str] = None, *, tool: Optional[str] = None,
        agent_id: str = agents.ORCHESTRATOR_ID, role: str = agents.ORCHESTRATOR_ROLE,
        skill: Optional[str] = None,
    ) -> None:
        await self.session._emit_thinking(
            stage, label, tool=tool, agent_id=agent_id, role=role, skill=skill
        )

    # -- tracing (§10.1) ----------------------------------------------------

    async def _trace(
        self, kind: str, *, agent_id: str, role: str, label: str,
        parent: Optional[str] = agents.ORCHESTRATOR_ID, level: int = 1,
        skill: Optional[str] = None, tool: Optional[str] = None,
        detail: Optional[str] = None, duration_ms: Optional[int] = None,
    ) -> None:
        await self.session.tracer.event(
            agent_id=agent_id, role=role, kind=kind, label=label, parent=parent,
            level=level, skill=skill, tool=tool, detail=detail, duration_ms=duration_ms,
        )

    @staticmethod
    def _trace_agents(subtasks: list[SubTask], stage_id: Optional[str]) -> list[dict]:
        out = [{"agent_id": agents.ORCHESTRATOR_ID, "role": agents.ORCHESTRATOR_ROLE,
                "parent": None, "level": 0}]
        for st in subtasks:
            out.append({"agent_id": st.agent_id, "role": st.role,
                        "parent": agents.ORCHESTRATOR_ID, "level": 1})
        if stage_id:
            out.append({"agent_id": stage_id, "role": "stage-agent",
                        "parent": agents.ORCHESTRATOR_ID, "level": 1})
        return out


def _call_label(call: ToolCall) -> str:
    args = call.arguments if isinstance(call.arguments, dict) else {}
    parts = []
    for k, v in args.items():
        sv = str(v)
        parts.append(f"{k}={sv[:40] + '…' if len(sv) > 40 else sv}")
    return f"{call.name}({', '.join(parts)})"


__all__ = ["Orchestrator", "SubTask", "AgentResult"]
