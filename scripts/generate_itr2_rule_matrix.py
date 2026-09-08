from __future__ import annotations
import re
from pathlib import Path

root = Path(__file__).resolve().parent.parent
source = root / 'tmp' / 'cbdt_rules' / 'CBDT__e-Filing_ITR 2_Validation Rules_AY 2026-27_V1.0 (1).txt'
out = root / 'Docs' / 'ITR2_CBDT_VALIDATION_RULE_MATRIX.md'
lines = source.read_text(encoding='utf-8').splitlines()

def parse(start: int, end: int, expected_start: int, expected_end: int) -> list[tuple[int, str, int]]:
    rows: list[tuple[int, str, int]] = []
    number: int | None = None
    parts: list[str] = []
    source_line = 0
    expected = expected_start
    pattern = re.compile(r'^\s*(\d{1,3})(?:\.\s*|\s*$)(.*)$')
    for index in range(start, end):
        match = pattern.match(lines[index])
        if match and int(match.group(1)) == expected:
            value = match.group(2).strip()
            if value:
                if number is not None:
                    rows.append((number, ' '.join(parts), source_line))
                number = expected
                expected += 1
                parts = [value]
                source_line = index + 1
            else:
                # PDF extraction sometimes places the next rule's first
                # wrapped line immediately before its standalone number.
                # Move that final line to the new rule while retaining the
                # prior rule's remaining continuation text.
                continuation = parts[-1:] if parts else []
                if parts:
                    parts = parts[:-1]
                if number is not None:
                    rows.append((number, ' '.join(parts), source_line))
                number = expected
                expected += 1
                parts = continuation
                source_line = index + 1
        elif number is not None:
            value = lines[index].strip().replace('\\f', '')
            if value:
                parts.append(value)
    if number is not None:
        rows.append((number, ' '.join(parts), source_line))
    if expected != expected_end + 1:
        raise SystemExit(f'Could not parse sequential rules {expected_start}-{expected_end}; stopped at {expected - 1}')
    return rows

category_a_table = next(i for i, value in enumerate(lines) if value.strip() == 'Table 2: Category A Rules')
category_bd_table = next(i for i, value in enumerate(lines) if value.strip() == 'Table 3: Category B/D Rule')
category_a = next(i for i in range(category_a_table, category_bd_table) if lines[i].strip() == 'Sl. No. Scenario')
category_bd = next(i for i in range(category_bd_table, len(lines)) if lines[i].strip() == 'Sl. No Scenarios')
a_rules = parse(category_a + 1, category_bd_table, 1, 764)
bd_rules = parse(category_bd + 1, len(lines), 1, 26)
if len(a_rules) != 764 or len(bd_rules) != 26:
    raise SystemExit(f'Unexpected inventory sizes: {len(a_rules)} and {len(bd_rules)}')
if {n for n, _, _ in a_rules} != set(range(1, 765)) or {n for n, _, _ in bd_rules} != set(range(1, 27)):
    raise SystemExit('Rule numbering is incomplete or duplicated')

def clean(value: str) -> str:
    return value.replace('|', '\\|').replace('\n', ' ')

