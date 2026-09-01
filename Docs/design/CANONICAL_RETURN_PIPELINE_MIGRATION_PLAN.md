# Canonical Return Pipeline Migration Plan

## Unified preparation flow for ITR-1, ITR-4, and partially implemented ITR-2

**Status:** Phase 5 (ITR-4 canonical preparation) completed and verified. ITR-1 canonical preparation remains complete; ITR-2 remains on its partial/pre-migration flow.
**Scope:** Backend canonical pipeline, typed return models, field mapping, calculation, validation, CBDT JSON generation, legacy ITR-2 compatibility, and regression testing
**Forms:** ITR-1 AY 2026-27, ITR-4 AY 2026-27, ITR-2 AY 2026-27 partial/v2 path
**Primary objective:** Eliminate the split `compute first → enrich later` flow and make one complete canonical return representation the only source for computation and filing JSON.

### Progress at a glance

| Phase | Area | Status |
|---|---|---|
| 0 | Baseline and safety gates | ✅ Completed as part of ITR-1 migration |
| 1 | Canonical personal-profile contract | ✅ ITR-1 scope completed; cross-form generalization pending |
| 2 | Shared normalization and hashing | ⬜ Not started |
| 3 | Shared mapping-helper extraction | ⬜ Not started |
| 4 | ITR-1 complete preparation and JSON parity | ✅ Completed and manually verified |
| 5 | ITR-4 complete preparation | ✅ Completed |
| 6 | ITR-2 complete preparation | ⬜ Not started |
| 7+ | Unified gateway, builders, frontend, legacy cleanup | ⬜ Not started |

### Completed ITR-1 migration summary

The ITR-1 canonical flow now prepares the filing/profile information before calculation. The following values are available on the typed input passed to `compute_itr1()`:

- `ITR1FilingProfile` built from the canonical draft;
- property profile rows aligned with house-property rows;
- bank accounts aligned with the refund-account source data;
- verification capacity, place, declaration, and representative details;
- optional tax-return-preparer details;
- filing section, revised-return metadata, notice metadata, and seventh-proviso declarations;
- eligibility facts mapped from the draft rather than hardcoded.

The ITR-1 JSON path consumes the already-prepared `pipeline.typed_input` and no longer performs a second ITR-1 profile/property/TRP enrichment pass. Existing top-level `tax_return_preparer` and scalar/list property fields remain as compatibility projections for direct builder callers; the canonical v2 path treats the filing profile and its attached taxpayer-level data as authoritative.

Verification completed:

```text
Focused ITR-1 gateway/profile/builder/validator suite: 219 passed
Application compilation: passed
Frontend manual canonical-flow test: completed by user
```

The official CBDT wire shape remains unchanged. `PersonalInfo`, `FilingStatus`, `Verification`, `Refund.BankAccountDtls`, and optional `TaxReturnPreparer` are still emitted as separate official blocks, but ITR-1 preparation now supplies them from one effective prepared input rather than constructing them only during JSON generation.

---

## 1. Executive decision

The implementation must converge on this invariant:

```text
One persisted ReturnDraft
    → one deterministic CanonicalReturnContext
        → one complete form-specific typed input
            → one calculation result
                ├── compute summary
                └── CBDT JSON
```

The system must not have separate mapping paths for:

- calculation input;
- filing profile;
- property profile;
- bank accounts;
- verification;
- tax-return-preparer data;
- JSON-only enrichment;
- compute-only normalization.

All of these must be assembled once by the form preparer before calculation.

### Non-negotiable personal-profile requirement

`bankAccounts`, `verification`, and `taxReturnPreparer` must be explicit members of the canonical personal-information profile. They must not remain independent, late-built artifacts in the canonical domain model.

CBDT's official JSON may represent these concepts in separate wire-level blocks. That is an external schema concern, not a reason to split the internal canonical model. The architecture must therefore use:

```text
CanonicalPersonalProfile
    ├── identity
    ├── contact
    ├── primary address
    ├── alternate address
    ├── filing status
    ├── eligibility declarations
    ├── verification
    ├── tax-return-preparer
    └── bank accounts
         ↓
    form-specific typed input
         ↓
    CBDT wire adapter emits PersonalInfo,
    FilingStatus, Verification, Refund,
    and TaxReturnPreparer where required
```

The wire adapter may split the output to match the official CBDT schema, but it must read only the already-prepared profile. It must never reconstruct those values from `ReturnDraft`.

---

## 2. Current-state analysis

### 2.1 ITR-1 flow after the completed migration

```text
ReturnDraft
  → app/routers/tax_v2.py
  → compute_canonical()
  → compute_canonical_itr1()
  → draft_to_itr1_input()
  → _filing_profile(draft)
  → _property_profiles(draft)
  → _itr1_tax_return_preparer(draft)
  → attach the complete profile, property profiles, bank accounts,
    verification, and TRP to ITR1Input
  → compute_itr1()
  → ITR1Result
  → summary
```

The ITR-1 preparation step now completes the typed input before invoking the calculator. In particular, it does not calculate an incomplete input and then add official filing fields only for JSON generation.

### 2.2 ITR-1 JSON flow after the completed migration

```text
ReturnDraft
  → app/routers/client_itr_v2.py
  → generate_cbdt_json()
  → _generate_cbdt_json_itr1()
  → compute_canonical_itr1()
  → reuse pipeline.typed_input and pipeline.computation
  → ITR-1 input validation
  → ITR-1 calculation validation
  → build_itr1_json(computation, typed_input)
  → official ITR-1 schema validation
  → final digest generation
  → CBDT JSON
```

The JSON path no longer independently calls `_filing_profile(draft)`, `_property_profiles(draft)`, or `_itr1_tax_return_preparer(draft)`, and no longer performs a second ITR-1 profile-enrichment `model_copy(update={...})` operation.

### 2.3 ITR-1 taxpayer-profile ownership and official wire projection

Internally, the completed ITR-1 typed input carries one effective taxpayer-level profile. Its filing profile includes:

