"""Production-path tests for ITR-2 JSON validation and routing."""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from decimal import Decimal
from typing import Any

import pytest
from fastapi import HTTPException

from app.engine.calculators.itr2 import compute
from app.engine.itd.itr2 import build_itr2_json
from app.engine.itd.itr2_schema import (
    ITR2SchemaValidationError,
    get_itr2_schema_validator,
    validate_itr2_json,
)
from app.routers.itr import itr2_compute, itr2_compute_json
from app.schemas.itr1 import AgeBracket, BankAccount, FilingAddress, SalaryIncome, TaxRegime, TDS1Entry, TDS2Entry
from app.schemas.itr2 import EmployerFilingDetail, ITR2FilingProfile, ITR2Input


def _profile() -> ITR2FilingProfile:
    """Return complete filing identity for production-path tests."""
    return ITR2FilingProfile(
        pan="AAAPA1234A",
        first_name="Asha",
        surname_or_org_name="Sharma",
        date_of_birth_or_formation=date(1990, 1, 1),
        father_name="Arun Sharma",
        verification_place="Delhi",
        primary_address=FilingAddress(
            residence_no="12",
            locality_or_area="Model Town",
            city_or_town_or_district="Delhi",
            state_code="07",
            pin_code="110009",
            mobile_no="9876543210",
            email="asha@example.com",
        ),
    )


def _input(**overrides: Any) -> ITR2Input:
    """Return a minimal filing-grade ITR-2 input."""
    values: dict[str, Any] = {
        "age_bracket": AgeBracket.BELOW_60,
        "tax_regime": TaxRegime.OLD,
        "filing_profile": _profile(),
    }
    values.update(overrides)
    return ITR2Input(**values)


def test_runtime_schema_validator_is_cached_and_thread_safe() -> None:
    """Concurrent validation reuses one immutable official validator."""
    input_data = _input()
    document = build_itr2_json(compute(input_data), input_data)

    def validate_once(_: int) -> int:
        validate_itr2_json(document)
        return id(get_itr2_schema_validator())

    with ThreadPoolExecutor(max_workers=8) as executor:
        validator_ids = list(executor.map(validate_once, range(32)))
    assert len(set(validator_ids)) == 1


def test_runtime_validator_reports_stable_document_path() -> None:
    """Schema failures expose actionable document paths."""
    input_data = _input()
    document = build_itr2_json(compute(input_data), input_data)
    del document["ITR"]["ITR2"]["PartB-TI"]
    with pytest.raises(ITR2SchemaValidationError) as caught:
        validate_itr2_json(document)
    assert caught.value.errors
    assert caught.value.errors[0]["path"] == "ITR.ITR2"


def test_salary_builder_rejects_missing_employer_address_evidence() -> None:
    """Schedule S never invents employer address particulars."""
    input_data = _input(
        salary_income=SalaryIncome(gross_salary=Decimal("800000")),
        tds1_entries=[
            TDS1Entry(
                employer_tan="DELA00001A",
                employer_name="Acme Limited",
                income_chargeable=Decimal("800000"),
                tds_deducted=Decimal("50000"),
            )
        ],
    )
    with pytest.raises(ValueError, match="employer_filing_details"):
        build_itr2_json(compute(input_data), input_data)


def test_tds2_uses_official_credit_shape_and_claimed_amount() -> None:
    """Schedule TDS2 emits official credit fields and claimed credit only."""
    input_data = _input(
        tds2_entries=[
            TDS2Entry(
                deductor_tan="DELA00001A",
                deductor_name="Bank Limited",
                tds_section="94A",
                gross_amount=Decimal("10000"),
                tds_deducted=Decimal("1000"),
                tds_claimed_this_year=Decimal("700"),
                financial_year="2024-25",
            )
        ],
        bank_accounts=[
            BankAccount(
                account_number="1234567890",
                ifsc_code="SBIN0000001",
                bank_name="State Bank of India",
                account_type="savings",
                is_primary=True,
            )
        ],
    )
    document = build_itr2_json(compute(input_data), input_data)
    validate_itr2_json(document)
    row = document["ITR"]["ITR2"]["ScheduleTDS2"]["TDSOthThanSalaryDtls"][0]
    assert row["TANOfDeductor"] == "DELA00001A"
    assert row["DeductedYr"] == 2024
    assert row["TaxDeductCreditDtls"]["TaxClaimedOwnHands"] == 700
    assert row["AmtCarriedFwd"] == 300


def test_compute_json_route_returns_schema_valid_document() -> None:
    """The production route passes canonical input to builder and validates output."""
    response = itr2_compute_json(_input(), current_user=None)  # type: ignore[arg-type]
    assert response.status_code == 200
    validate_itr2_json(json.loads(response.body))


def test_compute_json_route_maps_builder_incompleteness_to_http_400() -> None:
    """Missing filing identity is a client error, never an HTTP 500."""
    input_data = ITR2Input(age_bracket=AgeBracket.BELOW_60, tax_regime=TaxRegime.OLD)
    with pytest.raises(HTTPException) as caught:
        itr2_compute_json(input_data, current_user=None)  # type: ignore[arg-type]
    assert caught.value.status_code == 400
    assert caught.value.detail["message"] == "ITD JSON input is incomplete"


def test_compute_route_includes_post_calculation_validation() -> None:
    """The compute response exposes the post-calculation validation report."""
    response = itr2_compute(_input(), current_user=None)  # type: ignore[arg-type]
    assert response.validation is not None
    assert response.validation["can_upload"] is True
