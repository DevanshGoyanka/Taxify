"""
Pydantic response schemas for ITR computation and saved-return endpoints.

All monetary values are returned as strings (serialised from Decimal) so
that JSON precision is preserved without floating-point drift.
"""

from datetime import datetime
from decimal import Decimal
from typing import Any

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
    net_tax_liability: Decimal
    total_tds: Decimal
    total_tcs: Decimal
    total_taxes_paid: Decimal
    balance_payable: Decimal
    refund_due: Decimal
    hp_loss_disallowed: Decimal


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


# ---------------------------------------------------------------------------
# ITR-4 compute response
# ---------------------------------------------------------------------------

class ITR4ComputeResponse(_DecimalModel):
    """Full breakdown returned by POST /itr4/compute."""
    pgbp_income: Decimal
    salary_income: Decimal
    house_property_income: Decimal
    other_sources_income: Decimal
    capital_gains_112a: Decimal
    gross_total_income: Decimal
    deductions_chapter6a: Decimal
    taxable_income: Decimal
    slab_tax: Decimal
    special_rate_tax: Decimal
    rebate_87a: Decimal
    tax_after_rebate: Decimal
    surcharge: Decimal
    health_education_cess: Decimal
    total_tax_payable: Decimal
    hp_loss_disallowed: Decimal


# ---------------------------------------------------------------------------
# Saved-return endpoints
# ---------------------------------------------------------------------------

class SaveRequest(BaseModel):
    """Body for POST /returns/save."""
    itr_type: str          # "ITR1", "ITR2", "ITR3", or "ITR4"
    input_data: Any        # arbitrary JSON -- the original input dict
    computed_result: Any   # arbitrary JSON -- the engine output dict


class SaveResponse(BaseModel):
    """Response from POST /returns/save -- just the new row id."""
    id: int


class ReturnSummary(BaseModel):
    """One item in the GET /returns list -- lightweight, no full data."""
    id: int
    itr_type: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ReturnDetail(BaseModel):
    """Full record returned by GET /returns/{id}."""
    id: int
    itr_type: str
    input_data: Any        # parsed back from JSON text
    computed_result: Any   # parsed back from JSON text
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