```text
identity: PAN, name, DOB, Aadhaar, father name, employer category
contact/address: primary and optional alternate address, mobile, email
filing status: filing section, return type, revised/notice metadata
eligibility: values mapped from the canonical ReturnDraft
verification: declaration, capacity, place, representative details
bank accounts: refund-account rows used by the prepared input
TRP: optional tax-return-preparer details
seventh proviso: relevant Section 139(1) declarations
```

The CBDT schema intentionally keeps these as separate wire blocks:

```text
ITR1FilingProfile identity/address/status
  → PersonalInfo + FilingStatus
ITR1FilingProfile verification
  → Verification
ITR1FilingProfile bank_accounts
  → Refund.BankAccountDtls.AddtnlBankDetails
ITR1FilingProfile tax_return_preparer
  → TaxReturnPreparer
```

This is a wire-format projection only. The builder reads the prepared typed input and does not read the original `ReturnDraft` or reconstruct these fields.

### 2.4 ITR-1 flow limitations that remain intentionally unchanged

The migration fixed the timing and consistency of the existing ITR-1 profile mapping; it did not complete every ITR-1 field-mapping gap. The following remain separate follow-up work:

- detailed salary nature and Section 10 row mapping;
- complete employer identity mapping;
- children/hostel allowance capture and output;
- all property identity/ownership/tenant fields where not already supported;
- multi-employer HRA single-source reconciliation;
- complete official validation Category B/D coverage;
- response-alias cleanup;
- source hashing and immutable prepared-context objects.

These are not to be described as completed by this phase. The completed change specifically establishes that the existing supported ITR-1 profile/property/bank/verification/TRP data is prepared before computation and reused during JSON generation.

### 2.3 Completed ITR-4 canonical compute path

```text
ReturnDraft
  → compute_canonical_itr4()
  → draft_to_itr4_input()
  → _itr4_filing_profile()
  → _itr4_property_profile()
  → _itr4_bank_accounts()
  → _itr4_tax_return_preparer()
  → complete ITR4Input
  → compute_itr4()
  → ITR4Result
```

The complete supported ITR-4 filing input is prepared before calculation. Filing profile, property profile, refund bank accounts, verification data, and optional TRP data are therefore available to the calculator input and are not added after computation.

### 2.4 Completed ITR-4 JSON path

```text
ReturnDraft
  → compute_canonical_itr4()
  → complete pipeline.typed_input
  → ITR-4 validators
  → build_itr4_json()
  → official schema validation
```

JSON generation reuses the exact prepared typed input returned by `compute_canonical_itr4()`; it does not perform a second `model_copy(update={...})` enrichment pass. The official builder still emits the CBDT wire-level `PersonalInfo`, property, verification, refund-bank, and optional `TaxReturnPreparer` blocks from that prepared input.

Verification completed:

```text
ITR-4 gateway + calculator + input-validation suites: 164 passed
Application compilation: passed
git diff --check: passed
```

Remaining ITR-4 limitations are unchanged: shared profile normalization, immutable canonical context/hashing, broader Category B/D coverage, and cross-form personal-profile extraction remain future work. ITR-2 still uses its partial/pre-migration JSON enrichment path.

### 2.5 Current ITR-2 v2 path

```text
ReturnDraft
  → compute_canonical_itr2()
  → draft_to_itr2_input()
  → ITR2Input
  → compute_itr2()
  → ITR2Result
```

JSON adds these later:

```text
_itr2_filing_profile(draft)
_itr2_property_filing_details(draft)
_itr2_employer_filing_details(draft)
_itr2_tds3_filing_details(draft)
```

and then mutates the calculation input with `model_copy(update={...})`.

ITR-2 additionally has a legacy flat-payload route in `app/routers/tax.py`, where `_compute_itr2_from_flat_payload()` directly constructs `ITR2Input`. This is a second input architecture and must eventually be routed through `flat_to_draft()` and the canonical ITR-2 preparer.

### 2.6 Current canonical personal-profile split

The current `ReturnDraft` has these as separate top-level members:

```text
personal
filing
bankAccounts
verification
taxReturnPreparer
```

Evidence is in `app/schemas/return_draft.py`:

```python
personal: PersonalInfo
filing: FilingStatus
bankAccounts: list[BankAccount]
verification: Verification
taxReturnPreparer: TaxReturnPreparer
```

The current form-specific input models also split them:

- ITR-1: `filing_profile`, `bank_accounts`, `tax_return_preparer`;
- ITR-2: `filing_profile`, `bank_accounts`, plus separate filing-detail arrays;
- ITR-4: `filing_profile`, `bank_accounts`, `tax_return_preparer`.

The current `ITR1FilingProfile`, `ITR2FilingProfile`, and `ITR4FilingProfile` contain identity, address, filing status, and verification fields, but bank accounts and TRP are separate fields on the enclosing input models.

This is the exact design issue to correct.

---

## 3. Target architecture

### 3.1 New canonical domain objects

Add a shared immutable canonical context layer:

```text
app/engine/canonical/
    __init__.py
    context.py
    personal_profile.py
    shared_mapping.py
    readiness.py
    hashing.py
    itr1.py
    itr2.py
    itr4.py
```

The exact package name may be adjusted to repository convention, but the responsibilities must remain distinct.

### 3.2 Canonical personal profile

Create a shared canonical profile that owns all taxpayer-level information:

```python
@dataclass(frozen=True)
class CanonicalPersonalProfile:
    """Complete taxpayer and filing profile used by every pipeline stage."""

    identity: CanonicalIdentity
    contact: CanonicalContact
    primary_address: CanonicalAddress
    alternate_address: CanonicalAddress | None
    filing_status: CanonicalFilingStatus
    eligibility: CanonicalEligibility
    verification: CanonicalVerification
    tax_return_preparer: CanonicalTaxReturnPreparer | None
    bank_accounts: tuple[CanonicalBankAccount, ...]
```

The production implementation may use frozen Pydantic models instead of frozen dataclasses. The essential properties are:

- one owner for the data;
- no mutable post-calculation enrichment;
- no `None` placeholder for required filing data in filing-ready contexts;
- explicit representation of calculation validity versus filing readiness;
- deterministic serialization for hashing.