def classification(number: int, category: str) -> tuple[str, str, str]:
    """Return a conservative disposition based on the current code audit.

    Direct validator IDs are only used where the current ITR-2 validator emits
    an identifiable rule. Formula/builder ranges are deliberately labeled
    indirect: they are not equivalent to a CBDT rule-specific validator until
    a focused proof test and exact correspondence are recorded.
    """
    if category == 'B/D':
        if number == 5:
            return ('Implemented — warning emitted', 'app/engine/validators/itr2/input_rules.py:570-580; tests/test_itr2_input_validation.py:482-493', 'ITR2-IN-FORM-001; direct test evidence present')
        if number == 6:
            return ('Implemented — warning emitted', 'app/engine/validators/itr2/input_rules.py:581-588; tests/test_itr2_input_validation.py:496-508', 'ITR2-IN-FORM-002; direct test evidence present')
        if number in {9, 10, 20, 21, 23, 24}:
            return ('External dependency / pending', 'No local validator; requires another taxpayer, ITD/Aadhaar state, or external filing document', 'Add integration boundary or document approved external ownership')
        if number == 25:
            return ('Calculator behavior — proof pending', 'app/engine/calculators/itr2.py; no Category B/D warning emitted', 'Add CII proof test and/or warning if CBDT advisory must be surfaced')
        return ('Missing — no warning emitted', 'No dedicated implementation found in app/engine/validators/itr2/', 'Implement Category B/D reminder or document why it is unavailable')

    direct: dict[int, tuple[str, str, str]] = {}
    def add(numbers: range | set[int], rule_id: str, line: str, tests: str = '') -> None:
        evidence = f'app/engine/validators/itr2/{line}'
        if tests:
            evidence += f'; {tests}'
        for item in numbers:
            direct[item] = ('Explicit validator executed', evidence, rule_id)

    add({20}, 'ITR2-IN-PROFILE-002', 'input_rules.py:~', 'tests/test_itr2_input_validation.py:~')
    add({9}, 'ITR2-IN-PROFILE-003', 'input_rules.py:~', 'tests/test_itr2_input_validation.py:~')
    add({21}, 'ITR2-IN-REGIME-001', 'input_rules.py:~', 'tests/test_itr2_input_validation.py:~')
    add({36, 40}, 'ITR2-IN-SAL-009', 'input_rules.py:~', 'tests/test_itr2_input_validation.py:~')
    add({37}, 'ITR2-IN-SAL-010', 'input_rules.py:~', 'tests/test_itr2_input_validation.py:~')
    add({57}, 'ITR2-IN-SAL-007', 'input_rules.py:148-152', 'tests/test_itr2_input_validation.py:148-159')
    add({41}, 'ITR2-IN-SAL-001', 'input_rules.py:105-112', 'tests/test_itr2_input_validation.py:58-71')
    add({42}, 'ITR2-IN-SAL-002', 'input_rules.py:113-119', 'tests/test_itr2_input_validation.py:74-85')
    add({43}, 'ITR2-IN-SAL-003', 'input_rules.py:120-126', 'tests/test_itr2_input_validation.py:88-99')
    add({48}, 'ITR2-IN-SAL-004', 'input_rules.py:127-130', 'tests/test_itr2_input_validation.py:102-115')
    add({54}, 'ITR2-IN-SAL-006', 'input_rules.py:138-147', 'tests/test_itr2_input_validation.py:134-145')
    add({57}, 'ITR2-IN-SAL-007', 'input_rules.py:148-152', 'tests/test_itr2_input_validation.py:148-159')
    add({58}, 'ITR2-IN-SAL-008', 'input_rules.py:153-157', 'tests/test_itr2_input_validation.py:162-173')
    add({71}, 'ITR2-IN-HP-001', 'input_rules.py:169-174', 'tests/test_itr2_input_validation.py:176-189')
    add({74}, 'ITR2-IN-HP-002', 'input_rules.py:175-180', 'tests/test_itr2_input_validation.py:192-203')
    add({80}, 'ITR2-IN-HP-003', 'input_rules.py:181-187', 'tests/test_itr2_input_validation.py:206-220')
    add({757}, 'ITR2-IN-HP-006', 'input_rules.py:203-214', 'tests/test_itr2_input_validation.py:272-291')
    add({70}, 'ITR2-IN-HP-007', 'input_rules.py:202-214', 'tests/test_itr2_input_validation.py:293-324')
    add(set(range(84, 91)), 'ITR2-IN-112A-001..007', 'input_rules.py:368-418', 'tests/test_itr2_validators.py:62-81')
    add({173, 174}, 'ITR2-IN-112A-008', 'input_rules.py:419-426', 'tests/test_itr2_input_validation.py:323-332')
    add({178, 179, 180, 181, 188, 189}, 'ITR2-IN-VDA-001..004', 'input_rules.py:428-453', 'tests/test_itr2_validators.py:85-95; tests/test_itr2_input_validation.py:335-348')
    add({229}, 'ITR2-IN-SI-001', 'input_rules.py:553-565', 'tests/test_itr2_input_validation.py:406-430')
    add({275}, 'ITR2-IN-BFL-001..004', 'input_rules.py:456-485', 'tests/test_itr2_validators.py:98-105')
    add({342}, 'ITR2-IN-VIA-001', 'input_rules.py:231-248', 'tests/test_itr2_input_validation.py:365-374')
    add({759}, 'ITR2-IN-VIA-004', 'input_rules.py:282-290', 'tests/test_itr2_input_validation.py:404-421')
    add({317, 318, 319, 320, 321, 324, 325, 326}, 'ITR2-IN-VIA-002', 'input_rules.py:249-266', 'tests/test_itr2_input_validation.py:377-390')
    add({327, 328, 329}, 'ITR2-IN-VIA-003', 'input_rules.py:267-281', 'tests/test_itr2_input_validation.py:393-401')
    add({444}, 'ITR2-IN-FSI-001', 'input_rules.py:487-498')
    add({443}, 'ITR2-IN-FSI-003', 'input_rules.py:535-540', 'tests/test_itr2_input_validation.py:~')
    add({442}, 'ITR2-IN-TR1-001', 'input_rules.py:545-555', 'tests/test_itr2_validators.py:108-138')
    add({453}, 'ITR2-IN-TR1-003', 'input_rules.py:558-564', 'tests/test_itr2_input_validation.py:~')
    add({454}, 'ITR2-IN-TR1-004', 'input_rules.py:579-586', 'tests/test_itr2_input_validation.py:~')
    add({455}, 'ITR2-IN-TR1-005', 'input_rules.py:587-594', 'tests/test_itr2_input_validation.py:~')
    add({451, 452}, 'ITR2-IN-TR1-002', 'input_rules.py:595-603', 'tests/test_itr2_validators.py:108-138')
    add({229}, 'ITR2-IN-SI-001', 'input_rules.py:553-565', 'tests/test_itr2_input_validation.py:406-430')
    add({426, 427}, 'ITR2-IN-AMT-001', 'input_rules.py:600-611', 'tests/test_itr2_validators.py:108-138')
    add({428, 429}, 'ITR2-IN-AMT-002', 'input_rules.py:612-616', 'tests/test_itr2_validators.py:108-138')
    add({466, 467}, 'ITR2-IN-TDS-001', 'input_rules.py:628-637', 'tests/test_itr2_input_validation.py:436-464')
    add({463}, 'ITR2-IN-TDS-002', 'input_rules.py:666-673', 'tests/test_itr2_input_validation.py:~')
    add({462}, 'ITR2-IN-TDS-006', 'input_rules.py:824-830', 'tests/test_itr2_input_validation.py:~')
    add({464}, 'ITR2-IN-TDS-005', 'input_rules.py:815-821', 'tests/test_itr2_input_validation.py:~')
    add({465}, 'ITR2-IN-TDS-009', 'input_rules.py:852-858', 'tests/test_itr2_input_validation.py:~')
    add({468}, 'ITR2-IN-TDS-008', 'input_rules.py:832-840', 'tests/test_itr2_input_validation.py:~')
    add({479}, 'ITR2-IN-TDS-007', 'input_rules.py:831-843', 'tests/test_itr2_input_validation.py:~')
    add({480}, 'ITR2-IN-ESOP-001', 'input_rules.py:771-781', 'tests/test_itr2_input_validation.py:~')
    add({754}, 'ITR2-IN-CG-009', 'input_rules.py:790-803', 'tests/test_itr2_input_validation.py:~')
    add({471}, 'ITR2-IN-TDS-004', 'input_rules.py:680-692', 'tests/test_itr2_input_validation.py:~')
    add({472}, 'ITR2-IN-TDS-003', 'input_rules.py:674-679', 'tests/test_itr2_input_validation.py:~')
    add(set(range(101, 109)), 'ITR2-IN-CG-101..108', 'input_rules.py:~', 'tests/test_itr2_input_validation.py:~')
    add({650}, 'ITR2-IN-TDS-010..011', 'input_rules.py:~', 'tests/test_itr2_input_validation.py:~')
    add({652}, 'ITR2-IN-PROFILE-001', 'input_rules.py:~', 'tests/test_itr2_input_validation.py:~')
    add({653}, 'ITR2-IN-HP-008', 'input_rules.py:~', 'tests/test_itr2_input_validation.py:~')
    add({658, 659}, 'ITR2-IN-VIA-010..011', 'input_rules.py:~', 'tests/test_itr2_input_validation.py:~')
    add({662}, 'ITR2-IN-CG-010', 'input_rules.py:~', 'tests/test_itr2_input_validation.py:~')
    add({754}, 'ITR2-IN-CG-009', 'input_rules.py:~', 'tests/test_itr2_input_validation.py:~')
    add({479}, 'ITR2-IN-TDS-007', 'input_rules.py:~', 'tests/test_itr2_input_validation.py:~')
    add({480}, 'ITR2-IN-ESOP-001', 'input_rules.py:~', 'tests/test_itr2_input_validation.py:~')
    add({611, 612, 613, 614, 615, 616, 617, 618}, 'ITR2-IN-SCHEDULE-PENDING', 'Schedule 80D row-level insurer fields are absent from canonical ITR2Input')
    add({619}, 'ITR2-IN-FORM-004', 'input_rules.py:~', 'tests/test_itr2_input_validation.py:~')
    add({542}, 'ITR2-IN-FORM-003', 'input_rules.py:695-704', 'tests/test_itr2_input_validation.py:~')
    add({548}, 'ITR2-IN-VIA-007', 'input_rules.py:727-741', 'tests/test_itr2_input_validation.py:~')
    add({763}, 'ITR2-IN-VIA-005', 'input_rules.py:710-716', 'tests/test_itr2_input_validation.py:~')
    add({764}, 'ITR2-IN-VIA-006', 'input_rules.py:717-723', 'tests/test_itr2_input_validation.py:~')
    add({750}, 'ITR2-IN-CG-007', 'input_rules.py:354-361', 'tests/test_itr2_input_validation.py:274-289')
    add({591}, 'ITR2-IN-CG-008', 'input_rules.py:362-366', 'tests/test_itr2_input_validation.py:292-309')
    add({751}, 'ITR2-IN-HP-004', 'input_rules.py:188-194', 'tests/test_itr2_input_validation.py:228-247')
    add({753}, 'ITR2-IN-HP-005', 'input_rules.py:195-201', 'tests/test_itr2_input_validation.py:250-269')
    add({456}, 'ITR2-CALC-027', 'calc_rules.py:260-276', 'tests/test_itr2_calc_validation.py:27-54')
    if number in direct:
        return direct[number]

    # These rules are represented as derived calculator/builder output. The
    # current audit does not claim exact CBDT rule equivalence without a
    # rule-specific proof test.
    derived_ranges = [set(range(22, 28)), set(range(67, 70)), {72, 75, 76, 77, 78, 81},
                      set(range(190, 234)), set(range(234, 275)), set(range(277, 366)),
                      set(range(366, 422)), set(range(422, 434)), set(range(435, 461)),
                      set(range(461, 541))]
    if any(number in group for group in derived_ranges):
        return ('Indirect calculator/schema/builder coverage — proof pending', 'app/engine/calculators/itr2.py; app/engine/schedules/; app/engine/itd/itr2.py', 'Add exact CBDT-rule mapping and focused known-good/known-bad proof test before marking complete')

    external = {1, 2, 3, 11, 12, 15, 16, 17, 20, 82, 457, 746, 747, 748}
    if number in external:
        return ('External dependency / not locally verifiable', 'app/schemas/itr2.py; app/engine/filing_gateway_v2.py; ITD/PAN/Aadhaar/portal state is not available to local validation', 'Define integration check or record approved external ownership')

    return ('Missing / not representable / pending', 'app/schemas/itr2.py; app/engine/draft_to_itr2_input.py; no exact enforcement found', 'Implement, add the required canonical field, preserve the source row, or document approved non-representability')


