"""Extract the full leaf-field inventory from the official CBDT JSON schemas.

Resolves ``$ref`` against the schema's ``definitions`` block so the full
nested tree (Form_ITR1 -> PersonalInfo -> ... -> leaf scalar) is walked.
Emits one CSV row per leaf field: path | type | required | constraints.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path("Reference Docs by CBDT & ITD/Official JSON Schema")


def _constraints(node: dict[str, Any]) -> str:
    parts = []
    for key in ("minLength", "maxLength", "minimum", "maximum", "pattern",
                "enum", "format", "default", "minItems", "maxItems"):
        if key in node:
            val = node[key]
            if isinstance(val, list) and len(val) > 8:
                val = val[:8] + ["..."]
            s = json.dumps(val, ensure_ascii=False) if not isinstance(val, str) else val
            parts.append(f"{key}={s}")
    return ";".join(parts)


def _type(node: dict[str, Any]) -> str:
    if "$ref" in node:
        return f"ref:{node['$ref'].split('/')[-1]}"
    t = node.get("type")
    if isinstance(t, list):
        return "|".join(t)
    if t:
        return t
    if "enum" in node:
        return "enum"
    return "object" if any(k in node for k in ("properties", "allOf", "anyOf", "oneOf")) else ""


class Schema:
    """A JSON schema with resolved $ref."""

    def __init__(self, raw: dict[str, Any]) -> None:
        self.raw = raw
        self.definitions = raw.get("definitions", {})

    def resolve(self, node: dict[str, Any]) -> dict[str, Any]:
        """Follow a single $ref, merging the target into the node."""
        if not isinstance(node, dict):
            return {}
        if "$ref" in node:
            ref = node["$ref"]
            if ref.startswith("#/definitions/"):
                target = self.definitions.get(ref[len("#/definitions/"):], {})
                merged = dict(target)
                # Local constraints (rare) override the ref target.
                for k in ("description",):
                    if k in node:
                        merged[k] = node[k]
                return merged
        return node

    def walk(self, node: dict[str, Any], path: str, out: list[tuple[str, str, str, str]]) -> None:
        node = self.resolve(node)
        if not isinstance(node, dict):
            return
        for combiner in ("allOf",):
            if combiner in node and isinstance(node[combiner], list):
                for sub in node[combiner]:
                    if isinstance(sub, dict):
                        self.walk(sub, path, out)
        props = node.get("properties")
        required = node.get("required", []) if isinstance(node.get("required"), list) else []
        if isinstance(props, dict):
            for name, child in props.items():
                child = child if isinstance(child, dict) else {}
                req = "Y" if name in required else "N"
                child_path = f"{path}.{name}" if path else name
                resolved = self.resolve(child)
                ctype = _type(resolved) if "$ref" not in child else _type(child)
                is_object = ("properties" in resolved
                             or any(c in resolved for c in ("allOf", "anyOf", "oneOf")))
                if ctype == "array" or child.get("type") == "array":
                    items = resolved.get("items", {})
                    if isinstance(items, dict) and ("properties" in self.resolve(items)
                                                    or _type(self.resolve(items)) == "object"):
                        self.walk(self.resolve(items), child_path + "[]", out)
                    else:
                        out.append((child_path + "[]", f"array<{_type(self.resolve(items))}>", req, _constraints(resolved)))
                elif is_object or ctype == "object":
                    self.walk(resolved, child_path, out)
                else:
                    out.append((child_path, ctype or "?", req, _constraints(resolved)))
        elif path:
            out.append((path, _type(node) or "?", "", _constraints(node)))


def extract(schema_name: str) -> list[tuple[str, str, str, str]]:
    path = ROOT / schema_name
    raw = json.loads(path.read_text(encoding="utf-8"))
    schema = Schema(raw)
    out: list[tuple[str, str, str, str]] = []
    root_props = raw.get("properties", {})
    for top, node in root_props.items():
        schema.walk(node if isinstance(node, dict) else {}, top, out)
    return out


def main() -> None:
    for form, fname in (("ITR-1", "ITR-1_2026_Main_V1.1 (2).json"),
                        ("ITR-4", "ITR-4_2026_Main_V1.1 (2).json")):
        rows = extract(fname)
        print(f"=== {form}: {len(rows)} leaf fields ===")
        out_path = Path(f"audit_{form.lower().replace('-', '')}_schema_fields.csv")
        with out_path.open("w", encoding="utf-8") as f:
            f.write("path,type,required,constraints\n")
            for r in rows:
                f.write(",".join(json.dumps(c, ensure_ascii=False) for c in r) + "\n")
        print(f"  -> {out_path}")


if __name__ == "__main__":
    main()
