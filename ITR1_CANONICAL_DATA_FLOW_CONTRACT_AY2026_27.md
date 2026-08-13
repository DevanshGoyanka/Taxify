# ITR-1 Canonical Data-Flow Contract — AY 2026-27

**Status:** Proposed architecture freeze — review and approve before implementation

**Scope:** ITR-1 only. This is the template that ITR-2, ITR-3, and ITR-4 must later follow.

**Authority:** Official CBDT/ITD ITR-1 AY 2026-27 V1.1 JSON schema; official validation rules; current Taxify source.

---

## 1. Decision and Non-Negotiable Rule

ITR-1 must use one deterministic path:

```text
Client master
  ↓ seed only
Assessment-year return
  ↓
Canonical ITR-1 draft
  ↓
ITR-1 typed mapper
  ↓
ITR1Input
  ↓
ITR-1 computation
  ↓
Official CBDT JSON builder
  ↓
Official AY 2026-27 V1.1 schema validator
  ↓
Validated JSON artifact
  ↓
Future ITD / ERI submission
```

> The same canonical filing data must drive computation, validation, official JSON generation, and future submission. No official JSON may use placeholder taxpayer data, hidden default values, or a different data source from the computation path.

---

## 2. Current Production Blocker

### 2.1 Current actual path

```text
PersonalInfoTab collects real PAN, name, DOB, address, father name, filing data
  ↓
ReturnEditorModel → composeLegacyPayload → ClientITR.form_data
  ↓
filing_gateway._build_itr1_input_from_flat(payload)
  ↓
ITR1Input(filing_profile=None)
  ↓
build_itr1_json(result, input_data)
  ↓
legacy fallback values:
  PAN=A A A A A 0 0 0 0 A
  residenceNo=1; locality=Locality; city=City
  fatherName=FATHER; verification place=Delhi
```

### 2.2 Root cause

`app/engine/filing_gateway.py::_build_itr1_input_from_flat` maps income, deductions, TDS/TCS, and challans but does **not** create:

- `ITR1FilingProfile`;
- `FilingAddress`;
- `PostalAddress` alternate address;
- `PropertyFilingProfile`;
- official Verification facts;
- complete official FilingStatus facts.

The official builder (`app/engine/itd/itr1.py::build_itr1_json`) uses `input_data.filing_profile` when present; otherwise it falls back to placeholders. This makes current ITR-1 JSON structurally shaped but not safely fileable.

### 2.3 Required resolution

The ITR-1 mapper must create a complete typed filing profile from the stored return draft. The filing gateway must reject official JSON generation when this profile is absent or incomplete. Schema-validation failures must block generation, not be returned as warnings.

---

## 3. Canonical Ownership Model

| Entity | Purpose | Owner | Mutability |
|---|---|---|---|
| `Client` | Reusable client master defaults | Client domain | Mutable; changes seed future returns only |
| `ClientITR` | One client + one AY return, selected form, lifecycle, current draft | Return domain | Mutable until filing lock |
| `ITR1FilingProfile` | Identity, address, filing status, verification, representative/notices | ITR-1 filing domain | Mutable until final generation |
| ITR-1 schedules | Taxpayer-entered income, deductions, credits, payments | ITR-1 schedule domain | Mutable until filing lock |
| `ITR1Input` | Fully typed computation and builder input | Backend mapper | Immutable per invocation |
| `ITR1Result` | Derived schedule and tax totals | Calculator | Immutable derived output |
| Official JSON | CBDT V1.1 return artifact | Filing gateway | Immutable snapshot |
| Submission record | Future ITD/ERI lifecycle, acknowledgements | Submission domain | Append-only lifecycle |

### Client is a seed, not the filing source of truth

`Client` currently stores `pan`, `name`, `email`, `mobile`, `aadhaar`, and `dob`. A new AY return may be seeded from those fields (`GET /clients/{client_id}/itr/{year}`), but after the user opens the return, the return draft owns the filing snapshot. Editing a client later must not rewrite historical AY returns.

---

## 4. Target ITR-1 Canonical Draft

