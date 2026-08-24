"""Extract enum and numeric-capping fields from the official schemas.

Prints, for each form, the fields that carry an ``enum`` constraint or a
``minimum``/``maximum`` numeric capping, with their full allowed value
list. This is the ground-truth enum + capping inventory used to verify
the frontend type definitions enforce the same allowed values.
"""
import json
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent
ROOT = _REPO_ROOT / "frontend" / "ITD OFFICAL REFERENCE DOCS" / "AY 2026-27 Offical Schema JSON"
# Audit CSVs live under Docs/ alongside the rest of the schema audit output.
DOCS_DIR = _REPO_ROOT / "Docs"


def walk(node, path, schema, out, seen):
    if not isinstance(node, dict):
        return
    if "$ref" in node:
        ref = node["$ref"]
        if ref.startswith("#/definitions/"):
            node = {**schema.get("definitions", {}).get(ref[len("#/definitions/"):], {}), **{k: v for k, v in node.items() if k != "$ref"}}
    for combiner in ("allOf",):
        if combiner in node and isinstance(node[combiner], list):
            for sub in node[combiner]:
                walk(sub, path, schema, out, seen)
    props = node.get("properties")
    if isinstance(props, dict):
        for name, child in props.items():
            child = child if isinstance(child, dict) else {}
            child_path = f"{path}.{name}" if path else name
            resolved = child
            if "$ref" in child and child["$ref"].startswith("#/definitions/"):
                resolved = {**schema.get("definitions", {}).get(child["$ref"][len("#/definitions/"):], {}), **{k: v for k, v in child.items() if k != "$ref"}}
            t = resolved.get("type", child.get("type"))
            is_array = (t == "array") or child.get("type") == "array"
            if is_array:
                items = resolved.get("items", {})
                if "$ref" in items and items["$ref"].startswith("#/definitions/"):
                    items = schema.get("definitions", {}).get(items["$ref"][len("#/definitions/"):], {})
                if isinstance(items, dict) and ("properties" in items or _type(items) == "object"):
                    walk(items, child_path + "[]", schema, out, seen)
                else:
                    _record(child_path + "[]", f"array<{_type(items)}>", resolved, out, seen)
            elif "properties" in resolved or any(c in resolved for c in ("allOf", "anyOf", "oneOf")):
                walk(resolved, child_path, schema, out, seen)
            else:
                _record(child_path, _type(resolved), resolved, out, seen)


def _type(node):
    if "$ref" in node:
        return f"ref:{node['$ref'].split('/')[-1]}"
    t = node.get("type")
    return "|".join(t) if isinstance(t, list) else (t or ("enum" if "enum" in node else "?"))


def _record(path, typ, node, out, seen):
    enum = node.get("enum")
    minimum = node.get("minimum")
    maximum = node.get("maximum")
    if enum is None and minimum is None and maximum is None:
        return
    if path in seen:
        return
    seen.add(path)
    out.append((path, typ, json.dumps(enum, ensure_ascii=False) if enum else "", minimum, maximum))


def extract(name):
    raw = json.loads((ROOT / name).read_text(encoding="utf-8"))
    out, seen = [], set()
    for top, node in raw.get("properties", {}).items():
        walk(node, top, raw, out, seen)
    return out


def main():
    for form, fname in (("ITR-1", "ITR-1_2026_Main_V1.1 (1).json"),
                        ("ITR-4", "ITR-4_2026_Main_V1.1 (1).json")):
        rows = extract(fname)
        slug = form.lower().replace("-", "")
        out = DOCS_DIR / f"audit_{slug}_enums_cappings.csv"
        with out.open("w", encoding="utf-8") as f:
            f.write("path,type,enum,minimum,maximum\n")
            for r in rows:
                f.write(",".join(json.dumps(c, ensure_ascii=False) for c in r) + "\n")
        print(f"{form}: {len(rows)} enum/capping fields -> {out}")


if __name__ == "__main__":
    main()
