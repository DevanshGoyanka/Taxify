"""Cached runtime validation for official AY 2026-27 ITR-1 JSON."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from jsonschema import Draft4Validator
from jsonschema.exceptions import SchemaError

_SCHEMA_RELATIVE_PATH = (
    Path("frontend")
    / "ITD OFFICAL REFERENCE DOCS"
    / "AY 2026-27 Offical Schema JSON"
    / "ITR-1_2026_Main_V1.1 (1).json"
)


class ITR1SchemaValidationError(ValueError):
    """Raised when generated ITR-1 JSON fails the official Draft-4 schema."""

    def __init__(self, errors: list[dict[str, str]]) -> None:
        self.errors = errors
        message = "; ".join(
            f"{item['path'] or '$'}: {item['message']}" for item in errors
        )
        super().__init__(message)


@lru_cache(maxsize=1)
def get_itr1_schema_validator() -> Draft4Validator:
    """Load and cache the official ITR-1 Draft-4 validator."""
    repository_root = Path(__file__).resolve().parents[3]
    schema_path = repository_root / _SCHEMA_RELATIVE_PATH
    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        Draft4Validator.check_schema(schema)
    except (OSError, json.JSONDecodeError, SchemaError) as exc:
        raise RuntimeError(f"Unable to load official ITR-1 schema: {schema_path}") from exc
    return Draft4Validator(schema)


def validate_itr1_json(document: dict[str, Any]) -> None:
    """Validate a generated document against the official ITR-1 schema.

    Args:
        document: Complete ``{"ITR": {"ITR1": ...}}`` payload.

    Raises:
        ITR1SchemaValidationError: If one or more schema constraints fail.
        RuntimeError: If the official local schema cannot be loaded.
    """
    validation_errors = sorted(
        get_itr1_schema_validator().iter_errors(document),
        key=lambda error: tuple(str(part) for part in error.absolute_path),
    )
    if not validation_errors:
        return
    details = [
        {
            "path": ".".join(str(part) for part in error.absolute_path),
            "schema_path": ".".join(str(part) for part in error.absolute_schema_path),
            "message": error.message,
        }
        for error in validation_errors
    ]
    raise ITR1SchemaValidationError(details)