### 3.3 Why bank, verification, and TRP belong here

These are taxpayer-level filing facts. They are not calculator schedules and must not be assembled as unrelated gateway objects.

They affect:

- whether the return is filing-ready;
- Verification output;
- refund-account output;
- TaxReturnPreparer output;
- official FilingStatus and PersonalInfo sections;
- portal submission eligibility.

They should therefore be owned by the same canonical personal profile that owns PAN, name, address, filing section, and taxpayer declarations.

The official JSON builder may emit:

```text
CanonicalPersonalProfile.identity
    → CBDT PersonalInfo

CanonicalPersonalProfile.filing_status
    → CBDT FilingStatus

CanonicalPersonalProfile.verification
    → CBDT Verification

CanonicalPersonalProfile.bank_accounts
    → CBDT Refund.BankAccountDtls

CanonicalPersonalProfile.tax_return_preparer
    → CBDT TaxReturnPreparer
```

The builder must be a pure serializer of those fields, not another mapper.

### 3.4 Prepared return context

Add a generic wrapper:

```python
@dataclass(frozen=True)
class PreparedReturn(Generic[InputT, ResultT]):
    """Complete canonical return, calculation, and readiness state."""

    form: str
    assessment_year: str
    source_hash: str
    typed_input: InputT
    computation: ResultT
    mapping_breakdown: Mapping[str, Any]
    calculation_errors: tuple[str, ...]
    filing_errors: tuple[str, ...]
    warnings: tuple[str, ...]
```

The form-specific typed input must already contain the complete personal profile before the calculator runs.

### 3.5 Form-specific prepared contexts

Keep separate calculators and typed input models:

```text
PreparedReturn[ITR1Input, ITR1Result]
PreparedReturn[ITR2Input, ITR2Result]
PreparedReturn[ITR4Input, ITR4Result]
```

Do not create one huge universal ITR input model. Share the lifecycle and taxpayer profile abstractions, not every form-specific schedule.

---

## 4. Target end-to-end flow

### 4.1 Shared flow

```text
HTTP request
  ↓
ReturnDraft validation
  ↓
form dispatch
  ↓
prepare_and_compute(draft)
  ├── normalize draft
  ├── validate reconciliation state
  ├── map shared income/tax fields
  ├── map form-specific fields
  ├── build CanonicalPersonalProfile
  │     ├── identity
  │     ├── contact/address
  │     ├── filing status
  │     ├── eligibility
  │     ├── verification
  │     ├── bank accounts
  │     └── TRP
  ├── build form-specific property/profile schedules
  ├── construct complete typed input
  ├── run input validation
  ├── calculate exactly once
  ├── run calculation validation
  ├── compute filing readiness
  └── compute source hash
       ↓
PreparedReturn
  ├── summary serializer
  └── CBDT serializer
        ↓
     official schema validation
        ↓
     digest after final assembly
```

### 4.2 ITR-1

```python
prepared = prepare_itr1(draft)
summary = build_itr1_summary(prepared)
payload = build_itr1_json_from_prepared(prepared)
```

### 4.3 ITR-4

```python
prepared = prepare_itr4(draft)
summary = build_itr4_summary(prepared)
payload = build_itr4_json_from_prepared(prepared)
```

### 4.4 ITR-2

```python
prepared = prepare_itr2(draft)
summary = build_itr2_summary(prepared)
payload = build_itr2_json_from_prepared(prepared)
```

### 4.5 Separate HTTP requests

Compute and JSON endpoints are separate requests, so the preparation function will run separately. That is acceptable because it must be deterministic.

For the same persisted draft:

```text
prepare_itrN(draft) at time A
    source_hash = H

prepare_itrN(draft) at time B
    source_hash = H
```

If the hashes differ, the draft normalization is nondeterministic and the implementation must fail tests.

---

## 5. Phasewise implementation plan

## Phase 0 — Baseline, scope freeze, and safety gates

### Objective

Create a reliable baseline before moving any production path.

### Tasks

1. Confirm the working branch and clean/dirty state.
2. Record the current versions of:
   - `ReturnDraft`;
   - ITR-1/2/4 input models;
   - filing profiles;
   - calculators;
   - JSON builders;
   - v2 routes;
   - legacy ITR-2 route.
3. Run focused existing tests for ITR-1, ITR-2, and ITR-4.
4. Run application compilation.
5. Record known baseline failures separately from migration failures.
6. Create a mapping inventory of every `ReturnDraft` field.
7. Mark each field as:
   - mapped to calculation;
   - mapped to canonical personal profile;
   - mapped to a form-specific filing schedule;
   - intentionally unsupported and rejected;
   - intentionally informational;
   - not yet implemented.

### Required artifacts

Create or update:

```text
Docs/design/CANONICAL_RETURN_FIELD_INVENTORY.md
Docs/design/CANONICAL_RETURN_PIPELINE_MIGRATION_PLAN.md
```

### Exit criteria

- Focused baseline tests are recorded.
- Every current profile constructor is identified.
- Every current `model_copy(update={...})` enrichment site is identified.
- No code behavior is changed in this phase.

---

## Phase 1 — Define the canonical personal profile contract

### Objective

Make taxpayer-level data one explicit internal object.

### Tasks

1. Add shared canonical types for:
   - identity;
   - contact;
   - address;
   - filing status;
   - eligibility declarations;
   - verification;
   - bank account;
   - tax-return-preparer;
   - representative details;
   - seventh-proviso declarations.
2. Place `verification`, `bank_accounts`, and `tax_return_preparer` inside `CanonicalPersonalProfile`.
3. Decide whether the implementation uses:
   - frozen Pydantic models; or
   - frozen dataclasses around existing Pydantic values.
4. Prefer existing validated field types where possible; do not duplicate regex and enum definitions unnecessarily.
5. Define required versus optional semantics:
   - identity required for all canonical returns;
   - calculation-only drafts may carry incomplete filing fields with readiness errors;
   - filing JSON requires all form-required personal fields;
   - bank accounts are required when the official form/result requires a refund account;
   - TRP is optional only when `used == false`;
   - verification declaration and place are required for filing JSON;
   - representative details are required when representative verification is selected.