out_lines = [
    '# ITR-2 CBDT Validation Rule Matrix — AY 2026–27', '',
    '**Status:** Initial authoritative inventory and implementation tracker.',
    '**Source:** Official CBDT PDF `Reference Docs by CBDT & ITD/Official Validations/CBDT__e-Filing_ITR 2_Validation Rules_AY 2026-27_V1.0 (1).pdf`; extracted source: `tmp/cbdt_rules/CBDT__e-Filing_ITR 2_Validation Rules_AY 2026-27_V1.0 (1).txt`.',
    '**Inventory:** 764 Category A rules + 26 Category B/D rules = **790 rules**.',
    '**Completion gate:** A rule is complete only when this row has exact implementation evidence and a regression test, or an explicitly documented proof that schema/calculator/builder construction guarantees it.', '',
    '## Status definitions', '',
    '- **Explicit validator / derived check:** a runtime validator or exact post-calculation check executes on the filing path.',
    '- **Calculator/schema/builder invariant:** the value is derived or constrained before JSON emission; proof tests are still required.',
    '- **Missing / pending / not representable:** no complete enforcement exists, required data is absent, or mapper/pipeline behavior prevents validation.',
    '- **Pending / external / not representable:** Category B/D rule needs external portal/document/another taxpayer data or a missing model field.', '',
    '## Inventory integrity', '',
    '| Category | Expected | Parsed |', '|---|---:|---:|', f'| Category A | 764 | {len(a_rules)} |', f'| Category B/D | 26 | {len(bd_rules)} |', f'| **Total** | **790** | **{len(a_rules) + len(bd_rules)}** |', '',
    '## Category A rules', '',
    '| # | Official CBDT scenario | Status | Exact evidence | Validator / action | Source line |', '|---:|---|---|---|---|---:|']
