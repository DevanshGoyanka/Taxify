"""Official-schema field inventory and completeness reporting for ITR-3.

The builder must eventually provide a typed source for every field in this
manifest. This module intentionally reports gaps instead of treating missing
fields as harmless zero defaults.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.engine.itd.itr3_schema import get_itr3_schema_validator


_SCHEMA_PATH = Path(__file__).resolve().parents[3] / "Reference Docs by CBDT & ITD" / "Official JSON Schema" / "ITR-3_2026_Main_V1.1 (2).json"


@dataclass(frozen=True)
class ITR3FieldSpec:
    """One recursively discovered field from the official ITR-3 schema."""

    path: str
    field_name: str
    required: bool
    value_type: str
    enum_values: tuple[str, ...]
    array: bool
    definition: str


@dataclass(frozen=True)
class ITR3ScheduleSpec:
    """One official ITR-3 schedule and its recursively discovered fields."""

    name: str
    required: bool
    fields: tuple[ITR3FieldSpec, ...]


@dataclass(frozen=True)
class ITR3CompletenessReport:
    """Machine-readable report of schedule fields and known source paths."""

    schedules: tuple[ITR3ScheduleSpec, ...]
    missing_source_paths: tuple[str, ...]

    @property
    def complete(self) -> bool:
        """Return whether every inventoried field has an explicit source."""
        return not self.missing_source_paths

    @property
    def field_count(self) -> int:
        """Return the number of recursively inventoried fields."""
        return sum(len(schedule.fields) for schedule in self.schedules)

    def to_dict(self) -> dict[str, Any]:
        """Serialize the report for audit logs and tests."""
        return {
            "complete": self.complete,
            "field_count": self.field_count,
            "missing_source_paths": list(self.missing_source_paths),
            "schedules": [
                {
                    "name": schedule.name,
                    "required": schedule.required,
                    "fields": [
                        {
                            "path": field.path,
                            "field_name": field.field_name,
                            "required": field.required,
                            "value_type": field.value_type,
                            "enum_values": list(field.enum_values),
                            "array": field.array,
                            "definition": field.definition,
                        }
                        for field in schedule.fields
                    ],
                }
                for schedule in self.schedules
            ],
        }


def _load_schema() -> dict[str, Any]:
    """Load the official ITR-3 schema document."""
    return json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))


def _resolve_reference(node: dict[str, Any], definitions: dict[str, Any]) -> tuple[dict[str, Any], str]:
    """Resolve a local definition reference and return its definition name."""
    reference = node.get("$ref")
    if not isinstance(reference, str) or not reference.startswith("#/definitions/"):
        return node, ""
    name = reference.rsplit("/", 1)[-1]
    return definitions.get(name, node), name


def _value_type(node: dict[str, Any]) -> str:
    """Return a stable human-readable schema type."""
    declared = node.get("type")
    if isinstance(declared, str):
        return declared
    if isinstance(declared, list):
        return "|".join(str(value) for value in declared)
    if "$ref" in node:
        return "object"
    if "enum" in node:
        return "enum"
    return "object"


def _walk_fields(
    node: dict[str, Any],
    path: str,
    required: bool,
    definitions: dict[str, Any],
    definition: str = "",
) -> list[ITR3FieldSpec]:
    """Recursively flatten object properties and array item objects."""
    resolved, referenced_definition = _resolve_reference(node, definitions)
    definition = referenced_definition or definition
    properties = resolved.get("properties", {})
    if not isinstance(properties, dict):
        return [ITR3FieldSpec(
            path=path,
            field_name=path.rsplit(".", 1)[-1],
            required=required,
            value_type=_value_type(resolved),
            enum_values=tuple(str(value) for value in resolved.get("enum", [])),
            array=resolved.get("type") == "array",
            definition=definition,
        )]
    required_names = set(resolved.get("required", []))
    fields: list[ITR3FieldSpec] = []
    for name, child in properties.items():
        child_path = f"{path}.{name}" if path else str(name)
        if not isinstance(child, dict):
            continue
        child_resolved, child_definition = _resolve_reference(child, definitions)
        if child_resolved.get("type") == "array" and isinstance(child_resolved.get("items"), dict):
            item = child_resolved["items"]
            item_resolved, item_definition = _resolve_reference(item, definitions)
            fields.append(ITR3FieldSpec(
                path=child_path,
                field_name=name,
                required=name in required_names,
                value_type="array",
                enum_values=tuple(str(value) for value in item_resolved.get("enum", [])),
                array=True,
                definition=item_definition or child_definition,
            ))
            if isinstance(item_resolved.get("properties"), dict):
                fields.extend(_walk_fields(
                    item_resolved,
                    f"{child_path}[]",
                    name in required_names,
                    definitions,
                    item_definition or child_definition,
                ))
        elif child_resolved.get("properties") or child_resolved.get("$ref"):
            fields.extend(_walk_fields(child, child_path, name in required_names, definitions, child_definition))
        else:
            fields.append(ITR3FieldSpec(
                path=child_path,
                field_name=name,
                required=name in required_names,
                value_type=_value_type(child_resolved),
                enum_values=tuple(str(value) for value in child_resolved.get("enum", [])),
                array=False,
                definition=child_definition,
            ))
    return fields


@lru_cache(maxsize=1)
def get_itr3_schedule_manifest() -> tuple[ITR3ScheduleSpec, ...]:
    """Return every official ITR-3 schedule and recursively discovered field."""
    schema = _load_schema()
    definitions = schema.get("definitions", {})
    itr3 = definitions.get("ITR3", {})
    properties = itr3.get("properties", {})
    required_schedules = set(itr3.get("required", []))
    schedules: list[ITR3ScheduleSpec] = []
    for name, node in properties.items():
        if not isinstance(node, dict):
            continue
        schedules.append(ITR3ScheduleSpec(
            name=name,
            required=name in required_schedules,
            fields=tuple(_walk_fields(node, name, name in required_schedules, definitions)),
        ))
    return tuple(schedules)


def build_itr3_completeness_report(source_paths: set[str] | frozenset[str]) -> ITR3CompletenessReport:
    """Compare explicit typed/source paths against the official field manifest.

    Args:
        source_paths: Exact official JSON paths backed by typed models and
            builder mappings. Paths may name an entire schedule to mark all
            descendants as covered during an intermediate implementation phase.
    """
    missing: list[str] = []
    for schedule in get_itr3_schedule_manifest():
        for field in schedule.fields:
            if not any(field.path == source or field.path.startswith(f"{source}.") for source in source_paths):
                missing.append(field.path)
    return ITR3CompletenessReport(get_itr3_schedule_manifest(), tuple(missing))


__all__ = [
    "ITR3CompletenessReport",
    "ITR3FieldSpec",
    "ITR3ScheduleSpec",
    "build_itr3_completeness_report",
    "get_itr3_schedule_manifest",
]
