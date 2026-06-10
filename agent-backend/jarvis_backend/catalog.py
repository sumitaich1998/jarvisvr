"""Holographic widget catalog.

The canonical catalog is published by ``holo-tools/registry.json`` and consumed
by *both* the backend and the Unity client (ARCHITECTURE.md §3.4 / §6). Because
``holo-tools/`` is built in parallel, this module:

* loads the catalog from disk when ``registry.json`` is present, and
* falls back to a small built-in catalog so the backend is never blocked.

It also validates ``widget_type`` + ``props`` against the catalog (lightly, with
a dependency-free JSON-schema-ish checker) per the protocol conformance list.

Expected registry.json shape (the fallback mirrors it; reconcile when holo-tools
publishes the real schema)::

    {
      "version": "1.0.0",
      "widgets": {
        "weather_orb": {
          "prefab_id": "WeatherOrb",
          "description": "...",
          "interactions": ["grab", "tap", "resize"],
          "default_transform": { "anchor": "head", "position": [...], ... },
          "props_schema": { "type": "object", "required": [...],
                            "properties": { "city": {"type": "string"}, ... } }
        },
        ...
      }
    }
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

log = logging.getLogger("jarvis.catalog")


class CatalogError(Exception):
    """Raised when a widget/props fail validation against the catalog."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass
class WidgetSpec:
    widget_type: str
    prefab_id: str
    description: str = ""
    interactions: list[str] = field(default_factory=list)
    default_transform: dict[str, Any] = field(default_factory=dict)
    props_schema: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_entry(cls, widget_type: str, entry: dict[str, Any]) -> "WidgetSpec":
        return cls(
            widget_type=widget_type,
            prefab_id=entry.get("prefab_id", widget_type),
            description=entry.get("description", ""),
            interactions=list(entry.get("interactions", [])),
            default_transform=dict(entry.get("default_transform", {})),
            props_schema=dict(entry.get("props_schema", {})),
        )


# ---------------------------------------------------------------------------
# Built-in fallback catalog (used when holo-tools/registry.json is absent).
# Widget set follows README.md / ARCHITECTURE.md §3.4.
# ---------------------------------------------------------------------------