for number, scenario, source_line in a_rules:
    status, evidence, action = classification(number, 'A')
    out_lines.append(f'| {number} | {clean(scenario)} | {clean(status)} | {clean(evidence)} | {clean(action)} | {source_line} |')
out_lines += ['', '## Category B/D rules', '', '| # | Official CBDT scenario | Status | Exact evidence | Validator / action | Source line |', '|---:|---|---|---|---|---:|']
for number, scenario, source_line in bd_rules:
    status, evidence, action = classification(number, 'B/D')
    out_lines.append(f'| {number} | {clean(scenario)} | {clean(status)} | {clean(evidence)} | {clean(action)} | {source_line} |')
out_lines += ['', '## Required workflow for every implementation part', '', '1. Resolve rows marked missing, pending, or invariant with exact code and test evidence.', '2. Never silently drop invalid ReturnDraft rows before validation; preserve them or return a blocking mapping error.', '3. Add one known-good and one known-bad regression test for every explicit Category A validator.', '4. Add gateway tests proving invalid canonical ITR-2 drafts are blocked before JSON emission.', '5. Update this matrix in the same commit as each implementation part.', '6. Run the focused tests and full regression matrix before pushing.', '7. Do not claim all 790 rules are implemented until the matrix has no unresolved rows and remains exactly 764 + 26 = 790.']
out.write_text('\n'.join(out_lines) + '\n', encoding='utf-8')
print(f'Wrote {out} with {len(a_rules) + len(bd_rules)} rows.')
