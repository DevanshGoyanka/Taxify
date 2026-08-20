# Form 10E / Section 89(1) Relief — Implementation Plan (AY 2026-27)

**Status:** Approved
**Date:** 2026-08-15
**Scope:** Form 10E full implementation. ITD-JSON validation gate + remaining test cases deferred to separate later sessions. Full tax cascade (slab tax → rebate 87A → surcharge w/ marginal relief → 4% cess) in all four T-steps. Auto-compute inside the ITR-1 engine (engine-authoritative).

---

## Statutory Basis (verified)

- **Section 89(1) + Rule 21A** — confirmed via incometaxindia.gov.in and ClearTax/TaxClue authoritative guides.
- **CBDT ITR-1 Validation Rules PDF (AY 2026-27 V1.0):**
  - Rule 27/140 (Cat A): `Total Tax, Fees & Interest = (Gross Tax Liability − Relief u/s 89) + Total Interest + Fees`
  - Rule 125 (Cat A): Relief u/s 89 cannot be claimed if salary [17(1)+17(2)+17(3)] or family pension is zero/blank
  - Cat D Rule 1: Relief u/s 89(1) claimed without Form 10E → flagged (non-blocking)
- **Rule 21A six-step formula:**
  - T1 = tax on current-year total income **including** arrears (full cascade: slab→rebate→surcharge→cess)
  - T2 = tax on current-year total income **excluding** arrears (full cascade)
  - Value A = T1 − T2
  - T3 = tax on prior-year total income **including** the arrear portion (full cascade, **at prior-year rates/limits**)
  - T4 = tax on prior-year total income **excluding** the arrear (full cascade, at prior-year rates/limits)
  - Value B = T3 − T4
  - **Relief = max(0, Value A − Value B)** — negative relief clamped to zero

### ⚠️ Correction from original (pre-review) plan

