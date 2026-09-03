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

**Update (2026-09-03): §9's third named gap has now been covered — see §15.**

---

## 15. Tax-core, filing-profile/bank-account architecture, and TDS/TCS credit audit (2026-09-03)

Continues §14, covering the remaining named gap (filing profile/verification/bank accounts/
TDS-TCS) plus the core tax-computation modules every schedule ultimately feeds into
(`app/engine/common/`), which no prior pass in this document had read.

### 15.1 Core tax computation (`app/engine/common/`) — read end to end

All six modules (`slab_tax.py`, `rebate.py`, `surcharge.py`, `cess.py`, `interest.py`,
`rounding.py`) verified correct against current statute and Finance Act 2025 (AY 2026-27)
changes:

- **Slabs**: both regimes' rate tables match Budget 2025 exactly, including the new regime's
  revised 0/5/10/15/20/25/30% bands up to ₹24L.
- **Rebate 87A**: ₹5L/₹12,500 (old) and ₹12L/₹60,000 (new) thresholds correct; both regimes'
  marginal-relief formula correctly caps tax-after-rebate at the income excess over the
  threshold (never lets tax increase by more than income does, crossing the cliff); correctly
  computed against slab (normal-rate) tax only, never special-rate income — matches the
  statutory restriction on 87A against 112A/111A income.
- **Surcharge**: the 15% cap on capital-gains/dividend-income surcharge (a frequently-missed
  provision) is correctly applied only to that income basket, not the whole tax; the new
  regime's 25% surcharge ceiling above ₹5Cr (vs. the old regime's 37%) is correctly modeled as
  a separate slab table; marginal relief uses the correct "tax cannot increase by more than
  income does" principle across the actual threshold. (For ITR-1 specifically, only the lowest
  surcharge slab — 10%, ₹50L-₹1Cr — is ever reachable in practice, since ITR-1 eligibility caps
  total income at ₹50L; the higher slabs and their marginal relief are exercised only by the
  other forms sharing this module.)
- **234A/234B/234C interest**: the "part of a month counts as a full month" rule was traced
  through several boundary cases (exactly one month later, one day into a second month, etc.)
  and computes correctly in each. 234B's date-ordered self-assessment-payment reconciliation
  (interest accrues on the outstanding balance, reducing from each payment's actual deposit
  date) and 234C's presumptive-taxpayer single-installment carve-out both check out.
  234F/234-I late-fee thresholds match the statutory ₹1,000/₹5,000/₹10,000 tiers.
- **Rounding**: `round_to_nearest_10` correctly implements Sections 288A/288B (₹5 rounds up);
  `round_to_nearest_rupee`/`vba_round` correctly use half-up rounding — the module's own
  comment documents a prior fix (banker's rounding was wrong, already corrected before this
  audit).

No bugs found in this module.

### 15.2 AMT — correctly not wired into ITR-1

`app/engine/schedules/amt.py` (Section 115JC Alternative Minimum Tax) is not imported anywhere
in `app/engine/calculators/itr1.py`. Correct: AMT applies only to non-corporate assessees
claiming deductions like 80-IA/10AA, all of which `Chapter6ADeductions`' own field docstrings
already mark "ITR-3 only" (confirmed structurally inapplicable in §11.9). No gap.

### 15.3 Filing profile / bank accounts — already resolved by a prior "Phase 5F" refactor

The Phase 5F architecture concern on file for this codebase (a shared `personal_profile.py`
normalizer to close the risk of ITR-1's filing-profile/bank-account construction silently
diverging from its own compute-input construction) has **already been implemented** —
confirmed directly in code, not assumed from a plan document: `app/engine/filing_gateway_v2.py`'s
`_filing_profile()` is now "a thin adapter over `app.engine.personal_profile`'s shared
normalizer," and `app/engine/draft_to_itr1_input.py::_map_bank_accounts()`'s own docstring
states it now "delegates to the shared `app.engine.personal_profile` normalizer/projection —
this **used to be** a second, independent, zero-validation bank-account mapping." The specific
divergence risk that plan flagged as "the sharpest existing asymmetry" is closed. No further
action taken here — this is a report of a pre-existing fix, not a fix made by this session.

### 15.4 TDS/TCS credit computation — a severe, pre-existing, live bug affecting ITR-1 and ITR-4
(not ITR-2, not introduced by any fix in this document)

`app/schemas/itr1.py`'s `TDS2Entry` and `TDS3Entry` each carry a "claimed this year" field
distinct from the full amount deducted (`tds_claimed_this_year` / `tds_claimed`), reflecting
Rule 37BA(3) — a taxpayer may spread TDS credit across the years in which the corresponding
income is actually offered to tax (the common case: bank FD interest, TDS'd on accrual by the
bank, but income declared by the taxpayer on receipt/maturity). The frontend has a real,
rendered "Claim out of Total TDS" input for exactly this
(`frontend/src/pages/ITRComputationTabs.tsx`, confirmed in §13.1's money-input work), and the
ITD JSON builder (`app/engine/itd/itr1.py`) already correctly emits both figures per row
(`ClaimOutOfTotTDSOnAmtPaid`, `TDSClaimed`).

**The actual computed tax liability never used either field.**
`app/engine/schedules/tds_tcs/__init__.py::compute_all()` — the function every ITR-1/ITR-3/
ITR-4 calculator calls to determine `total_tds`, which feeds `total_taxes_paid`, which
determines 234A/B/C interest and the final payable/refund shown to the user — summed the raw
`tds_deducted` for every TDS2 row, ignoring `tds_claimed_this_year` entirely. **TDS3 (Section
195, TDS on payments to non-residents — e.g. rent withheld on payments to an NRI landlord, or
an NRI property purchase) was not passed to `compute_all()` at all by any ITR-1/ITR-3/ITR-4
caller**, so a genuine TDS3 credit reduced the computed tax liability by **zero**, regardless of
amount, even though the mapper correctly captured it and the JSON correctly reported it in the
TDS3 schedule. Confirmed via `grep` across every calculator: ITR-2 is unaffected — its
calculator (`app/engine/calculators/itr2.py`) has its own separate, already-correct TDS
aggregation that does use `tds_claimed_this_year` for both TDS2 and TDS3 — this bug is specific
to the three calculators sharing `compute_all()`. Neither of these defects was introduced by any
fix in this document; `tds_claimed_this_year` predates this session, and this is a pre-existing,
currently-shipped defect for any real ITR-1/ITR-4 filer with a genuine Rule 37BA(3) partial
claim or any TDS3 credit at all.

**Consequence:** in both directions —

- A taxpayer entering a legitimate partial current-year TDS2 claim (carrying the rest forward)
  had the *full* deducted amount credited against this year's liability instead — an
  over-claimed refund / under-stated payable, inconsistent with what the same taxpayer's filed
  JSON correctly showed on the row.
- A taxpayer with any TDS3 credit (Section 195 non-resident-payment withholding) had **none of
  it** applied to their computed liability — an under-claimed refund / over-stated payable, for
  the full deducted amount, every time.

**Fix:**

- `compute_all()` now accepts `tds3_entries` and aggregates them (using `tds_claimed`, the
  correct field name — see below), and its TDS2 loop now uses `tds_claimed_this_year` when it's
  meaningfully set (`> 0`), falling back to `tds_deducted` only when unset — preserving
  behavior for the one caller that never populates it (`app/routers/tax.py`'s legacy flat-blob
  path), while correctly honoring a real partial claim from the canonical v2 mapper (which
  always defaults `tds_claimed_this_year` to the full tax when the user doesn't specify a
  partial amount, so this fallback never masks a real 0-vs-unset ambiguity for that path).
- `app/engine/calculators/itr1.py` and `app/engine/calculators/itr4.py` now pass
  `tds3_entries=input_data.tds3_entries` to `compute_all()`. (ITR-3 has no `tds3_entries` field
  on its input schema at all — not touched, not applicable.)
- `app/engine/draft_to_itr1_input.py::_map_tds`'s own `claimed_total` (→
  `ITR1Input.total_tds_claimed`, read only by a validator cross-check, never by the
  calculator) had the identical bug — always summed the full `tax` regardless of a genuine
  partial TDS2 claim — fixed to match, computed before the per-row TAN-validity check so an
  invalid-TAN row's intended claim still counts toward the total (its original scope).
- **ITR1-R102** (`app/engine/validators/itr1/input_rules.py`): a second, independent bug in the
  same area — its TDS3 claimed-sum cross-check read `getattr(e, 'tds_claimed_this_year', _z)`,
  but `TDS3Entry`'s actual field is `tds_claimed` (a different name than TDS2Entry's), so the
  `getattr` always missed and silently defaulted to zero, permanently disabling this check
  regardless of any real mismatch. Fixed to read the correct field name.
- The same section's `tds2_total`/`tds3_total` locals (feeding ITR1-R103/R108's cross-checks)
  were also switched from raw `tds_deducted` sums to the same claimed-amount basis as the fix
  above, so these cross-checks now validate against what the calculator actually credits,
  instead of quietly comparing two independently-wrong numbers to each other and always passing.
- **Not fixed, explicitly deferred**: `app/engine/validators/itr4/input_rules.py` has the
  identical `tds_claimed_this_year`-vs-`tds_claimed` field-name bug independently, at two more
  sites (lines ~1951, ~1963) — confirmed by grep, not fixed here since it is ITR-4-specific
  validator code, not shared with ITR-1, and this document's scope (per the user's own stated
  form sequencing) is ITR-1 first. Flagged here so the ITR-4 phase does not have to
  re-discover it.

