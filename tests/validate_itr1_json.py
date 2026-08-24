"""Validate the generated CBDT ITR-1 JSON against the official schema.

Usage: py validate_itr1_json.py <path-to-generated-json>
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema
from jsonschema import Draft4Validator

REPO = Path(__file__).resolve().parents[1]
SCHEMA_PATH = REPO / "Reference Docs by CBDT & ITD" / "Official JSON Schema" / "ITR-1_2026_Main_V1.1 (2).json"


def load_schema() -> dict:
    """Load the official CBDT ITR-1 AY 2026-27 JSON schema."""
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8-sig"))


def load_instance(path: str) -> dict:
    """Load the generated JSON instance to validate."""
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def main() -> int:
    """Validate the generated JSON and report all schema violations."""
    if len(sys.argv) < 2:
        print("Usage: py validate_itr1_json.py <path-to-generated-json>")
        return 2

    instance_path = sys.argv[1]
    schema = load_schema()
    instance = load_instance(instance_path)

    validator = Draft4Validator(schema)
    errors = sorted(validator.iter_errors(instance), key=lambda e: list(e.absolute_path))

    if not errors:
        print("RESULT: PASS — the JSON validates against the official CBDT ITR-1 AY 2026-27 schema.")
        return 0

    print(f"RESULT: FAIL — {len(errors)} schema violation(s) found:")
    print()
    for i, err in enumerate(errors, 1):
        path = ".".join(str(p) for p in err.absolute_path) or "(root)"
        print(f"  [{i}] Path: {path}")
        print(f"      Message: {err.message}")
        if err.context:
            for sub in err.context:
                sub_path = ".".join(str(p) for p in sub.absolute_path) or "(root)"
                print(f"      Sub-error at {sub_path}: {sub.message}")
        print()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
