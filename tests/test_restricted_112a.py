"""Focused tests for canonical restricted Section 112A computation."""

from decimal import Decimal

from app.engine.schedules.restricted_112a import compute_restricted_112a
from app.schemas.itr1 import CapitalGainsIncome


def _valid(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "assetType": "EQUITY",
        "purchaseDate": "2023-01-01",
        "saleDate": "2025-01-02",
        "purchaseCost": "100000",
        "saleCost": "120000",
        "transferExpenses": "1000",
        "sttPaidOnAcquisition": True,
        "sttPaidOnTransfer": True,
        "recognizedExchange": True,
    }
    row.update(overrides)
    return row


def test_imported_incomplete_rows_remain_evidence_without_blocking_summary() -> None:
    """Legacy imported rows are evidence, not malformed taxable disposals."""
    result = compute_restricted_112a([{
        "assetType": "MUTUAL_FUND",
        "purchaseDate": "",
        "saleDate": "",
        "purchaseCost": 4000,
        "saleCost": 0,
        "importStatus": "INCOMPLETE",
        "importCategory": "purchase of securities and units of mutual funds",
    }])
    assert result.is_valid
    assert result.status == "EVIDENCE_ONLY"
    assert result.evidence_count == 1
    assert result.transactions == ()
    assert result.issues == ()
    assert result.gross_gain == Decimal("0")
    # Evidence-only without completed transactions does not block ITR-1/ITR-4.
    # The taxpayer simply has no Section 112A income to report.
    assert result.eligibility == {"ITR-1": True, "ITR-4": True}


def test_new_evidence_contract_is_excluded_from_computation() -> None:
    """Explicit evidence records remain outside restricted computation."""
    result = compute_restricted_112a([{
        "recordKind": "EVIDENCE",
        "evidenceSide": "SALE",
        "assetType": "MUTUAL_FUND",
        "saleValue": 68394,
    }])
    assert result.status == "EVIDENCE_ONLY"
    assert result.evidence_count == 1
    assert result.gross_gain == Decimal("0")


def test_empty_dates_on_completed_transaction_have_actionable_issues() -> None:
    """Completed draft rows with empty dates produce field-level missing issues."""
    result = compute_restricted_112a([_valid(purchaseDate="", saleDate="")])
    codes = {issue.code.value for issue in result.issues}
    assert "INVALID_TRANSACTION" not in codes
    assert codes >= {"MISSING_ACQUISITION_DATE", "MISSING_TRANSFER_DATE"}


def test_complete_valid_transaction() -> None:
    """A fully evidenced eligible transaction computes signed gross gain."""
    result = compute_restricted_112a([_valid()])
    assert result.is_valid
    assert result.gross_gain == Decimal("19000")
    assert result.full_value_of_consideration == Decimal("120000")
    assert result.cost_of_acquisition == Decimal("101000")
    assert result.transfer_expenses == Decimal("1000")
    assert (
        result.full_value_of_consideration - result.cost_of_acquisition
        == result.gross_gain
    )


def test_canonical_frontend_date_fields_compute_gain() -> None:
    """Canonical camelCase editor dates reach the Section 112A engine."""
    row = _valid()
    row["acquisitionDate"] = row.pop("purchaseDate")
    row["transferDate"] = row.pop("saleDate")

    result = compute_restricted_112a([row])

    assert result.is_valid
    assert result.status == "VALID"
    assert result.gross_gain == Decimal("19000")
    assert result.to_dict()["gross112AGain"] == 19000.0


def test_mutual_fund_disposal_computes_without_manual_stt_flags() -> None:
    """Eligible fund-unit disposals compute from purchase and sale facts."""
    row = _valid(assetType="EQUITY_ORIENTED_MUTUAL_FUND")
    row.pop("sttPaidOnAcquisition")
    row.pop("sttPaidOnTransfer")
    row.pop("recognizedExchange")

    result = compute_restricted_112a([row])

    assert result.is_valid
    assert result.status == "VALID"
    assert result.gross_gain == Decimal("19000")


def test_business_trust_disposal_computes_without_equity_only_flags() -> None:
    """Business-trust units do not require listed-equity confirmations."""
    row = _valid(assetType="BUSINESS_TRUST_UNIT")
    row.pop("sttPaidOnAcquisition")
    row.pop("sttPaidOnTransfer")
    row.pop("recognizedExchange")

    result = compute_restricted_112a([row])

    assert result.is_valid
    assert result.gross_gain == Decimal("19000")


def test_completed_imported_sale_evidence_is_promoted_to_transaction() -> None:
    """A completed AIS sale row contributes gain despite its evidence marker."""
    row = _valid(
        recordKind="EVIDENCE",
        evidenceSide="SALE",
        assetType="EQUITY_ORIENTED_MUTUAL_FUND",
    )

    result = compute_restricted_112a([row])

    assert result.is_valid
    assert result.status == "VALID"
    assert result.evidence_count == 0
    assert result.gross_gain == Decimal("19000")


