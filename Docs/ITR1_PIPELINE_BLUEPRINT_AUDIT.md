# ITR-1 PIPELINE AUDIT — The Production-Ready Blueprint for ITR-4

**Purpose:** Document the exact ITR-1 (Sahaj) production flow end-to-end so the ITR-4 (Sugam) pipeline can be brought to the same standard.

**AY:** 2026-27 · **Schema:** `ITR-1_2026_Main_V1.1 (2).json` · **Repository:** `C:\Users\Devansh\Desktop\Taxify`

---

## 1. The Canonical 7-Stage Pipeline

```
┌─────────────────────────────────────────────────────────────────────┐
│  1. Pydantic Typed Input          (app/schemas/itr1.py)              │
│     ITR1Input → filing_profile, property_profile(s), bank_accounts  │
│     → schedule_80c_entries, schedule_80e_entries, loan lists         │
│     → tds1/2/3_entries, tcs_entries, tax_payment_entries             │
│     → hra_details, schedule_80d, schedule_80gga/ggc, etc.            │
├─────────────────────────────────────────────────────────────────────┤
│  2. CBDT Category-A Input Rules  (validators/itr1/input_rules.py)    │
│     run_input_validation(body) → ValidationReport                   │
│     .can_upload == False → HTTP 400 with blocking_errors            │
├─────────────────────────────────────────────────────────────────────┤
│  3. Calculator                   (engine/calculators/itr1.py)        │
│     compute_itr1(body) → ITR1Result (dataclass)                     │
│     schedules: {salary, hp, os, deductions, tds_tcs, capital_gains} │
│     .errors non-empty → HTTP 400                                    │
├─────────────────────────────────────────────────────────────────────┤
│  4. CBDT Category-A Calc Rules   (validators/itr1/calc_rules.py)    │
│     run_calc_validation(body, result) → ValidationReport             │
│     .can_upload == False → HTTP 400 with blocking_errors            │
├─────────────────────────────────────────────────────────────────────┤
│  5. ITD JSON Builder             (engine/itd/itr1.py, 1795 lines)    │
│     build_itr1_json(result, input_data) → {"ITR":{"ITR1":{…}}}      │
│     Reads typed input_data for: PersonalInfo, FilingStatus,         │
│     Verification, Schedule80C/D/DD/U/E/EE/EEA/EEB/G/GGA/GGC,         │
│     TDS1/2/3, TCS, TaxPayments, ScheduleEA10_13A, PropertyDetails,  │
│     BankAccountDtls, TaxReturnPreparer                             │
│     Raises ValueError on incomplete evidence (no soft warnings)     │
├─────────────────────────────────────────────────────────────────────┤
│  6. Official Schema Validation   (engine/itd/itr1_schema.py)        │
│     validate_itr1_json(document) → None | ITR1SchemaValidationError │
│     Draft4Validator against ITR-1_2026_Main_V1.1.json              │
│     Hard fail → HTTP 400 with errors[]                              │
├─────────────────────────────────────────────────────────────────────┤
│  7. Digest + Return               (engine/itd/common.py)             │
│     _compute_digest(itr1) — HMAC-SHA256 base64 (44 chars)           │
│     Returns {"ITR":{"ITR1":{...,"CreationInfo.Digest":"…"}}}        │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 2. Stage-by-Stage Detail

### 2.1 Router — `app/routers/itr.py`

**`POST /itr1/compute`** (returns breakdown, no DB write):
```python
input_report = itr1_input_val(body)           # Stage 2
if not input_report.can_upload:
    raise HTTPException(400, …input_report.blocking_errors)
result = compute_itr1(body)                  # Stage 3
if result.errors: raise HTTPException(400, …result.errors)
calc_report = itr1_calc_val(body, result)    # Stage 4
if not calc_report.can_upload:
    raise HTTPException(400, …calc_report.blocking_errors)
