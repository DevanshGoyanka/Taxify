# Taxify ITR-1 AY 2026–27 Frontend Field Audit

**Date:** 2026-09-03
**Scope:** Every field in the official CBDT ITR-1 (Sahaj) AY 2026–27 JSON schema and the
official ITR-1 PDF form, cross-referenced against the live frontend (what a taxpayer can
actually type into the product) and the backend typed schema / mapper / serializer that
consumes it. **Validators are explicitly out of scope** per instruction — this audit does not
assess `app/engine/validators/itr1/` correctness, only field presence, wiring, and whether a
captured value actually reaches the computation/JSON.

**Methodology note (binding):** No prior markdown document in this repository — including
`Docs/ITR1_ITR4_COMPLETE_PIPELINE_REFERENCE.md` and any pre-existing ITR-1 audit — was treated
as ground truth. Every claim below was verified directly against the current source: the
official JSON schema at `Reference Docs by CBDT & ITD/Official JSON Schema/ITR-1_2026_Main_V1.1 (2).json`,
`app/schemas/itr1.py`, `app/engine/draft_to_itr1_input.py`, `app/engine/itd/itr1.py`,
`app/schemas/return_draft.py`, and the live frontend component files under `frontend/src/`.

---

## 1. Executive conclusion

**ITR-1's canonical pipeline is substantially more mature than the ITR-2 pipeline audited
separately (`Docs/ITR2_FRONTEND_AND_SERIALIZATION_AUDIT_AY2026_27.md`).** Nearly every field in
the official AY 2026-27 ITR-1 JSON schema has a genuine, wired path: frontend control →
canonical `ReturnDraft` field → `draft_to_itr1_input.py` mapper → `ITR1Input` → calculator →
`app/engine/itd/itr1.py` serializer → official JSON key. The serializer is unusually
disciplined for this codebase: it cross-foots computed totals against emitted rows and
**raises `ValueError` rather than silently emitting a placeholder or a zero** when required
detail (Schedule 80C identifier rows, 80G donee address, Section 24(b) loan rows, TDS
deductor identity, etc.) is missing. This is the opposite failure mode from what the ITR-2
audit found, and it is the correct one for a filing product.

That said, the audit did find **two concrete, high-severity computational-correctness bugs**
where a backend-consumed field has **no frontend input control at all**, so the value is
silently pinned to a default that is wrong for real taxpayers in that category — not merely an
inconvenience, but a bug that changes the computed tax:

1. **Section 10(5) LTA/LTC exemption is always ₹0**, for every filer, regardless of what the
   user enters. The evidence fields shown in the UI (Actual Eligible Fare, Journeys Used,
   Domestic Travel Only) are not read by any calculation path — the field the calculator
   actually trusts (`employer.ltaExempt`) has no UI control anywhere in the product.
2. **`isGovernmentEmployee` has no UI control anywhere**, permanently `false`. This silently
   misapplies two real statutory rules for every actual government-employee taxpayer: the
   Section 16(ii) entertainment-allowance deduction (government-employees-only) and the
   Section 80CCD(2) employer-NPS deduction cap (14% for government employees vs. 10% for
   everyone else).

Beyond these two, the remaining findings are minor: one materially dead/orphaned component
with field names that don't match the canonical schema, one vestigial schema field with no
live consumer on either side, and one architecture-level (not ITR-1-specific) note about
JS-number vs. `Decimal` money handling that was already flagged in the ITR-2 audit and applies
identically here.

**Bottom line:** ITR-1 is close to production-ready for the field-coverage dimension this audit
examines. It is **not yet correct** for two real, common taxpayer situations — a taxpayer who
traveled and is entitled to LTA exemption, and an actual government/PSU employee — until the
two P0 items below are fixed. Everything else surveyed is either complete or a low-severity
cleanup item.

