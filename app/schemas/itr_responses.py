"""
Pydantic response schemas for ITR computation endpoints.

All monetary values are returned as strings (serialised from Decimal) so
that JSON precision is preserved without floating-point drift.
"""

from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict


# ---------------------------------------------------------------------------
# Shared monetary type alias
# ---------------------------------------------------------------------------

class _DecimalModel(BaseModel):
    """Base that serialises Decimal fields to strings in JSON output."""
    model_config = ConfigDict(arbitrary_types_allowed=True)


# ---------------------------------------------------------------------------
# ITR-1 compute response
# ---------------------------------------------------------------------------

class ITR1ComputeResponse(_DecimalModel):
    """Full breakdown returned by POST /itr1/compute."""
    salary_income: Decimal
    house_property_income: Decimal
    other_sources_income: Decimal
    gross_total_income: Decimal
    deductions_chapter6a: Decimal
    taxable_income: Decimal
    slab_tax: Decimal
    rebate_87a: Decimal
    tax_after_rebate: Decimal
    surcharge: Decimal
    health_education_cess: Decimal
    total_tax_payable: Decimal
    hp_loss_disallowed: Decimal
    validation: Optional[dict] = None


# ---------------------------------------------------------------------------
# ITR-2 compute response
# ---------------------------------------------------------------------------

class ITR2ComputeResponse(_DecimalModel):
    """Full breakdown returned by POST /itr2/compute."""
    salary_income: Decimal
    house_property_income: Decimal
    capital_gains_income: Decimal
    other_sources_income: Decimal
    vda_income: Decimal
    clubbing_income: Decimal
    gti_before_loss_setoff: Decimal
    cyla_total_set_off: Decimal
    bfla_total_set_off: Decimal
    gti_after_loss_setoff: Decimal
    gross_total_income: Decimal
    net_agricultural_income: Decimal
    partial_integration_tax: Decimal
    deductions_total: Decimal
    taxable_income: Decimal
    aggregate_income: Decimal
    slab_tax: Decimal
    special_rate_tax: Decimal
    amt_tax: Decimal
    total_tax_before_relief: Decimal
    tax_before_rebate: Decimal
    rebate_87a: Decimal
    tax_after_rebate: Decimal
    surcharge: Decimal
    health_education_cess: Decimal
    gross_tax_liability: Decimal
    relief_89: Decimal
    relief_90_91: Decimal
    interest_234a: Decimal
    interest_234b: Decimal
    interest_234c: Decimal
    late_fee_234f: Decimal
    total_interest: Decimal
    net_tax_liability: Decimal
    total_tds: Decimal
    total_tcs: Decimal
    total_advance_tax: Decimal
    total_self_assessment_tax: Decimal
    total_taxes_paid: Decimal
    balance_payable: Decimal
    refund_due: Decimal
    hp_loss_disallowed: Decimal
    cyla_remaining: Decimal
    bfla_remaining: Decimal
    errors: list[str]
    warnings: list[str]
    validation: Optional[dict] = None


# ---------------------------------------------------------------------------
# ITR-3 compute response
# ---------------------------------------------------------------------------

class ITR3ComputeResponse(_DecimalModel):
    """Full breakdown returned by POST /itr3/compute."""
    business_income: Decimal
    salary_income: Decimal
    house_property_income: Decimal
    capital_gains_income: Decimal
    other_sources_income: Decimal
    vda_income: Decimal
    clubbing_income: Decimal
    partner_firm_income: Decimal
    gti_before_loss_setoff: Decimal
    cyla_total_set_off: Decimal
    bfla_total_set_off: Decimal
    gti_after_loss_setoff: Decimal
    gross_total_income: Decimal
    net_agricultural_income: Decimal
    partial_integration_tax: Decimal
    deductions_partb_chapter6a: Decimal
    deductions_partc_chapter6a: Decimal
    deductions_10aa: Decimal
    deductions_80ia: Decimal
    deductions_80ib: Decimal
    deductions_80ic: Decimal
    deductions_total: Decimal
    taxable_income: Decimal
    aggregate_income: Decimal
    slab_tax: Decimal
    special_rate_tax: Decimal
    amt_tax: Decimal
    total_tax_before_relief: Decimal
    tax_before_rebate: Decimal
    rebate_87a: Decimal
    tax_after_rebate: Decimal
    surcharge: Decimal
    health_education_cess: Decimal
    gross_tax_liability: Decimal
    relief_89: Decimal
    relief_90_91: Decimal
    interest_234a: Decimal
    late_fee_234f: Decimal
    total_interest: Decimal
    net_tax_liability: Decimal
    total_tds: Decimal
    total_tcs: Decimal
    total_advance_tax: Decimal
    total_self_assessment_tax: Decimal
    total_taxes_paid: Decimal
    balance_payable: Decimal
    refund_due: Decimal
    hp_loss_disallowed: Decimal
    cyla_remaining: Decimal
    bfla_remaining: Decimal
    unabsorbed_dep_setoff: Decimal
    validation: Optional[dict] = None


# ITR4ComputeResponse (POST /itr4/compute) and the saved-return CRUD models
# (SaveRequest/SaveResponse/ReturnSummary/ReturnDetail, for POST /returns/save,
# GET /returns, GET /returns/{id}) were removed 2026-09-05 (full-codebase
# dead-code audit): their only caller, app/routers/itr.py's now-removed
# itr4_compute/save_return/list_returns/get_return, had zero frontend
# callers and zero test coverage. See app/routers/itr.py's module docstring
# for the full evidence trail.
