"""Per-turn tracing (v1.3 §10.1).

The orchestrator records a :class:`Trace` per turn (keyed by ``plan_id``) — an
ordered list of secret-redacted entries (``memory_read``, ``memory_write``,
``skill_activated``, ``tool_call``, ``tool_result``, ``observation``,
``delegated``, ``speech``, ``error``). The :class:`Tracer`:

* keeps a **bounded ring buffer** of recent traces (served by ``client.trace_get``),
* streams ``orchestration.trace_event`` **live only when subscribed**
  (``client.trace_subscribe{enabled}``; default off),
* **redacts secrets** — API keys, bearer tokens, and long opaque tokens are
  scrubbed and details are truncated. The orchestrator additionally never passes
  raw frames/audio into ``detail`` (only short summaries).
"""

from __future__ import annotations

import re
import time
from collections import OrderedDict
from typing import Awaitable, Callable, Optional

from .. import protocol

_MAX_DETAIL = 200

# Scrub obvious secrets defensively (the caller already avoids raw secrets).
_SECRET_PATTERNS = [
    re.compile(r"\b(sk|rk|pk)-[A-Za-z0-9_\-]{6,}\b"),
    re.compile(r"\bBearer\s+[A-Za-z0-9._\-]+\b", re.IGNORECASE),
    re.compile(r"\b[A-Za-z0-9_\-]{32,}\b"),  # long opaque tokens
]


def _now_ms() -> int:
    return int(time.time() * 1000)


def redact(detail: Optional[str]) -> Optional[str]:
    if detail is None:
        return None
    text = " ".join(str(detail).split())
    for pat in _SECRET_PATTERNS:
        text = pat.sub("[redacted]", text)
    if len(text) > _MAX_DETAIL:
        text = text[: _MAX_DETAIL - 1] + "…"
    return text


class Trace:
    """One turn's ordered trace (kept in the ring + returned by trace_get)."""

    def __init__(self, plan_id: str, goal: str):
        self.plan_id = plan_id
        self.goal = goal
        self.agents: list[dict] = []  # {agent_id, role, parent, level}
        self.entries: list[dict] = []  # trace_event payload dicts, in order

    def set_agents(self, agents: list[dict]) -> None:
        self.agents = list(agents)

    def to_server_trace(self) -> protocol.ServerTrace:
        return protocol.ServerTrace(
            plan_id=self.plan_id,
            goal=self.goal,
            agents=[protocol.TraceAgent(**a) for a in self.agents],
            entries=[protocol.TraceEvent(**e) for e in self.entries],
        )


class Tracer:
    """Per-session trace recorder + live streamer with a bounded ring buffer."""

    def __init__(
        self,
        emit: Callable[..., Awaitable[None]],
        *,
        enabled: bool = True,
        subscribed: bool = False,
        capacity: int = 24,
    ):
        self._emit = emit
        self.enabled = enabled
        self.subscribed = subscribed
        self._capacity = max(1, capacity)
        self._traces: "OrderedDict[str, Trace]" = OrderedDict()
        self._current: Optional[Trace] = None
        self._seq = 0

    # -- lifecycle ----------------------------------------------------------

    def start(self, plan_id: str, goal: str) -> Optional[Trace]:
        if not self.enabled:
            self._current = None
            return None
        trace = Trace(plan_id, goal)
        self._seq = 0
        self._traces[plan_id] = trace
        while len(self._traces) > self._capacity:
            self._traces.popitem(last=False)
        self._current = trace
        return trace

    def set_agents(self, agents: list[dict]) -> None:
        if self._current is not None:
            self._current.set_agents(agents)

    def add_agent(self, agent: dict) -> None:
        """Register a sub-agent that appeared mid-turn (e.g. a summarizer)."""
        if self._current is not None:
            self._current.agents.append(agent)

    async def event(
        self,
        *,
        agent_id: str,
        role: str,
        kind: str,
        label: str,
        parent: Optional[str] = None,
        level: int = 1,
        skill: Optional[str] = None,
        tool: Optional[str] = None,
        detail: Optional[str] = None,
        duration_ms: Optional[int] = None,
    ) -> None:
        if not self.enabled or self._current is None:
            return
        ev = protocol.TraceEvent(
            plan_id=self._current.plan_id,
            seq=self._seq,
            ts=_now_ms(),
            agent_id=agent_id,
            role=role,
            parent=parent,
            level=level,
            kind=kind,
            label=label,
            skill=skill,
            tool=tool,
            detail=redact(detail),
            duration_ms=duration_ms,
        )
        self._seq += 1
        self._current.entries.append(ev.model_dump(exclude_none=True))
        if self.subscribed:
            await self._emit(protocol.MsgType.ORCHESTRATION_TRACE_EVENT, ev)

    # -- access -------------------------------------------------------------

    def get(self, plan_id: Optional[str] = None) -> Optional[Trace]:
        if plan_id:
            return self._traces.get(plan_id)
        if self._current is not None:
            return self._current
        if self._traces:
            return next(reversed(self._traces.values()))
        return None


__all__ = ["Trace", "Tracer", "redact"]