The current frontend has a normalized `ReturnDraft` plus a transitional flat compatibility envelope. The target contract does **not** require deleting the bridge immediately; it requires treating the following logical structure as authoritative.

```text
CanonicalITR1ReturnDraft
├── meta
│   ├── clientPublicId
│   ├── assessmentYear = 2026-27
│   ├── form = ITR-1
│   ├── status
│   └── taxRegime = OLD | NEW
├── filingProfile
│   ├── personal
│   ├── primaryAddress
│   ├── alternateAddress?
│   ├── filingStatus
│   ├── representative?
│   ├── verification
│   └── refundBankSelection
├── schedules
│   ├── salary
│   ├── houseProperty
│   ├── otherSources
│   ├── exemptIncome
│   ├── deductions
│   ├── ltcg112A
│   ├── tds1 / tds2 / tds3
│   ├── tcs
│   └── taxPayments
└── provenance
```

### 4.1 Filing profile contract

```text
ITR1FilingProfile
├── personal
│   ├── pan: string (official PAN)
│   ├── firstName: string, max 25
│   ├── middleName: string, max 25
│   ├── surnameOrOrgName: string, required, max 75
│   ├── dateOfBirth: YYYY-MM-DD
│   ├── employerCategory: CGOV|SGOV|PSU|PE|PESG|PEPS|PEO|OTH|NA
│   ├── aadhaarNumber?: 12 digits
│   └── fatherName: string, required, max 125
├── primaryAddress
│   ├── residenceNo: required, max 50
│   ├── residenceName?: max 50
│   ├── roadOrStreet?: max 50
│   ├── localityOrArea: required, max 50
│   ├── cityOrTownOrDistrict: required, max 50
│   ├── stateCode: official StateCode
│   ├── countryCode: official CountryCode
│   ├── pinCode?: Indian six-digit PIN
│   ├── zipCode?: max 8
│   ├── mobileCountryCode: 1..99999
│   ├── mobileNo: required
│   └── email: required
├── alternateAddress?: same postal address excluding primary contact fields
├── filingStatus
│   ├── returnFileSection: official integer enum
│   ├── dueDate: 2026-07-31 unless an official rule overrides it
│   ├── optOutNewTaxRegime: Y|N
│   ├── seventhProviso139: Y|N
│   ├── seventhProvisoDetail?
│   ├── originalAcknowledgementNumber? / originalFilingDate?
│   ├── noticeNumber? / noticeDate?
│   └── representativeAssessee?
├── verification
│   ├── declarationAccepted: true required to generate
│   ├── capacity: SELF | REPRESENTATIVE
│   ├── place: required, max 50
│   └── date?: YYYY-MM-DD
└── refund
    └── exactly one eligible bank account selected when refund is due
```

---

## 5. Current Implementation Inventory

### 5.1 Frontend boundaries

| Boundary | Current file | Current role | Target role |
|---|---|---|---|
| Client create/update | `frontend/src/api/clients.ts` | Calls client CRUD APIs | Stable client-master API |
| Return shell | `pages/ITRComputationPage.tsx` | Loads draft, creates editor model, renders tabs, save/validate/generate | Form-agnostic orchestration shell |
| Personal/filer UI | `components/PersonalInfoTab.tsx` | Collects most filing-profile facts | Sole ITR-1 filing-profile UI owner |
| Canonical editor | `domain/returns/editorModel.ts` | Holds `ReturnEditorModel`; flat update bridge | Canonical in-memory return owner |
| Adapter | `domain/returns/legacyAdapter.ts` | Flat payload → `ReturnDraft` | Transitional import adapter |
| Serializer | `domain/returns/legacySerializer.ts` | `ReturnDraft` → flat payload | Transitional persisted/API projection |
| API client | `api/itr.ts` | Save, compute, validate, generate | Transport only; no domain mutation |

### 5.2 Backend boundaries

