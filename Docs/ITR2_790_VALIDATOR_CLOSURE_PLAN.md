# ITR-2: Close All 790 Official CBDT Validation Rules — Implementation Plan

## Context

We independently re-extracted all 790 official CBDT ITR-2 Validation Rules (AY 2026-27) directly
from the source PDF (`Reference Docs by CBDT & ITD/Official Validations/CBDT__e-Filing_ITR 2_
Validation Rules_AY 2026-27_V1.0 (1).pdf` — 764 Category A rules + 26 Category B/D rules) and
cross-checked every single one against the **current code**, not against `Docs/
ITR2_VALIDATOR_GAP_MAPPING_AY2026_27.md` or any other markdown doc (the user explicitly
distrusts these as stale). The full per-rule result is saved at
`Docs/ITR2_VALIDATOR_INDEPENDENT_VERIFICATION_790_RULES.csv` in the repo (columns: `GlobalNo`,
`Category`, `PdfSlNo`, `Status`, `Evidence`).

Result: **542 Implemented, 125 Not Implemented, 81 Missing (no underlying schema field exists),
39 Partially Implemented, 3 Deferred (justified by an explicit in-code comment)**. This is
materially different from the existing gap-mapping doc's claim that all "175 genuine gaps" are
closed — this fresh count finds **248 rules** (31%) not fully covered. This plan closes that gap,
implementing every rule the codebase can actually check, and documents the handful that
structurally cannot be (rules needing live external government data this system has no access
to).

Along the way, the verification also surfaced **8 non-validator code defects** (numeric
discrepancies, a silent regime-logic contradiction, a duplicate rule-ID, incomplete guard
conditions) that are real bugs independent of "is a PDF rule checked" — these are included as
their own phase.

**Goal of this plan**: a phased, testable path to closing all 790 rules — 781 with real
implemented checks, and 9 explicitly resolved (implemented as best-effort informational checks,
or formally documented as out of scope) after a research spike into whether external-data
integration is feasible at all.

## Ground-truth artifacts (already produced, referenced throughout)