_FALLBACK: dict[str, Any] = {
    "version": "1.0.0",
    "source": "agent-backend builtin fallback",
    "widgets": {
        "weather_orb": {
            "prefab_id": "WeatherOrb",
            "description": "Floating orb showing current weather for a city.",
            "interactions": ["grab", "tap", "resize"],
            "default_transform": {
                "anchor": "head",
                "position": [0.45, 0.0, 0.9],
                "rotation": [0, 0, 0, 1],
                "scale": [1, 1, 1],
                "billboard": True,
            },
            "props_schema": {
                "type": "object",
                "required": ["city", "temp_c", "condition"],
                "properties": {
                    "city": {"type": "string"},
                    "temp_c": {"type": "number"},
                    "condition": {
                        "type": "string",
                        "enum": [
                            "clear", "partly_cloudy", "clouds", "rain",
                            "snow", "storm", "fog", "wind",
                        ],
                    },
                    "humidity_pct": {"type": "integer"},
                    "wind_kph": {"type": "number"},
                    "unit": {"type": "string", "enum": ["c", "f"]},
                },
            },
        },
        "timer": {
            "prefab_id": "TimerWidget",
            "description": "Countdown timer with start/pause/cancel.",
            "interactions": ["tap", "grab", "resize"],
            "default_transform": {
                "anchor": "head",
                "position": [-0.45, 0.1, 0.9],
                "rotation": [0, 0, 0, 1],
                "scale": [1, 1, 1],
                "billboard": True,
            },
            "props_schema": {
                "type": "object",
                "required": ["duration_ms", "remaining_ms", "state"],
                "properties": {
                    "label": {"type": "string"},
                    "duration_ms": {"type": "integer"},
                    "remaining_ms": {"type": "integer"},
                    "state": {
                        "type": "string",
                        "enum": ["idle", "running", "paused", "completed"],
                    },
                    "mode": {"type": "string", "enum": ["countdown", "stopwatch"]},
                },
            },
        },
        "panel": {
            "prefab_id": "Panel",
            "description": "Generic text panel for notes, info, reminders.",
            "interactions": ["tap", "grab", "drag", "resize"],
            "default_transform": {
                "anchor": "world",
                "position": [0.0, 1.4, 1.1],
                "rotation": [0, 0, 0, 1],
                "scale": [1, 1, 1],
                "billboard": False,
            },
            "props_schema": {
                "type": "object",
                "required": ["title"],
                "properties": {
                    "title": {"type": "string"},
                    "body": {"type": "string"},
                    "sections": {"type": "array"},
                    "background": {
                        "type": "string",
                        "enum": ["glass", "solid", "none"],
                    },
                    "scrollable": {"type": "boolean"},
                },
            },
        },
        "chart_3d": {
            "prefab_id": "Chart3D",
            "description": "3D data chart (bar/line/scatter).",
            "interactions": ["grab", "rotate", "resize", "tap"],
            "default_transform": {
                "anchor": "head",
                "position": [0.0, 0.0, 1.1],
                "rotation": [0, 0, 0, 1],
                "scale": [1, 1, 1],
                "billboard": False,
            },
            "props_schema": {
                "type": "object",
                "required": ["series"],
                "properties": {
                    "title": {"type": "string"},
                    "series": {"type": "array"},
                    "chart_type": {
                        "type": "string",
                        "enum": ["bar", "line", "scatter"],
                    },
                },
            },
        },
        "model_viewer": {
            "prefab_id": "ModelViewer",
            "description": "Interactive 3D model viewer.",
            "interactions": ["grab", "rotate", "resize"],
            "default_transform": {
                "anchor": "world",
                "position": [0.0, 1.0, 1.2],
                "rotation": [0, 0, 0, 1],
                "scale": [1, 1, 1],
                "billboard": False,
            },
            "props_schema": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "model_id": {"type": "string"},
                    "model_url": {"type": "string"},
                },
            },
        },
        "media_player": {
            "prefab_id": "MediaPlayer",
            "description": "Audio/video media player surface.",
            "interactions": ["tap", "grab", "resize"],
            "default_transform": {
                "anchor": "head",
                "position": [0.0, 0.0, 1.2],
                "rotation": [0, 0, 0, 1],
                "scale": [1, 1, 1],
                "billboard": True,
            },
            "props_schema": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "source": {"type": "string"},
                    "state": {"type": "string", "enum": ["playing", "paused"]},
                },
            },
        },
        "map_3d": {
            "prefab_id": "Map3D",
            "description": "3D map with markers.",
            "interactions": ["grab", "pan", "resize", "tap"],
            "default_transform": {
                "anchor": "surface",
                "position": [0.0, 0.05, 0.0],
                "rotation": [0, 0, 0, 1],
                "scale": [1, 1, 1],
                "billboard": False,
            },
            "props_schema": {
                "type": "object",
                "properties": {
                    "center": {"type": "array"},
                    "zoom": {"type": "number"},
                    "markers": {"type": "array"},
                },
            },
        },
        "smart_home_panel": {
            "prefab_id": "SmartHomePanel",
            "description": "Smart-home device control panel.",
            "interactions": ["tap", "toggle", "grab", "slider"],
            "default_transform": {
                "anchor": "head",
                "position": [0.0, 0.0, 1.0],
                "rotation": [0, 0, 0, 1],
                "scale": [1, 1, 1],
                "billboard": True,
            },
            "props_schema": {
                "type": "object",
                "properties": {
                    "room": {"type": "string"},
                    "devices": {"type": "array"},
                },
            },
        },
        # --- v1.1 perception widgets (P0). Lightweight fallbacks until holo-tools
        # publishes the canonical schemas; published versions take precedence. ---
        "vision_annotation": {
            "prefab_id": "VisionAnnotation",
            "description": "World-anchored callout/label pinned on a real object.",
            "interactions": ["tap", "grab"],
            "default_transform": {
                "anchor": "world",
                "position": [0.0, 1.2, 0.8],
                "rotation": [0, 0, 0, 1],
                "scale": [1, 1, 1],
                "billboard": True,
            },
            "props_schema": {
                "type": "object",
                "required": ["label"],
                "properties": {
                    "label": {"type": "string"},
                    "confidence": {"type": "number"},
                    "detail": {"type": "string"},
                    "color": {"type": "string"},
                },
            },
        },
        "bounding_box_3d": {
            "prefab_id": "BoundingBox3D",
            "description": "A 3D wireframe box around a detected object.",
            "interactions": ["tap"],
            "default_transform": {
                "anchor": "world",
                "position": [0.0, 1.0, 0.8],
                "rotation": [0, 0, 0, 1],
                "scale": [1, 1, 1],
                "billboard": False,
            },
            "props_schema": {
                "type": "object",
                "additionalProperties": False,
                "required": ["label", "size"],
                "properties": {
                    "label": {"type": "string"},
                    "size": {"type": "array"},
                    "confidence": {"type": "number"},
                    "color": {"type": "string"},
                    "filled": {"type": "boolean"},
                    "target_object_id": {"type": "string"},
                },
            },
        },
        "live_caption": {
            "prefab_id": "LiveCaption",
            "description": "Rolling captions of speech/sounds Jarvis hears.",
            "interactions": ["grab", "tap"],
            "default_transform": {
                "anchor": "head",
                "position": [0.0, -0.35, 1.0],
                "rotation": [0, 0, 0, 1],
                "scale": [1, 1, 1],
                "billboard": True,
            },
            "props_schema": {
                "type": "object",
                "additionalProperties": False,
                "required": ["lines"],
                "properties": {
                    "lines": {"type": "array"},
                    "speaker": {
                        "type": "string",
                        "enum": ["user", "other", "jarvis", "unknown"],
                    },
                    "max_lines": {"type": "integer"},
                    "language": {"type": "string"},
                    "translated": {"type": "boolean"},
                },
            },
        },
        "vision_feed": {
            "prefab_id": "VisionFeed",
            "description": "A panel showing what Jarvis currently sees.",
            "interactions": ["grab", "tap", "resize"],
            "default_transform": {
                "anchor": "head",
                "position": [0.55, 0.0, 1.0],
                "rotation": [0, 0, 0, 1],
                "scale": [1, 1, 1],
                "billboard": True,
            },
            "props_schema": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "status": {"type": "string"},
                    "frame_count": {"type": "integer"},
                    "width": {"type": "integer"},
                    "height": {"type": "integer"},
                },
            },
        },
        "scene_label": {
            "prefab_id": "SceneLabel",
            "description": "A floating label naming a place/region in the room.",
            "interactions": ["tap"],
            "default_transform": {
                "anchor": "world",
                "position": [0.0, 1.5, 1.0],
                "rotation": [0, 0, 0, 1],
                "scale": [1, 1, 1],
                "billboard": True,
            },
            "props_schema": {
                "type": "object",
                "required": ["text"],
                "properties": {
                    "text": {"type": "string"},
                    "color": {"type": "string"},
                },
            },
        },
        # --- P1 feature widgets (lightweight fallbacks). ---
        "clock": {
            "prefab_id": "Clock",
            "description": "A clock showing the current time/date.",
            "interactions": ["grab", "tap"],
            "default_transform": {
                "anchor": "head", "position": [0.0, 0.3, 1.0],
                "rotation": [0, 0, 0, 1], "scale": [1, 1, 1], "billboard": True,
            },
            "props_schema": {
                "type": "object",
                "properties": {
                    "time": {"type": "string"}, "date": {"type": "string"},
                    "tz": {"type": "string"}, "label": {"type": "string"},
                },
            },
        },
        "world_clock": {
            "prefab_id": "WorldClock",
            "description": "Clocks for multiple time zones.",
            "interactions": ["grab", "tap"],
            "default_transform": {
                "anchor": "world", "position": [0.0, 1.4, 1.1],
                "rotation": [0, 0, 0, 1], "scale": [1, 1, 1], "billboard": True,
            },
            "props_schema": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"}, "zones": {"type": "array"},
                },
            },
        },
        "calendar": {
            "prefab_id": "Calendar",
            "description": "A calendar / agenda of upcoming events.",
            "interactions": ["grab", "tap", "resize", "scroll"],
            "default_transform": {
                "anchor": "world", "position": [0.0, 1.4, 1.1],
                "rotation": [0, 0, 0, 1], "scale": [1, 1, 1], "billboard": False,
            },
            "props_schema": {
                "type": "object",
                "additionalProperties": False,
                "required": ["events"],
                "properties": {
                    "title": {"type": "string"},
                    "view": {"type": "string", "enum": ["day", "week", "month", "agenda"]},
                    "date": {"type": "string"},
                    "events": {"type": "array"},
                },
            },
        },
        "stocks_ticker": {
            "prefab_id": "StocksTicker",
            "description": "A scrolling ticker of stock quotes.",
            "interactions": ["grab", "tap"],
            "default_transform": {
                "anchor": "head", "position": [0.0, 0.4, 1.2],
                "rotation": [0, 0, 0, 1], "scale": [1, 1, 1], "billboard": True,
            },
            "props_schema": {
                "type": "object",
                "additionalProperties": False,
                "required": ["symbols"],
                "properties": {
                    "title": {"type": "string"},
                    "symbols": {"type": "array"},
                    "scroll": {"type": "boolean"},
                },
            },
        },
        "news_feed": {
            "prefab_id": "NewsFeed",
            "description": "A panel of news headlines.",
            "interactions": ["grab", "tap", "resize", "scroll"],
            "default_transform": {
                "anchor": "world", "position": [0.0, 1.4, 1.1],
                "rotation": [0, 0, 0, 1], "scale": [1, 1, 1], "billboard": False,
            },
            "props_schema": {
                "type": "object",
                "additionalProperties": False,
                "required": ["articles"],
                "properties": {
                    "title": {"type": "string"},
                    "category": {"type": "string"},
                    "articles": {"type": "array"},
                },
            },
        },
        "translator": {
            "prefab_id": "Translator",
            "description": "Shows source text and its translation.",
            "interactions": ["grab", "tap"],
            "default_transform": {
                "anchor": "head", "position": [0.0, 0.0, 1.0],
                "rotation": [0, 0, 0, 1], "scale": [1, 1, 1], "billboard": True,
            },
            "props_schema": {
                "type": "object",
                "additionalProperties": False,
                "required": ["source_lang", "target_lang"],
                "properties": {
                    "source_lang": {"type": "string"},
                    "target_lang": {"type": "string"},
                    "source_text": {"type": "string"},
                    "translated_text": {"type": "string"},
                    "mode": {"type": "string", "enum": ["text", "conversation", "sign"]},
                    "listening": {"type": "boolean"},
                },
            },
        },
        "navigation_arrow": {
            "prefab_id": "NavigationArrow",
            "description": "A wayfinding arrow pointing toward a destination.",
            "interactions": ["tap"],
            "default_transform": {
                "anchor": "head", "position": [0.0, -0.2, 1.0],
                "rotation": [0, 0, 0, 1], "scale": [1, 1, 1], "billboard": True,
            },
            "props_schema": {
                "type": "object",
                "additionalProperties": False,
                "required": ["direction"],
                "properties": {
                    "target_label": {"type": "string"},
                    "direction": {"type": "array"},
                    "distance_m": {"type": "number"},
                    "eta_min": {"type": "number"},
                    "color": {"type": "string"},
                    "style": {"type": "string", "enum": ["arrow", "beam", "path"]},
                },
            },
        },
        "measuring_tape": {
            "prefab_id": "MeasuringTape",
            "description": "A spatial measurement between two points.",
            "interactions": ["grab", "tap"],
            "default_transform": {
                "anchor": "world", "position": [0.0, 1.0, 0.8],
                "rotation": [0, 0, 0, 1], "scale": [1, 1, 1], "billboard": False,
            },
            "props_schema": {
                "type": "object",
                "additionalProperties": False,
                "required": ["points"],
                "properties": {
                    "points": {"type": "array"},
                    "unit": {"type": "string", "enum": ["m", "cm", "ft", "in"]},
                    "distance_m": {"type": "number"},
                    "mode": {"type": "string", "enum": ["distance", "area", "angle"]},
                    "label": {"type": "string"},
                },
            },
        },
        "data_table": {
            "prefab_id": "DataTable",
            "description": "A tabular data grid.",
            "interactions": ["grab", "tap", "resize", "scroll"],
            "default_transform": {
                "anchor": "world", "position": [0.0, 1.4, 1.1],
                "rotation": [0, 0, 0, 1], "scale": [1, 1, 1], "billboard": False,
            },
            "props_schema": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"}, "columns": {"type": "array"},
                    "rows": {"type": "array"},
                },
            },
        },
        "sticky_note": {
            "prefab_id": "StickyNote",
            "description": "A small sticky note pinned in space.",
            "interactions": ["grab", "tap"],
            "default_transform": {
                "anchor": "world", "position": [0.3, 1.3, 0.9],
                "rotation": [0, 0, 0, 1], "scale": [1, 1, 1], "billboard": True,
            },
            "props_schema": {
                "type": "object",
                "required": ["text"],
                "properties": {
                    "text": {"type": "string"}, "color": {"type": "string"},
                },
            },
        },
        "web_panel": {
            "prefab_id": "WebPanel",
            "description": "A browser surface / web content panel.",
            "interactions": ["grab", "tap", "resize", "scroll"],
            "default_transform": {
                "anchor": "world", "position": [0.0, 1.4, 1.1],
                "rotation": [0, 0, 0, 1], "scale": [1, 1, 1], "billboard": False,
            },
            "props_schema": {
                "type": "object",
                "additionalProperties": False,
                "required": ["url"],
                "properties": {
                    "url": {"type": "string"},
                    "title": {"type": "string"},
                    "width_m": {"type": "number"},
                    "height_m": {"type": "number"},
                    "interactive": {"type": "boolean"},
                    "scroll_y": {"type": "number"},
                },
            },
        },
        # --- v1 widgets also present in fallback so offline mode (no registry)
        # still covers them. ---
        "text_label": {
            "prefab_id": "TextLabel",
            "description": "A floating text label.",
            "interactions": ["tap", "grab"],
            "default_transform": {
                "anchor": "head", "position": [0.0, 0.2, 1.0],
                "rotation": [0, 0, 0, 1], "scale": [1, 1, 1], "billboard": True,
            },
            "props_schema": {
                "type": "object",
                "required": ["text"],
                "properties": {"text": {"type": "string"}, "color": {"type": "string"}},
            },
        },
        "todo_list": {
            "prefab_id": "TodoList",
            "description": "A checkable list of tasks.",
            "interactions": ["grab", "tap", "resize", "toggle"],
            "default_transform": {
                "anchor": "world", "position": [-0.4, 1.3, 1.0],
                "rotation": [0, 0, 0, 1], "scale": [1, 1, 1], "billboard": True,
            },
            "props_schema": {
                "type": "object",
                "required": ["items"],
                "properties": {"title": {"type": "string"}, "items": {"type": "array"}},
            },
        },
        "image_board": {
            "prefab_id": "ImageBoard",
            "description": "A grid/carousel of images.",
            "interactions": ["grab", "tap", "resize"],
            "default_transform": {
                "anchor": "world", "position": [0.0, 1.4, 1.2],
                "rotation": [0, 0, 0, 1], "scale": [1, 1, 1], "billboard": False,
            },
            "props_schema": {
                "type": "object",
                "required": ["images"],
                "properties": {"title": {"type": "string"}, "images": {"type": "array"}},
            },
        },
    },
}