> **Fix status (2026-09-03): both P0 findings fixed and verified**, in
> `app/engine/draft_to_itr1_input.py::_map_salary` — the single mapper function shared by
> ITR-1, ITR-2, and ITR-4 (confirmed via grep before fixing; both forms benefit). Fixing the
> LTA finding correctly required tracing `SalaryIncome.gross_salary` end to end, which
> surfaced **two additional, more severe, previously-undocumented bugs in the exact same
> function** — both fixed alongside the two audited P0s, since they are the same root-cause
> class (salary components silently mishandled between the mapper and
> `app/engine/schedules/salary.py`) and were found while directly investigating this section:
> - `employer.lta` (LTA/LTC received), `employer.otherAllowance` ("Other Taxable Salary"), and
>   `employer.arrearSalary` (arrears/advance salary) were **never summed into gross salary at
>   all** — not merely un-exempted, genuinely absent from taxable income. Confirmed via
>   `grep -rn "\.lta\b|\.otherAllowance\b|\.arrearSalary\b" app/` returning zero hits anywhere
>   in the canonical pipeline before the fix.
> - `perquisites_value` and `profits_in_lieu_of_salary` were **double-counted**:
>   `SalaryIncome.gross_salary`'s own docstring in `app/schemas/itr1.py` documents it as the
>   Section 17(1) portion only, but the mapper was passing the already-combined
>   17(1)+17(2)+17(3) total into it, and `app/engine/schedules/salary.py:131` then added
>   17(2)/17(3) on top again. Confirmed empirically with an isolated repro before touching any
>   code (basic=500000, perquisites=50000 → computed gross of 600000 instead of the correct
>   550000), and confirmed a live test,
>   `tests/test_draft_to_itr1_input.py::test_mapper_produces_valid_itr1_input`, literally
>   asserted the double-counted figure as "expected" before the fix.
>
> See §10 for the full fix write-up, verification detail, and the ten new regression tests
> added.

---

## 2. Scope and methodology

### In scope
- Official AY 2026–27 ITR-1 JSON schema (`ITR-1_2026_Main_V1.1`), read in full.
- Official ITR-1 (Sahaj) PDF form, cross-referenced for structure.
- `app/schemas/itr1.py` — the typed compute input (`ITR1Input` and all nested schedule types).
- `app/engine/draft_to_itr1_input.py` — the canonical `ReturnDraft` → `ITR1Input` mapper.
- `app/engine/itd/itr1.py` — the official-JSON serializer (`build_itr1_json`).
- `app/schemas/return_draft.py` — the canonical frontend-facing draft schema.
- `app/engine/filing_gateway_v2.py` — the ITR-1 filing-profile adapter (`_filing_profile`).
- Every live frontend component that edits ITR-1 data: `PersonalInfoTab.tsx`,
  `EmployerEntryManager.tsx`, `HousePropertyEntryManager.tsx`, `DeductionsWorkspace.tsx` and its
  sub-managers (`Section80CManager.tsx`, `Section80DManager.tsx`, `DonationEntryManager.tsx`,
  `DeductionLoanManager.tsx`), `ScheduleOSWorkspace.tsx`, `ExemptIncomeWorkspace.tsx`,
  `CapitalGainsEntryManager.tsx` (restricted-112A path), `BankAccountManager.tsx`,
  `ITRComputationTabs.tsx` (`TDSTab`), and `ITRComputationPage.tsx`'s ITR-1 wiring.

### Explicitly out of scope
Per instruction, `app/engine/validators/itr1/` (both `input_rules.py` and any calc-validation
rules) was **not** assessed for correctness or completeness. Findings below concern field
*presence* and *wiring*, not validator coverage.

### Evidence convention
Every finding cites a repository path and, where useful, a line number or line range from the
version audited. Line numbers may drift as the repository changes; the described behavior is
what matters.

---

## 3. Architecture assessment

Unlike ITR-2, **there is exactly one live ITR-1 mapping path.** `app/engine/draft_to_itr1_input.py`
is explicitly documented as replacing two former duplicate flat-payload mappers
(`app/routers/tax.py::_compute_tax_summary_impl` and the deleted
`app/engine/filing_gateway.py::_build_itr1_input_from_flat`); both are gone or retired. There is
no ITR-1 analogue of ITR-2's `frontend/src/api/itr2Mapper.ts` — no second, partial, competing
frontend-to-backend representation was found. This single-path architecture is the single
biggest structural reason ITR-1 does not suffer from ITR-2's "field exists in the model but two
different things happen to it depending on which path is taken" class of bug.

The serializer (`app/engine/itd/itr1.py`) additionally **fails loudly**. Representative examples,
all confirmed by direct reading:
- `_property_schedule` raises `ValueError` if Section 24(b) loan rows don't cross-foot exactly
  to the claimed interest amount, or if a loan is missing lender name/account/date
  (`app/engine/itd/itr1.py:190-212`).
