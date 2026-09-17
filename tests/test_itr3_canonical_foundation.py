"""Focused regression tests for the canonical ITR-3 foundation."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.engine.draft_to_itr3_input import draft_to_itr3_input
from app.engine.filing_gateway_v2 import (
    FilingGatewayV2Error,
    ITR3PipelineResult,
    compute_canonical,
    compute_canonical_itr3,
    generate_cbdt_json,
)
from app.engine.itd.itr3_schema import ITR3SchemaValidationError, validate_itr3_json
from app.engine.validators.itr3 import run_calc_validation, run_input_validation
from app.schemas.return_draft import AlternateAddress, ITR3NatureOfBusiness, Presumptive44AD, ReturnDraft, create_empty_draft


def _draft_with_business() -> ReturnDraft:
    """Build the smallest explicit ITR-3 compute draft."""
    draft = create_empty_draft("2026-27", "ITR-3", "new")
    draft.personal.pan = "ABCDE1234F"
    draft.personal.firstName = "Asha"
    draft.personal.surnameOrOrgName = "Sharma"
    draft.personal.dateOfBirth = "1985-01-01"
    draft.personal.flatNo = "1"
    draft.personal.localityOrArea = "Central"
    draft.personal.city = "Delhi"
    draft.personal.stateCode = "07"
    draft.personal.countryCode = "91"
    draft.personal.pinCode = "110001"
    draft.personal.mobile = "9876543210"
    draft.personal.email = "asha@example.com"
    draft.verification.place = "Delhi"
    draft.verification.date = "2026-07-31"
    draft.verification.declarationAccepted = True
    draft.businesses = [Presumptive44AD(
        id="business-1",
        natureCode="01001",
        digitalReceipts=Decimal("1000000"),
        declaredIncome=Decimal("60000"),
    )]
    return draft


def test_itr3_mapper_requires_explicit_business_income() -> None:
    """The mapper must not silently turn an empty business profile into zero."""
    draft = create_empty_draft("2026-27", "ITR-3", "new")
    with pytest.raises(ValueError, match="business or professional income"):
        draft_to_itr3_input(draft)


def test_itr3_mapper_preserves_identity_and_business_amount() -> None:
    """Canonical identity and declared business income reach typed input."""
    typed_input, breakdown = draft_to_itr3_input(_draft_with_business())
    assert typed_input.assessee_pan == "ABCDE1234F"
    assert typed_input.assessee_first_name == "Asha"
    assert typed_input.assessee_last_name == "Sharma"
    assert typed_input.business_income is not None
    assert typed_input.business_income.net_profit_before_tax == Decimal("60000")
    assert breakdown["business_income"] == Decimal("60000")


def test_itr3_personal_info_optional_fields_reach_typed_input_and_json() -> None:
    """Schedule 1 (Personal Information, A1-A18): every optional field the
    PDF prints -- building/village name (A6a), road/street (A7a), Aadhaar
    (A16), office phone with STD code and secondary mobile (A17), secondary
    email (A18), and a genuinely distinct secondary address (A5b-A13b) --
    must reach the typed input and the emitted JSON as real, sourced data,
    not silently dropped or fabricated as a copy of the primary address."""
    draft = _draft_with_business()
    draft.personal.residenceName = "Shivam Apartments"
    draft.personal.roadOrStreet = "MG Road"
    draft.personal.aadhaar = "123456789012"
    draft.personal.landlineStdCode = "011"
    draft.personal.landlinePhoneNo = "23456789"
    draft.personal.secondaryMobileCountryCode = "91"
    draft.personal.secondaryMobile = "9123456780"
    draft.personal.secondaryEmail = "asha.alt@example.com"
    draft.personal.secondaryAddressDifferent = True
    draft.personal.alternateAddress = AlternateAddress(
        residenceNo="42", residenceName="Green Villa", roadOrStreet="Park Street",
        localityOrArea="Salt Lake", cityOrTownOrDistrict="Kolkata",
        stateCode="19", countryCode="91", pinCode="700091",
    )

    typed_input, _breakdown = draft_to_itr3_input(draft)
    assert typed_input.residence_name == "Shivam Apartments"
    assert typed_input.road_or_street == "MG Road"
    assert typed_input.assessee_aadhaar == "123456789012"
    assert typed_input.office_phone_std_code == "011"
    assert typed_input.office_phone_no == "23456789"
    assert typed_input.secondary_mobile_no == "9123456780"
    assert typed_input.secondary_email == "asha.alt@example.com"
    assert typed_input.secondary_address_different is True
    assert typed_input.alternate_city == "Kolkata"
    assert typed_input.alternate_pin_code == "700091"

    from app.engine.calculators.itr3 import compute as compute_itr3
    from app.engine.itd.itr3 import build_itr3_json

    result = compute_itr3(typed_input)
    document = build_itr3_json(result, typed_input)
    personal = document["ITR"]["ITR3"]["PartA_GEN1"]["PersonalInfo"]

    # Scoped to Schedule 1 (Personal Information) only -- the full document
    # doesn't schema-validate yet since later schedules in this push (Part
    # A-BS/OI, CYLA/BFLA, Schedule OS, etc.) aren't closed out yet. Validate
    # PersonalInfo against its own official schema sub-definition directly.
    import json
    from jsonschema import Draft4Validator
    schema_path = (
        "Reference Docs by CBDT & ITD/Official JSON Schema/"
        "ITR-3_2026_Main_V1.1 (2).json"
    )
    with open(schema_path, encoding="utf-8") as f:
        full_schema = json.load(f)
    personal_info_schema = dict(full_schema["definitions"]["PersonalInfo"])
    personal_info_schema["definitions"] = full_schema["definitions"]
    errors = sorted(Draft4Validator(personal_info_schema).iter_errors(personal), key=lambda e: e.path)
    assert not errors, [e.message for e in errors]
    address = personal["Address"]
    assert address["ResidenceName"] == "Shivam Apartments"
    assert address["RoadOrStreet"] == "MG Road"
    assert personal["AadhaarCardNo"] == "123456789012"
    assert address["Phone"] == {"STDcode": 11, "PhoneNo": "23456789"}
    assert address["CountryCodeMobileNoSec"] == 91
    assert address["MobileNoSec"] == 9123456780
    assert address["EmailAddressSec"] == "asha.alt@example.com"
    assert personal["SecondaryAdd"] == "Y"
    alt = personal["AlternateAddress"]
    assert alt["ResidenceNo"] == "42"
    assert alt["ResidenceName"] == "Green Villa"
    assert alt["CityOrTownOrDistrict"] == "Kolkata"
    assert alt["StateCode"] == "19"
    assert alt["PinCode"] == 700091
    # Real, distinct alternate address -- not a copy of the primary one.
    assert alt["ResidenceNo"] != address["ResidenceNo"]
    assert alt["CityOrTownOrDistrict"] != address["CityOrTownOrDistrict"]


def test_itr3_secondary_address_flag_without_data_fails_closed() -> None:
    """A taxpayer who declares a secondary address (SecondaryAdd=Y) but
    never actually enters one must not silently file with a copied or
    fabricated AlternateAddress -- the builder must fail closed."""
    draft = _draft_with_business()
    draft.personal.secondaryAddressDifferent = True
    draft.personal.alternateAddress = None

    typed_input, _breakdown = draft_to_itr3_input(draft)
    assert typed_input.secondary_address_different is True
    assert typed_input.alternate_residence_no is None

    from app.engine.calculators.itr3 import compute as compute_itr3
    from app.engine.itd.itr3 import build_itr3_json

    result = compute_itr3(typed_input)
    with pytest.raises(ValueError, match="alternate-address"):
        build_itr3_json(result, typed_input)


def test_itr3_nri_112_115_securities_reach_cg_transactions_and_json() -> None:
    """Schedule CG item B6 (``ltNri112115``) had no mapper for ITR-3 at
    all, and the corresponding ``NRIOnSec112and115`` JSON block was
    entirely absent from the builder (unlike its STCG sibling
    ``NRISecur115AD``, which correctly stays empty for ITR-3 since section
    115AD is FII/FPI-specific and ITR-3 filers -- individuals/HUF -- can
    never be an FII/FPI entity). This is a genuine gap in ITR-3's own
    official schema coverage, not a by-design omission: confirmed the
    field exists identically in ITR-3's own JSON schema by direct
    introspection."""
    draft = _draft_with_business()
    draft.capitalGainsSchedule.ltNri112115 = [{
        "sectionCode": "5AC1c", "fullConsideration": Decimal("800000"),
        "acquisitionCost": Decimal("200000"), "transferExpenses": Decimal("3000"),
        "deduction54F": Decimal("50000"),
    }]
    typed_input, _breakdown = draft_to_itr3_input(draft)
    matching = [tx for tx in typed_input.cg_transactions if tx.is_nri_unquoted_shares_disposal]
    assert len(matching) == 1
    assert matching[0].section_code == "115AC"

    from app.engine.calculators.itr3 import compute as compute_itr3
    from app.engine.itd.itr3 import build_itr3_json

    result = compute_itr3(typed_input)
    document = build_itr3_json(result, typed_input)
    cg = document["ITR"]["ITR3"]["ScheduleCGFor23"]
    nri_dtls = cg["LongTermCapGain23"]["NRIOnSec112and115"]["NRIOnSec112and115Dtls"]
    assert len(nri_dtls) == 1
    assert nri_dtls[0]["SectionCode"] == "5AC1c"
    assert nri_dtls[0]["FullConsideration"] == 800000
    assert nri_dtls[0]["DeductSec48"]["AquisitCost"] == 200000


def test_itr3_mapper_uses_schedule_bp_workspace_values() -> None:
    """Persisted Schedule BP values override the presumptive fallback fields."""
    draft = _draft_with_business()
    draft.itr3BusinessWorkspace.core = {
        "ITR3ScheduleBP": {
            "BusinessIncOthThanSpec": {
                "ProfBfrTaxPL": 125000,
                "AmtDebPLDisallowUs36": 1500,
                "AmtDebPLDisallowUs40A": 2500,
                "DeemIncUs41": 700,
                "DeductUs32_1_iii": 300,
                "IncProfDecLossAccICDSAdj": 400,
                "DecProfIncLossAccICDSAdj": 100,
            }
        }
    }
    typed_input, breakdown = draft_to_itr3_input(draft)
    assert typed_input.business_income is not None
    assert typed_input.business_income.net_profit_before_tax == Decimal("125000")
    assert typed_input.business_income.disallowance_us36 == Decimal("1500")
    assert typed_input.business_income.disallowance_us40a == Decimal("2500")
    assert typed_input.business_income.deemed_income_us41 == Decimal("700")
    assert typed_input.business_income.deduction_us32_1_iii == Decimal("300")
    assert typed_input.business_income.icds_increase == Decimal("400")
    assert typed_input.business_income.icds_decrease == Decimal("100")
    assert breakdown["business_income"] == Decimal("125000")


def test_itr3_mapper_preserves_part_a_pl_workspace_values() -> None:
    """The typed input preserves required PARTA_PL workspace totals."""
    draft = _draft_with_business()
    draft.itr3BusinessWorkspace.core = {
        "PARTA_PL": {
            "GrossProfit": 240000,
            "Expenditure": 90000,
            "NetIncomeFrmSpecActivity": 12000,
            "TurnverFrmSpecActivity": 300000,
            "NoBooksOfAccPL": {"GrossReceipt": 400000, "GrossProfit": 150000, "Expenses": 50000, "NetProfit": 100000},
            "TaxProvAppr": {"ProvForCurrTax": 20000, "ProvDefTax": 5000, "ProfitAfterTax": 75000},
            "CreditsToPL": {"GrossProfitTrnsfFrmTrdAcc": 240000, "TotCreditsToPL": 252000, "OthIncome": {"TotOthIncome": 12000}},
            "DebitsToPL": {"OtherExpenses": 90000, "PBT": 162000},
        }
    }
    typed_input, _ = draft_to_itr3_input(draft)
    assert typed_input.profit_and_loss is not None
    assert typed_input.profit_and_loss.gross_profit == Decimal("240000")
    assert typed_input.profit_and_loss.no_books_net_profit == Decimal("100000")
    assert typed_input.profit_and_loss.profit_before_tax == Decimal("162000")
    assert typed_input.profit_and_loss.other_income_breakdown.dividends == Decimal("0")


def test_itr3_mapper_and_builder_preserve_part_a_pl_credit_debit_breakdown() -> None:
    """Mapped PARTA_PL credits and interest debits reach official integer paths."""
    from app.engine.calculators.itr3 import compute as compute_itr3
    from app.engine.itd.itr3 import build_itr3_json

    draft = _draft_with_business()
    draft.itr3BusinessWorkspace.core = {"PARTA_PL": {
        "CreditsToPL": {"OthIncome": {"RentInc": 1100, "Dividends": 2200, "InterestInc": 3300, "MiscOthIncome": 4400, "TotOthIncome": 11000}, "TotCreditsToPL": 15000},
        "DebitsToPL": {"InterestExpdrtDtls": {"InterestExpdr": 7700, "NonResOtherCompany": 1200, "Others": 6500}},
    }}
    typed_input, _ = draft_to_itr3_input(draft)
    assert typed_input.profit_and_loss is not None
    assert typed_input.profit_and_loss.other_income_breakdown.rent_income == Decimal("1100")
    assert typed_input.profit_and_loss.interest_expense.total == Decimal("7700")
    payload = build_itr3_json(compute_itr3(typed_input), typed_input)["ITR"]["ITR3"]["PARTA_PL"]
    assert payload["CreditsToPL"]["OthIncome"]["Dividends"] == 2200
    assert payload["CreditsToPL"]["OthIncome"]["MiscOthIncome"] == 4400
    assert payload["DebitsToPL"]["InterestExpdrtDtls"] == {"InterestExpdr": 7700, "NonResOtherCompany": 1200, "Others": 6500}


def test_itr3_builder_preserves_parta_pl_pbidta_and_depreciation() -> None:
    """PARTA_PL carries form rows 50 and 52 instead of hard-coded zeroes."""
    from app.engine.calculators.itr3 import compute as compute_itr3
    from app.engine.itd.itr3 import build_itr3_json

    draft = _draft_with_business()
    draft.itr3BusinessWorkspace.core = {
        "PARTA_PL": {
            "DebitsToPL": {
                "PBIDTA": 161000,
                "DepreciationAmort": 9000,
                "PBT": 152000,
            }
        }
    }
    typed_input, _ = draft_to_itr3_input(draft)
    payload = build_itr3_json(compute_itr3(typed_input), typed_input)["ITR"]["ITR3"]["PARTA_PL"]
    assert payload["DebitsToPL"]["PBIDTA"] == 161000
    assert payload["DebitsToPL"]["DepreciationAmort"] == 9000
    assert payload["DebitsToPL"]["PBT"] == 152000


def test_itr3_builder_uses_part_a_pl_workspace_data() -> None:
    """PARTA_PL JSON carries typed workspace totals instead of hardcoded zeros."""
    from app.engine.calculators.itr3 import compute as compute_itr3
    from app.engine.itd.itr3 import build_itr3_json

    draft = _draft_with_business()
    draft.itr3BusinessWorkspace.core = {"PARTA_PL": {"GrossProfit": 240000, "Expenditure": 90000, "NetIncomeFrmSpecActivity": 12000, "TurnverFrmSpecActivity": 300000}}
    typed_input, _ = draft_to_itr3_input(draft)
    document = build_itr3_json(compute_itr3(typed_input), typed_input)
    pl = document["ITR"]["ITR3"]["PARTA_PL"]
    assert pl["GrossProfit"] == 240000
    assert pl["Expenditure"] == 90000
    assert pl["NetIncomeFrmSpecActivity"] == 12000
    assert pl["TurnverFrmSpecActivity"] == 300000


def test_itr3_builder_maps_parta_gen2_workspace() -> None:
    """Part A-GEN2 JSON carries mapped audit and nature-of-business data."""
    from app.engine.calculators.itr3 import compute as compute_itr3
    from app.engine.itd.itr3 import build_itr3_json

    draft = _draft_with_business()
    draft.itr3AuditInfo.accountAudit = "Y"
    draft.itr3AuditInfo.liableSec44AB = "Y"
    draft.itr3AuditInfo.incomeDeclaredUnderPresumptive = "Y"
    draft.itr3NatureOfBusiness = [ITR3NatureOfBusiness(code="14001", tradeName="Tech", description="Software")]
    typed_input, _ = draft_to_itr3_input(draft)
    document = build_itr3_json(compute_itr3(typed_input), typed_input)
    gen2 = document["ITR"]["ITR3"]["PartA_GEN2"]
    assert gen2["AuditInfo"]["AccountAuditFlag"] == "Y"
    assert gen2["AuditInfo"]["LiableSec44ABflg"] == "Y"
    assert gen2["AuditInfo"]["IncDclrdUs"] == "Y"
    assert gen2["NatOfBus"]["NatureOfBusiness"] == [{"Code": "14001", "Description": "Software"}]


def test_itr3_mapper_preserves_manufacturing_and_trading_accounts() -> None:
    """Official account schedules remain typed and lossless at field level."""
    draft = _draft_with_business()
    draft.itr3BusinessWorkspace.core = {
        "ManufacturingAccount": {
            "OpeningInventory": {"OpngStckRawMat": 10000, "Purchases": 50000, "TotalDebtsManfctrngAcc": 70000},
            "ClosingStock": {"ClsngStckRawMaterial": 5000, "ClsngStckTotal": 5000},
            "CostOfGoodsPrdcd": 65000,
        },
        "TradingAccount": {"OperatingRevenueTotal": 300000, "SalesGrossReceiptsTotal": 300000, "TotRevenueFrmOperations": 300000, "TardingAccTotCred": 305000, "DirectExpenses": 150000, "GrossProfitFrmBusProf": 155000},
    }
    typed_input, _ = draft_to_itr3_input(draft)
    assert typed_input.business_accounts is not None
    assert typed_input.business_accounts.manufacturing_account is not None
    assert typed_input.business_accounts.manufacturing_account.cost_of_goods_produced == Decimal("65000")
    assert typed_input.business_accounts.trading_account is not None
    assert typed_input.business_accounts.trading_account.values["GrossProfitFrmBusProf"] == Decimal("155000")


def test_itr3_builder_emits_manufacturing_and_trading_schedules() -> None:
    """The builder emits exact official schedule names and nesting."""
    from app.engine.calculators.itr3 import compute as compute_itr3
    from app.engine.itd.itr3 import build_itr3_json

    draft = _draft_with_business()
    draft.itr3BusinessWorkspace.core = {"ManufacturingAccount": {"OpeningInventory": {"OpngStckRawMat": 10000}, "ClosingStock": {"ClsngStckTotal": 5000}, "CostOfGoodsPrdcd": 65000}, "TradingAccount": {"OperatingRevenueTotal": 300000, "SalesGrossReceiptsTotal": 300000, "TotRevenueFrmOperations": 300000, "TardingAccTotCred": 305000, "DirectExpenses": 150000}}
    typed_input, _ = draft_to_itr3_input(draft)
    payload = build_itr3_json(compute_itr3(typed_input), typed_input)["ITR"]["ITR3"]
    assert payload["ManufacturingAccount"]["OpeningInventory"]["OpngStckRawMat"] == 10000
    assert payload["ManufacturingAccount"]["CostOfGoodsPrdcd"] == 65000
    assert payload["TradingAccount"]["OperatingRevenueTotal"] == 300000
    assert payload["TradingAccount"]["DirectExpenses"] == 150000


    """Official workspace schedules are authoritative over duplicate legacy fields."""
    draft = _draft_with_business()
    draft.itr3AuditInfo.accountAudit = "N"
    draft.itr3NatureOfBusiness = [ITR3NatureOfBusiness(code="14001", tradeName="Legacy", description="Legacy")]
    draft.itr3BusinessWorkspace.core = {
        "PartA_GEN2": {
            "AuditInfo": {"AccountAuditFlag": "Y", "LiableSec44ABflg": "Y", "IncDclrdUs": "Y"},
            "NatOfBus": {"NatureOfBusiness": [{"Code": "16001", "Description": "Legal profession"}]},
        }
    }
    typed_input, _ = draft_to_itr3_input(draft)
    assert typed_input.audit_info is not None and typed_input.audit_info.account_audited is True
    assert typed_input.nature_of_business is not None
    assert typed_input.nature_of_business[0].code == "16001"


def test_itr3_mapper_prefers_workspace_balance_sheet_over_legacy_fields() -> None:
    """PARTA_BS workspace totals are authoritative over the duplicate summary."""
    draft = _draft_with_business()
    draft.itr3BalanceSheet.totalSources = Decimal("999")
    draft.itr3BusinessWorkspace.core = {
        "PARTA_BS": {
            "FundSrc": {
                "PropFund": {"TotPropFund": 700000},
                "LoanFunds": {"SecrLoan": {"TotSecrLoan": 100000}, "UnsecrLoan": {"TotUnSecrLoan": 50000}},
                "TotFundSrc": 850000,
            },
            "FundApply": {"FixedAsset": {"TotFixedAsset": 500000}, "CurrAssetLoanAdv": {"TotCurrAssetLoanAdv": 350000}, "TotFundApply": 850000},
        }
    }
    typed_input, _ = draft_to_itr3_input(draft)
    assert typed_input.balance_sheet is not None
    assert typed_input.balance_sheet.total_liabilities == Decimal("850000")
    assert typed_input.balance_sheet.total_assets == Decimal("850000")


    """The form dispatcher must route ITR-3 to the typed calculator path."""
    result = compute_canonical(_draft_with_business())
    assert isinstance(result, ITR3PipelineResult)
    assert result.summary["computedByFormEngine"] == "ITR-3"


def test_itr3_input_validator_reports_missing_business_income() -> None:
    """The baseline validator blocks an ITR-3 input without PGBP data."""
    typed_input, _ = draft_to_itr3_input(_draft_with_business())
    typed_input.business_income = None
    report = run_input_validation(typed_input)
    assert not report.can_upload
    assert any(item.rule_id == "ITR3-R001" for item in report.blocking_errors)


def test_itr3_input_validator_accepts_canonical_business_input() -> None:
    """A valid canonical foundation input passes the baseline validator."""
    typed_input, _ = draft_to_itr3_input(_draft_with_business())
    report = run_input_validation(typed_input)
    assert report.can_upload


def test_itr3_calculation_validator_accepts_computed_result() -> None:
    """The baseline calculation rules accept the current valid result."""
    pipeline = compute_canonical_itr3(_draft_with_business())
    report = run_calc_validation(pipeline.typed_input, pipeline.computation)
    assert report.can_upload
def test_itr3_schema_validator_reports_json_and_schema_paths() -> None:
    """Malformed documents expose actionable official-schema locations."""
    with pytest.raises(ITR3SchemaValidationError) as exc_info:
        validate_itr3_json({"ITR": {"ITR3": {}}})
    error = exc_info.value.errors[0]
    assert error["path"] == "ITR.ITR3"
    assert error["schema_path"]


def test_itr3_generation_fails_closed_until_builder_is_schema_exact() -> None:
    """The foundation must reject placeholder JSON, never return it as filing JSON."""
    with pytest.raises(FilingGatewayV2Error, match="official JSON generation failed"):
        generate_cbdt_json(_draft_with_business())


def test_itr3_compute_entrypoint_sets_filing_date() -> None:
    """The declared verification date reaches the computation input."""
    pipeline = compute_canonical_itr3(_draft_with_business())
    assert pipeline.typed_input.filing_date is not None
    assert pipeline.typed_input.filing_date.isoformat() == "2026-07-31"