# JSON-schema "type" -> python types accepted (numbers accept ints; ints reject bool).
_TYPE_MAP: dict[str, tuple[type, ...]] = {
    "string": (str,),
    "number": (int, float),
    "integer": (int,),
    "boolean": (bool,),
    "array": (list,),
    "object": (dict,),
}


class WidgetCatalog:
    """In-memory widget catalog with light props validation."""

    def __init__(self, data: dict[str, Any], *, source: str = "builtin"):
        self.version: str = str(data.get("version", "0.0.0"))
        self.source = data.get("source", source)
        self.widgets: dict[str, WidgetSpec] = {
            name: WidgetSpec.from_entry(name, entry)
            for name, entry in self._normalize_widgets(data).items()
        }

    @staticmethod
    def _normalize_widgets(data: dict[str, Any]) -> dict[str, dict[str, Any]]:
        """`widgets` may be a dict keyed by widget_type (our fallback) OR a list of
        entries each carrying its own `widget_type` (canonical registry.json).
        Normalize both to a {widget_type: entry} dict.
        """
        widgets_raw = data.get("widgets", {}) or {}
        entries: dict[str, dict[str, Any]] = {}
        if isinstance(widgets_raw, list):
            for entry in widgets_raw:
                if isinstance(entry, dict) and entry.get("widget_type"):
                    entries[entry["widget_type"]] = entry
        elif isinstance(widgets_raw, dict):
            entries = dict(widgets_raw)
        return entries

    def merge_missing(self, data: dict[str, Any]) -> int:
        """Add widgets from ``data`` that aren't already present. Returns count.

        Used to augment the canonical registry with our built-in fallbacks for
        widgets holo-tools hasn't published yet (e.g. v1.1 perception widgets),
        so the backend is never blocked. Published widgets always win.
        """
        added = 0
        for name, entry in self._normalize_widgets(data).items():
            if name not in self.widgets:
                self.widgets[name] = WidgetSpec.from_entry(name, entry)
                added += 1
        return added

    # -- construction -------------------------------------------------------

    @classmethod
    def builtin(cls) -> "WidgetCatalog":
        return cls(_FALLBACK, source="builtin")

    @classmethod
    def load(cls, path: Optional[Path]) -> "WidgetCatalog":
        """Load ``registry.json`` if present (then merge in any missing built-in
        fallback widgets), else use the built-in fallback catalog entirely."""
        if path and Path(path).is_file():
            try:
                data = json.loads(Path(path).read_text(encoding="utf-8"))
                cat = cls(data, source=str(path))
                if not cat.widgets:
                    log.warning(
                        "registry.json at %s had no widgets; using fallback", path
                    )
                    return cls.builtin()
                published = len(cat.widgets)
                added = cat.merge_missing(_FALLBACK)
                cat.source = f"{path} (+{added} builtin fallback)" if added else str(path)
                log.info(
                    "loaded widget catalog from %s (%d published + %d fallback = "
                    "%d widgets, v%s)",
                    path,
                    published,
                    added,
                    len(cat.widgets),
                    cat.version,
                )
                return cat
            except Exception as exc:  # noqa: BLE001
                log.warning(
                    "failed to parse registry.json at %s (%s); using fallback",
                    path,
                    exc,
                )
                return cls.builtin()
        log.info(
            "holo-tools registry.json not found (looked at %s); using built-in "
            "fallback catalog (%d widgets)",
            path,
            len(_FALLBACK["widgets"]),
        )
        return cls.builtin()

    # -- queries ------------------------------------------------------------

    def has(self, widget_type: str) -> bool:
        return widget_type in self.widgets

    def get(self, widget_type: str) -> Optional[WidgetSpec]:
        return self.widgets.get(widget_type)

    def names(self) -> list[str]:
        return sorted(self.widgets.keys())

    def default_transform(self, widget_type: str) -> dict[str, Any]:
        spec = self.widgets.get(widget_type)
        return dict(spec.default_transform) if spec and spec.default_transform else {}

    def supported_interactions(self, widget_type: str) -> list[str]:
        spec = self.widgets.get(widget_type)
        return list(spec.interactions) if spec else []

    # -- validation ---------------------------------------------------------

    def validate(self, widget_type: str, props: dict[str, Any]) -> None:
        """Validate a widget + props. Raises :class:`CatalogError` on failure.

        Validation is intentionally *light* and defensive: it enforces widget
        existence and (when a recognizable ``props_schema`` is present) required
        keys, basic types, and enums. Unknown schema shapes are skipped so we
        stay forward-compatible with whatever holo-tools eventually publishes.
        """
        spec = self.widgets.get(widget_type)
        if spec is None:
            raise CatalogError(
                "unknown_widget",
                f"widget_type '{widget_type}' not in registry "
                f"(known: {', '.join(self.names())})",
            )
        schema = spec.props_schema
        if not isinstance(schema, dict) or schema.get("type") != "object":
            return  # no/unknown schema -> accept

        required = schema.get("required", []) or []
        for key in required:
            if key not in props:
                raise CatalogError(
                    "invalid_props",
                    f"widget '{widget_type}' missing required prop '{key}'",
                )

        properties = schema.get("properties", {}) or {}
        # Enforce closed object schemas (canonical registry sets this).
        if schema.get("additionalProperties") is False:
            for key in props:
                if key not in properties:
                    raise CatalogError(
                        "invalid_props",
                        f"widget '{widget_type}' has unknown prop '{key}'",
                    )
        for key, value in props.items():
            pschema = properties.get(key)
            if not isinstance(pschema, dict):
                continue  # unspecified prop -> allowed
            expected = pschema.get("type")
            accepted = _TYPE_MAP.get(expected) if expected else None
            if accepted is not None:
                # bool is a subclass of int; reject it for number/integer.
                if expected in {"number", "integer"} and isinstance(value, bool):
                    raise CatalogError(
                        "invalid_props",
                        f"widget '{widget_type}' prop '{key}' must be {expected}",
                    )
                if not isinstance(value, accepted):
                    raise CatalogError(
                        "invalid_props",
                        f"widget '{widget_type}' prop '{key}' must be {expected}",
                    )
            enum = pschema.get("enum")
            if enum and value not in enum:
                raise CatalogError(
                    "invalid_props",
                    f"widget '{widget_type}' prop '{key}' must be one of {enum}",
                )


__all__ = ["WidgetCatalog", "WidgetSpec", "CatalogError"]
