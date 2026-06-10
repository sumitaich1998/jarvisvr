"""Deterministic, offline "vision".

When no real vision LLM is configured (the default), Jarvis still needs to talk
about what the user sees. This module synthesizes a plausible, *deterministic*
scene description from whatever signals are available:

1. client-side ``perception.scene_objects`` (preferred — real detections), else
2. a canned desk scene, so vision Q&A always works offline.

It also provides a mock OCR and a tiny mock translator for read/translate tools.
"""

from __future__ import annotations

import hashlib
import math
from typing import Any, Optional

# A plausible default scene (world-anchored, ~desk height in front of the user).
CANNED_OBJECTS: list[dict[str, Any]] = [
    {"label": "coffee mug", "confidence": 0.82, "position": [0.30, 0.80, 0.70], "anchor": "world"},
    {"label": "laptop", "confidence": 0.91, "position": [0.00, 0.80, 0.70], "anchor": "world"},
    {"label": "notebook", "confidence": 0.74, "position": [-0.30, 0.78, 0.70], "anchor": "world"},
    {"label": "potted plant", "confidence": 0.69, "position": [0.62, 0.95, 0.85], "anchor": "world"},
    {"label": "smartphone", "confidence": 0.77, "position": [0.18, 0.79, 0.60], "anchor": "world"},
]

# A few canned signs OCR can "read" when no scene text is present.
_CANNED_SIGNS = [
    "CAFÉ — Open 7am to 7pm. Free Wi-Fi.",
    "CAUTION — Wet floor.",
    "Gate B12 — Boarding 14:35.",
    "Museum of Modern Art — Tickets this way.",
]

# Tiny offline phrase translator (enough for a believable demo).
_PHRASES: dict[str, dict[str, str]] = {
    "es": {
        "hello": "hola", "open": "abierto", "closed": "cerrado", "exit": "salida",
        "welcome": "bienvenido", "free": "gratis", "caution": "precaución",
        "wet floor": "piso mojado", "tickets": "entradas", "this way": "por aquí",
    },
    "fr": {
        "hello": "bonjour", "open": "ouvert", "closed": "fermé", "exit": "sortie",
        "welcome": "bienvenue", "free": "gratuit", "caution": "attention",
        "wet floor": "sol mouillé", "tickets": "billets", "this way": "par ici",
    },
    "de": {
        "hello": "hallo", "open": "offen", "closed": "geschlossen", "exit": "ausgang",
        "welcome": "willkommen", "free": "kostenlos", "caution": "vorsicht",
    },
    "ja": {
        "hello": "こんにちは", "open": "営業中", "closed": "閉店", "exit": "出口",
        "welcome": "ようこそ", "free": "無料",
    },
    "hi": {
        "hello": "नमस्ते", "open": "खुला", "closed": "बंद", "exit": "निकास",
        "welcome": "स्वागत है", "free": "मुफ़्त",
    },
}

_LANG_ALIASES = {
    "spanish": "es", "español": "es", "espanol": "es", "es": "es",
    "french": "fr", "français": "fr", "francais": "fr", "fr": "fr",
    "german": "de", "deutsch": "de", "de": "de",
    "japanese": "ja", "ja": "ja", "jp": "ja",
    "hindi": "hi", "hi": "hi",
}


def normalize_lang(lang: Optional[str]) -> str:
    if not lang:
        return "es"
    return _LANG_ALIASES.get(lang.strip().lower(), lang.strip().lower())


def scene_objects(context: dict[str, Any]) -> list[dict[str, Any]]:
    """Detected objects if the client provided them, else the canned scene."""
    objs = context.get("objects") or []
    return objs if objs else CANNED_OBJECTS


def _join_labels(labels: list[str]) -> str:
    labels = [str(x) for x in labels if x]
    if not labels:
        return "nothing in particular"
    if len(labels) == 1:
        return labels[0]
    if len(labels) == 2:
        return f"{labels[0]} and {labels[1]}"
    return ", ".join(labels[:-1]) + f", and {labels[-1]}"


def describe_scene(context: dict[str, Any], *, max_objects: int = 4) -> dict[str, Any]:
    """Return ``{text, objects}`` describing the current view (deterministic)."""
    objs = scene_objects(context)[:max_objects]
    labels = [o.get("label", "object") for o in objs]
    source = "your camera" if context.get("objects") else "your desk"
    text = f"I can see {_join_labels(labels)} on {source}."
    return {"text": text, "objects": objs}


def _distance(a: list[float], b: list[float]) -> float:
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


def focus_object(context: dict[str, Any]) -> Optional[dict[str, Any]]:
    """The object the user is most likely asking about.

    Preference: gaze-hit object id match -> nearest object to the gaze hit point
    -> first detected/canned object.
    """
    objs = scene_objects(context)
    if not objs:
        return None
    gaze = context.get("gaze") or {}
    hit_id = gaze.get("hit_object_id")
    if hit_id:
        for o in objs:
            if o.get("object_id") == hit_id or o.get("id") == hit_id:
                return o
    hit_point = gaze.get("hit_point")
    if isinstance(hit_point, list) and len(hit_point) == 3:
        placed = [o for o in objs if isinstance(o.get("position"), list)]
        if placed:
            return min(placed, key=lambda o: _distance(o["position"], hit_point))
    return objs[0]


def mock_ocr(context: dict[str, Any]) -> str:
    """Return text 'read' from the view (deterministic, offline)."""
    # If any detected object carries text, prefer it.
    for o in context.get("objects") or []:
        if o.get("text"):
            return str(o["text"])
    frame = context.get("frame") or {}
    seed = str(frame.get("frame_id") or frame.get("seq") or "0")
    idx = int(hashlib.sha256(seed.encode()).hexdigest(), 16) % len(_CANNED_SIGNS)
    return _CANNED_SIGNS[idx]


def mock_translate(text: str, target_lang: str) -> str:
    """A tiny deterministic translator; good enough for an offline demo."""
    lang = normalize_lang(target_lang)
    table = _PHRASES.get(lang)
    if not table:
        return f"[{lang}] {text}"
    low = text.lower()
    # Phrase-level replacements first (longest keys), then word-level.
    out = text
    for key in sorted(table, key=len, reverse=True):
        if key in low:
            out = _ci_replace(out, key, table[key])
            low = out.lower()
    # If nothing matched, mark it so the user knows it's a (mock) translation.
    if out == text:
        return f"[{lang}] {text}"
    return out


def _ci_replace(text: str, key: str, repl: str) -> str:
    low = text.lower()
    result = []
    i = 0
    while i < len(text):
        if low.startswith(key, i):
            result.append(repl)
            i += len(key)
        else:
            result.append(text[i])
            i += 1
    return "".join(result)


__all__ = [
    "CANNED_OBJECTS",
    "scene_objects",
    "describe_scene",
    "focus_object",
    "mock_ocr",
    "mock_translate",
    "normalize_lang",
]
