# Taxify Production Readiness Audit — ITR-1 & ITR-4 (AY 2026-27)

**Audit Date:** 2026-08-26  
**Reference Documents Used:**
- `Reference Docs by CBDT & ITD/Official JSON Schema/ITR-1_2026_Main_V1.1 (2).json`
- `Reference Docs by CBDT & ITD/Official JSON Schema/ITR-4_2026_Main_V1.1 (2).json`
- `Reference Docs by CBDT & ITD/Official Validations/CBDT_e-Filing_ITR 1_Validation Rules_AY 2026-27 (1).pdf` (V1.0, 15th May 2026)
- `Reference Docs by CBDT & ITD/Official Validations/CBDT_e-Filing_ITR 4_Validation Rules_AY 2026-27 (1).pdf` (V1.0, 15th May 2026)

**Verdict: NOT PRODUCTION READY** — 9 Category A (upload-blocking) violations confirmed against official CBDT rules, plus 6 incorrect implementations and 2 structural duplications.

---

## Severity Legend

| Label | Meaning |
|-------|---------|
| **CAT-A** | CBDT Category A — return upload will be rejected at portal |
| **CAT-B** | CBDT Category B — upload allowed but 139(9) defective-return notice issued |
| **WRONG** | Incorrect implementation relative to the statute |
| **SILENT** | Data silently dropped or zeroed — wrong output, no error surfaced |
| **SEC** | Security issue |
| **DUP** | Dead code / stale duplication |

---

## 1. BLOCKING BUGS — Category A Upload Failures

### 1.1 Fake TAN Hardcoded in TDS Schedules

**Files:** `app/engine/itd/itr1.py:1218,1241` | `app/engine/itd/itr4.py:2292,2314`  
**Severity:** CAT-A (both forms)  
**CBDT Rule:** ITR-1 Rules 98–102 (TDS column totals); ITR-4 Rules 118–120 (TDS totals)

```python
# Current (both files, two locations each):
"TAN": e.get("TAN", "DELA00001A")
```

When a TDS entry has no TAN, the builder silently substitutes the fabricated TAN `DELA00001A`. The portal cross-references TAN against the ITD TAN master database and validates format (10-character ABCD12345E pattern). A non-existent TAN will cause the TDS row to fail cross-validation, triggering a Category A defect that blocks upload entirely.

**Fix required:** Either require TAN as a mandatory field in the TDS input schema, or omit the TDS row when TAN is absent. Never inject a hardcoded fallback TAN.

---

### 1.2 ITR-1 Schema Validation Not Called

**File:** `app/routers/itr.py:329–383`  
**Severity:** CAT-A (ITR-1 only — ITR-4 is not affected)  
**CBDT Rule:** All Category A rules — structural validation is the first gate

The `/itr1/compute-json` route calculates `input_val` and `calc_val` but never calls `validate_itr1_json()`. The ITR-4 route at line 523 does call `validate_itr4_json()`. This asymmetry means malformed ITR-1 JSONs are returned to callers with no structural check. Any CBDT Category A rule violation that the validator would catch passes silently through to the portal, where it causes a hard upload rejection.

**Fix required:** Call `validate_itr1_json()` (or equivalent) before returning the JSON from `/itr1/compute-json`, mirroring the ITR-4 route.

---

### 1.3 Section 44AE Heavy-Goods Vehicle Rate Absent

**Files:** `app/engine/constants.py:151–152` | `app/engine/schedules/presumptive.py`  
**Severity:** CAT-A (ITR-4 only)  
**CBDT Rule:** ITR-4 Validation Rule 144

CBDT Rule 144 states:
> "The presumptive income offered u/s 44AE per vehicle is less than Rs. 1,000 per MT per month (where the tonnage capacity exceeds 12 MT) or Rs. 7,500 per month (where the tonnage capacity does not exceed 12 MT)."

The constants file defines only a single flat rate:

```python
PRESUMPTIVE_44AE_PER_VEHICLE_OWNER: Final[Decimal] = Decimal("7500")   # monthly
PRESUMPTIVE_44AE_PER_VEHICLE_LEASED: Final[Decimal] = Decimal("7500")  # monthly
```

There is no tonnage-based path. Any heavy goods vehicle (GVW > 12 MT) submitted under 44AE will have its presumptive income calculated at Rs 7,500/month instead of Rs 1,000 × tonnage/month, producing an understatement that the portal catches as a Category A defect.

**Fix required:** Add a `tonnage_capacity_mt` field to the 44AE vehicle input and apply the CBDT split: `max(7500, 1000 × tonnage)` per vehicle per month for vehicles with GVW > 12 MT; Rs 7,500/month for all others.

---

### 1.4 ScheduleBP GST Sub-Schedule Emitted as Empty Array

**File:** `app/engine/itd/itr4.py:734–756`  
**Severity:** CAT-A (ITR-4 only)  
**CBDT Rule:** ITR-4 Validation Rule 1 (ScheduleBP must be filled when 44AD/44ADA/44AE income is declared)

When a taxpayer has business income under 44AD, the ITR-4 JSON builder emits the GST sub-schedule inside ScheduleBP as an empty array `[]` with a zero total, rather than including actual GSTIN rows. Rule 1 requires that ScheduleBP be filled whenever income u/s 44AD/44ADA/44AE is disclosed in Part B Gross Total Income. An empty GST schedule with non-zero turnover triggers a consistency mismatch that is a Category A defect.

**Fix required:** Collect GSTIN and turnover data per GSTIN as input fields and populate the GST schedule rows. If the taxpayer is not GST-registered, emit the appropriate "not registered" indicator per the schema — not an empty array.

---

### 1.5 Section 80CCD(2) Cap Bypassed When Salary is Zero

**File:** `app/engine/schedules/deductions/section_80ccd2.py:64`  
**Severity:** CAT-A (both forms)  
**CBDT Rule:** ITR-1 Rule 4 (non-CG/SG: 10% of salary); Rule 120 (CG/SG: 14% of salary); ITR-4 Rule 25, Rule 47, Rule 263

```python
# Current:
ceiling = (salary * pct) if salary > _ZERO else user_claim
```

When `salary` is zero, the ceiling is set to the full user claim with no cap. Under CBDT Rules 4 and 120 (ITR-1) and Rules 25 and 47 (ITR-4), the deduction cannot exceed 10% or 14% of salary. When salary is zero, the correct answer is that 80CCD(2) cannot be claimed at all (ceiling = 0), not that the claim passes uncapped.

**Fix required:** Replace the else branch with `else: ceiling = Decimal("0")`.

---

### 1.6 HRA and 80GG Simultaneous Claim Not Blocked

**File:** Tax calculator + deduction engine  
**Severity:** CAT-A (both forms)  
**CBDT Rule:** ITR-1 Rule 119; ITR-4 Rule 151

> ITR-1 Rule 119: "HRA and 80GG cannot both be claimed."  
> ITR-4 Rule 151: "House rent allowance (HRA u/s 10(13A)) is claimed, hence deduction u/s 80GG above Rs 55,000 not allowed."

There is no guard in the calculator or validator that raises an error when both `hra_exempt` (Schedule 10(13A)) and `deduction_80gg` are non-zero. A return submitted with both populated will fail portal validation as a Category A defect.

**Fix required:** In the Chapter VI-A deduction engine, check that if HRA exemption (10(13A)) > 0, then 80GG must be forced to zero and the caller notified; or raise a validation error before JSON generation.

---

### 1.7 Children Education and Hostel Allowances Hard-Coded to Zero

**File:** `app/engine/schedules/salary.py:154–158`  
**Severity:** CAT-A (both forms)  
**CBDT Rule:** ITR-1 Rules 63–76 (exempt allowance limits); ITR-4 Rules 80–81 (10(14)(i)/(ii) limits)