return _build_itr1_response(result) | validation=calc_report.to_dict()
```

**`POST /itr1/compute-json`** (returns CBDT ITD JSON):
```python
input_report = itr1_input_val(body)           # Stage 2 — blocking
if not input_report.can_upload: raise HTTPException(400, …)
result = compute_itr1(body)                  # Stage 3
if result.errors: raise HTTPException(400, …)
calc_report = itr1_calc_val(body, result)    # Stage 4 — blocking
if not calc_report.can_upload: raise HTTPException(400, …)
itd_json = build_itr1_json(result, body)     # Stage 5
validate_itr1_json(itd_json)                 # Stage 6 — HARD FAIL
return Response(json.dumps(itd_json, indent=2, default=str), …)
```

**Key invariant:** Both endpoints run all 4 gates (input-val → compute → calc-val → schema-val for JSON). No stage is skipped.

---

### 2.2 Stage 1 — Typed Input (`app/schemas/itr1.py`)

`ITR1Input` carries **every** taxpayer-entered field the JSON builder needs. Critical typed sub-models:

| Field | Type | Used by Builder for |
|---|---|---|
| `filing_profile` | `ITR1FilingProfile` | PersonalInfo, FilingStatus, Verification |
| `property_profile` / `property_profiles` | `PropertyFilingProfile` | `PropertyDetails[].AddressDetailWithZipCode` |
| `bank_accounts` | `List[BankAccount]` | `Refund.BankAccountDtls.AddtnlBankDetails` |
| `tax_return_preparer` | `Optional[TaxReturnPreparer]` | `TaxReturnPreparer` node |
| `schedule_80c_entries` | `List[Schedule80CEntry]` | `Schedule80C.Schedule80CDtls` |
| `schedule_80e_entries` | `List[Schedule80EEntry]` | `Schedule80E.Schedule80EDtls` |
| `loan_details_80ee_list` | `List[ITR1Schedule80EELoanEntry]` | `Schedule80EE.Schedule80EEDtls` |
| `loan_details_80eea_list` | `List[ITR1Schedule80EEALoanEntry]` | `Schedule80EEA.Schedule80EEADtls` |
| `loan_details_80eeb_list` | `List[ITR1Schedule80EEBLoanEntry]` | `Schedule80EEB.Schedule80EEBDtls` |
| `schedule_80d` | `Optional[Schedule80D]` | `Schedule80D.Sec80DSelfFamHIDtls.Sch80DInsDtls` |
| `schedule_80dd` / `schedule_80u` | `Optional[Schedule80DD]`/`Schedule80U` | `Schedule80DD` / `Schedule80U` |
| `schedule_80gga` / `schedule_80ggc` | `Optional[Schedule80GGA]`/`Schedule80GGC` | `Schedule80GGA` / `Schedule80GGC` |
| `hra_details` / `schedule_10_13a` | `Optional[HRADetails]` | `ScheduleEA10_13A` + `AllwncExemptUs10Dtls[HRA]` |
| `tds1_entries` | `Optional[List[TDS1Entry]]` | `TDSonSalaries.TDSonSalary[]` |
| `tds2_entries` | `Optional[List[TDS2Entry]]` | `TDSonOthThanSals.TDSonOthThanSal[]` |
| `tds3_entries` | `Optional[List[TDS3Entry]]` | `ScheduleTDS3Dtls.TDS3Details[]` |
| `tcs_entries` | `Optional[List[TCSEntry]]` | `ScheduleTCS.TCS[]` |
| `tax_payment_entries` | `List[TaxPaymentDetail]` | `TaxPayments.TaxPayment[]` |
| `property_stamp_duty_value_80eea` | `Optional[Decimal]` | `Schedule80EEA.PropStmpDtyVal` |
| `pran_number` | `Optional[str]` | 80CCD(1B) evidence |
| `is_property_co_owned` | `bool` | `PropertyDetails[].PropCoOwnedFlg` |
| `co_ownership_details` | `Optional[CoOwnershipDetails]` | co-owned share % |

**Key principle:** The builder reads from `input_data` (typed), not from kwargs. Legacy kwargs are only a fallback when `input_data is None`.

---

### 2.3 Stage 2 — CBDT Category-A Input Rules (`validators/itr1/input_rules.py`)

```python
input_report = itr1_input_val(body)
if not input_report.can_upload:   # ← blocking gate
    raise HTTPException(400, …input_report.blocking_errors)
