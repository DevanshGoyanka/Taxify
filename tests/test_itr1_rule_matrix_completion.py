"""Regression tests for the completed ITR-1 339-rule validation matrix."""

from __future__ import annotations

import csv
from decimal import Decimal
from pathlib import Path

from app.engine.validators.itr1.input_rules import validate_itr1_input
from app.schemas.itr1 import (
    AgeBracket,
    Chapter6ADeductions,
    HousePropertyIncome,
    ITR1Input,
    OtherSourcesIncome,
    PropertyType,
    SalaryIncome,
    TDS2Entry,
    TaxRegime,
)


def _base_input(**updates: object) -> ITR1Input:
    """Build the minimal valid ITR-1 input used by focused rule tests."""
    data: dict[str, object] = {
        "age_bracket": AgeBracket.BELOW_60,
        "tax_regime": TaxRegime.OLD,
        "salary_income": SalaryIncome(),
        "house_property_income": HousePropertyIncome(
            property_type=PropertyType.SELF_OCCUPIED,
        ),
        "other_sources_income": OtherSourcesIncome(),
        "deductions_chapter6a": Chapter6ADeductions(),
    }
    data.update(updates)
    return ITR1Input(**data)


def _failed_rule_ids(inp: ITR1Input) -> set[str]:
    """Return all failed validation-rule IDs for an input."""
    return {
        result.rule_id
        for result in validate_itr1_input(inp)
        if not result.passed
    }


def test_duplicate_exempt_income_dropdown_emits_exact_official_rule() -> None:
    """Duplicate Section 10(11) selections must fail official rule R033."""
    inp = _base_input(
        exempt_income_dropdowns=[
            "Sec 10(11) Statutory Provident Fund",
            "10(11) statutory provident fund received",
        ],
    )

    assert "ITR1-R033" in _failed_rule_ids(inp)


def test_duplicate_other_source_dropdown_emits_exact_official_rule() -> None:
    """Duplicate family-pension selections must fail official rule R056."""
    inp = _base_input(
        other_sources_dropdowns=["Family pension", "family-pension income"],
    )

    assert "ITR1-R056" in _failed_rule_ids(inp)


def test_claimed_tds_without_financial_year_fails_r099() -> None:
    """Claiming TDS2 credit without a deduction year must fail R099."""
    inp = _base_input(
        tds2_entries=[
            TDS2Entry(
                deductor_tan="ABCD12345E",
                tds_section="194A",
                gross_amount=Decimal("1000"),
                tds_deducted=Decimal("100"),
                tds_claimed_this_year=Decimal("100"),
            )
        ],
    )

    assert "ITR1-R099" in _failed_rule_ids(inp)


def test_claimed_tds_with_financial_year_passes_r099() -> None:
    """A valid TDS2 financial year must satisfy R099."""
    inp = _base_input(
        tds2_entries=[
            TDS2Entry(
                deductor_tan="ABCD12345E",
                tds_section="194A",
                gross_amount=Decimal("1000"),
                tds_deducted=Decimal("100"),
                tds_claimed_this_year=Decimal("100"),
                financial_year="2025-26",
            )
        ],
    )

    assert "ITR1-R099" not in _failed_rule_ids(inp)


def test_generated_rule_matrix_has_339_proven_rows_and_no_gaps() -> None:
    """The committed matrix must prove all 339 Category-A rules."""
    matrix_path = (
        Path(__file__).resolve().parents[1]
        / "Docs"
        / "audit"
        / "itr1_validation_rule_matrix.csv"
    )
    with matrix_path.open(encoding="utf-8", newline="") as file:
        rows = list(csv.DictReader(file))

    assert len(rows) == 339
    assert {row["rule_id"] for row in rows} == {
        f"ITR1-R{number:03d}" for number in range(1, 340)
    }
    assert not {
        row["rule_id"]
        for row in rows
        if row["status"] in {"MISSING_OR_UNPROVEN", "PARTIAL"}
    }
