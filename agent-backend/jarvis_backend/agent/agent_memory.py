"""Per-agent memory namespaces (v1.3 §10.1).

Each specialist **role** gets its own isolated memory namespace on top of the
shared :class:`LongTermStore`:

* **long-term** — persisted under the key ``agent_mem:<role>`` (survives restarts,
  shared across sessions), so an agent accumulates knowledge over time.
* **short-term** — an in-RAM per-turn scratch buffer, cleared at the start of each
  turn via :meth:`PerAgentMemory.begin_turn`.

Isolation is by construction: ``for_role(r)`` only ever reads/writes ``r``'s key,
so one agent can never see another's memory. Reads/writes are surfaced as trace
events by the orchestrator (this module stays I/O-free besides the store).
"""

from __future__ import annotations

import time
from typing import Any, Optional

from .memory import LongTermStore


def _now_ms() -> int:
    return int(time.time() * 1000)


class AgentMemory:
    """A single role's isolated memory namespace."""

    def __init__(self, role: str, store: LongTermStore):
        self.role = role
        self.store = store
        self._key = f"agent_mem:{role}"
        self._short: list[dict[str, Any]] = []

    # -- writes -------------------------------------------------------------

    def remember(self, text: str, *, kind: str = "note", **extra: Any) -> dict[str, Any]:
        """Persist an item to this role's long-term namespace (and short-term)."""
        item = {"ts": _now_ms(), "role": self.role, "kind": kind, "text": str(text)[:500], **extra}
        self.store.append(self._key, item)
        self._short.append(item)
        return item

    def note(self, text: str, **extra: Any) -> dict[str, Any]:
        """Short-term-only note for the current turn (not persisted)."""
        item = {"ts": _now_ms(), "role": self.role, "kind": "note", "text": str(text)[:500], **extra}
        self._short.append(item)
        return item

    # -- reads (own namespace only) ----------------------------------------

    def all(self) -> list[dict[str, Any]]:
        return list(self.store.get(self._key, []) or [])

    def recall(self, query: Optional[str] = None, *, n: int = 5) -> list[dict[str, Any]]:
        items = self.all()
        if query:
            q = query.lower()
            items = [i for i in items if q in str(i.get("text", "")).lower()]
        return items[-n:]

    def recent(self, n: int = 5) -> list[dict[str, Any]]:
        return self.all()[-n:]

    def short_term(self) -> list[dict[str, Any]]:
        return list(self._short)

    def count(self) -> int:
        return len(self.all())

    def summary(self) -> str:
        items = self.all()
        if not items:
            return f"No memories yet for {self.role}."
        return f"{len(items)} memory item(s); latest: {str(items[-1].get('text',''))[:120]}"

    def reset_turn(self) -> None:
        self._short = []


class PerAgentMemory:
    """Manager that hands out one :class:`AgentMemory` per role (cached)."""

    def __init__(self, store: LongTermStore):
        self.store = store
        self._mems: dict[str, AgentMemory] = {}

    def for_role(self, role: str) -> AgentMemory:
        mem = self._mems.get(role)
        if mem is None:
            mem = AgentMemory(role, self.store)
            self._mems[role] = mem
        return mem

    def begin_turn(self) -> None:
        for mem in self._mems.values():
            mem.reset_turn()

    def roles(self) -> list[str]:
        return sorted(self._mems)


__all__ = ["AgentMemory", "PerAgentMemory"]