- `Docs/ITR2_VALIDATOR_INDEPENDENT_VERIFICATION_790_RULES.csv` — all 790 rows, Status + Evidence.
- Scratchpad working files (to be copied into `Docs/` as the first execution step — see Phase 6):
  `gaps_missing.csv` (81), `gaps_not_implemented.csv` (125), `gaps_partially_implemented.csv`
  (39), `gaps_deferred.csv` (3) — same schema as the master CSV plus the actual `RuleText` column,
  at `C:\Users\Devansh\AppData\Local\Temp\claude\C--Users-Devansh\
  8588a125-6f50-47da-b69a-411741875645\scratchpad\itr2_validators\`.

Existing code entry points (all confirmed live and wired, not aspirational):
- `app/engine/validators/itr2/input_rules.py` (2552 lines) — pre-compute checks,
  `validate_itr2_input(inp) -> list[ValidationResult]`, called by `run_input_validation`.
- `app/engine/validators/itr2/calc_rules.py` (376 lines) — post-computation cross-schedule
  checks, called by `run_calc_validation`.
- `app/engine/validators/itr2/__init__.py` — wires both into `run_all`, itself called from
  `app/engine/filing_gateway_v2.py::_generate_cbdt_json_itr2`.
- Rule ID convention already in use: `ITR2-IN-<AREA>-<NNN>` (e.g. `ITR2-IN-SAL-010`,
  `ITR2-IN-VIA-001`) for input rules, `ITR2-CALC-<NNN>` for calc rules. New rules must follow
  this — extend an existing `<AREA>` bucket's numbering where one exists (`SAL`, `HP`, `CG`,
  `OS`, `SI`, `VIA`, `TDS`, `DTAA`, ...), introduce a new `<AREA>` only for genuinely new
  schedules (`PTI`, `EI`, `AMTC`, `ESOP`, `FA`).
- Test files to extend (all currently passing, 486/492 baseline — do not regress):
  `tests/test_itr2_validators.py`, `tests/test_itr2_input_validation.py`,
  `tests/test_itr2_calc_validation.py`, `tests/test_itr2_itd_builder.py`,
  `tests/test_itr2_integration.py`. Repo convention (see `CLAUDE.md`): write the known-bad test
  case *before* the fix — if the schema can't even construct the bad state, the rule may already
  be structurally moot.

---

## Phase 0 — Non-validator defects found during verification (do first, small and self-contained)

These are real bugs independent of the 790-rule checklist; fix and test each individually.

1. **Rule-ID collision**: `ITR2-IN-HP-009` is used for two unrelated checks
   (`input_rules.py:466` and `:1765`). Rename the second occurrence to the next free `HP-0NN`.
   Check no code/tests key off the ID string for the wrong one.
2. **Professional tax cap discrepancy**: code caps at ₹2,500 (`ITR2-IN-SAL-010`,
   `input_rules.py:161-166`); the PDF's rule #37 text says ₹5,000. Before changing anything,
   verify against a primary source (Income-tax Act s.16(iii) / the current Finance Act figure) —
   the repo's own convention (see `CLAUDE.md`'s ₹2,500-vs-₹5,000 note on a different, still-open
   rule) is not to trust either the code or the PDF blindly. Fix the cap to match whichever is
   actually correct, or add a documented deferral comment (matching rules #323/#347's pattern) if
   the PDF is the one that's wrong.
3. **Rule #350 / 80CCH regime contradiction**: `section_80cch.py` explicitly implements 80CCH as
   allowed in *both* regimes with a docstring defending that; the PDF's rule #350 says 80CCH(1) is
   *not* allowed under the new regime. Unlike #323/#347 (which have defending comments citing
   cross-form evidence), #350 has none — this is a silent, unexplained gap. Research the actual
   statute, then either fix the regime gating or add the same kind of documented-deviation comment
   used for #323/#347.
4. **`AcquisitionCost` vs `CostAcqWithoutIndx` field-name ambiguity** (rules #85/86/92/93): the
   112A/115AD grandfathering higher-of/lower-of formula is computed correctly in
   `itd/itr2.py:2266-2268`, but written to a field named `AcquisitionCost`. Check the actual
   official ITD JSON schema (`app/engine/itd/itr2_schema.py` / `Reference Docs by CBDT & ITD/
   Official JSON Schema/`) for the real required key name for Col.7. If the correct key is
   `CostAcqWithoutIndx`, this is a live field-mapping bug (the class of bug `CLAUDE.md` already
   flags as historically real and dangerous) — fix the builder. If `AcquisitionCost` is in fact
   correct, mark rules #85/86/92/93 Implemented in the tracking CSV with that evidence.
5. **Rule #177/#187 — 112A/115AD mutual exclusivity**: `calculators/itr2.py:635` concatenates
   `cg_112a_scrips` and `cg_115ad_scrips` unconditionally with no check preventing both being
   populated by the same return, though the PDF says only one schedule applies. Add an
   `ITR2-IN-CG-0NN` pre-compute rule.
6. **Rule #605 — HRA validator silent skip**: `ITR2-IN-SAL-015`'s guard
   (`input_rules.py:329`) only runs when `employer_filing_details` is non-empty, so a claim with
   `hra_exempt_amount > 0` and zero Table 10(13A) rows is never caught. Fix the guard to fire
   whenever the exemption is claimed, regardless of row presence.
7. **Rule #535 — 87A rebate over-broad exclusion**: `calculators/itr2.py:443`'s `is_resident`
   check excludes `NOT_ORDINARILY_RESIDENT` unconditionally, denying RNOR the rebate always — the
   PDF rule only denies it above the ₹5L old-regime threshold. Narrow the condition to match the
   rule.
8. **Documentation/tracking discrepancy**: `Docs/ITR2_VALIDATOR_GAP_MAPPING_AY2026_27.md` claims
   all "175 genuine gaps" are closed; this fresh, code-verified count finds 248. Once this plan's
   phases land, retire or fully rewrite that doc against the new authoritative CSV rather than
   patching it — do not try to reconcile the two numbering schemes.

## Phase 1 — Research spike: are the 9 externally-dependent rules integrable at all?

Per the user's decision, investigate before deciding how to close these:
- **PAN-database name/DOB match** (#2, #3, #664, #665) — is there an NSDL/e-Filing PAN
  verification API this system could call? Check if `app/eri/` already has any adjacent
  capability (the ERI Type-2 API surface is the most likely existing integration point).
- **Cross-taxpayer TDS/TCS credit verification** (BD #9/#10, rules #773/#774) — requires seeing
  another person's filed return; almost certainly not integrable by any taxpayer-side filing tool.
  Document why and move to "permanently out of scope" rather than spending further research time.
- **RBI IFSC database match** (#532) — RBI publishes an IFSC list; check if a static/periodically-
  refreshed local IFSC dataset is a viable substitute for a live database call (this one is the
  most plausible to actually close for real, unlike the PAN/Aadhaar ones).
- **Aadhaar-PAN linking status** (BD #23/#24, rules #787/#788) — check if the e-Filing/ERI API
  surface exposes any linking-status field already being received (e.g. from prefill data) that's
  just not being checked yet, vs. needing a new external call.

Output of this phase: for each of the 4 clusters, a concrete decision — "implement using
[integration]" or "document as permanently out of scope, reason: [X]" — recorded in the tracking
CSV. Do not let this spike block Phases 2-5, which don't depend on its outcome.

## Phase 2 — New validators requiring no schema changes (125 "Not Implemented" rules)

This is the bulk of the work but the lowest-risk: every field these rules need already exists.
Work cluster by cluster (each independently shippable/testable), following the existing file's
patterns exactly (`_result()` helper, `Severity.A` vs `D` matching Category A/B-D, blocking vs.
warning per the existing convention).

Clusters (rule numbers below are `GlobalNo`s — cross-reference `gaps_not_implemented.csv` for
exact PDF text per rule):

1. **Schedule Salary** (~16 rules: 11, 30, 32, 33, 34, 36, 51, 55, 56, 59, 60, 61, 66, 601, 605
   [Phase 0 #6 above], 606) — dropdown-sum-vs-headline reconciliations, old/new-regime allowance
   caps, section 89A HUF/ceiling checks. Follow the pattern of the existing `ITR2-IN-SAL-*` rules
   immediately preceding each.
2. **OS ↔ SI special-rate income reconciliation** (~53 rules: 192, 198, 225, 228, 366, 367, 369,
   370, 371, 372, 373, 375, 378-418). **Important implementation note**: the PDF repeats the same
   "OS Sl.2d/2e should equal corresponding SI income" sentence roughly a dozen times with only
   category labels varying (115BB, 115BBE, 115AD, DTAA dividend, etc.) — this is not 53 distinct
   checks to write by hand. Design ~6-10 generic parametrized reconciliation functions (one per OS
   special-income sub-category vs. its SI counterpart) that collectively close the whole cluster,
   rather than one-off functions per PDF row. Reference which OS field and which SI entry each
   maps to using the existing `_DIVIDEND_SECTION_DATE_RANGE_FIELD`-style mapping table pattern
   already in `itd/itr2.py:967-976`.
3. **Chapter VI-A / deductions eligibility & ceilings** (~28 rules: 314, 331, 333-341, 348, 611-
   618, 620, 627, 645, 648, 649, 756, 760, 761 — excludes 350, handled in Phase 0 #3). Covers
   80GGA schedule-required-when-claimed, 80QQB/80RRB NR/HUF and due-date gating, 80CCD(2)
   pensioner-category exclusion, 80D insurer-name/policy-number required-when-claimed and
   per-bucket premium cross-foot, 80EE/80EEA sequencing and ₹45L stamp-duty ceiling, PRAN
   required-when-claimed.
4. **CYLA/BFLA/CFL forward loss-setoff completeness** (~8 rules: 248, 271, 276, 486, 660, 762,
   771, 775) — the existing checks only catch losses *exceeding* available setoff; add the
   converse "available income not fully absorbed by carried-forward loss" checks for HP/OS/CG.
5. **Capital Gains** (~8 rules: 87, 94, 177 [Phase 0 #5], 183, 187 [dup of 177], 570, 590, 661) —
   FMV cross-multiplication check, date-of-acquisition required-when-claimed, non-resident
   indexation exclusion completeness, 54/54B/54EC sub-detail-required-when-claimed, STCG@15%
   duplicate-entry prevention.
6. **AMTC** (2 rules: 427, 429) — per-row and aggregate carry-forward-credit reconciliation.
7. **Schedule TR** (2 rules: 451, 452) — 90/90A vs 91 relief sub-item reconciliation.
8. **Misc singles**: 69 (HP co-ownership share pre-scaling), 287 (80G category-sum reconciliation),
   481 (ESOP Sl.8 vs Part B-TTI cross-check), 538 (income-schedule-required-when-tax-paid-
   disclosed), 694/695 (234-I revised-return fee gating), 532 (deferred to Phase 1).

Each cluster: implement → write known-bad + known-good tests in the matching test file → run the
full ITR-2 suite (`pytest tests/test_itr2_*.py tests/test_draft_to_itr2_input.py tests/
test_filing_gateway_v2_itr2.py -v`) → confirm 486+N passing, 0 new failures → move to next
cluster. Update the tracking CSV's `Status` to `Implemented` with new file:line evidence as each
rule closes.

## Phase 3 — Complete the 39 "Partially Implemented" rules

Lower cost than Phase 2 (existing validator to extend, not a new one) but requires care to avoid
regressing the already-passing half. Group by what's shared:

- **112A/115AD grandfathering field-name** (85, 86, 92, 93) — resolved by Phase 0 #4.
- **DTAA rate one-directional-vs-equality checks** (152, 207) — `ITR2-IN-CG-004` and
  `ITR2-IN-DTAA-002` currently only check `applicable_rate > ceiling`; change to exact equality
  to the lower of the two rates.
- **Table F quarterly vs BFLA/SI cross-checks** (169, 170, 171, 172, 180, 181) — add explicit
  `calc_rules.py` checks comparing the CG quarterly breakdown builder output against the
  corresponding BFLA/SI fields (both already computed, just never compared).
- **Dividend quarterly vs Sl.2d/2e cross-check** (219, 220, 221, 222, 223, 231) — extend
  `ITR2-IN-OS-012`'s per-row self-consistency check with an additional cross-field check against
  the Sl.2d/2e dividend selection total.
- **OS special-rate headline totals** (196, 206, 208, 214, 217, 247) — add the missing summation/
  cross-schedule terms (e.g. #208's `IncChargeableSpecialRates` needs `IncChargblSplRateOS`/
  `NRIOsDTAA` folded in).
- **Donee PAN vs representative PAN** (277, 313) — extend `ITR2-IN-VIA-031/032` to also check
  against the representative's verification PAN when filed by a representative.
- **80CCH/VIA new-regime disallowed-list gap** (342) — add 80QQB/80RRB to
  `ITR2-IN-VIA-001`'s `_new_regime_disallowed` dict (confirmed genuinely missing, not a duplicate
  of Phase 0 #3).
- **TDS/TCS head-of-income** (464, 465) — extend `ITR2-IN-TDS-005/009` with the missing
  `head_of_income`-required check.
- **Misc**: 191 (OS Sl.3c 4-term sum field-for-field verification), 523 (tax-payable formula
  independent-verification), 547 (80GGC date-range check, not just presence), 549 (co-owner
  name/PAN required, not just share), 596 (new-regime standard-deduction excess-claim surfaced
  pre-compute, mirroring the old-regime sibling `ITR2-IN-SAL-009`), 621/622 (80EE/80EEA loan row
  membership in Table 24(b), not just presence of *a* row).

Same test-then-verify loop as Phase 2.

## Phase 4 — Schema/data-model expansion for the 81 "Missing" rules

Highest cost, highest risk — these require new Pydantic fields, calculator wiring, ITD-builder
mapping, and in most cases **new frontend UI** since no field currently captures the data at all.
Sequence by leverage (biggest rule-count-closed per unit of schema work first) and treat each
sub-phase as its own schema-migration-sized unit of work, not a quick add.

1. **Schedule EI exempt-income sub-categories** (the largest single cluster — ~49 rules: 686,
   698-746) — `app/schemas/itr2.py`'s `ExemptIncome` model currently collapses ~40 distinct
   Section 10 sub-clauses (10(4)(i), 10(12A), 10(16), 10(35), etc.) into one generic
   `other_exempt` bucket. Replace with a structured list of typed exempt-income entries (clause
   code + amount), each clause appearing at most once — this single schema change closes ~49
   rules in one pass since they're all instances of the same "drop-down cannot repeat" pattern.
   Needs: new Pydantic model, calculator pass-through, ITD builder remapping of `itd/
   itr2.py:3245`-adjacent EI construction, **and** a frontend UI change (a structured
   clause-picker replacing whatever free-text/generic field exists today in
   `frontend/src/components/itr2/` — check what's there before assuming nothing is).
2. **PTI structural breakdown** (7 rules: 432, 441, 654-658) — `PTIEntry`
   (`schemas/itr2.py:689-697`) is a flat `income_amount`-only model; the official schedule needs
   Col.7/8/9 (ST/LT/OS sub-splits) and an exempt-income sub-split (a/b/c). Extend `PTIEntry` with
   these sub-fields, update the calculator's PTI aggregation and the ITD builder
   (`itd/itr2.py:3752`-adjacent) to derive real totals instead of hardcoded zeros. Also closes
   the frontend-adjacent gap in `434`/`436`/`445` (EI's DTAA-detail array and agricultural-detail
   array are hardcoded empty for the same "no input field exists" reason — bundle with this or
   Schedule EI sub-phase, whichever lands first, since the fix pattern is identical).
3. **Capital Gains classification fields** (5 rules: 153, 155, 186, 597, 600) — add a
   112(1)(c)/115AC classification field to CG transactions (closes 153/155/597 together), a
   "year of improvement" field alongside the existing `improvement_cost` (186), and a buyback-
   loss classification flag cross-referenced from Schedule OS (600).
2a. **ESOP Sl.4/Sl.5 dropdowns** (2 rules: 482, 483) — add the "sold/not sold" and "auto-populate
   from Sl.3" Yes/No fields to `ESOPDeferralInput`.
2b. **80CCC per-row schedule** (2 rules: 693, 758) — currently a scalar `amount_80ccc`; add a
   row-level schedule (type of identifier, identifier no., amount) matching the 80CCH/80GGC
   per-row pattern already used elsewhere in the same file, for consistency.
2c. **Misc small additions**: 746 (make Schedule FA mandatory when Part B-TTI Sl.19 flag is Yes —
   this is a validator addition once the flag itself is confirmed to already exist, may not need
   a schema change at all, verify first), 4 (track original return's own filing section), 8
   (track uploader's own PAN separately from assessee PAN), 15/17 (role-CD / schedule-enablement
   concepts — lowest priority, smallest rule count, revisit last).

For each schema addition: confirm with a frontend grep first whether UI already exists but is
unwired (cheaper fix) vs. genuinely absent (real feature work) — do not assume the frontend gap
without checking `frontend/src/components/itr2/` and `frontend/src/domain/returns/` directly.
Every new field must round-trip through `draft_to_itr2_input.py` → calculator → ITD builder →
official schema validation (`validate_itr2_json`) before being considered done, per the
project's own complete-preparation contract.

## Phase 5 — Review the 3 "Deferred" rules (323, 347, 598)

These already have defending in-code comments (matching the standard this plan sets for Phase 0's
findings). Low effort: re-verify each comment's cited reasoning is still accurate (e.g. #347's
claim that ITR-1/ITR-4's official PDFs both independently state 46.2%/₹288,000 for the same
provision), and if confirmed, carry them forward unchanged into the new tracking CSV as
`Deferred` with their existing justification — no code change expected unless research turns up
new information.

## Phase 6 — Tracking, docs, and final verification

1. First concrete step of execution (not part of this planning doc): commit the working CSVs
   (`gaps_missing.csv`, `gaps_not_implemented.csv`, `gaps_partially_implemented.csv`,
   `gaps_deferred.csv`) into `Docs/` alongside the already-committed master verification CSV, and
   write this plan itself to `Docs/ITR2_790_VALIDATOR_CLOSURE_PLAN.md` (mirroring how the repo's
   other production-readiness plans are versioned and referenced from `CLAUDE.md`).
2. As each rule closes, update `Docs/ITR2_VALIDATOR_INDEPENDENT_VERIFICATION_790_RULES.csv` in
   place (`Status` → `Implemented`, `Evidence` → new file:line) rather than creating a second,
   parallel tracking artifact — this repo has previously accumulated multiple overlapping
   validator-tracking docs; don't repeat that.
3. Retire/rewrite `Docs/ITR2_VALIDATOR_GAP_MAPPING_AY2026_27.md` once this plan's phases close
   (Phase 0 item #8) — reconciling its "175" figure against the "248" figure item-by-item is not
   worth the effort; the new CSV supersedes it.
4. Final verification gate before declaring "790/790 (or 781/790 + 9 documented) closed": run the
   full ITR-2 suite plus a fresh independent re-derivation pass (same method used to produce this
   plan — re-parse the PDF, re-grep the code) to confirm the count, rather than trusting the
   incrementally-updated CSV alone — this mirrors the exact failure mode (accumulated doc drift)
   that motivated this whole exercise.
5. This plan does **not** change ITR-2's Type-2 direct-API submission gate
   (`app/routers/filing.py`, confirmed hard-blocked pending live UAT hardening) — closing these
   790 rules is necessary but not sufficient for lifting that gate; that remains a separate,
   later decision requiring an actual live UAT round, per prior findings in this conversation.

## Verification approach (applies to every phase)

- Unit-test each new/modified rule with both a known-bad input (must fail/warn) and a known-good
  input (must pass) in the appropriate `tests/test_itr2_*.py` file, following existing test
  naming/style in that file.
- After each cluster: `pytest tests/test_itr2_validators.py tests/test_itr2_input_validation.py
  tests/test_itr2_calc_validation.py tests/test_itr2_itd_builder.py tests/test_itr2_integration.py
  tests/test_draft_to_itr2_input.py tests/test_filing_gateway_v2_itr2.py -v` — must stay at the
  486/492 baseline plus newly-added passing tests, zero new failures.
- After Phase 4's schema changes: additionally run the official-schema validation path
  (`validate_itr2_json`) against a full sample return exercising every new field, confirming no
  `jsonschema` violations — this is the exact failure mode `CLAUDE.md` flags as historically real
  (schema-valid-but-wrong-number bugs, and `_to_rupees()` accumulator pitfalls) for this file.
- Do not touch the Type-2 submission gate as part of this work (see Phase 6 item 5).
