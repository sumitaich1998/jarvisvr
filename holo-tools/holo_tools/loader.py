"""Loading helpers for the JarvisVR holographic tools catalog.

The catalog ships as two language-neutral JSON files that live at the root of
``holo-tools/``:

* ``registry.json`` — the canonical widget catalog (single source of truth).
* ``tools.json``    — agent-facing tool/function-calling schemas.

These loaders locate those files by searching upward from this module, so they
work whether the package is imported from an editable install (``pip install -e .``)
or run directly from the source tree.
"""

from __future__ import annotations

import functools
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

REGISTRY_FILENAME = "registry.json"
TOOLS_FILENAME = "tools.json"

#: Environment variables that override catalog file locations. Resolution order is
#: explicit ``path=`` argument > environment variable > upward filesystem search.
#: Useful for packaged/containerized deployments where the JSON lives outside the
#: source tree.
REGISTRY_ENV = "JARVIS_HOLO_REGISTRY"
TOOLS_ENV = "JARVIS_HOLO_TOOLS"


class CatalogFileNotFound(FileNotFoundError):
    """Raised when a catalog JSON file cannot be located."""


def _search_upwards(filename: str, start: Optional[Path] = None) -> Path:
    """Return the first ``filename`` found in ``start`` or any parent directory."""
    base = Path(start) if start else Path(__file__).resolve()
    if base.is_file():
        base = base.parent
    for directory in [base, *base.parents]:
        candidate = directory / filename
        if candidate.is_file():
            return candidate
    raise CatalogFileNotFound(
        f"Could not locate {filename!r} starting from {base}. "
        "Run from the holo-tools source tree or pass an explicit path."
    )


def _resolve_catalog_path(filename: str, env_var: str) -> Path:
    """Resolve a catalog file: honour the env-var override, else search upward."""
    override = os.environ.get(env_var)
    if override:
        candidate = Path(override)
        if not candidate.is_file():
            raise CatalogFileNotFound(
                f"{env_var}={override!r} does not point to an existing file"
            )
        return candidate
    return _search_upwards(filename)


def registry_path() -> Path:
    """Absolute path to ``registry.json`` (honours ``$JARVIS_HOLO_REGISTRY``)."""
    return _resolve_catalog_path(REGISTRY_FILENAME, REGISTRY_ENV)


def tools_path() -> Path:
    """Absolute path to ``tools.json`` (honours ``$JARVIS_HOLO_TOOLS``)."""
    return _resolve_catalog_path(TOOLS_FILENAME, TOOLS_ENV)


@functools.lru_cache(maxsize=None)
def load_registry(path: Optional[str] = None) -> Dict[str, Any]:
    """Load and parse ``registry.json`` (cached)."""
    resolved = Path(path) if path else registry_path()
    with resolved.open(encoding="utf-8") as fh:
        return json.load(fh)


@functools.lru_cache(maxsize=None)
def load_tools(path: Optional[str] = None) -> Dict[str, Any]:
    """Load and parse ``tools.json`` (cached)."""
    resolved = Path(path) if path else tools_path()
    with resolved.open(encoding="utf-8") as fh:
        return json.load(fh)


def get_widgets(registry: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """Return the list of widget entries."""
    registry = registry if registry is not None else load_registry()
    return list(registry.get("widgets", []))


def widgets_by_type(registry: Optional[Dict[str, Any]] = None) -> Dict[str, Dict[str, Any]]:
    """Return a mapping of ``widget_type`` -> widget entry."""
    return {w["widget_type"]: w for w in get_widgets(registry)}


def get_tools(tools_doc: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """Return the list of tool schemas."""
    tools_doc = tools_doc if tools_doc is not None else load_tools()
    return list(tools_doc.get("tools", []))
