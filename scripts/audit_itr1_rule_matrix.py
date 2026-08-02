from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RULES_FILE = ROOT / "tmp_itr1_rules.txt"
CODE_PATHS = [
    ROOT / "app" / "schemas" / "itr1.py",
    ROOT / "app" / "engine" / "validators" / "itr1" / "input_rules.py",
    ROOT / "app" / "engine" / "validators" / "itr1" / "calc_rules.py",
    ROOT / "app" / "engine" / "validators" / "itr1" / "runner.py",
    ROOT / "app" / "engine" / "calculators" / "itr1.py",
    ROOT / "app" / "engine" / "itd" / "itr1.py",
    ROOT / "app" / "engine" / "schedules" / "salary.py",
    ROOT / "app" / "engine" / "schedules" / "house_property.py",
    ROOT / "app" / "engine" / "schedules" / "other_sources.py",
    ROOT / "app" / "engine" / "schedules" / "special_rates.py",
    ROOT / "app" / "engine" / "common" / "interest.py",
    ROOT / "app" / "engine" / "common" / "rebate.py",
    ROOT / "app" / "engine" / "common" / "slab_tax.py",
    ROOT / "app" / "engine" / "common" / "surcharge.py",
    ROOT / "app" / "engine" / "common" / "cess.py",
    ROOT / "app" / "engine" / "schedules" / "deductions" / "section_80c.py",
    ROOT / "app" / "engine" / "schedules" / "deductions" / "section_80d.py",
    ROOT / "app" / "engine" / "schedules" / "deductions" / "section_80g.py",
    ROOT / "app" / "engine" / "schedules" / "deductions" / "section_80gga.py",
    ROOT / "app" / "engine" / "schedules" / "deductions" / "section_80ggc.py",
    ROOT / "app" / "engine" / "schedules" / "deductions" / "section_80ccd2.py",
    ROOT / "app" / "engine" / "schedules" / "deductions" / "section_80ccd1b.py",
    ROOT / "app" / "engine" / "schedules" / "deductions" / "section_80dd.py",
    ROOT / "app" / "engine" / "schedules" / "deductions" / "section_80ddb.py",
    ROOT / "app" / "engine" / "schedules" / "deductions" / "section_80e.py",
    ROOT / "app" / "engine" / "schedules" / "deductions" / "section_80ee.py",
    ROOT / "app" / "engine" / "schedules" / "deductions" / "section_80eea.py",
    ROOT / "app" / "engine" / "schedules" / "deductions" / "section_80eeb.py",
    ROOT / "app" / "engine" / "schedules" / "deductions" / "section_80gg.py",
    ROOT / "app" / "engine" / "schedules" / "deductions" / "section_80tta.py",
    ROOT / "app" / "engine" / "schedules" / "deductions" / "section_80ttb.py",
    ROOT / "app" / "engine" / "schedules" / "deductions" / "section_80u.py",
    ROOT / "app" / "routers" / "tax.py",
    ROOT / "app" / "routers" / "itr.py",
    ROOT / "app" / "routers" / "client_itr.py",
]
OUT_DIR = ROOT / "docs" / "audit"
CSV_OUT = OUT_DIR / "itr1_validation_rule_matrix.csv"
MD_OUT = OUT_DIR / "ITR1_VALIDATION_RULE_MATRIX.md"

KNOWN_GROUPED_COVERAGE: dict[int, tuple[str, str]] = {
    **{i: ("IMPLEMENTED_GROUPED", "Covered by grouped Schedule VIA consistency validator ITR1-R272-291 in input_rules.py") for i in range(272, 292)},
}

