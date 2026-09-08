"""Cached runtime validation for official AY 2026-27 ITR-2 JSON."""

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
    / "ITR-2_2026_Main_V1.1 (1).json"
)


class ITR2SchemaValidationError(ValueError):
    """Raised when generated ITR-2 JSON fails the official Draft-4 schema."""

    def __init__(self, errors: list[dict[str, str]]) -> None:
        """Initialize the validation exception with stable error details.

        Args:
            errors: Schema errors containing document and schema paths.
        """
        self.errors = errors
        message = "; ".join(
            f"{item['path'] or '$'}: {item['message']}" for item in errors
        )
        super().__init__(message)


@lru_cache(maxsize=1)
def get_itr2_schema_validator() -> Draft4Validator:
    """Load and cache the official ITR-2 Draft-4 validator.

    Returns:
        A process-wide immutable validator instance.

    Raises:
        RuntimeError: If the official schema file is missing or malformed.
    """
    repository_root = Path(__file__).resolve().parents[3]
    schema_path = repository_root / _SCHEMA_RELATIVE_PATH
    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        Draft4Validator.check_schema(schema)
    except (OSError, json.JSONDecodeError, SchemaError) as exc:
        raise RuntimeError(f"Unable to load official ITR-2 schema: {schema_path}") from exc
    return Draft4Validator(schema)


def validate_itr2_json(document: dict[str, Any]) -> None:
    """Validate a generated document against the official ITR-2 schema.

    Args:
        document: Complete ``{"ITR": {"ITR2": ...}}`` payload.

    Raises:
        ITR2SchemaValidationError: If one or more schema constraints fail.
        RuntimeError: If the official local schema cannot be loaded.
    """
    validation_errors = sorted(
        get_itr2_schema_validator().iter_errors(document),
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
    raise ITR2SchemaValidationError(details)


__all__ = [
    "ITR2SchemaValidationError",
    "get_itr2_schema_validator",
    "validate_itr2_json",
]
