"""Verify and synchronize ITR-1/ITR-4 matrix metadata with CBDT schemas.

The official schemas are the sole source of truth for path, type,
required-in-parent, constraints, and description.  Implementation status and
evidence remain human-reviewed and are never inferred by this script.

Usage:

    python verify_matrix_coverage.py
    python verify_matrix_coverage.py --sync-schema
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Iterable

from extract_schema_inventory import SCHEMAS, extract

ROOT = Path(__file__).resolve().parent
MATRIX_FILES = (
    ROOT / "CBDT_FRONTEND_FIELD_MATRIX_AY2026_27.csv",
    ROOT / "CBDT_FRONTEND_FIELD_TO_TAB_IMPLEMENTATION_ROUTING_AY2026_27.csv",
)
SCHEMA_COLUMNS = (
    "required_in_parent",
    "schema_type",
    "constraints",
    "description",
)


def _official_rows() -> dict[tuple[str, str], dict[str, str]]:
    rows: dict[tuple[str, str], dict[str, str]] = {}
    for form, filename in SCHEMAS.items():
        for field in extract(form, filename):
            schema_type = field["type"]
            constraints = field["constraints"]
            # Preserve the matrix's useful historical label for string enums.
            if schema_type == "string" and constraints:
                parsed = json.loads(constraints)
                if "enum" in parsed:
                    schema_type = "enum"
            rows[(form, field["path"])] = {
                "required_in_parent": "Yes" if field["required"] == "Y" else "No",
                "schema_type": schema_type,
                "constraints": constraints,
                "description": field["description"],
            }
    return rows


def _read(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        if reader.fieldnames is None:
            raise ValueError(f"{path.name} has no header")
        return list(reader.fieldnames), list(reader)


def _write(path: Path, columns: list[str], rows: Iterable[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _verify_one(
    path: Path,
    official: dict[tuple[str, str], dict[str, str]],
    *,
    sync: bool,
) -> list[str]:
    columns, rows = _read(path)
    errors: list[str] = []
    applicable = {
        (row["form"], row["schema_path"]): row
        for row in rows
        if row["form"] in SCHEMAS
    }

    missing = sorted(set(official) - set(applicable))
    extra = sorted(set(applicable) - set(official))
    for form, field_path in missing:
        errors.append(f"{path.name}: missing {form} {field_path}")
    for form, field_path in extra:
        errors.append(f"{path.name}: unknown {form} {field_path}")

    for key in sorted(set(official) & set(applicable)):
        actual = applicable[key]
        expected = official[key]
        for column in SCHEMA_COLUMNS:
            if actual[column] == expected[column]:
                continue
            if sync:
                actual[column] = expected[column]
            else:
                errors.append(
                    f"{path.name}: {key[0]} {key[1]} {column}: "
                    f"expected {expected[column]!r}, got {actual[column]!r}"
                )

    if sync and not missing and not extra:
        _write(path, columns, rows)
    return errors


def _verify_parallel_matrices() -> list[str]:
    _, primary = _read(MATRIX_FILES[0])
    _, routing = _read(MATRIX_FILES[1])
    primary_by_key = {
        (row["form"], row["schema_path"]): row
        for row in primary
        if row["form"] in SCHEMAS
    }
    routing_by_key = {
        (row["form"], row["schema_path"]): row
        for row in routing
        if row["form"] in SCHEMAS
    }
    errors: list[str] = []
    if set(primary_by_key) != set(routing_by_key):
        errors.append("ITR-1/ITR-4 path sets differ between the two matrices")
        return errors
    shared = (
        "top_level_schedule",
        *SCHEMA_COLUMNS,
        "frontend_status",
        "frontend_evidence",
        "audit_note",
    )
    for key in sorted(primary_by_key):
        for column in shared:
            if primary_by_key[key][column] != routing_by_key[key][column]:
                errors.append(
                    f"Matrix disagreement for {key[0]} {key[1]} {column}"
                )
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--sync-schema",
        action="store_true",
        help="replace schema-derived columns with official values",
    )
    args = parser.parse_args()

    official = _official_rows()
    errors: list[str] = []
    for matrix_path in MATRIX_FILES:
        errors.extend(_verify_one(matrix_path, official, sync=args.sync_schema))
    errors.extend(_verify_parallel_matrices())

    if errors:
        print(f"FAILED: {len(errors)} matrix coverage issue(s)")
        for error in errors[:100]:
            print(f"- {error}")
        if len(errors) > 100:
            print(f"- ... {len(errors) - 100} more")
        return 1

    action = "synchronized and verified" if args.sync_schema else "verified"
    print(f"ITR-1/ITR-4 schema metadata {action}: {len(official)} fields")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
