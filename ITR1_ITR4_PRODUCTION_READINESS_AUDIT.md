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
| Present in maximally populated audit document | 316 (75.1%) | 291 (71.3%) |
| Missing from that document | 103 | 115 |
| Present but empty conditional arrays | 2 | 2 |
| Official schema validation | Pass | Pass |

The measured figures are scenario coverage, not a statement that every
schema-required path must appear in every return. CBDT schedules are
conditional and mutually exclusive. The audit document now exercises the
principal supported conditional paths, including HRA, 80C, 80CCC, 80D, 80E,
80EEA, 80G, 80GGA where permitted, 80GGC, Section 24(b), TDS1/TDS2/TDS3,
TCS, tax challans, compact-form other-source categories, and all five
dividend receipt periods.

The exhaustive field matrices contain no unresolved implementation statuses:

| Matrix classification | ITR-1 | ITR-4 |
|---|---:|---:|
| Present | 424 | 468 |
| Derived-System | 149 | 168 |
| Partial / Missing / Incorrect | 0 | 0 |
| Total schema paths | 573 | 636 |

**Verdict:** ITR-1 and ITR-4 are production-ready for the implemented AY
2026-27 scope. Every official schema path is classified as either a persisted
taxpayer input or a system-derived structural, statutory, or aggregate value.
Both forms generate schema-valid official JSON, and the canonical data-loss
and calculation defects found in this audit are fixed. Conditional paths that
are absent from the maximal audit fixture have targeted gateway regressions;
the scenario-coverage figures above should not be read as unresolved matrix
coverage.

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

These are listed exactly in `audit_itr1_missing.csv` and
`audit_itr4_missing.csv`.

### ITR-1

| Group | Paths | Reason |
|---|---:|---|
| Schedule 80G alternate categories | 48 | Fixture exercises one of four mutually exclusive donation categories |
| Schedule 80EEB | 11 | No EV-loan claim in audit scenario |
| Schedule 80EE | 10 | No 80EE claim in audit scenario |
| Schedule 80D alternate senior buckets | 8 | Fixture exercises non-senior policy buckets |
| Filing status | 7 | Seventh-proviso and representative-assessment details |
| Personal information | 4 | Alternate/secondary contact variants omitted from the scenario |
| Schedule 80DD | 4 | No dependent-disability claim in audit scenario |
| Schedule 80U | 3 | No self-disability claim in audit scenario |
| Income deductions | 3 | Conditional other-source/exempt-income variants omitted |
| LTCG 112A | 3 | No listed-equity gain in audit scenario |
| Tax return preparer | 2 | No TRP in audit scenario |

### ITR-4

| Group | Paths | Reason |
|---|---:|---|
| Schedule 80G alternate categories | 42 | Fixture exercises one donation category |
| Schedule BP variants | 18 | 44ADA/44AE and GSTIN variants are exercised in separate tests, not the 44AD audit document |
| Schedule 80EEB | 11 | No EV-loan claim in audit scenario |
| Schedule 80EE | 10 | No 80EE claim in audit scenario |
| Schedule 80D alternate senior buckets | 8 | Fixture exercises non-senior policy buckets |
| Filing status | 7 | Seventh-proviso and representative-assessment details |
| Personal information | 4 | Alternate/secondary contact variants omitted from the scenario |
| Schedule 80DD | 4 | No dependent-disability claim in audit scenario |
| Schedule 80U | 3 | No self-disability claim in audit scenario |
| LTCG 112A | 3 | No listed-equity gain in audit scenario |
| Exempt-income details | 2 | No matching exempt-income row in audit scenario |
| Tax return preparer | 2 | No TRP in audit scenario |
| Income deductions | 1 | Conditional income variant omitted |

The two “present but empty” paths in each form are the inactive senior-citizen
80D policy-detail arrays. Empty arrays are valid for those conditional buckets,
and both generated documents pass the official schema gate.

## Validation evidence

- Exhaustive field matrices: ITR-1 **424 Present / 149 Derived-System**;
  ITR-4 **468 Present / 168 Derived-System**; **0 Partial, Missing, or
  Incorrect**. Both synchronized CSVs match all **1,209** official schema
  paths and each other.
- Focused backend mapper, calculator, builder, gateway, and validator suites:
  **369 passed**. Additional focused ITR-4 account/schema validation:
  **175 passed** after the final ITR-4 defect closure.
- Complete frontend unit suite: **156 passed**, including **12** focused
  preflight tests.
- Available schema and golden suites: **35 passed**.
- Audit generator: both documents passed their official JSON schema gates;
  ITR-1 measured **316/421**, ITR-4 measured **291/408**. Each had two valid
  empty arrays in inactive conditional Schedule 80D buckets.
- Maintained backend `tests/`: **1271 passed, 10 failed**. The failures are
  existing unrelated automation/ERI issues: two automation migration/worker
  expectations and eight ERI router tests against unavailable legacy exports.
- Repository-root `pytest` collection is additionally blocked by legacy
  scripts importing removed ERI/automation modules and one file containing
  null bytes.
- Complete frontend unit suite: **160 passed**. TypeScript compilation and the
  production frontend build pass.
- Repository-wide frontend lint remains blocked by its existing baseline:
  **250 errors and 9 warnings**, dominated by legacy explicit-`any`,
  unused-variable, and React-hook diagnostics outside this audit's scope.

## Release boundaries

Do not present untested conditional branches as generally supported merely
because their schema paths exist. Before enabling each remaining branch for
all users, add a dedicated canonical fixture, gateway regression, and schema
assertion. Highest-value next fixtures are:

1. all four Schedule 80G categories,
2. 80EE and 80EEB with matching 24(b) evidence,
3. 80DD and 80U with Form 10-IA,
4. add seventh-proviso and representative assessee branches to the maximal
   audit fixture,
5. restricted 112A.

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
- `audit_itr1_present.csv` (192)
- `audit_itr1_missing.csv` (55)
- `audit_itr1_empty.csv` (0)
- `audit_itr4_generated.json`
- `audit_itr4_present.csv` (182)
- `audit_itr4_missing.csv` (54)
- `audit_itr4_empty.csv` (0)
