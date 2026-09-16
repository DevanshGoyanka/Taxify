"""Official-schema coverage for every supported Schedule FA category."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

import pytest
from jsonschema import Draft4Validator

from app.engine.itd.itr2 import _schedule_fa
from app.engine.itd.itr3_schema import get_itr3_schema_validator
from app.schemas.itr2 import ForeignAssetEntry, ForeignAssetType, ITR2Input


_CATEGORY_TO_SCHEMA_KEY: dict[ForeignAssetType, str] = {
    ForeignAssetType.BANK_ACCOUNT: "DetailsForiegnBank",
    ForeignAssetType.CUSTODIAL_ACCOUNT: "DtlsForeignCustodialAcc",
    ForeignAssetType.EQUITY_DEBT_INTEREST: "DtlsForeignEquityDebtInterest",
    ForeignAssetType.CASH_VALUE_INSURANCE: "DtlsForeignCashValueInsurance",
    ForeignAssetType.FINANCIAL_INTEREST: "DetailsFinancialInterest",
    ForeignAssetType.IMMOVABLE_PROPERTY: "DetailsImmovableProperty",
    ForeignAssetType.SIGNING_AUTHORITY: "DetailsOfAccntsHvngSigningAuth",
    ForeignAssetType.TRUST: "DetailsOfTrustOutIndiaTrustee",
    ForeignAssetType.OTHER_FOREIGN_INCOME: "DetailsOfOthSourcesIncOutsideIndia",
    ForeignAssetType.OTHER_ASSET: "DetailsOthAssets",
}


def _entry(asset_type: ForeignAssetType, **overrides: Any) -> ForeignAssetEntry:
    """Create a minimal valid typed entry for one Schedule FA category."""
    values: dict[str, Any] = {
        "asset_type": asset_type,
        "country_code": "14",
        "institution_or_entity_name": "Example Foreign Entity",
        "address": "1 Example Street",
        "zip_code": "10001",
        "account_or_asset_identifier": "ACC-001",
        "ownership_status": "DIRECT",
        "opening_or_acquisition_date": date(2025, 4, 1),
        "peak_value": Decimal("1000"),
        "closing_value": Decimal("900"),
        "gross_income": Decimal("100"),
        "income_offered": Decimal("100"),
        "income_head": "OS",
        "nature_of_asset": "Equity interest",
        "nature_of_income": "Interest income",
        "income_tax_schedule_item_no": "1",
    }
    values.update(overrides)
    return ForeignAssetEntry(**values)


def _validate_schedule_fa(payload: dict[str, Any]) -> None:
    """Validate a Schedule FA subtree against the official ITR-3 definitions."""
    full_schema = get_itr3_schema_validator().schema
    schedule_schema = dict(full_schema["definitions"]["ScheduleFA"])
    schedule_schema["definitions"] = full_schema["definitions"]
    errors = list(Draft4Validator(schedule_schema).iter_errors(payload))
    assert not errors, "\n".join(error.message for error in errors)


@pytest.mark.parametrize("asset_type", list(ForeignAssetType))
def test_every_foreign_asset_category_validates_in_its_official_row(
    asset_type: ForeignAssetType,
) -> None:
    """Each declared category maps to its own schema row and validates."""
    category_values: dict[ForeignAssetType, dict[str, Any]] = {
        ForeignAssetType.BANK_ACCOUNT: {"ownership_status": "OWNER"},
        ForeignAssetType.CUSTODIAL_ACCOUNT: {
            "ownership_status": "OWNER",
            "nature_of_amount": "I",
        },
        ForeignAssetType.EQUITY_DEBT_INTEREST: {
            "initial_value_of_investment": Decimal("800"),
        },
        ForeignAssetType.CASH_VALUE_INSURANCE: {
            "cash_value_or_surrender_value": Decimal("700"),
        },
        ForeignAssetType.FINANCIAL_INTEREST: {},
        ForeignAssetType.IMMOVABLE_PROPERTY: {},
        ForeignAssetType.SIGNING_AUTHORITY: {
            "income_accrued_tax_flag": "Y",
            "name_mentioned_in_account": "Example Owner",
        },
        ForeignAssetType.TRUST: {
            "name_of_trust": "Example Trust",
            "address_of_trust": "Trust Address",
            "name_of_other_trustees": "Other Trustee",
            "address_of_other_trustees": "Other Trustee Address",
            "name_of_settlor": "Example Settlor",
            "address_of_settlor": "Settlor Address",
            "name_of_beneficiaries": "Example Beneficiary",
            "address_of_beneficiaries": "Beneficiary Address",
            "income_derived_tax_flag": "Y",
        },
        ForeignAssetType.OTHER_FOREIGN_INCOME: {
            "name_of_person": "Example Person",
            "address_of_person": "Person Address",
            "income_derived_tax_flag": "Y",
        },
        ForeignAssetType.OTHER_ASSET: {},
    }
    document = _schedule_fa(
        ITR2Input(
            age_bracket="below_60",
            tax_regime="new",
            foreign_assets=[_entry(asset_type, **category_values[asset_type])],
        )
    )
    assert document is not None
    _validate_schedule_fa(document)
    expected_key = _CATEGORY_TO_SCHEMA_KEY[asset_type]
    assert len(document[expected_key]) == 1
    assert all(
        not rows for key, rows in document.items() if key != expected_key
    )
    if asset_type != ForeignAssetType.OTHER_ASSET:
        assert not document["DetailsOthAssets"]


@pytest.mark.parametrize(
    ("asset_type", "field", "message"),
    [
        (ForeignAssetType.CUSTODIAL_ACCOUNT, "nature_of_amount", "NatureOfAmount"),
        (
            ForeignAssetType.EQUITY_DEBT_INTEREST,
            "initial_value_of_investment",
            "initial_value_of_investment",
        ),
        (
            ForeignAssetType.CASH_VALUE_INSURANCE,
            "cash_value_or_surrender_value",
            "cash_value_or_surrender_value",
        ),
        (ForeignAssetType.SIGNING_AUTHORITY, "income_accrued_tax_flag", "income_accrued_tax_flag"),
        (ForeignAssetType.TRUST, "name_of_trust", "trust"),
        (ForeignAssetType.OTHER_FOREIGN_INCOME, "name_of_person", "incomplete"),
        (ForeignAssetType.OTHER_ASSET, "nature_of_asset", "nature_of_asset"),
    ],
)
def test_schedule_fa_fails_closed_when_category_field_is_missing(
    asset_type: ForeignAssetType,
    field: str,
    message: str,
) -> None:
    """Incomplete category-specific data is rejected, never reclassified."""
    category_values: dict[ForeignAssetType, dict[str, Any]] = {
        ForeignAssetType.CUSTODIAL_ACCOUNT: {"nature_of_amount": "I"},
        ForeignAssetType.EQUITY_DEBT_INTEREST: {
            "initial_value_of_investment": Decimal("800"),
        },
        ForeignAssetType.CASH_VALUE_INSURANCE: {
            "cash_value_or_surrender_value": Decimal("700"),
        },
        ForeignAssetType.SIGNING_AUTHORITY: {
            "income_accrued_tax_flag": "Y",
            "name_mentioned_in_account": "Example Owner",
        },
        ForeignAssetType.TRUST: {
            "name_of_trust": "Example Trust",
            "address_of_trust": "Trust Address",
            "name_of_other_trustees": "Other Trustee",
            "address_of_other_trustees": "Other Trustee Address",
            "name_of_settlor": "Example Settlor",
            "address_of_settlor": "Settlor Address",
            "name_of_beneficiaries": "Example Beneficiary",
            "address_of_beneficiaries": "Beneficiary Address",
            "income_derived_tax_flag": "Y",
        },
        ForeignAssetType.OTHER_FOREIGN_INCOME: {
            "name_of_person": "Example Person",
            "address_of_person": "Person Address",
            "income_derived_tax_flag": "Y",
        },
        ForeignAssetType.OTHER_ASSET: {},
    }
    values = dict(category_values[asset_type])
    values[field] = None
    entry = _entry(asset_type, **values)
    with pytest.raises(ValueError, match=message):
        _schedule_fa(
            ITR2Input(
                age_bracket="below_60",
                tax_regime="new",
                foreign_assets=[entry],
            )
        )
