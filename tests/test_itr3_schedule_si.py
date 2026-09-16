"""Focused Schedule SI serialization tests."""

from __future__ import annotations

from decimal import Decimal

from jsonschema import Draft4Validator

from app.engine.calculators.itr3 import ITR3Result, compute
from app.engine.itd.itr3 import _partb_ti, _schedule_si
from app.engine.schedules.special_rates import SpecialRateEntry, SpecialRatesResult
from app.engine.itd.itr3_schema import get_itr3_schema_validator
from app.schemas.itr3 import ITR3Input
from app.schemas.itr2 import ScheduleSIEntry


def test_partb_ti_os_special_rate_excludes_capital_gain_and_vda_si_rows() -> None:
    """Part B-TI 5b is Schedule OS 2, not the whole Schedule SI total."""
    result = ITR3Result()
    result.schedules["si"] = SpecialRatesResult(entries=[
        SpecialRateEntry(section="111A", taxable_income=Decimal("20000")),
        SpecialRateEntry(section="112A", taxable_income=Decimal("30000")),
        SpecialRateEntry(section="115BBH", taxable_income=Decimal("40000")),
        SpecialRateEntry(section="115BB", taxable_income=Decimal("5000")),
        SpecialRateEntry(section="115BBE", taxable_income=Decimal("6000")),
    ])
    payload = _partb_ti(result)
    assert payload["IncFromOS"]["IncChargblSplRate"] == 11000
    assert payload["IncChargeTaxSplRate111A112"] == 101000



    """No special-rate source means no Schedule SI object."""
    typed = ITR3Input(age_bracket="below_60", tax_regime="new")
    assert _schedule_si(compute(typed), typed) is None


def test_schedule_si_maps_official_115bb_code_and_validates() -> None:
    """A typed 115BB entry becomes official code 5BB and validates."""
    typed = ITR3Input(
        age_bracket="below_60",
        tax_regime="new",
        si_entries=[ScheduleSIEntry(
            section="115BB",
            description="Listed equity",
            gross_income=Decimal("100000"),
            deductions=Decimal("0"),
            tax_rate_pct=Decimal("12.5"),
        )],
    )
    payload = _schedule_si(compute(typed), typed)
    assert payload is not None
    assert payload["SplCodeRateTax"][0]["SecCode"] == "5BB"
    full = get_itr3_schema_validator().schema
    schema = dict(full["definitions"]["ScheduleSI"])
    schema["definitions"] = full["definitions"]
    assert not list(Draft4Validator(schema).iter_errors(payload))
