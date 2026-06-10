"""Tool registry primitives.

A *tool* is a named, JSON-schema-typed callable that the LLM can invoke. Each
tool returns a :class:`ToolResult` carrying both structured ``data`` (fed back to
the LLM as the observation) and zero or more *holo directives* describing which
holograms to spawn/update/destroy. The agent loop turns those directives into the
concrete ``holo.*`` protocol messages (assigning server-side ``object_id``s).
"""

from __future__ import annotations

import inspect
import logging
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Optional, Union

from ..llm import ToolSpec
from ..state import SessionState

log = logging.getLogger("jarvis.tools")


# ---------------------------------------------------------------------------
# Holo directives (tool -> render intent; agent resolves refs + object_ids)
# ---------------------------------------------------------------------------


@dataclass
class SpawnDirective:
    widget_type: str
    props: dict[str, Any] = field(default_factory=dict)
    # Logical handle so later turns/interactions can address this object.
    ref: Optional[str] = None
    transform: Optional[dict[str, Any]] = None  # override; else catalog default
    interactions: Optional[list[str]] = None  # override; else catalog supported
    interactable: bool = True
    ttl_ms: int = 0


@dataclass
class UpdateDirective:
    ref: Optional[str] = None
    object_id: Optional[str] = None
    props: Optional[dict[str, Any]] = None
    transform: Optional[dict[str, Any]] = None


@dataclass
class DestroyDirective:
    ref: Optional[str] = None
    object_id: Optional[str] = None
    fade_ms: int = 300


Directive = Union[SpawnDirective, UpdateDirective, DestroyDirective]


@dataclass
class ToolResult:
    """Result of a tool call: observation data + render directives."""

    data: dict[str, Any] = field(default_factory=dict)
    directives: list[Directive] = field(default_factory=list)
    error: Optional[str] = None  # error code (e.g. "unknown_widget") if failed

    @property
    def ok(self) -> bool:
        return self.error is None


# ---------------------------------------------------------------------------
# Tool context + registry
# ---------------------------------------------------------------------------


@dataclass
class ToolContext:
    """Everything a tool needs at call time."""

    config: Any
    session: SessionState
    catalog: Any  # WidgetCatalog
    longterm: Any  # LongTermStore
    episodic: Any = None  # EpisodicMemory (events / facts / spatial index)

    @property
    def perception(self):
        """Convenience: the session's rolling perception buffer."""
        return self.session.perception


ToolHandler = Callable[[dict[str, Any], ToolContext], Union[ToolResult, Awaitable[ToolResult]]]


@dataclass
class Tool:
    name: str
    description: str
    parameters: dict[str, Any]  # JSON schema for function calling
    handler: ToolHandler

    def spec(self) -> ToolSpec:
        return ToolSpec(self.name, self.description, self.parameters)


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        if tool.name in self._tools:
            log.warning("overwriting already-registered tool %s", tool.name)
        self._tools[tool.name] = tool

    def add(
        self,
        name: str,
        description: str,
        parameters: dict[str, Any],
        handler: ToolHandler,
    ) -> None:
        self.register(Tool(name, description, parameters, handler))

    def get(self, name: str) -> Optional[Tool]:
        return self._tools.get(name)

    def has(self, name: str) -> bool:
        return name in self._tools

    def names(self) -> list[str]:
        return sorted(self._tools.keys())

    def specs(self) -> list[ToolSpec]:
        return [t.spec() for t in self._tools.values()]

    async def run(self, name: str, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
        tool = self._tools.get(name)
        if tool is None:
            return ToolResult(
                data={"error": f"unknown tool '{name}'", "speech": ""},
                error="tool_failed",
            )
        try:
            result = tool.handler(args or {}, ctx)
            if inspect.isawaitable(result):
                result = await result
            return result
        except Exception as exc:  # noqa: BLE001 - tools must never crash the loop
            log.exception("tool %s failed", name)
            return ToolResult(
                data={"error": str(exc), "speech": f"Sorry, {name} failed."},
                error="tool_failed",
            )


__all__ = [
    "SpawnDirective",
    "UpdateDirective",
    "DestroyDirective",
    "Directive",
    "ToolResult",
    "ToolContext",
    "Tool",
    "ToolRegistry",
    "ToolHandler",
]
