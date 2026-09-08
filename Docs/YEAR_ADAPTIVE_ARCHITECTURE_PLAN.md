# Year-Adaptive Architecture Plan

**Status:** Deferred until ITR-1 is declared production-ready  
**Date:** 2026-08-14  
**Scope:** Backend `TaxYearProfile` system + frontend config context to handle IT Act changes, Finance Act (annual rule) changes, and CBDT schema changes per assessment year, with backward compatibility.

---

## Table of Contents

1. [Current Architecture Analysis](#current-architecture-analysis)
2. [The Three Annual Changes](#the-three-annual-changes)
3. [Design Principle](#design-principle)
4. [Phase 1: Frontend Cleanup](#phase-1-frontend-cleanup)
5. [Phase 2: Backend Year-Adaptive System](#phase-2-backend-year-adaptive-system)
6. [Phase 3: Frontend Tax-Year Config Context](#phase-3-frontend-tax-year-config-context)
7. [Phase 4: Adding a New Assessment Year](#phase-4-adding-a-new-assessment-year)
8. [Implementation Order](#implementation-order)
9. [What This Architecture Achieves](#what-this-architecture-achieves)

---

## Current Architecture Analysis

### Backend

**Single flat constants module with no AY dimension:**
- `app/engine/constants.py` holds ~90 `Final[Decimal]` values, all for AY 2026-27
- 25+ engine modules import directly at module level — no dependency injection, no profile/config object
- The `TaxRegime` enum (OLD/NEW) is the *only* mechanism for regime selection

**Hard AY rejection gate:**
- `app/routers/tax.py` line 343–348 rejects any AY ≠ "2026-27" with HTTP 422
- Same gate in the business-income endpoint (line 1357)

**7 categories of statutory values hardcoded inline (not in constants.py):**

| Module | Hardcoded values | Constants exist but unused? |
|---|---|---|
| `other_sources.py` L50 | ₹15,000 / ₹25,000 (57(iia) cap), `Decimal("3")` (1/3 fraction) | No — not in constants |
| `house_property.py` L48, L98 | ₹2,00,000 HP loss set-off cap, 70% arrears | ₹2L exists as `HOUSE_PROPERTY_INTEREST_LIMIT_SELF_OCCUPIED` but is a different concept |
| `special_rates.py` | 7 special-rate percentages (115BBF 10%, 115BBG 10%, 115BBI 5%, 115BBA 20%, 115E(a) 20%, 115E(b) 10%, 115BBJ 30%) | No — not in constants |
| `presumptive.py` L40-50 | 44AE ₹1,000/ton/month, ₹7,500/month | **Yes — `PRESUMPTIVE_44AE_*` constants exist but are unused** |
| `agricultural.py` L60 | ₹5,000 agri threshold for partial integration | No — not in constants |
| `salary.py` L160-175 | ₹2,500 prof tax cap, ₹5,000 entertainment, 20%/5% formula | No — not in constants |
| `routers/tax.py` L680 | ₹10,000 (80TTA), ₹50,000 (80TTB) | **Yes — `SECTION_80TTA_LIMIT` / `SECTION_80TTB_LIMIT` exist but router hardcodes** |

**Validators duplicate all thresholds:**
- `app/engine/validators/itr1/calc_rules.py` imports **zero** constants
- Re-derives every threshold from hardcoded literals: `500_000`, `12_500`, `Decimal("1270590")`, `50_000`, `75_000`, `5_000_000`
- Creates **dual sources of truth** — change constants.py and validators still use old values

**Duplicated flat→typed mapper:**
- `tax.py` `_compute_tax_summary_impl()` (lines ~490–830)
- `filing_gateway.py` `_build_itr1_input_from_flat()` (lines ~650–900)
- Both reimplement `_money()`, `_first_money()`, `_date()`, `_records()`, and the same regex patterns

**Double computation in filing gateway:**
- Step 1: calls `compute_tax_summary()` (router function)
- Step B: calls `compute_itr1()` again — the engine runs **twice** for a filing artifact

**Schema paths hardcoded in 3 separate files:**
- `app/engine/itd/itr1_schema.py` line 13: `"ITR-1_2026_Main_V1.1 (2).json"`
- `app/engine/itd/itr2_schema.py`: `"ITR-2_2026_Main_V1.1 (2).json"`
- `app/engine/itd/itr4_schema.py` line 15: `"ITR-4_2026_Main_V1.1 (2).json"`
- Loaded at runtime with `@lru_cache(maxsize=1)`, but the filename is baked into source

### Frontend

**Tax computation is already backend-only:**
- `taxResult` useMemo (line 663) returns `backendTaxResult` if present, else all-zeros
- `computeTaxSummary` called via debounced `useEffect` (line 618)
- No frontend tax math runs in `ITRComputationPage`
- `EmployerEntryManager` and `HousePropertyEntryManager` already read from backend result

**But statutory values are hardcoded in 4+ locations:**

| Location | Hardcoded values |
|---|---|
| `domain/eligibility.ts` L157, L163, L176 | `5_000_000` (₹50L), `5_000` (agri), `50_000_000` (₹5Cr ITR-4) |
| `autoDetectITRForm` (ITRComputationPage L1510, L1524) | `5000000`, `5000` — duplicates eligibility.ts |
| `validateITRFormSelection` (ITRComputationPage L1577, L1580) | `5000000`, `5000` — triplicates eligibility.ts |
| `Section80DManager.tsx` L49-53 | 5 cap constants (₹25k/₹50k/₹5k) |
| `CapitalGainsEntryManager.tsx` L197 | `125000` (112A cap) |
| `ScheduleOSWorkspace.tsx` L239 | `25000` (57(iia) cap), `/3` fraction |
| `ExemptIncomeWorkspace.tsx` L108 | net agriculture formula (display-only) |
| `types/scheduleOS.ts` L113-118 | `taxRate: 30`, `tdsThreshold: 10000` in WINNINGS_INFO |

**No tax-year-config endpoint exists:**
- The frontend has no way to fetch statutory limits
- `AYContext.tsx` hardcodes `currentAY: '2026-27'` (line 13)
- Every statutory value is a hardcoded literal in frontend source

**Three independent eligibility implementations:**
1. `domain/eligibility.ts` — `assessFormEligibility` (canonical, memoized at line 574)
2. `autoDetectITRForm` — `ITRComputationPage.tsx:1418-1540` (UX auto-suggest)
3. `validateITRFormSelection` — `ITRComputationPage.tsx:1551-1632` (hard validation)

All three re-derive the same verdicts from the same hardcoded thresholds.

**Dead code confirmed:**
- `LegacyPersonalInfoTab` (line 2423) is defined but **never rendered** — grep for `<LegacyPersonalInfoTab` returns zero matches
- Contains its own duplicate `calculateAge` helper with the same `'2026-03-31'` reference date

**Triplicate age calculation:**
1. `ITRComputationPage.tsx` line 49: `calculateAgeFromDob()` (added in commit b5e1496)
2. `ITRComputationPage.tsx` line 2424: `calculateAge()` inside `LegacyPersonalInfoTab` (dead code)
3. `PersonalInfoTab.tsx` line 147: inline `setDob` logic

---

## The Three Annual Changes

| Change | What must happen | Current capability |
|---|---|---|
| **1. IT Act 1961 → 2025** | New slab structures, new deduction logic, possibly new computation algorithm | ❌ Router rejects AY 2027-28. Even if it didn't, every module has hardcoded 2026-27 values. No Act version concept exists. |
| **2. Finance Act (annual)** | Rates, CII, caps, thresholds change — algorithm stays same | ❌ constants.py is a single flat module with no AY dimension. Adding AY 2027-28 values would overwrite 2026-27. |
| **3. CBDT Schema (annual)** | Schema file changes field names, maxItems, enums | ❌ Schema filename hardcoded in 3 separate `*_schema.py` files. New schema = manual code changes in 3 places. |

---

## Design Principle

**Every statutory value lives in exactly one place: a `TaxYearProfile` dataclass looked up by assessment year.** No module hardcodes values. No validator duplicates thresholds. No frontend guesses caps. The profile is the single source of truth, threaded through the engine and exposed to the frontend via a single API endpoint.

---

## Phase 1: Frontend Cleanup (11 steps, no architecture change)

These fix the immediate problems. No backend changes needed — components already have `taxResult` from the backend; they just need to stop duplicating calculations and thresholds.

| Step | Action | File(s) | Why |
|---|---|---|---|
| 1.1 | Create `utils/age.ts` with `calculateAgeFromDob(dob, ay)` that derives reference date from AY string | New file | Eliminates triplicate age logic, makes AY-aware |
| 1.2 | Delete `LegacyPersonalInfoTab` (confirmed dead code — never rendered) | ITRComputationPage.tsx L2423+ | Dead code with duplicate age calculation |
| 1.3 | Change `age: 30` → `age: 0` in initial formData state | ITRComputationPage.tsx L413 | Stops sending wrong default age to backend |
| 1.4 | Replace inline age calculation in `PersonalInfoTab.tsx` with utility import | PersonalInfoTab.tsx L147 | Single source of truth for age |
| 1.5 | Replace inline age calculation in `ITRComputationPage.tsx` hydration with utility | ITRComputationPage.tsx L537 | Single source of truth for age |
| 1.6 | Remove local 112A gain derivation; show `—` until backend computes | CapitalGainsEntryManager.tsx L189-197 | Backend already computes this correctly |
| 1.7 | Remove local family pension deduction; show `—` until backend computes | ScheduleOSWorkspace.tsx L239 | Backend already computes via `deduction_57iia` |
| 1.8 | Remove 5 hardcoded 80D caps; remove local cap enforcement; display backend `deductionBreakdown["80D"]` | Section80DManager.tsx L49-53 | Backend enforces caps authoritatively |
| 1.9 | Remove `taxRate`/`tdsThreshold` from `WINNINGS_INFO`; keep label/section only | types/scheduleOS.ts L113-118 | Statutory rates belong in backend |
| 1.10 | Delete `validateITRFormSelection`'s ITR-1 hardcoded threshold branch (lines 1576-1601); rely on `assessFormEligibility` result (already fetched at line 574) | ITRComputationPage.tsx | Eliminates triplicate eligibility logic |
| 1.11 | Add `CURRENT_AY` and `CURRENT_FY` constants; replace AY/FY literals | ITRComputationPage.tsx, AYContext.tsx | Single source for current AY |

**After Phase 1:** Components show `—` or "Awaiting computation" until the backend runs. This is correct production behavior — the user sees authoritative values, never locally-derived guesses.

---

## Phase 2: Backend Year-Adaptive System (9 steps)

### 2.1 Create `TaxYearProfile` dataclass + `ActVersion` enum

**New directory:** `app/engine/tax_years/`

```
app/engine/tax_years/
  __init__.py
  base.py              # TaxYearProfile, SlabBand, ActVersion
  registry.py          # get_profile(ay) → TaxYearProfile
  schema_loader.py     # load_schema(profile, itr_form) → dict
  profiles/
    __init__.py
    ay2026_27.py        # all values consolidated here
    ay2027_28.py        # stub (populated when FA 2026 / IT Act 2025 enacted)
```

`TaxYearProfile` is a **frozen dataclass** carrying every statutory value — the ~90 from constants.py **plus** the 7 categories of hardcoded values (57(iia) caps, special rates, 44AE rates, agri threshold, salary caps, HP loss set-off cap).

It also carries:
- `act_version: ActVersion` — enum (`IT_ACT_1961` or `IT_ACT_2025`)
- `schema_dir: str` — path to the CBDT schema directory for this AY
- `schema_version: str` — e.g., "V1.1" for AY 2026-27
- `reference_date: str` — e.g., "2026-03-31" for AY 2026-27

**Why frozen + per-AY profile?**
- Each AY gets its own immutable profile
- A return saved for AY 2026-27 always computes with the AY 2026-27 profile, even after AY 2027-28 is added
- Backward compatible by design — old returns never recompute differently

**Why `ActVersion` enum?**
- When IT Act 2025 replaces IT Act 1961, the computation *algorithm* may change
- The enum lets the calculator branch on the Act version in exactly one place
- Old AY profiles keep `IT_ACT_1961`; new AY profiles use `IT_ACT_2025`

### 2.2 Create the registry

```python
_PROFILES: dict[str, TaxYearProfile] = {
    "2026-27": AY2026_27_PROFILE,
    # "2027-28": AY2027_28_PROFILE,  # Uncomment when populated
}

def get_profile(assessment_year: str) -> TaxYearProfile:
    if assessment_year not in _PROFILES:
        raise ValueError(f"Unsupported assessment year: {assessment_year}")
    return _PROFILES[assessment_year]
```

### 2.3 Populate the AY 2026-27 profile

`profiles/ay2026_27.py` carries every value from constants.py **plus** the 7 hardcoded categories. This is the single source of truth for AY 2026-27.

### 2.4 Make `constants.py` a backward-compat shim

```python
from app.engine.tax_years.registry import get_profile
_PROFILE = get_profile("2026-27")

OLD_REGIME_SLABS_BELOW_60 = _PROFILE.old_regime_slabs_below_60
SECTION_80C_LIMIT = _PROFILE.section_80c_limit
# ... etc for all 90 constants
```

**Why keep constants.py?** Zero breaking changes. All 25+ engine modules that import from constants continue to work. New code uses the profile directly. Migration is gradual.

### 2.5 Create the schema loader

`schema_loader.py` replaces the 3 hardcoded path modules:

```python
def load_schema(profile: TaxYearProfile, itr_form: str) -> dict:
    cache_key = f"{profile.assessment_year}:{itr_form}"
    if cache_key in _CACHE:
        return _CACHE[cache_key]
    path = repository_root / profile.schema_dir / f"{itr_form}_{profile.schema_year}_Main_{profile.schema_version}.json"
    schema = json.loads(path.read_text(encoding="utf-8"))
    _CACHE[cache_key] = schema
    return schema
```

The profile carries `schema_dir` and `schema_version`, so each AY points to its own schema file. When AY 2027-28 arrives, its profile points to `ITR-1_2027_Main_V1.2.json` — no code change, just a new profile.

### 2.6 Add `/api/tax-year-config/{ay}` endpoint

```python
@router.get("/{assessment_year}")
def get_tax_year_config(assessment_year: str):
    profile = get_profile(assessment_year)
    return {
        "assessmentYear": profile.assessment_year,
        "slabs": {...},
        "standardDeduction": {"old": ..., "new": ...},
        "rebate87A": {...},
        "deductionLimits": {"80C": ..., "80D_selfFamily": ..., ...},
        "capitalGains": {"ltcg112aExemption": ..., ...},
        "eligibility": {"itr1TotalIncomeCap": ..., "itr1AgriculturalIncomeCap": ...},
        "referenceDate": profile.reference_date,
    }
```

This gives the frontend a single endpoint to fetch all statutory values for any AY.

### 2.7 Migrate engine modules (gradual, 6 batches)

Each module gains an optional `profile` parameter defaulting to the AY 2026-27 profile:

```python
# Before
from app.engine.constants import SECTION_80C_LIMIT
def compute(input_data, regime):
    ...  # uses SECTION_80C_LIMIT

# After
from app.engine.tax_years.base import TaxYearProfile
from app.engine.tax_years.registry import get_profile
_DEFAULT = get_profile("2026-27")
def compute(input_data, regime, profile: TaxYearProfile = _DEFAULT):
    limit = profile.section_80c_limit
```

| Batch | Modules | Also fixes hardcoded values |
|---|---|---|
| A | `common/slab_tax.py`, `common/rebate.py`, `common/surcharge.py`, `common/cess.py` | — |
| B | All `schedules/deductions/section_*.py` (12 files) | — |
| C | `schedules/house_property.py`, `schedules/other_sources.py`, `schedules/salary.py` | 57(iia) caps, HP loss cap, salary prof-tax/entertainment |
| D | `schedules/special_rates.py`, `schedules/presumptive.py`, `schedules/agricultural.py` | 7 special rates, 44AE rates, agri threshold |
| E | `calculators/itr1.py`, `routers/tax.py`, `engine/filing_gateway.py` | 80TTA/80TTB inline derivation → profile |
| F | `validators/itr1/calc_rules.py` | All hardcoded literals → profile lookups |

**After each batch, run the full test suite (722 tests).** If all pass, the migration is correct.

### 2.8 Extract shared mapper + remove double computation

**New file:** `app/engine/mappers/itr1_mapper.py`

```python
def map_flat_to_itr1_input(payload: dict, profile: TaxYearProfile) -> ITR1Input:
    """Shared flat→typed mapper used by both router and gateway."""
    ...
```

Both `tax.py` and `filing_gateway.py` import and call this. The gateway's `_build_itr1_input_from_flat` and its duplicated helpers are deleted. The gateway reuses the `ITR1Result` from the compute step instead of re-running the engine.

### 2.9 Remove the AY gate from the router

```python
# Before
if assessment_year != "2026-27":
    raise HTTPException(422, "...")

# After
try:
    profile = get_profile(assessment_year)
except ValueError:
    raise HTTPException(422, f"Unsupported AY: {assessment_year}")
res = compute_itr1(ITR1Input(**common_input), profile=profile)
```

When AY 2027-28 is added to the registry, it passes automatically — no code change in the router.

---

## Phase 3: Frontend Tax-Year Config Context (3 steps)

### 3.1 Create API client + React context

**New file:** `frontend/src/contexts/TaxYearConfigContext.tsx`

```typescript
interface TaxYearConfig {
  assessmentYear: string;
  slabs: { old: {...; new: [...] };
  standardDeduction: { old: number; new: number };
  rebate87A: {...};
  deductionLimits: Record<string, number>;
  capitalGains: {...};
  eligibility: {...};
  referenceDate: string;
}
```

`TaxYearConfigProvider` fetches `/api/tax-year-config/{ay}` when the AY changes and caches in React context. Components use `useTaxYearConfig()`.

### 3.2 Update components to use config context

| Component | Currently hardcoded | Will use |
|---|---|---|
| `Section80DManager.tsx` | 5 cap constants | `config.deductionLimits["80D_*"]` |
| `CapitalGainsEntryManager.tsx` | `125000` | `config.capitalGains.ltcg112aExemption` |
| `autoDetectITRForm` | `5000000`, `5000` | `config.eligibility.itr1TotalIncomeCap` |
| Age calculation | `new Date('2026-03-31')` | `config.referenceDate` |
| `ExemptIncomeWorkspace.tsx` | "₹5,000" text | `config.eligibility.itr1AgriculturalIncomeCap` |

### 3.3 Update `AYContext.tsx` to fetch supported years

```typescript
// Before
const currentAY = '2026-27';

// After
const { data } = useQuery(['supported-years'], () => itrApi.getSupportedYears());
const [currentAY, setCurrentAY] = useState(data?.[0] ?? '2026-27');
```

The frontend learns which AYs are supported from the backend, not from a hardcoded string.

---

## Phase 4: Adding a New Assessment Year (The Future Workflow)

This is the payoff — what happens when AY 2027-28 arrives:

**Case 1: Finance Act 2026 only (same IT Act, new values):**
1. Create `profiles/ay2027_28.py` — copy AY2026_27, update changed values
2. Add `"2027-28": AY2027_28_PROFILE` to registry
3. Drop new CBDT schema files into `Reference Docs by CBDT & ITD/Official JSON Schema/`
4. Set `schema_dir`/`schema_version` in the new profile
5. **Done. No engine code changes. No frontend changes.**

**Case 2: IT Act 2025 enacted (computation algorithm changes):**
1. Create `profiles/ay2027_28.py` with `act_version=ActVersion.IT_ACT_2025`
2. Add calculator branch:
   ```python
   if profile.act_version == ActVersion.IT_ACT_2025:
       return _compute_itr1_act_2025(input_data, profile)
   return _compute_itr1_act_1961(input_data, profile)
   ```
3. Create `app/engine/calculators/itr1_act2025.py` with new computation
4. New schema files + profile registration
5. **Old AY 2026-27 returns still use the 1961 path — backward compatible.**

**Case 3: CBDT schema format change (same Act, same Rules, new JSON structure):**
1. Drop new schema files
2. Update `schema_dir`/`schema_version` in the new profile
3. If the ITD JSON builder must emit different field names, add a builder version branch
4. **Old AY profiles still point to old schema files — backward compatible.**

---

## Implementation Order

| Phase | Step | Action | Commit after? |
|---|---|---|---|
| 1 | 1 | Create `utils/age.ts`, delete `LegacyPersonalInfoTab`, fix age default | Yes |
| 1 | 2 | Remove local 112A, 80D, family pension calculations | Yes |
| 1 | 3 | Remove `validateITRFormSelection` ITR-1 branch, remove `WINNINGS_INFO` rates | Yes |
| 1 | 4 | Add `CURRENT_AY` constant, replace AY/FY literals | Yes |
| 2 | 5 | Create `app/engine/tax_years/` (base, registry) | No |
| 2 | 6 | Create `profiles/ay2026_27.py` (consolidate ALL values including hardcoded ones) | No |
| 2 | 7 | Make `constants.py` a shim; **run tests** | Yes |
| 2 | 8 | Create `schema_loader.py`, replace 3 hardcoded schema modules | Yes |
| 2 | 9 | Add `/api/tax-year-config` endpoint | Yes |
| 2 | 10 | Migrate engine batch A (slab_tax, rebate, surcharge, cess) | Yes |
| 2 | 11 | Migrate engine batch B (12 deduction sections) | Yes |
| 2 | 12 | Migrate engine batch C (house_property, other_sources, salary) + fix hardcoded values | Yes |
| 2 | 13 | Migrate engine batch D (special_rates, presumptive, agricultural) + fix hardcoded values | Yes |
| 2 | 14 | Migrate engine batch E (calculator, router, filing_gateway) + extract shared mapper | Yes |
| 2 | 15 | Migrate engine batch F (validators/calc_rules.py) | Yes |
| 2 | 16 | Remove AY gate from router | Yes |
| 3 | 17 | Create `TaxYearConfigContext` + API client | No |
| 3 | 18 | Update components to use config context | Yes |
| 3 | 19 | Update `AYContext.tsx` to fetch supported years | Yes |
| 4 | 20 | Create `profiles/ay2027_28.py` stub | Yes |
| — | 21 | Full regression: all backend tests + frontend build | — |
| — | 22 | Full regression: Test 1-6 golden suite | — |
| — | 23 | Final commit | Yes |

---

## What This Architecture Achieves

| Requirement | How it's met |
|---|---|
| **IT Act change (1961 → 2025)** | `ActVersion` enum + calculator branches on it in one place; each AY profile declares its Act version |
| **Finance Act (annual rule changes)** | Each AY has its own profile with all values; add a new profile file per year |
| **CBDT Schema (annual format changes)** | Each profile carries `schema_dir`/`schema_version`; schema loader resolves per AY; old AYs keep old schemas |
| **Backward compatibility** | Frozen per-AY profiles; old returns always compute with their year's values; new profiles don't affect old ones |
| **Single source of truth** | No hardcoded values in schedules, validators, or frontend; everything flows from the profile |
| **No duplicated mapper** | Shared `itr1_mapper.py` used by both router and gateway |
| **No double computation** | Gateway reuses the `ITR1Result` from the compute step |
| **No triplicate eligibility** | Frontend relies solely on backend `assessFormEligibility` result |

---

## Execution Priority

> **⚠️ This plan is DEFERRED until ITR-1 is declared production-ready.**
>
> The immediate priority is fixing the Phase 1 frontend issues (steps 1–4) that block ITR-1 production readiness. These are:
> - Hardcoded `age: 30` default
> - Dead `LegacyPersonalInfoTab` code
> - Triplicate age calculation
> - Local 112A/80D/family pension calculations in components
> - Triplicate eligibility validation
> - Wrong `netSalary` derivation
> - Hardcoded reference dates and AY literals
>
> Once ITR-1 testing is complete and the form is declared production-ready, this full plan (Phases 2–4) will be executed to handle the three annual changes.
