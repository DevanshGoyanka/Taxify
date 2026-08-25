"""Blocking-gate regressions for stateless ITR-1 routes."""

from decimal import Decimal
from unittest.mock import patch

import pytest
from fastapi import HTTPException

from app.engine.calculators.itr1 import ITR1Result
from app.engine.validators.base import Severity, ValidationReport, ValidationResult
from app.routers.itr import itr1_compute, itr1_compute_json
from app.schemas.itr1 import (
    AgeBracket,
    Chapter6ADeductions,
    HousePropertyIncome,
    ITR1Input,
    OtherSourcesIncome,
    PropertyType,
    SalaryIncome,
    Schedule80CEntry,
    TDS2Entry,
    TCSEntry,
    TaxRegime,
)


def _valid_input() -> ITR1Input:
    """Build an input that satisfies the current blocking input rules."""
    return ITR1Input(
        age_bracket=AgeBracket.BELOW_60,
        tax_regime=TaxRegime.NEW,
        salary_income=SalaryIncome(gross_salary=Decimal("600000")),
        house_property_income=HousePropertyIncome(property_type=PropertyType.SELF_OCCUPIED),
        other_sources_income=OtherSourcesIncome(),
        deductions_chapter6a=Chapter6ADeductions(),
        nature_of_employment="Private",
    )


def _blocking_report() -> ValidationReport:
    """Build a report containing one Category-A failure."""
    return ValidationReport(
        form_type="ITR1",
        results=[
            ValidationResult(
                rule_id="ITR1-TEST",
                severity=Severity.A,
                passed=False,
                message="Blocking calculation mismatch",
            )
        ],
    )


def test_compute_rejects_calculator_errors() -> None:
    """Calculator eligibility errors must not become HTTP-200 partial results."""
    with patch("app.routers.itr.itr1_input_val", return_value=ValidationReport("ITR1")), patch(
        "app.routers.itr.compute_itr1",
        return_value=ITR1Result(errors=["Ineligible for ITR-1: File ITR-2."]),
    ):
        with pytest.raises(HTTPException) as exc_info:
            itr1_compute(_valid_input(), current_user=None)

    assert exc_info.value.status_code == 400
    assert "File ITR-2" in str(exc_info.value.detail)


def test_compute_rejects_blocking_calculation_validation() -> None:
    """Post-calculation Category-A failures must block the compute response."""
    with patch("app.routers.itr.itr1_input_val", return_value=ValidationReport("ITR1")), patch(
        "app.routers.itr.compute_itr1", return_value=ITR1Result()
    ), patch("app.routers.itr.itr1_calc_val", return_value=_blocking_report()):
        with pytest.raises(HTTPException) as exc_info:
            itr1_compute(_valid_input(), current_user=None)

    assert exc_info.value.status_code == 400
    assert "calculation validation failed" in str(exc_info.value.detail).lower()


def test_compute_json_rejects_calculator_errors_before_builder() -> None:
    """A rejected calculation must never invoke official JSON generation."""
    with patch("app.routers.itr.itr1_input_val", return_value=ValidationReport("ITR1")), patch(
        "app.routers.itr.compute_itr1",
        return_value=ITR1Result(errors=["Ineligible for ITR-1: File ITR-2."]),
    ), patch("app.engine.itd.itr1.build_itr1_json") as builder:
        with pytest.raises(HTTPException) as exc_info:
            itr1_compute_json(_valid_input(), current_user=None)

    assert exc_info.value.status_code == 400
    builder.assert_not_called()


def test_compute_json_rejects_blocking_calculation_validation() -> None:
    """Non-uploadable calculations must not produce downloadable JSON."""
    with patch("app.routers.itr.itr1_input_val", return_value=ValidationReport("ITR1")), patch(
        "app.routers.itr.compute_itr1", return_value=ITR1Result()
    ), patch("app.routers.itr.itr1_calc_val", return_value=_blocking_report()), patch(
        "app.engine.itd.itr1.build_itr1_json"
    ) as builder:
        with pytest.raises(HTTPException) as exc_info:
            itr1_compute_json(_valid_input(), current_user=None)

    assert exc_info.value.status_code == 400
    builder.assert_not_called()


def test_old_regime_rebate_uses_taxable_income_after_deductions() -> None:
    """A valid old-regime rebate must not be blocked because GTI exceeds Rs 5 lakh."""
    body = ITR1Input(
        age_bracket=AgeBracket.BELOW_60,
        tax_regime=TaxRegime.OLD,
        salary_income=SalaryIncome(gross_salary=Decimal("650000")),
        house_property_income=HousePropertyIncome(property_type=PropertyType.SELF_OCCUPIED),
        other_sources_income=OtherSourcesIncome(),
        deductions_chapter6a=Chapter6ADeductions(amount_80c=Decimal("150000")),
        schedule_80c_entries=[
            Schedule80CEntry(
                amount=Decimal("150000"),
                payment_type="PPF",
                identifier_number="PPF-REBATE-1",
            ),
        ],
        nature_of_employment="Private",
    )

    response = itr1_compute(body, current_user=None)

    assert response.taxable_income == Decimal("450000")
    assert response.rebate_87a > 0


def test_optional_claimed_credit_columns_default_to_zero() -> None:
    """Omitted claimed-credit columns must not crash blocking validation."""
    body = _valid_input().model_copy(update={
        "tds2_entries": [
            TDS2Entry(
                deductor_tan="ABCD12345E",
                tds_section="194A",
                gross_amount=Decimal("1000"),
                tds_deducted=Decimal("100"),
            )
        ],
        "tcs_entries": [
            TCSEntry(
                collector_tan="WXYZ12345F",
                tcs_section="206C",
                gross_amount=Decimal("1000"),
                tcs_collected=Decimal("10"),
            )
        ],
    })

    from app.engine.validators.itr1.input_rules import validate_itr1_input

    results = validate_itr1_input(body)
    assert isinstance(results, list)


def test_compute_json_passes_validated_input_to_builder() -> None:
    """Official JSON generation must receive the validated source input."""
    body = _valid_input()
    with patch("app.routers.itr.itr1_input_val", return_value=ValidationReport("ITR1")), patch(
        "app.routers.itr.compute_itr1", return_value=ITR1Result()
    ), patch("app.routers.itr.itr1_calc_val", return_value=ValidationReport("ITR1")), patch(
        "app.engine.itd.itr1.build_itr1_json", return_value={"ITR": {"ITR1": {}}}
    ) as builder:
        itr1_compute_json(body, current_user=None)

    builder.assert_called_once()
    assert builder.call_args.args[1] is body


def test_compute_json_reports_missing_filing_profile_as_client_error() -> None:
    """Missing official identity data must return a controlled HTTP 400."""
    body = _valid_input()
    with patch("app.routers.itr.itr1_input_val", return_value=ValidationReport("ITR1")), patch(
        "app.routers.itr.compute_itr1", return_value=ITR1Result()
    ), patch("app.routers.itr.itr1_calc_val", return_value=ValidationReport("ITR1")):
        with pytest.raises(HTTPException) as exc_info:
            itr1_compute_json(body, current_user=None)

    assert exc_info.value.status_code == 400
    assert "filing_profile" in str(exc_info.value.detail)