```python
# Current:
children_education_exempt = _exempt_children_education(
    input_data.sec10_14i_prescribed_allowance, 0,   # num_children=0
)
hostel_exempt = _exempt_hostel(input_data.sec10_14ii_personal_allowance, 0)
```

The comment in the code acknowledges this: "the schema does not yet have a dedicated field, so default to 0 children (i.e., exemption = 0)." With `num_children=0`, the exempt amounts are always zero regardless of actual entitlement.

CBDT rules specify Rs 100/month/child (max 2 children) for education allowance and Rs 300/month/child for hostel allowance. If a taxpayer provides these allowances as income and claims exemptions, the returned ITD JSON will show the allowance as fully taxable, which misrepresents their return.

**Fix required:** Add `num_children` to the salary input schema and pass the actual value to both helper functions.

---

### 1.8 Section 80CCH — Age and Employer Category Not Validated

**File:** `app/engine/constants.py:231` | deduction engine  
**Severity:** CAT-A (both forms)  
**CBDT Rule:** ITR-1 Rule 187 (CG employment + age 17–27 at date of joining armed forces); ITR-4 Rule 225 (identical condition); ITR-1 Rule 186 / ITR-4 Rule 224 (cap: 46.2% of salary u/s 17(1), max Rs 2,88,000)

The code comment at line 231 reads:
```python
# Section 80CCH - Agniveer Corpus Fund (no statutory rupee ceiling per s.80CCH)
```

This is incorrect on two counts. CBDT validation rules impose:
1. A percentage cap: 80CCH cannot exceed 46.2% of salary u/s 17(1), with an absolute ceiling of Rs 2,88,000.
2. Eligibility conditions: Central Government employment and age between 17 and 27 years at date of joining the armed forces.

Neither condition is enforced in the deduction engine. A non-Agniveer claiming 80CCH will pass through the engine unchallenged and produce a Category A defect at the portal.

**Fix required:** Add employer category and date-of-joining checks to the 80CCH deduction handler. Apply the 46.2%/Rs 2,88,000 ceiling.

---

### 1.9 New Regime 87A Marginal Relief Not Computed

**File:** `app/engine/constants.py:95` | rebate engine  
**Severity:** CAT-A / WRONG (both forms — wrong tax output, not a hard portal rejection but produces incorrect ITD JSON values)  
**CBDT Rule:** ITR-1 Rule 191; ITR-4 Rule 227

```python
# Current:
NEW_REBATE_INCOME_LIMIT: Final[Decimal] = Decimal("1200000")  # Full rebate income ceiling
```

CBDT Rule 191 (ITR-1) and Rule 227 (ITR-4) state that taxpayers with new regime total income (excluding LTCG u/s 112A) above Rs 12,00,000 but ≤ approximately Rs 12,70,590 receive a marginal rebate such that net tax is no more than the excess over Rs 12,00,000. The engine currently gives zero rebate for any income above Rs 12,00,000, over-taxing taxpayers in the Rs 12,00,001–12,70,590 band. The ITD JSON will show a higher tax figure than the portal computes, causing a mismatch in Category A rule 52 (tax reconciliation).

**Fix required:** Implement marginal rebate: for new regime income between Rs 12,00,000 and ~Rs 12,70,590, rebate = max(0, tax − (income − Rs 12,00,000)).

---

## 2. INCORRECT IMPLEMENTATIONS

### 2.1 44AD Turnover Limit Documented as Rs 2 Crore, Implemented as Rs 3 Crore

**File:** `app/engine/calculators/itr4.py:9` (docstring)  
**Severity:** WRONG (documentation, not code)  
**Correct limit:** Rs 3 Crore (Finance Act 2024; `SEC_44AD_TURNOVER_LIMIT = Decimal("30000000")` in constants.py)

