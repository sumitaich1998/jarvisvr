"""jarvis-holo-tools — the JarvisVR holographic widget catalog.

Importing this package gives you the parsed catalog plus validators::

    import holo_tools as ht

    ht.WIDGET_TYPES            # ['weather_orb', 'chart_3d', ...]
    ht.WIDGETS_BY_TYPE['timer']
    ht.TOOLS_BY_NAME['show_weather']

    ht.validate_widget('weather_orb', {'city': 'Tokyo', 'temp_c': 18, 'condition': 'clouds'})
    ht.validate_holo_object({'widget_type': 'timer', 'props': {...}})

The catalog itself lives in language-neutral ``registry.json`` / ``tools.json`` at
the root of ``holo-tools/`` so non-Python consumers (Unity C#, TypeScript) can read
the exact same source of truth.
"""

from __future__ import annotations

from . import loader, tools, validate
from .loader import (
    CatalogFileNotFound,
    get_tools,
    get_widgets,
    load_registry,
    load_tools,
    registry_path,
    tools_path,
    widgets_by_type,
)
from .tools import WIDGET_TOOL_NAMES, derive_tools, derive_widget_tool
from .validate import (
    HoloValidationError,
    InvalidPropsError,
    UnknownWidgetError,
    get_widget,
    is_valid_widget,
    iter_widget_errors,
    validate_holo_object,
    validate_widget,
)

REGISTRY = load_registry()
WIDGETS = get_widgets(REGISTRY)
WIDGETS_BY_TYPE = widgets_by_type(REGISTRY)
WIDGET_TYPES = [w["widget_type"] for w in WIDGETS]
VERSION = REGISTRY.get("version")
PROTOCOL_VERSION = REGISTRY.get("protocol_version")
ANCHORS = REGISTRY.get("anchors", [])
INTERACTIONS = REGISTRY.get("interactions", [])
CATEGORIES = REGISTRY.get("categories", [])

# tools.json is a derived artifact; fall back to deriving it if the file is absent
# (e.g. during first-time generation).
try:
    TOOLS_DOC = load_tools()
except CatalogFileNotFound:  # pragma: no cover - only during bootstrap
    TOOLS_DOC = derive_tools(REGISTRY)
TOOLS = TOOLS_DOC.get("tools", [])
TOOLS_BY_NAME = {t["name"]: t for t in TOOLS}

__version__ = VERSION or "1.0.0"

__all__ = [
    # submodules
    "loader",
    "tools",
    "validate",
    # catalog data
    "REGISTRY",
    "WIDGETS",
    "WIDGETS_BY_TYPE",
    "WIDGET_TYPES",
    "VERSION",
    "PROTOCOL_VERSION",
    "ANCHORS",
    "INTERACTIONS",
    "CATEGORIES",
    "TOOLS_DOC",
    "TOOLS",
    "TOOLS_BY_NAME",
    # loaders
    "load_registry",
    "load_tools",
    "registry_path",
    "tools_path",
    "get_widgets",
    "widgets_by_type",
    "get_tools",
    "CatalogFileNotFound",
    # validators
    "validate_widget",
    "validate_holo_object",
    "is_valid_widget",
    "iter_widget_errors",
    "get_widget",
    "HoloValidationError",
    "UnknownWidgetError",
    "InvalidPropsError",
    # tool derivation
    "derive_tools",
    "derive_widget_tool",
    "WIDGET_TOOL_NAMES",
]
