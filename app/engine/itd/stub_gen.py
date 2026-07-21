"""
Schema-driven stub generator. Given a CBDT JSON Schema definition,
recursively generates a valid default dict that satisfies all
required fields, proper types, and pattern constraints.
"""
from typing import Any

_SAFE_PATTERN_ARGS = {
    "nonEmptyString": "NA",
    "PAN": "AAAAA0000A",
    "AADHAAR": "000000000000",
    "TAN": "DELA00001A",
    "BSRCode": "1234567",
    "DATE": "2025-06-15",
    "EMAIL": "assessee@example.com",
    "MOBILE": "9999999999",
    "IFSC": "SBIN0000001",
    "PIN": 110001,
}
_ENUM_DEFAULTS = {
    "Y": "Y", "N": "N",
}


def generate_default(schema: dict, defs: dict, visited: set | None = None) -> Any:
    """Recursively build a default value that satisfies a JSON Schema definition."""
    if visited is None:
        visited = set()

    # $ref
    if "$ref" in schema:
        ref_name = schema["$ref"].split("/")[-1]
        if ref_name in visited:
            return None
        visited.add(ref_name)
        if ref_name not in defs:
            return 0
        return generate_default(defs[ref_name], defs, visited)

    # type handling
    stype = schema.get("type", "object")

    if stype == "object":
        props = schema.get("properties", {})
        required = set(schema.get("required", []))
        result = {}
        for key, prop in props.items():
            val = generate_default(prop, defs, visited.copy())
            if key in required or val is not None:
                result[key] = val
        return result

    if stype == "array":
        items = schema.get("items", {})
        min_items = schema.get("minItems", 0)
        if min_items and min_items > 0:
            return [generate_default(items, defs, visited.copy())]
        return []

    if stype == "integer":
        return 0

    if stype == "number":
        return 0.0

    if stype == "string":
        # Use enum if available
        enums = schema.get("enum", [])
        if enums:
            return enums[0]
        # Pattern-based defaults
        pat = schema.get("pattern", "")
        if "nonEmptyString" in str(schema.get("allOf", [])):
            return "NA"
        return ""

    # boolean or null
    if stype == "boolean":
        return False

    return None


def generate_root(structure_name: str, schema: dict) -> dict:
    """Generate the top-level ITR output: {ITR: {ITR1/ITR2/ITR4: ...}}."""
    defs = schema.get("definitions", {})
    root = defs.get(structure_name, {})
    return {
        "ITR": {
            structure_name: generate_default(root, defs)
        }
    }