| Boundary | Current file | Current role | Target role |
|---|---|---|---|
| Client API | `app/routers/clients.py` | Client CRUD + ownership | Client master management |
| Return API | `app/routers/client_itr.py` | GET/PUT draft, validate, generate JSON | Return lifecycle/API boundary |
| Persistence | `app/db/models.py::Client`, `ClientITR` | Client master + AY JSON blob | Store versioned canonical-draft snapshot during migration |
| Shared compute | `app/routers/tax.py::compute_tax_summary` | Maps flat payload into form engine | Transitional compute orchestration |
| Filing gateway | `app/engine/filing_gateway.py` | Form routing and compute→build pipeline | Sole official artifact gateway |
| Typed schema | `app/schemas/itr1.py::ITR1Input` | Typed ITR-1 compute/filing input | Canonical backend input contract |
| Calculator | `app/engine/calculators/itr1.py::compute` | Tax/schedule calculation | Derived results only |
| Builder | `app/engine/itd/itr1.py::build_itr1_json` | Builds official document | Deterministic typed-input + result transformation |
| Validator | `app/engine/itd/itr1_schema.py` | Runs official JSON schema validator | Mandatory final filing gate |
| Submission | `app/routers/eri.py`, `app/eri/` | Existing future/integration boundary | Must consume validated immutable artifact only |

---

## 6. Current End-to-End API and Persistence Flow

```text
1. POST /clients
   frontend clientsApi.create(payload)
   → Client row (master defaults)

2. GET /clients/{client_id}/itr/{year}
   frontend itrApi.getFormData(...)
   → if no ClientITR row: seed payload from Client
   → else: return JSON-decoded ClientITR.form_data

3. Frontend edits
   PersonalInfoTab / schedule components
   → setFormData or updateEditor
   → ReturnEditorModel
   → composeLegacyPayload(editorModel)

4. PUT /clients/{client_id}/itr/{year}
   frontend itrApi.saveFormData(...)
   → client_itr.save_client_itr
   → ClientITR.form_data = json.dumps(flat payload)
   → ClientITR.itr_type = selected form
   → status = In Progress

5. POST /tax-summary/compute?regime={OLD|NEW}
   frontend live/debounced compute
   → shared compute_tax_summary
   → tax summary used for UI only

6. POST /clients/{client_id}/itr/{year}/validate
   → basic identity checks
   → shared compute_tax_summary
   → current valid/errors response

7. POST /clients/{client_id}/itr/{year}/generate-cbdt-json
   → filing_gateway.generate_filing_artifact
   → shared compute_tax_summary
   → _build_itr1_input_from_flat
   → compute_itr1
   → build_itr1_json
   → validate_itr1_json
   → JSON download
```

### Required correction to step 7

The generated official JSON must use the **same persisted/live canonical draft** as steps 4–6. It must construct `ITR1Input.filing_profile`, never invoke a placeholder builder fallback, and treat `validate_itr1_json` failures as a blocking `422` response.

---

## 7. Exact ITR-1 Filing-Profile Field Lineage

The table below freezes the source-to-destination mapping for fields necessary to create a valid official ITR-1 filing identity.