```

`ValidationReport.blocking_errors` are Category-A (upload-blocking) findings. Non-blocking warnings attach to `warnings` but don't stop the pipeline.

---

### 2.4 Stage 3 — Calculator (`engine/calculators/itr1.py`)

```python
result = compute_itr1(body)
if result.errors: raise HTTPException(400, …result.errors)
```

`ITR1Result` dataclass holds: computed income heads, tax, TDS/TCS totals, and a `schedules` dict with typed schedule results (`salary`, `hp`, `os`, `deductions` with `.section_details` and `.breakdown`, `tds_tcs`, `capital_gains`). The builder consumes these in Stage 5.

---

### 2.5 Stage 4 — CBDT Category-A Calc Rules (`validators/itr1/calc_rules.py`)

```python
calc_report = itr1_calc_val(body, result)
if not calc_report.can_upload:   # ← blocking gate
    raise HTTPException(400, …calc_report.blocking_errors)
```

Post-computation consistency: cross-field totals, deduction-limit recomputation against computed GTI, etc.

---

### 2.6 Stage 5 — ITD JSON Builder (`engine/itd/itr1.py`)

`build_itr1_json(result, input_data)` produces `{"ITR":{"ITR1":{…}}}`. **Critical patterns:**

#### 2.6.1 PersonalInfo from typed profile (not kwargs)
```python
if input_data is not None:
    profile = input_data.filing_profile
    personal = _personal_info_from_profile(profile)   # real data
    ver = _verification_from_profile(profile)         # real data
    filing = _filing_status_itr1(
        return_file_sec=profile.return_file_section,
        opt_out_new_regime=("Y" if input_data.tax_regime.value == "old" else "N"),
        seventh_proviso=profile.seventh_proviso,       # typed!
        assessee_representative_flag=False,
    )
else:
    # legacy kwargs path — only when input_data is None
```

#### 2.6.2 Deductions from typed schedule results (not hardcoded)
The builder reads `ded_sched = result.schedules["deductions"]` and its `.section_details` dict, which holds **typed** results: `Section80CResult`, `LoanDeductionResult`, `Schedule80GResult`, etc. Each has `.rows` (per-entry) and `.allowed_deduction`. The builder serializes them with cross-foot validation:
```python
details_80c = ded_sched.section_details.get("80C")
if combined_80c > 0:
    if details_80c is None or not details_80c.rows:
        raise ValueError("A positive Section 80C claim requires Schedule 80C detail rows")
    itr1["Schedule80C"] = _schedule_80c(details_80c)   # per-row serialization
```

#### 2.6.3 Hard errors, no soft warnings
```python
if details_80c is None or not details_80c.rows:
    raise ValueError("A positive Section 80C claim requires Schedule 80C detail rows")
```
The builder **raises** on incomplete evidence. It never emits a placeholder.

#### 2.6.4 TDS/TCS/TaxPayments from typed entries
```python
def _tds_other_from_input(input_data: ITR1Input) -> Optional[dict]:
    rows = []
    for entry in input_data.tds2_entries or []:
        if not entry.deductor_name:
            raise ValueError("TDS2 entries require deductor name for ITD JSON")
        rows.append({
            "EmployerOrDeductorOrCollectDetl": {"TAN": entry.deductor_tan, …},
            "TDSSection": _official_tds_section(entry.tds_section),
            "DeductedYr": "2025",   # ← ITR-1 also has this bug (see §4)
            …
        })
```

#### 2.6.5 ScheduleEA10_13A with cross-foot validation
```python
hra = input_data.hra_details or input_data.schedule_10_13a
if hra is not None:
    hra_schedule = _schedule_ea10_13a(…)
    if hra_schedule["EligbleExmpAllwncUs13A"] != _to_rupees(input_data.salary_income.hra_exempt_amount):
        raise ValueError("Schedule 10(13A) eligible exemption must equal the HRA exemption claimed")
    itr1["ScheduleEA10_13A"] = hra_schedule
