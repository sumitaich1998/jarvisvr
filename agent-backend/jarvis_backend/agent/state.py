"""Per-connection session state shared by the agent loop and the tools.

Kept in its own module so both ``agent.py`` and ``tools/`` can import it without
creating an import cycle.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from ..perception import PerceptionBuffer
from ..protocol import HoloObject
from .memory import ConversationMemory


@dataclass
class SessionState:
    """Everything we remember for one connected headset session."""

    session_id: str
    memory: ConversationMemory = field(default_factory=ConversationMemory)
    # Live holograms by server-assigned object_id.
    objects: dict[str, HoloObject] = field(default_factory=dict)
    # Logical handle (e.g. "notes_panel", "timer:ab12") -> object_id.
    refs: dict[str, str] = field(default_factory=dict)
    # Free-form scratch space for stateful tools (timers, etc.).
    store: dict[str, Any] = field(default_factory=dict)
    # v1.1: rolling multimodal perception (sight/sound/gaze) for this session.
    perception: PerceptionBuffer = field(default_factory=PerceptionBuffer)

    def resolve(self, ref: str) -> Optional[str]:
        return self.refs.get(ref)

    def get_object(self, object_id: str) -> Optional[HoloObject]:
        return self.objects.get(object_id)

    def track(self, obj: HoloObject, ref: Optional[str] = None) -> None:
        self.objects[obj.object_id] = obj
        if ref:
            self.refs[ref] = obj.object_id

    def untrack(self, object_id: str) -> None:
        self.objects.pop(object_id, None)
        for ref, oid in list(self.refs.items()):
            if oid == object_id:
                self.refs.pop(ref, None)


__all__ = ["SessionState"]
