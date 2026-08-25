# ITR-1 and ITR-4 Production-Readiness Audit, AY 2026-27

**Date:** 2026-08-23

**Scope:** Canonical frontend draft, backend mapping, tax computation,
validation, and official CBDT JSON generation for ITR-1 and ITR-4.

**Authority:** `ITR-1_2026_Main_V1.1 (2).json` and
`ITR-4_2026_Main_V1.1 (2).json` in the CBDT reference directory.

## Executive summary

| Measure | ITR-1 | ITR-4 |
|---|---:|---:|
| Schema paths | 573 | 636 |
| Deduplicated required paths | 421 | 408 |
| Present across the variant-union audit document | 421 (100.0%) | 408 (100.0%) |
| Missing across the variant-union audit document | 0 | 0 |
| Present but empty conditional arrays | 0 | 0 |
| Official schema validation | Pass | Pass |

The audit generator builds one maximally-populated canonical draft per
*filing variant* (mutually-exclusive branches such as the 80EE vs 80EEA
loan, or the 44AD vs 44ADA vs 44AE presumptive scheme), generates the
official CBDT JSON for each, and **unions the present-path sets**. A path
is reported MISSING only when it is absent or empty across ALL variants;
every required path is now exercised by at least one variant.

Variants audited:
- **ITR-1**: 80EEA default + 80EE senior-citizen loan (for Schedule 80EE,
  the senior 80D policy arrays, 80EEB EV-loan, 80DD, 80U with Form 10-IA,
  all four 80G categories, 80GGA, 80GGC, 7th-proviso clause-iv,
  representative assessee + alternate address, TRP, PRAN/NPS, restricted
  112A, exempt-income detail rows).
- **ITR-4**: 44AD + 44ADA + 44AE presumptive schemes, plus a 44AD/80EE
  senior-citizen variant (for ITR-4 Schedule 80EE, senior 80D arrays,
  all Schedule BP business-identity + goods-vehicle + GSTIN-turnover rows,
  exempt-income detail rows).

CBDT schedules are conditional and mutually exclusive; the scenario
figures are union coverage, not a claim that every path appears in every
return. The exhaustive field matrices below contain no unresolved
implementation statuses:

| Matrix classification | ITR-1 | ITR-4 |
|---|---:|---:|
| Present | 424 | 468 |
| Derived-System | 149 | 168 |
| Partial / Missing / Incorrect | 0 | 0 |
| Total schema paths | 573 | 636 |

**Verdict:** ITR-1 and ITR-4 are production-ready for the implemented AY
2026-27 scope. Every official schema path is classified as either a persisted
taxpayer input or a system-derived structural, statutory, or aggregate value.
Both forms generate schema-valid official JSON across every audited filing
variant, and the canonical data-loss and calculation defects found in this
audit are fixed. All 421 (ITR-1) and 408 (ITR-4) deduplicated required paths
are now exercised end-to-end by the audit fixture union — no conditional
branch remains unproven.

## Implemented findings

### Filing identity and preflight

- Complete `ReturnFileSec` mapping, including revised returns and required
  original-return metadata.
- Personal-level `EmployerCategory` using the CBDT enum, independent of
  employer rows.
- Constrained state and employment enums.
- Frontend and backend PIN validation.
- CBDT TAN validation for employer, TDS, and TCS rows. TDS3 remains correctly
  PAN/Aadhaar based.
- Older persisted drafts are normalized to include the new 80CCC list.

### Deductions and conditional schedules

- Schedule 80C detail rows retain identifiers.
- `PensionContribution80CCC` retains identifier type, identifier name, and
  amount from the editor through official JSON.
- Schedule 80D retains policy evidence, preventive checkups, and senior
  citizen medical expenditure. It is emitted only under the old regime.
- Schedule 80G, 80GGA, and 80GGC rows are mapped, with eligible amounts used
  for deduction cross-footing.
- Structured 80DD and 80U schedules and Form 10-IA metadata are propagated.
- 80E, 80EE, 80EEA, and 80EEB canonical loan rows are mapped. ITR-4 now emits
  the required 80EEA property stamp-duty value.
- Schedule 10(13A) is derived from employer evidence. Mixed metro and
  non-metro evidence is rejected because one CBDT schedule cannot truthfully
  represent both classifications.

### House property

- The shared editor captures the complete ITR-1/ITR-4 property address,
  ownership type, co-owner identities and shares, tenant identities, rent
  details, and Section 24(b) loan evidence.
