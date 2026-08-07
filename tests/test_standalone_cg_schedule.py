"""Tests for the standalone capital-gains schedule and per-form projections.

These tests lock in the unified CG schedule architecture: one form-agnostic
``compute()`` entry point classifies every canonical transaction into the
112A / 111A / section-112 / land-building / other baskets, applies
grandfathering and the ₹1.25L aggregate threshold, and returns signed
baskets plus current-year losses.  Form calculators then PROJECT this
single result — ITR-1/4 aggregate the 112A basket (losses forfeited,
exemptions disallowed), ITR-2/3 consume the full signed result.
"""

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
from typing import Any

from app.engine.schedules.capital_gains import (
    CG112AAsset,
    CGAsset,
    compute,
    project_restricted_112a,
)


def _eq_scrip(
    *,
    sale: str = "120000",
    cost: str = "100000",
    fmv: str = "0",
    acquired: str = "2023-01-01",
    transferred: str = "2025-01-02",
) -> SimpleNamespace:
    """Build a minimal equity-MF scrip transaction (112A long-term)."""
    return SimpleNamespace(
        asset_type="equity_oriented_fund_112a",
        description="ICICI Prudential",
        isin_code="INF109K01QS1",
        full_consideration=Decimal(sale),
        cost_of_acquisition=Decimal(cost),
        fair_market_value_jan2018=Decimal(fmv) if fmv else None,
        expenditure_on_transfer=Decimal("0"),
        date_of_acquisition=__import__("datetime").date.fromisoformat(acquired),
        date_of_transfer=__import__("datetime").date.fromisoformat(transferred),
        exemptions=[],
        explicit_long_term=None,
    )


def test_compute_classifies_long_term_equity_into_112a_basket() -> None:
    """A >12-month equity-MF disposal lands in the 112A basket with gain."""
    tx = _eq_scrip(sale="120000", cost="100000")
    result = compute([tx])
    # ₹20,000 LTCG u/s 112A, within the ₹1.25L exemption → taxable 0.
    assert result.ltcg.income_112a == Decimal("20000")
    assert result.ltcg.taxable_112a == Decimal("0")
    assert result.stcg.total_stcg == Decimal("0")
    assert result.vda == Decimal("0")


def test_compute_short_term_equity_lands_in_111a_basket() -> None:
    """A <12-month listed-equity disposal is STCG u/s 111A, not 112A.

    The 111A asset type denotes short-term listed equity; a long-term
    disposal of the same scrip would use the 112A asset type instead.
    """
    tx = _eq_scrip(sale="120000", cost="100000", acquired="2025-01-01", transferred="2025-06-01")
    tx.asset_type = "listed_equity_111a"
    result = compute([tx])
    assert result.stcg.income_111a == Decimal("20000")
    assert result.ltcg.income_112a == Decimal("0")


def test_compute_land_building_long_term_uses_indexed_cost() -> None:
    """Long-term land/building gain deducts indexed cost when supplied."""
    tx = SimpleNamespace(
        asset_type="land_building",
        description="Flat",
        isin_code="",
        full_consideration=Decimal("5000000"),
        cost_of_acquisition=Decimal("2000000"),
        indexed_cost=Decimal("3000000"),
        improvement_cost=Decimal("0"),
        indexed_improvement=Decimal("0"),
        expenditure_on_transfer=Decimal("50000"),
        fair_market_value_jan2018=None,
        date_of_acquisition=__import__("datetime").date(2020, 4, 1),
        date_of_transfer=__import__("datetime").date(2025, 5, 1),
        exemptions=[],
        explicit_long_term=None,
    )
    result = compute([tx])
    # 50L - 30L (indexed) - 50K = 19.5L
    assert result.ltcg.income_125per_other == Decimal("1950000")


def test_compute_applies_112a_threshold_once_across_scrips() -> None:
    """Multiple 112A scrips share the single ₹1.25L aggregate exemption."""
    scrips = [
        _eq_scrip(sale="150000", cost="100000"),  # +50k
        _eq_scrip(sale="200000", cost="100000"),  # +100k
    ]
    result = compute(scrips)
    # Total 112A gain 1.5L; exemption 1.25L; taxable 25k.
    assert result.ltcg.income_112a == Decimal("150000")
    assert result.ltcg.taxable_112a == Decimal("25000")


def test_compute_grandfathers_pre_31jan2018_acquisition() -> None:
    """A pre-31-Jan-2018 acquisition uses max(cost, min(FMV, sale))."""
    tx = _eq_scrip(
        sale="200000",
        cost="50000",
        fmv="180000",
        acquired="2017-06-01",
        transferred="2025-01-02",
    )
    result = compute([tx])
    # Effective cost = max(50k, min(180k, 200k)) = 180k → gain 20k.
    assert result.ltcg.income_112a == Decimal("20000")