6. Define one bank-account primary-account rule shared across ITR-1, ITR-2, and ITR-4.
7. Define one TRP validation rule shared by all forms, with form-specific wire adapters only where official field names differ.

### Important modeling decision

Do not make the canonical profile mirror CBDT's top-level JSON layout. The canonical profile should model the domain cleanly. The JSON builder then emits the official layout.

### Proposed conceptual shape

```text
ReturnDraft
  ├── personal data
  ├── filing data
  ├── verification data
  ├── TRP data
  ├── bank data
  └── income/schedule data
        ↓
CanonicalReturnDraftView
  └── personal_profile: CanonicalPersonalProfile
```

During migration, `ReturnDraft` may retain its current top-level wire-compatible fields. The preparer must immediately combine them into one canonical profile. A later schema migration may physically nest them in `ReturnDraft`, but correctness must not wait for that migration.

### Exit criteria

- Canonical personal profile can represent all currently supported ITR-1/2/4 profile fields.
- Bank, verification, and TRP are members of the same profile object.
- Unit tests cover profile construction, conditional fields, bank primary count, representative verification, and TRP validation.

---

## Phase 2 — Add shared normalization and deterministic hashing

### Objective

Ensure the same draft always produces the same effective canonical input.

### Tasks

1. Add `normalize_return_draft()`.
2. Normalize:
   - whitespace;
   - PAN casing;
   - TAN casing;
   - empty strings versus `None`;
   - dates;
   - decimal values;
   - enum representations;
   - ordering of collections where order is not semantically meaningful.
3. Preserve semantic ordering where it matters:
   - employers;
   - properties;
   - TDS rows when schedule row order matters;
   - capital-gain transactions where source order is retained.
4. Reject invalid numeric values rather than converting them silently.
5. Add a deterministic canonical serializer.
6. Hash the normalized draft/profile/schedule source using SHA-256.
7. Never include generated timestamps or digest values in the source hash.
8. Return the hash in `PreparedReturn` and optionally in API diagnostics.

### Exit criteria

- Same draft produces byte-equivalent normalized representation.
- Same draft produces the same source hash across repeated preparation.
- Changing a filing field changes the hash.
- Changing a bank account changes the hash.
- Changing verification or TRP changes the hash.
- Hash tests run on all three forms.

---

## Phase 3 — Extract shared mapping helpers from the ITR-1 mapper

### Objective

Stop treating ITR-1 as the owner of shared salary/property/tax mapping.

### Current problem

`draft_to_itr2_input.py` and `draft_to_itr4_input.py` import private helpers from `draft_to_itr1_input.py`.

This creates:

```text
ITR-2 mapper → ITR-1 mapper internals
ITR-4 mapper → ITR-1 mapper internals
```

### Tasks

Move shared helpers into:

```text
app/engine/canonical/shared_mapping.py
```

Candidate helpers include:

```text
_age_bracket_from_dob
_to_date
_map_salary
_map_hra_details
_map_house_properties
_map_other_sources
_map_capital_gains
_map_deductions
_map_deduction_loans
_map_disability_schedules
_map_80d_schedule
_map_80gga
_map_80ggc
_map_tds
_map_tds3
_map_tcs
_map_tax_payments
_map_bank_accounts
_map_24b_loans
_map_dividend_quarterly_breakdown
_map_compact_exempt_income
```

### Rules

- Preserve behavior initially.
- Do not combine form-specific schedule logic merely to reduce file count.
- Keep shared helpers form-neutral.
- Add tests before and after extraction.
- Replace private cross-module imports with imports from the neutral shared module.

### Exit criteria

- ITR-1, ITR-2, and ITR-4 no longer import shared private helpers from the ITR-1 mapper.
- Existing focused tests remain green.
- No change in calculated values is observed for known fixtures.

---

## Phase 4 — Build the complete ITR-1 preparer

### Objective

Make ITR-1 produce a complete typed input before calculation.

### New function

```python
def prepare_itr1(draft: ReturnDraft) -> PreparedReturn[ITR1Input, ITR1Result]:
    """Normalize, map, validate, calculate, and prepare an ITR-1 return."""
```

### Preparation order

1. Check `draft.form == "ITR-1"`.
2. Check pending reconciliation discrepancies.
3. Check out-of-scope taxable evidence.
4. Normalize the draft.
5. Build canonical personal profile, including:
   - PAN;
   - name;
   - DOB;
   - Aadhaar;
   - employer category;
   - address;
   - alternate address;
   - filing section;
   - revised/notice metadata;
   - seventh-proviso declarations;
   - eligibility facts;
   - verification;
   - representative details;
   - bank accounts;
   - TRP.
6. Map salary rows and employer details.
7. Map Section 10 exemption rows.
8. Resolve one authoritative HRA calculation.
9. Map house-property income and property filing profiles.
10. Map ownership, co-owner, tenant, and lender data.
11. Map other sources.
12. Map restricted 112A data and explicitly reject unsupported capital gains.
13. Map Chapter VI-A deductions.
14. Map TDS, TDS3, TCS, and tax payments.
15. Construct one complete `ITR1Input`.
16. Run input validation.
17. Calculate once.
18. Run calculation validation.
19. Calculate filing readiness.
20. Return `PreparedReturn`.

### Critical change

The following must happen before `compute_itr1()`:

```python
filing_profile = build_canonical_personal_profile(draft)
property_profiles = build_itr1_property_profiles(draft)
```

Do not calculate first and call `model_copy(update={...})` later.

### ITR-1 profile representation

Short-term migration representation:

```text
ITR1Input
  ├── personal_profile: CanonicalPersonalProfile
  ├── property_profiles
  ├── income schedules
  └── tax schedules
```

If changing the existing builder signature is too risky initially, retain a compatibility projection:

```text
CanonicalPersonalProfile
  → ITR1FilingProfile
  → builder's official PersonalInfo/FilingStatus/Verification blocks

CanonicalPersonalProfile.bank_accounts
  → ITR1Input.bank_accounts

CanonicalPersonalProfile.tax_return_preparer
  → ITR1Input.tax_return_preparer
```