The fix required no changes anywhere downstream of `result.total_tds`/`result.total_taxes_paid`
— every consumer (234A/B/C interest, the JSON's `TaxesPaid`/`BalTaxPayable`/`Refund` sections)
already reads those fields rather than recomputing independently, so the single fix at the
shared aggregation point correctly propagates through the entire pipeline.

### 15.5 Verification

- New `tests/test_tds_tcs_schedule.py` (5 tests): TDS2 credit uses `tds_claimed_this_year` when
  set and falls back to full `tds_deducted` when unset (both directions); TDS3 credit reaches
  `total_tds` and correctly uses the claimed (not full deducted) amount; all four credit types
  (TDS1/TDS2/TDS3/TCS) aggregate correctly together.
- 3 new tests in `tests/test_draft_to_itr1_input.py`: a TDS2 partial claim reaches both
  `TDS2Entry.tds_claimed_this_year` and the mapper's `claimed_tds` aggregate (not the full
  deducted amount); the full-claim default case still works when no partial amount is
  specified; TDS3 credit reaches the real computed tax liability end to end through the actual
  `compute_itr1` calculator, not just a unit-level mock.
- `pytest tests/test_tds_tcs_schedule.py tests/test_draft_to_itr1_input.py
  tests/test_itr1_input_validation.py -v` — 165 passed.
- `pytest tests/ -k "itr1 or itr2 or itr3 or itr4 or tds"` — 789 passed, no regressions across
  any of the four forms (confirms the shared `compute_all()` fix is safe for ITR-2, which has
  its own separate, unaffected TDS aggregation, and for ITR-3, which doesn't reach the changed
  TDS3 parameter at all).
- Full backend suite — 1552 passed, same 3 pre-existing failures (`test_tax_v2_compute.py`) and
  1 pre-existing collection error (`test_26as_batch.py`) as every prior run this session — no
  new failures.

### 15.6 What remains after this pass

§9's three named gaps are now all covered (§14 for validators/House Property/Other Sources/
Capital Gains/Chapter VI-A; §15 for tax-core and filing-profile/bank-account architecture). The
TDS/TCS credit bug found in §15.4 was not part of any of §9's three named gaps — it surfaced
while investigating the filing-profile/bank-account gap and following a "what else reads
`tds_claimed_this_year`" trail, the same investigative method (follow a confirmed defect's
exact field/pattern to its other occurrences) that found the validator bugs in §14.5. This
suggests the productive next step for further depth, if wanted, is the same method applied to
other "two similarly-named fields, only one of which the actual computation reads" pairs
elsewhere in the schema — not named here, since none were found, only the general pattern that
found real bugs twice in this document.

## 16. Official CBDT ITR-1 Validation Rules cross-reference (AY 2026-27)

§16.1-16.5 are the findings, gathered and documented before any code was touched, per the
explicit "findings first" instruction. §16.3's decision was then resolved (by tracing the
mapper, not guessed) and implemented; §16.5's fix was implemented too. Both are recorded as
done at the point they were resolved, so this section reads as a findings-then-fix log rather
than a pure findings snapshot.

### 16.1 Methodology