| Domain field | Frontend source | Current flat payload key | ITR1Input destination | Official JSON path | Required? | Current state |
|---|---|---|---|---|---|---|
| PAN | PersonalInfoTab PAN | `pan` | `filing_profile.pan` | `ITR.ITR1.PersonalInfo.PAN` | Yes | Collected, mapper missing |
| First name | First Name | `firstName` | `filing_profile.first_name` | `PersonalInfo.AssesseeName.FirstName` | No | Collected, mapper missing |
| Middle name | Middle Name | `middleName` | `filing_profile.middle_name` | `PersonalInfo.AssesseeName.MiddleName` | No | Collected, mapper missing |
| Surname/org | Surname/Organisation | `surnameOrOrgName` | `filing_profile.surname` | `PersonalInfo.AssesseeName.SurNameOrOrgName` | Yes | Collected, mapper missing |
| DOB | DOB | `dob` | `filing_profile.date_of_birth` | `PersonalInfo.DOB` | Yes | Collected, mapper missing |
| Employer category | Employer Category | `employerCategory` | `filing_profile.employer_category` | `PersonalInfo.EmployerCategory` | Yes | Collected, mapper missing |
| Aadhaar | Aadhaar Number | `aadhaar` | `filing_profile.aadhaar_number` | `PersonalInfo.AadhaarCardNo` | Conditional | Collected, mapper missing |
| Father name | Father’s Name | `fatherName` | `filing_profile.father_name` | `Verification.Declaration.FatherName` | Required by builder | Collected, mapper missing |
| Residence no. | Primary address | `flatNo` | `primary_address.residence_no` | `PersonalInfo.Address.ResidenceNo` | Yes | Collected, mapper missing |
| Residence name | Primary address | `premises` | `primary_address.residence_name` | `PersonalInfo.Address.ResidenceName` | No | Collected, mapper missing |
| Road | Primary address | `road` | `primary_address.road_or_street` | `PersonalInfo.Address.RoadOrStreet` | No | Collected, mapper missing |
| Locality | Primary address | `area` | `primary_address.locality_or_area` | `PersonalInfo.Address.LocalityOrArea` | Yes | Collected, mapper missing |
| City | Primary address | `city` | `primary_address.city_or_town_or_district` | `PersonalInfo.Address.CityOrTownOrDistrict` | Yes | Collected, mapper missing |
| State | Primary address | `state` | `primary_address.state_code` | `PersonalInfo.Address.StateCode` | Yes | Collected, mapper missing |
| Country | Primary address | `country` | `primary_address.country_code` | `PersonalInfo.Address.CountryCode` | Yes | Collected, mapper missing |
| PIN | Primary address | `pincode` | `primary_address.pin_code` | `PersonalInfo.Address.PinCode` | India | Collected, mapper missing |
| ZIP | Primary address | `zipCode` | `primary_address.zip_code` | `PersonalInfo.Address.ZipCode` | Foreign | Collected, mapper missing |
| Mobile country code | Contact | `mobileCountryCode` | `primary_address.mobile_country_code` | `PersonalInfo.Address.CountryCodeMobile` | Yes | Collected, mapper missing |
| Mobile | Contact | `mobile` | `primary_address.mobile_no` | `PersonalInfo.Address.MobileNo` | Yes | Collected, mapper missing |
| Email | Contact | `email` | `primary_address.email` | `PersonalInfo.Address.EmailAddress` | Yes | Collected, mapper missing |
| Alternate address flag | Different correspondence address | `secondaryAddressDifferent` | alternate profile presence | `PersonalInfo.SecondaryAdd` | Yes | Collected, mapper missing |
| Alternate address | Alternate address controls | `alternateAddress` | `filing_profile.alternate_address` | `PersonalInfo.AlternateAddress.*` | Conditional | Collected, mapper missing |
| Filing section | Filing-status select | `filingSection` | `return_file_section` | `FilingStatus.ReturnFileSec` | Yes | Collected as label; normalize |
| Regime election | Tax Regime Election | `optOutNewTaxRegime`, `regime` | filing profile + tax regime | `FilingStatus.OptOutNewTaxRegime` | Yes | Collected; reconcile one source |
| Due date | System | `itrFilingDueDate` | filing profile / builder | `FilingStatus.ItrFilingDueDate` | Yes | Builder currently hardcodes |
| 7th proviso | Filing-status section | `seventhProviso139` | filing status | `FilingStatus.SeventhProvisio139` | Conditional | Collected; mapper/builder missing |
| 7th proviso travel | Filing-status section | `foreignTravelExpenditure` | filing status | `FilingStatus.AmtSeventhProvisio139ii` | Conditional | Collected; mapper/builder missing |
| 7th proviso electricity | Filing-status section | `electricityExpenditure` | filing status | `FilingStatus.AmtSeventhProvisio139iii` | Conditional | Collected; mapper/builder missing |
| Revised ack no. | Revised/defective flow | `originalAcknowledgementNumber` | filing status | `FilingStatus.ReceiptNo` | Conditional | Collected; mapper/builder missing |
| Original filing date | Revised/defective flow | `originalFilingDate` | filing status | `FilingStatus.OrigRetFiledDate` | Conditional | Collected; mapper/builder missing |
| Notice number | Notice flow | `noticeNumber` | filing status | `FilingStatus.NoticeNo` | Conditional | Collected; mapper/builder missing |
| Notice date | Notice flow | `noticeDate` | filing status | `FilingStatus.NoticeDateUnderSec` | Conditional | Collected; mapper/builder missing |
| Representative flag | Representative control | `assesseRepFlg` | filing status / verification capacity | `FilingStatus.AsseseeRepFlg` | Yes | Collected; normalize Y/N |
| Representative details | Representative controls | `representativeAssessee` | filing profile representative | `FilingStatus.AssesseeRep.*` | Conditional | Collected; mapper/builder missing |
| Declaration accepted | Verification panel (new) | `verification.declarationAccepted` | filing profile verification | `Verification.Declaration.*` | Yes | Canonical type exists; UI missing |
| Capacity | Verification panel (new) | `verification.capacity` | `verification_capacity` | `Verification.Capacity` | Yes | Canonical type exists; UI missing |
| Place | Verification panel (new) | `verification.place` | `verification_place` | `Verification.Place` | Yes | Canonical type exists; UI missing |
| Date | Verification panel (new) | `verification.date` | verification date | ITR-1 does not require Date | Optional | Canonical type exists; UI missing |
| Bank accounts | BankAccountManager | `bankAccountData.accounts` / `bankAccountDetails` | typed bank/refund schedule | `Refund.BankAccountDtls` | Required | Collected; mapper path incomplete |