- `AnnualLetableValue` is the authoritative canonical GAV input. Legacy
  `annualRent` is retained only as a migration fallback; municipal/fair-rent
  helper values no longer silently override the official schedule value.
- The calculator derives balance ALV after unrealized rent and local taxes,
  applies the assessee's ownership share, computes the 30% Section 24(a)
  deduction, and leaves the assessee's Section 24(b) claim unscaled.
- Computed property leaves are returned per property and displayed read-only
  in the frontend. Builders cross-check the calculation share against the
  filing profile before emitting official JSON.
- Co-owner and tenant serials are normalized in generated JSON. The
  maximally populated audit fixture now exercises those conditional arrays,
  and no `PropertyDetails` path remains in either missing-path report.
- Canonical `HouseProperty.homeLoans` rows now map to typed Schedule 24(b)
  rows, including property sequence, lender type/name, account/reference,
  loan date, principal, outstanding balance, and interest.
- ITR-1 and ITR-4 builders serialize `Section24BDtls` and
  `TotalInterestUs24B`.
- Loan rows must cross-foot to the interest claimed for the property.
- The statutory rule that 80EE/80EEA follows exhaustion of the applicable
  Section 24(b) limit is enforced for ITR-4 as well as ITR-1.
- 80EE/80EEA rows are checked against the corresponding 24(b) loan by lender
  and account number.

### Tax credits and payments

- TDS2 preserves claimed amount, deduction year, head of income, and official
  section-code translations.
- TDS3 uses each form's official field shape and section codes.
- TCS invalid-TAN rows produce structured issues instead of disappearing.
- TCS uses section `206C`, and totals use claimed credit rather than gross tax
  collected.
- Advance-tax and self-assessment challans survive canonical mapping and are
  emitted in the form-specific official schedule.

### Salary and other sources

- Salary Section 17 components, Section 10 exemptions, net salary, and
  Section 16 deductions are preserved through the canonical mapper and shown
  in the read-only computation summary.
- Compact-form other-source detail rows preserve savings, deposit,
  income-tax-refund, provident-fund proviso, dividend, family-pension, and
  other-income categories. Other-income descriptions are retained.
- ITR-1 and ITR-4 both serialize the five statutory dividend receipt periods.

### Refund, verification, and creation metadata

- The shared bank editor captures every mandatory refund-account field.
  Frontend preflight and the filing gateway require at least one complete
  account, exactly one refund selection, valid account/IFSC formats, valid
  account types, and no duplicate IFSC/account-number pair.
- ITR-1 and ITR-4 emit all canonical bank rows with exact CBDT account codes
  and `UseForRefund` values. ITR-1 preserves the official `OTH` account code.
- Verification name, father name, PAN, capacity, and place come from the
  canonical identity and verification fields. Declaration acceptance and
  form-specific capacities are enforced before generation.
- `CreationInfo` is generated from software credentials, current date, fixed
  software metadata, and the iterative HMAC digest path. The export boundary
  rejects a placeholder digest.

### Validator corrections

- 80D totals include preventive checkups and eligible senior medical expense.
- ITR-4 Schedule 80D receives the top-level structured policy schedule, keeps
  premium, preventive-checkup, and medical-expense buckets distinct, and uses
  the schedule's senior-citizen flags for cap validation.
- ITR-1 Chapter VI-A reconciliation avoids double-counting 80CCC/80CCD(1)
  against the combined 80CCE bucket.
- ITR-4 Form 10-IA validation is conditional on a positive disability claim.
- ITR-4 TDS3 totals use the claimed field.
- Invalid ITR-4 80G gross-versus-net comparison was removed.
- ITR-4 net-tax validation now matches calculator pre-payment liability
  semantics.
- ITR-4 HRA uses 50% of salary for metro evidence and 40% for non-metro.
- ITR-4 seventh-proviso amounts must strictly exceed ₹1 crore for current
  accounts, ₹2 lakh for foreign travel, and ₹1 lakh for electricity.

### Final ITR-4 defect closure

- `DeductionUs57iia` now carries the eligible family-pension deduction, and
  family-pension source metadata is derived for validation.
- `UsrDeductUndChapVIA` now preserves taxpayer claims independently of the
  statutory eligible `DeductUndChapVIA` values.
- Schedule 80D aggregate fields now include the applicable premium,
  preventive-checkup, and senior medical-expense amounts.