The projection must occur once inside the preparer, not inside JSON generation.

### Exit criteria

- ITR-1 calculator receives the same filing/profile/bank/TRP data that JSON receives.
- No ITR-1 JSON code calls `_filing_profile(draft)` or `_property_profiles(draft)`.
- Compute and JSON use the same prepared typed input contract.
- Tests prove non-resident, director, foreign-assets, and unlisted-equity states are rejected.

---

## Phase 5 — Build the complete ITR-4 preparer

### Objective

Apply the same complete-preparation contract to ITR-4 without rewriting its calculator.

### New function

```python
def prepare_itr4(draft: ReturnDraft) -> PreparedReturn[ITR4Input, ITR4Result]:
    """Normalize, map, validate, calculate, and prepare an ITR-4 return."""
```

### Move into the preparer

- `_itr4_filing_profile()`;
- `_itr4_property_profile()`;
- `_itr4_bank_accounts()`;
- `_itr4_tax_return_preparer()`;
- Form 10-IEA mapping;
- seventh-proviso mapping;
- verification and representative checks;
- personal address mapping;
- ITR-4 eligibility/profile fields.

### ITR-4-specific considerations

- Preserve ITR-4's assessee-status support.
- Preserve presumptive-business schedule mapping.
- Preserve ITR-4-specific Form 10-IEA semantics.
- Keep ITR-4 bank wire fields compatible with the official builder.
- Convert the shared canonical bank account to `ITR4BankAccount` once in the preparer if the existing form schema requires that type.
- Do not rebuild bank accounts in `app/engine/itd/itr4.py` from the draft.

### Exit criteria

- `compute_itr4()` receives the complete profile projection before calculation.
- `_generate_cbdt_json_itr4()` no longer enriches `pipeline.typed_input`.
- ITR-4 computation and JSON use identical profile, bank, verification, and TRP values.
- Form 10-IEA tests remain green.

---

## Phase 6 — Build the complete ITR-2 preparer for the v2 path

### Objective

Remove the v2 compute/JSON split and prepare ITR-2 for eventual full production support.

### New function

```python
def prepare_itr2(draft: ReturnDraft) -> PreparedReturn[ITR2Input, ITR2Result]:
    """Normalize, map, validate, calculate, and prepare an ITR-2 return."""
```

### Move into the preparer

- `_itr2_filing_profile()`;
- `_itr2_property_filing_details()`;
- `_itr2_employer_filing_details()`;
- `_itr2_tds3_filing_details()`;
- bank-account projection from the canonical personal profile;
- verification and filing status;
- resident/RNOR/non-resident fields;
- director/unlisted-equity declarations;
- FII/FPI and SEBI data;
- Portuguese Civil Code data;
- seventh-proviso data.

### Preserve explicit ITR-2 gaps

The preparer must not silently claim full support for fields documented as incomplete. For every unsupported field:

- reject it if filing under ITR-2 requires it;
- or emit a visible unsupported-field warning;
- or add a mapping implementation before marking the phase complete.

Particular attention:

- generic capital-gain rows;
- scrips without transfer dates;
- FSI/TR/FA/SPI/PTI/AMT data;
- brought-forward losses;
- Schedule SI;
- property/employer/TDS3 row counts;
- foreign-asset and residential-status declarations.

### Exit criteria

- v2 ITR-2 compute and JSON use one complete prepared input.
- No ITR-2 JSON function calls `_itr2_filing_profile(draft)` directly.
- Every known partial mapping is visible in readiness output.
- Existing ITR-2 production-plan status is updated accurately.

---

## Phase 7 — Introduce the unified gateway lifecycle

### Objective

Reduce `filing_gateway_v2.py` to orchestration and dispatch.

### Target gateway responsibilities

```text
form dispatch
preparer invocation
summary serialization
JSON serializer dispatch
schema validation dispatch
error translation
```

### Gateway must not do

- field mapping;
- personal-profile construction;
- bank mapping;
- verification mapping;
- TRP mapping;
- property-profile construction;
- `model_copy(update={...})` enrichment;
- independent recalculation.

### Target interface

```python
def prepare_and_compute(
    draft: ReturnDraft,
) -> PreparedReturn[Any, Any]:
    """Prepare and calculate one complete canonical return."""
```

```python
def compute_canonical(
    draft: ReturnDraft,
) -> PreparedReturn[Any, Any]:
    """Dispatch to the form-specific canonical preparer."""
```

```python
def generate_cbdt_json(
    draft: ReturnDraft,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Prepare once, serialize the prepared result, and validate the schema."""
```

### JSON dispatch

```text
prepared.form == ITR-1
    → serialize_itr1(prepared)

prepared.form == ITR-2
    → serialize_itr2(prepared)

prepared.form == ITR-4
    → serialize_itr4(prepared)
```

Each serializer receives `prepared`, not `draft`.

### Exit criteria

- The gateway contains no duplicate form-profile mapping paths.
- All three supported v2 forms use the same lifecycle.
- A grep for `_itr1_filing_profile(draft)`, `_itr4_filing_profile(draft)`, and `_itr2_filing_profile(draft)` shows no JSON-path calls.
- A grep for `model_copy(update=` in the gateway finds no profile enrichment.

---

## Phase 8 — Refactor builders into pure wire serializers

### Objective

Make CBDT builders serialize prepared typed data and calculator output only.

### ITR-1 builder

Change conceptually from:

```python
build_itr1_json(result, input_data)
```

to either:

```python
build_itr1_json(prepared)
```

or:

```python
build_itr1_json(prepared.computation, prepared.typed_input)
```

The second form is acceptable only if both objects come from the same immutable `PreparedReturn`.

### ITR-2 and ITR-4 builders

Apply the same rule.

### Builder constraints

Builders may:

- transform canonical typed values into CBDT field names;
- emit conditional official blocks;
- cross-foot values already present in the prepared input/result;
- validate official schema;
- insert the final digest after complete assembly.

Builders must not:

- read `ReturnDraft`;
- call a draft mapper;
- call a profile constructor;
- invent taxpayer values;
- use placeholder identity/bank/verification values;
- recalculate tax independently;
- source bank/verification/TRP from unrelated arguments.