---

## 8. Filing Section Normalization Contract

The UI may display human-readable labels, but the canonical mapper must use official integer values.

| UI label | Canonical `ReturnFileSec` | ITR-1 allowed? |
|---|---:|---|
| `139(1)` | 11 | Yes |
| `139(4)` | 12 | Yes |
| `142(1)` | 13 | Yes |
| `148` | 14 | Yes |
| `153C` | 15 | Yes |
| `139(5)` | 16 | Yes |
| `139(9)` | 17 | Yes |
| `119(2)(b)` | 20 | Yes |

Rules:

1. UI labels must map through one immutable mapping constant.
2. The canonical filing-profile value is the integer code.
3. Legacy saved drafts with strings remain readable through a migration adapter.
4. `assesseRepFlg`, `seventhProviso139`, and `optOutNewTaxRegime` serialize as official `Y`/`N`, not booleans.

---

## 9. ITR-1 Mapper Contract

### 9.1 Mapper signature

```python
def _build_itr1_input_from_flat(payload: dict[str, Any]) -> ITR1Input:
    ...
```

This remains the in-place mapper selected for Slice 1. It is the only permitted flat-to-typed ITR-1 boundary.

### 9.2 Mapper responsibilities

1. Normalize legacy/flat aliases once.
2. Build `ITR1FilingProfile` from filing-profile data.
3. Build `PropertyFilingProfile` when a property schedule is reportable.
4. Build typed income/deduction/credit/payment inputs.
5. Reject incomplete official-filing data when called by official JSON generation.
6. Preserve draft permissiveness for ordinary live computation only where the gateway is not generating JSON.

### 9.3 Mapper must not

- invent PAN, address, name, father name, verification place, bank account, or filing section;
- silently coerce invalid official values to unrelated defaults;
- discard an entered array row;
- calculate tax totals that belong to the calculator;
- directly build JSON;
- read client master data after the return payload has been created, except as an explicit first-draft seed before return persistence.

### 9.4 Required mapper outputs

```text
ITR1Input
├── filing_profile: required for official generation
├── property_profile: required when Schedule HP property details must be emitted
├── salary_income
├── house_property_income
├── other_sources_income
├── deductions_chapter6a and detailed deduction schedules
├── capital_gains (restricted 112A only)
├── tds1_entries / tds2_entries / tds3_entries
├── tcs_entries
├── advance/self-assessment payment entries
├── bank/refund details
└── filing/computation dates and relief values
```

---

## 10. Official JSON Builder Contract

`app/engine/itd/itr1.py::build_itr1_json(result, input_data)` is a deterministic projection. It receives only typed input and computed result.

