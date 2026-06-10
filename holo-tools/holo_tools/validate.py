"""Validation utilities for JarvisVR holographic objects and widget props.

Errors are surfaced with codes that match the wire protocol (``docs/PROTOCOL.md``
section 5.13): ``unknown_widget`` and ``invalid_props``. Each exception can be
turned into a ``server.error`` payload via :meth:`HoloValidationError.to_error_payload`.

Design notes
------------
* Widget **props** are validated strictly against the catalog's JSON Schema
  (``additionalProperties: false``) so the agent can't hallucinate unknown props.
* The surrounding **holo object** envelope (transform/interactions/ttl) is validated
  leniently (unknown keys ignored) to honour the protocol's forward-compatibility
  rule, while still type-checking the known fields.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from jsonschema import Draft202012Validator

from . import loader

_DEFAULT_ANCHORS = ["world", "head", "hand_left", "hand_right", "surface"]
_DEFAULT_INTERACTIONS = ["tap", "grab", "release", "drag", "slider", "toggle", "resize", "dwell"]


class HoloValidationError(Exception):
    """Base class for catalog validation errors. Carries a protocol error ``code``."""

    code = "invalid"

    def __init__(self, message: str, *, code: Optional[str] = None, errors: Optional[List[str]] = None):
        super().__init__(message)
        self.message = message
        if code is not None:
            self.code = code
        self.errors = list(errors or [])

    def to_error_payload(self, fatal: bool = False) -> Dict[str, Any]:
        """Render as a ``server.error`` / ``client.error`` payload (PROTOCOL.md 5.13)."""
        return {"code": self.code, "message": self.message, "fatal": fatal}

    def __str__(self) -> str:
        return f"[{self.code}] {self.message}"


class UnknownWidgetError(HoloValidationError):
    """The ``widget_type`` is not present in the registry."""

    code = "unknown_widget"


class InvalidPropsError(HoloValidationError):
    """The props (or holo object structure) failed schema validation."""

    code = "invalid_props"


def _registry() -> Dict[str, Any]:
    return loader.load_registry()


def _anchors() -> List[str]:
    return list(_registry().get("anchors", _DEFAULT_ANCHORS))


def _interactions() -> List[str]:
    return list(_registry().get("interactions", _DEFAULT_INTERACTIONS))


def get_widget(widget_type: str) -> Dict[str, Any]:
    """Return the registry entry for ``widget_type`` or raise :class:`UnknownWidgetError`."""
    widgets = loader.widgets_by_type()
    if widget_type not in widgets:
        known = ", ".join(sorted(widgets))
        raise UnknownWidgetError(
            f"widget_type {widget_type!r} not in registry (known: {known})"
        )
    return widgets[widget_type]


def _format_error(err) -> str:
    location = "/".join(str(p) for p in err.absolute_path)
    where = f" (at '/{location}')" if location else ""
    return f"{err.message}{where}"


def iter_widget_errors(widget_type: str, props: Any) -> List[str]:
    """Return a list of human-readable validation errors for ``props`` (empty if valid)."""
    widget = get_widget(widget_type)
    validator = Draft202012Validator(widget["props_schema"])
    return [
        _format_error(e)
        for e in sorted(validator.iter_errors(props), key=lambda e: list(e.absolute_path))
    ]


def validate_widget(widget_type: str, props: Any) -> Dict[str, Any]:
    """Validate ``props`` for ``widget_type``.

    Returns the validated props on success. Raises :class:`UnknownWidgetError`
    if the widget is unknown, or :class:`InvalidPropsError` if props are invalid.
    """
    # get_widget raises UnknownWidgetError for unknown types.
    get_widget(widget_type)
    if not isinstance(props, dict):
        raise InvalidPropsError(
            f"props for widget {widget_type!r} must be a JSON object, got {type(props).__name__}"
        )
    errors = iter_widget_errors(widget_type, props)
    if errors:
        raise InvalidPropsError(
            f"props for widget {widget_type!r} failed validation: " + "; ".join(errors),
            errors=errors,
        )
    return props


def is_valid_widget(widget_type: str, props: Any) -> bool:
    """Boolean convenience wrapper around :func:`validate_widget`."""
    try:
        validate_widget(widget_type, props)
        return True
    except HoloValidationError:
        return False


def _transform_schema() -> Dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": True,
        "properties": {
            "anchor": {"enum": _anchors()},
            "position": {"type": "array", "items": {"type": "number"}, "minItems": 3, "maxItems": 3},
            "rotation": {"type": "array", "items": {"type": "number"}, "minItems": 4, "maxItems": 4},
            "scale": {"type": "array", "items": {"type": "number"}, "minItems": 3, "maxItems": 3},
            "billboard": {"type": "boolean"},
        },
    }


def holo_object_schema() -> Dict[str, Any]:
    """JSON Schema for the holo-object envelope (PROTOCOL.md 5.6), minus widget props."""
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "additionalProperties": True,
        "required": ["widget_type"],
        "properties": {
            "object_id": {"type": "string"},
            "widget_type": {"type": "string"},
            "transform": _transform_schema(),
            "props": {"type": "object"},
            "interactable": {"type": "boolean"},
            "interactions": {"type": "array", "items": {"enum": _interactions()}},
            "ttl_ms": {"type": "integer", "minimum": 0},
        },
    }


def validate_holo_object(obj: Any) -> Dict[str, Any]:
    """Validate a full holographic object (PROTOCOL.md 5.6).

    Checks (in order): is an object; has a known ``widget_type``; the envelope
    structure (transform/interactions/ttl) type-checks; the requested
    ``interactions`` are a subset of the widget's supported set; and the
    widget-specific ``props`` validate. Returns ``obj`` on success.
    """
    if not isinstance(obj, dict):
        raise InvalidPropsError(f"holo object must be a JSON object, got {type(obj).__name__}")

    widget_type = obj.get("widget_type")
    if not isinstance(widget_type, str) or not widget_type:
        raise InvalidPropsError("holo object missing required string field 'widget_type'")

    widget = get_widget(widget_type)  # raises UnknownWidgetError

    # Structural validation of everything except the widget-specific props blob.
    validator = Draft202012Validator(holo_object_schema())
    structural = {k: v for k, v in obj.items() if k != "props"}
    errors = [
        _format_error(e)
        for e in sorted(validator.iter_errors(structural), key=lambda e: list(e.absolute_path))
    ]
    if errors:
        raise InvalidPropsError(
            "holo object structure invalid: " + "; ".join(errors), errors=errors
        )

    # interactions must be a subset of the widget's supported set.
    requested = obj.get("interactions")
    if requested is not None:
        supported = set(widget.get("interactions", []))
        bad = [i for i in requested if i not in supported]
        if bad:
            raise InvalidPropsError(
                f"interactions {bad} not supported by widget {widget_type!r} "
                f"(supports: {sorted(supported)})",
                errors=[f"unsupported interaction: {i}" for i in bad],
            )

    # widget-specific props.
    validate_widget(widget_type, obj.get("props", {}))
    return obj