### Digest rule

The digest must be computed only after:

1. all schedules are assembled;
2. PersonalInfo is emitted;
3. FilingStatus is emitted;
4. Verification is emitted;
5. Refund and bank blocks are emitted;
6. TaxReturnPreparer is emitted when applicable;
7. all schema-normalization fields are present;
8. the digest field itself is excluded or handled according to the official digest algorithm.

### Exit criteria

- Builders are pure serializers.
- No builder reads the draft.
- Digest tests prove that changing a personal, bank, verification, or TRP field changes the final digest.
- JSON numeric values match the single stored calculation result.

---

## Phase 9 — Migrate the routes

### 9.1 v2 compute route

`app/routers/tax_v2.py` should call:

```python
prepared = compute_canonical(draft)
return build_summary(prepared)
```

It must not perform mapping or profile enrichment.

### 9.2 client JSON-generation route

`app/routers/client_itr_v2.py` should load the saved `ReturnDraft` and call only:

```python
payload, summary = generate_cbdt_json(draft)
```

The route should not reconstruct any profile fields.

### 9.3 legacy ITR-1 route

Audit `app/routers/itr.py`.

Preferred migration:

```text
legacy typed input
  → ReturnDraft adapter where feasible
  → prepare_itr1()
```

If backward compatibility requires direct typed input temporarily, document it as a legacy path and ensure it cannot be mistaken for the canonical v2 path.

### 9.4 legacy ITR-2 flat route

Refactor:

```text
flat payload
  → flat_to_draft()
  → prepare_itr2()
  → calculator/JSON serializer
```

Remove direct construction of `ITR2Input` from `app/routers/tax.py` after frontend callers are migrated.

### Exit criteria

- v2 routes use only canonical preparation.
- Legacy ITR-2 accepts a compatibility adapter but has one downstream pipeline.
- No route directly calls a form mapper plus a separate profile builder.

---

## Phase 10 — Fix field mapping and readiness gaps

This phase addresses the substantive field gaps found in the audit after the architecture is stable.

### ITR-1 personal fields

Implement and test:

- PAN;
- DOB;
- Aadhaar;
- employer category;
- primary address;
- alternate address;
- secondary contact data;
- father name;
- filing section;
- return type;
- acknowledgement/date;
- notice number/date;
- representative details;
- seventh-proviso declarations;
- Form 10-IEA fields where applicable;
- verification;
- bank accounts;
- TRP.

### ITR-1 salary fields

Implement or explicitly reject:

- employer name/TAN/address;
- salary nature rows;
- perquisite nature rows;
- Section 10 exemption rows;
- children education allowance;
- hostel allowance;
- uniform allowance;
- arrears;
- leave encashment;
- gratuity;
- commuted pension;
- LTA fare/journey details;
- employer NPS;
- salary TDS metadata.

### ITR-1 property fields

Implement or explicitly reject:

- address;
- property sequence;
- identification number;
- owner type;
- joint-ownership flag;
- co-owner rows;
- ownership share;
- tenant rows;
- vacancy period;
- lender details;
- loan identifiers;
- pre-construction interest;
- construction/completion information.

### ITR-2 fields

Track separately:

- full capital-gain transaction support;
- foreign assets;
- FSI/TR/SPI/PTI/AMT;
- brought-forward losses;
- Schedule SI;
- property/employer/TDS3 detail rows;
- FII/FPI declarations;
- residential status.

### ITR-4 fields

Track separately:

- Form 10-IEA cascade;
- presumptive schedules;
- assessee status;
- property profile;
- bank wire conversion;
- TRP wire conversion.

### Unsupported-field policy

No frontend field may disappear silently. Each unsupported field must be:

```text
MAPPED
REJECTED
WARNING_WITH_EXPLICIT_UI_MESSAGE
STRUCTURALLY_IGNORED_BY_FORM
```

The chosen disposition must be documented and tested.

---

## Phase 11 — Fix validation architecture and official rule coverage

### Objective

Ensure validation runs consistently after preparation and before JSON generation.

### Validation stages

```text
Draft schema validation
  ↓
Canonical profile validation
  ↓
Form input validation
  ↓
Calculation
  ↓
Calculation validation
  ↓
Filing-readiness validation
  ↓
Official JSON schema validation
```

### Calculation versus filing errors

Expose separate collections:

```text
calculation_errors
filing_errors
warnings
```

A mathematically valid draft may still be non-filing-ready. The API and UI must make that distinction explicit.

### ITR-1 rules requiring correction or audit

Continue the outstanding work on:

- R032 actual duplicate Section 10(10D) behavior;
- R037 actual duplicate Section 10(17) behavior;
- R113 strict versus informational status;
- R019 identity-match limitations;
- R212 Aadhaar-match limitations;
- R126 and R152 external proceeding limitations;
- R272–R291 coverage accuracy;
- R296/R298/R299/R324 review;
- R328 precise 234-I condition;
- Category B rules;
- Category D/Form 10E rule.

The validation matrix must not claim `339 / 339` complete coverage while Category B and D remain excluded.

### Exit criteria

- Validators receive the same prepared typed input used for calculation and JSON.
- Every warning/blocking status is explicit.
- Matrix includes Category A, B, and D.
- Rule IDs match official rules or are clearly marked as internal rules.

---

## Phase 12 — Remove old flow responsibilities

### Remove from `filing_gateway_v2.py`

Delete or replace:

- `_filing_profile(draft)`;
- `_property_profiles(draft)`;
- `_itr4_filing_profile(draft)`;
- `_itr4_property_profile(draft)`;
- `_itr4_bank_accounts(draft)`;
- `_itr4_tax_return_preparer(draft)`;
- `_itr2_filing_profile(draft)`;
- `_itr2_property_filing_details(draft)`;
- `_itr2_employer_filing_details(draft)`;
- `_itr2_tds3_filing_details(draft)`;
- any equivalent late-enrichment helpers;
- any `typed_input.model_copy(update={...})` used for profile enrichment.

These functions may temporarily delegate to preparer modules during migration, but they must not remain as independent production paths.