Source document: `Reference Docs by CBDT & ITD/Official Validations/CBDT_e-Filing_ITR
1_Validation Rules_AY 2026-27 (1).pdf` (22 pages, read in full via the `Read` tool's PDF
support). It catalogs 339 Category A rules (blocking — "Return will not be allowed to be
uploaded"), 9 Category B rules (upload allowed, defect flagged, possible 139(9) notice), and 1
Category D rule (deduction/claim not entertained without the supporting form).

Every rule was transcribed into a standalone catalog
(`scratchpad/official_rules.py`, not committed — scratch only) keyed by its official serial
number, then cross-referenced by script against every `"ITR1-R..."`-style literal in
`app/engine/validators/itr1/input_rules.py` and `calc_rules.py` (4,516 combined lines). The
script flagged 14 Category A rules with no matching literal. Each of the 14 was then
individually re-verified by reading the actual implementing code (not just re-grepping) — per
the same three-question method this repo already documents for ITR-2's validator build-out
(CLAUDE.md: is the field genuinely user-suppliable and calculator-consumed; does the schema
already structurally guarantee it; is there an equivalent check elsewhere under a different
ID) — because a bare regex miss conflates four very different situations: a true gap, a
same-check-different-ID case, a structurally-guaranteed-by-construction case, and a
false-negative from the regex itself (e.g. a rule cited only in a code *comment*, or built via
an f-string the regex can't expand).

### 16.2 Result: 347 of 349 rules implemented; one substantive gap

- **Category A: 337 of 339 implemented or structurally covered.** Of the 14 initial
  regex-misses: 1 is the same check as an existing rule under a different ID (10, dual
  direction of R139/R242 — see §16.4); 1 is a literal duplicate of an already-implemented rule
  (71, same ₹5L VRS cap as R103); 6 are functionally implemented but ID-mislabeled (80/81/82/
  85/86/87 — see §16.5); 3 are structurally guaranteed by direct-formula construction and
  cannot diverge (296/298/299 — see §16.4); 1 is implemented but the regex missed it because
  the rule number appears only in a docstring, not an `"ITR1-R328"` literal (328, confirmed
  live in `app/engine/common/interest.py::compute_234i` — see §16.4). **That left exactly 2
  genuine gaps: rules 68 and 69** (§16.3) — both now implemented.
- **Category B: 9 of 9 implemented** — `app/engine/validators/itr1/input_rules.py` lines
  3587-3700, under an `"ITR1-B_..."` naming scheme (not the `"ITR1-RB#"` pattern the diff
  script initially searched for, hence needing manual confirmation) with explicit `CBDT B1`.."B9"`
  comment citations for every one: Aadhaar-PAN link (B1), Aadhaar quoting u/s 139AA (B2), the
  three TDS-section-code ineligibility groups for both TDS2 and TDS3 (B3/B4 special-rate, B5/B6
  non-resident, B7/B8 business-income), and TDS1-exceeds-gross-salary (B9).
- **Category D: 1 of 1 implemented** — `"ITR1-RD1"` (89(1) relief without Form 10E).

### 16.3 The one substantive gap — rules 68 and 69, and a direct conflict with today's earlier fix

Official rules 68/69 (PDF page 8):

> 68. Exempt Allowance u/Sec 10(10A)-Commuted value of pension received cannot be more than
> Salary as per sec 17(1)
>
> 69. Exempt Allowance u/s 10(10AA)-Earned leave encashment on retirement cannot more than
> Salary as per sec 17(1) (Message to be shown... maximum deduction for a non-Government
> employee including PSU is only Rs 25 lakh)

These are **Category A — blocking at portal upload**, not advisory. Earlier in *this same
session* (§14, before this document's most recent findings), `app/engine/validators/itr1/
input_rules.py` lines 218-234 record removing what were then locally-numbered `ITR1-R100/
R101/R102` — checks that compared `gratuity_received`/`commuted_pension_received`/
`leave_encashment_received` against `salary_income.gross_salary` — with this reasoning:

> "There is no such statutory test anywhere in the Income Tax Act — these are career-end lump
> sums that routinely and correctly exceed one year's running salary... removed rather than
> 'corrected' since no valid replacement comparison exists."

That reasoning is sound **as a question about the Income Tax Act**, but rules 68/69 are not
statutory tests — they are the ITD e-Filing portal's own upload-time gate, independent of
whether the comparison is economically sensible for a multi-decade lump-sum payout. The
"Purpose" section of the validation-rules PDF itself is explicit about this: the rules exist so
"the data which is being uploaded are accurate and compliant to the validation rules... to
avoid rejection of return." A JSON that Taxify's own validators pass but that fails this
specific portal gate is exactly the failure mode CLAUDE.md's instruction was warning about
("the same JSON is to be uploaded to the portal").

Concretely, whether this matters depends on what the field actually represents. Given the
sibling fields in the same schema are already treated as *exempt claim amounts* under Section
10 (not gross receipts) — e.g. `retrenchment_compensation`/`vrs_compensation` are matched
directly against the flat ₹5,00,000 caps in R070/R103/R104, and `leave_encashment_received`
is matched directly against the ₹25,00,000 cap in the still-live R142 — `commuted_pension_received`
and `leave_encashment_received` most likely carry the same meaning here (the amount being
claimed exempt, not the gross lump sum received). Under that reading, rules 68/69 are a genuine
sanity bound the portal enforces (an exempt claim cannot exceed the very salary figure it's
computed against) and are unrelated to the "career-end lump sum exceeds one year's salary"
argument that justified removing R100-R102 — that argument is about comparing a lump sum's
*face value* to one year's pay, not about an *exemption claim* exceeding it.

**Resolved by tracing the mapper.** `app/engine/draft_to_itr1_input.py`'s salary mapper (the
function building `SalaryIncome`) settles the field-semantics question directly: `salary_input
= SalaryIncome(gross_salary=section_17_1, ...)` (line 334) — `sal.gross_salary`, the exact
field every validator reads, is set to `section_17_1` alone (basic+DA+bonus+commission+HRA
received+LTA received+other allowance+other taxable salary+arrears+uniform allowance — line
209-212), which deliberately **excludes** gratuity/commuted-pension/leave-encashment/VRS/
retrenchment. Those five are gross retirement/severance receipts (`e.commutedPension`,
`e.leaveEncashment`, etc., summed at lines 260-264) — a materially different, non-overlapping
quantity from `sal.gross_salary`. (The function does compute a *second*, separately-scoped
local also named `gross_salary` — reused for its own returned tuple, augmented with these five
receipts at lines 365-368 — but that local is never stored on `SalaryIncome` and is not what
`sal.gross_salary` means anywhere a validator reads it.) So `commuted_pension_received` and
`leave_encashment_received` are genuinely independent of `sal.gross_salary`, not a subset of
it — the comparison is not trivial or structurally guaranteed, and a taxpayer with a modest
running salary but a large one-time commuted-pension or leave-encashment payout at retirement
is a real, reachable case this schema can represent. **Conclusion: option (a)** — rules 68/69
are genuine, currently-missing Category A portal gates and should be re-implemented,
independent of the (still-correct, for its own narrower question) statutory reasoning that
removed R100-R102. Implemented in this pass as `ITR1-R068`/`ITR1-R069`, mirroring the existing
`ITR1-R064` LTA-vs-gross-salary pattern — see `app/engine/validators/itr1/input_rules.py`.

### 16.4 The 13 apparent gaps that are not real gaps (verified by reading the implementing code)

- **Rule 10** ("Schedule VIA 80G claimed > eligible donation per Schedule 80G"): implemented in
  the opposite comparison direction under a different ID —
  `calc_rules.py`'s `ITR1-R242` (`ch6a.amount_80g > eng_80g` against the engine-computed
  eligible amount) covers the same relationship `input_rules.py`'s `ITR1-R139` covers from the
  Schedule-80G-eligible side. Same relationship, two IDs, no gap.
- **Rule 71** ("10(10C) VRS amount cannot exceed ₹5,00,000"): a literal duplicate of the
  already-implemented `ITR1-R103` (same cap, same field, same regime gate).
- **Rules 296/298/299** (HP co-owned annual-value-owned = %share × AV; Schedule HP internal
  subtotal cross-foots Sl.1d = 1b+1c and Sl.1i = 1g+1h): all three are computed by direct
  formula, not by independent re-entry, so they cannot diverge — confirmed by reading both the
  calculator and the JSON builder. `app/engine/schedules/house_property.py`'s
  `compute_house_property()` computes `annual_value_owned = balance_alv *
  ownership_share_percentage / 100` (line ~114) directly from the percentage parameter (which
  `app/engine/itd/itr1.py` line 176 cross-checks against the filing profile's
  `assessee_share_percentage` and raises `ValueError` on mismatch before this formula ever
  runs) — rule 296 by construction. `app/engine/itd/itr1.py`'s `_property_schedule()` computes
  `total_deduction = standard_deduction + interest` (line 234, feeding `"TotalDeduct"` — rule
  298's Sl.1d) and derives `standard_deduction` itself from a formula that the same function
  asserts cross-foots via an explicit `raise ValueError(...)` if it doesn't (lines 229-233) —
  rule 299's Sl.1i relationship is the same class of direct-formula construction. A dedicated
  validator rule would be redundant with an assertion that already exists closer to the
  computation.
- **Rule 328** (₹5,000 late-fee tier for 234-I on revised returns with income > ₹5L, vs. ₹1,000
  otherwise): implemented and live — `app/engine/common/interest.py::compute_234i()` (lines
  158-182) computes both tiers exactly, and its own docstring cites `"CBDT Rule R328"`
  explicitly. The cross-reference script missed it because the literal string `"ITR1-R328"`
  never appears — only `"R328"` inside a docstring comment, and the enforcement lives in the
  fee calculator, not in `input_rules.py`/`calc_rules.py`, which is why `input_rules.py`'s own
  `ITR1-R324` is deliberately informational ("computed by the engine and verified in
  calc_rules"). Confirmed correct; nothing to do.

### 16.5 Rules 80/81/82/85/86/87 were functionally correct but ID-mislabeled — fixed

`input_rules.py` had **two** separate blocks implementing "each 80G table (A/B/C/D) needs
cash-or-noncash before a total" / "each row's total must cross-foot to cash+noncash", both
correctly looping over all four tables but both always reporting every violation under table
A's literal ID (`"ITR1-R079"`/`"ITR1-R084"`) regardless of which table actually failed — so a
Table-C violation reported as `"ITR1-R079"` instead of the official `"ITR1-R081"`. This never
affected blocking behavior (the check fired correctly and the return was correctly blocked in
every table), only rule-ID fidelity in the validation report. Fixed in both blocks by mapping
`donation_category` to its own official ID (`{"A": "ITR1-R079", "B": "ITR1-R080", "C":
"ITR1-R081", "D": "ITR1-R082"}` and the equivalent 084-087 map) instead of the literal.
Verified with a new test asserting a Table-B violation now reports `ITR1-R080`, not `ITR1-R079`
(`tests/test_itr1_input_validation.py::test_R080_82_85_87_80g_table_bcd_use_official_rule_ids_not_table_a`).

## 17. Official ITR-1 JSON schema constraint compliance (type/required/min-max/pattern/enum)

### 17.1 Methodology

Source: `Reference Docs by CBDT & ITD/Official JSON Schema/ITR-1_2026_Main_V1.1 (2).json`
(JSON Schema Draft-04, `additionalProperties: false` at every object level). Verified against
the actual **production** JSON-generation entrypoint — `app.engine.filing_gateway_v2.
generate_cbdt_json(draft)` — rather than hand-constructing a minimal `ITR1Input` directly (the
approach both pre-existing test files, `tests/check_schema_compliance.py` and
`tests/validate_schemas.py`, take; the latter additionally has stale hardcoded schema paths
pointing at a `Downloads\...(1).json` file that no longer exists on this machine, so it
currently cannot run at all — not fixed in this pass, noted as a low-priority pre-existing test
tooling defect). Using the real production entrypoint means every generated JSON in this check
also passed through the full mapper, the Category A input/calc validators, and the complete
filing-profile/property-profile/bank-account/TRP construction — not just the calculator core.

Two scripts (scratch only, not committed): `schema_catalog.py` walks the schema (resolving
every `$ref`) into a flat catalog of all 479 leaf properties with path, required-ness, and
every constraint keyword (`type`, `minimum`/`maximum`/`exclusiveMinimum`/`exclusiveMaximum`,
`pattern`, `enum`, `minLength`/`maxLength`, `default`, `minItems`/`maxItems`, `format`,
`multipleOf`) — 362 required, 80 with a pattern, 246 with a min/max bound, 46 with an enum.
`coverage_check.py` cross-references that catalog against the keys actually present in each
generated JSON sample to report which schema paths were never exercised.

Four deliberately diverse `ReturnDraft` fixtures were built to maximize real-pipeline coverage
in one pass, each validated with `jsonschema.Draft4Validator(schema).iter_errors(...)`:

1. Self-occupied HP + home loan, old regime, 80C/80D(flat)/80TTA/80CCD(1B), TDS1+TDS2, Section
   10 exempt-allowance rows.
2. Let-out HP with tenant, LTCG 112A via `simplified112A`, 80DD+80U disability with
   `Form10IAFiling`, TDS3, TCS, new regime, PSU employer.
3. HRA via employer `hra`+`rentPaid`, 80G donation (`100_NO_APPROVAL`, non-cash with
   IFSC+transaction ref), 80GGA, 80GGC, 80E education loan, a Tax Return Preparer.
4. Structured `Section80D`/`Category80D`/`Policy80D` for self and parents, 80EE matched to a
   `HouseProperty.HomeLoan` by lender/account number with interest at exactly ₹2,00,000 (to
   simultaneously satisfy the self-occupied cap and the "must exhaust 24(b) before claiming
   80EE" rule), 80EEB EV loan.

Every real `FilingGatewayV2Error` hit while building these four (missing loan/PRAN/80C-identifier
evidence, HRA-vs-schedule mismatch, new-regime professional-tax rejection, TRP identification-number
pattern, 80G both-cash-and-noncash, 80G eligible-amount-exceeded, 80EE/80EEA mutual exclusivity,
80EE-before-24(b)-exhausted) was a **correct rejection of an invalid fixture**, fixed by
correcting the fixture — not a product bug. Each confirms the production Category A validators
are actually wired and firing on the real pipeline, not bypassed by this test approach.

### 17.2 Result: zero schema violations across all four scenarios

`Draft4Validator(schema).iter_errors(official_json)` returned **zero errors** for all four
generated JSONs — every type, required/optional, min/max, exclusiveMinimum/exclusiveMaximum,
pattern, and enum constraint the official schema declares was satisfied in every scenario
tested. This is a strong, positive, well-evidenced finding for the specific fields these four
drafts exercised (roughly two-thirds of the schema's 479 leaf paths — see §17.3 for the rest).

### 17.3 Honest scope caveat — paths not exercised by any of the four drafts

`coverage_check.py` against the combined four samples found 186 of 479 catalog paths never
touched. The large majority are fields that are structurally "required" only *inside* an
optional parent object none of the four drafts happened to populate (e.g. Schedule 80G's
internal per-row structure wasn't touched until draft 3; 80EE/80EEA's structure needed draft
4) — a property of how the catalog script counts required-ness, not a real gap; each such
parent object *was* exercised in at least one draft, satisfying its own internal
required-fields. The paths that are genuinely never exercised by any draft, and so remain an
honest unverified gap in this specific schema-compliance check (though several are already
covered by dedicated non-schema tests elsewhere in the suite):

- `PersonalInfo.AlternateAddress` (secondary/alternate address block)
- `FilingStatus.AssesseeRep` (representative/KARTA filing details — R293/R294/R331 already
  exercise the *validator* side of this; the JSON shape itself wasn't schema-checked)
- Revised-return / notice fields: `OrigRetFiledDate`, `NoticeNo`, `NoticeDateUnderSec`,
  `ReceiptNo`, and the seventh-proviso clause-(iv) detail rows
- `PropertyDetails[].CoOwners` / `.TenantDetails` (co-ownership and tenant rows — the *code
  path* was directly read in §16.4's rule-296/298/299 check, but no draft in this pass actually
  populated `co_owners`/`tenants`, so the schema-shape itself is unverified here)
- `Schedule80EEA` specifically (80EE and 80EEA are mutually exclusive per R123, so no single
  draft can exercise both; draft 4 isolated 80EE only)
- `PensionContribution80CCC` identifier rows (Schedule 80CCC's per-row identifier/amount
  structure, relevant to R337)
- `ExemptIncAgriOthUs10Dtls` category/subcategory fields
- `ScheduleTDS3Dtls.AadhaarofTenant`

None of these produced a violation in any test that did reach them (the drafts that read
adjacent parts of the same objects passed cleanly) — they are simply untested by this specific
check, not known-broken. Recorded here rather than silently omitted, matching this document's
established practice of stating scope honestly (§9).

## 18. Continued "two similarly-named fields" pattern hunt

Per the explicit instruction to keep pushing on this method after it found the TDS2/TDS3 bug
(§15.4) and the validator keyword-matching bug (§14): a second pass searched
`app/schemas/itr1.py`'s full 349-field list programmatically for near-duplicate name pairs
(shared prefix ≥ 12 characters, similar length) as candidates, then manually verified each
plausible hit against the calculator/mapper.

The one genuinely suspicious candidate — `loan_details_80ee`/`loan_details_80eea`/
`loan_details_80eeb` (singular, `Optional["LoanDetails"]`) alongside `loan_details_80ee_list`/
`_80eea_list`/`_80eeb_list` (the canonical `List[...]` fields the mapper actually populates,
confirmed via `app/engine/draft_to_itr1_input.py` lines 1307-1442, which explicitly sets the
singular fields to `None`) — turned out to already be guarded against exactly this bug class.
`ITR1Input.loan_schedule_rows(section)` (`app/schemas/itr1.py` lines 1224-1242) is the sole
accessor every caller uses, and it explicitly `raise ValueError(...)` if the legacy singular
field is non-`None` rather than silently preferring one field over the other — the same
protective pattern `reconciled_house_properties()`/`reconciled_property_profiles()` already use
for the analogous scalar-vs-list staleness risk documented in those methods' own docstrings.
Not a bug: this is the fix pattern from §15.4 already applied proactively elsewhere in the
schema, confirming §15.4's fix was in the right spirit for future authors adding similar
legacy/canonical field pairs.

No new defect found in this pass. The other near-duplicate pairs found by the same search
(`advance_tax_paid`/`advance_tax_q1-4`, `amount_80d_preventive_self`/`_parents`,
`interest_paid_let_out`/`_self_occupied`, `medical_expense_self_senior`/`_parents_senior`,
`political_party_name`/`_pan`, `representative_email`/`_phone`, `schedule_tds2_total_claimed`/
`schedule_tds3_total_claimed`, etc.) were all confirmed to be legitimately distinct fields
(different schedules, different beneficiary categories, or a genuine self/parent or self/other
split) rather than duplicate-purpose pairs — no further action.

## 19. Summary of §16-§18 items and their disposition

1. **Rules 68/69 (§16.3) — implemented.** Resolved by tracing the mapper (not left as an open
   decision): `sal.gross_salary` is Section 17(1) only, a genuinely independent quantity from
   `commuted_pension_received`/`leave_encashment_received`, so these are real Category A
   checks. Added as `ITR1-R068`/`ITR1-R069` in `app/engine/validators/itr1/input_rules.py`,
   mirroring the existing `ITR1-R064` LTA-vs-gross-salary pattern. 4 new tests
   (`test_R068_*`, `test_R069_*`), plus the pre-existing `test_R101_*`/`test_R102_*` tests'
   docstrings updated to point at the new rule IDs that now correctly catch those exact
   scenarios.
2. **Rule-ID mislabeling for 80G tables B/C/D (§16.5) — fixed.** Both implementing blocks now
   map `donation_category` to its own official rule ID instead of always using table A's. 1 new
   test.
3. **`tests/validate_schemas.py` — fixed for ITR-1** (§17.1, §20.4). ITR-2/3 remain on their
   original hand-built-minimal-input approach and hardcoded paths — explicitly out of scope,
   see §20.4.
4. **§17.3's unexercised schema paths — the original 8 areas are now closed** (§20.5); a
   broader, newly-visible set was found while closing them and is recorded honestly, not
   fixed, in the same subsection.

### 19.1 Verification

- `pytest tests/test_itr1_input_validation.py -v -k "R068 or R069 or R080_82 or R100 or R101 or
  R102 or R103 or R064 or R142"` — 10 passed (the 6 new tests plus the 4 pre-existing tests
  whose scenarios are now also covered under the new IDs, confirmed non-conflicting).
- `pytest tests/ -k "itr1"` (excluding the pre-existing unrelated collection-error files — see
  CLAUDE.md's documented baseline) — 343 passed, no regressions.
- All four §17 schema-audit draft scripts re-run after the R068/R069/R080-082/085-087 changes:
  `Draft4Validator` — 0 schema violations in every draft, confirming the new validator checks
  don't alter the JSON shape (they're pre-compute gates, as expected) and none of the four
  fixtures happens to trip the newly-reinstated R068/R069 gates.

## 20. Remaining §11.9/§14/§17 items closed (2026-09-03, same-day follow-up)

Continuing directly from §16-19's validation-rule/schema work in this same pass: every item
§19 had left open (or newly found while closing another) was itself either fixed or explicitly,
honestly recorded as still open, per instruction to close every leftover finding.

### 20.1 Rules 68/69 already covered §16.3's gap; this subsection covers the rest

§16.3/§19 already closed the one substantive *validation-rule* gap. This section covers the
remaining *computation/architecture* gaps §14 and §11.9 had left open with reasoning on file,
plus the two low-priority test-tooling items from §17.

### 20.2 §14.1 — self-occupied interest correctly capped at Rs 30,000 for pre-1999 loans

`app/engine/schedules/house_property.py::compute()` now accepts an optional
`loan_sanction_dates: list[date | None]` parameter; if any date in the list predates 1 April
1999, the self-occupied interest cap switches from the usual
`HOUSE_PROPERTY_INTEREST_LIMIT_SELF_OCCUPIED` (Rs 2,00,000) to the new
`HOUSE_PROPERTY_INTEREST_LIMIT_SELF_OCCUPIED_PRE_1999` (Rs 30,000) constant
(`app/engine/constants.py`). `app/engine/calculators/itr1.py`'s call site resolves the relevant
loans per property from `input_data.loan_details_24b_list` (filtered by
`property_sequence_no`) and passes their `sanction_date`s through — the field was already
captured end-to-end (`HouseProperty.homeLoans[].dateOfLoan` → `LoanDetail.sanction_date`), just
never read by the calculator. A conservative choice for the near-impossible multi-loan case: if
*any* loan on the property predates the cutoff, the stricter cap applies to the property's
total interest rather than attempting a per-loan split the schema doesn't represent.

New `tests/test_house_property_schedule.py` (6 tests): default 2L cap; explicit post-1999 date
still 2L; pre-1999 date drops to 30k; an amount already under 30k is unaffected either way; the
conservative multi-loan choice; new-regime disallowance is unaffected by sanction date. Plus one
mapper-to-calculator integration test in `test_draft_to_itr1_input.py` confirming a
1998-sanctioned loan reaches the real computed `house_property_income`.

### 20.3 §14.2/§14.3 — dead code removed, warning message corrected

- `app/engine/draft_to_itr1_input.py::_map_deductions`'s dead `interest_sb` local (computed,
  never read) and its now-also-dead `_SAVINGS_KINDS` module constant (that local's only
  consumer) are removed. No behavior change — confirmed by grep that neither had any other
  reader in the function or file.