- Schedule BP preserves 44AE tonnage for non-heavy vehicles and applies the
  statutory 44AD 6%/8% fallback when optional component amounts are omitted.
- Explicit canonical 80TTA claims survive draft mapping.
- TRP reimbursement uses the official 14-digit upper bound.

## Exercised end-to-end paths

| Area | ITR-1 | ITR-4 |
|---|---|---|
| Personal, filing, verification, refund bank | Yes | Yes |
| Salary and HRA | Yes | Yes |
| House property and Section 24(b) | Yes | Yes |
| Savings interest | Yes | Yes |
| 80C, 80CCC, 80D | Yes | Yes |
| 80E and 80EEA | Yes | Yes |
| 80G and 80GGC | Yes | Yes |
| 80GGA | Yes | Not available with business income |
| TDS1, TDS2, TDS3, TCS | Yes | Yes |
| Advance/self-assessment challans | Yes | Yes |
| Presumptive 44AD | N/A | Yes |
| 44ADA and 44AE | Separate gateway regressions | Yes |

## Remaining paths per audit document

There are none. The variant-union audit exercises every deduplicated
required path: ITR-1 **421/421**, ITR-4 **408/408**, with **zero** missing
and **zero** empty conditional arrays. The previously-missing conditional
branches (all four 80G categories, 80EE/80EEB, senior 80D, 80DD, 80U,
7th-proviso clause-iv, representative assessee, alternate address, TRP,
PRAN/NPS, restricted 112A, exempt-income rows, and the ITR-4 44ADA/44AE/
GSTIN-turnover/goods-vehicle Schedule BP rows) are now all covered by
dedicated variants in `audit_itr_coverage.py`. See the generated CSVs
`audit_itr1_present.csv` (421) and `audit_itr4_present.csv` (408).

### Resolved: 112A capital-gains GTI inconsistency

While wiring the restricted-112A fixture, the audit surfaced two
inconsistencies between the ITR-1 calculator and its validators (and an
ITR-4 validator comparison) that only appeared with a **positive** (sale >
cost) 112A gain. Both are now fixed, and the audit fixture exercises a
positive ₹80,000 112A gain end-to-end.