def test_incomplete_evidence_is_blocked_with_structured_issues() -> None:
    """Incomplete imported evidence is blocked rather than omitted."""
    raw = _valid()
    raw.pop("purchaseDate")
    raw.pop("sttPaidOnTransfer")
    result = compute_restricted_112a([raw])
    assert not result.is_valid
    assert {issue.code.value for issue in result.issues} >= {
        "MISSING_ACQUISITION_DATE", "MISSING_STT_TRANSFER"
    }


def test_unsupported_and_short_term_transactions_are_blocked() -> None:
    """Non-112A assets and short-term holdings cannot enter ITR-1/4."""
    unsupported = compute_restricted_112a([_valid(assetType="PROPERTY")])
    short_term = compute_restricted_112a([_valid(purchaseDate="2024-06-01")])
    assert "UNSUPPORTED_ASSET" in {issue.code.value for issue in unsupported.issues}
    assert "NOT_LONG_TERM" in {issue.code.value for issue in short_term.issues}


def test_ais_long_term_fund_disposal_computes_without_acquisition_date() -> None:
    """Explicit AIS long-term classification replaces an unavailable date."""
    result = compute_restricted_112a([{
        "recordKind": "TRANSACTION",
        "evidenceSide": "SALE",
        "assetType": "EQUITY_ORIENTED_MUTUAL_FUND",
        "purchaseDate": "",
        "saleDate": "2026-03-30",
        "purchaseCost": "10000",
        "saleCost": "12000",
        "transferExpenses": "0",
        "aisHoldingPeriod": "Long term",
        "sttAmount": "0.12",
        "sttPaidOnTransfer": True,
    }])

    assert result.is_valid
    assert result.status == "VALID"
    assert result.gross_gain == Decimal("2000")
    assert result.transactions[0].holding_period_days == 0
    assert result.transactions[0].holding_period_months == 13


def test_signed_loss_is_not_clamped_or_silently_omitted() -> None:
    """A transaction loss remains in signed totals and blocks restricted forms."""
    result = compute_restricted_112a([_valid(saleCost="90000")])
    assert "SECTION_112A_LOSS" in {issue.code.value for issue in result.issues}
    assert result.gross_gain == Decimal("-11000")
    assert result.full_value_of_consideration == Decimal("90000")
    assert result.cost_of_acquisition == Decimal("101000")
    assert len(result.transactions) == 1


def test_aggregate_over_limit_is_blocked() -> None:
    """Gross Section 112A gain above Rs 1.25 lakh disqualifies both forms."""
    result = compute_restricted_112a([_valid(saleCost="230000", transferExpenses="0")])
    assert result.gross_gain == Decimal("130000")
    assert "AGGREGATE_LIMIT_EXCEEDED" in {issue.code.value for issue in result.issues}
    assert result.eligibility == {"ITR-1": False, "ITR-4": False}


def test_capital_gains_income_projects_canonical_aggregate() -> None:
    """Typed ITR-1/4 shared input derives official aggregate schedule values."""
    capital_gains = CapitalGainsIncome(transactions=[_valid()])
    assert capital_gains.ltcg_112a == Decimal("19000")
    assert capital_gains.full_value_of_consideration == Decimal("120000")
    assert capital_gains.cost_of_acquisition == Decimal("101000")


def test_pre_2018_acquisition_requires_fmv_evidence() -> None:
    """An old acquisition must not silently bypass grandfathering."""
    result = compute_restricted_112a([_valid(purchaseDate="2017-01-01")])
    assert "MISSING_FMV_31_JAN_2018" in {
        issue.code.value for issue in result.issues
    }


def test_fund_unit_does_not_require_equity_only_market_evidence() -> None:
    """Fund units require transfer STT, not equity acquisition/exchange facts."""
    row = _valid(assetType="EQUITY_ORIENTED_MUTUAL_FUND")
    row.pop("sttPaidOnAcquisition")
    row.pop("recognizedExchange")
    result = compute_restricted_112a([row])
    assert result.is_valid


def test_exact_calendar_year_across_leap_day_is_not_long_term() -> None:
    """Exactly twelve calendar months remains short-term despite 366 days."""
    result = compute_restricted_112a([_valid(
        purchaseDate="2024-01-01",
        saleDate="2025-01-01",
    )])
    assert "NOT_LONG_TERM" in {issue.code.value for issue in result.issues}


def test_pre_2018_grandfathering_uses_statutory_deemed_cost() -> None:
    """Pre-2018 assets use max(actual cost, min(FMV, sale value))."""
    result = compute_restricted_112a([_valid(
        purchaseDate="2017-01-01", purchaseCost="50000", saleCost="120000",
        transferExpenses="0", fmvAsOn31Jan2018="100000",
    )])
    assert result.is_valid
    assert result.cost_of_acquisition == Decimal("100000")
    assert result.gross_gain == Decimal("20000")
    assert result.transactions[0].grandfathering_applied