- `app/engine/calculators/itr1.py`'s 80TTB age-mismatch warning no longer reads as if it
  performs the zeroing itself ("Deduction set to Rs 0"); reworded to "This deduction will not be
  allowed," with a new comment pointing at where the real zeroing happens
  (`section_80ttb.compute_details()`). No test asserted the old exact string (checked before
  changing it).

### 20.4 §17.1 — `tests/validate_schemas.py` fixed for ITR-1

The file's ITR-1 fixture was rewritten to use the real production pipeline
(`ReturnDraft` → `filing_gateway_v2.generate_cbdt_json`) — the same methodology §17 established
— instead of a hand-built minimal `ITR1Input` fed directly to `build_itr1_json`, which had
started raising `ValueError("Bank account details are required for ITD JSON")` once the JSON
builder began requiring `filing_profile`/bank accounts that this file's original fixture never
supplied. The `SCHEMAS["ITR-1"]` path was also switched from a hardcoded
`C:\Users\Devansh\Downloads\...` path to a repo-relative one resolving into `Reference Docs by
CBDT & ITD/Official JSON Schema/`, so it no longer depends on this machine's Downloads folder
contents. **Correction to §17.1's own earlier claim**: that claim ("hardcoded schema paths...
that no longer exist on this machine, so it currently cannot run at all") was checked again
while doing this fix and found to be inaccurate — the Downloads-folder schema files do
currently exist on this machine; the actual failure was the stale fixture/JSON-builder mismatch
above, unrelated to file existence. Recorded here so a future reader trusts what was actually
verified over what an earlier pass assumed.

ITR-2/ITR-3 remain on their original hand-built-minimal-input fixtures and hardcoded Downloads
paths — both were already failing before this fix (stale `BFLossItem` field/enum values,
confirmed by re-running before touching anything) and are unrelated to ITR-1's scope per the
established form sequencing; a comment in the file now explains this explicitly so it isn't
mistaken for an oversight. `pytest tests/validate_schemas.py -v`: `test_itr1` and `test_itr4`
pass; `test_itr2`/`test_itr3` fail exactly as before (not a regression — same two tests, same
reason, unchanged by this fix).

### 20.5 §17.3 — the original 8 unexercised areas closed; a broader, newly-visible set recorded