### Allowed behavior

- Derive totals from `ITR1Result`.
- Convert typed filing profile values to official CBDT paths.
- Omit optional schedules only when officially inapplicable/empty.
- Cross-foot schedule values and reject inconsistent facts.

### Prohibited behavior

- Use placeholder personal identity in the filing-gateway path.
- Override typed taxpayer facts with function defaults.
- Turn schema-validation errors into warnings.
- Recompute independent tax rules outside the calculator.

### Mandatory official JSON top-level nodes

For a valid ITR-1 artifact, the builder must produce:

```text
ITR.ITR1
├── CreationInfo
├── Form_ITR1
├── PersonalInfo
├── FilingStatus
├── ITR1_IncomeDeductions
├── ITR1_TaxComputation
├── TaxPaid
├── Refund
└── Verification
```

Optional schedules are emitted only when populated/applicable: `LTCG112A`, `Schedule80C`, `Schedule80D`, `Schedule80DD`, `Schedule80E`, `Schedule80EE`, `Schedule80EEA`, `Schedule80EEB`, `Schedule80G`, `Schedule80GGA`, `Schedule80GGC`, `Schedule80U`, `ScheduleEA10_13A`, `ScheduleTCS`, `ScheduleTDS3Dtls`, `TDSonOthThanSals`, `TDSonSalaries`, `TaxPayments`, `TaxReturnPreparer`.

---

## 11. Validation Ownership Matrix

| Validation category | Primary owner | Examples |
|---|---|---|
| Immediate field syntax | Frontend | PAN, Aadhaar, PIN, IFSC, email, dates, maxlength |
| Conditional UI completeness | Frontend + backend mapper | Revised return requires receipt/date; rep=Y requires representative details; verification declaration/place required |
| Canonical typed validity | Pydantic `ITR1Input` and nested models | typed dates, enums, address requirements, monetary bounds |
| Tax/computation rules | ITR-1 calculator and schedule calculators | regime handling, 80C/80D caps, tax, rebate, cess, TDS credits |
| Official cross-field filing rules | filing gateway + official builder | filing-section dependencies, bank/refund consistency, Schedule HP / loan evidence |
| Official document structure | `validate_itr1_json` | official V1.1 Draft-4 schema |
| Submission rules | future ERI adapter | authentication, submission state, server acknowledgement |

**Rule:** official schema validation is a hard generation gate. It must return `422` with path-specific errors; it must never yield a downloadable filing artifact with warnings.

---

## 12. Persistence Contract

### 12.1 Current database records

```text
Client
  public_id, user_id, pan, name, email, mobile, aadhaar, dob, portal_password

ClientITR
  client_id, year, itr_type, status, form_data, computed_result
```

### 12.2 Transitional persistence model

Until a schema-versioned canonical JSON column is introduced:

- `ClientITR.form_data` remains the persisted draft payload.
- It must contain a `contractVersion`, defaulting legacy rows to `legacy-flat-v1`.
- New ITR-1 drafts should persist `contractVersion: "itr1-canonical-v1"`.
- `legacyAdapter` reads legacy fields and maps them into the canonical editor model.
- `legacySerializer` may continue emitting compatibility aliases, but canonical data must win on collision.
- `ClientITR.computed_result` remains a cache only, never a filing source of truth.

### 12.3 No silent client-master overwrite

A saved AY return must never be regenerated by re-reading mutable `Client` details. The actual return-draft snapshot is the source for official JSON.

---

## 13. Return Lifecycle and API Contract

| Transition | Endpoint | Input | Output | Required validation |
|---|---|---|---|---|
| Create client | `POST /clients` | Client master fields | Client with public ID | PAN/name syntax |
| Open/seed return | `GET /clients/{id}/itr/{year}` | client+AY | saved draft or client seed | ownership |
| Save draft | `PUT /clients/{id}/itr/{year}` | complete draft projection | status `DRAFT` | ownership, draft shape |
| Live compute | `POST /tax-summary/compute` | draft projection | derived summary | computation-input validation |
| Validate filing | `POST /clients/{id}/itr/{year}/validate` | draft projection | `valid`, errors, warnings | filing-profile + compute rules |
| Generate JSON | `POST /clients/{id}/itr/{year}/generate-cbdt-json` | live/persisted draft | validated official JSON | all mandatory gates |
| Submit future artifact | ERI/ITD endpoint | immutable validated artifact | acknowledgement/status | submission-specific rules |

