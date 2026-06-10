"""Dynamic widget-spawn tools, derived from the widget catalog.

For every catalog widget that isn't already covered by a richer dedicated tool,
register a ``show_<widget>`` spawn tool whose parameters are the widget's
``props_schema``. Nicer tool names/descriptions are pulled from
``holo-tools/tools.json`` when present (the canonical agent-facing schemas);
otherwise we synthesize them — so this works whether or not holo-tools has
published yet.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Optional

from .base import SpawnDirective, Tool, ToolContext, ToolRegistry, ToolResult

log = logging.getLogger("jarvis.tools")

# Widgets already handled by dedicated, behaviour-rich tools.
_CLAIMED_WIDGETS = {"weather_orb", "timer", "panel"}


def _load_tools_json(path: Optional[Path]) -> dict[str, dict[str, Any]]:
    """Map widget_type -> {name, description} from tools.json spawn tools."""
    out: dict[str, dict[str, Any]] = {}
    if not path or not Path(path).is_file():
        return out
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        for t in data.get("tools", []):
            wt = t.get("x_widget_type")
            if wt and t.get("x_action") == "spawn":
                out[wt] = {"name": t.get("name"), "description": t.get("description")}
    except Exception as exc:  # noqa: BLE001
        log.warning("could not parse tools.json at %s (%s)", path, exc)
    return out


def _make_handler(widget_type: str):
    def handler(args: dict[str, Any], ctx: ToolContext) -> ToolResult:
        props = dict(args or {})
        pretty = widget_type.replace("_", " ")
        return ToolResult(
            data={"opened": True, "widget_type": widget_type, "speech": f"Here's the {pretty}."},
            directives=[SpawnDirective(widget_type=widget_type, props=props, ref=f"widget:{widget_type}")],
        )

    return handler


def register_widget_tools(
    reg: ToolRegistry, catalog: Any, tools_json_path: Optional[Path] = None
) -> int:
    """Register a spawn tool per catalog widget. Returns how many were added."""
    meta = _load_tools_json(tools_json_path)
    added = 0
    for widget_type in catalog.names():
        if widget_type in _CLAIMED_WIDGETS:
            continue
        info = meta.get(widget_type, {})
        tool_name = info.get("name") or f"show_{widget_type}"
        if reg.has(tool_name):
            continue  # don't clobber a dedicated tool
        spec = catalog.get(widget_type)
        schema = spec.props_schema if spec else {}
        if isinstance(schema, dict) and schema.get("type") == "object":
            params = schema
        else:
            params = {"type": "object", "properties": {}}
        desc = info.get("description") or (
            f"Spawn the '{widget_type}' hologram. {getattr(spec, 'description', '')}".strip()
        )
        reg.register(Tool(tool_name, desc, params, _make_handler(widget_type)))
        added += 1
    log.info("registered %d dynamic widget-spawn tools", added)
    return added


__all__ = ["register_widget_tools"]