A fifth `ReturnDraft` scenario (`schema_audit5.py`, scratch only) was built specifically to
exercise every area §17.3 had listed as untested: alternate/secondary address
(`PersonalInfo.AlternateAddress`), representative-assessee filing (`Verification.capacity =
"REPRESENTATIVE"` + `FilingStatus.AssesseeRep`), a revised return (`139(5)` +
`OrigRetFiledDate`/original acknowledgement), a co-owned let-out property with both a co-owner
and a tenant row (`PropertyDetails[].CoOwners`/`.TenantDetails`), Section 80EEA claimed in
isolation from 80EE (`Schedule80EEA`, satisfied by the same property's loan since 80EEA — unlike
the self-occupied-only Rs 2L cap under 24(b) — applies to any residential property),
`PensionContribution80CCC` identifier rows, agricultural exempt income
(`ExemptIncAgriOthUs10Dtls`), and a TDS3 row with `AadhaarofTenant` set. Re-running the coverage
check across all five samples confirms **all 8 originally-listed paths are now exercised**, with
zero schema violations in the new draft.

**One new, real validator bug surfaced while building this draft, not fixed here — flagged for
a future pass**: `ITR1-R246` (24(b) per-property interest cross-foot,
`app/engine/validators/itr1/input_rules.py` ~line 3213) compares the *legacy single-property*
`inp.house_property_income.home_loan_interest_paid` against the **sum of `loan_details_24b_list`
across every property**, not just the one it's nominally checking. For a genuine two-property
filer where each property has its own Section 24(b) loan, this fires a false-positive Category A
block (the check demands the *first* property's interest alone equal the *combined* total of
both properties' loans) — confirmed directly: the original two-property version of this draft
failed with exactly this mismatch (Rs 50,000 vs Rs 2,50,000) before being restructured to a
single property to route around it. `app/engine/validators/itr4/input_rules.py`'s `ITR4-R295` is
the same pattern, same bug, same fix needed, confirmed by reading its neighboring code (not
fixed here, ITR-4 is out of current scope per the established sequencing). This was not part of
§16's rule-by-rule cross-reference (which checks rule *coverage*, not per-rule *correctness for
multi-property inputs* — a different kind of defect) — recorded here rather than silently
worked around, matching this document's practice of surfacing what a fix's own test-building
process happens to uncover (the same way §15.4's TDS bug surfaced while chasing a different
trail).

Re-running the coverage check across all five samples together also surfaces a **broader,
previously-invisible set of ~93 still-uncovered schema paths** — not part of the original 8, and
not chased down in this pass (a materially larger undertaking than closing 8 named items):
structured per-donee-PAN blocks for all three approval categories of Schedule 80G
(`Don50PercentNoApprReqd`/`Don100PercentApprReqd`/`Don50PercentApprReqd`, each with donee
name/PAN/address/IFSC/transaction-ref sub-fields), Schedule 80D's structured per-policy
insurer/policy-number rows for senior-citizen self/family and parents categories, and Schedule
80DD/80U's structured nature-of-disability/type/dependent-type/amount blocks. None of these
produced a violation in any test that reached adjacent parts of the same objects — they are
untested by this specific check, not known-broken — recorded honestly rather than omitted,
same convention as the original 8.

### 20.6 §11.9 — uniform allowance now correctly exempted from actual-expenditure evidence

§11.9/§13.2 left this as an intentionally deferred gap: `employer.uniformAllowance` reached
taxable income (correct, not a bug) but could never be partially exempted, because Section
10(14)(i)/Rule 2BB(1)(f)'s exemption basis is *actual expenditure incurred* — a fundamentally
different formula from CEA/hostel's fixed per-child/month statutory rate immediately above it in
the same schema, so it could not be safely folded into `sec10_14i_prescribed_allowance` without
risking the wrong cap being applied.

**Fix**: a genuinely separate received/expenditure evidence pair, keeping the fixed-rate and
actual-expenditure formulas from ever touching the same input field:

- New `Employer.uniformAllowanceExpenditure` (backend `return_draft.py` and frontend
  `types.ts`/the component-local `EmployerEntry` type), with a new
  `IndianNumberInput`-backed UI field in `EmployerEntryManager.tsx` right next to the existing
  "Uniform Allowance" field, labeled "Uniform Allowance — Actual Amount Spent" with inline help
  explaining the exemption basis and that leaving it at 0 still taxes the allowance in full
  (never silently drops it). All 8 `Employer`-construction default-value sites across the
  frontend (import mappers, tests, the computation page) updated with the new field's default.
- New `SalaryIncome.uniform_allowance_received`/`.uniform_allowance_actual_expenditure` fields
  and `schedules/salary.py::_exempt_uniform_allowance(received, expenditure) ->
  min(received, expenditure)` — the actual-expenditure formula, structurally incapable of
  exceeding either bound. Included in `exempt_allowances`, and — per CBDT Rule 149, the same
  disallowed category as HRA/LTA — zeroed under the new regime alongside them (not previously
  true for CEA/hostel's *existing* exemptions, which is a separate, pre-existing, unrelated gap
  not introduced or fixed here — flagged only so it isn't mistaken for something this change
  touched).
- The mapper (`draft_to_itr1_input.py`) sums both fields across employers and wires them onto
  `SalaryIncome`, unchanged from the existing (correct) behavior of always adding the *received*
  amount to taxable income regardless of expenditure evidence.
- The JSON builder (`itd/itr1.py::_allowance_rows`) adds the computed
  `uniform_allowance_exempt` into the same official `"10(14)(i)"` bucket as `cea_exempt` — the
  official schema has one combined code for all Rule 2BB(1) allowances, so the calculator-side
  separation (needed to keep the formulas apart) correctly collapses back to one JSON figure at
  the output side, not the input side.
- New `SalaryResult.uniform_allowance_exempt` and `ITR1Result.salary_uniform_allowance_exempt`
  fields, mirroring every sibling exemption type already exposed this way.

New tests: 5 in `tests/test_salary_schedule.py` (lesser-of-received-and-expenditure; capped at
received even if more was spent; zero exemption without evidence — the received amount still
reaches income; reduces old-regime chargeable income; correctly zeroed under new regime). 2 in
`tests/test_draft_to_itr1_input.py` (received-only reaches gross salary fully taxable, matching
existing behavior; received+expenditure together reach the calculator as a real exemption,
verified via `compute_itr1`).

### 20.7 Verification

- `pytest tests/test_house_property_schedule.py tests/test_salary_schedule.py -v` — 28 passed
  (new files/additions).
- `pytest tests/test_draft_to_itr1_input.py -v -k "uniform or pre_1999"` — 3 passed.
- `pytest tests/ -k "itr1"` (same pre-existing-collection-error exclusions as every prior run) —
  345 passed (the two mapper-level tests; the schedule-level test files don't match the `itr1`
  keyword filter, hence the smaller delta here than in the full-suite number below).
- Full backend suite (same exclusion list) — 1570 passed, same 3 pre-existing failures
  (`test_tax_v2_compute.py`) as every prior run this session — no new failures.
- `npx tsc -b`, `npx vitest run` (185 passed) — both clean after the frontend field addition.
- **Browser-verified** (not just compiled): started the real backend (`run.py`) and frontend dev
  servers, signed in, opened a real ITR-1 client's Salary Income schedule, and confirmed the new
  "Uniform Allowance — Actual Amount Spent" field renders correctly next to "Uniform Allowance"
  with its help text, accepts typed input, and behaves identically to the pre-existing "Transport
  Allowance" field beside it (including the shared `IndianNumberInput` comma-formatting behavior
  on blur). No unsaved changes were submitted against the real client record. Both servers were
  stopped after verification.

## 21. Summary of open items after §20

1. **New, flagged, not fixed**: `ITR1-R246`'s (and ITR-4's identical `ITR4-R295`'s)
   single-property assumption breaks for genuine multi-property 24(b) filers (§20.5) — a real
   Category A false-positive block for an identifiable, non-rare population (any ITR-1 filer
   with two mortgaged properties). Worth prioritizing in the next validator pass.
2. **Not fixed, deliberately out of scope**: ITR-2/ITR-3's stale fixtures in
   `tests/validate_schemas.py` (§20.4) — matches the established ITR-1-first sequencing.
3. **Not fixed, deliberately out of scope**: ITR-4's identical `tds_claimed_this_year`-vs-
   `tds_claimed` validator bug (§15.4) — same sequencing reason.
4. **Recorded, not chased**: the newly-visible ~93-path broader schema-coverage gap (§20.5) —
   structured 80G/80D/80DD/80U detail blocks untested by any current draft; no known defect,
   just unverified by this specific check.
5. **No other open items remain** from §1-§20 that represent a known, live defect in ITR-1's
   compute-and-generate-JSON pipeline. The ERI portal-submission pipeline
   (`app/eri/`, `app/automation/`, `app/filing_automation/`) remains outside this document's
   scope entirely, as stated when this question was last asked directly.

## 22. `ITR1-R246` multi-property false positive — fixed (2026-09-03)

§20.5/§21 flagged this the same day it was found rather than fixing it immediately, since it
surfaced mid-way through an unrelated schema-coverage exercise; fixed in this same session's
next turn.