### Status transition rules

```text
NOT_STARTED → DRAFT on first successful save
DRAFT → VALIDATED only when filing validation passes
VALIDATED → JSON_GENERATED only when schema validation passes
JSON_GENERATED → SUBMISSION_PENDING on submit action
SUBMISSION_PENDING → SUBMITTED or SUBMISSION_FAILED
SUBMITTED → ACKNOWLEDGED when acknowledgement is received
```

A draft can move back to `DRAFT` after an edit. A generated/submitted artifact must remain immutable and retain its content digest.

---

## 14. Required ITR-1 Invariants

1. One client + one assessment year has at most one current return (`uq_client_itr_client_year`).
2. Form selected by the taxpayer is persisted exactly; it is not inferred from a few income values.
3. The return draft owns the filing-profile snapshot after seed.
4. `filing_profile` is required for ITR-1 official JSON generation.
5. Placeholder identity values are forbidden in gateway-generated JSON.
6. PersonalInfo PAN equals verification PAN and return draft PAN.
7. `Verification.declarationAccepted` must be true; capacity and place must be present.
8. Filing-section code is official integer internally; labels are presentation only.
9. Boolean filing flags are `Y`/`N` at the official mapper boundary.
10. Exactly one refund account is selected when refund is due; selected account must have valid bank fields.
11. Arrays are preserved in full through adapter, editor model, serializer, mapper, and builder.
12. The same typed input instance drives calculator and official builder for a generation request.
13. Official V1.1 schema failure blocks download and submission.
14. Computed totals are derived only; user controls never become an alternative source for derived fields.
15. Every official required field has a UI owner, canonical field, mapper rule, validation owner, and JSON destination.

---

## 15. ITR-1 Production Slices After Contract Approval

### Slice 1 — Filing profile and Verification

- Add Verification capture inside existing `PersonalInfoTab`.
- Construct `ITR1FilingProfile`, `FilingAddress`, and alternate `PostalAddress` in `_build_itr1_input_from_flat`.
- Pass real identity, filing status, and verification data to official builder.
- Make missing profile / schema validation blocking failures.
- Golden result: real PAN/name/address/father/verification in a schema-valid ITR-1 JSON.

### Slice 2 — Filing-section normalization and regime integrity

- Store/normalize official return-section integer code.
- Normalize official `Y`/`N` flags.
- Prevent stale old-regime deductions from affecting new-regime computation and JSON.

### Slice 3 — Missing ITR-1 filing schedules

- Schedule 80GGA.
- Schedule 80GGC.
- Tax Return Preparer.

### Slice 4 — Credits, payments, refund

- Full Schedule TDS3 details.
- Typed bank/refund mapping into `Refund.BankAccountDtls`.
- Advance/self-assessment tax official schedule completeness.

### Slice 5 — HRA and cross-field validation

- Schedule EA10_13A.
- Co-owner share, donation PAN, disability evidence, PRAN, tax-credit reconciliation, and house-property cross-field rules.

### Slice 6 — Final production gate

- Final ITR-1 readiness checklist within existing workflow (no extra tab required).
- Golden test suite.
- Schema-validation CI gate.
- Remove dead/legacy code only after compatibility verification.

---

## 16. Required Golden Tests

| Case | Required proof |
|---|---|
| ITR-1 salary-only | Real personal profile + verification; official JSON validates |
| Salary + deductions + refund | 80C/80D/80G, TDS, bank refund selection; JSON validates |
| Revised / defective return | return section, acknowledgement, original filing date; JSON validates |
| Seventh-proviso filer | flag and applicable amount/detail path; JSON validates |
| HRA + house property | Schedule EA10_13A and property data cross-foot; JSON validates |
| TDS3 + TCS + challans | all credits/payments retained and reconcile; JSON validates |
| Invalid profile | generation returns path-specific 422, never placeholder JSON |

