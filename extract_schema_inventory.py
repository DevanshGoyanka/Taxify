"""Extract authoritative field metadata from the official CBDT JSON schemas.

The field matrix contains every property plus synthetic ``[]`` rows for array
items, not only scalar leaves.  This extractor therefore:

* resolves local JSON pointers (including chained ``$ref`` values);
* composes ``allOf`` constraints instead of walking each branch separately;
* carries the immediate parent's ``required`` declaration to each property;
* emits objects, arrays, array items, and scalar fields exactly once; and
* retains all validation constraints inherited through composition.

Run from the repository root:

    python extract_schema_inventory.py
"""
from __future__ import annotations

import csv
import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parent
SCHEMA_ROOT = ROOT / "Reference Docs by CBDT & ITD" / "Official JSON Schema"

SCHEMAS = {
    "ITR-1": "ITR-1_2026_Main_V1.1 (2).json",
    "ITR-4": "ITR-4_2026_Main_V1.1 (2).json",
}

CONSTRAINT_KEYS = (
    "minLength",
    "maxLength",
    "minimum",
    "maximum",
    "exclusiveMinimum",
    "exclusiveMaximum",
    "multipleOf",
    "pattern",
    "enum",
    "format",
    "const",
    "default",
    "minItems",
    "maxItems",
    "uniqueItems",
    "minProperties",
    "maxProperties",
)


def _ordered_union(left: Iterable[Any], right: Iterable[Any]) -> list[Any]:
    result: list[Any] = []
    for value in (*left, *right):
        if value not in result:
            result.append(value)
    return result