**Fix**: `app/engine/validators/itr1/input_rules.py`'s R246 block now iterates
`inp.reconciled_house_properties()` (the same authoritative multi-property accessor already
used by `ITR1-R336` a few hundred lines below it, and by the calculator itself) and, for each
property, filters `inp.loan_details_24b_list` to only that property's rows by
`property_sequence_no` (1-indexed, matching the calculator's own convention in
`app/engine/calculators/itr1.py`'s `hp_results` comprehension) before cross-footing. A
single-property filer sees identical behavior to before (`reconciled_house_properties()` falls
back to `[house_property_income]` when the typed list isn't used). The failure message and
`field_path` now identify which property failed (`"Property 2: ..."`,
`house_properties[1].home_loan_interest_paid`) instead of only ever referencing the legacy
single-property field name.

4 new tests in `tests/test_itr1_input_validation.py`: single property with a matching loan
passes; single property with a genuine mismatch still fails (regression fence for existing
behavior); the exact two-property bug scenario from §20.5 (property 1: Rs 50,000 interest
against its own Rs 50,000 loan; property 2: Rs 2,00,000 against its own Rs 2,00,000 loan) no
longer false-positives; a genuine mismatch on the *second* property is still caught and
correctly attributed to "Property 2", not masked by the first property's correct loan.

**Not fixed in this pass**: `app/engine/validators/itr4/input_rules.py`'s `ITR4-R295` has the
identical single-property-vs-all-properties-summed pattern (confirmed by re-reading it while
fixing R246) — left alone per the established ITR-1-first sequencing; flagged here so the ITR-4
phase doesn't have to re-discover it, matching how the analogous ITR-4 TDS bug was flagged in
§15.4.

### 22.1 Verification

- `pytest tests/test_itr1_input_validation.py -v -k "R246"` — 4 passed.
- Full backend suite (same pre-existing-exclusion list as every prior run this session) — 1574
  passed, same 3 pre-existing failures (`test_tax_v2_compute.py`) — no new failures (net +4 vs.
  the prior run, matching the 4 new tests).
- `schema_audit5.py` (the draft that originally surfaced this bug, restructured to a single
  property to route around it) re-run after the fix: still 0 schema violations — confirms the
  fix doesn't change the JSON shape, only which property-level comparison the validator makes.

## 23. Summary of open items after §22

1. **Not fixed, deliberately out of scope**: ITR-4's identical `ITR4-R295` (§22) and
   `tds_claimed_this_year`-vs-`tds_claimed` (§15.4) bugs — both flagged for the ITR-4 phase,
   matching the established ITR-1-first sequencing.
2. **Not fixed, deliberately out of scope**: ITR-2/ITR-3's stale fixtures in
   `tests/validate_schemas.py` (§20.4) — same sequencing reason.
3. **Recorded, not chased**: the ~93-path broader schema-coverage gap (§20.5) — structured
   80G/80D/80DD/80U detail blocks untested by any current draft; no known defect, just
   unverified by this specific check.
4. **Correction, superseded by §24**: item 4 as originally written here claimed no other known
   live defects remained. That claim was wrong — §24, found the same day while starting the
   ITR-4 audit, is the single most severe finding in this entire document and affected ITR-1
   too. Left here rather than silently edited, per this document's own practice of recording
   corrections instead of erasing a prior claim (see §17.1's identical treatment).
5. **Correction, superseded by §25**: a second, independent live defect (fixed) — the
   `is_government_employee` field silently denied PSU employees their Section 16(ii)
   entertainment-allowance deduction in the actual tax computation, not just the validator.
   Found during ITR-4's CBDT rules cross-reference and duplicate-ID audit; affected ITR-1 via
   shared calculator code (`app/engine/schedules/salary.py`). See §25 for the full write-up.
6. **Correction, superseded by §26**: a third, independent live defect (fixed) — the
   `NetTaxLiability`/`TotTaxPlusIntrstPay` ITD JSON fields misreported Part D's "Balance Tax
   After Relief" vs. the final total, for any return with nonzero late-filing interest or fees
   (far more common than a Section-89-relief edge case). Found during ITR-4's official FORM-flow
   verification against the gazette PDF; affected ITR-1's identical builder pattern. See §26 for
   the full write-up.
7. **Correction, superseded by §27**: a fourth, independent live defect (fixed), and the most
   directly financially material one in this document — `section_80ccd2.py`'s engine computation
   ignored the tax regime entirely, capping employer NPS contributions at the old regime's 10%
   for every non-government-employed new-regime filer instead of Finance (No. 2) Act 2024's
   correct 14% ceiling, silently denying up to 4% of salary in legitimate deduction for a common
   taxpayer profile. Found during an exhaustive re-verification of the tax-calculation flow
   (explicitly prioritized ahead of the validator-by-validator recheck). See §27 for the full
   write-up.
8. **Correction, superseded by §28**: a fifth, independent live defect (fixed), shared by ITR-1
   and ITR-4 — Section 234C never implemented the 12%/36% "safe harbor" proviso for the
   June/September advance-tax installments, over-charging statutory interest a compliant taxpayer
   does not legally owe (the opposite direction from most findings in this document, which
   understate deductions rather than overstate a charge). See §28.

## 24. CRITICAL: `filing_date` never reached the real compute pipeline — 234A/B/C interest and
234F/234-I late fees were silently zero for every ITR-1 and ITR-4 return (2026-09-03)

**Severity: the most severe finding in this document.** Found while starting the ITR-4 deep
audit (reading `draft_to_itr4_input.py`'s `filing_date=_to_date(draft.personal.dateOfBirth),
# placeholder; gateway sets filing_date` — the comment claimed a later step would overwrite it;
grepping confirmed no such step exists anywhere in `filing_gateway_v2.py`). Checking whether
ITR-1 had the equivalent "gateway sets it" step revealed it does not either, for either form —
this is a shared-root-cause bug, not an ITR-4-only one, and it directly contradicts this
document's own earlier "ITR-1 is production ready" conclusion.

### 24.1 What was actually happening

- `app/engine/draft_to_itr1_input.py` never sets `ITR1Input.filing_date`/`.due_date` at all —
  they stay at the Pydantic default (`None`).
- `app/engine/draft_to_itr4_input.py` set `ITR4Input.filing_date` to
  `_to_date(draft.personal.dateOfBirth)` — the taxpayer's **date of birth** — with a comment
  claiming the gateway would overwrite it later. It never did.
- `app/engine/filing_gateway_v2.py`'s `compute_canonical_itr1`/`compute_canonical_itr4` — the
  single dispatch point for the real production pipeline per this codebase's own architecture
  (`generate_cbdt_json(draft)`) — each call `typed_input.model_copy(update={...})` to attach
  `filing_profile`/`property_profile`/`bank_accounts`/`tax_return_preparer` before compute, but
  neither update dict included `filing_date` or `due_date`.
- `app/engine/calculators/itr1.py`/`itr4.py` both gate every interest/fee computation behind
  `if filing_date and due_date:`. For ITR-1, `filing_date` was always `None` → the gate never
  ran → `interest_234a`/`interest_234b`/`interest_234c`/`late_fee_234f`/`fees_234i` were **always
  Decimal("0")**, for every ITR-1 return generated through `generate_cbdt_json`, regardless of
  whether the taxpayer filed on time or years late. For ITR-4, `filing_date` was always the
  taxpayer's date of birth (decades before any due date) → the gate ran, saw a "filing date"
  long before the due date → same result, always zero.
- Confirmed empirically, not just by reading code: a test draft filed under Section 139(4)
  (belated) on 2027-01-15 — 5.5 months after the AY 2026-27 due date, ₹15L salary, zero TDS —
  generated an official JSON showing `"IntrstPayUs234A": 0, "IntrstPayUs234B": 0,
  "IntrstPayUs234C": 0, "LateFilingFee234F": 0, "TotalIntrstPay": 0` before the fix.

**Practical impact**: every ITR-1/ITR-4 JSON this platform has ever generated through the real
production `generate_cbdt_json` pipeline understated the taxpayer's actual statutory liability
by the full amount of interest and late fees owed — for anyone who filed late, paid tax late, or
underpaid advance tax. This is not a display bug; it is the exact number that gets uploaded to
the ITD portal as `TotalTaxPlusIntrstPay`.

### 24.2 The fix

`draft.verification.date` — the value the return already declares itself filed on (the same one
`_reject_section_after_due_date` judges the filing section against, and that becomes the CBDT
`Verification.Date`) — is the correct source for `filing_date`. `due_date` is
`get_due_date(form, assessment_year)` (already implemented, correctly form-aware: 31 July for
ITR-1, 31 August for ITR-4). Both `compute_canonical_itr1` and `compute_canonical_itr4` now
include `"filing_date"`/`"due_date"` in their `model_copy(update={...})` calls. The ITR-4
mapper's date-of-birth placeholder and stale comment are removed — `filing_date`/`due_date` are
left `None` there now, exactly matching ITR-1's mapper, since the gateway is the correct single
place to set them (a schedule/compute-input field populated once, not independently guessed by
each per-form mapper).

### 24.3 Two more bugs this fix immediately exposed, both fixed in the same pass

Wiring a real `filing_date` through for the first time made two previously-dormant code paths
reachable — the same "fixing a root cause exposes a second, previously-unreachable defect"
pattern this document has hit repeatedly (§14.5, §15.4):

- **`ITR1-R190` was coded far too broadly.** The official rule (PDF rule 190: *"Option to
  withdraw from New Tax Regime is not available after due date of filing of return as mentioned
  u/s 139(1)"*) only blocks selecting the **old** regime after the due date — the exact same
  restriction `ITR1-R151` already enforces. As coded, R190 fired for **any** regime (including a
  perfectly valid belated New Regime filing) whenever `filing_section != "139(1)"` and the
  return was late, because it was never gated on `is_old` the way R151 is. This is a pure
  implementation bug — the condition literally didn't match its own rule text — that had zero
  observable effect until `filing_date`/`due_date` became real, since `if inp.filing_date and
  inp.due_date:` was always `False` before. Fixed: gated on `is_old`, mirroring R151.
- **`compute_234f` still implemented the pre-Finance-Act-2021 three-tier structure** (₹1,000 /
  ₹5,000 / ₹10,000, with the ₹10,000 tier for filing after 31 December). That third tier was
  **removed** by the Finance Act 2021 (effective AY 2021-22 onward, still current law for AY
  2026-27) — the maximum late fee under Section 234F is ₹5,000, full stop, regardless of how
  late within the belated-filing window the return is filed. Confirmed independently by the
  official ITR-1 JSON schema itself: `LateFilingFee234F` has `"maximum": 5000` — the very first
  real late-filing scenario run after the `filing_date` fix hit exactly this ceiling
  (`compute_234f` returned 10000) and failed official schema validation outright, which is how
  this was caught. Fixed: `compute_234f` now returns `1000`/`5000` only, with no post-31-December
  branch. Two existing unit tests (`tests/test_interest_reconciliation.py`,
  `tests/test_itr4_statutory_formula_known_answers.py`) had encoded the wrong ₹10,000 "known
  answer" as their expected value — both corrected to match current law, with a comment
  explaining why.

### 24.4 Verification

- Empirical before/after: the same late-filing test draft that showed all-zero interest/fees
  before the fix now shows `IntrstPayUs234A: 5850, IntrstPayUs234B: 9750, IntrstPayUs234C: 4924,
  LateFilingFee234F: 5000, TotalIntrstPay: 25524` — and passes official JSON schema validation.
- 4 new permanent regression tests (2 per form) in `tests/test_filing_gateway_v2.py` /
  `tests/test_filing_gateway_v2_itr4.py`: `filing_date`/`due_date` reach `typed_input` correctly
  from `verification.date` for an on-time filing; a genuinely late-filed return produces
  nonzero 234A interest and the correct ₹5,000 234F fee in the real generated JSON (not a unit
  test of the formula in isolation — the full `generate_cbdt_json` path, the same one that
  shipped the bug).
- Full backend suite (same pre-existing-exclusion list as every prior run this session): 1574
  passed, same 3 pre-existing unrelated failures (`test_tax_v2_compute.py`) as every prior run —
  no new failures, confirming the fix (and the two bugs it exposed) didn't regress anything else
  in either form's pipeline.

### 24.5 Why this wasn't caught by §15.1's earlier "234A/B/C interest... computes correctly" claim

§15.1 verified the interest **formulas** (`compute_234a`/`compute_234b`/`compute_234c` in
`app/engine/common/`) directly, with `filing_date`/`due_date` supplied by hand as test
arguments — and those formulas are, and remain, correct. What was missing is not a formula bug
but a **wiring** bug: nothing between the real `ReturnDraft` a taxpayer fills in and those
correct formulas ever supplied a real filing date. A direct unit test of `compute_234a` cannot
catch a wiring gap upstream of it; only an end-to-end test through the real
`generate_cbdt_json(draft)` entrypoint — which is what the new regression tests in §24.4 do —
can. This is the same lesson §17's methodology section already drew from a different angle (why
the schema-compliance check had to use the real pipeline, not a hand-built minimal input) —
recorded here again because it is the reason this specific bug survived an otherwise thorough
audit for as long as it did.

## 25. `is_government_employee` silently denied PSU employees their Section 16(ii) entertainment-
allowance deduction — found during ITR-4's CBDT rules cross-reference (2026-09-03)

**Found while auditing ITR-4's duplicate rule IDs** (`ITR4_FRONTEND_AND_SERIALIZATION_AUDIT_AY2026_27.md`
§7.3–7.4) — two implementations of the same entertainment-allowance eligibility check disagreed
for PSU employees, and tracing the disagreement led back into `app/engine/schedules/salary.py`
and `app/engine/draft_to_itr1_input.py`, both shared by ITR-1. This directly affects ITR-1
despite this document's earlier "production ready" conclusion — recorded here in full because
that conclusion needs the correction, not just a pointer to the other document.

**The bug**: `SalaryIncome.is_government_employee`'s own docstring (`app/schemas/itr1.py`) says
it means Central/State Government **or PSU**, and is required for the Section 16(ii)
entertainment-allowance deduction. But the mapper that populates it
(`draft_to_itr1_input.py`) computed it as `natureOfEmployment in {"CGOV", "SGOV"}` —
**excluding PSU** — per a comment claiming PSU doesn't qualify, citing `section_80ccd2.py`'s
definition. That citation is correct for Section 80CCD(2)'s 14% cap and for the Section
10(10)/10(10A)/10(10AA) retirement exemptions (gratuity/commuted pension/leave encashment,
genuinely CG/SG-only by statute) but is **wrong specifically for Section 16(ii)**: the official
CBDT ITR-4 Validation Rules PDF (page 8, rules 67–68) explicitly states entertainment allowance
"will be allowed" to "Central, State Govt, & PSU employees" and disallowed only for "employees
other than Central, State Government, and PSU." One boolean field was serving two statutory
definitions that genuinely differ, and the mapper satisfied only the narrower one.

**Impact — a calculator bug, not a validator false positive**: `app/engine/schedules/salary.py`'s
`compute()` — the shared Schedule S module both ITR-1 and ITR-4 call — gates the actual
entertainment-allowance deduction on this same flag. A PSU employee under the old regime with a
genuine entertainment allowance had the deduction **silently zeroed in the real tax
computation**, overstating taxable income and tax payable, for both forms.

**Fix**: `SalaryIncome` gained a second field, `is_cg_sg_employee` (CG/SG only), used for the
80CCD(2) cap and the three retirement exemptions; `is_government_employee` keeps its documented
CG/SG/PSU meaning and is now used only for entertainment allowance. `draft_to_itr1_input.py`
computes both correctly from `natureOfEmployment`. `app/engine/calculators/itr1.py`'s
`compute_deductions(is_government_employee=...)` call (which feeds the 80CCD(2) cap) now passes
the narrow `is_cg_sg_employee` flag. The legacy flat-dict pipeline (`app/routers/tax.py`, out of
the v2 canonical scope) has no CGOV/SGOV-vs-PSU distinction in its payload, so both flags are
set from its single existing boolean there — behavior-preserving.

**Verification**: `tests/test_draft_to_itr1_input.py` and `tests/test_itr1_calculator.py` gained
tests asserting the corrected CG/SG-vs-PSU split, including a full mapper-to-calculator
integration test proving a PSU employee now gets the entertainment-allowance deduction (capped
correctly) while their 80CCD(2) claim is capped at 10%, not 14%. Full backend suite: 1601
passed, 3 pre-existing unrelated failures (`test_tax_v2_compute.py`, confirmed via `git stash`
to fail identically before this change), 1 pre-existing collection error — no regressions. Full
detail, including the exact code paths and the official-rule citation, is in
`ITR4_FRONTEND_AND_SERIALIZATION_AUDIT_AY2026_27.md` §7.4.

## 26. Real bug found and fixed: `NetTaxLiability`/`TotTaxPlusIntrstPay` JSON fields swapped in
substance — found during ITR-4's official FORM-flow verification, live in production for ITR-1
too (2026-09-03)

**Found while directly tracing the official ITR-4 gazette form PDF's Part D against the JSON
builder** — a check neither §17's JSON-schema pass nor §16's CBDT-rules cross-reference was
positioned to catch, since schema validation only checks type/shape (both fields are valid
integers either way) and the rules PDF's checks validate the *calculator's* internal
consistency, never the ITD JSON builder's field-to-field mapping against itself. Confirmed to
affect ITR-1 identically — `app/engine/itd/itr1.py::_tax_computation_itr1` has the exact same
bug pattern as ITR-4's builder, both sharing the same root confusion.

**The bug**: the official JSON schema documents `ITR1_TaxComputation.NetTaxLiability` as
`"description": "Balance Tax After Relief"` — Part D's `D7 = D5 - D6` (gross tax+cess minus
Section 89 relief, computed *before* interest/late fees are added). The builder instead
populated this field with the calculator's own `result.net_tax_liability`, which the calculator
uses as the name for a *different, larger* quantity: the fully-final total (`D11` on ITR-1's own
Part D, "Total Tax, Fee and Interest" = gross tax+cess - relief_89 + all interest + all fees) —
a pure naming coincidence between the calculator's internal variable and the
similarly-named-but-narrower-scoped official JSON field. The undocumented
`TotTaxPlusIntrstPay` field (which, by its name and position, should carry that final total) had
the mirror-image bug: computed as `gross_tax_liability + total_interest + late_fee_234f +
fees_234i`, omitting the Section 89 relief subtraction entirely.

**Confirmed empirically**: a late-filed fixture (`gross_tax_liability=257400`,
`total_interest=64479`, `late_fee_234f=5000`, `relief_89=0`) showed the JSON's
`"NetTaxLiability"` — labeled "Balance Tax After Relief" — reporting **326879** before the fix
(overstated by exactly the interest+fee amount, 69479, even with zero Section 89 relief in
play); after the fix it correctly reports **257400**, with `TotTaxPlusIntrstPay` correctly
carrying the true final total (326879) instead. **This does not require Section 89 relief to be
nonzero to manifest** — it triggers for any return with nonzero 234A/234B/234C interest or
234F/234-I fees, i.e. any late-filed return or any return with an advance-tax shortfall, far
more common than most findings in this document. The final payable/refund amount was never
wrong — that comes from a separate code path unaffected by this bug; the defect was confined to
these two intermediate Part D JSON fields misreporting their documented meaning, a real
compliance/accuracy defect in the submitted JSON itself.

**Fix**: `_tax_computation_itr1` now computes `balance_tax_after_relief = max(0,
gross_tax_liability - relief_89)` for `"NetTaxLiability"`, and reuses the
already-correctly-computed `net_tax_liability` parameter for `"TotTaxPlusIntrstPay"` instead of
re-deriving it incorrectly. No calculator changes.

**Verification**: `test_itr1_net_tax_liability_json_field_excludes_interest_and_fees`
(`tests/test_filing_gateway_v2.py`) against real late-filed `generate_cbdt_json` output, asserting
`NetTaxLiability == GrossTaxLiability - Section89`, `TotTaxPlusIntrstPay == NetTaxLiability +
TotalIntrstPay`, and `TotTaxPlusIntrstPay > NetTaxLiability` (the inequality the bug destroyed).
Full backend suite: 1603 passed, same 3 pre-existing unrelated failures, no regressions. Full
detail, including the ITR-4-side fix and the (currently-dormant) related `TotalTaxPayable`
finding, is in `ITR4_FRONTEND_AND_SERIALIZATION_AUDIT_AY2026_27.md` §9.2–9.3.

## 27. Real, financially material bug found and fixed: Section 80CCD(2) engine computation never
applied Finance (No. 2) Act 2024's 14% new-regime rate for non-government employers (2026-09-03)

**Found during a dedicated, exhaustive re-verification of the tax-calculation flow** (requested
explicitly, prioritized above the validator-by-validator recheck) by tracing every statutory cap
in `app/engine/constants.py` and each `app/engine/schedules/deductions/section_*.py` module for
regime- or category-dependent logic the *calculator* (not just the validator) might be missing —
the exact pattern the ITR-4 audit's §9 findings had already shown can hide undetected by
schema/rules validation.

**The law**: Section 80CCD(2)'s statutory ceiling on the employer's NPS contribution deduction
was 10% of salary for private-sector employers and 14% for Central/State Government employers,
under both regimes, until Finance (No. 2) Act 2024 raised the ceiling to **14% of salary for
ALL employers** — but only for assessees who have opted for the **new regime** u/s 115BAC.
Non-government employers under the **old** regime remain at 10%.

**The bug**: `app/engine/schedules/deductions/section_80ccd2.py::compute_details()` selected the
rate using only `is_government_employee` (`14%` if true, else a flat `10%`), never consulting the
`regime` parameter it already received — despite this codebase's *own* ITR-1 (`ITR1-R216`) and
ITR-4 (`ITR4-R263`) validators independently, correctly encoding the FA-2024 rule (`if is_new:
cap = salary * 0.14`, unconditionally, no employer-category check at all). This is the same class
of defect as ITR-4's `TotalTaxPayable` finding (§9.3 in the ITR-4 doc) — a validator correctly
implements a rule the calculator's own engine does not — except this one is **not dormant**:
`app/engine/calculators/itr1.py` passes real `salary`/`is_cg_sg_employee` values into
`compute_deductions()`, so the wrong 10% ceiling was **actively capping the real computed
deduction**, not just an informational check, for every non-government-employed ITR-1 filer under
the new regime with an employer NPS contribution between 10% and 14% of salary — a common
private-sector taxpayer profile.

**Confirmed empirically**: a non-government employee, salary Rs 10,00,000, employer NPS
contribution declared at Rs 1,30,000 (13% of salary, i.e. a legitimate claim under the correct
14% new-regime ceiling). Before the fix: `statutory_ceiling=100000` (old regime's 10% rate,
wrongly applied), `allowed_deduction=100000` — Rs 30,000 of a legitimate deduction silently
denied, directly overstating taxable income and tax payable. After the fix:
`statutory_ceiling=140000`, `allowed_deduction=130000` — the full legitimate claim allowed. The
old regime's 10% ceiling is confirmed unchanged and still correctly applied for old-regime
non-government filers.

ITR-4 is **not** affected in practice: its calculator never threads `salary`/
`is_government_employee` into `compute_deductions()` at all (confirmed in the ITR-4 audit's §9.3
investigation), so 80CCD(2)'s actual deduction amount for ITR-4 always came from the user-declared
figure directly, gated only by the validator (`ITR4-R263`), which was already correct. This fix
is purely an ITR-1 (and any other future caller of `section_80ccd2.compute_details` that threads
real salary/regime, e.g. a future ITR-2) correctness fix.

**Fix**: `section_80ccd2.compute_details()` now selects the rate as: `14%` if
`is_government_employee` (CG/SG, either regime); else `14%` under the new regime, `10%` under the
old regime (was: `14%`/`10%` with no regime distinction for non-government employers). Module
docstring and parameter docs updated to state the regime-dependent rule explicitly, citing the
two validators that already had it right.

**Tests added** (`tests/test_itr1_calculator.py`):
`test_80ccd2_non_govt_employer_new_regime_gets_14pct_not_10pct` (asserts the corrected 14%
ceiling and full Rs 1,30,000 allowance) and
`test_80ccd2_non_govt_employer_old_regime_stays_at_10pct` (asserts the old regime's 10% ceiling
is unchanged, same claim capped at Rs 1,00,000). Full backend suite: 1605 passed, same 3
pre-existing unrelated failures, no regressions.

## 28. Real, taxpayer-unfavorable bug found and fixed: Section 234C never implemented the
12%/36% "safe harbor" proviso for the June/September advance-tax installments — shared by ITR-1
and ITR-4 (2026-09-03)

**Found continuing the same exhaustive tax-calculation-flow re-verification** as §27, this time
tracing `app/engine/common/interest.py` (shared by both forms' calculators) formula-by-formula
against the statutory text of Sections 234A/B/C/F/234-I rather than just their headline
percentages/thresholds.

**The law**: Section 234C(1)(b)'s main clause requires cumulative advance tax of 15% by 15 June
and 45% by 15 September (for non-corporate assessees); its **proviso** grants a lower "safe
harbor": no interest is charged for the June installment specifically if at least 12% was paid by
then, nor for the September installment specifically if at least 36% was paid by then — even
though the headline requirement for those two dates is higher (15%/45%). This proviso applies
*only* to the June and September installments; December (75%) and March (100%) have no such
exception and are strictly enforced.

**The bug**: `compute_234c()` computed the shortfall against the strict 15%/45%/75%/100% cumulative
requirements at every installment, with no safe-harbor exception at all. A taxpayer who paid, say,
13% of assessed tax by 15 June — fully compliant with the law, owing zero interest for that
installment — was charged interest on the (illusory) 2% shortfall against the 15% headline figure
this code enforced instead. **This is the opposite direction from most of this document's other
findings**: it overstates a statutory interest charge the taxpayer does not legally owe, rather
than understating a deduction.

**Confirmed empirically**: paying exactly 13% by June (safe-harbor-compliant) previously produced
Rs 60 of spurious 234C interest; after the fix, Rs 0. A taxpayer one rupee short of the 12% safe
harbor is still correctly charged interest on the full 15%-headline shortfall (not just the
1-rupee gap to the safe harbor) — the proviso is a binary "did you clear the lower bar," not a
second, lower requirement level.

**Fix**: `compute_234c()` now checks, for the June and September installments only, whether
cumulative paid already clears the 12%/36% safe harbor before falling back to the strict
15%/45% shortfall calculation; December and March are unchanged (no safe harbor exists for them
in the statute).

**Tests added** (`tests/test_itr4_statutory_formula_known_answers.py`,
`test_interest_234c_section_1b_proviso_safe_harbor`): exact safe-harbor compliance (zero
interest), one rupee short of the safe harbor (full shortfall interest, not just the gap),
independent per-installment evaluation (Q1 charged even when cumulative smoothing would clear a
later quarter's safe harbor), and confirmation December has no equivalent exception. Full backend
suite: 1606 passed, same 3 pre-existing unrelated failures, no regressions. Shared module with
ITR-4 (`app/engine/calculators/itr4.py` calls the same `compute_234c`) — no ITR-4-specific
write-up needed since the fix and its correctness apply identically to both forms.

## 29. Real bug found and fixed: disabled-employee transport allowance exemption capped at half
the correct statutory amount — found during ITR-4's exhaustive rule-by-rule sweep, shared with
ITR-1 (2026-09-03)

**Found while sweeping ITR-4's `input_rules.py` rule-by-rule** (continuing after the
tax-calculation-flow priority) by cross-checking `ITR4-R105`'s hardcoded transport-allowance
ceiling (`38_400`, matching the official CBDT rule text) against
`app/engine/constants.py::TRANSPORT_ALLOWANCE_DISABLED_LIMIT` — the constant the *calculator*
actually uses for the same figure — and finding they disagreed: the constant was `19200`, exactly
half.

**The law**: Section 10(14)(ii) read with Rule 2BB(1)(f) exempts transport allowance paid to a
blind, deaf-and-dumb, or orthopedically-handicapped employee up to Rs 3,200/month = **Rs
38,400/year**. (The unrelated *general* transport allowance, historically Rs 1,600/month, was
withdrawn entirely by Finance Act 2018 and folded into the standard deduction — not a live
exemption today.) The constant's own comment had mislabeled/misapplied that withdrawn general
rate as if it were the disability-specific figure.

**Impact**: `app/engine/schedules/salary.py::_exempt_transport()` is this constant's sole
consumer (confirmed by a full-repo grep), so every disabled employee's transport allowance
exemption was silently capped at half its correct ceiling — directly overstating taxable salary
income and tax payable. Since ITR-4's mapper reuses ITR-1's `_map_salary`/salary schedule
wholesale, both forms were affected identically. This is the same pattern as §27's 80CCD(2) fix
and the ITR-4 doc's §11 57(iia) fix — a validator citing the correct figure while the
calculator's separately-sourced constant is wrong.

**Fix**: `TRANSPORT_ALLOWANCE_DISABLED_LIMIT` corrected `19200` → `38400`.

**Tests updated/added** (`tests/test_salary_schedule.py`,
`tests/test_draft_to_itr1_input.py`): a pre-existing test claiming Rs 25,000 and asserting the
wrong Rs 19,200-capped result was corrected to the right Rs 25,000 (below the true cap, no
capping should occur); a new test claims Rs 50,000 and confirms the cap now correctly bites at
Rs 38,400. Full backend suite: 1613 passed, same 3 pre-existing unrelated failures, no
regressions. Full detail: `ITR4_FRONTEND_AND_SERIALIZATION_AUDIT_AY2026_27.md` §13.
