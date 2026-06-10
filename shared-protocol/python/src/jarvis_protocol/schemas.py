"""Loads the canonical JSON Schemas and builds Draft 2020-12 validators.

The schemas in ``shared-protocol/schema`` are the single source of truth. This
module locates that directory, registers every schema by ``$id`` so that
cross-file ``$ref``s resolve, and exposes cached validators.

Resolution order for the schema directory:
  1. ``$JARVIS_PROTOCOL_SCHEMA_DIR`` env var, if it points at a dir with the schemas.
  2. The nearest ``schema/`` directory walking up from this file (works for an
     editable/source checkout).
"""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Dict, Optional

from jsonschema import Draft202012Validator
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

from .catalog import TYPE_TO_SCHEMA


def _find_schema_dir() -> Path:
    candidates = []
    env = os.environ.get("JARVIS_PROTOCOL_SCHEMA_DIR")
    if env:
        candidates.append(Path(env))
    here = Path(__file__).resolve()
    candidates.extend(parent / "schema" for parent in here.parents)
    for cand in candidates:
        if (cand / "envelope.schema.json").is_file():
            return cand
    raise RuntimeError(
        "Could not locate shared-protocol/schema. "
        "Set the JARVIS_PROTOCOL_SCHEMA_DIR environment variable to its path."
    )


#: Absolute path to the canonical schema directory.
SCHEMA_DIR: Path = _find_schema_dir()


@lru_cache(maxsize=1)
def load_schemas() -> Dict[str, dict]:
    """Return ``{filename: schema}`` for every ``*.schema.json`` in SCHEMA_DIR."""
    schemas: Dict[str, dict] = {}
    for path in sorted(SCHEMA_DIR.glob("*.schema.json")):
        schemas[path.name] = json.loads(path.read_text(encoding="utf-8"))
    if "envelope.schema.json" not in schemas:  # pragma: no cover - sanity
        raise RuntimeError(f"envelope.schema.json missing from {SCHEMA_DIR}")
    return schemas


@lru_cache(maxsize=1)
def _registry() -> Registry:
    resources = [
        (schema["$id"], Resource.from_contents(schema, default_specification=DRAFT202012))
        for schema in load_schemas().values()
    ]
    return Registry().with_resources(resources)


@lru_cache(maxsize=1)
def envelope_validator() -> Draft202012Validator:
    return Draft202012Validator(load_schemas()["envelope.schema.json"], registry=_registry())


@lru_cache(maxsize=None)
def payload_validator(type_name: str) -> Optional[Draft202012Validator]:
    """Validator for a message ``type``'s payload, or ``None`` if unknown."""
    filename = TYPE_TO_SCHEMA.get(type_name)
    if filename is None:
        return None
    return Draft202012Validator(load_schemas()[filename], registry=_registry())


__all__ = [
    "SCHEMA_DIR",
    "load_schemas",
    "envelope_validator",
    "payload_validator",
]
