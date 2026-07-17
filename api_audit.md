# OpenTax API Audit Report

## 1. Folder Structure Inside api/

`
api/
├── .env
├── .gitignore
├── README.md
├── requirements.txt
├── app_settings.py
├── main.py
├── main_router.py
├── filing/
│   ├── filing_controller.py
│   ├── tax_calculation/
│   │   ├── tax_calculation_service.py
│   │   ├── interest_234_service.py
│   │   └── models/
│   │       ├── tax_calculation_response.py
│   │       ├── tax_regime_breakdown.py
│   │       └── tax_interest_breakdown.py
│   ├── itr/
│   │   ├── itr_building_orchestrator.py
│   │   ├── itrtojson.py
│   │   ├── auto_mapper.py
│   │   ├── validations/
│   │   │   └── tax_validation_service.py
│   │   └── itr1/
│   │       ├── itr1_building_service.py
│   │       ├── itr1_income_builder_service.py
│   │       ├── itr1_deduction_builder_service.py
│   │       ├── filing_to_itr1_mapper.py
│   │       ├── itr1-schema.json
│   │       └── models/
│   │           ├── itr1_model.py
│   │           └── filing_build_itr1_return_model.py
│   ├── utils/
│   │   ├── tax_filing_helpers.py
│   │   ├── master_data_service.py
│   │   └── encryption.py
│   └── models/
│       ├── filing_model.py
│       ├── salary_model.py
│       ├── house_property_model.py
│       ├── professional_income_model.py
│       └── [60+ other model files]
`

## 2. Files Containing Tax Computation Logic

| File | Purpose |
|------|---------|
| filing/tax_calculation/tax_calculation_service.py | Core tax computation - slab calculation (old/new regime), rebate (87A), surcharge, cess, BEL adjustment for LTCG, special rate taxes |
| filing/tax_calculation/interest_234_service.py | Interest calculation u/s 234A/B/C/F |
| filing/utils/tax_filing_helpers.py | Helper functions (age calculation) |

## 3. Files Containing ITR JSON Building Logic

| File | Purpose |
|------|---------|
| filing/itr/itr_building_orchestrator.py | Orchestrator - determines ITR1 vs ITR2 |
| filing/itr/itr1/itr1_building_service.py | Main ITR1 builder |
| filing/itr/itr1/itr1_income_builder_service.py | Builds income sections |
| filing/itr/itr1/itr1_deduction_builder_service.py | Builds Chapter VIA deduction schedules |
| filing/itr/itr1/models/itr1_model.py | Pydantic models for ITR1 JSON |

## 4. Boilerplate Files

| File | Purpose |
|------|---------|
| main.py | FastAPI app initialization |
| main_router.py | Route registration |
| app_settings.py | Pydantic settings |
| requirements.txt | Python dependencies |
| .env | Environment variables |

## 5. ITR-1 Specific Code

### Salary Income
- File: filing/itr/itr1/itr1_income_builder_service.py
- Functions: build_salary_income, _build_section_171_salary, _build_section_172_perquisites, _build_section_173_profits_in_lieu, _build_allowances_exempt_us10, _build_deductions_us16

### House Property
- File: filing/itr/itr1/itr1_income_builder_service.py
- Functions: build_house_property_income, _build_type_of_house_property, _build_gross_rent_received, _build_annual_value, _build_standard_deduction_30_percent, _build_interest_payable_on_borrowed_capital, _build_total_income_of_house_property

### Chapter VI-A Deductions
- File: filing/itr/itr1/itr1_deduction_builder_service.py
- Functions: _apply_section_80c, _apply_section_80d, _apply_section_80e, _apply_section_80g, _apply_section_80gg, _apply_section_80tta, _apply_section_80u, _apply_section_80dd, _apply_section_80ddb, _apply_section_80ee, _apply_section_80eeb, _apply_section_80gga, _apply_section_80ggc

## 6. ITR-4 Specific Code (Presumptive Income 44AD/44ADA/44AE)

**Finding: NO ITR-4 code exists in the repository.**

- No computation logic for Section 44AD (traders)
- No computation logic for Section 44ADA (professionals)
- No computation logic for Section 44AE (goods carriage)
- No ITR-4 form builder
- Note in itr_building_orchestrator.py: ITR2 not yet supported

## 7. Old-vs-New Tax Regime Comparison

**Yes, implemented.**

- File: filing/tax_calculation/tax_calculation_service.py
- Functions: calc_slab_breakdown_old_regime, calc_slab_breakdown_new_regime_2025_26, calc_slab_breakdown_new_regime, _compute_rebate_amount, _compute_surcharge_amount

## 8. Reusability Rating

| Component | Rating | Notes |
|-----------|--------|-------|
| Slab Calculation | REUSE WITH MODIFICATION | Well-structured, age-based old regime, new regime for AY 2025-26/2026-27 |
| Deductions | REUSE WITH MODIFICATION | Comprehensive Chapter VIA, new regime logic correct |
| ITR-1 Flow | REUSE WITH MODIFICATION | Complete ITR-1 building, dual-regime support |
| ITR-4 Flow | REWRITE FROM SCRATCH | Does not exist |
| JSON Builder | REUSE WITH MODIFICATION | Complete ITR-1 JSON, Pydantic models |

---
## Summary

OpenTax provides solid ITR-1 foundation with full tax computation and deductions. ITR-4 is completely absent - must be built from scratch.
