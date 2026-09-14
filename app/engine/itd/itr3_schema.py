"""Cached validation for the official AY 2026-27 ITR-3 schema."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from jsonschema import Draft4Validator
from jsonschema.exceptions import SchemaError

_SCHEMA_RELATIVE_PATH = Path("Reference Docs by CBDT & ITD") / "Official JSON Schema" / "ITR-3_2026_Main_V1.1 (2).json"


class ITR3SchemaValidationError(ValueError):
    """Raised when an ITR-3 document violates the official schema."""

    def __init__(self, errors: list[dict[str, str]]) -> None:
        """Store structured, actionable validation errors."""
        self.errors = errors
        super().__init__("; ".join(f"{e['path'] or '$'}: {e['message']}" for e in errors))


@lru_cache(maxsize=1)
def get_itr3_schema_validator() -> Draft4Validator:
    """Load and cache the official Draft-4 ITR-3 validator."""
    path = Path(__file__).resolve().parents[3] / _SCHEMA_RELATIVE_PATH
    try:
        schema = json.loads(path.read_text(encoding="utf-8"))
        Draft4Validator.check_schema(schema)
    except (OSError, json.JSONDecodeError, SchemaError) as exc:
        raise RuntimeError(f"Unable to load official ITR-3 schema: {path}") from exc
    return Draft4Validator(schema)


def validate_itr3_json(document: dict[str, Any]) -> None:
    """Validate a complete ITR-3 payload and raise with JSON/schema paths."""
    errors = sorted(
        get_itr3_schema_validator().iter_errors(document),
        key=lambda e: tuple(str(p) for p in e.absolute_path),
    )
    if errors:
        raise ITR3SchemaValidationError([
            {
                "path": ".".join(str(p) for p in e.absolute_path),
                "schema_path": ".".join(str(p) for p in e.absolute_schema_path),
                "message": e.message,
            }
            for e in errors
        ])