class Schema:
    """A JSON schema resolver and deterministic structural inventory walker."""

    def __init__(self, raw: dict[str, Any]) -> None:
        self.raw = raw
        self._resolved_refs: dict[str, dict[str, Any]] = {}

    def _pointer(self, ref: str) -> dict[str, Any]:
        if not ref.startswith("#/"):
            raise ValueError(f"Unsupported non-local schema reference: {ref}")
        current: Any = self.raw
        for raw_part in ref[2:].split("/"):
            part = raw_part.replace("~1", "/").replace("~0", "~")
            if not isinstance(current, dict) or part not in current:
                raise KeyError(f"Schema reference does not exist: {ref}")
            current = current[part]
        if not isinstance(current, dict):
            raise TypeError(f"Schema reference is not an object: {ref}")
        return current

    @staticmethod
    def _merge(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
        """Compose two schema fragments using the intersection semantics of allOf."""
        result = deepcopy(left)
        for key, right_value in right.items():
            if key == "required":
                result[key] = _ordered_union(result.get(key, []), right_value)
            elif key == "properties":
                properties = deepcopy(result.get(key, {}))
                for name, child in right_value.items():
                    if name in properties:
                        properties[name] = Schema._merge(properties[name], child)
                    else:
                        properties[name] = deepcopy(child)
                result[key] = properties
            elif key == "items" and isinstance(result.get(key), dict) and isinstance(right_value, dict):
                result[key] = Schema._merge(result[key], right_value)
            elif key == "enum" and key in result:
                result[key] = [value for value in result[key] if value in right_value]
            elif key in {"minimum", "minLength", "minItems", "minProperties"} and key in result:
                result[key] = max(result[key], right_value)
            elif key in {"maximum", "maxLength", "maxItems", "maxProperties"} and key in result:
                result[key] = min(result[key], right_value)
            elif key == "pattern" and key in result and result[key] != right_value:
                patterns = list(result.pop("_allOfPatterns", [result.pop("pattern")]))
                if right_value not in patterns:
                    patterns.append(right_value)
                result["_allOfPatterns"] = patterns
            elif key == "_allOfPatterns":
                existing = result.pop("pattern", None)
                patterns = list(result.get("_allOfPatterns", []))
                if existing is not None:
                    patterns.insert(0, existing)
                result["_allOfPatterns"] = _ordered_union(patterns, right_value)
            elif key not in result or result[key] == right_value:
                result[key] = deepcopy(right_value)
            elif key in {"description", "title", "default"}:
                # A property-local annotation is more specific than its referenced
                # base type. ``right`` is always the later/local fragment.
                result[key] = deepcopy(right_value)
            else:
                # The CBDT schemas do not currently contain incompatible values
                # for other validation keywords. Fail loudly if that changes.
                raise ValueError(
                    f"Cannot losslessly compose schema keyword {key!r}: "
                    f"{result[key]!r} and {right_value!r}"
                )
        return result

    def resolve(self, node: dict[str, Any], stack: tuple[str, ...] = ()) -> dict[str, Any]:
        """Resolve references and flatten allOf into one effective schema."""
        if not isinstance(node, dict):
            return {}

        result: dict[str, Any] = {}
        ref = node.get("$ref")
        if ref is not None:
            if ref in stack:
                chain = " -> ".join((*stack, ref))
                raise ValueError(f"Circular schema reference: {chain}")
            if ref not in self._resolved_refs:
                self._resolved_refs[ref] = self.resolve(self._pointer(ref), (*stack, ref))
            result = self._merge(result, self._resolved_refs[ref])

        for part in node.get("allOf", []):
            if not isinstance(part, dict):
                raise TypeError("Every allOf entry must be a schema object")
            result = self._merge(result, self.resolve(part, stack))

        local = {
            key: value
            for key, value in node.items()
            if key not in {"$ref", "allOf"}
        }
        return self._merge(result, local)

    @staticmethod
    def schema_type(node: dict[str, Any]) -> str:
        schema_type = node.get("type")
        if isinstance(schema_type, list):
            return "|".join(schema_type)
        if isinstance(schema_type, str):
            return schema_type
        if "properties" in node:
            return "object"
        if "items" in node:
            return "array"
        # An enum without a declared primitive type is still useful to flag.
        if "enum" in node:
            return "enum"
        return "?"

    @staticmethod
    def constraints(node: dict[str, Any]) -> str:
        constraints: dict[str, Any] = {}
        for key in CONSTRAINT_KEYS:
            if key in node:
                constraints[key] = node[key]
        if "_allOfPatterns" in node:
            constraints.pop("pattern", None)
            constraints["allOfPatterns"] = node["_allOfPatterns"]
        return json.dumps(
            constraints,
            ensure_ascii=False,
            separators=(",", ":"),
        ) if constraints else ""

    def inventory(self, form: str) -> list[dict[str, str]]:
        """Return all form fields in the same path convention as the matrix."""
        root = self.resolve(self.raw)
        itr_property = root.get("properties", {}).get("ITR")
        if not isinstance(itr_property, dict):
            raise KeyError("Official schema has no ITR root property")
        itr = self.resolve(itr_property)

        form_name = form.replace("-", "")
        form_property = itr.get("properties", {}).get(form_name)
        if not isinstance(form_property, dict):
            raise KeyError(f"Official schema has no ITR.{form_name} property")
        form_schema = self.resolve(form_property)

        rows: list[dict[str, str]] = []
        self._walk_object(
            form_schema,
            path=f"ITR.{form_name}",
            rows=rows,
        )
        return rows

    def _walk_object(
        self,
        node: dict[str, Any],
        path: str,
        rows: list[dict[str, str]],
    ) -> None:
        node = self.resolve(node)
        properties = node.get("properties", {})
        if not isinstance(properties, dict):
            return
        required = set(node.get("required", []))
        for name, raw_child in properties.items():
            if not isinstance(raw_child, dict):
                raise TypeError(f"Schema field {path}.{name} is not an object")
            child = self.resolve(raw_child)
            child_path = f"{path}.{name}"
            child_type = self.schema_type(child)
            rows.append(
                {
                    "path": child_path,
                    "type": child_type,
                    "required": "Y" if name in required else "N",
                    "constraints": self.constraints(child),
                    "description": str(child.get("description", "")),
                }
            )

            if child_type == "object":
                self._walk_object(child, child_path, rows)
            elif child_type == "array":
                raw_items = child.get("items", {})
                if not isinstance(raw_items, dict):
                    raise TypeError(f"Array items for {child_path} are not an object")
                items = self.resolve(raw_items)
                item_type = self.schema_type(items)
                item_path = f"{child_path}[]"
                rows.append(
                    {
                        "path": item_path,
                        "type": item_type,
                        # An item schema applies whenever an item exists.
                        "required": "Y",
                        "constraints": self.constraints(items),
                        "description": str(items.get("description", "")),
                    }
                )
                if item_type == "object":
                    self._walk_object(items, item_path, rows)


def extract(form: str, schema_name: str) -> list[dict[str, str]]:
    raw = json.loads((SCHEMA_ROOT / schema_name).read_text(encoding="utf-8"))
    return Schema(raw).inventory(form)


def main() -> None:
    for form, filename in SCHEMAS.items():
        rows = extract(form, filename)
        output_path = ROOT / f"audit_{form.lower().replace('-', '')}_schema_fields.csv"
        with output_path.open("w", encoding="utf-8", newline="") as output:
            writer = csv.DictWriter(
                output,
                fieldnames=("path", "type", "required", "constraints", "description"),
            )
            writer.writeheader()
            writer.writerows(rows)
        print(f"{form}: {len(rows)} fields -> {output_path.name}")


if __name__ == "__main__":
    main()
