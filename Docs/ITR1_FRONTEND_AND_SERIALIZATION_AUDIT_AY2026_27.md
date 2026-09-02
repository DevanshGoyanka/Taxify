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

> **Update (2026-09-03): the LTA fix's own investigation led to a full schedule-by-schedule
> re-audit (§11), which found this executive summary's "beyond these two, the remaining
> findings are minor" framing was wrong.** Tracing why §6.3's gratuity/leave-encashment
> sub-limit formulas were incomplete revealed the inputs those formulas needed
> (`gratuity_received`, `leave_encashment_received`, and four more fields) were never mapped
> at all — the same shape of bug as the two P0s above, just for six more retirement/exemption
> categories, some involving large one-time payouts. That re-audit (§11), its fixes (§12), and
> a further pass closing every remaining open item including money-input parsing (§13) are all
> now complete and verified. **§9's "Final assessment" and §8's remediation plan below are
> updated accordingly — read those two sections for the current bottom line, not the
> paragraphs immediately above, which describe this audit's state as of its first pass only.**

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

### 6.1 `BankInterestEntryManager.tsx` is dead, orphaned code with a mismatched schema — **Fixed (2026-09-03)**

**Fix:** deleted `frontend/src/components/BankInterestEntryManager.tsx` outright (confirmed
zero JSX render sites before deletion, per the original finding), and removed its now-dangling
imports from `ITRComputationPage.tsx` and `ITRComputationTabs.tsx`. The live interest-entry
surface (`ScheduleOSWorkspace.tsx` via `OtherSourcesTab`) is untouched. Verified: `npx tsc -b`,
`npx vitest run` (185 passed), and `npm run build` all clean.

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

### 6.2 `Employer.employerNPS` is a vestigial field — **Fixed (2026-09-03)**

**Fix:** removed `employerNPS` from the `Employer` schema (`app/schemas/return_draft.py`) and
every place that set or read it — the legacy `flat_to_draft.py` converter, the TS `Employer`
type, all frontend default-Employer-construction sites (`ITRComputationPage.tsx`,
`map26asToDraftPatch.ts`, `mapAisToDraftPatch.ts`, `mapReconciledToDraftPatch.ts`,
`mapTisToDraftPatch.ts`), and the corresponding test fixtures.

Because `Employer` is a `_StrictModel` (`extra="forbid"`), and `employerNPS` was always
serialized (defaulting to `0`), removing the field would break loading of any previously-saved
draft whose stored JSON still carries the old key. Rather than risk that, a migration step was
added: `_migrate_employer_nps()` strips `employerNPS` from every stored employer row before
`ReturnDraft.model_validate()`. This was folded into a single shared entry point,
`migrate_stored_draft_payload()` (moved from a `client_itr_v2.py`-local helper to
`app/schemas/return_draft.py`), alongside the pre-existing `otherClauseIVDetail` migration.

That consolidation surfaced a real, previously-undiscovered gap: the old migration helper was
only called from the 3 `client_itr_v2.py` sites — `app/engine/filing_orchestrator.py` (the
Type-3 export/filing path) and `app/routers/client_itr.py` (the legacy router's stored-draft
fallback) both validate stored payloads too, and neither had migration applied. Both now call
`migrate_stored_draft_payload()` as well, so the pre-existing `otherClauseIVDetail` migration's
coverage gap is also closed, not just the new `employerNPS` one.

Verified: full backend suite scoped to `itr1`/`client_itr`/`filing_gateway`/`return_draft`/
`flat_to_draft` (400 passed), plus `npx tsc -b`, `npx vitest run` (185 passed), and
`npm run build`, all clean.

`app/schemas/return_draft.py:249` declares `employerNPS: Money`, and it is read by the legacy
`app/engine/flat_to_draft.py:234` converter, but **not** by the live
`draft_to_itr1_input.py` mapper — Section 80CCD(2) (employer NPS contribution) is instead
entered as a single aggregate directly on `ChapterVIA.section80CCDEmployer` via
`DeductionsWorkspace.tsx:266`. No frontend component sets `employer.employerNPS` to a non-zero
value (confirmed: it only appears as a `0` default in the same import-mapper files as
§5.1/§5.2). Unlike the two P0 findings, nothing computationally depends on this field being
populated — it's dead schema surface, not a live bug.

### 6.3 Retirement-benefit evidence fields (`averageMonthlySalary`, `yearsOfService`,
`unavailedLeaveDays`) are captured but not used by the current simplified exemption formulas —
**Fixed (2026-09-03), superseded by §11.8/§12** (see also §11.1-§11.7 for the much larger bug
this finding led to)

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

### 6.4 Money input parsing: `Number(x) || 0` silently coerces invalid entries to zero — not a
decimal/paise precision problem — **Fixed (2026-09-03), see §13**

**Correction (2026-09-03):** this finding was originally written as "frontend uses JS `number`,
backend uses `Decimal`," implying the fix was a decimal-string state migration to preserve paise
precision, mirroring finding §14.1 in the ITR-2 audit. That framing is wrong for ITR-1 and was
corrected after directly checking the official schema rather than assuming CBDT wire-format
semantics: **every monetary field in the official AY 2026-27 ITR-1 JSON schema is
`"type": "integer"`.** Confirmed by walking the entire schema tree programmatically — the only
two `"type": "number"` (fractional) fields anywhere in it are `PropertyDetails.AsseseeShareProperty`
and `CoOwners.PercentShareProperty`, both ownership-*percentage* fields (`multipleOf: 0.01`), not
currency. `app/engine/itd/common.py::_to_rupees()` already enforces this at the JSON boundary —
it returns a Python `int`, half-up rounded to the nearest whole rupee — so no monetary figure this
product emits ever carries paise. JS `Number` exactly represents every integer up to 2^53
(~9×10¹⁵), and CBDT's own field cap is `99999999999999` (~10¹⁴) — well inside that range. As long
as a money field only ever stores whole numbers, there is **no floating-point precision-loss
risk at all**; a decimal-string migration would be solving a problem that does not exist here.

The real (much narrower) issue is `Number(x) || 0` / `parseFloat(x) || 0` on entry: this pattern,
found across `EmployerEntryManager.tsx`, `DeductionsWorkspace.tsx` and its sub-managers,
`ScheduleOSWorkspace.tsx`, and `ITRComputationTabs.tsx::TDSTab`, silently coerces a garbled or
non-numeric entry to `0` rather than rejecting it or flagging it. Some money inputs already do
the right thing — `HousePropertyEntryManager.tsx`'s `Money()` helper already uses `step="1"`
integer semantics. The fix is to standardize every money input on one shared component using an
integer parser (`Math.round(Number(raw))`, rejecting non-finite/negative results instead of
defaulting to `0`) rather than each component's own ad hoc `parseFloat`/`Number` call — a small,
low-risk, mechanical consolidation, not an architecture change.

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

**Status (2026-09-03): every item below is fixed.** Left in its original form as the historical
record of what was found and prioritized; see §10/§12/§13 for what actually shipped for each
line (in a few cases — item 1's exemption-from-evidence approach, item 3's outright deletion
rather than deprecation — the shipped fix took the first option listed, not a blend).

### P0 — must fix before claiming ITR-1 is correct for real filers
1. **Wire Section 10(5) LTA exemption end-to-end** (§5.1). Either compute it from the existing
   evidence fields (mirroring the HRA pattern) or add an explicit exempt-amount input and read
   it in the mapper. Add a regression test asserting a nonzero `actualLtaFare`/`journeysInBlock`
   combination produces a nonzero `lta_exempt_amount` reaching `ITR1Input`. — **Fixed, §10.1.**