**Root cause.** The ITR-1 calculator built Gross Total Income from the
**post-exemption** taxable 112A (`cg_112a_taxable`), while
`result.capital_gains_112a` held the **pre-exemption** net gain. This
violated the CBDT schema's two distinct GTI fields:
`GrossTotIncomeIncLTCG112A` ("Gross Total Income **including** LTCG u/s
112A") and `GrossTotIncome` ("Gross Total Income **without** LTCG u/s
112A"). The annual ₹1.25L Section 112A exemption is a **special-rate-tax
reduction only** — it zeroes the 12.5% tax on a gain within the threshold —
not a GTI reduction. The full pre-exemption gain must flow into GTI.

**Fix.**
- `app/engine/calculators/itr1.py`: GTI now uses `cg_112a_income`
  (pre-exemption); the slab base subtracts the full `cg_112a_income` (the
  entire 112A gain is taxed at the special rate, which the exemption then
  zeroes). The exemption is now applied exactly once, in `cg_112a_tax`.
- `app/engine/validators/itr4/calc_rules.py` (R264): now compares
  `result.capital_gains_112a` against `cg_sched.net_income` (pre-exemption),
  not `taxable_income` (post-exemption). The ITR-4 calculator was already
  correct; only the validator compared against the wrong field.
- The 80G/80GG adjusted-GTI ceiling
  (`app/engine/schedules/deductions/__init__.py`) already subtracted the
  full `cg_112a_income` and needed no change.

**Verification.** The audit fixture now carries a positive ₹80,000 112A
gain (sale ₹1,80,000 − cost ₹1,00,000). The generated CBDT JSON confirms:
`LTCG112A.LongCap112A = 80000`, `GrossTotIncomeIncLTCG112A = 695800`
(salary + OS + full 112A), `GrossTotIncome = 615800` (excluding 112A),
special-rate tax = 0 (gain below ₹1.25L exemption). Two existing tests that
encoded the old buggy expectation
(`test_permitted_112a_gain_remains_part_of_gross_total_income`,
`test_itr1_ltcg_112a_exemption_and_slab_isolation`,
`test_tax_summary_computes_canonical_restricted_112a_rows`) were updated to
the correct statutory semantics.

### Resolved: CreationInfo must always flow from the selected ERI credentials

The ITR JSON's `CreationInfo` (`SWCreatedBy` / `JSONCreatedBy`) and the
`Digest` MUST always flow from the selected ERI credential bundle for the
active `(ERI_MODE, ERI_ENV)` pair — there is no non-ERI source for these
identity fields. The JSON builders (`app/engine/itd/itr1..4.py`) all source
`CreationInfo` and the `Digest` via `app/engine/itd/common.py`'s
`_creation_info()` / `_resolve_sw_id()` / `_compute_digest()`, which call
`app.eri.config.get_eri_credentials()`. The `SWCreatedBy` and the Digest
secret are read from the SAME `(mode, environment)` suffix, so the identity
stamped in `CreationInfo` always matches the credentials used to compute the
`Digest`.

Two silent-fallback paths that violated this invariant were removed:
- `_resolve_sw_id()` previously caught resolver exceptions and returned a
  hardcoded placeholder `"SW00000001"`, producing a JSON whose
  `SWCreatedBy` did not match the selected ERI type.
- `_compute_digest()` previously returned the schema-legal placeholder `"-"`

Both now raise `ERIConfigurationError` so generation fails loudly instead of
emitting a half-credentialed JSON. A new `ERIConfigurationError` exception
(`app/eri/config.py`) surfaces resolver failures as one consistent type, and
12 regression tests (`tests/test_eri_creation_info_invariant.py`) lock the
invariant: no placeholder SW_ID, no placeholder Digest, the SW_ID and
Digest secret always come from the same credential bundle, the Digest is
byte-identical to the reference `API_Testing/digest_generator.py`, and it
is computed over the COMPLETE ITR document (not the inner form dict). The
audit generator now `load_dotenv()`s before any builder import, so the real
Type-3 UAT credentials (`SW20014122` + 44-char Digest) flow into every
generated JSON.

The Digest computation is now consolidated into a single ERI-owned module
(`app/eri/digest.py`) per the Dual-Mode ERI Integration Plan and the SOP
"Digest_generation_ERI 2 (2).pdf" §5.3. `_compute_digest` in
`app/engine/itd/common.py` is a thin delegate to
`app.eri.digest.compute_digest`, and the Type-3 file exporter
(`serialize_itd_json`) delegates to the same canonical serializer
(`serialize_for_upload`) — so the bytes hashed are byte-identical to the
bytes uploaded. The Digest is HMAC-SHA256 iterated N times (where N is the
ERI-resolved iteration count) over the minified full document with the
Digest value set to `"-"`, then Base64-encoded — verified byte-identical
to `API_Testing/digest_generator.py` across both Type-2 UAT (1344) and
Type-3 UAT (1038) credentials.

### Completed: standalone acknowledgement downloader, audit log, UAT sanity pack

Three remaining ERI-plan gaps were closed, making the implementation fully
compliant with the letter of the Dual-Mode ERI Integration Plan (Phases
1–4 of the roadmap, excluding the operational Phase 4 ITD SW_ID enablement
and next-season Phase 6 Type-2 work):

- **§A7 — Standalone acknowledgement downloader**
  (`app/eri/type3/ack_downloader.py`): a Playwright downloader that logs in
  as the taxpayer, navigates to View Filed Returns, locates the row for a
  given ARN, and downloads the ITR-V PDF — independent of (and without
  touching) the working portal uploader in `app/filing_automation/uploader.py`.
  It reuses only the proven `app/automation/*` primitives
  (browser/auth/navigation/timing). Exposed via the new
  `POST /api/v1/filing/{client_id}/{ay}/{itr_type}/acknowledgement/fetch`
  endpoint, which persists the downloaded path on `FilingRecord` so the
  existing `GET .../acknowledgement` endpoint serves it subsequently.
- **§7.5 / §10.1 — Filing-action audit log**: a new `AuditLog` table +
  `app/services/audit_service.py` (`log_filing_action` /
  `log_filing_action_by_id`). Every filing action (generate, submit,
  upload, everify, ack) is audit-logged with
  `{user_id, client_id, ay, mode, environment, action, outcome, itd_code}`.
  No payload or PII is ever stored — only the action descriptor, a
  high-level outcome (`ok`/`error`), an optional ITD code, and a short
  non-PII status string (capped at 1000 chars as a hard PII guard). Audit
  writes are best-effort and never break the filing flow they log. The
  worker (`app/filing_automation/worker.py`) logs upload/everify outcomes
  via the id-keyed helper.
- **§A11 — UAT sanity pack** (`scripts/type3_uat_sanity.py`): generates
  CBDT-compliant ITR-1 (×2 variants) and ITR-4 (×3 variants) JSONs using
  the active Type-3 UAT credentials, each carrying the real `SW20014122`
  SW_ID + a real 44-char Digest that round-trips. Writes a manifest
  (`sanity_manifest.json`) ready to email to `erihelp@incometax.gov.in`
  for the ITD UAT sanity check (SOP §3-4, Phase 4).
- **Appendix — dead-code removal**: deleted
  `app/services/submission_service.py` (confirmed unreferenced by any live
  code), per the plan's appendix "DELETE" directive.

## Validation evidence

- Exhaustive field matrices: ITR-1 **424 Present / 149 Derived-System**;
  ITR-4 **468 Present / 168 Derived-System**; **0 Partial, Missing, or
  Incorrect**. Both synchronized CSVs match all **1,209** official schema
  paths and each other.
- Focused backend mapper, calculator, builder, gateway, and validator suites
  (draft-to-input, ITR-1/ITR-4 ITD builder, filing-gateway v2, ITR-1/ITR-4
  input + calc validation, ITR-1/ITR-4 calculator, ITR-1 filing-gateway
  profile, AY 2026-27 calculator regressions, AY 2026-27 special-tax
  hardening, boundary regression, 112A unification, standalone CG schedule):
  **555 passed**.
- Complete frontend unit suite: **160 passed**, TypeScript compilation and
  the production frontend build pass.
- Audit generator: every variant passed the official JSON schema gate;
  ITR-1 measured **421/421**, ITR-4 measured **408/408**. Zero missing,
  zero empty.
- Maintained backend `tests/`: **1300 passed, 0 failed**. The ERI Type-2
  router tests were updated to align with the Dual-Mode ERI Integration
  Plan (Phase 1 — Type-2 modules moved to `app/eri/type2/`, mode guard
  returns 503 in Type-3 mode); the additive `init_db` migration now guards
  the legacy `name`-column backfill on the column's existence; and the
  Phase 2 automation worker test was updated to match the committed
  worker's prefill-parsing behaviour (which the ERI plan explicitly
  documents as correct and unchanged). The full suite is green.