### Old mapper files

Do not delete immediately:

```text
app/engine/draft_to_itr1_input.py
app/engine/draft_to_itr2_input.py
app/engine/draft_to_itr4_input.py
```

First convert their public APIs into compatibility wrappers or migrate all callers.

Possible final state:

```python
def draft_to_itr1_input(draft: ReturnDraft) -> tuple[ITR1Input, dict[str, Any]]:
    """Legacy compatibility wrapper around prepare_itr1()."""
    prepared = prepare_itr1(draft)
    return prepared.typed_input, dict(prepared.mapping_breakdown)
```

The wrapper must not be used by the canonical gateway once migration is complete.

Delete a mapper file only when:

1. no production caller imports it;
2. no supported test requires its private internals;
3. compatibility consumers have migrated;
4. `git grep` confirms no remaining call path;
5. full focused tests pass.

### Legacy ITR-2 function

Delete `_compute_itr2_from_flat_payload()` only after:

```text
flat payload → flat_to_draft() → prepare_itr2()
```

is working for all supported legacy callers.

---

## Phase 13 — Frontend contract cleanup

### Objective

Make the frontend understand the canonical state and stop presenting unsupported fields as effective filing inputs.

### Tasks

1. Keep `ReturnDraft` as the frontend source model.
2. Update response types to one canonical name per result value.
3. Remove duplicate aliases such as:
   - `gti` / `grossTotalIncome` / `grossTotIncome`;
   - `totalDeductions` / `deductChapVIA`;
   - `taxPayable` / `balancePayable` / `balTaxPayable`;
   - `refund` / `refundDue`.
4. Add explicit API state:
   - `calculationValid`;
   - `filingReady`;
   - `calculationErrors`;
   - `filingErrors`;
   - `warnings`;
   - `sourceHash`.
5. Show entered but disallowed new-regime deductions as disallowed rather than displaying them as effective deductions.
6. Show unsupported ITR-1 capital-gain fields as unavailable for ITR-1.
7. Show that bank, verification, and TRP belong to the filing-readiness portion of the personal profile.
8. Prevent JSON-generation actions when required filing profile data is missing, while still allowing calculation if product requirements permit it.
9. Remove business-tab fallbacks that display irrelevant ITR-1 fields as zero-valued business results.

### Exit criteria

- UI labels distinguish calculation from filing readiness.
- No frontend result consumer depends on a deprecated alias.
- Unsupported fields have an intentional user-visible disposition.

---

## Phase 14 — Test strategy and required test matrix

### 14.1 Architecture tests

Add tests that prove:

1. `prepare_itr1(draft)` is deterministic.
2. `prepare_itr2(draft)` is deterministic.
3. `prepare_itr4(draft)` is deterministic.
4. Source hash changes when any personal-profile field changes.
5. Bank account changes affect the prepared hash and JSON.
6. Verification changes affect the prepared hash and JSON.
7. TRP changes affect the prepared hash and JSON.
8. The calculator receives a complete profile projection.
9. JSON generation does not perform late enrichment.
10. Builders do not read `ReturnDraft`.

### 14.2 Personal-profile tests

For each supported form:

- missing PAN;
- invalid PAN;
- missing DOB;
- missing address;
- alternate address required but absent;
- representative capacity without representative details;
- declaration not accepted;
- missing verification place;
- zero bank accounts;
- multiple primary bank accounts;
- no primary bank account;
- invalid IFSC;
- TRP marked used without ID/name;
- TRP marked unused with no output block;
- revised return without acknowledgement/date;
- notice return without notice number/date;
- Form 10-IEA conditional fields.

### 14.3 ITR-1 mapping tests

- non-resident rejected;
- director rejected;
- foreign assets rejected;
- unlisted shares rejected;
- Section 10 row appears in canonical input/JSON;
- children education allowance appears or is explicitly rejected;
- hostel allowance appears or is explicitly rejected;
- employer identity is preserved;
- property address preserved;
- co-owner preserved;
- tenant preserved;
- two-property profile count and order preserved;
- multiple-employer HRA calculator and JSON agree;
- zero-valued gift rows do not trigger an incorrect rejection;
- invalid TAN rows do not inflate credits;
- valid transport allowance at or below ₹38,400 accepted;
- over-limit transport allowance rejected;
- taxable LTA receipt without exemption accepted;
- TDS3 missing deduction year rejected;
- R032 and R037 actual duplicate rules tested.

### 14.4 ITR-2 mapping tests

- residential status preserved;
- director/unlisted-equity status preserved;
- foreign asset rows preserved;
- FII/FPI and SEBI data preserved;
- Portuguese Civil Code data preserved;
- property detail count matches properties;
- employer detail count matches TDS1 rows;
- TDS3 detail count matches TDS3 rows;
- unsupported generic capital gains are rejected or reported;
- missing transfer-date behavior is visible;
- full supported ITR-2 schedules produce JSON from the same prepared input.

### 14.5 ITR-4 mapping tests

- individual/HUF status behavior preserved;
- presumptive schedules preserved;
- Form 10-IEA cascade preserved;
- property profile preserved;
- bank account conversion preserved;
- TRP conversion preserved;
- verification capacity restrictions preserved.

### 14.6 Compute/JSON equivalence tests

For each form:

```text
prepared = prepare_itrN(draft)
summary = serialize_summary(prepared)
payload = serialize_json(prepared)
```

Assert that:

- salary totals match;
- property totals match;
- deductions match;
- TDS/TCS totals match;
- tax payable/refund match;
- interest and late fee match;
- filing profile values match;
- bank values match;
- verification values match;
- TRP values match;
- source hash is unchanged;
- digest is generated after final assembly.

---

## 6. File-by-file change map

### Add

```text
app/engine/canonical/__init__.py
app/engine/canonical/context.py
app/engine/canonical/personal_profile.py
app/engine/canonical/shared_mapping.py
app/engine/canonical/readiness.py
app/engine/canonical/hashing.py
app/engine/canonical/itr1.py
app/engine/canonical/itr2.py
app/engine/canonical/itr4.py
```