```

#### 2.6.6 Schedule80D from typed policies
```python
def _policy_insurance_details(policies, section_code):
    rows = []
    for p in policies or []:
        if str(getattr(p, "section", "1a")) != section_code: continue
        rows.append({"InsurerName": …, "PolicyNo": …, "HealthInsAmt": …})
    return rows
```

#### 2.6.7 BankAccountDtls from typed bank_accounts
```python
def _bank_accounts_from_input(input_data):
    primary_count = sum(a.is_primary for a in input_data.bank_accounts)
    if primary_count != 1:
        raise ValueError("Exactly one bank account must be selected for refund")
    rows = [_bank_row(ifsc=a.ifsc_code, bank_name=a.bank_name, …) for a in input_data.bank_accounts]
```

#### 2.6.8 Digest appended last
```python
itr1["CreationInfo"]["Digest"] = _compute_digest(itr1)
```

---

### 2.7 Stage 6 — Official Schema Validation (`engine/itd/itr1_schema.py`)

```python
@lru_cache(maxsize=1)
def get_itr1_schema_validator() -> Draft4Validator:
    schema = json.loads(schema_path.read_text())
    Draft4Validator.check_schema(schema)
    return Draft4Validator(schema)

def validate_itr1_json(document):
    errors = sorted(validator.iter_errors(document), key=…)
    if not errors: return
    raise ITR1SchemaValidationError([...])
```

Called by the router **after** `build_itr1_json` — any failure → HTTP 400.

---

### 2.8 Stage 7 — Filing Gateway (`engine/filing_gateway.py`)

`_build_itr1_official_json` mirrors the router pipeline but for flat-draft input:
```python
typed_input = _build_itr1_input_from_flat(engine_payload)   # flat → typed
cross_field_errors = _validate_itr1_cross_fields(typed_input)  # extra cross-checks
if cross_field_errors: raise FilingGatewayError(…)
result = compute_itr1(typed_input)
if result.errors: raise FilingGatewayError(…)
itd_json = build_itr1_json(result, typed_input)
validate_itr1_json(itd_json)   # ← HARD FAIL (raises FilingGatewayError)
return itd_json, []
```

**Key:** ITR-1 gateway **raises** on schema failure. ITR-4 gateway **swallows** it as a warning — a parity violation.

---

## 3. The 10 Cardinal Rules of the ITR-1 Flow

| # | Rule | ITR-4 Status |
|---|---|---|
| R1 | Router runs `input_val` → 400 on `not can_upload` | ✅ Has |
| R2 | Router runs `calc_val` → 400 on `not can_upload` | ❌ Missing on `/compute-json` |
| R3 | Router runs `validate_itrX_json` → 400 on failure | ❌ Missing |
| R4 | Builder reads typed `input_data`, not kwargs | ❌ Missing (uses kwargs) |
| R5 | Builder raises `ValueError` on incomplete evidence | ❌ Missing (emits placeholders) |
| R6 | Gateway raises `FilingGatewayError` on schema failure | ❌ Missing (soft warning) |
| R7 | `_compute_digest` fallback returns schema-valid `"-"` | ❌ Missing (returns 64-hex) |
| R8 | `DeductedYr` enum-constrained before emit | ❌ Missing (hardcodes `"2025"`) |
| R9 | `ScheduleTCS` entry has all 4 required fields | ❌ Missing (2 of 4) |
| R10 | `ScheduleTDS3Dtls` emitted from typed `tds3_entries` | ❌ Missing |

---

## 4. Known ITR-1 Defect (to fix in BOTH forms)

`_tds_other_from_input` in `itr1.py` hardcodes `"DeductedYr": "2025"` — which is **not** in the ITR-1 enum either. This is a shared bug. The fix (derive from challan date, default to `"2024"` for AY 2026-27) must be applied to both ITR-1 and ITR-4.

---

## 5. Summary

The ITR-1 pipeline is production-ready because it enforces a **4-gate hard-fail pipeline** (input-val → compute → calc-val → schema-val) and the builder reads from **typed input** with **cross-foot validation** and **raises on incomplete evidence**. ITR-4 currently fails R2–R10. The remediation below brings ITR-4 to parity.
