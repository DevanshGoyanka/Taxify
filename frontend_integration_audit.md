# Taxify Frontend Integration Audit: Complete Field-Level Pipeline Map

**Date:** 2026-07-21  
**Scope:** ITR-1, ITR-2, ITR-4 — every field across Input Schemas → Calculators → ITD JSON Output  
**Purpose:** Enables a frontend developer to build correct forms, wire multi-step data collection, and map every user-facing field to the exact API contract.

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [The Complete Data Pipeline (All 3 Stages)](#2-the-complete-data-pipeline)
3. [ITR-1: Complete Field Map](#3-itr-1-complete-field-map)
   - [3.1 Frontend → Input Schema (POST /itr1/compute)](#31-itr-1-input-schema)
   - [3.2 Input Schema → Calculator](#32-itr-1-input-schema--calculator)
   - [3.3 Calculator → ITD JSON Builder](#33-itr-1-calculator--itd-json-builder)
   - [3.4 ITD JSON Output vs CBDT Schema](#34-itr-1-itd-json-output-vs-cbdt-schema)
4. [ITR-2: Complete Field Map](#4-itr-2-complete-field-map)
   - [4.1 Frontend → Input Schema (POST /itr2/compute)](#41-itr-2-input-schema)
   - [4.2 Input Schema → Calculator](#42-itr-2-input-schema--calculator)
   - [4.3 Calculator → ITD JSON Builder](#43-itr-2-calculator--itd-json-builder)
5. [ITR-4: Complete Field Map](#5-itr-4-complete-field-map)
   - [5.1 Frontend → Input Schema (POST /itr4/compute)](#51-itr-4-input-schema)
   - [5.2 Input Schema → Calculator](#52-itr-4-input-schema--calculator)
   - [5.3 Calculator → ITD JSON Builder](#53-itr-4-calculator--itd-json-builder)
6. [Response Shape (What the API Returns)](#6-response-shape)
7. [ITD JSON Builder → API Contract (build_itrN_json)](#7-itd-json-builder--api-contract)
8. [Frontend Multi-Step Form Design](#8-frontend-multi-step-form-design)
9. [Validation Mapping (Pydantic → CBDT)](#9-validation-mapping)
10. [Quick Reference: Every Enum, Pattern, and Constraint](#10-quick-reference)

---

## 1. Architecture Overview

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│                              FRONTEND (React/Vue/Angular)                         │
│                                                                                  │
│  Multi-step form collects user data → sends JSON to POST /itrN/compute            │
└───────────────────────────────┬──────────────────────────────────────────────────┘
                                │  JSON (ITRNInput Pydantic schema)
                                ▼
┌──────────────────────────────────────────────────────────────────────────────────┐
│                              BACKEND: FastAPI Router                             │
│                                                                                  │
│  app/routers/itr.py                                                              │
│  - POST /itr1/compute  → ITR1Input → ITR1ComputeResponse                         │
│  - POST /itr2/compute  → ITR2Input → ITR2ComputeResponse                         │
│  - POST /itr4/compute  → ITR4Input → ITR4ComputeResponse                         │
└───────────────────────────────┬──────────────────────────────────────────────────┘
                                │  ITRNInput (validated)
                                ▼
┌──────────────────────────────────────────────────────────────────────────────────┐
│                          CALCULATOR ENGINE (app/engine/calculators/)              │
│                                                                                  │
│  itr1.py: compute(ITR1Input) → ITR1Result                                        │
│  itr2.py: compute(ITR2Input) → ITR2Result                                        │
│  itr4.py: compute(ITR4Input) → ITR4Result                                        │
│                                                                                  │
│  Each calculator orchestrates schedule modules:                                  │
│  salary.py, house_property.py, other_sources.py, capital_gains.py,               │
│  special_rates.py, deductions, presumptive.py, cyla.py, bfla.py,                  │
│  agricultural.py, amt.py, etc.                                                   │
└───────────────────────────────┬──────────────────────────────────────────────────┘
                                │  ITRNResult dataclass
                                ▼
┌──────────────────────────────────────────────────────────────────────────────────┐
│                       ITD JSON BUILDER (app/engine/itd/)                          │
│                                                                                  │
│  itr1.py: build_itr1_json(ITR1Result, ...) → CBDT-compliant ITD JSON             │
│  itr2.py: build_itr2_json(ITR2Result, ...) → CBDT-compliant ITD JSON             │
│  itr4.py: build_itr4_json(ITR4Result, ...) → CBDT-compliant ITD JSON             │
│                                                                                  │
│  common.py: shared helpers (_to_rupees, _creation_info, _verification, etc.)      │
└───────────────────────────────┬──────────────────────────────────────────────────┘
                                │  ITD JSON (validated against CBDT schemas)
                                ▼
┌──────────────────────────────────────────────────────────────────────────────────┐
│                         ITD E-FILING SUBMISSION (ERI / JSON Upload)               │
└──────────────────────────────────────────────────────────────────────────────────┘
```

### Key Data Flows

| Stage | Input | Output | Files |
|-------|-------|--------|-------|
| **Pydantic Validation** | Frontend JSON | `ITRNInput` | `app/schemas/itr1.py`, `itr2.py`, `itr4.py` |
| **Tax Computation** | `ITRNInput` | `ITRNResult` | `app/engine/calculators/itr1.py`, `itr2.py`, `itr4.py` |
| **ITD JSON Generation** | `ITRNResult` + personal info | `{"ITR": {"ITR1": {...}}}` | `app/engine/itd/itr1.py`, `itr2.py`, `itr4.py` |
| **API Response** | `ITRNResult` | `ITRNComputeResponse` | `app/schemas/itr_responses.py` |

---

## 2. The Complete Data Pipeline (All 3 Stages)

Every user-facing value flows through exactly three transformations:

```
FRONTEND FIELD → Pydantic Field → Calculator Variable → ITD JSON Key
```

**Example — Salary Gross:**

| Stage | Field Name | Type | File |
|-------|-----------|------|------|
| Frontend form field | `gross_salary` | number (₹) | — |
| Pydantic input | `salary_income.gross_salary` | `Decimal` | `itr1.py:SalaryIncome` |
| Calculator | `sal.gross_salary` | `Decimal` | `salary.py:SalaryResult` |
| Calculator result | `result.salary_gross` | `Decimal` | `itr1.py:ITR1Result` |
| ITD JSON | `ITR1_IncomeDeductions.GrossSalary` | integer (₹) | `itd/itr1.py` |

**Example — Section 80C Deduction:**

| Stage | Field Name | Type | File |
|-------|-----------|------|------|
| Frontend form field | `amount_80c` | number (₹) | — |
| Pydantic input | `deductions_chapter6a.amount_80c` | `Decimal` | `itr1.py:Chapter6ADeductions` |
| Calculator | `ded.total` | `Decimal` | `deductions/__init__.py:DeductionResult` |
| Calculator result | `result.deductions_total` | `Decimal` | `itr1.py:ITR1Result` |
| ITD JSON | `ScheduleVIA.DeductUndChapVIA.Section80C` | integer (₹) | `itd/itr1.py:_chapter_via()` |

---

## 3. ITR-1: Complete Field Map

ITR-1 is for resident individuals with Salary + 1 House Property + Other Sources income ≤ ₹50L.

### 3.1 ITR-1 Input Schema

**Source:** `app/schemas/itr1.py` — `ITR1Input`  

#### Top-Level Fields

| # | Frontend Field | Pydantic Path | Type | Default | Required | Description |
|---|---------------|---------------|------|---------|----------|-------------|
| 1 | Age Bracket | `age_bracket` | `AgeBracket` enum | — | YES | `below_60`, `60_to_80`, `above_80` |
| 2 | Tax Regime | `tax_regime` | `TaxRegime` enum | — | YES | `old` or `new` |
| 3 | Advance Tax Paid | `advance_tax_paid` | `Decimal` | 0 | NO | Total advance tax deposited |
| 4 | Self-Assessment Tax | `self_assessment_tax_paid` | `Decimal` | 0 | NO | SA tax paid before filing |
| 5 | Filing Date | `filing_date` | `date` (YYYY-MM-DD) | None | NO | Date return is being filed |
| 6 | Due Date | `due_date` | `date` (YYYY-MM-DD) | None | NO | Statutory due date for interest calc |

#### SalaryIncome (`salary_income`)

| # | Frontend Field | Pydantic Field | Type | Default | Required | Range/Guidance |
|---|---------------|---------------|------|---------|----------|----------------|
| 7 | Gross Salary | `gross_salary` | `Decimal` | 0 | NO | ≥ 0. Section 17(1) |
| 8 | Perquisites Value | `perquisites_value` | `Decimal` | 0 | NO | ≥ 0. Section 17(2) |
| 9 | Profits in Lieu | `profits_in_lieu_of_salary` | `Decimal` | 0 | NO | ≥ 0. Section 17(3) |
| 10 | HRA Exempt | `hra_exempt_amount` | `Decimal` | 0 | NO | ≥ 0. Section 10(13A) |
| 11 | LTA Exempt | `lta_exempt_amount` | `Decimal` | 0 | NO | ≥ 0. Section 10(5). New regime: must be 0 |
| 12 | Standard Deduction | `standard_deduction_claimed` | `Decimal` | 0 | NO | ≤ ₹50K old, ≤ ₹75K new |
| 13 | Entertainment Allowance | `entertainment_allowance` | `Decimal` | 0 | NO | ≤ ₹5K. Govt employees only (old regime) |
| 14 | Professional Tax | `professional_tax_paid` | `Decimal` | 0 | NO | ≤ ₹2,500 typical. Old regime only |
| 15 | Govt Employee? | `is_government_employee` | `bool` | False | NO | Required for entertainment allowance |

#### HousePropertyIncome (`house_property_income`)

| # | Frontend Field | Pydantic Field | Type | Required | Values |
|---|---------------|---------------|------|----------|--------|
| 16 | Property Type | `property_type` | `PropertyType` enum | YES | `S` (self-occupied), `L` (let-out), `D` (deemed let-out) |
| 17 | Annual Rent | `annual_rent_received` | `Decimal` | NO | ≥ 0. Must be 0 if `S` |
| 18 | Municipal Taxes | `municipal_taxes_paid` | `Decimal` | NO | ≥ 0. Deducted from rent |
| 19 | Home Loan Interest | `home_loan_interest_paid` | `Decimal` | NO | ≥ 0. Capped at ₹2L for self-occupied |
| 20 | Arrears/Unrealised Rent | `arrears_unrealised_rent_received` | `Decimal` | NO | ≥ 0. Section 25A(1) |

#### OtherSourcesIncome (`other_sources_income`)

| # | Frontend Field | Pydantic Field | Type | Default |
|---|---------------|---------------|------|---------|
| 21 | Savings Bank Interest | `savings_bank_interest` | `Decimal` | 0 |
| 22 | Fixed Deposit Interest | `fixed_deposit_interest` | `Decimal` | 0 |
| 23 | Family Pension | `family_pension_received` | `Decimal` | 0 |
| 24 | Dividend Income | `dividend_income` | `Decimal` | 0 |

#### Chapter6ADeductions (`deductions_chapter6a`)

| # | Frontend Field | Pydantic Field | Type | Cap/Guidance |
|---|---------------|---------------|------|--------------|
| 25 | 80C | `amount_80c` | `Decimal` | ≤ ₹1,50,000 (shared with 80CCC/80CCD1) |
| 26 | 80CCC (Annuity) | `amount_80ccc` | `Decimal` | Shares 80C pool |
| 27 | 80CCD(1) (NPS Employee) | `amount_80ccd1` | `Decimal` | Shares 80C pool |
| 28 | 80CCD(1B) (NPS Addl) | `amount_80ccd1b` | `Decimal` | ≤ ₹50,000. Above 80C ceiling |
| 29 | 80D Self/Family | `amount_80d_self_family` | `Decimal` | ≤ ₹25K (₹50K if senior) |
| 30 | 80D Parents | `amount_80d_parents` | `Decimal` | ≤ ₹25K (₹50K if senior parents) |
| 31 | 80TTA (Savings Int.) | `amount_80tta` | `Decimal` | ≤ ₹10K. For < 60 years only |
| 32 | 80TTB (Senior Deposit Int.) | `amount_80ttb` | `Decimal` | ≤ ₹50K. For ≥ 60 years only |
| 33 | 80E (Education Loan) | `amount_80e` | `Decimal` | No cap. 8 years from repayment start |
| 34 | 80CCD(2) (NPS Employer) | `amount_80ccd2` | `Decimal` | Allowed in both regimes |
| 35 | 80CCH (Agniveer) | `amount_80cch` | `Decimal` | Allowed in both regimes |
| 36 | 80DD (Disabled Dependent) | `amount_80dd` | `Decimal` | ≥ 0 |
| 37 | 80DDB (Specified Disease) | `amount_80ddb` | `Decimal` | ≥ 0 |
| 38 | 80U (Disability) | `amount_80u` | `Decimal` | ≥ 0 |
| 39 | 80EE (First Home Loan) | `amount_80ee` | `Decimal` | ≥ 0 |
| 40 | 80EEA (Affordable Housing) | `amount_80eea` | `Decimal` | ≥ 0 |
| 41 | 80EEB (Electric Vehicle) | `amount_80eeb` | `Decimal` | ≥ 0 |
| 42 | 80G (Donations — simple) | `amount_80g` | `Decimal` | Fallback field |
| 43 | 80G (Donations — structured) | `donations_80g` | `List[Donation80G]` | None |
| 44 | 80GG (Rent — no HRA) | `amount_80gg` | `Decimal` | ≥ 0 |

#### Donation80G (sub-object for `donations_80g`)

| # | Frontend Field | Pydantic Field | Type | Values |
|---|---------------|---------------|------|--------|
| 45 | Cash Amount | `cash_amount` | `Decimal` | ≥ 0 |
| 46 | Non-Cash Amount | `non_cash_amount` | `Decimal` | ≥ 0 |
| 47 | Qualifying % | `qualifying_percentage` | `str` | `"50%"` or `"100%"` |
| 48 | Limit | `limit_on_deduction` | `str` | `"with limit"` or `"without limit"` |

#### CapitalGainsIncome (`capital_gains`)

| # | Frontend Field | Pydantic Field | Type | Cap |
|---|---------------|---------------|------|-----|
| 49 | LTCG 112A | `ltcg_112a` | `Decimal` | ≤ ₹1,25,000 for ITR-1 eligibility |
| 50 | Cost of Acquisition | `cost_of_acquisition` | `Decimal` | ≥ 0 |

#### TDS/TCS

| # | Frontend Field | Pydantic Field | Type |
|---|---------------|---------------|------|
| 51 | TDS on Salary | `tds1_entries` | `List[TDS1Entry]` |
| 52 | TDS on Other | `tds2_entries` | `List[TDS2Entry]` |
| 53 | TCS | `tcs_entries` | `List[TCSEntry]` |

#### TDS1Entry (per Form 16)

| Field | Type | Pattern |
|-------|------|---------|
| `employer_tan` | `str?` | `[A-Z]{4}[0-9]{5}[A-Z]` |
| `employer_name` | `str?` | ≤ 125 chars |
| `income_chargeable` | `Decimal` | ≥ 0 |
| `tds_deducted` | `Decimal` | ≥ 0 |

#### TDS2Entry

| Field | Type | Pattern |
|-------|------|---------|
| `deductor_tan` | `str` | `[A-Z]{4}[0-9]{5}[A-Z]` |
| `deductor_name` | `str?` | ≤ 125 chars |
| `tds_section` | `str` | e.g. "194A", "194I", "194C" |
| `gross_amount` | `Decimal` | ≥ 0 |
| `tds_deducted` | `Decimal` | ≥ 0 |

#### TCSEntry

| Field | Type | Pattern |
|-------|------|---------|
| `collector_tan` | `str` | `[A-Z]{4}[0-9]{5}[A-Z]` |
| `collector_name` | `str?` | — |
| `tcs_section` | `str` | e.g. "206C" |
| `gross_amount` | `Decimal` | ≥ 0 |
| `tcs_collected` | `Decimal` | ≥ 0 |

### 3.2 ITR-1 Input Schema → Calculator

**Source:** `app/engine/calculators/itr1.py` — `compute(ITR1Input) → ITR1Result`

#### Computation Pipeline

```
Step 1: compute_salary(input.salary_income, regime) → sal: SalaryResult
          sal.gross_salary       → result.salary_gross
          sal.income_chargeable  → result.salary_income
          sal.net_salary         → result.salary_net
          sal.deductions_u16     → result.salary_deduction_us16
          sal.standard_deduction → result.salary_deduction_us16ia
          sal.entertainment_allowance → result.salary_entertainment_allowance
          sal.professional_tax   → result.salary_professional_tax

Step 2: compute_hp(input.house_property_income, regime) → hp: HPResult
          hp.income_chargeable  → result.house_property_income
          hp.loss_disallowed    → result.hp_loss_disallowed

Step 3: compute_os(input.other_sources_income, regime) → os: OSResult
          os.income_chargeable  → result.other_sources_income

Step 4: Capital Gains 112A
          IF input.capital_gains:
            check ltcg_112a ≤ ₹1,25,000
            compute_112a(ltcg_112a) → result.capital_gains_112a

Step 5: GTI = salary + hp + os + cg_112a
          check GTI ≤ ₹50,00,000

Step 6: compute_deductions(input.deductions_chapter6a, gti, age, regime, ...) → ded: DeductionResult
          ded.total → result.deductions_total

Step 7: TI = round_to_nearest_10(max(0, gti - ded.total)) → result.taxable_income

Step 8: Slab tax on (TI - cg_112a) → result.slab_tax

Step 9: Special rate tax on cg_112a @ 12.5% → result.special_rate_tax
          tax_before_rebate = slab + special

Step 10: Rebate u/s 87A → result.rebate_87a
           tax_after_rebate = max(0, tax_before - rebate)

Step 11: Surcharge → result.surcharge

Step 12: Cess @ 4% → result.health_education_cess
           gross_tax_liability = tax_after_rebate + surcharge + cess

Step 13: Interest 234A + Late Fee 234F → result.interest_234a, result.late_fee_234f

Step 14: Tax Credits: sum all TDS1 + TDS2 + TCS → result.total_tds, result.total_tcs
           total_taxes_paid = tds + tcs + advance + sa

Step 15: Final = round_to_nearest_10(gross_tax + interest + late_fee)
           diff = final - total_taxes_paid
           IF diff > 0: result.balance_payable = diff
           ELSE:        result.refund_due = abs(diff)
```

#### Complete ITR1Result Fields

| # | Field | Type | Source |
|---|-------|------|--------|
| 1 | `salary_income` | Decimal | sal.income_chargeable |
| 2 | `house_property_income` | Decimal | hp.income_chargeable |
| 3 | `other_sources_income` | Decimal | os.income_chargeable |
| 4 | `capital_gains_112a` | Decimal | compute_112a |
| 5 | `gross_total_income` | Decimal | sum of heads |
| 6 | `deductions_total` | Decimal | ded.total |
| 7 | `taxable_income` | Decimal | round_to_nearest_10(GTI - ded) |
| 8 | `salary_gross` | Decimal | sal.gross_salary |
| 9 | `salary_perquisites` | Decimal | input.salary.perquisites_value |
| 10 | `salary_profits_in_lieu` | Decimal | input.salary.profits_in_lieu_of_salary |
| 11 | `salary_net` | Decimal | sal.net_salary |
| 12 | `salary_deduction_us16` | Decimal | sal.deductions_u16 |
| 13 | `salary_deduction_us16ia` | Decimal | sal.standard_deduction |
| 14 | `salary_entertainment_allowance` | Decimal | sal.entertainment_allowance |
| 15 | `salary_professional_tax` | Decimal | sal.professional_tax |
| 16 | `advance_tax_paid` | Decimal | input.advance_tax_paid |
| 17 | `self_assessment_tax_paid` | Decimal | input.self_assessment_tax_paid |
| 18 | `slab_tax` | Decimal | compute_slab_tax |
| 19 | `special_rate_tax` | Decimal | 112A tax |
| 20 | `tax_before_rebate` | Decimal | 18 + 19 |
| 21 | `rebate_87a` | Decimal | compute_rebate |
| 22 | `tax_after_rebate` | Decimal | 20 - 21 |
| 23 | `surcharge` | Decimal | compute_surcharge |
| 24 | `health_education_cess` | Decimal | 4% of (22 + 23) |
| 25 | `gross_tax_liability` | Decimal | 22 + 23 + 24 |
| 26 | `relief_89` | Decimal | always 0 (not wired) |
| 27 | `interest_234a` | Decimal | compute_234a |
| 28 | `interest_234b` | Decimal | always 0 (not wired) |
| 29 | `interest_234c` | Decimal | always 0 (not wired) |
| 30 | `late_fee_234f` | Decimal | compute_234f |
| 31 | `total_interest` | Decimal | 27 + 28 + 29 |
| 32 | `net_tax_liability` | Decimal | final rounded liability |
| 33 | `total_tds` | Decimal | sum of all TDS |
| 34 | `total_tcs` | Decimal | sum of all TCS |
| 35 | `total_taxes_paid` | Decimal | 33 + 34 + 16 + 17 |
| 36 | `balance_payable` | Decimal | if diff > 0 |
| 37 | `refund_due` | Decimal | if diff < 0 |
| 38 | `hp_loss_disallowed` | Decimal | hp.loss_disallowed |

### 3.3 ITR-1 Calculator → ITD JSON Builder

**Source:** `app/engine/itd/itr1.py` — `build_itr1_json(result, pan, first_name, ...)`

The ITD JSON builder takes `ITR1Result` + personal identity fields and produces the CBDT-compliant JSON.

#### Parameters the Frontend Must Supply to build_itr1_json()

These are NOT from the calculator result — they are identity fields the frontend collects separately:

| # | Parameter | Type | Default | Description | Pattern |
|---|-----------|------|---------|-------------|---------|
| 1 | `pan` | str | — | PAN of assessee | `[A-Z]{5}[0-9]{4}[A-Z]` |
| 2 | `first_name` | str | — | First name | ≤ 75 chars |
| 3 | `middle_name` | str | `""` | Middle name | ≤ 75 chars |
| 4 | `last_name` | str | — | Last name | ≤ 75 chars |
| 5 | `dob` | str | — | Date of birth | `YYYY-MM-DD` |
| 6 | `employer_category` | str | `"OTH"` | Govt/PSU/Other | `"GOV"`, `"PSU"`, `"OTH"` |
| 7 | `residence_no` | str | `"1"` | House/flat number | — |
| 8 | `locality` | str | — | Locality/area | — |
| 9 | `city` | str | — | City | — |
| 10 | `state_code` | str | — | State code | `"07"` = Delhi (2-digit) |
| 11 | `country_code` | str | `"91"` | Country code | — |
| 12 | `mobile_no` | str? | None | Mobile number | 10 digits |
| 13 | `email` | str? | None | Email address | — |
| 14 | `aadhaar` | str? | None | Aadhaar number | 12 digits |
| 15 | `secondary_add` | str | `"N"` | Secondary address flag | `"Y"` or `"N"` |
| 16 | `pin_code` | str? | None | PIN code | 6 digits |
| 17 | `father_name` | str | — | Father's name | — |
| 18 | `ver_place` | str | `"Delhi"` | Place of verification | — |
| 19 | `return_file_sec` | int | `11` | Return filing section | 11-20 |
| 20 | `tds_salary_entries` | list? | None | TDS on salary entries | — |
| 21 | `tds_other_entries` | list? | None | TDS other entries | — |
| 22 | `tcs_entries` | list? | None | TCS entries | — |
| 23 | `cg_sale_consideration` | Decimal? | None | LTCG 112A sale value | — |
| 24 | `cg_cost_acquisition` | Decimal? | None | LTCG 112A cost | — |
| 25 | `cg_112a_income` | Decimal? | None | Taxable 112A income | — |
| 26 | `cg_112a_tax` | Decimal? | None | 112A tax amount | — |

#### Mapping: ITR1Result → ITD JSON Keys

| ITR1Result Field | ITD JSON Path | Rounding |
|-----------------|---------------|----------|
| `salary_gross` | `ITR1_IncomeDeductions.GrossSalary` | `_to_rupees()` |
| `salary_perquisites` | `ITR1_IncomeDeductions.PerquisitesValue` | `_to_rupees()` |
| `salary_profits_in_lieu` | `ITR1_IncomeDeductions.ProfitsInSalary` | `_to_rupees()` |
| `salary_net` | `ITR1_IncomeDeductions.Salary` (when `net_salary + ded_us16`) | `_to_rupees()` |
| `salary_deduction_us16` | `ITR1_IncomeDeductions.DeductionUs16` | `_to_rupees()` |
| `salary_deduction_us16ia` | `ITR1_IncomeDeductions.DeductionUs16ia` | `_to_rupees()` |
| `salary_entertainment_allowance` | `ITR1_IncomeDeductions.EntertainmentAlw16ii` | `_to_rupees()` |
| `salary_professional_tax` | `ITR1_IncomeDeductions.ProfessionalTaxUs16iii` | `_to_rupees()` |
| `salary_income` | `ITR1_IncomeDeductions.IncomeFromSal` | `_to_rupees()` |
| `house_property_income` | `ITR1_IncomeDeductions.IncomeHP` | `_to_rupees()` |
| `other_sources_income` | `ITR1_IncomeDeductions.IncomeOS` | `_to_rupees()` |
| `gross_total_income - cg_112a` | `ITR1_IncomeDeductions.GrossTotIncome` | `_to_rupees()` |
| `gross_total_income` (full GTI with CG) | `ITR1_IncomeDeductions.GrossTotIncomeIncLTCG112A` | `_to_rupees()` |
| `deductions_total` | `ITR1_IncomeDeductions.UsrDeductUndChapVIA` | Chapter VIA object |
| `deductions_total` | `ITR1_IncomeDeductions.DeductUndChapVIA` | Chapter VIA object |
| `taxable_income` | `ITR1_IncomeDeductions.TotalIncome` | `_to_rupees_rounded10()` |
| `slab_tax + special_rate_tax` | `ITR1_TaxComputation.TotalTaxPayable` | `_to_rupees_rounded10()` |
| `rebate_87a` | `ITR1_TaxComputation.Rebate87A` | `_to_rupees_rounded10()` |
| `tax_after_rebate` | `ITR1_TaxComputation.TaxPayableOnRebate` | `_to_rupees_rounded10()` |
| `health_education_cess` | `ITR1_TaxComputation.EducationCess` | `_to_rupees_rounded10()` |
| `gross_tax_liability` | `ITR1_TaxComputation.GrossTaxLiability` | `_to_rupees_rounded10()` |
| `relief_89` | `ITR1_TaxComputation.Section89` | `_to_rupees_rounded10()` |
| `net_tax_liability` | `ITR1_TaxComputation.NetTaxLiability` | `_to_rupees_rounded10()` |
| `total_interest + late_fee_234f` | `ITR1_TaxComputation.TotalIntrstPay` | `_to_rupees_rounded10()` |
| `total_tds` | `TaxPayments.TaxesPaid.TDS` | `_to_rupees()` |
| `total_tcs` | `TaxPayments.TaxesPaid.TCS` | `_to_rupees()` |
| `advance_tax_paid` | `TaxPayments.TaxesPaid.AdvanceTax` | `_to_rupees()` |
| `self_assessment_tax_paid` | `TaxPayments.TaxesPaid.SelfAssessmentTax` | `_to_rupees()` |
| `balance_payable` | `TaxPayments.BalTaxPayable` | `_to_rupees_rounded10()` |
| `refund_due` | `Refund.RefundDue` | `_to_rupees_rounded10()` |

### 3.4 ITR-1 ITD JSON Output vs CBDT Schema

The complete output structure validated against `ITR-1_2026_Main_V1.1.json`:

```json
{
  "ITR": {
    "ITR1": {
      "CreationInfo": { "SWVersionNo": "1.0.0", "SWCreatedBy": "Taxify", ... },
      "FilingStatus": {
        "ReturnFileSec": 11, "OptOutNewTaxRegime": "N",
        "SeventhProvisio139": "N", "AsseseeRepFlg": "N",
        "ItrFilingDueDate": "2026-07-31"
      },
      "Form_ITR1": { "FormName": "ITR-1", "Description": "For AY 2026-27", ... },
      "PersonalInfo": { "AssesseeName": {...}, "PAN": "...", "Address": {...}, ... },
      "ITR1_IncomeDeductions": {
        "GrossSalary": 1075000, "Salary": 1022500,
        "PerquisitesValue": 50000, "ProfitsInSalary": 25000,
        "AllwncExemptUs10": { "AllwncExemptUs10Dtls": [], "TotalAllwncExemptUs10": 0 },
        "DeductionUs16": 5250000, "DeductionUs16ia": 5000000,
        "EntertainmentAlw16ii": 0, "ProfessionalTaxUs16iii": 2500,
        "IncomeFromSal": 1022500, "IncomeHP": -150000, "IncomeOS": 50000,
        "GrossTotIncome": 922500, "GrossTotIncomeIncLTCG112A": 922500,
        "UsrDeductUndChapVIA": { "Section80C": 150000, "Section80D": 25000, ... },
        "DeductUndChapVIA": { ... },
        "TotalIncome": 610000,
        "Schedule80C": { ... }, "Schedule80D": { ... },
        "Schedule80G": { ... }, "Schedule80GGA": { ... },
        "Schedule80DD": { ... }, "Schedule80U": { ... },
        "Schedule80E": { ... }, "Schedule80EE": { ... },
        "Schedule80EEA": { ... }, "Schedule80EEB": { ... },
        "ExemptIncAgriOthUs10": { "ExemptIncAgriOthUs10Dtls": [], "ExemptIncAgriOthUs10Total": 0 }
      },
      "ITR1_TaxComputation": {
        "TotalTaxPayable": 10000, "Rebate87A": 10000,
        "TaxPayableOnRebate": 0, "EducationCess": 0,
        "GrossTaxLiability": 0, "Section89": 0,
        "NetTaxLiability": 0, "TotalIntrstPay": 0,
        "IntrstPay": { "IntrstPayUs234A": 0, "IntrstPayUs234B": 0, "IntrstPayUs234C": 0 },
        "LateFilingFee234F": 0, "FeeDefaultUs234F": 0
      },
      "ScheduleTDS1": { "TDSonSalary": [...], "TotalTDSonSalaries": 0 },
      "ScheduleTDS2": { "TDSonOthThanSal": [...], "TotalTDSonOthThanSals": 0 },
      "ScheduleTCS": { "TCS": [...], "TotalSchTCS": 0 },
      "Schedule112A": { "LongCap112A": 0, "Exemption112A": 125000, ... },
      "ScheduleTDS3Dtls": { "TDS3Details": [], "TotalTDS3Details": 0 },
      "TaxReturnPreparer": { ... },
      "TaxPayments": {
        "TaxesPaid": { "AdvanceTax": 50000, "TDS": 25000, "TCS": 0, "SelfAssessmentTax": 10000 },
        "TotalTaxesPaid": 85000, "BalTaxPayable": 0
      },
      "Refund": { "RefundDue": 0, "BankAccountDtls": { ... } },
      "Verification": {
        "Declaration": { "AssesseeVerName": "...", "FatherName": "...", "AssesseeVerPAN": "..." },
        "Capacity": "S", "Place": "Delhi"
      }
    },
    "ITR1_Form": { ... }, "Digest": "..."
  }
}
```

---

## 4. ITR-2: Complete Field Map

ITR-2 is for individuals/HUFs NOT having business income but having capital gains, foreign assets, or losses.

### 4.1 ITR-2 Input Schema

**Source:** `app/schemas/itr2.py` — `ITR2Input`

#### Top-Level Fields

| # | Frontend Field | Pydantic Path | Type | Required | Description |
|---|---------------|---------------|------|----------|-------------|
| 1 | Age Bracket | `age_bracket` | `AgeBracket` enum | YES | `below_60`, `60_to_80`, `above_80` |
| 2 | Tax Regime | `tax_regime` | `TaxRegime` enum | YES | `old` / `new` |
| 3 | Residential Status | `residential_status` | `ResidentialStatus` | NO | `RES`, `NRI`, `NOR` |
| 4 | Filing Section | `filing_section` | `ReturnFileSection` | NO | 11-20 |
| 5 | Advance Tax | `advance_tax_paid` | `Decimal` | NO | ≥ 0 |
| 6 | SA Tax | `self_assessment_tax_paid` | `Decimal` | NO | ≥ 0 |
| 7 | Filing Date | `filing_date` | `date` | NO | — |
| 8 | Due Date | `due_date` | `date` | NO | — |

#### Shared Income Heads (same as ITR-1)

All `Optional` — only populate if applicable:

| # | Field | Type |
|---|-------|------|
| 9 | `salary_income` | `Optional[SalaryIncome]` |
| 10 | `house_property_income` | `Optional[HousePropertyIncome]` |
| 11 | `other_sources_income` | `Optional[OtherSourcesIncome]` |

#### Capital Gains (ITR-2 unique — full CG schedule)

| # | Frontend Field | Pydantic Field | Type | Description |
|---|---------------|---------------|------|-------------|
| 12 | CG Transactions | `cg_transactions` | `Optional[List[CGTransaction]]` | All capital gains transactions |

#### CGTransaction

| # | Field | Type | Required | Values |
|---|-------|------|----------|--------|
| 13 | Asset Type | `asset_type` | YES | `land_building`, `listed_equity_112a`, `listed_equity_111a`, `unlisted_shares`, `debt_mutual_fund`, `bonds_debentures`, `jewellery`, `other` |
| 14 | Description | `description` | NO | Free text |
| 15 | Date of Acquisition | `date_of_acquisition` | NO | `YYYY-MM-DD` |
| 16 | Date of Transfer | `date_of_transfer` | NO | `YYYY-MM-DD` |
| 17 | Full Consideration | `full_consideration` | NO | ≥ 0 |
| 18 | Cost of Acquisition | `cost_of_acquisition` | NO | ≥ 0 |
| 19 | Indexed Cost | `indexed_cost` | NO | ≥ 0. For land/buildings held > 24 months |
| 20 | Improvement Cost | `improvement_cost` | NO | ≥ 0 |
| 21 | Indexed Improvement | `indexed_improvement` | NO | ≥ 0 |
| 22 | Expenditure on Transfer | `expenditure_on_transfer` | NO | ≥ 0 |
| 23 | Deduction u/s 54 | `deduction_us54` | NO | ≥ 0. Residential house |
| 24 | Deduction u/s 54B | `deduction_us54b` | NO | ≥ 0. Agricultural land |
| 25 | Deduction u/s 54EC | `deduction_us54ec` | NO | ≥ 0. Capital gains bonds |
| 26 | Deduction u/s 54F | `deduction_us54f` | NO | ≥ 0. Other asset → residential house |
| 27 | STT Paid? | `is_stt_paid` | NO | True/False |
| 28 | FMV Jan 2018 | `fair_market_value_jan2018` | NO | ≥ 0. For grandfathering u/s 112A |

#### CG112AScrip (for Schedule 112A)

| # | Field | Type | Pattern |
|---|-------|------|---------|
| 29 | ISIN Code | `isin_code` | `str?` | `IN[0-9A-Z]{10}` |
| 30 | Share/Unit Name | `share_unit_name` | `str?` | ≤ 125 |
| 31 | Before 31-Jan-2018? | `is_before_31jan2018` | `bool` | — |
| 32 | No. of Shares/Units | `num_shares_units` | `Decimal?` | ≥ 0 |
| 33 | Sale Price/Share | `sale_price_per_share` | `Decimal?` | ≥ 0 |
| 34 | Total Sale Value | `total_sale_value` | `Decimal` | ≥ 0 |
| 35 | Cost Acq w/o Index | `cost_acq_without_index` | `Decimal` | ≥ 0 |
| 36 | FMV Per Share | `fmv_per_share` | `Decimal?` | ≥ 0 |
| 37 | Total FMV | `total_fmv` | `Decimal` | ≥ 0 |
| 38 | Expenditure on Transfer | `expenditure_on_transfer` | `Decimal` | ≥ 0 |
| 39 | Total Deductions | `total_deductions` | `Decimal` | ≥ 0 |
| 40 | Balance | `balance` | `Decimal` | — |

#### VDATransaction (Virtual Digital Assets)

| # | Field | Type | Required |
|---|-------|------|----------|
| 41 | Date of Acquisition | `date_of_acquisition` | YES |
| 42 | Date of Transfer | `date_of_transfer` | YES |
| 43 | Acquisition Cost | `acquisition_cost` | NO (≥ 0) |
| 44 | Consideration | `consideration_received` | NO (≥ 0) |
| 45 | Income from VDA | `income_from_vda` | NO (≥ 0) |

#### Brought-Forward Losses

| # | Field | Type |
|---|-------|------|
| 46 | BF Losses | `bf_losses` | `Optional[List[BFLossItem]]` |

#### BFLossItem

| Field | Type | Required |
|-------|------|----------|
| `assessment_year` | `str` | YES (e.g. "2023-24") |
| `head` | `str` | YES |
| `sub_category` | `str` | NO |
| `original_loss` | `Decimal` | NO (≥ 0) |
| `brought_forward` | `Decimal` | NO (≥ 0) |

#### Special Rate Incomes

| # | Field | Type |
|---|-------|------|
| 47 | SI Entries | `si_entries` | `Optional[List[ScheduleSIEntry]]` |

#### ScheduleSIEntry

| Field | Type | Required |
|-------|------|----------|
| `section` | `str` | YES (e.g. "115BB", "115BBE", "115BBF") |
| `description` | `str?` | NO |
| `gross_income` | `Decimal` | NO (≥ 0) |
| `deductions` | `Decimal` | NO (≥ 0) |
| `tax_rate_pct` | `Decimal?` | NO (0-100) |

#### Agricultural & Exempt Income

| # | Field | Pydantic Path | Type |
|---|-------|---------------|------|
| 48 | Agricultural Income | `agricultural_income` | `Optional[AgriculturalIncome]` |
| 49 | Exempt Income | `exempt_income` | `Optional[ExemptIncome]` |

#### AgriculturalIncome

| Field | Type |
|-------|------|
| `gross_agricultural_income` | `Decimal` (≥ 0) |
| `agricultural_deductions` | `Decimal` (≥ 0) |
| `share_from_firm` | `Decimal` (≥ 0) |

#### ExemptIncome

| Field | Type |
|-------|------|
| `ppf_interest` | `Decimal` |
| `sukanya_samriddhi_interest` | `Decimal` |
| `tax_free_bond_interest` | `Decimal` |
| `nre_interest` | `Decimal` |
| `other_exempt` | `Decimal` |

#### Foreign Schedules

| # | Field | Pydantic Path | Type |
|---|-------|---------------|------|
| 50 | Foreign Income | `fsi_entries` | `Optional[List[FSICountryEntry]]` |
| 51 | Tax Relief | `tr1_entries` | `Optional[List[TR1Entry]]` |

#### FSICountryEntry

| Field | Type | Required |
|-------|------|----------|
| `country_code` | `str` | YES (2 chars) |
| `tax_identification_no` | `str?` | NO |
| `salary_income` | `Decimal` | NO |
| `hp_income` | `Decimal` | NO |
| `cg_income` | `Decimal` | NO |
| `os_income` | `Decimal` | NO |
| `total_income` | `Decimal` | NO |
| `tax_paid_outside_india` | `Decimal` | NO |

#### TR1Entry

| Field | Type | Required |
|-------|------|----------|
| `country_code` | `str` | YES (2 chars) |
| `income_included_in_this_return` | `Decimal` | NO |
| `tax_paid_outside_india` | `Decimal` | NO |
| `indian_tax_payable` | `Decimal` | NO |
| `relief_claimed` | `Decimal` | NO |
| `is_dtaa_claim` | `bool` | NO |

#### Clubbing, AMT

| # | Field | Pydantic Path | Type |
|---|-------|---------------|------|
| 52 | Clubbing (SPI) | `spi_entries` | `Optional[List[SPIEntry]]` |
| 53 | AMT | `amt_input` | `Optional[AMTInput]` |

#### PartA-GEN1 (ITR-2 specific identity fields)

| # | Field | Type | Required | Pattern/Values |
|---|-------|------|----------|----------------|
| 54 | PAN | `parta_gen1.pan` | YES | `[A-Z]{5}[0-9]{4}[A-Z]` |
| 55 | First Name | `parta_gen1.first_name` | YES | ≤ 75 chars |
| 56 | Middle Name | `parta_gen1.middle_name` | NO | ≤ 75 chars |
| 57 | Surname | `parta_gen1.surname` | YES | 1-75 chars |
| 58 | DOB | `parta_gen1.dob` | YES | `YYYY-MM-DD` |
| 59 | Aadhaar | `parta_gen1.aadhaar_card_no` | NO | `[0-9]{12}` |
| 60 | Mobile | `parta_gen1.mobile_no` | YES | `[1-9][0-9]{9}` |
| 61 | Email | `parta_gen1.email_address` | NO | — |
| 62 | Residential Status | `parta_gen1.residential_status` | NO | `RES`, `NRI`, `NOR` |
| 63 | Return File Section | `parta_gen1.return_file_section` | NO | 11-20 |
| 64 | Receipt No. | `parta_gen1.receipt_no` | NO | `[0-9]{15}` |
| 65 | Orig Return Date | `parta_gen1.orig_return_filed_date` | NO | `YYYY-MM-DD` |
| 66 | Filing Due Date | `parta_gen1.itr_filing_due_date` | NO | `YYYY-MM-DD` |
| 67 | 7th Proviso 139 | `parta_gen1.seventh_provisio_139` | NO | `"Y"` / `"N"` |
| 68 | Employer Category | `parta_gen1.employer_category` | NO | `"GOVT"`, `"PSU"`, `"OTHER"` |
| 69 | Filed by Rep? | `parta_gen1.return_filed_by_representative` | NO | `"Y"` / `"N"` |

### 4.2 ITR-2 Input Schema → Calculator

**Source:** `app/engine/calculators/itr2.py` — `compute(ITR2Input) → ITR2Result`

The ITR-2 calculator is the most complex. Here's the full computation pipeline:

```
Step 1: Salary → sal: SalaryResult
Step 2: House Property → hp: HPResult
Step 3: Other Sources → os: OSResult

Step 4: Capital Gains (full CG)
  For each CGTransaction:
    - listed_equity_111a → 111A STCG / 112A LTCG (365-day test)
    - land_building → STCG / LTCG (730-day test) with 54/54B/54EC/54F
    - other → STCG
  For each CG112AScrip → added to 112A LTCG assets
  For each VDATransaction → VDA compute
  compute_stcg(stcg_111a, stcg_land, stcg_other) → stcg: STCGResult
  compute_ltcg(ltcg_112a, ltcg_land, ltcg_other, ltcg_dtaa) → ltcg: LTCGResult
  compute_vda(vda_entries) → vda_income
  compute_exemptions(54, 54B, 54EC, 54F) → exemptions
  aggregate_cg(stcg, ltcg, vda, exemptions) → cg_result

Step 5: Clubbing (SPI)
  Sum all spi.amount_included → add to other_sources_income

Step 6: GTI before loss = salary + hp + cg + os

Step 7: CYLA (Current Year Loss Adjustment)
  compute_cyla(CYLAInput(...)) → cyla: CYLAResult
  result.cyla_total_set_off = cyla.total_loss_set_off
  result.cyla_remaining = cyla.total_loss_remaining

Step 8: BFLA (Brought Forward Loss Adjustment)
  compute_bfla(BFLAInput(...)) → bfla: BFLAResult
  result.bfla_total_set_off = bfla.total_bf_loss_set_off

Step 9: GTI after losses = gti_before - cyla_off - bfla_off

Step 10: Agricultural Income
  compute_agri(gross, deductions, share) → result.net_agricultural_income

Step 11: Chapter VI-A Deductions
  compute_deductions(...) → ded: DeductionResult
  result.deductions_total = ded.total

Step 12: Taxable Income = round_to_nearest_10(max(0, gti - ded.total))

Step 13: Aggregate Income = TI + net_agricultural_income

Step 14: Special Rate Income Tax
  compute_112a(ltcg.income_112a) → si_entries
  compute_111a(stcg.income_111a) → si_entries
  compute_vda(vda_income) → si_entries
  Custom SI entries from input
  aggregate_si(si_entries) → si_result: SpecialRatesResult

Step 15: Slab Tax on (TI - total_special_rate_income)
  + partial_integration_tax (if agri > 5000, old regime)

Step 16: AMT (u/s 115JC)

Step 17: Total tax before relief = slab + special + amt

Step 18: Rebate u/s 87A

Step 19: Surcharge

Step 20: Cess @ 4%

Step 21: Gross tax liability

Step 22: Foreign tax relief u/s 90/91 (TR1)

Step 23: Interest 234A + Late Fee 234F

Step 24: Tax Credits (TDS + TCS + Advance + SA)

Step 25: Final = round_to_nearest_10(gross_tax - relief + interest + late_fee)
  diff = final - total_taxes_paid
```

#### Complete ITR2Result Fields

| # | Field | Type |
|---|-------|------|
| 1 | `salary_income` | Decimal |
| 2 | `house_property_income` | Decimal |
| 3 | `capital_gains_income` | Decimal |
| 4 | `other_sources_income` | Decimal |
| 5 | `vda_income` | Decimal |
| 6 | `clubbing_income` | Decimal |
| 7 | `gti_before_loss_setoff` | Decimal |
| 8 | `cyla_total_set_off` | Decimal |
| 9 | `bfla_total_set_off` | Decimal |
| 10 | `gti_after_loss_setoff` | Decimal |
| 11 | `gross_total_income` | Decimal |
| 12 | `net_agricultural_income` | Decimal |
| 13 | `partial_integration_tax` | Decimal |
| 14 | `deductions_total` | Decimal |
| 15 | `taxable_income` | Decimal |
| 16 | `aggregate_income` | Decimal |
| 17 | `slab_tax` | Decimal |
| 18 | `special_rate_tax` | Decimal |
| 19 | `amt_tax` | Decimal |
| 20 | `total_tax_before_relief` | Decimal |
| 21 | `tax_before_rebate` | Decimal |
| 22 | `rebate_87a` | Decimal |
| 23 | `tax_after_rebate` | Decimal |
| 24 | `surcharge` | Decimal |
| 25 | `health_education_cess` | Decimal |
| 26 | `gross_tax_liability` | Decimal |
| 27 | `relief_89` | Decimal |
| 28 | `relief_90_91` | Decimal |
| 29 | `interest_234a` | Decimal |
| 30 | `interest_234b` | Decimal |
| 31 | `interest_234c` | Decimal |
| 32 | `late_fee_234f` | Decimal |
| 33 | `total_interest` | Decimal |
| 34 | `net_tax_liability` | Decimal |
| 35 | `total_tds` | Decimal |
| 36 | `total_tcs` | Decimal |
| 37 | `total_advance_tax` | Decimal |
| 38 | `total_self_assessment_tax` | Decimal |
| 39 | `total_taxes_paid` | Decimal |
| 40 | `balance_payable` | Decimal |
| 41 | `refund_due` | Decimal |
| 42 | `hp_loss_disallowed` | Decimal |
| 43 | `cyla_remaining` | Decimal |
| 44 | `bfla_remaining` | Decimal |

### 4.3 ITR-2 Calculator → ITD JSON Builder

**Source:** `app/engine/itd/itr2.py` — `build_itr2_json(result, pan, first_name, ...)`

#### Parameters Supplied by Frontend

Same 26+ parameters as ITR-1 PLUS ITR-2 specific:

| # | Parameter | Type | Default | Description |
|---|-----------|------|---------|-------------|
| 27 | `residential_status` | str | `"RES"` | `"RES"`, `"NRI"`, `"NOR"` |
| 28 | `return_file_sec` | int | `11` | 11-20 |
| 29 | `assessee_status` | str | `"I"` | `"I"`, `"H"`, `"F"` (ITR-2: individual/HUF) |
| 30 | `tds1_entries` | list? | None | TDS on salary list |
| 31 | `tds2_entries` | list? | None | TDS on other list |

#### ITR-2 ITD JSON Structure (43+ schedules)

```
ITR / ITR2
├── CreationInfo
├── Form_ITR2
├── PartA_GEN1
│   ├── PersonalInfo (nested: AssesseeName, PAN, Address, DOB, Status, Aadhaar)
│   └── FilingStatus (ReturnFileSec, OptOutNewTaxRegime, ResidentialStatus,
│                      HeldUnlistedEqShrPrYrFlg, FiiFpiFlag, ItrFilingDueDate)
├── ScheduleCYLA (14 head blocks × {IncCYLA} — nested by income head)
│   ├── Salary / HP / STCG20Per / STCG30Per / STCGAppRate / STCGDTAARate
│   ├── LTCG12_5Per / LTCGDTAARate / IncOSDTAA / OthSrcExclRaceHorse / OthSrcRaceHorse
│   ├── LossRemAftSetOff, TotalCurYr, TotalLossSetOff
├── ScheduleBFLA (same 14 head blocks × {IncBFLA})
├── PartB-TI (Computation of Total Income)
│   ├── Salaries, IncomeFromHP, CapGain {ShortTerm, LongTerm}, IncFromOS
│   ├── CurrentYearLoss, BalanceAfterSetoffLosses, BroughtFwdLossesSetoff
│   ├── GrossTotalIncome, DeductionsUnderScheduleVIA, TotalIncome, TotalTI
├── PartB_TTI (Computation of Tax Liability)
│   ├── ComputationOfTaxLiability {TaxPayableOnTI, TaxRelief, Rebate87A,
│   │     Surcharge25ofSI, SurchargeOnAboveCrore, TotalSurcharge, EducationCess,
│   │     GrossTaxLiability, GrossTaxPay, CreditUS115JD, NetTaxLiability,
│   │     IntrstPay {234A, 234B, 234C, 234F, 234I}, AggregateTaxInterestLiability}
│   ├── Surcharge, HealthEduCess, AssetOutIndiaFlag
│   ├── TaxPaid {TaxesPaid {AdvanceTax, TDS, TCS, SelfAssessmentTax, TotalTaxesPaid}}
│   └── Refund {RefundDue, BankAccountDtls {BankDtlsFlag, AddtnlBankDetails}}
├── ScheduleS (Salary: Salaries[], TotIncUnderHeadSalaries)
├── ScheduleHP (PropertyDetails[], TotalIncomeChargeableUnHP)
├── ScheduleOS (55-field IncOthThanOwnRaceHorse sub-object)
├── ScheduleCGFor23 (ShortTermCapGainFor23 + LongTermCapGain23 + DeducClaimInfo + CurrYrLosses)
├── Schedule112A, Schedule115AD, ScheduleVDA
├── ScheduleCFL (12 loss summary objects)
├── ScheduleVIA (DeductUndChapVIA + UsrDeductUndChapVIA)
├── ScheduleSI, ScheduleEI, ScheduleFA (10 sub-object arrays)
├── ScheduleAL, Schedule5A2014, ScheduleESOP
├── Schedule80C/D/G/GGA/GGC/DD/U/E/EE/EEA/EEB
├── ScheduleIT (TaxPayment challan array)
├── ScheduleTDS1/2/3, ScheduleTCS
├── ScheduleFSI, ScheduleTR1, ScheduleAMT, ScheduleAMTC
├── TaxReturnPreparer, Verification
```

---

## 5. ITR-4: Complete Field Map

ITR-4 is for resident individuals/HUFs/firms under presumptive taxation (44AD/44ADA/44AE) with income ≤ ₹50L.

### 5.1 ITR-4 Input Schema

**Source:** `app/schemas/itr4.py` — `ITR4Input`

#### Top-Level Fields

| # | Frontend Field | Pydantic Path | Type | Required | Description |
|---|---------------|---------------|------|----------|-------------|
| 1 | Age Bracket | `age_bracket` | `AgeBracket` enum | YES | — |
| 2 | Tax Regime | `tax_regime` | `TaxRegime` enum | YES | — |
| 3 | Presumptive Scheme | `presumptive_scheme` | `PresumptiveScheme` enum | YES | `none`, `44AD`, `44ADA`, `44AE` |

#### PresumptiveBusinessIncome44AD (`business_income_44ad`)

| # | Field | Type | Required | Cap |
|---|-------|------|----------|-----|
| 4 | Total Turnover | `total_turnover` | `Decimal` | YES (if 44AD) | ≤ ₹3 Cr |
| 5 | Digital Turnover | `digital_turnover` | `Decimal` | NO | ≥ 0 |
| 6 | Cash Turnover | `cash_turnover` | `Decimal` | NO | ≥ 0. ≤ 5% for ₹3 Cr limit |
| 7 | Income Declared | `income_declared` | `Decimal?` | NO | If higher than presumptive |

#### PresumptiveProfessionalIncome44ADA (`professional_income_44ada`)

| # | Field | Type | Required | Cap |
|---|-------|------|----------|-----|
| 8 | Gross Receipts | `gross_receipts` | `Decimal` | YES (if 44ADA) | ≤ ₹75L |
| 9 | Digital Receipts | `digital_receipts` | `Decimal` | NO | ≥ 0 |
| 10 | Cash Receipts | `cash_receipts` | `Decimal` | NO | ≤ 5% for ₹75L limit |
| 11 | Income Declared | `income_declared` | `Decimal?` | NO | If > 50% of receipts |

#### PresumptiveGoodsCarriage44AE (`goods_carriage_44ae`)

| # | Field | Type | Required | Cap |
|---|-------|------|----------|-----|
| 12 | Vehicles | `vehicles` | `List[GoodsCarriageVehicle]` | YES (if 44AE) | ≤ 10 vehicles |

#### GoodsCarriageVehicle (per vehicle)

| # | Field | Type | Required | Values |
|---|-------|------|----------|--------|
| 13 | Heavy Vehicle? | `is_heavy_goods_vehicle` | `bool` | YES | — |
| 14 | GVW (Tons) | `gross_vehicle_weight_tons` | `Decimal?` | For heavy | ≥ 0 |
| 15 | Months Owned | `months_owned` | `int` | YES | 1-12 |
| 16 | Income Declared | `income_declared` | `Decimal?` | NO | If higher |

#### Shared Heads (optional, same as ITR-1)

| # | Field | Type |
|---|-------|------|
| 17 | `salary_income` | `Optional[SalaryIncome]` |
| 18 | `house_property_income` | `Optional[HousePropertyIncome]` |
| 19 | `other_sources_income` | `Optional[OtherSourcesIncome]` |
| 20 | `deductions_chapter6a` | `Optional[Chapter6ADeductions]` |
| 21 | `capital_gains` | `Optional[CapitalGainsIncome]` |
| 22 | `advance_tax_paid` | `Decimal` |
| 23 | `self_assessment_tax_paid` | `Decimal` |

### 5.2 ITR-4 Input Schema → Calculator

**Source:** `app/engine/calculators/itr4.py`

```
Step 1: Presumptive income via compute_presumptive(input) → pres: PresumptiveResult
  44AD: presumptive = digital*6% + cash*8% (or income_declared)
  44ADA: presumptive = max(gross*50%, income_declared)
  44AE: sum over vehicles (₹1000/ton/month or ₹7500/month)

Step 2-5: Same as ITR-1 (Salary, HP, OS, CG-112A)

Step 6: GTI = presumptive + salary + hp + os + cg_112a
  check GTI ≤ ₹50,00,000

Steps 7-16: Same as ITR-1 (deductions, TI, slab tax, special rate, rebate, surcharge, cess)
```

### 5.3 ITR-4 Calculator → ITD JSON Builder

**Source:** `app/engine/itd/itr4.py`

Key differences from ITR-1 in the ITD JSON:

| ITR-1 | ITR-4 | Reason |
|-------|-------|--------|
| `OptOutNewTaxRegime: "N"` | `Form10IEAEarlierAYOldRegime: "NA"` + 13 Form10IEA fields | ITR-4 uses Form 10-IEA for regime election |
| `ItrFilingDueDate: "2026-07-31"` | `ItrFilingDueDate: "2026-08-31"` | ITR-4 due date is 31 Aug |
| No `Status` field | `PersonalInfo.Status: "I"/"H"/"F"` | ITR-4 covers individuals, HUFs, firms |
| No `Address.Phone` | `Address.Phone: {STDcode, PhoneNo}` | Required in ITR-4 |
| `ITR1_IncomeDeductions` | `IncomeDeductions` (different name) | Different schema root |
| `ExemptIncAgriOthUs10` | `TaxExmpIntIncDtls` | ITR-4 uses different exempt income schedule |
| `EntertainmentAlw16ii` | `EntertainmntalwncUs16ii` | Different spelling |
| `DeductUndChapVIA` has 80GGA | No `Section80GGA` | 80GGA unavailable for biz income |
| `Schedule80D.NonSrctznSlfFam.HealthInsPremSlfFam` | same structure | Same 80D structure |
| Root `TaxPayments` | No root `TaxPayments` | Folded into `ScheduleIT` |
| `ScheduleBP` for presumptive turnover | — | ITR-4 only |

---

## 6. Response Shape (What the API Returns)

**Source:** `app/schemas/itr_responses.py`

### POST /itr1/compute → ITR1ComputeResponse

```json
{
  "salary_income": "1022500",
  "house_property_income": "-150000",
  "other_sources_income": "50000",
  "gross_total_income": "922500",
  "deductions_chapter6a": "185000",
  "taxable_income": "610000",
  "slab_tax": "12000",
  "rebate_87a": "12000",
  "tax_after_rebate": "0",
  "surcharge": "0",
  "health_education_cess": "0",
  "total_tax_payable": "0",
  "hp_loss_disallowed": "0"
}
```

### POST /itr2/compute → ITR2ComputeResponse

```json
{
  "salary_income": "1500000",
  "house_property_income": "-200000",
  "capital_gains_income": "590000",
  "other_sources_income": "70000",
  "vda_income": "300000",
  "clubbing_income": "0",
  "gti_before_loss_setoff": "2260000",
  "cyla_total_set_off": "200000",
  "bfla_total_set_off": "100000",
  "gti_after_loss_setoff": "1960000",
  "gross_total_income": "1960000",
  "net_agricultural_income": "50000",
  "deductions_total": "185000",
  "taxable_income": "1775000",
  "aggregate_income": "1825000",
  "slab_tax": "25000", "special_rate_tax": "151250", "amt_tax": "0",
  "total_tax_before_relief": "176250", "tax_before_rebate": "176250",
  "rebate_87a": "0", "tax_after_rebate": "176250",
  "surcharge": "0", "health_education_cess": "7050",
  "gross_tax_liability": "183300",
  "relief_89": "0", "relief_90_91": "0",
  "net_tax_liability": "183300",
  "total_tds": "50000", "total_tcs": "5000",
  "total_taxes_paid": "155000",
  "balance_payable": "28300", "refund_due": "0",
  "hp_loss_disallowed": "0"
}
```

### POST /itr4/compute → ITR4ComputeResponse

```json
{
  "pgbp_income": "1200000",
  "salary_income": "500000",
  "house_property_income": "-100000",
  "other_sources_income": "30000",
  "capital_gains_112a": "0",
  "gross_total_income": "1630000",
  "deductions_chapter6a": "150000",
  "taxable_income": "1480000",
  "slab_tax": "95000", "special_rate_tax": "0",
  "rebate_87a": "0", "tax_after_rebate": "95000",
  "surcharge": "0", "health_education_cess": "3800",
  "total_tax_payable": "98800",
  "hp_loss_disallowed": "0"
}
```

---

## 7. ITD JSON Builder → API Contract

**IMPORTANT:** The ITD JSON builder is currently NOT exposed via any API endpoint. It exists as a standalone function. To integrate:

1. Create a new endpoint: `POST /itr1/build-json` that accepts `ITR1Result` + identity params
2. Call `build_itr1_json(result, pan=..., first_name=..., ...)` 
3. Return the complete ITD JSON

The builder signature for each form:

```python
# ITR-1
json_output = build_itr1_json(
    result,        # ITR1Result (from calculator)
    pan="ABCDE1234F",
    first_name="John",
    middle_name="",
    last_name="Doe",
    dob="1990-01-01",
    employer_category="OTH",
    residence_no="1",
    locality="MG Road",
    city="Mumbai",
    state_code="27",
    country_code="91",
    mobile_no="9876543210",
    email="john@example.com",
    aadhaar="123456789012",
    father_name="Richard Doe",
    ver_place="Mumbai",
    tds_salary_entries=[...],
    tds_other_entries=[...],
    tcs_entries=[...],
    cg_sale_consideration=Decimal("0"),
    cg_cost_acquisition=Decimal("0"),
    cg_112a_income=Decimal("0"),
    cg_112a_tax=Decimal("0"),
)

# ITR-2
json_output = build_itr2_json(
    result, pan=..., first_name=..., ...,
    residential_status="RES",
    return_file_sec=11,
    assessee_status="I",
    tds1_entries=[...],
    tds2_entries=[...],
)

# ITR-4
json_output = build_itr4_json(
    result, pan=..., first_name=..., ...,
    assessee_status="I",
    bp_cash_turnover=Decimal("0"),
    bp_other_turnover=Decimal("0"),
    bp_scheme="44AD",
    # Form 10IEA parameters (13 fields)
    form_10iea_earlier_ay_old_regime="NA",
    ...
)
```

---

## 8. Frontend Multi-Step Form Design

### Recommended Form Steps

#### ITR-1 (5 Steps)

```
Step 1: Personal Info
  └─ PAN, Name (First/Middle/Last), DOB, Age Bracket, Tax Regime
  └─ Address: Residence No, Locality, City, State, PIN, Country

Step 2: Salary Income
  └─ Gross Salary, Perquisites, Profits in Lieu, HRA Exempt, LTA
  └─ Standard Deduction, Entertainment Allowance, Professional Tax
  └─ Is Govt Employee? checkbox

Step 3: House Property + Other Sources
  └─ Property Type dropdown (Self-Occupied / Let-Out / Deemed)
  └─ [If Let-Out]: Annual Rent, Municipal Taxes
  └─ Home Loan Interest
  └─ Savings Interest, FD Interest, Family Pension, Dividend

Step 4: Deductions (Chapter VI-A)
  └─ 80C: aggregate investments (or detailed sub-form)
  └─ 80D: Self/Family insurance + Parents insurance
  └─ 80TTA/80TTB: deposit interest deduction
  └─ 80E, 80CCD(1B), 80CCD(2), 80CCH
  └─ 80G: donation entries (cash, non-cash, 50%/100%, with/without limit)

Step 5: Tax Payments + Review
  └─ TDS on Salary (Form 16) — multiple entries
  └─ TDS on Other (Form 16A/26AS) — multiple entries
  └─ TCS entries
  └─ Advance Tax + Self-Assessment Tax
  └─ Filing Date, Due Date
  └─ Summary: GTI, Deductions, TI, Tax, Refund/Payable
```

#### ITR-2 (10 Steps)

```
Step 1: Personal Info + Filing Status
  └─ PAN, Name, DOB, Residential Status, Filing Section
  └─ Employer Category, Return Filed by Representative?

Step 2: Salary + House Property + Other Sources
  └─ Same as ITR-1 Steps 2-3

Step 3: Capital Gains — Asset List
  └─ Add CG Transaction: Asset Type, Dates, Consideration, Cost
  └─ Per transaction: Indexed Cost, Improvement, 54/54B/54EC/54F deductions
  └─ STT Paid checkbox

Step 4: Schedule 112A Scrips + VDA
  └─ Per scrip: ISIN, Sale Value, FMV, Cost w/o Index, Deductions
  └─ VDA Transactions: Dates, Cost, Consideration

Step 5: Brought-Forward Losses (BFLA)
  └─ Per loss: Assessment Year, Head, Sub-Category, Original Loss, BF Amount

Step 6: Special Rate Incomes (SI)
  └─ Per entry: Section code, Gross Income, Deductions, Tax Rate

Step 7: Agricultural + Exempt Income (EI)
  └─ Gross Agri Receipts, Agri Deductions, Share from Firm
  └─ PPF Interest, SSY Interest, Tax-Free Bonds, NRE Interest, Other

Step 8: Foreign Schedules (FSI + TR1)
  └─ Per country: Income breakdown, Tax Paid, Relief Claimed, DTAA flag

Step 9: Deductions + Clubbing + AMT
  └─ Same Chapter VI-A fields as ITR-1
  └─ SPI entries: Spouse Name, Relationship, Amount, Head
  └─ AMT: Adjusted TI, Rate, Credit BF, Credit Utilised

Step 10: Tax Payments + Review
  └─ TDS Salary, TDS Other, TCS
  └─ Advance Tax, SA Tax
  └─ Full summary with CG breakdown, CYLA, BFLA, SI, EI
```

#### ITR-4 (6 Steps)

```
Step 1: Personal Info + Scheme Selection
  └─ Same as ITR-1 Step 1 + Presumptive Scheme dropdown

Step 2: Presumptive Business/Professional Income
  └─ [If 44AD]: Total Turnover, Digital Turnover, Cash Turnover
  └─ [If 44ADA]: Gross Receipts, Digital Receipts, Cash Receipts
  └─ [If 44AE]: Vehicle List (Heavy?, GVW, Months Owned)

Step 3-6: Same as ITR-1 Steps 2-5
  └─ Plus Form 10-IEA parameters if old regime
```

### Field Validation Rules (Frontend)

| Rule | Form(s) | Condition |
|------|---------|-----------|
| Age bracket determines basic exemption | All | `below_60`: ₹2.5L, `60_to_80`: ₹3L, `above_80`: ₹5L |
| New regime disables 80C/80D/80E etc. | All | Show warning; set to 0 |
| 80TTA vs 80TTB mutual exclusion | All | < 60: show 80TTA only; ≥ 60: show 80TTB only |
| Self-occupied: disable rent fields | ITR-1/2/4 | property_type = 'S' → rent = 0 |
| Home loan interest cap | ITR-1/2/4 | Self-occupied: max ₹2,00,000 |
| GTI > ₹50L blocks ITR-1/4 | ITR-1, ITR-4 | Redirect to ITR-2/3 |
| LTCG 112A > ₹1.25L blocks ITR-1/4 | ITR-1, ITR-4 | Redirect to ITR-2/3 |
| 44AD turnover > ₹2 Cr needs 95% digital | ITR-4 | Show validation |
| 44ADA receipts > ₹50L needs 95% digital | ITR-4 | Show validation |
| 44AE max 10 vehicles | ITR-4 | Show validation |
| Cash donations > ₹2,000 not allowed u/s 80G | All | Show warning |
| Govt employee → entertainment allowance enabled | ITR-1 | Only if govt |

---

## 9. Validation Mapping (Pydantic → CBDT)

### Pydantic Validators (app/schemas/)

| Constraint | Where | Error Message |
|------------|-------|---------------|
| `Decimal(ge=0)` | 50+ fields | "ensure this value is greater than or equal to 0" |
| `Decimal(le=...)` | 44AD turnover, 44ADA receipts | "value exceeds statutory limit" |
| `pattern=r"^[A-Z]{5}[0-9]{4}[A-Z]$"` | PAN | "string does not match regex" |
| `pattern=r"^[0-9]{12}$"` | Aadhaar | "string does not match regex" |
| `min_length=1, max_length=75` | Name fields | "ensure this value has at least 1 characters" |
| Enum validation | AgeBracket, TaxRegime, PropertyType, etc. | "value is not a valid enumeration member" |
| `model_validator` | 44AD/44ADA caps | Custom ValueError |
| `@validator` | Mutual exclusion (80TTA/80TTB) | Custom |

### CBDT Schema Validators (from PDF validation rules)

These are enforced by the ITD portal, NOT by Taxify's Pydantic layer. The jsonschema validation in `validate_schemas.py` catches mismatches BEFORE submission. Key CBDT rules:

| Rule | Form(s) | What it enforces |
|------|---------|-----------------|
| additionalProperties: false | All | No extra fields anywhere |
| integer type (not paise) | All | Whole rupees only |
| max/min on integer fields | All | Statutory caps (80C: 150000, etc.) |
| enum constraints | All | State codes, country codes, section codes |
| pattern on strings | All | PAN, Aadhaar, TAN, IFSC, BSR, dates |
| required arrays with minItems:1 | All | TDSonSalary, TCS, TaxPayment, SplCodeRateTax |
| Date patterns | All | `YYYY-MM-DD`, specific fiscal year patterns |
| Status = "I"/"H"/"F" | ITR-4 only | Filed only by Individuals/HUFs/Firms |
| Form10IEA cascade | ITR-4 only | 13 interrelated fields for regime election |
| TaxExmpIntIncDtls | ITR-4 only | Not ExemptIncAgriOthUs10 |

---

## 10. Quick Reference: Every Enum, Pattern, and Constraint

### Enums

| Enum | Values | Used By |
|------|--------|---------|
| `AgeBracket` | `below_60`, `60_to_80`, `above_80` | All |
| `TaxRegime` | `old`, `new` | All |
| `PropertyType` | `S`, `L`, `D` | ITR-1, ITR-2, ITR-4 |
| `PresumptiveScheme` | `none`, `44AD`, `44ADA`, `44AE` | ITR-4 |
| `CGAssetType` | `land_building`, `listed_equity_112a`, `listed_equity_111a`, `unlisted_shares`, `debt_mutual_fund`, `bonds_debentures`, `jewellery`, `other` | ITR-2 |
| `ResidentialStatus` | `RES`, `NRI`, `NOR` | ITR-2 |
| `ReturnFileSection` | `11`-`20` | ITR-2 |

### Regex Patterns

| Pattern | Field | Example |
|---------|-------|---------|
| `[A-Z]{5}[0-9]{4}[A-Z]` | PAN | `ABCDE1234F` |
| `[0-9]{12}` | Aadhaar | `123456789012` |
| `[1-9][0-9]{9}` | Mobile | `9876543210` |
| `[A-Z]{4}[0-9]{5}[A-Z]` | TAN | `DELA00001A` |
| `IN[0-9A-Z]{10}` | ISIN | `INE002A01018` |
| `[0-9]{15}` | Receipt No. | `123456789012345` |
| `DIPP[0-9]{3,5}` | DPIIT Reg No. | `DIPP00001` |
| `2026-07-31` | ITR-1 due date | exact literal |
| `2026-08-31` | ITR-4 due date | exact literal |
| `[0-9]{4}-[0-9]{2}` | Assessment Year Tax Relief | `2025-26` |
| `2021-22` / `2022-23` … `2026-27` | ESOP AssessmentYear | exact literals per type |

### Monetary Caps

| Cap | Amount | Section |
|-----|--------|---------|
| Standard Deduction (Old) | ₹50,000 | 16(ia) |
| Standard Deduction (New) | ₹75,000 | 16(ia) / 115BAC |
| Entertainment Allowance | ₹5,000 | 16(ii) |
| Professional Tax | ₹2,500 | 16(iii) |
| Home Loan Interest (SOP) | ₹2,00,000 | 24(b) |
| 80C / 80CCC / 80CCD(1) combined | ₹1,50,000 | 80CCE |
| 80CCD(1B) NPS additional | ₹50,000 | 80CCD(1B) |
| 80D Self/Family (non-senior) | ₹25,000 | 80D |
| 80D Self/Family (senior) | ₹50,000 | 80D |
| 80D Parents (non-senior) | ₹25,000 | 80D |
| 80D Parents (senior) | ₹50,000 | 80D |
| 80TTA (savings interest) | ₹10,000 | 80TTA |
| 80TTB (senior deposit interest) | ₹50,000 | 80TTB |
| 80G cash limit | ₹2,000 per donee | 80G(5D) |
| LTCG 112A exemption | ₹1,25,000 | 112A |
| ITR-1/4 total income limit | ₹50,00,000 | CBDT rules |
| 44AD turnover limit | ₹2 Cr (₹3 Cr with 95% digital) | 44AD |
| 44ADA gross receipts limit | ₹50L (₹75L with 95% digital) | 44ADA |
| 44AE vehicle limit | 10 vehicles | 44AE |
| Rebate u/s 87A (old regime, TI ≤ 5L) | ₹12,500 | 87A |
| Rebate u/s 87A (new regime, TI ≤ 7L) | ₹25,000 | 87A |

### State Codes (CBDT Standard — subset)

| Code | State |
|------|-------|
| `07` | Delhi |
| `27` | Maharashtra |
| `29` | Karnataka |
| `33` | Tamil Nadu |
| `09` | Uttar Pradesh |
| `24` | Gujarat |
| `36` | Telangana |
| `35` | Andhra Pradesh |
| `19` | West Bengal |

### Employer Category Codes

| Code | Meaning |
|------|---------|
| `GOV` / `CGOV` | Central Government |
| `SGOV` | State Government |
| `PSU` | Public Sector Undertaking |
| `PE` | Pensioner |
| `OTH` | Others (Private sector) |

### SI Section Codes (ScheduleSI)

| Code | Meaning | Rate |
|------|---------|------|
| `1` | 111A STCG (listed equity, STT paid) | 15%/20% |
| `1A` | 112A LTCG (listed equity) | 12.5% |
| `21ciii` | VDA u/s 115BBH | 30% |
| `2A` | Lottery/Gambling u/s 115BB | 30% |
| `5BBE` | Unexplained income u/s 115BBE | 60% |
| `DTAASTCG` | STCG taxed at DTAA rate | varies |
| `DTAALTCG` | LTCG taxed at DTAA rate | varies |
