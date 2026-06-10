"""Best-effort validation of holo objects against holo-tools/registry.json.

The registry is owned by another team and its exact shape isn't pinned yet, so
this module is defensive: it discovers known ``widget_type`` names and, when a
per-widget props JSON Schema is recognizable, validates ``props`` against it.

Policy:
  * widget_type membership      -> hard error if the registry is available.
  * props schema mismatch       -> warning by default; error when strict_props.
  * registry absent/unparseable -> everything is skipped (no errors).
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from jsonschema import Draft202012Validator

LOG = logging.getLogger("jarvis.e2e.holotools")

#: v1.1 perception widgets that may still be landing in holo-tools/registry.json.
#: If one of these isn't in the registry yet, membership is a *warning*, not a
#: failure (structural holo_object validation in shared-protocol still applies).
PENDING_WIDGETS = frozenset(
    {"vision_annotation", "bounding_box_3d", "live_caption", "vision_feed", "scene_label"}
)


def find_registry() -> Optional[Path]:
    env = os.environ.get("HOLO_TOOLS_REGISTRY")
    if env and Path(env).is_file():
        return Path(env)
    here = Path(__file__).resolve()
    for parent in here.parents:
        cand = parent / "holo-tools" / "registry.json"
        if cand.is_file():
            return cand
    return None


def _entry_type(entry: Any) -> Optional[str]:
    if isinstance(entry, dict):
        for key in ("widget_type", "type", "id", "name"):
            val = entry.get(key)
            if isinstance(val, str) and val:
                return val
    return None


def _entries(registry: Any) -> Dict[str, Any]:
    """Map widget_type -> its registry entry, across several plausible shapes."""
    out: Dict[str, Any] = {}
    if isinstance(registry, dict):
        container = registry.get("widgets", registry)
        if isinstance(container, dict):
            for key, val in container.items():
                if isinstance(key, str) and not key.startswith("$"):
                    out[key] = val
        elif isinstance(container, list):
            for entry in container:
                wt = _entry_type(entry)
                if wt:
                    out[wt] = entry
    elif isinstance(registry, list):
        for entry in registry:
            wt = _entry_type(entry)
            if wt:
                out[wt] = entry
    return out


def _looks_like_schema(value: Any) -> bool:
    return isinstance(value, dict) and any(k in value for k in ("type", "properties", "$schema", "allOf", "oneOf"))


def _props_schema(entry: Any) -> Optional[dict]:
    if not isinstance(entry, dict):
        return None
    for key in ("props_schema", "propsSchema", "propsSchemaJson", "schema", "props"):
        val = entry.get(key)
        if _looks_like_schema(val):
            return val
    return None


class HoloToolsValidator:
    def __init__(self, registry: Optional[Any], *, strict_props: bool = False):
        self.registry = registry
        self.strict_props = strict_props
        self._entries = _entries(registry) if registry is not None else {}
        self.widget_types = set(self._entries)

    @classmethod
    def load(cls, *, strict_props: bool = False) -> "HoloToolsValidator":
        path = find_registry()
        if not path:
            LOG.info("holo-tools/registry.json not found; holo-tools checks skipped")
            return cls(None, strict_props=strict_props)
        try:
            registry = json.loads(path.read_text(encoding="utf-8"))
            LOG.info("loaded holo-tools registry from %s", path)
            return cls(registry, strict_props=strict_props)
        except Exception as exc:  # noqa: BLE001
            LOG.warning("could not parse registry %s: %s; skipping holo-tools checks", path, exc)
            return cls(None, strict_props=strict_props)

    @property
    def available(self) -> bool:
        return self.registry is not None and bool(self.widget_types)

    def validate_holo(self, holo: Dict[str, Any]) -> Tuple[List[str], List[str]]:
        """Return (errors, warnings) for a holographic object payload."""
        errors: List[str] = []
        warnings: List[str] = []
        if not self.available:
            return errors, warnings

        widget_type = holo.get("widget_type")
        if widget_type not in self.widget_types:
            if widget_type in PENDING_WIDGETS:
                # In-flight v1.1 perception widget not in the registry yet: note, don't fail.
                warnings.append(
                    f"widget_type {widget_type!r} not in holo-tools registry yet "
                    "(v1.1 perception widget landing in parallel); skipped props validation"
                )
            else:
                errors.append(
                    f"widget_type {widget_type!r} not in holo-tools registry {sorted(self.widget_types)}"
                )
            return errors, warnings

        schema = _props_schema(self._entries.get(widget_type))
        if schema is None:
            warnings.append(f"no props schema for {widget_type!r} in registry; props not validated")
            return errors, warnings

        props = holo.get("props") or {}
        msgs = [
            f"props/{'/'.join(str(p) for p in e.path)}: {e.message}"
            for e in Draft202012Validator(schema).iter_errors(props)
        ]
        if msgs:
            (errors if self.strict_props else warnings).extend(f"{widget_type} {m}" for m in msgs)
        return errors, warnings
