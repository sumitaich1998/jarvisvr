"""Derive agent-facing tool/function-calling schemas from the widget registry.

The registry (``registry.json``) is the single source of truth. The widget tools
in ``tools.json`` are derived from it so they never drift; this module both powers
that generation and lets a backend rebuild the tool list at runtime.

Each tool follows the OpenAI/Anthropic-compatible shape
``{"name", "description", "parameters"}`` plus ``x_*`` extension keys that document
which ``widget_type``/``prefab_id`` a tool produces and which ``holo.*`` command it
maps to. Strip ``x_*`` keys before sending to an LLM if your provider rejects
unknown fields.
"""

from __future__ import annotations

import copy
from typing import Any, Dict, List, Optional

from . import loader

_DEFAULT_ANCHORS = ["world", "head", "hand_left", "hand_right", "surface"]

#: Friendly, agent-facing tool name for each widget's spawn tool.
WIDGET_TOOL_NAMES: Dict[str, str] = {
    # v1.0 widgets
    "weather_orb": "show_weather",
    "chart_3d": "show_chart",
    "model_viewer": "open_model_viewer",
    "panel": "show_panel",
    "text_label": "show_text",
    "button": "show_button",
    "timer": "start_timer",
    "media_player": "play_media",
    "map_3d": "show_map",
    "smart_home_panel": "show_smart_home",
    "todo_list": "show_todo_list",
    "image_board": "show_image_board",
    # v1.1 perception widgets (P0)
    "vision_annotation": "annotate_object",
    "bounding_box_3d": "draw_bounding_box",
    "live_caption": "show_live_caption",
    "vision_feed": "show_vision_feed",
    "scene_label": "drop_scene_label",
    # v1.1 feature widgets (P1)
    "clock": "show_clock",
    "world_clock": "show_world_clock",
    "calendar": "show_calendar",
    "stocks_ticker": "show_stocks",
    "news_feed": "show_news",
    "translator": "show_translator",
    "recipe_card": "show_recipe",
    "whiteboard": "open_whiteboard",
    "sticky_note": "show_sticky_note",
    "code_viewer": "show_code",
    "document_viewer": "show_document",
    "web_panel": "show_web",
    "avatar": "show_avatar",
    "navigation_arrow": "show_navigation",
    "health_ring": "show_health_ring",
    "music_visualizer": "show_music_visualizer",
    "graph_3d": "show_graph",
    "data_table": "show_data_table",
    "measuring_tape": "measure",
    "pomodoro": "start_pomodoro",
    "image_gen_viewer": "show_generated_image",
    "volumetric_globe": "show_globe",
    "system_launcher": "show_system_launcher",
    "notification_toast": "notify",
    "settings_panel": "show_settings",
}


def _placement_properties(anchors: List[str]) -> Dict[str, Any]:
    """Optional placement-override fields added to every widget tool."""
    return {
        "anchor": {
            "type": "string",
            "enum": list(anchors),
            "description": "Optional anchor override (defaults to the widget's default_transform.anchor).",
        },
        "position": {
            "type": "array",
            "items": {"type": "number"},
            "minItems": 3,
            "maxItems": 3,
            "description": "Optional position [x, y, z] in meters relative to the anchor.",
        },
        "billboard": {
            "type": "boolean",
            "description": "Optional: if true, the widget always faces the user.",
        },
    }


def derive_widget_tool(
    widget: Dict[str, Any],
    name: Optional[str] = None,
    anchors: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Build a spawn tool schema for a single registry ``widget`` entry."""
    anchors = anchors or _DEFAULT_ANCHORS
    widget_type = widget["widget_type"]
    name = name or WIDGET_TOOL_NAMES.get(widget_type, f"show_{widget_type}")
    props_schema = widget["props_schema"]

    properties = copy.deepcopy(props_schema.get("properties", {}))
    properties.update(_placement_properties(anchors))

    parameters = {
        "type": "object",
        "additionalProperties": False,
        "properties": properties,
        "required": list(props_schema.get("required", [])),
    }

    return {
        "name": name,
        "description": (
            f"{widget['title']}: {widget['description']} "
            f"Produces a '{widget_type}' hologram (holo.spawn)."
        ),
        "parameters": parameters,
        "x_widget_type": widget_type,
        "x_prefab_id": widget["prefab_id"],
        "x_action": "spawn",
    }


def utility_tools(anchors: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    """Return the non-widget utility tools (layout / destroy / update)."""
    anchors = anchors or _DEFAULT_ANCHORS
    arrange = {
        "name": "arrange_holograms",
        "description": (
            "Arrange existing holograms into a spatial layout (arc, grid, stack, or free). "
            "Maps to holo.layout."
        ),
        "parameters": {
            "type": "object",
            "additionalProperties": False,
            "required": ["arrangement", "object_ids"],
            "properties": {
                "arrangement": {"type": "string", "enum": ["arc", "grid", "stack", "free"]},
                "anchor": {"type": "string", "enum": list(anchors), "default": "head"},
                "object_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "minItems": 1,
                    "description": "Object ids to arrange.",
                },
                "spacing": {
                    "type": "number",
                    "exclusiveMinimum": 0,
                    "default": 0.25,
                    "description": "Spacing between objects in meters.",
                },
            },
        },
        "x_action": "layout",
    }
    close = {
        "name": "close_hologram",
        "description": "Remove a hologram from the scene. Maps to holo.destroy.",
        "parameters": {
            "type": "object",
            "additionalProperties": False,
            "required": ["object_id"],
            "properties": {
                "object_id": {"type": "string", "description": "Id of the object to remove."},
                "fade_ms": {
                    "type": "integer",
                    "minimum": 0,
                    "default": 300,
                    "description": "Fade-out duration in milliseconds.",
                },
            },
        },
        "x_action": "destroy",
    }
    update = {
        "name": "update_hologram",
        "description": (
            "Patch the props and/or transform of an existing hologram. Maps to holo.update."
        ),
        "parameters": {
            "type": "object",
            "additionalProperties": False,
            "required": ["object_id"],
            "properties": {
                "object_id": {"type": "string"},
                "props": {
                    "type": "object",
                    "description": "Partial props patch (validated against the object's widget schema).",
                },
                "transform": {"type": "object", "description": "Partial transform patch."},
            },
        },
        "x_action": "update",
    }
    return [arrange, close, update]


def derive_tools(registry: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Build the full ``tools.json`` document from the registry."""
    registry = registry if registry is not None else loader.load_registry()
    anchors = registry.get("anchors", _DEFAULT_ANCHORS)
    tools = [derive_widget_tool(w, anchors=anchors) for w in registry.get("widgets", [])]
    tools.extend(utility_tools(anchors))
    return {
        "version": registry.get("version", "1.0.0"),
        "description": (
            "Agent-facing tool/function schemas for JarvisVR. Group (a) widget tools "
            "(x_action='spawn') are derived from registry.json; group (b) utility tools "
            "(arrange_holograms/close_hologram/update_hologram). Strip x_* keys before "
            "sending to an LLM if your provider rejects unknown fields."
        ),
        "tools": tools,
    }