# Rules whose exact official checks are structurally enforced in schema/domain models or calculator schedules,
# but currently do not carry exact ITR1-Rxxx validator IDs. Keep this list intentionally small and evidence-based.
KNOWN_STRUCTURAL_COVERAGE: dict[int, tuple[str, str]] = {
    5: ("IMPLEMENTED_CALCULATION", "80DDB senior cap is computed in section_80ddb.py / deductions aggregator; no exact rule ID emitted"),
    10: ("IMPLEMENTED_CALCULATION", "80G allowed deduction is computed by section_80g.py and cross-footed in ITD builder; no exact rule ID emitted"),
    68: ("IMPLEMENTED_CALCULATION", "Commuted pension exemption capped in salary schedule; no exact rule ID emitted"),
    69: ("IMPLEMENTED_CALCULATION", "Leave encashment exemption capped in salary schedule; no exact rule ID emitted"),
    71: ("IMPLEMENTED_CALCULATION", "VRS exemption capped in salary schedule; no exact rule ID emitted"),
    80: ("IMPLEMENTED_BUILDER", "80G table rows require donation cash/other-mode amounts to emit totals; builder cross-foots schedule"),
    81: ("IMPLEMENTED_BUILDER", "80G table rows require donation cash/other-mode amounts to emit totals; builder cross-foots schedule"),
    82: ("IMPLEMENTED_BUILDER", "80G table rows require donation cash/other-mode amounts to emit totals; builder cross-foots schedule"),
    85: ("IMPLEMENTED_BUILDER", "80G category total donation equals cash plus other mode in ITD builder; no exact rule ID emitted"),
    86: ("IMPLEMENTED_BUILDER", "80G category total donation equals cash plus other mode in ITD builder; no exact rule ID emitted"),
    87: ("IMPLEMENTED_BUILDER", "80G category total donation equals cash plus other mode in ITD builder; no exact rule ID emitted"),
    99: ("PARTIAL", "TDS/TCS claim consistency exists, but year-of-deduction null/zero is not proven as an exact validator for all TDS2/TDS3/TCS rows"),
    328: ("IMPLEMENTED_CALCULATION", "234-I computation exists in interest.py/calculator and R27/R28/R140 include fees_234i; exact R328 ID not emitted"),
    296: ("RECONCILED_MODEL_INVARIANT", "The normalized ITR-1 HP model stores the assessee-share annual value directly; no separate pre-share annual-value field exists, so the official multiplication cannot diverge inside the domain model"),
    298: ("RECONCILED_MODEL_INVARIANT", "Official HP Sl.1d is a presentation total; the normalized model stores annual rent and arrears separately and the calculator/builder derives their total instead of accepting an editable total"),
    299: ("RECONCILED_MODEL_INVARIANT", "Official HP Sl.1i is a presentation total; the normalized loan rows store component interest and the validator/calculator sum rows instead of accepting an editable total"),
}

@dataclass(frozen=True)
class Rule:
    number: int
    category: str
    text: str

@dataclass(frozen=True)
class Evidence:
    path: str
    line: int
    snippet: str


def read_text(path: Path) -> str:
    text = path.read_text(encoding="utf-8", errors="ignore")
    # The PDF-extracted official rules file is UTF-16-like in places but lacks
    # a reliable BOM for normal decoding; remove embedded NULs before parsing.
    return text.replace("\x00", "")


def parse_rules() -> list[Rule]:
    text = read_text(RULES_FILE).replace("\r\n", "\n")
    # There is a table-of-contents occurrence of "Category A:" before the
    # real table. Anchor to the full table heading and stop at Category B.
    heading = "Table 2: Category A Rules"
    cat_a_start = text.index(heading)
    cat_b_start = text.index("1.2 Category B:", cat_a_start)
    cat_a = text[cat_a_start:cat_b_start]
    matches = list(re.finditer(r"(?m)^\s*(\d{1,3})\.\s*$", cat_a))
    rules: list[Rule] = []
    for idx, match in enumerate(matches):
        number = int(match.group(1))
        if not 1 <= number <= 339:
            continue
        body_start = match.end()
        body_end = matches[idx + 1].start() if idx + 1 < len(matches) else len(cat_a)
        body = cat_a[body_start:body_end]
        body = re.sub(r"(?m)^Page \d+\s*$", "", body)
        body = re.sub(r"(?m)^=== PAGE \d+ ===\s*$", "", body)
        body = re.sub(r"\s+", " ", body).strip()
        rules.append(Rule(number=number, category="A", text=body))
    return rules


def code_files() -> list[Path]:
    return [p for p in CODE_PATHS if p.exists()]


def build_evidence_index() -> dict[int, list[Evidence]]:
    index: dict[int, list[Evidence]] = {i: [] for i in range(1, 340)}
    for path in code_files():
        rel = path.relative_to(ROOT).as_posix()
        lines = read_text(path).splitlines()
        for lineno, line in enumerate(lines, 1):
            for match in re.finditer(r"ITR1-R(\d{3})\b", line):
                num = int(match.group(1))
                if 1 <= num <= 339:
                    index[num].append(Evidence(rel, lineno, line.strip()))
    return index