The class docstring states "turnover up to Rs 2 Crore" but the constant is correctly set to Rs 3 Crore. The code is right, the comment is stale. However, this creates a maintenance risk where developers applying business logic will use the wrong figure.

**Fix required:** Update docstring to "turnover up to Rs 3 Crore (Finance Act 2024)."

---

### 2.2 Exception Message Leaks Internal Stack Detail

**File:** `app/routers/itr.py:375`  
**Severity:** SEC

```python
detail=f"ITD JSON generation failed: {exc}"
```

Internal Python exception text (including file paths, line numbers, or third-party library error strings) is returned verbatim in the HTTP 500 response body. This exposes implementation details to clients.

**Fix required:** Log `exc` server-side and return a generic message: `"ITD JSON generation failed. Contact support."`.

---

### 2.3 CORS Configuration is Overpermissive

**File:** `app/main.py:130–133`  
**Severity:** SEC

```python
allow_credentials=True
allow_methods=["*"]
allow_headers=["*"]
```

`allow_credentials=True` combined with `allow_origins` that is not an explicit whitelist means any origin can make credentialed requests. This violates the CORS specification security requirement and is flagged by browser security scanners.

**Fix required:** Enumerate allowed origins explicitly (production domain + localhost for dev). Restrict `allow_methods` to `["GET","POST"]` and `allow_headers` to the minimum required.

---

### 2.4 PDF Download Is Not CBDT-Compliant

**File:** `app/routers/client_itr.py:251–288`  
**Severity:** WRONG (user-facing, non-upload-blocking)

The `/download-pdf` endpoint generates a lightweight summary PDF. The endpoint's own docstring acknowledges this: "A full CBDT-compliant PDF should be generated from the canonical engine result." The PDF does not follow the ITD acknowledgment or computation sheet format. Distributing this to taxpayers as their "ITR" document is misleading.

**Fix required:** Either generate the PDF from the canonical ITD JSON output using the official computation sheet layout, or label the document clearly as "Computation Summary — Not an ITR Filing Acknowledgment."

---

### 2.5 Duplicate Schema Files at Root Level

**Files:** `schemas/itr1_input.py` | `schemas/itr4_input.py`  
**Severity:** DUP

These files are stale copies of `app/schemas/itr1.py` and `app/schemas/itr4.py`. They are not imported by any live route. Any schema change made in `app/schemas/` will diverge silently from the root copies, creating confusion and risk of the wrong schema being imported in future work.

**Fix required:** Delete `schemas/itr1_input.py` and `schemas/itr4_input.py` entirely. Confirm no import paths reference the root-level copies.

---

### 2.6 ITR-2 and ITR-3 Routes Are Live With Incomplete Engines

**File:** `app/routers/itr.py:386–442`  
**Severity:** WRONG (scope risk, not an ITR-1/4 bug)

Routes `/itr2/compute-json` and `/itr3/compute-json` are reachable in production but their engines have documented gaps. Clients can call these endpoints and receive incomplete output without any indication that the computation is partial. This is a reliability and liability issue.

**Fix required:** Return HTTP 501 Not Implemented from ITR-2 and ITR-3 routes until those engines are complete, or protect them behind a feature flag.

---

## 3. VERIFIED CORRECT IMPLEMENTATIONS

The following items were cross-referenced against official CBDT reference documents and confirmed correct:

| Area | CBDT Rule | Implementation |
|------|-----------|----------------|
| Old regime tax slabs (below 60, 60–80, above 80) | IT Act s.11 | `constants.py:12–30` — correct |
| New regime slabs AY 2026-27 | Finance Act 2025 | `constants.py:36–44` — 0/5/10/15/20/25/30% correct |
| Standard deduction old regime Rs 50,000 | ITR-1 Rule 112 | `constants.py:50` — correct |
| Standard deduction new regime Rs 75,000 | ITR-1 Rule 215; ITR-4 Rule 262 | `constants.py:51` — correct |
| Old regime 87A: Rs 12,500 rebate at ≤ Rs 5L | ITR-1 Rule 192; ITR-4 Rule 229 | `constants.py:90–91` — correct |
| New regime 87A: Rs 60,000 rebate at ≤ Rs 12L | ITR-1 Rule 191 | `constants.py:94–95` — correct (marginal relief missing; see Issue 1.9) |
| 80CCE combined cap Rs 1,50,000 | ITR-1 Rule 1 | `constants.py:159` — correct |
| 80CCD(1B) Rs 50,000 additional NPS | ITR-1 Rule 115; ITR-4 Rule 145 | `constants.py:168` — correct |
| 80TTA Rs 10,000 savings interest | ITR-1 Rule 11; ITR-4 Rule 152 | `constants.py:222` — correct |
| 80TTB Rs 50,000 senior citizen interest | ITR-1 Rule 14; ITR-4 Rule 153 | `constants.py:225` — correct |
| HP standard deduction 30% | ITR-1 Rule 43; ITR-4 Rule 57 | `constants.py:237` — correct |
| HP interest self-occupied cap Rs 2,00,000 | IT Act s.24(b) | `constants.py:238` — correct |
| 44AD digital 6%, cash 8% | ITR-4 Rules 5–7 | `constants.py:140–141` — correct |
| 44AD threshold Rs 3 Crore (FA 2024) | ITR-4 Rule 9 | `constants.py:142` — correct |
| 44ADA rate 50%, threshold Rs 75L | ITR-4 Rules 13–14 | `constants.py:146–147` — correct |
| LTCG 112A exemption Rs 1,25,000 | CBDT notification | `constants.py:251` — correct |
| Health & education cess 4% | IT Act s.272B | `constants.py:101` — correct |
| 80CCD(2) rate: 14% CG/SG, 10% others | ITR-1 Rules 4,120; ITR-4 Rules 25,47,263 | `section_80ccd2.py:26–27` — rates correct (salary=0 bypass is the bug) |
| HRA = min(actual, rent−10%salary, 40/50% salary) | ITR-1 Rules 261–263; ITR-4 Rules 311–313 | HRA helper logic — confirmed correct formula |
| 80GG max Rs 60,000 (Rs 5,000/month) | ITR-4 Rule 37 | `constants.py:212` — correct |
| 80U disabled Rs 75,000, severe Rs 1,25,000 | ITR-4 Rule 42/182 | `constants.py:228–229` — correct |
| Surcharge new regime capped at 25% above 5Cr | Finance Act 2023 | `constants.py:131` — correct |
| ITR-4 route calls validate_itr4_json() | — | `itr.py:523` — confirmed |
| Fernet encryption for portal passwords | — | Confirmed in DB layer |
| HMAC-SHA256 digest for ITD JSON | — | Confirmed |

---

## 4. SUMMARY — PRODUCTION READINESS VERDICT

| Category | Count | Action |
|----------|-------|--------|
| CAT-A Upload-Blocking Bugs | 9 | Must fix before any live filing |
| Incorrect Implementations | 6 | Fix before public release |
| Verified Correct | 26 | No action needed |

**ITR-1 is blocked by:** Issues 1.2 (no schema validation), 1.1 (fake TAN), 1.5 (80CCD(2) bypass), 1.6 (HRA+80GG), 1.7 (children allowances), 1.8 (80CCH), 1.9 (87A marginal rebate).

**ITR-4 is blocked by:** Issues 1.1 (fake TAN), 1.3 (44AE heavy vehicle rate), 1.4 (empty GST schedule in ScheduleBP), 1.5 (80CCD(2) bypass), 1.6 (HRA+80GG), 1.7 (children allowances), 1.8 (80CCH), 1.9 (87A marginal rebate).

Both forms share the majority of blockers. The minimum set to unblock ITR-1 filing is Issues 1.1, 1.2, 1.5, 1.6, 1.7, 1.8, and 1.9. For ITR-4, additionally fix Issues 1.3 and 1.4.