Each test must assert:

```text
frontend canonical draft
  → serialized persisted payload
  → _build_itr1_input_from_flat
  → ITR1Input
  → compute_itr1
  → build_itr1_json
  → validate_itr1_json
```

---

## 17. Explicit Migration Decisions

| Concern | Frozen decision |
|---|---|
| Existing flat drafts | Read through `legacyAdapter`; no destructive migration required in Slice 1 |
| Existing display labels for return section | Keep UI labels; normalize in mapper through one mapping constant |
| Existing `verification` canonical type | Reuse it; UI writes `declarationAccepted`, `capacity`, `place`, `date` |
| ITR-1 verification capacity | Current typed backend supports `S`; representative filing requires explicit backend support before official generation is allowed |
| Client changes after return starts | Do not overwrite return profile automatically |
| Compatibility fields | Preserve during transition; canonical fields override them |
| Schema validator warnings | Convert to blocking generation errors |
| Builder placeholder path | Retain only for isolated legacy tests, prohibit through filing gateway |
| Submission | Do not submit a draft or a non-schema-valid document; submission uses immutable generated artifact only |

---

## 18. Contract Approval Gate

Implementation of Slice 1 may begin only after approval of these decisions:

- [ ] `Client` is seed-only after return creation.
- [ ] Filing profile is a first-class ITR-1 draft concept.
- [ ] Existing Personal Info tab owns Verification capture; no additional tab is needed.
- [ ] `_build_itr1_input_from_flat` remains the in-place ITR-1 mapper.
- [ ] `ITR1Input.filing_profile` is mandatory for official JSON generation.
- [ ] Placeholder identity is prohibited in filing gateway output.
- [ ] Official schema validation blocks official JSON generation.
- [ ] Human-friendly UI labels normalize at the mapper boundary.
- [ ] The same typed input drives calculation and JSON builder.
- [ ] Future ITR-2/3/4 pipelines follow this exact architectural pattern.

---

## 19. Immediate Implementation Baseline

When this contract is approved, Slice 1 has exactly four code-level objectives:

1. Add Verification controls within `PersonalInfoTab`.
2. Ensure verification survives `ReturnDraft → legacy payload → ReturnDraft` round-trips.
3. Extend `_build_itr1_input_from_flat` in place to construct the typed `ITR1FilingProfile` and addresses from existing payload fields.
4. Make `generate_filing_artifact(..., include_official_json=True)` reject absent filing profiles and schema-validation errors.

No unrelated ITR-2/3/4 work should be mixed into Slice 1.

---

## 20. Source Files Governed by This Contract

| Layer | Files |
|---|---|
| Frontend client APIs | `frontend/src/api/clients.ts`, `frontend/src/api/itr.ts` |
| Frontend return shell | `frontend/src/pages/ITRComputationPage.tsx`, `frontend/src/pages/ITRComputationTabs.tsx` |
| Frontend filing UI | `frontend/src/components/PersonalInfoTab.tsx`, `frontend/src/components/BankAccountManager.tsx` |
| Frontend canonical/bridge | `frontend/src/domain/returns/types.ts`, `factory.ts`, `editorModel.ts`, `legacyAdapter.ts`, `legacySerializer.ts` |
| Backend client/return routes | `app/routers/clients.py`, `app/routers/client_itr.py`, `app/routers/tax.py` |
| Backend persistence | `app/db/models.py`, `app/schemas/clients.py` |
| Filing gateway | `app/engine/filing_gateway.py` |
| ITR-1 typed contract | `app/schemas/itr1.py` |
| ITR-1 calculator | `app/engine/calculators/itr1.py` |
| ITR-1 official builder | `app/engine/itd/itr1.py` |
| ITR-1 schema validation | `app/engine/itd/itr1_schema.py` |
| Future submission boundary | `app/routers/eri.py`, `app/eri/` |

---

**End of contract.**
