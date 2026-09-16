"""Tests for the official ITR-3 schedule field manifest."""

from __future__ import annotations

from app.engine.itd.itr3_manifest import get_itr3_schedule_manifest


def test_itr3_manifest_contains_all_official_schedules() -> None:
    """The manifest includes the official ITR-3 definition set."""
    schedules = {schedule.name: schedule for schedule in get_itr3_schedule_manifest()}
    assert len(schedules) == 69
    for name in ("PARTA_OI", "PARTA_QD", "ManufacturingAccount", "TradingAccount", "ScheduleFA", "ScheduleESOP"):
        assert name in schedules
        assert schedules[name].fields


def test_itr3_manifest_marks_required_schedules_and_nested_fields() -> None:
    """Required schedules and nested required fields are preserved."""
    schedules = {schedule.name: schedule for schedule in get_itr3_schedule_manifest()}
    assert schedules["PARTA_PL"].required is True
    paths = {field.path for field in schedules["PARTA_PL"].fields}
    assert "PARTA_PL.CreditsToPL.GrossProfitTrnsfFrmTrdAcc" in paths
    assert schedules["ITR3ScheduleBP"].required is True
    assert any(field.path.endswith("BusinessIncOthThanSpec.ProfBfrTaxPL") for field in schedules["ITR3ScheduleBP"].fields)


def test_itr3_manifest_preserves_enums_and_array_metadata() -> None:
    """Enum values and array schedule metadata are available for typed work."""
    schedules = {schedule.name: schedule for schedule in get_itr3_schedule_manifest()}
    qd_fields = {field.path: field for field in schedules["PARTA_QD"].fields}
    assert qd_fields["PARTA_QD.TradingConcern.QuantitDet"].array is True
    unit_fields = [field for field in schedules["PARTA_QD"].fields if field.field_name == "UnitOfMeasure"]
    assert "101" in unit_fields[0].enum_values