def classify(rule: Rule, evidence: list[Evidence]) -> tuple[str, str, str]:
    if evidence:
        locations = "; ".join(f"{e.path}:{e.line}" for e in evidence[:6])
        if len(evidence) > 6:
            locations += f"; +{len(evidence)-6} more"
        return "IMPLEMENTED_EXPLICIT", "HIGH", locations
    if rule.number in KNOWN_GROUPED_COVERAGE:
        status, reason = KNOWN_GROUPED_COVERAGE[rule.number]
        return status, "MEDIUM", reason
    if rule.number in KNOWN_STRUCTURAL_COVERAGE:
        status, reason = KNOWN_STRUCTURAL_COVERAGE[rule.number]
        confidence = "MEDIUM" if status.startswith("IMPLEMENTED") else "LOW"
        return status, confidence, reason
    return "MISSING_OR_UNPROVEN", "LOW", "No exact ITR1-R%03d validator ID or curated structural coverage found; needs manual implementation/reconciliation" % rule.number


def write_outputs(rules: list[Rule], index: dict[int, list[Evidence]]) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rows = []
    counts: dict[str, int] = {}
    for rule in rules:
        evidence = index[rule.number]
        status, confidence, notes = classify(rule, evidence)
        counts[status] = counts.get(status, 0) + 1
        rows.append({
            "rule_id": f"ITR1-R{rule.number:03d}",
            "category": rule.category,
            "status": status,
            "confidence": confidence,
            "official_rule_text": rule.text,
            "evidence_or_notes": notes,
        })

    with CSV_OUT.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    missing = [row for row in rows if row["status"] == "MISSING_OR_UNPROVEN"]
    partial = [row for row in rows if row["status"] == "PARTIAL"]

    md: list[str] = []
    md.append("# ITR-1 AY 2026-27 Strict Validation Rule Matrix")
    md.append("")
    md.append("This matrix is generated from `tmp_itr1_rules.txt` and current Taxify source code by `scripts/audit_itr1_rule_matrix.py`.")
    md.append("")
    md.append("## Method")
    md.append("")
    md.append("- Parses the official Category-A rules 1–339 from `tmp_itr1_rules.txt`.")
    md.append("- Searches the ITR-1 schema, validators, calculator, schedule modules, ITD builder, and relevant routers for exact `ITR1-Rxxx` evidence.")
    md.append("- Applies a deliberately small curated map for grouped/range validators and structural/calculation coverage where exact IDs are not emitted.")
    md.append("- Anything not proven by exact evidence or curated coverage is marked `MISSING_OR_UNPROVEN`; this avoids false sign-off.")
    md.append("")
    md.append("## Status counts")
    md.append("")
    md.append("| Status | Count |")
    md.append("|---|---:|")
    for status in sorted(counts):
        md.append(f"| {status} | {counts[status]} |")
    md.append(f"| **TOTAL** | **{len(rows)}** |")
    md.append("")
    md.append("## Gaps requiring implementation or explicit reconciliation")
    md.append("")
    md.append(f"Missing/unproven rules: **{len(missing)}**")
    md.append(f"Partial rules: **{len(partial)}**")
    md.append("")
    if missing:
        md.append("### Missing or unproven rule IDs")
        md.append("")
        md.append(", ".join(row["rule_id"] for row in missing))
        md.append("")
    if partial:
        md.append("### Partial rule IDs")
        md.append("")
        md.append(", ".join(row["rule_id"] for row in partial))
        md.append("")
    md.append("## Full matrix")
    md.append("")
    md.append("| Rule | Status | Confidence | Evidence / Notes | Official rule text |")
    md.append("|---|---|---|---|---|")
    for row in rows:
        text = row["official_rule_text"].replace("|", "\\|")
        notes = row["evidence_or_notes"].replace("|", "\\|")
        md.append(f"| {row['rule_id']} | {row['status']} | {row['confidence']} | {notes} | {text} |")
    md.append("")
    md.append("## Regeneration")
    md.append("")
    md.append("```powershell")
    md.append("cd C:\\Users\\Devansh\\Desktop\\Taxify")
    md.append("python scripts/audit_itr1_rule_matrix.py")
    md.append("```")
    md.append("")
    MD_OUT.write_text("\n".join(md), encoding="utf-8")


def main() -> None:
    rules = parse_rules()
    if len(rules) != 339:
        raise SystemExit(f"Expected 339 Category-A rules, parsed {len(rules)}")
    index = build_evidence_index()
    write_outputs(rules, index)
    print(f"Parsed rules: {len(rules)}")
    print(f"Wrote: {CSV_OUT.relative_to(ROOT)}")
    print(f"Wrote: {MD_OUT.relative_to(ROOT)}")

if __name__ == "__main__":
    main()