- Repository-root `pytest` collection is additionally blocked by legacy
  scripts importing removed ERI/automation modules and one file containing
  null bytes.
- Repository-wide frontend lint remains blocked by its existing baseline:
  **250 errors and 9 warnings**, dominated by legacy explicit-`any`,
  unused-variable, and React-hook diagnostics outside this audit's scope.

## Release boundaries

All audited conditional branches (the four 80G categories; 80EE and 80EEB
with matching 24(b) evidence; 80DD and 80U with Form 10-IA; 7th-proviso and
representative-assessee filing; restricted 112A; the ITR-4 44ADA/44AE/GSTIN
Schedule BP variants) now have a dedicated canonical fixture variant and
schema assertion in `audit_itr_coverage.py`. No conditional branch remains
unproven end-to-end.

The 112A capital-gains GTI inconsistency documented above is **resolved**
— the audit fixture now exercises a positive ₹80,000 listed-equity LTCG
gain end-to-end, and the generated CBDT JSON correctly reports the full
pre-exemption gain in `GrossTotIncomeIncLTCG112A` while the ₹1.25L
exemption zeroes the special-rate tax. Live filers with a positive
listed-equity LTCG are now computed correctly.

## Reproduction

```text
py audit_itr_coverage.py
py -m pytest -q tests/test_draft_to_itr1_input.py tests/test_draft_to_itr4_input_itr4.py tests/test_itr1_itd_builder.py tests/test_filing_gateway_v2.py tests/test_filing_gateway_v2_itr4.py tests/test_itr1_input_validation.py tests/test_itr4_input_validation.py tests/test_itr1_route_validation.py
cd frontend
npm test -- --run
npx tsc -b --pretty false
```

Generated evidence:

- `audit_itr1_generated.json`
- `audit_itr1_present.csv` (421)
- `audit_itr1_missing.csv` (0)
- `audit_itr1_empty.csv` (0)
- `audit_itr4_generated.json`
- `audit_itr4_present.csv` (408)
- `audit_itr4_missing.csv` (0)
- `audit_itr4_empty.csv` (0)