The implementation may combine small modules initially, but the responsibilities must remain separated.

### Refactor

```text
app/engine/filing_gateway_v2.py
app/engine/draft_to_itr1_input.py
app/engine/draft_to_itr2_input.py
app/engine/draft_to_itr4_input.py
app/engine/itd/itr1.py
app/engine/itd/itr2.py
app/engine/itd/itr4.py
app/routers/tax_v2.py
app/routers/client_itr_v2.py
app/routers/tax.py
app/routers/itr.py
app/schemas/itr1.py
app/schemas/itr2.py
app/schemas/itr4.py
app/schemas/return_draft.py
```

### Keep as specialized layers

```text
app/engine/calculators/itr1.py
app/engine/calculators/itr2.py
app/engine/calculators/itr4.py
app/engine/validators/itr1/
app/engine/validators/itr2/
app/engine/validators/itr4/
app/engine/itd/itr1_schema.py
app/engine/itd/itr2_schema.py
app/engine/itd/itr4_schema.py
```

Do not delete these as part of the canonical-flow migration.

---

## 7. Migration compatibility strategy

### Avoid a flag day

Implement the new path alongside the old path, then switch one form at a time:

```text
Phase A: ITR-1 preparer behind existing gateway API
Phase B: ITR-4 preparer behind existing gateway API
Phase C: ITR-2 v2 preparer behind existing gateway API
Phase D: remove gateway late enrichment
Phase E: retire legacy ITR-2 direct mapper
```

### Compatibility rules

- Existing public route URLs should not change during the migration.
- Existing API response fields may remain temporarily, but new canonical fields must be introduced and consumers migrated.
- Compatibility wrappers may call the new preparers.
- New code must not call compatibility wrappers.
- Do not persist multiple independently editable representations of the same return.
- If cached computed results remain, persist the source hash used to create them.

### Rollback strategy

Each form migration must be independently revertible until its equivalence tests pass.

At each phase:

1. Keep the old implementation available behind a clearly named compatibility function.
2. Compare old and new calculation outputs on fixtures.
3. Compare JSON outputs after normalizing non-semantic ordering and digest fields.
4. Switch the route only after parity is confirmed.
5. Remove the old path only after one stabilization cycle.

---

## 8. Caching and persistence rules

### Source of truth

Persist only the canonical draft as the authoritative editable source:

```text
ReturnDraft
```

Generated artifacts may be persisted, but they are derived:

```text
computed_result
computed_source_hash
cbdt_json
json_source_hash
json_digest
```

### Cache invalidation

A cached result is valid only when:

```python
cached_source_hash == prepared.source_hash
```

Any change to the following invalidates calculation and JSON caches:

- income;
- deductions;
- filing status;
- eligibility;
- address;
- verification;
- bank accounts;
- TRP;
- property profile;
- TDS/TCS/payment details.

### No stale profile artifacts

Do not persist an independently editable `ITR1FilingProfile` or `ITR4FilingProfile` alongside the draft. If legacy database columns contain these values, migrate them into the draft/profile source or treat them as read-only derived artifacts.

---

## 9. Definition of done

The migration is complete only when all of the following are true:

### Architecture

- One preparer exists for ITR-1, ITR-2 v2, and ITR-4.
- Each preparer constructs a complete typed input before calculation.
- `CanonicalPersonalProfile` owns identity, filing status, verification, bank accounts, and TRP.
- JSON builders do not read `ReturnDraft`.
- JSON builders do not construct profiles.
- Gateway does not enrich typed input after calculation.
- There is no production `model_copy(update={...})` profile-enrichment path.

### Correctness

- Compute and JSON use the same prepared source hash.
- Numeric values in summary and JSON match.
- Personal, bank, verification, and TRP values match.
- Digest is created after final schedule assembly.
- Unsupported fields are rejected or explicitly reported.

### Validation

- Calculation and filing readiness are separate states.
- ITR-1 eligibility fields are mapped from the draft.
- ITR-1 Category A/B/D coverage is accurately represented.
- False rule IDs and overstated coverage are corrected.
- TDS3, R148, and R149 regressions remain fixed.

### Legacy compatibility

- Legacy ITR-2 input is adapted into `ReturnDraft`.
- Direct flat-payload construction of `ITR2Input` is retired.
- Compatibility wrappers have no independent logic.
- Old mapper files are deleted only after no production caller remains.

### Testing

- Focused ITR-1, ITR-2, and ITR-4 tests pass.
- Compute/JSON equivalence tests pass for all three forms.
- Mapping inventory has no unclassified fields.
- Application compilation passes.
- Diff and formatting checks pass.
- Full-suite failures are either resolved or documented as pre-existing with no new failures.

---

## 10. Final recommended implementation order

Use this exact order to minimize risk:

```text
1. Baseline and mapping inventory
2. CanonicalPersonalProfile contract
3. Deterministic normalization and source hashing
4. Extract shared mapping helpers
5. Complete ITR-1 preparer
6. Switch ITR-1 compute and JSON to the preparer
7. Complete ITR-4 preparer
8. Switch ITR-4 compute and JSON to the preparer
9. Complete ITR-2 v2 preparer
10. Switch ITR-2 v2 compute and JSON to the preparer
11. Simplify filing_gateway_v2.py
12. Refactor CBDT builders into pure serializers
13. Migrate legacy ITR-2 through flat_to_draft()
14. Fix remaining field-mapping gaps
15. Complete validation Category B/D and rule-ID corrections
16. Normalize frontend response contract
17. Retire compatibility wrappers and dead mapper paths
18. Run final schema, digest, mapping, and equivalence audit
```

## Final architectural rule

```text
ReturnDraft
  → prepare complete personal profile and form input
  → calculate once
  → validate once
  → serialize summary and CBDT JSON from the same immutable prepared return
```

The official CBDT JSON may contain separate `PersonalInfo`, `FilingStatus`, `Verification`, `Refund`, and `TaxReturnPreparer` blocks. Internally, however, these must be projections of one canonical personal-information profile. That distinction preserves official schema compliance while eliminating the split representation that currently allows computation, saved drafts, and filing JSON to diverge.