2. **Add a UI control for `isGovernmentEmployee`** (§5.2) and confirm it changes both the
   Section 16(ii) entertainment-allowance eligibility and the Section 80CCD(2) NPS cap in an
   end-to-end test (draft → `compute_canonical_itr1` → result). — **Fixed, §10.2.**

### P1 — cleanup, no known live bug
3. Delete or clearly deprecate `BankInterestEntryManager.tsx` (§6.1). — **Fixed (deleted), §6.1.**
4. Remove or document `Employer.employerNPS` (§6.2). — **Fixed (removed, with a stored-payload
   migration), §6.2.**
5. Decide, as a calculator-scope follow-up (not this audit's remit), whether
   `_exempt_leave_encashment`/`_exempt_gratuity` should incorporate the average-salary and
   unavailed-leave evidence already captured (§6.3). — **Fixed, §12.2** — and this specific
   question turned out to be entry point into the much larger §11 re-audit, not a standalone
   item.

### P2 — architecture-level, shared with other forms
6. Consolidate money-field parsing onto one shared component using integer-rupee semantics
   (§6.4) — **not** a decimal-string migration; CBDT's own wire format is integer rupees
   throughout, confirmed against the official schema. The fix is standardizing away from
   `Number(x) || 0`/`parseFloat(x) || 0`'s silent-zero-coercion, not preserving paise precision.
   — **Fixed, §13.1** (a suitable shared component, `IndianNumberInput`, already existed and
   only needed adoption).

### P3 — found during §11's re-audit and §13's verification, not in the original six items above
7. Six retirement/severance payout categories, transport/CEA/hostel allowances, the disabled-
   employee exemption, three Section 10(6)/10(7)/10(10CC) rows, `lta_amount_received`, and
   `standard_deduction_claimed` (§11.1-§11.6) — **Fixed, §12.**
8. The ITD JSON's `10(10B)(i)` row using the raw instead of capped retrenchment amount (§11.7)
   — **Fixed, §12.2.**
9. `uniformAllowance` reaching income, `gratuityAlsoReceived` affecting the commuted-pension
   fraction, the 80DDB reimbursement gap, and four vestigial `Employer` fields (§11.9's
   follow-ups) — **Fixed, §13.2.**

---

## 9. Final assessment

**Superseded (2026-09-03) — this section originally described the state after only the two P0
findings of §5 were known.** §11's re-audit found the actual defect surface was considerably
larger (§11.1-§11.9), all now fixed (§12, §13). The assessment below reflects the state after
all of it.

Verified directly against the current codebase, not against any prior audit document or this
document's own earlier drafts: ITR-1's canonical pipeline has one mapping path, a serializer
that fails loudly rather than fabricating data, and — with the exceptions found and fixed in
§5 and §11 — genuine, complete frontend coverage of the official AY 2026-27 schema's fields,
including the less commonly implemented ones (Section 24(b) per-loan detail, per-donee 80G
address, disability-schedule Form 10-IA/UDID detail, TDS3 non-resident tenant rows,
spouse/other-person TCS ownership split).

Every P0/P1 finding this audit surfaced across §5 and §11 is fixed and verified (§10, §12,
§13): the Section 10(5) LTA exemption, the government-employee derivation, six retirement/
severance payout categories that previously never reached computed income, transport/CEA/
hostel allowances, the disabled-employee exemption, three Section 10(6)/10(7)/10(10CC)
exemption rows, the real Section 10(10)/10(10AA) statutory sub-limit formulas, the commuted-
pension gratuity-also-received fraction, uniform allowance, 80DDB reimbursement, money-input
parsing, and every live filing-blocking validator regression these fixes exposed along the way
(§12.4). What remains, precisely, and why it is **not** covered by this "fixed" claim:

- **Validators beyond the specific regressions this work caused were never audited.** This
  audit's own scope statement (§2) excludes `app/engine/validators/itr1/` from review. Every
  validator bug actually found and fixed here (ITR1-R100/R101/R102/R142, the `lta_amount_received`
  cross-check) was found *reactively* — by populating a field that had always been `0` and
  discovering a dormant rule fire — not by a systematic pass over the ~2,800-line validator
  file. Other rules with the same "written against a field nothing ever populated" latent-bug
  shape may exist unfound in areas this work never touched (House Property, Other Sources,
  Capital Gains, Chapter VI-A validators specifically).
- **House Property, Other Sources, Capital Gains (112A), and Chapter VI-A got a lighter-touch
  check than Salary.** §11's AST cross-reference script (declared-field vs. constructor-kwarg)
  found zero unset-but-read fields in any of them, and a manual `getattr(..., default)`
  phantom-field sweep across every schedule module found nothing outside `salary.py`. Neither
  check would have caught the *other* bug shapes found in Salary purely by chance during this
  work: a real input parameter silently hardcoded to a constant regardless of what's passed in
  (§11.2's `num_children=0`), or a statutory sub-formula the calculator simply never
  implements (§11.8's average-salary/unavailed-leave sub-limits). Those schedules were not
  read function-by-function hunting for either pattern the way Salary was.
- **Filing-profile/verification/bank-account/TDS-TCS structural correctness** was checked in §4
  as field-*presence* completeness (every schema field has a frontend control), which is a
  different, shallower claim than "the data that reaches the calculator through this path is
  correct" — the depth applied to Salary in §11.
- **ITR-2 and ITR-4** share the fixed `_map_salary`/`schedules/salary.py` code and therefore
  inherit every fix in this document, but their own non-shared mapper code was not reviewed as
  part of this ITR-1-scoped audit.

**Bottom line:** every finding this audit actually looked for and found is fixed, tested, and
documented. That is a materially stronger position than before this work started, but it is
not the same claim as "every field, formula, and validator in ITR-1 is correct" — the salary
schedule specifically earned that level of scrutiny; the rest earned presence-and-wiring
verification, which is the level the original audit's own methodology (§2) set out to check.

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

---

## 11. Full schedule-by-schedule re-audit (2026-09-03): mapper-level income/exemption omissions

**Trigger:** while implementing §6.3 (originally scoped as "the leave-encashment/gratuity
exemption formulas are missing a sub-limit"), tracing `_exempt_gratuity()`/
`_exempt_leave_encashment()`'s inputs upward revealed that `gratuity_received` and
`leave_encashment_received` are never set by any mapper anywhere in the codebase — the
finding was not "formula incomplete," it was "the input never arrives." That is the exact
shape of bug §5.1 (LTA) already fixed, so the user asked for a full re-audit of every ITR-1
schedule for the same pattern before implementing anything, not just the two fields §6.3
originally named.

**Method:** a script (`ast`-parsed, not text-matched) extracted every field declared on every
Pydantic model in `app/schemas/itr1.py`, then cross-referenced each field against every keyword
argument actually passed when that model is constructed in `app/engine/draft_to_itr1_input.py`
— the ITR-1 mapper is the *only* place any of these models are constructed (verified by
`grep -rn "SalaryIncome(\|OtherSourcesIncome(\|HousePropertyIncome(\|CapitalGainsIncome(\|Chapter6ADeductions("`
across `app/engine/`). Every field the script flagged as "declared but never assigned" was then
checked by hand for two things: (1) is it genuinely read downstream (calculator, schedule
module, ITD JSON builder, or a validator) — a flagged-but-never-read field is dead schema
surface, not a bug; (2) does the frontend actually capture the data that would populate it — a
field with no frontend source isn't a mapper-omission bug, it's a (much lower-severity)
missing-input gap. Every finding below cites the exact grep/read evidence for both checks; nothing
here is inferred from the script's output alone.

### 11.1 Six retirement/severance payout categories are captured on the frontend, typed on the
schema, read by the calculator and the ITD JSON builder — and completely absent from the mapper

`EmployerEntryManager.tsx:524-528` has a live, rendered input for each of: Commuted Pension,
Gratuity, Leave Encashment, VRS Compensation, Retrenchment Compensation
(`frontend/src/components/EmployerEntryManager.tsx:524-528` — confirmed these are real
`<AmountInput>` JSX, not dead code, unlike §6.1's deleted component). The frontend even computes
its own "gross including these" total for on-screen display
(`EmployerEntryManager.tsx:380-381`: `profitsInLieu + commutedPension + gratuity +
leaveEncashment + vrsCompensation + retrenchmentCompensation`). Each has a corresponding
`SalaryIncome` field (`gratuity_received`, `commuted_pension_received`,
`leave_encashment_received`, `vrs_compensation`, `retrenchment_compensation` —
`app/schemas/itr1.py:231-235`), and each is genuinely read: by `app/engine/schedules/salary.py`
(`_exempt_gratuity`, `_exempt_leave_encashment`, `_exempt_commutted_pension`, `_exempt_vrs`
applied to both `vrs_compensation` and `retrenchment_compensation`), and by
`app/engine/itd/itr1.py:1300-1318`'s `_allowance_rows()`, which builds the official Schedule S
`10(10)`/`10(10A)`/`10(10AA)`/`10(10B)(i)`/`10(10C)` exemption rows directly from them.

`app/engine/draft_to_itr1_input.py::_map_salary` never reads `e.gratuity`, `e.commutedPension`,
`e.leaveEncashment`, `e.vrsCompensation`, or `e.retrenchmentCompensation` for any employer row
(confirmed: zero hits for any of those five attribute names anywhere in the file before this
audit). Every one of these fields reaches `SalaryIncome` as its schema default of `Decimal("0")`.

This is more severe than a missing-exemption bug. `app/engine/schedules/salary.py:131`'s
`gross = input_data.gross_salary + input_data.perquisites_value +
input_data.profits_in_lieu_of_salary` never independently adds these five received amounts —
the design (correctly) expects the *exempt* portion to be subtracted from an already-inclusive
gross, not for the received amount to be added and then partially exempted. Since the mapper
never puts any of these amounts into `gross_salary`/17(1) either, **the taxable (non-exempt)
residual of a real gratuity, leave-encashment, commuted-pension, VRS, or retrenchment payout
never enters computed income at all** — not merely under-exempted, but entirely invisible to
the calculator. These are frequently large, one-time amounts (retirement/severance payouts),
making this the most severe correctness gap found in this audit, ITR-1 P0 findings included.

### 11.2 Transport allowance and the two Section 10(14) child-related allowances: same
omission, plus a second, independent bug even after the omission is fixed

`employer.transportAllowance`, `employer.childrenEducationAllowance`,
`employer.hostelExpenditureAllowance` are captured (`EmployerEntryManager.tsx:505-507`) and have
corresponding `SalaryIncome` fields (`transport_allowance`, `sec10_14i_prescribed_allowance`,
`sec10_14ii_personal_allowance`), each read by `salary.py`'s `_exempt_transport`/
`_exempt_children_education`/`_exempt_hostel` — but, like §11.1, never mapped
(`_map_salary` has zero references to any of the three `Employer` attribute names).

Even fixing that mapping is not sufficient on its own for the two child-allowance exemptions:
`app/engine/schedules/salary.py:155-158` calls
`_exempt_children_education(input_data.sec10_14i_prescribed_allowance, 0)` and
`_exempt_hostel(input_data.sec10_14ii_personal_allowance, 0)` with the child-count parameter
**hardcoded to `0`**, with a comment acknowledging it: *"the schema does not yet have a
dedicated field, so default to 0 children."* Since both exemption formulas are
`min(allowance, per_child_statutory_rate * 12 * num_children)`, a hardcoded `num_children=0`
caps the statutory limit at ₹0 regardless of the allowance amount — these two exemptions are
**structurally zero no matter what the mapper passes**, until `salary.py` itself is changed to
accept a real child count. `employer.numberOfChildren` is captured on the frontend
(`EmployerEntryManager.tsx:510`) and has nowhere to go — `SalaryIncome` has no field for it.

### 11.3 `is_disabled_employee` is read by the calculator but was never a declared schema field

`app/engine/schedules/salary.py:150` calls
`getattr(input_data, "is_disabled_employee", False)` — a defensive-`getattr` pattern that,
per this codebase's own established convention (compare the already-fixed
`is_government_employee`/`agriculture_income`, which *are* declared fields where `getattr` is
purely stylistic), signals an attribute that may not exist. Confirmed by grep: `SalaryIncome`
in `app/schemas/itr1.py` has **no `is_disabled_employee` field at all**. The `getattr` default
therefore always returns `False`, permanently disabling the ₹19,200 disabled-employee transport
allowance exemption (Section 10(14), Rule 2BB) regardless of input. `employer.isDisabledEmployee`
is captured on the frontend (`EmployerEntryManager.tsx:513`) with a real Y/N control — the data
exists, there is simply no schema field to carry it to the calculator. (This is a different,
more fundamental gap than §11.2: adding the mapping alone cannot fix it — the schema itself
needs the field first.)

### 11.4 Three more Section 10 exemption categories, captured via a real dropdown+amount UI,
never read by the mapper at all

Distinct from the scalar per-category fields above: `EmployerEntryManager.tsx` has a live
`Section10Rows` sub-component (`EmployerEntryManager.tsx:203-238`, rendered at line 545) letting
a taxpayer add rows tagged `10(6)` (foreign diplomatic remuneration), `10(7)` (government
service outside India), or `10(10CC)` (employer-paid tax on a non-monetary perquisite), each
with an amount. These are stored on `employer.section10ExemptionRows`
(`app/schemas/return_draft.py:210`) and have corresponding `SalaryIncome` fields
(`sec10_6_embassy_exempt`, `sec10_7_foreign_allowance`, `sec10_10cc_perquisite_tax`), each read
by both `salary.py`'s `exempt_allowances` sum and `itd/itr1.py:1311-1312,1318`'s JSON row
builder. `_map_salary` never reads `e.section10ExemptionRows` at all (zero hits) — these three
exemption categories are dropped identically to §11.1/§11.2, just via a structured-row input
rather than a flat scalar.

By contrast, `employer.salaryNatureRows` and `employer.perquisiteNatureRows` — two structurally
similar per-employer row lists — are genuinely **not** a bug: confirmed via
`grep -rn "salaryNatureRows|perquisiteNatureRows" frontend/src/` that every occurrence outside
type declarations and test fixtures is a `[]` default (26AS/AIS/TIS/reconciled importers, and
the manual-entry default-Employer object) — unlike `section10ExemptionRows`, no live UI
component ever renders or writes a non-empty row into either list. They are vestigial schema
surface, the same class of issue as the already-fixed `employerNPS` (§6.2), not a live bug.

### 11.5 `lta_amount_received` — never mapped, and now a live regression from the §5.1 P0 fix

`SalaryIncome.lta_amount_received` (`app/schemas/itr1.py:237`) is a field distinct from
`lta_exempt_amount` — it exists specifically so `app/engine/validators/itr1/input_rules.py:306-320`
can cross-check the claimed exemption against the amount actually received:

```python
if sal.lta_amount_received > _z and sal.lta_exempt_amount == _z:
    ... # "LTA received but exempt amount is 0"
if sal.lta_exempt_amount > sal.lta_amount_received:
    ... # "exempt amount cannot be more than LTA received"
```

Both are `Severity.A` rules (`app/engine/validators/base.py:17`: *"Return WILL NOT be allowed
to upload"* — a hard filing block, not a warning). `lta_amount_received` is never set by
`_map_salary` and stays at its schema default of `0`. Before the §5.1 fix, this was harmless by
coincidence: `lta_exempt_amount` was also always `0`, so `0 > 0` never fired. **After the §5.1
fix (this session, commit `3ae3c47`), `lta_exempt_amount` is correctly computed as nonzero for
any real LTA claim — which means the second rule (`lta_exempt_amount > lta_amount_received`,
i.e. `nonzero > 0`) now fires for every genuine LTA claimant, hard-blocking their filing with
"exempt amount cannot be more than LTA received."** This is a live, currently-shipped
regression, not a latent one — it needs to be closed in the same change that finishes wiring
the mapper, not deferred with the rest of §11's lower-severity items.

### 11.6 `standard_deduction_claimed` — never mapped, produces a universal false warning

`SalaryIncome.standard_deduction_claimed` is never set by `_map_salary`. The engine does not
need it for computation — `salary.py`'s `compute()` derives the standard deduction itself
(`std_ded = min(OLD_REGIME_STANDARD_DEDUCTION, ...)`) and never reads
`input_data.standard_deduction_claimed`. But `input_rules.py:2776-2783`'s Rule `ITR1-B004`
(`Severity.B`, non-blocking) fires whenever `gross_salary > 0 and standard_deduction_claimed ==
0` — which, since the field is never populated, is **every salaried ITR-1 return, unconditionally**,
producing "Did you mean to claim the standard deduction?" on every filing regardless of whether
the deduction was in fact correctly auto-applied. Lower severity than §11.1-§11.5 (non-blocking,
cosmetic), but free to fix alongside them since the mapper already computes the regime-
appropriate statutory cap it should report here.

### 11.7 Secondary bug found while tracing §11.1: the ITD JSON's `10(10B)(i)` row uses the raw
received amount, not the capped exempt amount

`app/engine/schedules/salary.py`'s `SalaryResult` dataclass has a `vrs_exempt` field but **no
`retrenchment_exempt` field**, even though `compute()` does calculate
`retrenchment_exempt = _exempt_vrs(input_data.retrenchment_compensation)` (line 147) — a real
Rs 5-lakh-capped value — and folds it correctly into `exempt_allowances` (so the *aggregate* tax
computation is right). It is simply never exposed on the result object. Consequently
`app/engine/itd/itr1.py:1316` falls back to the raw, uncapped
`salary.retrenchment_compensation` for the official `10(10B)(i)` JSON row instead of the capped
exempt amount every other row in the same table uses (compare line 1313's `gratuity_exempt`,
line 1317's `vrs_exempt` — both pulled from `sal_sched`, not the raw input). For any retrenchment
compensation exceeding ₹5,00,000, the emitted JSON would overstate the Section 10(10B)(i)
exemption row even though the computed tax liability behind it is correct — a JSON-consistency
bug, not a tax-liability bug, but still a mismatch CBDT/ITD validation could reasonably reject.

### 11.8 §6.3's original finding, now understood in full context

The three fields §6.3 originally named — `averageMonthlySalary`, `yearsOfService`,
`unavailedLeaveDays` — are captured on the frontend (`EmployerEntryManager.tsx:529-531`) but,
unlike every field above, **`SalaryIncome` has no corresponding fields for them at all** — they
would need to be added, not just wired. They are the inputs the real Section 10(10)/10(10AA)
statutory tests need beyond the flat ceiling `_exempt_gratuity()`/`_exempt_leave_encashment()`
currently apply (10 months'/completed-years'-of-service average-salary sub-limits; the cash
equivalent of unavailed leave, capped at 30 days per completed year of service). This finding
stands as originally scoped — it is the reason the deeper audit above happened, not superseded
by it — but is now understood as one piece of a much larger, connected cluster: fixing it in
isolation (adding the two sub-limit formulas) would have been pointless while
`gratuity_received`/`leave_encashment_received` themselves never reached the calculator (§11.1).

### 11.9 Verified clean, or correctly out of scope — checked and ruled out, not merely unchecked

- **`HousePropertyIncome`** — every declared field is set by `_map_house_property`/
  `_map_house_properties`; the cross-reference script found zero unset fields. No `getattr`-
  with-default pattern in `app/engine/schedules/house_property.py` (checked directly — the only
  place such a pattern would hide a phantom field the way §11.3 did for salary).
- **`OtherSourcesIncome.income_56_2_x` / `.income_56_2_vib`** (Section 56(2)(x)/(vib) — gifts and
  under-value property transfers) — flagged by the script, but correctly unset: ITR-1 has no
  gift-income path at all. `_map_other_sources` explicitly rejects any `draft.otherSources.gifts`
  entry for ITR-1/ITR-4 with `DraftMappingError("... taxable gifts are outside ITR-1/ITR-4")`
  (`app/engine/draft_to_itr1_input.py`, in `_map_other_sources`) — these two fields are
  structurally inapplicable to ITR-1, not an omission.
- **`CapitalGainsIncome.transactions`** — flagged by the script, but it is a legitimate optional
  alternate input path (canonical transaction-evidence rows), populated by
  `_map_capital_gains` precisely when such evidence exists; not a gap.
- **`Chapter6ADeductions.amount_80ia`/`.amount_80ib`/`.amount_80ic`/`.amount_10aa`/`.amount_80ra`**
  — flagged by the script, but each field's own docstring says "ITR-3 only" / "SEZ units, ITR-3
  only"; genuinely inapplicable to ITR-1.
- **`Chapter6ADeductions.schedule_80dd` / `.schedule_80u`** — flagged by the script as unset
  *on the nested `Chapter6ADeductions` construction call* — a false positive. Both are correctly
  populated as **top-level `ITR1Input` fields** instead
  (`app/engine/draft_to_itr1_input.py:1288-1289`, sourced from `_map_disability_schedules`), and
  consumed via `ITR1Input.disability_schedule_80dd()`/`.disability_schedule_80u()`, which read
  `self.schedule_80dd or nested` — the mechanical script cannot distinguish the two classes'
  same-named fields; manual verification confirmed this is correctly wired, just not through the
  nested copy.
- **`Section80DDBDetails.reimbursement_amount`** — flagged and genuinely unset; there was no
  frontend field anywhere to source it from. **Fixed (2026-09-03), see §13** — a new
  `ChapterVIA.section80DDBReimbursement` field and UI input were added rather than left as a
  documented gap, since the user asked for every open item closed.
- **`PoliticalContribution.contribution_mode`** — **correction (2026-09-03):** this was
  originally misclassified as vestigial by the mechanical script, which only checks kwargs
  passed at construction time. Re-verified by hand: `contribution_mode` is a
  `model_validator`-derived field (`app/schemas/itr1.py`'s `Donation80GGC`-equivalent
  normalizer: `self.contribution_mode = "cash" if ... else "non_cash"`), always self-computed
  from `cash_amount`/`other_mode_amount` regardless of whether the mapper passes it explicitly,
  and it **is** read live by `app/engine/validators/itr4/input_rules.py`. Not a bug, not
  vestigial — no action needed. Flagged here as a caution about the mechanical script's blind
  spot for validator-derived fields, confirmed not to have caused any other false removal in
  this audit's fixes.
- **`employer.uniformAllowance`** (found while implementing the fix below, not by the script —
  it has no corresponding scalar `SalaryIncome` field at all, so the AST cross-reference could
  not flag it) — a real, rendered frontend input (`EmployerEntryManager.tsx:508`) with no live
  mapper path. Deliberately **not folded into `sec10_14i_prescribed_allowance`** during the
  §11.1-§11.8 fix below: uniform allowance's Section 10(14)(i)/Rule 2BB exemption is "actual
  expenditure incurred," not the fixed ₹100/month/child CEA rate `_exempt_children_education()`
  applies — mixing the two inputs would silently apply the wrong cap to uniform allowance rather
  than fix it. Left as an open, documented gap; needs its own `SalaryIncome` field and exemption
  function (actual-expenditure-based, uncapped by statute) before it can be wired correctly.
- **`employer.otherExempt`** — has a `SalaryIncome`-shaped intent but, unlike `uniformAllowance`,
  has **no rendered UI at all** in `EmployerEntryManager.tsx` (confirmed by grep — no JSX
  reference); vestigial, same class as `employerNPS`/`salaryNatureRows`/`perquisiteNatureRows`.

### 11.10 Updated severity ranking

§11.1 (six retirement/severance categories: complete income *and* exemption omission, large
one-time amounts) and §11.5 (`lta_amount_received`: live Severity-A filing-blocking regression
for real LTA claimants, shipped in commit `3ae3c47`) are **P0** — both cause either understated
tax liability or an outright inability to file for identifiable, non-rare taxpayer populations.
§11.2-§11.4 and §11.8 (transport/CEA/hostel allowances, disabled-employee exemption, the three
`section10ExemptionRows` categories, and the original average-salary/years-of-service/unavailed-
leave sub-limits) are **P1** — real omissions, smaller and rarer-population than §11.1, but
still genuine under-taxation-relief bugs that need the same class of fix. §11.6 (standard
deduction warning) and §11.7 (JSON row uses raw vs. capped retrenchment amount) are **P2** —
cosmetic/consistency issues with no effect on computed tax liability.

---

## 12. §11 fix write-up (2026-09-03)

Every finding in §11.1-§11.8 was implemented in the same change; §11.9's items were
deliberately left alone (confirmed correctly out of scope) except for the two additional gaps
(`uniformAllowance`, `otherExempt`) documented, not fixed, in §11.9's updated list.

### 12.1 New `SalaryIncome` fields

`app/schemas/itr1.py` gained five fields with no prior schema representation:
`is_disabled_employee`, `number_of_children`, `average_monthly_salary`, `years_of_service`,
`unavailed_leave_days`. Every other field this section wires (`gratuity_received`,
`commuted_pension_received`, `leave_encashment_received`, `vrs_compensation`,
`retrenchment_compensation`, `transport_allowance`, `sec10_14i_prescribed_allowance`,
`sec10_14ii_personal_allowance`, `sec10_6_embassy_exempt`, `sec10_7_foreign_allowance`,
`sec10_10cc_perquisite_tax`, `lta_amount_received`, `standard_deduction_claimed`) already
existed on the schema — only the mapper was missing.

### 12.2 `app/engine/schedules/salary.py` — real statutory sub-limit formulas (§11.8)

`_exempt_gratuity()` now takes `average_monthly_salary`/`years_of_service` and applies a third
sub-limit, `0.5 × average_monthly_salary × years_of_service` — the formula for employees **not**
covered under the Payment of Gratuity Act 1972. Employees covered under the Act get a more
generous formula (`15/26 × last-drawn salary × years`), but this product does not capture
coverage status; using the lower non-covered multiple is the documented conservative choice
when that fact is unknown (`GRATUITY_NON_COVERED_SALARY_MULTIPLE`'s docstring in
`app/engine/constants.py`).

`_exempt_leave_encashment()` now takes the same two inputs plus `unavailed_leave_days`, and
applies two further sub-limits: the cash equivalent of unavailed leave (days capped at 30 per
completed year of service, valued at the average monthly salary) and 10 months' average salary
— both real Section 10(10AA) statutory tests, not present before.

Both functions return `0` (not an unbounded pass-through) when the salary-sub-limit evidence is
absent, matching this codebase's established HRA/LTA "never grant an exemption the engine
cannot verify" convention — a taxpayer whose employer form is filled in completely gets the
correct exemption; one who is not still gets the received amount taxed (§12.3), never silently
dropped.

`SalaryResult` gained a `retrenchment_exempt` field (§11.7) — `compute()` was already computing
this value and folding it into `exempt_allowances` correctly, just never exposing it;
`app/engine/itd/itr1.py`'s `10(10B)(i)` JSON row now reads it instead of the raw, uncapped
`retrenchment_compensation`.

`compute()`'s `gross` local now also adds `gratuity_received`, `commuted_pension_received`,
`leave_encashment_received`, `vrs_compensation`, and `retrenchment_compensation` — closing
§11.1's core bug: previously the exempt *portion* of these was computed correctly (once the
mapper started supplying them) but the taxable *residual* never entered gross salary at all,
since `gross` never independently added the received amounts.

### 12.3 `app/engine/draft_to_itr1_input.py::_map_salary` — the mapper rewrite

Gained a `tax_regime: TaxRegime` parameter (needed for §12.5's standard-deduction fix) — the
three call sites (`draft_to_itr1_input.py`, and the shared function's other two callers,
`draft_to_itr2_input.py` and `draft_to_itr4_input.py`) already compute `tax_regime` before
calling `_map_salary`, so no reordering was needed, just passing it through.

Every field named in §12.1 is now summed/derived from the `Employer` rows and wired into
`SalaryIncome`. Two design notes:

- `average_monthly_salary`/`years_of_service`/`unavailed_leave_days` are facts about a single
  retirement event, not independently additive across employer rows (unlike `basic`/`da`/etc.,
  which genuinely are sums across concurrent employers). They are taken from whichever employer
  row reports the largest combined retirement payout (`gratuity + leaveEncashment +
  commutedPension + vrsCompensation + retrenchmentCompensation`) — correct for the overwhelming
  common case of one retiring employer; a taxpayer with two genuinely separate retirement events
  in the same year is an edge case this aggregate `SalaryIncome` shape cannot represent
  precisely, noted rather than silently mishandled.
- `number_of_children` and `is_disabled_employee` are per-taxpayer facts captured per-employer-row
  on the draft; taken as `max()` and `any()` respectively across employers (not summed) to avoid
  double-counting the same real-world fact.

`section10ExemptionRows` (the `10(6)`/`10(7)`/`10(10CC)` dropdown+amount list) is now iterated
per employer and routed by `natureCode` to the three matching `SalaryIncome` scalars.

`standard_deduction_claimed` is now set to the regime-appropriate statutory cap
(`OLD_REGIME_STANDARD_DEDUCTION`/`NEW_REGIME_STANDARD_DEDUCTION`) whenever `section_17_1 > 0` —
silencing ITR1-B004's previously-universal false warning (§11.6). This does not change computed
tax: `schedules/salary.py::compute()` still derives the actual standard deduction itself.

### 12.4 Live validator regressions found and fixed while verifying §12.3 end-to-end

Building a realistic test case (a 25-year government employee with a ₹25L gratuity and LTA
claim) surfaced two more dormant-until-now `Severity.A` (filing-blocking) validator bugs in
`app/engine/validators/itr1/input_rules.py`, on top of §11.5's `lta_amount_received` regression
— all three share the same root cause: a check written against a field that was always `0`
before this session's fixes, activated for the first time once the mapper started supplying
real values.

- **ITR1-R100/R101/R102 (removed):** compared `gratuity_received`/`commuted_pension_received`/
  `leave_encashment_received` against `salary_income.gross_salary` — the *current year's*
  Section 17(1) salary — and blocked filing if the retirement payout was larger. There is no
  such test anywhere in the Income Tax Act; a career-end lump sum routinely and correctly
  exceeds one year's running salary (25 years of service commonly produces gratuity several
  times the final year's salary — exactly the realistic case that triggered this). Removed
  rather than "corrected," since no valid replacement comparison exists; the real statutory caps
  are already enforced in `schedules/salary.py`.
- **ITR1-R142 (fixed):** its non-government-employee detection matched keywords like
  `"central government"`/`"cg-"` against `inp.nature_of_employment`, which actually carries the
  raw official code (`CGOV`/`SGOV`/`PSU`/...) — a string that never contains those keywords. The
  rule therefore treated every employee as non-government, unconditionally. Fixed to check
  `nature_of_employment in {"CGOV", "SGOV"}`, matching the definition already established
  elsewhere in this codebase (`section_80ccd2.py`, and this same mapper's
  `is_government_employee` derivation).

Both fixes are documented inline at the removal/change site with the same reasoning as here.

### 12.5 Verification

- **New test file `tests/test_salary_schedule.py`** (13 tests): direct unit coverage of
  `_exempt_gratuity`/`_exempt_leave_encashment`'s new sub-limit formulas (statutory-ceiling-
  binds, salary-sub-limit-binds, received-amount-binds, and zero-without-evidence cases for
  each), plus `compute()`-level coverage of `retrenchment_exempt` exposure, the disabled-
  employee transport exemption, and the two child-allowance exemptions reading real
  `number_of_children` instead of a hardcoded `0`.
- **`tests/test_draft_to_itr1_input.py`**: 7 new tests — `lta_amount_received` mapped
  (§11.5's regression-prevention test), retirement receipts reaching both `SalaryIncome` and
  taxable `gross_salary`, transport/CEA/hostel allowances reaching `SalaryIncome` and producing
  correct calculator exemptions, a control case confirming CEA/hostel are correctly zero without
  `numberOfChildren`, `section10ExemptionRows` routing to the three matching scalars, and
  `standard_deduction_claimed` resolving to the regime-appropriate cap in both regimes.
- **`tests/test_itr1_input_validation.py`**: the 3 tests asserting the now-removed
  `ITR1-R100`/`R101`/`R102` rules were rewritten to assert the corrected (non-blocking) behavior
  instead, with each documenting why.
- `pytest tests/test_salary_schedule.py tests/test_draft_to_itr1_input.py tests/test_itr1_input_validation.py -v` — 155 passed (13 + 41 + 101).
- `pytest tests/ -k "itr1 or itr2 or itr4"` (same pre-existing-exclusion list as prior phase
  notes) — 679 passed before adding the new tests above, re-verified green after.
- End-to-end script verification (not part of the automated suite): a realistic CGOV employee
  draft with LTA (received ₹30,000 / fare ₹22,000), gratuity ₹25,00,000 (25 years of service,
  ₹50,000 average monthly salary), leave encashment ₹4,00,000 (300 unavailed days), disabled-
  employee transport allowance ₹30,000, and 2 children's education/hostel allowances — confirmed
  every field reaches `SalaryIncome`, the calculator produces a nonzero chargeable salary income
  that includes the retirement receipts, and `validate_itr1_input()` produces **zero**
  `Severity.A` failures (previously the LTA claim alone would have hard-blocked filing via the
  §11.5 regression, before either the mapper or validator fixes in this section).
- Formula-correctness spot checks (direct calls to `_exempt_gratuity`/`_exempt_leave_encashment`
  outside pytest): confirmed the gratuity salary sub-limit (`0.5 × avg × years`), the leave-
  encashment cash-equivalent-of-leave sub-limit with the 30-days-per-year cap actually binding,
  and full exemption for government employees regardless of amount.

---

## 13. §6.4 and remaining-open-item fix write-up (2026-09-03)

Closes out every item left open at the end of §12: §6.4 (money input parsing), plus the four
smaller gaps found and fixed along the way while verifying §6.4 in a real client return in the
browser.

### 13.1 §6.4 — money input parsing consolidated onto `IndianNumberInput`

A correctly-built shared component already existed —
`frontend/src/components/IndianNumberInput.tsx` — with real integer-rupee semantics
(`Math.round(Number(rawValue))`), Indian lakh/crore comma formatting, and a `!isNaN(numValue)`
guard that rejects a garbled edit instead of coercing it to `0`. It was used in exactly one
place (`AdvancedTaxPage.tsx`) before this fix. Replaced the ad hoc `parseFloat(e.target.value)
|| 0` / `Number(e.target.value) || 0` pattern with it across every site the original §6.4
finding named, plus every other occurrence found by a fresh `grep -rn` sweep:
`DeductionLoanManager.tsx`, `dividend/DividendEntryManager.tsx`, `DonationEntryManager.tsx`,
`familyPension/FamilyPensionManager.tsx`, `gifts/GiftPropertyManager.tsx`,
`interest/InterestEntryManager.tsx`, `Section80CManager.tsx`, `Section80DManager.tsx`,
`winnings/WinningsManager.tsx`, and `ITRComputationTabs.tsx` (TDS/TCS/advance-tax tabs, 11
separate fields).

`EmployerEntryManager.tsx`'s own local `AmountInput` helper (§6.4's original citation) was not
just using the ad hoc pattern — it was worse: `Number(e.target.value.replace(/\D/g, ''))`
strips every non-digit character including the decimal point, so a value like `"50000.50"`
became `"5000050"`, a **100x error**, rather than rounding to `50001`. `AmountInput` now
delegates to `IndianNumberInput` (kept as a thin same-signature wrapper so its ~30 existing call
sites needed no changes).

`ITR2SchedulesWorkspace.tsx` has the same ad hoc pattern but was deliberately left untouched —
it is exclusively ITR-2 UI, outside every citation in the original §6.4 finding and outside this
audit's scope per the user's own stated sequencing (ITR-1 → ITR-4 → ITR-2 → ITR-3).
`CapitalGainsEntryManager.tsx`'s `Number(row[field] ?? 0) || 0` was also left alone — it
aggregates already-numeric *imported* row data in a `reduce()`, not a keystroke handler, so it
isn't an instance of the bug this finding describes.

**Verified in the running app, not just by type-checking:** signed into a real client return
(ITR-4, salary tab) and typed `50000.75` into an `IndianNumberInput`-backed field — it correctly
rounded to `50,001` on blur (confirmed the exact bug described above no longer reproduces).
Typed garbled text (`abc12,34x5`) into the same field — the component correctly rejected it and
kept the last valid value rather than corrupting or zeroing it. The test edit was reverted
before navigating away; nothing was saved to the client's actual return.

**Incident during verification, disclosed for completeness:** while getting the app running to
test this in a browser, a `curl` health-check to the already-running dev backend timed out, and
a second `python run.py` instance was started to investigate — briefly leaving two processes
bound to port 8000. The extra process was killed once noticed, but investigating further command
output established that the pre-existing backend on that port was not responding either. The
user reported having manually closed both their backend and frontend dev servers around the same
time, which was the actual explanation — no server state was corrupted by this session; both
were cleanly restarted (`python run.py`; `npm run dev` via `.claude/launch.json`, added this
session) to complete the browser verification.

### 13.2 Additional gaps found and fixed while verifying §6.4 (not part of the original audit)

- **`employer.uniformAllowance`** (§11.9's documented-but-deferred item) — still has no
  statutory basis for a formulaic exemption (Section 10(14)(i)/Rule 2BB exempts only *actual
  expenditure incurred*, a fact this product does not capture), so no exemption is claimed for
  it. But it was reaching neither income nor exemption at all — the received amount is now
  added to `section_17_1` as fully taxable income (`app/engine/draft_to_itr1_input.py::_map_salary`),
  the same conservative treatment already used for `other_taxable_salary`: it reaches income,
  and claims no unverifiable relief.
- **`employer.gratuityAlsoReceived`** — a real, rendered frontend control
  (`EmployerEntryManager.tsx:532`, conditionally shown alongside commuted pension) that
  determines the Section 10(10A) commuted-pension exemption fraction (1/3rd if gratuity is also
  received, 1/2 if not) but was never wired to the calculator, which always used the flat 1/3rd
  fraction. New `SalaryIncome.is_gratuity_also_received` field (default `True`, the lower/
  conservative fraction); `_exempt_commutted_pension()` now takes it as a parameter; new
  constants `COMMUTED_PENSION_WITH_GRATUITY_PCT`/`COMMUTED_PENSION_WITHOUT_GRATUITY_PCT` replace
  the old single `COMMUTED_PENSION_NON_GOV_T_PCT`. This under-exemption (not under-income) bug
  was found by re-reading the Employer schema line-by-line while removing the vestigial fields
  below, not by the original AST script.
- **`ChapterVIA.section80DDBReimbursement`** — §11.9 had documented this as a rare, low-severity
  gap not worth escalating; implemented anyway per the user's "fix all the open" instruction.
  New field + a `NumberField` input in `DeductionsWorkspace.tsx`'s 80DDB section, wired to
  `Section80DDBDetails.reimbursement_amount` in the mapper.
- **Vestigial field cleanup**: `employer.ltaExempt` (found to be dead in the same pass — no live
  frontend writer since the §5.1 LTA fix moved exemption computation to evidence-based
  recomputation, and no reader either), `employer.otherExempt`, `employer.salaryNatureRows`,
  `employer.perquisiteNatureRows` removed from the `Employer` schema, the frontend type, every
  default-construction site, and test fixtures — same treatment as the already-fixed
  `employerNPS` (§6.2), including a `migrate_stored_draft_payload` migration
  (`_migrate_employer_vestigial_salary_fields`) so previously-saved drafts carrying any of the
  four keys still load. `PoliticalContribution.contribution_mode` was investigated for the same
  treatment but found to be a live, correctly self-computed field — see the correction in §11.9.

### 13.3 Verification

- `npx tsc -b`, `npx vitest run` (185 passed), `npm run build` — all clean after both the
  money-input consolidation and the four follow-up fixes.
- New tests: 4 in `tests/test_salary_schedule.py` (commuted-pension gratuity-also-received
  fraction, govt-fully-exempt, and the conservative default), 3 in `tests/test_draft_to_itr1_input.py`
  (uniform allowance reaching gross salary, gratuity-also-received flag reaching `SalaryIncome`
  and the calculator, 80DDB reimbursement reaching `Section80DDBDetails`), 1 in
  `tests/test_client_itr_v2_download.py` (the new migration strips all four vestigial keys from
  a stored employer row and the migrated payload still validates end-to-end).
- `pytest tests/test_salary_schedule.py tests/test_draft_to_itr1_input.py tests/test_client_itr_v2_download.py -q`
  — 60 + 44 + 13 = 117 passed.
- Full backend suite (same pre-existing-exclusion list as prior phase notes) — 1530 passed, same
  3 pre-existing failures + 1 collection error as every prior run this session, confirmed
  unrelated by inspection (unchanged failure set, `test_tax_v2_compute.py`/`test_26as_batch.py`,
  nothing this change touches).

---

## 14. Deep audit of the remaining schedules and the validator suite (2026-09-03)

§9 named three things this audit had explicitly not verified at Salary's depth: validators
beyond the specific regressions this work caused, House Property/Other Sources/Capital Gains/
Chapter VI-A's formula completeness, and filing-profile/bank-account/TDS-TCS depth. This section
covers the first three; filing profile/bank accounts/TDS-TCS were not reached in this pass (see
§14.5).

### 14.1 House Property (`app/engine/schedules/house_property.py`) — read end to end

Structurally sound. Multi-property intra-head netting happens before the inter-head Section
71(3A) ₹2L loss-setoff cap is applied, correctly permitting one property's profit to offset
another's loss before the cross-head limit bites — matches the module's own documented design
and the real statutory sequencing. Section 25A arrears (70% taxable), the old/new-regime
self-occupied interest treatment, and `ownership_share_percentage`'s documented scope (GAV only,
not interest/arrears — a deliberate, stated design given co-owners typically already report
their own share of loan interest) all check out.

One genuine but near-zero-population gap: `HOUSE_PROPERTY_INTEREST_LIMIT_SELF_OCCUPIED` is a
flat ₹2,00,000 for every self-occupied loan regardless of sanction date, when the correct rule
caps loans sanctioned before 1 April 1999 at ₹30,000 instead. `LoanDetail.sanction_date` is
captured and reaches the JSON output, but `schedules/house_property.py::compute()` never reads
it. Not fixed — a loan from before April 1999 would need a still-active 25+ year tenure to
appear in an AY 2026-27 filing, an vanishingly rare population; noted for completeness, not
escalated.

### 14.2 Other Sources (`app/engine/schedules/other_sources.py`) — read end to end

Correct. Section 57(iia) family-pension deduction (1/3rd of pension or a statutory cap) 
correctly reflects the Finance Act 2024 new-regime enhancement (₹25,000 vs the old regime's
₹15,000). Found one piece of genuinely dead code while tracing 80TTA/80TTB eligibility: a local
`interest_sb` computed inside `_map_deductions` (`app/engine/draft_to_itr1_input.py`, using a
`_SAVINGS_KINDS` set that inconsistently includes `POST_OFFICE` interest as savings-type,
diverging from the Schedule-OS categorization) is computed but never read anywhere in the
function — harmless (the real 80TTA/80TTB deduction is computed correctly, see §14.3), just
confusing leftover code. Not fixed — no behavioral effect, flagged for a future cleanup pass
only.

### 14.3 Chapter VI-A Deductions (`app/engine/schedules/deductions/`) — spot-checked in depth

This is a materially more mature module than a first read of `Chapter6ADeductions` (a flat data
container) suggests: 22 dedicated per-section files (`section_80c.py`, `section_80d.py`,
`section_80tta.py`, `section_80ttb.py`, `section_80g.py`, `section_80gg.py`, etc.), aggregated by
`app/engine/schedules/deductions/__init__.py::compute_all`. Verified directly:

- **80CCE combined pool** (80C+80CCC+80CCD(1), ₹1.5L cap): correctly enforced with proportional
  allocation across the three components when the raw total exceeds the cap, and per-row
  allocation within Schedule 80C's own detail rows.
- **80TTA/80TTB**: correctly capped at `min(user_claim, actual_savings_interest,
  statutory_limit)`, correctly zeroed for the wrong age bracket or new regime. (The frontend
  lets a user type any 80TTA/80TTB figure with no client-side cap — but the backend
  `compute_all` pipeline independently re-derives and caps the real deduction from actual
  Other-Sources interest, so a spoofed frontend claim cannot inflate the computed tax
  liability — consistent with this codebase's "never trust an unverified frontend figure"
  convention.)
- **80G/80GG/80GGA/80GGC cascade**: correctly computed in dependency order (80GG's adjusted-GTI
  excludes deductions-before-80G and CG-112A/111A income per CBDT rules; 80G's own adjusted GTI
  further excludes the just-computed 80GG; 80GGA/80GGC each recompute available headroom from
  what's already been consumed) — this ordering matters and is correctly sequenced.
- A `calculators/itr1.py` warning block (`"80TTB is only available for senior citizens... Deduction
  set to Rs 0"`) reads as if it performs the zeroing itself; it does not — it is a separate,
  purely informational warning layer, and the actual zeroing already happens correctly inside
  `section_80ttb.compute_details()`. Confirmed this is not a bug (the message is misleading
  about *where* the zeroing happens, not about whether it happens) — not fixed, a documentation/
  clarity nit only.

No bugs found or fixed in this module.

### 14.4 Capital Gains — restricted Section 112A (`app/engine/schedules/restricted_112a.py`) — read end to end

Also more mature than expected: the file's own inline comments reference specific past bugs and
their fixes (a "purchase-only evidence row misread as a ₹0 sale, fabricating a fake loss" bug;
an evidence-vs-completed-sale disambiguation bug), suggesting this module has already been
through real iteration. Verified directly: the grandfathering formula
(`max(actual_cost, min(fmv_31_jan_2018, sale_value))`) is the correct Section 112A/Finance Act
2018 proviso; the 12-month long-term threshold uses calendar-anniversary date arithmetic (not a
naive `days/365`), correctly handling variable month lengths; STT/recognized-exchange
confirmations are correctly required only for listed equity, not equity-oriented mutual funds or
business-trust units (which are not subject to STT on acquisition the same way); the ₹1,25,000
aggregate-gain ITR-1/ITR-4 eligibility threshold is applied exactly once
(`special_rates.py`'s `pre_exempted` parameter exists specifically to prevent double-applying
it). No bugs found or fixed in this module.

### 14.5 Validators — systematic review found and fixed a severe, pre-existing, recurring bug
class (not part of §5/§11/§12/§13; not introduced by any fix in this document)

§9's caveat specifically named this as the least-verified area. A systematic sweep for the same
root cause as the already-fixed ITR1-R142 (§12.4) — matching human-readable keywords like
`"central government"`/`"pension"`/`"cg-"` against `nature_of_employment`, which actually
carries the raw official code `CGOV`/`SGOV`/`PSU`/`PE`/`PESG`/`PEPS`/`PEO`/`OTH` (see
`frontend/src/domain/returns/cbdtEnums.ts`'s `NATURE_OF_EMPLOYMENT_OPTIONS`) — found **9 more
occurrences** of the identical bug in `app/engine/validators/itr1/input_rules.py`, none of them
caused by this session's earlier fixes (`nature_of_employment` has carried the raw code since
before this session started; these are pre-existing, currently-shipped defects). Unlike
R100-102/R142 (exposed only after this session wired previously-always-zero salary fields),
these were live and broken from the moment the fields they check (`amount_80ccd2`,
`amount_80cch`, `gratuity_received`, `exempt_income_dropdowns`, etc.) were ever populated by any
real filer — i.e., potentially in production already, for any actual CG/SG employee, pensioner,
or judge who used ITR-1.

Two failure directions, both real:

- **False-positive blocking** (fires when it should not, hard-blocking a legitimate filer):
  - **ITR1-R119/R120**: a genuine CGOV/SGOV employee claiming Section 80CCD(2) between 10% and
    14% of salary (legitimate under the government-employee 14% cap) was always routed to the
    stricter 10% non-government check and blocked, since `"central"/"state"/"government"` never
    matched `"CGOV"`/`"SGOV"`.
  - **ITR1-R187**: 80CCH (Agniveer Corpus Fund) always blocked, even for a genuine Central
    Government employee, since `"central government" not in emp_lower` was always `True`.
  - **ITR1-R301/R270** (two independent copies of the same check, different rule IDs — a
    pre-existing ID collision, not touched here): the Judge Salaries Act exemption always
    blocked, even for a genuine CGOV/SGOV employee (e.g. a Supreme/High Court judge).
- **Silently dormant** (never fires when it should, letting an invalid claim through unchecked
  — the calculator's own statutory formulas remain correct regardless per §12, since they
  derive `is_govt` independently and correctly; only this validator-layer sanity check was
  inert):
  - **ITR1-R116**: pensioners claiming Section 80CCD(2) (which requires a live employer, and a
    pensioner has none) were never flagged.
  - **ITR1-R002/R003**: a pensioner's Section 80CCD(1) claim was always checked against the
    non-pensioner 10%-of-salary rule instead of the correct 20%-of-estimated-GTI rule, since
    `"pension"` never matched `PE`/`PESG`/`PEPS`/`PEO`.
  - **ITR1-R185**: Section 10(10B) retrenchment-compensation exemption (only for industrial
    workers under the ID Act) was never checked against government-employee/pensioner status.
  - **ITR1-R267**: a genuine CGOV/SGOV employee's gratuity claim was never checked against the
    ₹25L government-employee ceiling (fell through uncaught rather than being compared against
    the correct, more generous limit).

**Fix:** two shared helpers, `_is_cg_sg_employee()` and `_is_pensioner()`, added once near the
top of `input_rules.py`, checking `nature_of_employment` against the correct code sets
(`{"CGOV","SGOV"}` and `{"PE","PESG","PEPS","PEO"}` respectively, taken directly from the
frontend's own enum definition) — used at all 9 sites plus the pre-existing R142 fix, replacing
every ad hoc keyword-matching expression. R267's companion check (`is_psu_private`, the ₹20L
non-government cap) was corrected from an independent, equally-broken keyword guess to the
logical complement of `is_cg_sg` — everyone who isn't CG/SG is capped at ₹20L, which is what
the statute and the calculator's own `is_govt` logic already say.

No other instance of this keyword-vs-raw-code pattern was found against any other field — a full
`.lower()` sweep of both `input_rules.py` and `calc_rules.py` found only legitimate uses
(attribute-name construction, case-insensitive email comparison) elsewhere. `calc_rules.py`
(post-computation arithmetic cross-checks — GTI/deduction/tax-liability self-consistency) was
read in full separately; it does not reference `nature_of_employment` at all and shows no
comparable defect.

### 14.6 Verification

- 12 new tests in `tests/test_itr1_input_validation.py`, each asserting both directions (a real
  CG/SG/pensioner/judge case that must now pass, and a real non-CG/SG/non-pensioner case that
  must still correctly fail) for R119/R120, R116, R002/R003, R187, R270/R301, R267, and R185.
- `pytest tests/test_itr1_input_validation.py -v` — 113 passed (101 pre-existing + 12 new).
- `pytest tests/ -k "itr1 or itr2 or itr4"` — 688 passed, no regressions.
- Full backend suite — 1544 passed, same 3 pre-existing failures (`test_tax_v2_compute.py`) and
  1 pre-existing collection error (`test_26as_batch.py`) as every prior run this session — no
  new failures.

### 14.7 What this pass still did not cover

Filing profile / verification / bank accounts / TDS-TCS structural depth (§9's third named gap)
was not reached in this pass — §9's caveat about it still stands. The three schedules covered
here (§14.1-§14.4) and the validator sweep (§14.5) were chosen because they were the most likely
locations for a Salary-shaped bug (a formula gap or a systematic miscalibration) and because the
validator sweep's method — searching for a recurrence of an already-confirmed bug pattern — is
concrete and repeatable, unlike an open-ended "read everything" pass. A future session
continuing this work should start with filing profile/bank accounts/TDS-TCS before considering
ITR-1 exhaustively covered.