The original plan incorrectly said "no surcharge (Form 10E uses pre-surcharged tax)". This was **wrong**. Rule 21A requires the **full surcharge + cess cascade** in all four T-steps. This revised plan corrects that error. (Confirmed by TaxClue, ClearTax, and the Income Tax Department's Section 89 page — referencer.in AY 2025-26 tax rate table explicitly shows surcharge + cess added in both regimes.)

## User's TEST 8 scenario (zero-relief trap)

- T1=₹1,50,800, T2=₹97,500, T3=₹1,30,000, T4=₹71,500
- Value A = 1,50,800 − 97,500 = ₹53,300
- Value B = 1,30,000 − 71,500 = ₹58,500
- Relief = max(0, 53,300 − 58,500) = **₹0** (the zero-relief trap — filer sees *why* via Table A/B breakdown)
- Final tax = T1 − relief = ₹1,50,800

---

## Edge Cases Addressed

| Edge Case | How This Plan Handles It |
|---|---|
| **Historical Regime Persistence** | New `slabs_for_ay(ay, age, regime)` resolver + prior-year rebate/surcharge/std-ded tables. T3/T4 look up AY 2025-26 values, NOT AY 2026-27. Each `Form10EArrearEntry` carries its own `prior_ay`, `prior_year_age_bracket`, `prior_year_regime` so multi-year arrears use the correct historical profile per entry. |
| **Surcharge & Cess Cascade** | Every T-step runs the **full cascade**: slab tax → 87A rebate (with marginal relief) → surcharge (with marginal relief) → 4% health & education cess. Reuses existing `compute_rebate`, `compute_surcharge`, `compute_cess` modules. No T-step is pre-surcharged. |
| **UI/UX Input Validation (arrear sum)** | Pydantic validator on `Relief89Request`: `sum(arrear_entries[].arrear_amount) == total_arrears_received` (±₹1 tolerance for rounding). Frontend `Relief89Calculator` shows inline error if mismatched. |
| **Multiple prior-year arrears** | T3/T4 computed per prior AY (each entry carries its own `prior_ay`), then summed. Value B = Σ(T3_i − T4_i) across all entries. |
| **Negative relief clamp** | `relief = max(Decimal("0"), value_a - value_b)` — matches Rule 21A "If Value A ≤ Value B: relief = ₹0". |
| **Form 10E filing mandate** | Cat D Rule 1: if `relief_89 > 0` and `form_10e_filed == False` → emit Cat D warning (non-blocking). Existing ITR-1 input validator already has this rule; verify it fires. |

---

## Implementation Steps

### Step 1 — Prior-year statutory tables in `constants.py` + `slab_tax.py`

Add to `app/engine/constants.py` (verified against referencer.in AY 2025-26 table):

```python
# AY 2025-26 (FY 2024-25) — New Regime slabs (FA 2024)
NEW_REGIME_SLABS_AY_2025_26: Final[list] = [
    (Decimal("0"), Decimal("300000"), Decimal("0")),       # 0-3L @ 0%
    (Decimal("300000"), Decimal("700000"), Decimal("5")),   # 3L-7L @ 5%
    (Decimal("700000"), Decimal("1000000"), Decimal("10")), # 7L-10L @ 10%
    (Decimal("1000000"), Decimal("1200000"), Decimal("15")),# 10L-12L @ 15%
    (Decimal("1200000"), Decimal("1500000"), Decimal("20")),# 12L-15L @ 20%
    (Decimal("1500000"), None, Decimal("30")),              # Above 15L @ 30%
]
# AY 2025-26 Old regime slabs (unchanged from AY 2026-27 — same 3 age tiers)
# Reuse OLD_REGIME_SLABS_BELOW_60 / 60_TO_80 / ABOVE_80
# AY 2025-26 rebate thresholds (FA 2024)
NEW_REBATE_TAX_LIMIT_AY_2025_26 = Decimal("25000")
NEW_REBATE_INCOME_LIMIT_AY_2025_26 = Decimal("700000")
# Old regime rebate unchanged: 12,500 / 5,00,000
# Standard deduction AY 2025-26: NEW=75,000 (FA 2024), OLD=50,000
```

Add to `app/engine/common/slab_tax.py`:

```python
def slabs_for_ay(assessment_year: str, age_bracket: str, regime: str) -> Sequence[Slab]:
    """Return slab table for any AY. AY 2026-27 → current; AY 2025-26 → prior."""
    from app.engine.constants import NEW_REGIME_SLABS_AY_2025_26, NEW_REGIME_SLABS_AY_2026_27
    if regime == "new":
        if assessment_year == "2025-26":
            return NEW_REGIME_SLABS_AY_2025_26
        return NEW_REGIME_SLABS_AY_2026_27  # default / 2026-27
    # Old regime slabs identical across recent AYs
    return _slabs_for(age_bracket, regime)

def rebate_for_ay(assessment_year: str, regime: str) -> tuple[Decimal, Decimal]:
    """Return (income_limit, tax_limit) for 87A rebate by AY."""
    if regime == "new" and assessment_year == "2025-26":
        return (NEW_REBATE_INCOME_LIMIT_AY_2025_26, NEW_REBATE_TAX_LIMIT_AY_2025_26)
    if regime == "new":
        return (NEW_REBATE_INCOME_LIMIT, NEW_REBATE_TAX_LIMIT)
    return (OLD_REBATE_INCOME_LIMIT, OLD_REBATE_TAX_LIMIT)
```

**Why this is structured for future `TaxYearProfile`:** The `slabs_for_ay()` / `rebate_for_ay()` pattern is a minimal year-adaptive resolver. When the full `TaxYearProfile` architecture lands (per `YEAR_ADAPTIVE_ARCHITECTURE_PLAN.md`), these functions become thin delegates to `get_profile(ay).slabs` — no breaking changes.

### Step 2 — Form 10E engine module: `app/engine/common/relief_89.py`

```python
@dataclass
class Form10EArrearEntry:
    prior_ay: str               # "2025-26" for FY 2024-25 arrears
    arrear_amount: Decimal
    prior_year_total_income_excl_arrear: Decimal  # original TI for that prior year
    prior_year_regime: str     # "old" / "new"
    prior_year_age_bracket: str

@dataclass
class Form10ERequest:
    current_ay: str = "2026-27"
    current_year_total_income_incl_arrears: Decimal = Decimal("0")
    current_year_total_income_excl_arrears: Decimal = Decimal("0")
    current_year_regime: str = "new"
    current_year_age_bracket: str = "below_60"
    total_arrears_received: Decimal = Decimal("0")
    arrear_entries: list[Form10EArrearEntry] = field(default_factory=list)

@dataclass
class Form10EResult:
    t1: Decimal; t2: Decimal
    t3_per_entry: list[Decimal]; t4_per_entry: list[Decimal]
    t3_total: Decimal; t4_total: Decimal
    value_a: Decimal; value_b: Decimal
    relief: Decimal              # clamped ≥ 0
    table_a: dict                # current-year breakdown
    table_b: list[dict]         # per-prior-year breakdown
    warnings: list[str]

def _compute_full_cascade(taxable_income, ay, regime, age_bracket) -> Decimal:
    """One T-step: slab tax → 87A rebate → surcharge → 4% cess."""
    slabs = slabs_for_ay(ay, age_bracket, regime)
    slab_tax = _compute_slabs(slabs, taxable_income)
    rebate = _compute_rebate_for_ay(ay, regime, taxable_income, slab_tax)
    tax_after_rebate = max(Decimal("0"), slab_tax - rebate)
    surcharge = compute_surcharge(taxable_income, tax_after_rebate, regime, age_bracket)
    cess = compute_cess(tax_after_rebate + surcharge)
    return tax_after_rebate + surcharge + cess

def compute_relief_89(request: Form10ERequest) -> Form10EResult:
    """Run the Rule 21A six-step computation. Relief clamped to ≥ 0."""
    # Validate arrear sum (edge case 3)
    arrear_sum = sum(e.arrear_amount for e in request.arrear_entries)
    warnings = []
    if abs(arrear_sum - request.total_arrears_received) > Decimal("1"):
        warnings.append(f"Arrear sum (₹{arrear_sum}) ≠ total (₹{request.total_arrears_received})")
    
    # Steps 1 & 2: current-year cascade
    t1 = _compute_full_cascade(request.current_year_total_income_incl_arrears,
                               request.current_ay, request.current_year_regime,
                               request.current_year_age_bracket)
    t2 = _compute_full_cascade(request.current_year_total_income_excl_arrears,
                               request.current_ay, request.current_year_regime,
                               request.current_year_age_bracket)
    value_a = t1 - t2
    
    # Steps 4 & 5: prior-year cascade per entry
    t3_list, t4_list = [], []
    for entry in request.arrear_entries:
        ti_with = entry.prior_year_total_income_excl_arrear + entry.arrear_amount
        t3_i = _compute_full_cascade(ti_with, entry.prior_ay,
                                     entry.prior_year_regime, entry.prior_year_age_bracket)
        t4_i = _compute_full_cascade(entry.prior_year_total_income_excl_arrear,
                                     entry.prior_ay, entry.prior_year_regime,
                                     entry.prior_year_age_bracket)
        t3_list.append(t3_i); t4_list.append(t4_i)
    t3_total = sum(t3_list, Decimal("0"))
    t4_total = sum(t4_list, Decimal("0"))
    value_b = t3_total - t4_total
    
    # Step 6: final relief (clamped)
    relief = max(Decimal("0"), value_a - value_b)
    
    return Form10EResult(t1=t1, t2=t2, t3_per_entry=t3_list, t4_per_entry=t4_list,
                         t3_total=t3_total, t4_total=t4_total,
                         value_a=value_a, value_b=value_b, relief=relief,
                         table_a={...}, table_b=[...], warnings=warnings)
```

### Step 3 — Pydantic schema: `app/schemas/relief_89.py`

`Relief89Request` (matches frontend payload) + `Relief89Response` (exposes `relief`, `t1`, `t2`, `t3`, `t4`, `valueA`, `valueB`, `tableA`, `tableB`, `warnings`). The `@model_validator` enforces the arrear-sum check (edge case 3).

### Step 4 — Backend router: `app/routers/advanced_tax.py` (new)

```python
router = APIRouter(prefix="/advanced-tax", tags=["advanced-tax"])

@router.post("/relief89")
def compute_relief_89_endpoint(request: Relief89Request, 
                               current_user: User = Depends(get_current_user)):
    engine_request = _map_to_engine_request(request)
    result = compute_relief_89(engine_request)
    return _map_to_response(result)
```

Register in `app/main.py`: `app.include_router(advanced_tax_router.router)`.

**Other `/advanced-tax/*` endpoints the frontend already calls** (HRA, 14A, 50C, depreciation, etc.) are currently 404. This plan implements ONLY `relief89`; the others remain stubs for a future session. The frontend `Relief89Calculator` will work end-to-end after this step.

### Step 5 — Auto-compute wired into ITR-1 calculator

Add to `app/schemas/itr1.py`:
```python
form_10e: Optional[Form10ERequest] = None  # when supplied, engine computes relief
```

Modify `app/engine/calculators/itr1.py` (one change at the existing relief block):
```python
# Relief u/s 89 — engine-authoritative when form_10e supplied
if input_data.form_10e is not None:
    from app.engine.common.relief_89 import compute_relief_89
    f10e_result = compute_relief_89(input_data.form_10e)
    result.relief_89 = f10e_result.relief
    result.schedules["form_10e"] = f10e_result  # for ITD JSON / display
else:
    result.relief_89 = input_data.relief_89  # pass-through (backward-compat)
```

The existing `result.gross_tax_liability - result.relief_89` arithmetic (lines for interest 234B/C assessed-tax base, and final liability) remains unchanged — it already subtracts relief at the statutorily-correct post-cess stage.

### Step 6 — ITD JSON emission (verify, no change)

The existing `Section89` field in `_tax_computation_itr1` emits `_to_rupees(relief_89)`. The auto-computed relief flows through `ITR1Result.relief_89 → build_itr1_json`. Test assertion: `Section89 == computed relief`.

### Step 7 — Frontend wiring

Update `Relief89Calculator` in `AdvancedTaxPage.tsx`:
- Accept income figures (not just pre-computed tax) so the engine computes T1–T4
- Render Table A (current-year) + Table B (per-prior-year) breakdown
- Show the "trap" clearly: when relief=0, display "Value B (₹X) exceeded Value A (₹Y) — no relief available"
- Inline validation: `sum(arrearEntries[].arrearAmount) == totalArrearsReceived`

### Step 8 — Tests (`tests/test_relief_89.py`)

1. **TEST 8 — zero-relief trap**: user's exact numbers → `relief == 0`, final tax == T1.
2. **Positive relief**: construct scenario where Value A > Value B → relief > 0, verify it reduces gross tax liability in ITR-1 calculator.
3. **Negative-relief clamp**: Value B > Value A → relief = 0 (TEST 8 is this case).
4. **Multiple prior-year arrears**: two entries (different prior AYs) → T3/T4 aggregated correctly.
5. **Historical persistence**: arrear for AY 2025-26 → T3/T4 use AY 2025-26 slabs (₹3L basic exemption new regime), NOT AY 2026-27 slabs (₹4L basic exemption).
6. **Surcharge cascade**: high-income filer (>₹50L) → T-step includes surcharge + cess.
7. **CBDT Rule 125**: relief claimed with zero salary → validation error.
8. **CBDT Cat D Rule 1**: relief > 0 without `form_10e_filed=True` → Cat D warning.
9. **Arrear-sum mismatch**: `sum(arrear_amount) != total_arrears_received` → warning + 422 if tolerance exceeded.
10. **Endpoint test**: POST `/advanced-tax/relief89` with TEST 8 payload → 200, `relief == 0`, breakdown present.
11. **ITD JSON**: computed relief flows to `Section89` field.

---

## Files to create/modify

| File | Action |
|---|---|
| `app/engine/constants.py` | Add AY 2025-26 slab + rebate tables |
| `app/engine/common/slab_tax.py` | Add `slabs_for_ay()`, `rebate_for_ay()` resolvers |
| `app/engine/common/relief_89.py` | **NEW** — Form 10E six-step engine (full cascade) |
| `app/schemas/relief_89.py` | **NEW** — Pydantic request/response + arrear-sum validator |
| `app/routers/advanced_tax.py` | **NEW** — `/advanced-tax/relief89` endpoint |
| `app/main.py` | Register `advanced_tax` router |
| `app/schemas/itr1.py` | Add optional `form_10e` field |
| `app/engine/calculators/itr1.py` | Auto-compute relief when `form_10e` supplied |
| `frontend/src/pages/AdvancedTaxPage.tsx` | Render Table A/B breakdown + arrear-sum validation |
| `tests/test_relief_89.py` | **NEW** — 11 test cases |

All existing 733 tests remain green; the pass-through `relief_89` scalar path is preserved for backward compatibility (when `form_10e` is None, behavior is unchanged).

---

## Sequencing Recommendation

| Order | Task | Why this order |
|---|---|---|
| 1 | **Remaining 2 test cases** (separate session) | Completes golden suite before adding new features |
| 2 | **ITD-JSON validation gate** (separate session) | Your "hard generation gate" — proves the JSON validates against official CBDT schema before adding more fields |
| 3 | **Form 10E / Section 89** (THIS plan) | Adds the missing computation path; flows into `Section89` field already in the ITD builder |
| 4 | **Year-adaptive architecture** (future, when AY 2027-28 approaches) | `YEAR_ADAPTIVE_ARCHITECTURE_PLAN.md` explicitly defers this until ITR-1 is production-ready. This plan's `slabs_for_ay()` resolver is a head-start that slots cleanly into the future `TaxYearProfile`. |

---

## Prior-Year (AY 2025-26) Statutory Values — Authoritative Source

Verified against referencer.in Income Tax Rates AY 2025-26 table (cross-referenced with incometaxindia.gov.in):

**New Regime (FY 2024-25 / AY 2025-26):**
- Slabs: 0–3L @ 0%, 3L–7L @ 5%, 7L–10L @ 10%, 10L–12L @ 15%, 12L–15L @ 20%, above 15L @ 30%
- Basic exemption: ₹3,00,000
- Standard deduction: ₹75,000 (FA 2024)
- Rebate 87A: income ≤ ₹7,00,000 → rebate up to ₹25,000
- Surcharge: 10%/15%/25%/25% (capped at 25% above ₹5Cr)
- Cess: 4% (Health & Education)

**Old Regime (FY 2024-25 / AY 2025-26):**
- Slabs (below 60): 0–2.5L @ 0%, 2.5L–5L @ 5%, 5L–10L @ 20%, above 10L @ 30%
- Slabs (60–80): 0–3L @ 0%, 3L–5L @ 5%, 5L–10L @ 20%, above 10L @ 30%
- Slabs (above 80): 0–5L @ 0%, 5L–10L @ 20%, above 10L @ 30%
- Standard deduction: ₹50,000
- Rebate 87A: income ≤ ₹5,00,000 → rebate up to ₹12,500
- Surcharge: 10%/15%/25%/37%
- Cess: 4%