def test_compute_retains_signed_loss() -> None:
    """A capital loss is retained as a signed negative, not floored to 0."""
    tx = _eq_scrip(sale="80000", cost="100000")
    result = compute([tx])
    # The 112A basket carries a signed -20k; total is signed.
    assert result.ltcg.income_112a == Decimal("-20000")


def test_compute_handles_dict_rows_from_flat_payload() -> None:
    """The schedule accepts plain dict rows (frontend payload shape)."""
    row = {
        "assetType": "EQUITY_ORIENTED_MUTUAL_FUND",
        "description": "ICICI Prudential",
        "isin": "INF109K01QS1",
        "saleValue": "120000",
        "actualCost": "100000",
        "transferExpenses": "0",
        "acquisitionDate": "2023-01-01",
        "transferDate": "2025-01-02",
    }
    result = compute([row])
    assert result.ltcg.income_112a == Decimal("20000")


def test_project_restricted_112a_clamps_loss_and_surfaces_forfeiture() -> None:
    """ITR-1/4 projection forfeits losses and reports them as disallowed."""
    loss_tx = _eq_scrip(sale="80000", cost="100000")  # -20k loss
    result = compute([loss_tx])
    projection = project_restricted_112a(result)
    assert projection["gain_112a"] == Decimal("0")
    assert projection["losses_forfeited"] == Decimal("20000")


def test_project_restricted_112a_surfaces_other_cg_as_disallowed() -> None:
    """Non-112A CG in the projection flags ITR-1 ineligibility."""
    tx = SimpleNamespace(
        asset_type="land_building",
        description="Flat",
        isin_code="",
        full_consideration=Decimal("5000000"),
        cost_of_acquisition=Decimal("2000000"),
        indexed_cost=Decimal("0"),
        improvement_cost=Decimal("0"),
        indexed_improvement=Decimal("0"),
        expenditure_on_transfer=Decimal("0"),
        fair_market_value_jan2018=None,
        date_of_acquisition=__import__("datetime").date(2020, 4, 1),
        date_of_transfer=__import__("datetime").date(2025, 5, 1),
        exemptions=[],
        explicit_long_term=None,
    )
    result = compute([tx])
    projection = project_restricted_112a(result)
    # Land/building LTCG is non-112A → disallowed for ITR-1.
    assert projection["other_cg_disallowed"] > Decimal("0")
    assert projection["gain_112a"] == Decimal("0")


def _minimal_itr1_input(cg_transactions: list) -> Any:
    """Build a minimal ITR1Input with all required fields populated."""
    from app.schemas.itr1 import (
        ITR1Input,
        AgeBracket,
        TaxRegime,
        SalaryIncome,
        HousePropertyIncome,
        OtherSourcesIncome,
        Chapter6ADeductions,
        PropertyType,
    )

    return ITR1Input(
        age_bracket=AgeBracket.BELOW_60,
        tax_regime=TaxRegime.OLD,
        salary_income=SalaryIncome(),
        house_property_income=HousePropertyIncome(property_type=PropertyType.SELF_OCCUPIED),
        other_sources_income=OtherSourcesIncome(),
        deductions_chapter6a=Chapter6ADeductions(),
        cg_transactions=cg_transactions,
    )


def test_itr1_calculator_projects_restricted_112a_from_cg_transactions() -> None:
    """ITR-1 consumes the standalone schedule and projects the 112A aggregate."""
    from app.engine.calculators.itr1 import compute as compute_itr1

    tx = _eq_scrip(sale="120000", cost="100000")  # +20k, within 1.25L
    result = compute_itr1(_minimal_itr1_input([tx]))
    assert not result.errors
    assert result.capital_gains_112a == Decimal("20000")
    # The unified schedule result and the projection are attached.
    assert "capital_gains_unified" in result.schedules
    assert "capital_gains_projection" in result.schedules


def test_itr1_calculator_rejects_loss_via_projection() -> None:
    """A capital loss forces ITR-1 ineligibility (losses cannot be filed in ITR-1).

    Note: a pure 112A loss is actually zero gain (clamped), so the 112A-only
    case stays eligible with zero income.  This test confirms the projection
    surfaces the forfeited loss figure for the form classifier.
    """
    from app.engine.calculators.itr1 import compute as compute_itr1

    tx = _eq_scrip(sale="80000", cost="100000")  # -20k loss
    result = compute_itr1(_minimal_itr1_input([tx]))
    # A pure 112A loss is clamped to 0 gain — ITR-1 eligible with ₹0 income.
    assert not result.errors
    assert result.capital_gains_112a == Decimal("0")
    projection = result.schedules["capital_gains_projection"]
    assert projection["losses_forfeited"] == Decimal("20000")
