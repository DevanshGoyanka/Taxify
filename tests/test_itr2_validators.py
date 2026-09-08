"""Focused tests for production ITR-2 validators."""

from datetime import date
from decimal import Decimal

from app.engine.calculators.itr2 import ITR2Result
from app.engine.validators.itr2 import run_calc_validation, run_input_validation
from app.schemas.itr1 import AgeBracket, TaxRegime
from app.schemas.itr1 import TCSEntry, TDS2Entry
from app.schemas.itr2 import (
    AMTInput,
    BFLossItem,
    CG112AScrip,
    CGAssetType,
    CGTransaction,
    FSICountryEntry,
    ITR2Input,
    TR1Entry,
    VDATransaction,
)


def _input(**updates: object) -> ITR2Input:
    """Create a minimal valid ITR-2 input with optional overrides."""
    values: dict[str, object] = {
        "age_bracket": AgeBracket.BELOW_60,
        "tax_regime": TaxRegime.OLD,
        "filing_date": date(2026, 7, 1),
        "due_date": date(2026, 7, 31),
    }
    base = ITR2Input(**values)
    return base.model_copy(update=updates)


def _failed_ids(inp: ITR2Input) -> set[str]:
    """Return failed input-validation rule identifiers."""
    return {item.rule_id for item in run_input_validation(inp).results if not item.passed}


def test_input_report_uses_standard_contract() -> None:
    """Validator entry points return the shared report shape."""
    report = run_input_validation(_input())
    assert report.form_type == "ITR2"
    assert report.can_upload
    assert report.to_dict()["can_upload"] is True


def test_capital_gain_dates_stt_and_fmv_are_required() -> None:
    """Listed equity validates dates, STT, consideration, and grandfathering FMV."""
    tx = CGTransaction.model_construct(
        asset_type=CGAssetType.LISTED_EQUITY_112A,
        date_of_acquisition=date(2018, 1, 1),
        date_of_transfer=date(2017, 1, 1),
        full_consideration=Decimal("0"),
        is_stt_paid_on_acquisition=False,
        is_stt_paid_on_transfer=False,
    )
    ids = _failed_ids(_input(cg_transactions=[tx]))
    assert {"ITR2-IN-CG-002", "ITR2-IN-CG-003", "ITR2-IN-CG-005", "ITR2-IN-CG-006"} <= ids


def test_112a_facts_and_arithmetic_are_reconciled() -> None:
    """Schedule 112A validates identity, quantity, FMV, deductions, and balance."""
    scrip = CG112AScrip.model_construct(
        isin_code="",
        share_unit_name="",
        date_of_acquisition=date(2017, 1, 1),
        date_of_transfer=date(2025, 1, 1),
        is_before_31jan2018=True,
        num_shares_units=Decimal("10"),
        sale_price_per_share=Decimal("20"),
        total_sale_value=Decimal("250"),
        cost_acq_without_index=Decimal("100"),
        expenditure_on_transfer=Decimal("5"),
        total_deductions=Decimal("80"),
        balance=Decimal("999"),
    )
    ids = _failed_ids(_input(cg_112a_scrips=[scrip]))
    assert {
        "ITR2-IN-112A-001", "ITR2-IN-112A-004", "ITR2-IN-112A-005",
        "ITR2-IN-112A-006", "ITR2-IN-112A-007",
    } <= ids


def test_vda_disallows_inconsistent_loss_claim() -> None:
    """VDA facts enforce nonnegative statutory income."""
    tx = VDATransaction.model_construct(
        date_of_acquisition=date(2025, 2, 1),
        date_of_transfer=date(2025, 3, 1),
        acquisition_cost=Decimal("100"),
        consideration_received=Decimal("50"),
        income_from_vda=Decimal("20"),
    )
    ids = _failed_ids(_input(vda_transactions=[tx]))
    assert "ITR2-IN-VDA-003" in ids


def test_brought_forward_loss_category_year_expiry_and_amount() -> None:
    """Brought-forward losses enforce categories, AY syntax, expiry, and amounts."""
    losses = [
        BFLossItem.model_construct(assessment_year="2016-17", head="HP", original_loss=Decimal("20"), brought_forward=Decimal("20")),
        BFLossItem.model_construct(assessment_year="2024-24", head="UNKNOWN", original_loss=Decimal("1"), brought_forward=Decimal("1")),
    ]
    ids = _failed_ids(_input(bf_losses=losses))
    assert {"ITR2-IN-BFL-001", "ITR2-IN-BFL-003"} <= ids


def test_fsi_tr1_amt_tds_and_tcs_reconciliation() -> None:
    """Foreign relief, AMT, and source-tax claims cannot exceed represented facts."""
    inp = _input(
        fsi_entries=[FSICountryEntry.model_construct(
            country_code="US", tax_identification_no="TIN123", salary_income=Decimal("100"),
            total_income=Decimal("100"), tax_paid_outside_india=Decimal("20"),
        )],
        tr1_entries=[TR1Entry.model_construct(
            country_code="US", tax_identification_no="TIN123",
            income_included_in_this_return=Decimal("80"),
            tax_paid_outside_india=Decimal("25"), indian_tax_payable=Decimal("10"),
            relief_claimed=Decimal("15"),
        )],
        amt_input=AMTInput.model_construct(
            adjusted_total_income=Decimal("1000"), amt_rate_pct=Decimal("20"),
            amt_tax=Decimal("100"), amt_credit_brought_forward=Decimal("5"),
            amt_credit_utilised=Decimal("6"),
        ),
        tds2_entries=[TDS2Entry.model_construct(
            deductor_tan="ABCD12345E", tds_section="194A", tds_deducted=Decimal("10"),
            tds_claimed_this_year=Decimal("11"),
        )],
        tcs_entries=[TCSEntry.model_construct(
            collector_tan="ABCD12345E", tcs_section="206C", tcs_collected=Decimal("10"),
            tcs_credit_claimed=Decimal("11"),
        )],
    )
    ids = _failed_ids(inp)
    assert {
        "ITR2-IN-TR1-001", "ITR2-IN-TR1-002",
        "ITR2-IN-AMT-001", "ITR2-IN-AMT-002", "ITR2-IN-TDS-001", "ITR2-IN-TCS-001",
    } <= ids


def test_clean_computation_passes_post_validation() -> None:
    """An untouched calculator result satisfies post-computation invariants."""
    inp = _input()
    result = ITR2Result()
    report = run_calc_validation(inp, result)
    assert report.can_upload, [item.to_dict() for item in report.blocking_errors]


def test_tampered_computation_fails_arithmetic_and_nonnegative_checks() -> None:
    """Post-validation detects arithmetic corruption and negative computed values."""
    inp = _input()
    result = ITR2Result()
    result.gross_total_income = Decimal("100")
    result.deductions_total = Decimal("200")
    result.total_taxes_paid = Decimal("-1")
    result.net_tax_liability = Decimal("0")
    ids = {item.rule_id for item in run_calc_validation(inp, result).blocking_errors}
    assert {"ITR2-CALC-003", "ITR2-CALC-006", "ITR2-CALC-021"} <= ids