- `_schedule_80c` raises if a positive 80C claim has no identifier-numbered detail rows, and
  raises again if the emitted rows don't sum to the eligible amount
  (`app/engine/itd/itr1.py:846-873`).
- `_schedule_80g` raises if a donee is missing name, PAN, or address
  (`app/engine/itd/itr1.py:920-922`).
- `_tds3_from_input`/`_tds_salary_from_input`/`_tds_other_from_input`/`_tcs_from_input` each
  raise if a required identity field (tenant PAN/name, employer TAN/name, deductor name,
  collector name) is missing, rather than emitting a placeholder
  (`app/engine/itd/itr1.py:1417-1527`).

This is the correct failure mode for a filing product: an incomplete return fails to generate
JSON with an actionable error, instead of silently producing a JSON that is schema-valid but
wrong.

---

## 4. Verified complete (no field gap found)

The following areas were checked field-by-field against the official schema and found to have
a live, correctly-wired frontend control for every field the backend mapper/serializer reads.
Listed so the P0/P1 findings below are not misread as representative of the whole surface —
they are the exceptions, not the rule.

| Area | Frontend component | Backend consumer | Verdict |
|---|---|---|---|
| Identity, contact, primary + alternate address | `PersonalInfoTab.tsx` | `filing_gateway_v2.py::_filing_profile` → `ITR1FilingProfile` | Complete |
| Filing section (all 8 official codes), revised-return metadata, notice metadata, representative | `PersonalInfoTab.tsx:203-256` | same | Complete |
| Seventh proviso (foreign travel, electricity, clause-(iv) detail rows) | `PersonalInfoTab.tsx:213-231` | `filing_gateway_v2.py:556-566` → `_filing_status_itr1` | Complete — correctly restricted to nature codes `"1"`/`"2"` for ITR-1, matching the official schema's `clauseiv7provisio139iNature` enum (ITR-4 alone gets `"3"`/`"4"`) |
| Verification (capacity, place, date, declaration, representative contact) | `PersonalInfoTab.tsx:246-256` | `_verification_from_profile` | Complete |
| Tax Return Preparer | `PersonalInfoTab.tsx:257-258` | `TaxReturnPreparer` / `_tax_return_preparer` | Complete |
| Bank accounts, exactly-one-refund enforcement | `BankAccountManager.tsx` | `_bank_accounts_from_accounts` / `_bank_accounts_from_input` | Complete — the "exactly one refund" rule is enforced by construction in the UI (`BankAccountManager.tsx:61-63`), not left to the validator |
| Salary: all `SalaryIncome` scalar fields, HRA evidence, section 10(14) allowances, retirement receipts, other section-10 exemption rows | `EmployerEntryManager.tsx` | `draft_to_itr1_input.py::_map_salary` → `_allowance_rows` | Complete, **except** two fields noted in §5 |
| House property (up to 2 properties): address, ownership, co-owners, tenants, rent detail, Section 24(b) per-loan rows | `HousePropertyEntryManager.tsx` | `_map_house_property` / `_map_24b_loans` / `_property_schedule` | Complete |
| Other sources: interest by kind, dividends + quarterly breakdown, family pension, other income | `ScheduleOSWorkspace.tsx` (via `OtherSourcesTab`) | `_map_other_sources` | Complete for the ITR-1-eligible categories; correctly warns (does not silently drop) when an ITR-1-incompatible category (winnings, gifts, DTAA, 89A, PF) is populated — see §6 |
| Exempt income (Schedule EI compact form), agricultural income | `ExemptIncomeWorkspace.tsx` | `_map_compact_exempt_income` | Complete — `ITR1_SUBCATEGORIES` gating matches the official `ExemptIncAgriOthUs10Type.SubCategory` enum exactly |
| Restricted LTCG u/s 112A (ITR-1's only permitted capital-gains category) | `CapitalGainsEntryManager.tsx:219-295` | `_map_capital_gains` | Complete — correctly locks out full Schedule CG for ITR-1/ITR-4 with an explicit warning |
| Chapter VI-A: 80C (with identifier rows), 80CCC/80CCD family, 80D (4 categories, per-policy), 80DD/80DDB/80U (full disability schedule incl. Form 10-IA, UDID, dependent identity), 80G (4 categories, per-donee address+PAN), 80GGA (per-donation, full address+PAN), 80GGC (per-contribution, date+IFSC+party PAN), 80E/80EE/80EEA/80EEB (per-loan, incl. 80EEA stamp duty and 80EEB vehicle reg.), 80GG, 80TTA/80TTB, Form 10-BA ack., any-other-80CCH | `DeductionsWorkspace.tsx` + sub-managers | `draft_to_itr1_input.py::_map_deductions` and related | Complete |
| TDS on salary (Schedule TDS1), TDS on other income (Schedule TDS2, incl. spouse/other-person ownership, brought/carried-forward), TDS on non-resident transactions (Schedule TDS3, incl. tenant/buyer PAN/Aadhaar), TCS (incl. spouse/other-person split) | `ITRComputationTabs.tsx::TDSTab` | `_map_tds` / `_map_tds3` / `_map_tcs` | Complete |
| Advance tax / self-assessment tax challans (BSR code, deposit date, challan serial) | `ITRComputationTabs.tsx::TDSTab` | `_map_tax_payments` / `_tax_payments_from_input` | Complete |
| Employer category, state codes, country codes (enum completeness) | `frontend/src/domain/returns/cbdtEnums.ts` | — | Complete — `EMPLOYER_CATEGORY_OPTIONS` has all 9 official codes incl. `NA`; state/country lists match the schema enums |

---

## 5. P0 findings — real computational-correctness bugs

### 5.1 Section 10(5) LTA/LTC exemption is permanently ₹0

**Severity: Critical.** Affects any ITR-1 filer who actually traveled and is entitled to a
Leave Travel Allowance exemption — a common, not edge-case, scenario for salaried taxpayers.

**Evidence chain:**

- The calculator trusts a single pre-computed input field and does **not** derive it from
  travel evidence:
  ```python
  # app/engine/schedules/salary.py:137
  lta_exempt = input_data.lta_exempt_amount
  ```
  Contrast this with every other exemption in the same file — HRA is recomputed from raw facts
  via `compute_hra_exemption()`, and gratuity/leave-encashment/VRS/commuted-pension each go
  through dedicated `_exempt_*()` functions. LTA alone has no such function; it is a bare
  pass-through.
- `input_data.lta_exempt_amount` (`SalaryIncome.lta_exempt_amount`) is populated by the mapper
  directly from the canonical draft's raw `ltaExempt` scalar, with no computation:
  ```python
  # app/engine/draft_to_itr1_input.py:190
  lta_exempt = sum((e.ltaExempt for e in employers), Decimal("0"))
  ```
- `Employer.ltaExempt` (`app/schemas/return_draft.py:236`) defaults to `Decimal("0")` and is
  never set to anything else by any live code path:
  - `frontend/src/components/EmployerEntryManager.tsx`'s `EmployerEntry` interface declares
    `ltaExempt?: number` (line 88) — the component is *aware* of the field — but the LTA claim
    section it renders (lines 487-501, guarded by `ltaClaimed`) only exposes three inputs:
    **Actual Eligible Fare** (`entry.actualLtaFare`), **Journeys Used in Current Block**
    (`entry.journeysInBlock`), and **Domestic Travel Only** (`entry.isDomesticTravel`). None of
    these three write to `entry.ltaExempt`, and no other control in the file does either.
  - Every other place `ltaExempt` appears in the frontend is a default-initialization to `0`:
    `frontend/src/pages/ITRComputationPage.tsx:1111`, and the import-mapping utilities
    `map26asToDraftPatch.ts`, `mapAisToDraftPatch.ts`, `mapReconciledToDraftPatch.ts`,
    `mapTisToDraftPatch.ts` (all set it to `0` when constructing a fresh `Employer` row).
  - Confirmed via `grep -rn "ltaExempt" frontend/src/` (excluding tests) — the complete result
    set is the interface declaration, the four zero-initializations, and nothing else.
  - The three evidence fields that *are* editable (`actualLtaFare`, `journeysInBlock`,
    `isDomesticTravel`) are themselves never read by any backend computation path — confirmed
    via `grep -rn "actualLtaFare|journeysInBlock|isDomesticTravel" app/` — the only backend hit
    is the legacy `flat_to_draft.py` converter, which just carries the values through
    unchanged; nothing computes an exemption from them, in either the legacy `app/routers/tax.py`
    path (`app/routers/tax.py:470` shows the same bare pass-through:
    `lta_exempt = sum((_money(row.get("ltaExempt")) for row in salary_rows), ...)`) or the
    canonical pipeline.

**Net effect:** the "LTA / LTC claim — Section 10(5)" section in the UI presents three fields
that look like they establish an exemption claim, but none of them — individually or
together — ever produce a non-zero exemption. A taxpayer's full "LTA/LTC Received" amount is
taxed as if no exemption were ever claimed, in every case, for every filer.

**Remediation:** either (a) compute `lta_exempt_amount` from `actualLtaFare` capped at the
amount received and the block-of-four-years eligibility rule, mirroring the pattern already
used for HRA, or (b) if a deliberate simplification, add an explicit "LTA exempt amount"
override field the same way other sections do, and wire it through the mapper. Do not leave
the current state, where evidence fields are collected but silently discarded.

### 5.2 `isGovernmentEmployee` has no frontend control anywhere

**Severity: Critical.** Affects every actual Central/State Government or PSU employee filing
ITR-1 — a population the product explicitly supports (the `EmployerCategory` dropdown includes
`CGOV`/`SGOV`/`PSU`, confirmed in `cbdtEnums.ts:17-19`).

**Evidence chain:**

- `Employer.isGovernmentEmployee: bool` exists in the canonical schema
  (`app/schemas/return_draft.py:225`, `default=False`) and is genuinely read by the mapper:
  ```python
  # app/engine/draft_to_itr1_input.py:193
  is_govt = any(e.isGovernmentEmployee for e in employers)
  ```
  which becomes `SalaryIncome.is_government_employee`.
- This flag has **two real, confirmed computational effects**, not just a validator check:
  1. `app/engine/schedules/salary.py:130` — `is_govt = getattr(input_data, "is_government_employee", False)` gates Section 16(ii) entertainment-allowance eligibility (government-employees-only under the Income-tax Act).
  2. `app/engine/schedules/deductions/section_80ccd2.py:44-63` — the Section 80CCD(2)
     employer-NPS-contribution deduction cap is `_NPS_GOV_T_PCT` (14%, the post-Budget-2024
     rate) for government employees and a lower percentage otherwise. This directly changes a
     computed deduction amount, not just an eligibility flag.
- **No frontend component exposes a control for this field.** Confirmed via
  `grep -rn "isGovernmentEmployee" frontend/src/` (excluding tests): it appears in
  `types.ts`'s type declaration and in five separate zero-initialization sites
  (`ITRComputationPage.tsx:1108`, `map26asToDraftPatch.ts`, `mapAisToDraftPatch.ts`,
  `mapReconciledToDraftPatch.ts`, `mapTisToDraftPatch.ts`) — never in a JSX input, checkbox, or
  select. `EmployerEntryManager.tsx`'s `EmployerEntry` interface does not even declare the
  field (unlike `ltaExempt`, which is at least declared-but-unwired).
- The entertainment-allowance input field itself is present and editable in
  `EmployerEntryManager.tsx:549-551` with help text reading "Government employees only;
  capped by law" — but nothing in the UI actually distinguishes a government employee from a
  private one, so the help text's precondition can never be truthfully satisfied by the data
  reaching the calculator.

**Net effect:** every government/PSU employee using this product has their entertainment
allowance deduction and their employer-NPS deduction cap computed as if they were a private-
sector employee — a real, silent understatement of two legitimate deductions.

**Remediation:** add a control (e.g., derive it from the `EmployerCategory` selection already
captured on `PersonalInfo` — `CGOV`/`SGOV`/`PSU` clearly imply a government employer — or add
an explicit per-employer "Is this a government/PSU employer?" toggle in
`EmployerEntryManager.tsx`) and wire it to `Employer.isGovernmentEmployee`.

---

## 6. P1 / lower-severity findings

### 6.1 `BankInterestEntryManager.tsx` is dead, orphaned code with a mismatched schema

`frontend/src/components/BankInterestEntryManager.tsx` defines its own `BankInterestEntry`
shape (`bankName`, `accountType: string` with values `SAVINGS`/`FD`/`RD`/`CURRENT`,
`accountNumber`, `ifscCode`, `interestEarned`, `tdsDeducted`, `section`) that does **not**
match the canonical `InterestIncome` type (`kind: InterestKind`, `grossAmount`, plus
post-office/NSC/SCSS-specific fields — see `app/schemas/return_draft.py:870-887`). It is
imported in both `ITRComputationPage.tsx` and `ITRComputationTabs.tsx` (confirmed via
`grep -c`, one hit each — the import line itself) but **never rendered as JSX anywhere**
(confirmed via `grep -n "<BankInterestEntryManager"` — zero matches in either file). The live
interest-entry surface is `ScheduleOSWorkspace.tsx`, wired through `OtherSourcesTab`
(`ITRComputationTabs.tsx:166-182`), which does use the correct canonical shape.

This is not currently causing data loss (it's unreachable), but it is exactly the kind of
stale, schema-mismatched component the ITR-2 audit flagged as a risk class (`itr2Mapper.ts`) —
if anyone ever wires it back in, it would silently write data no backend mapper reads.
**Recommendation:** delete it, or mark it clearly deprecated/unreachable.

### 6.2 `Employer.employerNPS` is a vestigial field

`app/schemas/return_draft.py:249` declares `employerNPS: Money`, and it is read by the legacy
`app/engine/flat_to_draft.py:234` converter, but **not** by the live
`draft_to_itr1_input.py` mapper — Section 80CCD(2) (employer NPS contribution) is instead
entered as a single aggregate directly on `ChapterVIA.section80CCDEmployer` via
`DeductionsWorkspace.tsx:266`. No frontend component sets `employer.employerNPS` to a non-zero
value (confirmed: it only appears as a `0` default in the same import-mapper files as
§5.1/§5.2). Unlike the two P0 findings, nothing computationally depends on this field being
populated — it's dead schema surface, not a live bug. **Recommendation:** remove it, or
document why it's retained.

### 6.3 Retirement-benefit evidence fields (`averageMonthlySalary`, `yearsOfService`,
`unavailedLeaveDays`) are captured but not used by the current simplified exemption formulas

Distinct from §5.1: this is **not** a missing frontend field — `EmployerEntryManager.tsx:529-531`
does capture these three values, and the frontend does write them to the canonical draft. The
issue is on the calculator side: `app/engine/schedules/salary.py:74-78`'s
`_exempt_leave_encashment()` and `_exempt_gratuity()` implement only the flat statutory-ceiling
half of each exemption test (₹25L / ₹20L respectively) and do not use average-salary or
unavailed-leave-days to compute the other statutory sub-limits (10 months' average salary; cash
equivalent of unavailed leave) that the real Section 10(10AA) test also requires as a minimum.
This is a calculator-formula completeness question, not a frontend field gap — flagged here for
visibility since it was discovered while tracing the same code path as §5.1, but it is adjacent
to (not inside) this audit's field-presence scope and may already be a known, deliberate
simplification.

### 6.4 Money precision: frontend uses JavaScript `number`, backend uses `Decimal`

Structurally identical to finding §14.1 in the ITR-2 audit and not ITR-1-specific — every ITR-1
component surveyed (`EmployerEntryManager.tsx`, `HousePropertyEntryManager.tsx`,
`DeductionsWorkspace.tsx` and its sub-managers, `ScheduleOSWorkspace.tsx`, `TDSTab`) represents
monetary values as JS `number` and parses user input with `parseFloat`/`Number(...) || 0`,
while the backend schema is `Decimal` throughout per this repository's own convention (CLAUDE.md).
The backend remains authoritative for the final computed figures (the frontend never computes
tax itself), which limits the practical severity versus the ITR-2 finding, but the same risks
apply to raw entered amounts: precision loss on very large values, inability to distinguish
blank from zero in a few components, and `Number(x) || 0` silently coercing an invalid entry to
zero rather than rejecting it. Not re-scored as critical here since it's a pre-existing,
shared-architecture pattern rather than something specific to ITR-1's field coverage.

---

## 7. Fields verified present in the official schema with no frontend concern

For completeness, these official ITR-1 schema elements were checked and found to require no
taxpayer-facing input at all — they are either backend-computed/derived, or static metadata the
backend fills in without any frontend role:

- `CreationInfo` (SW version, digest, JSON creation date) — `app/engine/itd/common.py::_creation_info`.
- `Form_ITR1` (form name, description, AY, schema/form version) — `_form_itr`.
- `ITR1_TaxComputation` (slab tax, rebate 87A, cess, surcharge, interest 234A/B/C, late fee
  234F/234I) — fully backend-computed from the calculator result; no raw user input maps
  directly here.
- `TaxPaid.BalTaxPayable`, `Refund.RefundDue` — computed, rounded per Sections 288A/288B.
- `LTCG112A` — derived from the same `simplified112A` fields as §4's capital-gains row; no
  separate input.

No gap found in this category.

---

## 8. Prioritized remediation plan

### P0 — must fix before claiming ITR-1 is correct for real filers
1. **Wire Section 10(5) LTA exemption end-to-end** (§5.1). Either compute it from the existing
   evidence fields (mirroring the HRA pattern) or add an explicit exempt-amount input and read
   it in the mapper. Add a regression test asserting a nonzero `actualLtaFare`/`journeysInBlock`
   combination produces a nonzero `lta_exempt_amount` reaching `ITR1Input`.
2. **Add a UI control for `isGovernmentEmployee`** (§5.2) and confirm it changes both the
   Section 16(ii) entertainment-allowance eligibility and the Section 80CCD(2) NPS cap in an
   end-to-end test (draft → `compute_canonical_itr1` → result).

### P1 — cleanup, no known live bug
3. Delete or clearly deprecate `BankInterestEntryManager.tsx` (§6.1).
4. Remove or document `Employer.employerNPS` (§6.2).
5. Decide, as a calculator-scope follow-up (not this audit's remit), whether
   `_exempt_leave_encashment`/`_exempt_gratuity` should incorporate the average-salary and
   unavailed-leave evidence already captured (§6.3).

### P2 — architecture-level, shared with other forms
6. Consider a systematic decimal-string money representation across the frontend, as already
   noted for ITR-2 (§6.4) — not ITR-1-specific and not blocking.

---

## 9. Final assessment

Verified directly against the current codebase, not against any prior audit document: ITR-1's
canonical pipeline has one mapping path, a serializer that fails loudly rather than fabricating
data, and — with the two exceptions in §5 — genuine, complete frontend coverage of the official
AY 2026-27 schema's fields, including the less commonly implemented ones (Section 24(b)
per-loan detail, per-donee 80G address, disability-schedule Form 10-IA/UDID detail, TDS3
non-resident tenant rows, spouse/other-person TCS ownership split).

The two P0 findings are real and will produce an incorrect computed tax liability for two
identifiable, non-rare taxpayer populations (anyone with a genuine LTA claim; any actual
government/PSU employee). Until both are fixed, ITR-1 should be classified as:

**Broadly complete and structurally sound, but not yet correct for taxpayers who claim LTA
exemption or who are government/PSU employees — fix the two P0 items, verify with an
end-to-end test for each, then re-audit before calling ITR-1 production-ready.**

---

## 10. P0 fix write-up (2026-09-03)

Both P0 findings, plus two additional bugs discovered while fixing them, were resolved in a
single change to `app/engine/draft_to_itr1_input.py::_map_salary` — the one shared mapper
function ITR-1, ITR-2, and ITR-4 all call (confirmed via `grep -n "_map_salary"` across
`app/engine/draft_to_itr2_input.py` and `app/engine/draft_to_itr4_input.py` before touching
anything), so the fix benefits all three forms, not just ITR-1.

### 10.1 LTA exemption (§5.1) — fixed by computing it from evidence, not `employer.ltaExempt`

`_map_salary` now recomputes the Section 10(5) exemption per employer row as
`min(lta_received, max(0, actual_fare))`, zeroed for non-domestic travel, mirroring the
existing HRA pattern in the same function exactly. `employer.ltaExempt` is no longer read —
consistent with this codebase's own stated philosophy elsewhere in the function ("the engine
never trusts a frontend-supplied exempt amount"). No frontend change was needed: the evidence
fields (`actualLtaFare`, `isDomesticTravel`) were already live, editable UI controls in
`EmployerEntryManager.tsx` — they were simply never read by the backend before this fix.

### 10.2 `isGovernmentEmployee` (§5.2) — fixed by deriving it from `natureOfEmployment`, not a
separate unwired field

Rather than adding a new, redundant UI control (the originally-sketched fix), `_map_salary`
now derives `is_government_employee` from the `natureOfEmployment` value already required on
every employer row: `any(e.natureOfEmployment in {"CGOV", "SGOV"} for e in employers)`. This
is a materially better fix than "add a checkbox" would have been — `natureOfEmployment` is a
required field every taxpayer already fills in, so the fix applies immediately to existing
saved drafts with no re-entry needed, and there is no risk of the two fields (a hypothetical
new checkbox vs. the existing dropdown) silently disagreeing. The Central/State-only scope
(excluding PSU and the pensioner codes PE/PESG/PEPS/PEO) matches this codebase's own existing
definition in `app/engine/schedules/deductions/section_80ccd2.py`'s docstring, verified before
writing the fix — PSU employees do not get the 14% NPS cap or the Section 16(ii) deduction
under the actual Income-tax Act, so including PSU would have been a new, wrong behavior, not a
fix. `employer.isGovernmentEmployee` (the scalar field the mapper previously read) is no
longer referenced.

### 10.3 Additional bugs found and fixed in the same function (not in the original audit)

Tracing `SalaryIncome.gross_salary` to fix §5.1 correctly required understanding exactly how
gross salary is assembled, which surfaced two further, more severe bugs in the identical
code path:

- **Income omission**: `employer.lta`, `employer.otherAllowance`, and `employer.arrearSalary`
  were never summed into `section_17_1` at all (confirmed via
  `grep -rn "\.lta\b|\.otherAllowance\b|\.arrearSalary\b" app/` returning zero hits before the
  fix) — not merely un-exempted, genuinely dropped from taxable income. All three are now
  included.
- **Double-counting**: `SalaryIncome.gross_salary` was being set to the already-combined
  17(1)+17(2)+17(3) total, but `app/schemas/itr1.py`'s own field docstring documents it as the
  17(1) portion only, and `app/engine/schedules/salary.py:131` separately adds
  `perquisites_value`/`profits_in_lieu_of_salary` on top — so both were counted twice whenever
  either was nonzero. `_map_salary` now sets `SalaryIncome.gross_salary=section_17_1` (17(1)
  only), matching the schema's documented contract; the mapper's own `gross_salary` return
  value (used for the compute-response breakdown, not the schema field) still correctly holds
  the full combined total.

### 10.4 Verification

- **Regression tests**: 10 new tests added to `tests/test_draft_to_itr1_input.py` — LTA
  recomputed from evidence, capped at amount received, zeroed for foreign travel, and (with no
  exemption evidence at all) still reaching gross salary as taxable income;
  otherAllowance/arrearSalary reaching gross salary; perquisites/profits-in-lieu no longer
  double-counted; `is_government_employee` correctly derived as `True` for CGOV and `False` for
  PSU. Two pre-existing tests
  (`test_mapper_produces_valid_itr1_input`, `test_compute_runs_cleanly_on_mapped_input`) had
  their assertions corrected from the double-counted figures they previously encoded as
  "expected" to the verified-correct ones, with an explanatory comment on each.
- `pytest tests/test_draft_to_itr1_input.py -v` — 35 passed (25 pre-existing + 10 new).
- `pytest tests/ -k "itr1 or itr4"` (same pre-existing-exclusion list as prior phase notes in
  this repository) — 514 passed, no regressions.
- `pytest tests/ -k "itr2"` — 166 passed, no regressions (confirms the shared `_map_salary` fix
  did not disturb ITR-2, which is intentionally out of scope for active work right now per the
  user's own stated sequencing — ITR-1, then ITR-4, then ITR-2, then ITR-3).
- Full backend suite `pytest tests/ -q` (same exclusion list) — 1505 passed, 3 failed, 1 error;
  the 3 `test_tax_v2_compute.py` failures and the 1 `test_26as_batch.py::test_single_file`
  collection error are the identical pre-existing baseline seen throughout this session's work
  — zero new failures from this fix.
- `tests/check_schema_compliance.py` and 3 of `tests/validate_schemas.py`'s form checks fail
  both before and after this change (bank-account and CG112AScrip schema-drift issues
  unrelated to salary, confirmed via `git stash` comparison) — pre-existing, not introduced by
  this fix.
- End-to-end script verification (not part of the automated suite): built a Central Government
  employee draft with LTA received ₹30,000 / actual fare ₹22,000 / domestic travel, and an
  entertainment allowance of ₹5,000. Confirmed `gross_salary` includes the LTA received
  (1,030,000, not 1,000,000), `lta_exempt_amount` correctly resolves to ₹22,000 (the lesser of
  the two), and the entertainment-allowance deduction is correctly nonzero (₹5,000). A parallel
  PSU-employer control case confirmed `is_government_employee` resolves to `False` and the
  entertainment-allowance deduction correctly stays zero for that case.
