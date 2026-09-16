"""Focused tests for exact PARTA_OI and PARTA_QD mappings."""

from __future__ import annotations

from decimal import Decimal

import pytest
from jsonschema import Draft4Validator

from app.engine.itd.itr3 import _parta_oi, _parta_qd
from app.engine.itd.itr3_schema import get_itr3_schema_validator
from app.schemas.itr3 import ITR3Input, ITR3PartAQD, ITR3PartAOI, ITR3TradingQDRow


def test_parta_qd_maps_official_nested_quantitdet() -> None:
    """Trading quantitative details use the exact CBDT nesting."""
    typed = ITR3Input(
        age_bracket="below_60",
        tax_regime="new",
        parta_qd=ITR3PartAQD(TradingConcern=[ITR3TradingQDRow(
            ItemName="Rice",
            UnitOfMeasure="101",
            OpeningStock=Decimal("1"),
            PurchaseQty=Decimal("2"),
            SaleQty=Decimal("3"),
            ClgStock=Decimal("0"),
            AnyShortExces=Decimal("0"),
        )]),
    )
    assert _parta_qd(typed) == {"TradingConcern": {"QuantitDet": [{
        "ItemName": "Rice", "UnitOfMeasure": "101", "OpeningStock": 1,
        "PurchaseQty": 2, "SaleQty": 3, "ClgStock": 0, "AnyShortExces": 0,
    }]}}


def test_parta_oi_uses_typed_decimal_boundary_conversion() -> None:
    """PARTA_OI monetary Decimals become official integer rupees."""
    typed = ITR3Input(
        age_bracket="below_60",
        tax_regime="new",
        parta_oi=ITR3PartAOI(ProfDeviatDueAcctMeth=Decimal("12.00")),
    )
    assert _parta_oi(typed)["ProfDeviatDueAcctMeth"] == 12


def _parta_qd_validator() -> Draft4Validator:
    """Build a self-contained validator for the referenced QD definition."""
    full_schema = get_itr3_schema_validator().schema
    schema = dict(full_schema["definitions"]["PARTA_QD"])
    schema["definitions"] = full_schema["definitions"]
    return Draft4Validator(schema)

def test_parta_qd_mapping_is_schema_valid() -> None:
    """A fully populated QD branch validates against the official definition."""
    typed = ITR3Input(
        age_bracket="below_60",
        tax_regime="new",
        parta_qd=ITR3PartAQD(TradingConcern=[ITR3TradingQDRow(
            ItemName="Rice", UnitOfMeasure="101", OpeningStock=1,
            PurchaseQty=2, SaleQty=3, ClgStock=0, AnyShortExces=0,
        )]),
    )
    document = _parta_qd(typed)
    errors = list(_parta_qd_validator().iter_errors(document))
    assert errors == []



def test_parta_qd_rejects_unknown_unit_code() -> None:
    """Typed QD input rejects values outside the official enum once validated by schema."""
    typed = ITR3Input(
        age_bracket="below_60", tax_regime="new",
        parta_qd=ITR3PartAQD(TradingConcern=[ITR3TradingQDRow(
            ItemName="Rice", UnitOfMeasure="000", OpeningStock=1,
            PurchaseQty=2, SaleQty=3, ClgStock=0, AnyShortExces=0,
        )]),
    )
    assert list(_parta_qd_validator().iter_errors(_parta_qd(typed)))
