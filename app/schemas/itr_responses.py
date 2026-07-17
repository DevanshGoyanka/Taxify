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
# ITR-4 compute response
# ---------------------------------------------------------------------------

class ITR4ComputeResponse(_DecimalModel):
    """Full breakdown returned by POST /itr4/compute."""
    pgbp_income: Decimal
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
# Saved-return endpoints
# ---------------------------------------------------------------------------

class SaveRequest(BaseModel):
    """Body for POST /returns/save."""
    itr_type: str          # "ITR1" or "ITR4"
    input_data: Any        # arbitrary JSON — the original input dict
    computed_result: Any   # arbitrary JSON — the engine output dict


class SaveResponse(BaseModel):
    """Response from POST /returns/save — just the new row id."""
    id: int


class ReturnSummary(BaseModel):
    """One item in the GET /returns list — lightweight, no full data."""
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
