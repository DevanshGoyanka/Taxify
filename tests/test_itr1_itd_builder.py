"""Official-schema and detail-preservation tests for the ITR-1 JSON builder."""

import json
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from jsonschema import Draft4Validator

from pydantic import ValidationError

from app.engine.calculators.itr1 import compute
from app.engine.itd.itr1 import build_itr1_json
from app.schemas.itr1 import (
    AgeBracket,
    BankAccount,
    CapitalGainsIncome,
    Chapter6ADeductions,
    DependentRelationship,
    DisabilityCategory,
    DisabilitySeverity,
    Donation80G,
    Donation80GGA,
    DonationAddress,
    EducationLoanLenderType,
    FilingAddress,
    HousePropertyIncome,
    ITR1FilingProfile,
    ITR1Input,
    OtherSourcesIncome,
    PoliticalContribution,
    PostalAddress,
    PropertyFilingProfile,
    PropertyType,
    SalaryIncome,
    Schedule80CEntry,
    Schedule80DD,
    Schedule80EEntry,
    Schedule80GGA,
    Schedule80GGC,
    ITR1Schedule80EELoanEntry,
    ITR1Schedule80EEALoanEntry,
    ITR1Schedule80EEBLoanEntry,
    Schedule80U,
    Section80DDBDetails,
    Section80DDBUserType,
    Section80GGAClause,
    SpecifiedDisease80DDB,
    TDS1Entry,
    TDS2Entry,
    TCSEntry,
    TaxPaymentDetail,
    TaxRegime,
)

_SCHEMA_PATH = (
    Path(__file__).resolve().parents[1]
    / "Reference Docs by CBDT & ITD"
    / "Official JSON Schema"
    / "ITR-1_2026_Main_V1.1 (2).json"
)


def _input(*, amount_80c: str = "100000", amount_80d: str = "25000") -> ITR1Input:
    """Build a detailed old-regime input suitable for official JSON tests."""
    return ITR1Input(
        age_bracket=AgeBracket.BELOW_60,
        tax_regime=TaxRegime.OLD,
        salary_income=SalaryIncome(
            gross_salary=Decimal("1000000"),
            hra_exempt_amount=Decimal("120000"),
            lta_exempt_amount=Decimal("20000"),
        ),
        house_property_income=HousePropertyIncome(
            property_type=PropertyType.SELF_OCCUPIED
        ),
        other_sources_income=OtherSourcesIncome(
            savings_bank_interest=Decimal("10000"),
            fixed_deposit_interest=Decimal("20000"),
            family_pension_received=Decimal("30000"),
            dividend_income=Decimal("4000"),
            interest_on_it_refund=Decimal("1000"),
        ),
        deductions_chapter6a=Chapter6ADeductions(
            amount_80c=Decimal(amount_80c),
            amount_80d_self_family=Decimal(amount_80d),
        ),
        schedule_80c_entries=(
            [Schedule80CEntry(
                amount=Decimal(amount_80c),
                payment_type="PPF",
                identifier_number="PPF-12345",
            )]
            if Decimal(amount_80c) > 0 else []
        ),
        bank_accounts=[BankAccount(
            account_number="1234567890",
            ifsc_code="SBIN0001234",
            bank_name="State Bank of India",
            account_type="savings",
            is_primary=True,
        )],
        filing_profile=ITR1FilingProfile(
            pan="ABCDE1234F",
            first_name="Asha",
            middle_name="Rani",
            surname="Sharma",
            date_of_birth=date(1990, 1, 15),
            employer_category="OTH",
            aadhaar_number="123456789012",
            primary_address=FilingAddress(
                residence_no="12A",
                road_or_street="MG Road",
                locality_or_area="Central Colony",
                city_or_town_or_district="Delhi",
                state_code="07",
                country_code="91",
                pin_code="110001",
                mobile_no="9876543210",
                email="asha.sharma@example.com",
            ),
            father_name="Ramesh Sharma",
            verification_place="Delhi",
            verification_capacity="S",
            return_file_section=11,
        ),
        property_profile=PropertyFilingProfile(
            address_detail="Flat 12A, MG Road",
            city_or_town_or_district="Delhi",
            state_code="07",
            country_code="91",
            pin_code="110001",
        ),
        agriculture_income=Decimal("5000"),
        nature_of_employment="Private",
    )


def _build(body: ITR1Input) -> dict:
    """Compute and build an ITR-1 document with deterministic source data."""
    result = compute(body)
    assert result.errors == []
    return build_itr1_json(result, body)


def test_builder_projects_canonical_restricted_112a_schedule() -> None:
    """Canonical transactions must cross-foot into the official LTCG schedule."""
    body = _input().model_copy(update={
        "capital_gains": CapitalGainsIncome(transactions=[{
            "assetType": "LISTED_EQUITY",
            "purchaseDate": "2023-01-01",
            "saleDate": "2025-01-02",
            "purchaseCost": "100000",
            "saleCost": "120000",
            "transferExpenses": "1000",
            "sttPaidOnAcquisition": True,
            "sttPaidOnTransfer": True,
            "recognizedExchange": True,
        }]),
    })
    schedule = _build(body)["ITR"]["ITR1"]["LTCG112A"]
    assert schedule == {
        "TotSaleCnsdrn": 120000,
        "TotCstAcqisn": 101000,
        "LongCap112A": 19000,
    }


def test_builder_emits_zero_cost_canonical_112a_schedule() -> None:
    """A legitimate zero acquisition cost must not suppress LTCG112A."""
    body = _input().model_copy(update={
        "capital_gains": CapitalGainsIncome(transactions=[{
            "assetType": "LISTED_EQUITY",
            "purchaseDate": "2023-01-01",
            "saleDate": "2025-01-02",
            "purchaseCost": "0",
            "saleCost": "100000",
            "transferExpenses": "0",
            "sttPaidOnAcquisition": True,
            "sttPaidOnTransfer": True,
            "recognizedExchange": True,
        }]),
    })
    schedule = _build(body)["ITR"]["ITR1"]["LTCG112A"]
    assert schedule["TotCstAcqisn"] == 0
    assert schedule["LongCap112A"] == 100000


def test_detailed_document_matches_official_ay_2026_27_schema() -> None:
    """A generated detailed return must satisfy the official Draft-4 schema."""
    schema = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8-sig"))
    errors = list(Draft4Validator(schema).iter_errors(_build(_input())))

    assert errors == [], [
        f"{'/'.join(map(str, error.absolute_path))}: {error.message}"
        for error in errors
    ]


def test_builder_maps_self_occupied_property_profile() -> None:
    """Self-occupied property must contain real address and zero cross-footed rent."""
    prop = _build(_input())["ITR"]["ITR1"]["ITR1_IncomeDeductions"][
        "PropertyDetails"
    ][0]
    assert prop["AddressDetailWithZipCode"] == {
        "AddrDetail": "Flat 12A, MG Road",
        "CityOrTownOrDistrict": "Delhi",
        "StateCode": "07",
        "CountryCode": "91",
        "PinCode": 110001,
    }
    assert prop["PropertyOwner"] == "SE"
    assert prop["PropCoOwnedFlg"] == "NO"
    assert prop["AsseseeShareProperty"] == 100
    assert prop["ifLetOut"] == "S"
    assert prop["Rentdetails"] == {
        "AnnualLetableValue": 0,
        "TotalUnrealizedAndTax": 0,
        "BalanceALV": 0,
        "AnnualOfPropOwned": 0,
        "ThirtyPercentOfBalance": 0,
        "IntOnBorwCap": 0,
        "TotalDeduct": 0,
        "IncomeOfHP": 0,
    }


@pytest.mark.parametrize(
    ("property_type", "rent", "taxes", "arrears", "expected"),
    [
        (PropertyType.LET_OUT, "300000", "10000", "0", 203000),
        (PropertyType.DEEMED_LET_OUT, "240000", "12000", "30000", 180600),
    ],
)
def test_builder_cross_foots_let_out_property(
    property_type: PropertyType,
    rent: str,
    taxes: str,
    arrears: str,
    expected: int,
) -> None:
    """Let-out and deemed-let-out schedules must match calculator income."""
    body = _input().model_copy(update={
        "house_property_income": HousePropertyIncome(
            property_type=property_type,
            annual_rent_received=Decimal(rent),
            municipal_taxes_paid=Decimal(taxes),
            arrears_unrealised_rent_received=Decimal(arrears),
        )
    })
    income = _build(body)["ITR"]["ITR1"]["ITR1_IncomeDeductions"]
    rent_details = income["PropertyDetails"][0]["Rentdetails"]
    assert rent_details["IncomeOfHP"] == expected
    assert income["TotalIncomeChargeableUnHP"] == expected
    assert rent_details["TotalDeduct"] == rent_details["ThirtyPercentOfBalance"]
    assert "Section24B" not in rent_details
    assert "TenantDetails" not in income["PropertyDetails"][0]


def test_builder_cross_foots_fractional_property_rounding() -> None:
    """Independent half-even rounding must not reject a valid property schedule."""
    body = _input().model_copy(update={
        "house_property_income": HousePropertyIncome(
            property_type=PropertyType.LET_OUT,
            annual_rent_received=Decimal("5"),
        )
    })
    income = _build(body)["ITR"]["ITR1"]["ITR1_IncomeDeductions"]
    rent_details = income["PropertyDetails"][0]["Rentdetails"]
    assert rent_details["AnnualOfPropOwned"] == 5
    assert rent_details["ThirtyPercentOfBalance"] == 1
    assert rent_details["IncomeOfHP"] == 4
    assert rent_details["AnnualOfPropOwned"] - rent_details["TotalDeduct"] == 4


def test_property_profile_rejects_non_official_country_code() -> None:
    """Property country code must belong to the official ITD enumeration."""
    with pytest.raises(ValidationError, match="official ITD country code"):
        PropertyFilingProfile(
            address_detail="1 Main Road",
            city_or_town_or_district="Nowhere",
            state_code="99",
            country_code="abcd",
        )


@pytest.mark.parametrize(
    ("regime", "expected_top_level"),
    [
        (TaxRegime.OLD, -200000),
        (TaxRegime.NEW, 0),
    ],
)
def test_property_row_preserves_raw_loss_before_inter_head_setoff(
    regime: TaxRegime,
    expected_top_level: int,
) -> None:
    """The property row keeps raw loss while the top level applies regime limits."""
    body = _input().model_copy(update={
        "tax_regime": regime,
        "house_property_income": HousePropertyIncome(
            property_type=PropertyType.LET_OUT,
            annual_rent_received=Decimal("100000"),
            home_loan_interest_paid=Decimal("400000"),
        ),
    })
    result = compute(body)
    # schedules["hp"] is now a list of HPResult (one per property); the
    # single-property case yields a one-element list.
    assert result.schedules["hp"][0].income_chargeable == Decimal("-330000.0")
    assert result.hp_results[0].income_chargeable == Decimal("-330000.0")
    assert result.house_property_income == Decimal(expected_top_level)

    # Loan-detail mapping is deliberately outside this slice. Clear only the
    # input guard to exercise the raw-vs-post-setoff serialization contract.
    serializable = body.model_copy(deep=True)
    serializable.house_property_income.home_loan_interest_paid = Decimal("0")
    income = build_itr1_json(result, serializable)["ITR"]["ITR1"][
        "ITR1_IncomeDeductions"
    ]
    assert income["PropertyDetails"][0]["Rentdetails"]["IncomeOfHP"] == -330000
    assert income["TotalIncomeChargeableUnHP"] == expected_top_level


def test_builder_rejects_missing_or_unsupported_property_details() -> None:
    """Property JSON must not fabricate address, co-owner, or loan identities."""
    with pytest.raises(ValueError, match="property_profile"):
        _build(_input().model_copy(update={"property_profile": None}))
    with pytest.raises(ValueError, match="Co-owned"):
        _build(_input().model_copy(update={"is_property_co_owned": True}))
    body = _input().model_copy(update={
        "house_property_income": HousePropertyIncome(
            property_type=PropertyType.SELF_OCCUPIED,
            home_loan_interest_paid=Decimal("10000"),
        )
    })
    with pytest.raises(ValueError, match=r"24\(b\)"):
        _build(body)


def test_builder_preserves_filing_profile_without_placeholders() -> None:
    """Personal information, filing status, and verification must use source data."""
    itr1 = _build(_input())["ITR"]["ITR1"]

    assert itr1["PersonalInfo"] == {
        "AssesseeName": {
            "FirstName": "Asha",
            "MiddleName": "Rani",
            "SurNameOrOrgName": "Sharma",
        },
        "PAN": "ABCDE1234F",
        "Address": {
            "ResidenceNo": "12A",
            "ResidenceName": "",
            "RoadOrStreet": "MG Road",
            "LocalityOrArea": "Central Colony",
            "CityOrTownOrDistrict": "Delhi",
            "StateCode": "07",
            "CountryCode": "91",
            "PinCode": 110001,
            "ZipCode": "",
            "CountryCodeMobile": 91,
            "MobileNo": 9876543210,
            "CountryCodeMobileNoSec": 0,
            "MobileNoSec": 0,
            "EmailAddress": "asha.sharma@example.com",
        },
        "SecondaryAdd": "N",
        "DOB": "1990-01-15",
        "EmployerCategory": "OTH",
        "AadhaarCardNo": "123456789012",
    }
    assert itr1["FilingStatus"]["ReturnFileSec"] == 11
    assert itr1["FilingStatus"]["OptOutNewTaxRegime"] == "Y"
    assert itr1["Verification"] == {
        "Declaration": {
            "AssesseeVerName": "Asha Rani Sharma",
            "FatherName": "Ramesh Sharma",
            "AssesseeVerPAN": "ABCDE1234F",
        },
        "Capacity": "S",
        "Place": "Delhi",
    }
    serialized = json.dumps(itr1)
    for placeholder in (
        "AAAAA0000A",
        "assessee@example.com",
        "9999999999",
        '"FATHER"',
        '"ASSESSEE"',
    ):
        assert placeholder not in serialized


def test_builder_rejects_missing_filing_profile() -> None:
    """API-path JSON generation must not fabricate required taxpayer identity."""
    body = _input().model_copy(update={"filing_profile": None})
    with pytest.raises(ValueError, match="filing_profile"):
        _build(body)


def test_builder_maps_alternate_address() -> None:
    """A supplied alternate address must be preserved in PersonalInfo."""
    profile = _input().filing_profile
    assert profile is not None
    alternate = PostalAddress(
        residence_no="9",
        locality_or_area="Camp Area",
        city_or_town_or_district="Pune",
        state_code="27",
        country_code="91",
        pin_code="411001",
    )
    body = _input().model_copy(update={
        "filing_profile": profile.model_copy(update={"alternate_address": alternate})
    })
    personal = _build(body)["ITR"]["ITR1"]["PersonalInfo"]
    assert personal["SecondaryAdd"] == "Y"
    assert personal["AlternateAddress"]["CityOrTownOrDistrict"] == "Pune"
    assert "MobileNo" not in personal["AlternateAddress"]


def test_filing_profile_rejects_non_self_and_unsupported_sections() -> None:
    """Incomplete representative/revised filing modes must fail at input parsing."""
    profile = _input().filing_profile
    assert profile is not None
    with pytest.raises(ValidationError):
        ITR1FilingProfile(**{
            **profile.model_dump(),
            "verification_capacity": "R",
        })
    with pytest.raises(ValidationError):
        ITR1FilingProfile(**{
            **profile.model_dump(),
            "return_file_section": 17,
        })


def test_filing_profile_uses_official_email_and_employer_categories() -> None:
    """Profile constraints must match official email and employer enums."""
    profile = _input().filing_profile
    assert profile is not None
    with pytest.raises(ValidationError):
        FilingAddress(**{
            **profile.primary_address.model_dump(),
            "email": "not-an-email",
        })
    pensioner = profile.model_copy(update={"employer_category": "PESG"})
    assert _build(_input().model_copy(update={"filing_profile": pensioner}))[
        "ITR"
    ]["ITR1"]["PersonalInfo"]["EmployerCategory"] == "PESG"


def test_builder_preserves_allowance_and_other_source_details() -> None:
    """Section 10, Section 57, exempt, and OS details must not be discarded."""
    income = _build(_input())["ITR"]["ITR1"]["ITR1_IncomeDeductions"]

    allowances = {
        row["SalNatureDesc"]: row["SalOthAmount"]
        for row in income["AllwncExemptUs10"]["AllwncExemptUs10Dtls"]
    }
    other_sources = {
        row["OthSrcNatureDesc"]: row["OthSrcOthAmount"]
        for row in income["OthersInc"]["OthersIncDtlsOthSrc"]
    }

    assert allowances == {"10(5)": 20000, "10(13A)": 120000}
    assert other_sources == {
        "SAV": 10000,
        "IFD": 20000,
        "TAX": 1000,
        "FAP": 30000,
        "DIV": 4000,
    }
    assert income["DeductionUs57iia"] == 10000
    assert income["ExemptIncAgriOthUs10"]["ExemptIncAgriOthUs10Total"] == 5000


def test_builder_omits_empty_tds3_schedule() -> None:
    """An absent TDS3 input must omit the optional non-empty schedule."""
    itr1 = _build(_input())["ITR"]["ITR1"]
    assert "ScheduleTDS3Dtls" not in itr1


def test_deduction_state_is_isolated_across_concurrent_builds() -> None:
    """Concurrent builds must not leak one taxpayer's deductions to another."""
    inputs = [
        _input(amount_80c="10000", amount_80d="5000"),
        _input(amount_80c="140000", amount_80d="25000"),
    ]

    with ThreadPoolExecutor(max_workers=2) as executor:
        documents = list(executor.map(_build, inputs))

    first = documents[0]["ITR"]["ITR1"]["ITR1_IncomeDeductions"]["DeductUndChapVIA"]
    second = documents[1]["ITR"]["ITR1"]["ITR1_IncomeDeductions"]["DeductUndChapVIA"]
    assert (first["Section80C"], first["Section80D"]) == (10000, 5000)
    assert (second["Section80C"], second["Section80D"]) == (140000, 25000)


def test_builder_maps_real_tax_credit_and_challan_rows() -> None:
    """Credit and payment schedules must preserve source identity and amounts."""
    body = _input().model_copy(update={
        "tds1_entries": [TDS1Entry(
            employer_tan="DELA00001A",
            employer_name="Example Employer",
            income_chargeable=Decimal("500000"),
            tds_deducted=Decimal("25000"),
        )],
        "tds2_entries": [TDS2Entry(
            deductor_tan="MUMA00001A",
            deductor_name="Example Bank",
            tds_section="194A",
            gross_amount=Decimal("20000"),
            tds_deducted=Decimal("2000"),
            tds_claimed_this_year=Decimal("2000"),
        )],
        "tcs_entries": [TCSEntry(
            collector_tan="BLRA00001A",
            collector_name="Example Collector",
            tcs_section="206C",
            gross_amount=Decimal("100000"),
            tcs_collected=Decimal("1000"),
            tcs_credit_claimed=Decimal("1000"),
        )],
        "advance_tax_paid": Decimal("5000"),
        "tax_payment_entries": [TaxPaymentDetail(
            amount=Decimal("5000"),
            payment_type="advance",
            payment_date=date(2025, 6, 15),
            bsr_code="1234ABC",
            challan_serial_number="00001",
        )],
    })

    itr1 = _build(body)["ITR"]["ITR1"]

    assert itr1["TDSonSalaries"]["TDSonSalary"][0][
        "EmployerOrDeductorOrCollectDetl"
    ]["TAN"] == "DELA00001A"
    assert itr1["TDSonOthThanSals"]["TDSonOthThanSal"][0]["TDSSection"] == "94A"
    assert itr1["ScheduleTCS"]["TCS"][0]["TotalTCS"] == 1000
    assert itr1["TaxPayments"]["TaxPayment"][0] == {
        "BSRCode": "1234ABC",
        "DateDep": "2025-06-15",
        "SrlNoOfChaln": 1,
        "Amt": 5000,
    }


def test_80c_family_components_do_not_double_report() -> None:
    """The shared 80CCE cap must retain distinct 80C, 80CCC, and 80CCD(1) rows."""
    body = _input().model_copy(update={
        "deductions_chapter6a": Chapter6ADeductions(
            amount_80c=Decimal("50000"),
            amount_80ccc=Decimal("25000"),
            amount_80ccd1=Decimal("25000"),
        ),
        "schedule_80c_entries": [Schedule80CEntry(
            amount=Decimal("50000"),
            payment_type="PPF",
            identifier_number="PPF-12345",
        )],
    })

    deductions = _build(body)["ITR"]["ITR1"]["ITR1_IncomeDeductions"][
        "DeductUndChapVIA"
    ]
    assert deductions["Section80C"] == 50000
    assert deductions["Section80CCC"] == 25000
    assert deductions["Section80CCDEmployeeOrSE"] == 25000
    assert deductions["TotalChapVIADeductions"] == 100000


def test_builder_maps_all_real_bank_accounts() -> None:
    """Refund details must preserve every bank and exactly one primary account."""
    body = _input().model_copy(update={
        "bank_accounts": [
            BankAccount(
                account_number="1234567890",
                ifsc_code="SBIN0001234",
                bank_name="State Bank of India",
                account_type="savings",
                is_primary=True,
            ),
            BankAccount(
                account_number="CURRENT123",
                ifsc_code="HDFC0005678",
                bank_name="HDFC Bank",
                account_type="current",
                is_primary=False,
            ),
        ]
    })

    rows = _build(body)["ITR"]["ITR1"]["Refund"]["BankAccountDtls"][
        "AddtnlBankDetails"
    ]
    assert rows == [
        {
            "IFSCCode": "SBIN0001234",
            "BankName": "State Bank of India",
            "BankAccountNo": "1234567890",
            "AccountType": "SB",
            "UseForRefund": "true",
        },
        {
            "IFSCCode": "HDFC0005678",
            "BankName": "HDFC Bank",
            "BankAccountNo": "CURRENT123",
            "AccountType": "CA",
            "UseForRefund": "false",
        },
    ]


def test_builder_rejects_missing_bank_details() -> None:
    """Official JSON generation must never fabricate a refund bank account."""
    body = _input().model_copy(update={"bank_accounts": []})

    with pytest.raises(ValueError, match="bank account"):
        _build(body)


def test_builder_preserves_schedule_80c_rows() -> None:
    """Schedule 80C must contain the real identifier and payment amount."""
    schedule = _build(_input())["ITR"]["ITR1"]["Schedule80C"]
    assert schedule == {
        "Schedule80CDtls": [
            {"IdentificationNo": "PPF-12345", "Amount": 100000}
        ],
        "TotalAmt": 100000,
    }


def test_builder_omits_zero_unsupported_schedules() -> None:
    """Zero-value optional schedules must be omitted instead of fabricated."""
    itr1 = _build(_input())["ITR"]["ITR1"]
    for key in (
        "Schedule80G",
        "Schedule80GGA",
        "Schedule80GGC",
        "Schedule80DD",
        "Schedule80U",
        "Schedule80E",
        "Schedule80EE",
        "Schedule80EEA",
        "Schedule80EEB",
        "TaxReturnPreparer",
    ):
        assert key not in itr1


def test_builder_allocates_capped_80c_rows_to_allowed_total() -> None:
    """Capped 80C rows and schedule total must equal the allowed deduction."""
    body = _input(amount_80c="200000").model_copy(update={
        "schedule_80c_entries": [
            Schedule80CEntry(amount=Decimal("120000"), identifier_number="PPF-1"),
            Schedule80CEntry(amount=Decimal("80000"), identifier_number="ELSS-1"),
        ]
    })
    schedule = _build(body)["ITR"]["ITR1"]["Schedule80C"]
    assert sum(row["Amount"] for row in schedule["Schedule80CDtls"]) == 150000
    assert schedule["TotalAmt"] == 150000


def test_builder_requires_exactly_one_refund_account() -> None:
    """Direct builder calls must reject zero or multiple primary accounts."""
    accounts = [
        BankAccount(
            account_number="1234567890",
            ifsc_code="SBIN0001234",
            bank_name="State Bank of India",
            account_type="savings",
            is_primary=False,
        ),
        BankAccount(
            account_number="CURRENT123",
            ifsc_code="HDFC0005678",
            bank_name="HDFC Bank",
            account_type="current",
            is_primary=False,
        ),
    ]
    with pytest.raises(ValueError, match="Exactly one"):
        _build(_input().model_copy(update={"bank_accounts": accounts}))


def test_builder_preserves_preventive_80d_bucket() -> None:
    """Preventive checkups must not be reported as insurance premiums."""
    body = _input(amount_80d="0").model_copy(update={
        "deductions_chapter6a": Chapter6ADeductions(
            amount_80c=Decimal("100000"),
            amount_80d_self_family=Decimal("20000"),
            amount_80d_preventive_self=Decimal("5000"),
        )
    })
    schedule = _build(body)["ITR"]["ITR1"]["Schedule80D"][
        "Sec80DSelfFamSrCtznHealth"
    ]
    assert schedule["HealthInsPremSlfFam"] == 20000
    assert schedule["PrevHlthChckUpSlfFam"] == 5000
    assert schedule["EligibleAmountOfDedn"] == 25000


def test_builder_emits_complete_schedule_80dd() -> None:
    """A complete dependent-disability claim must map to official Schedule 80DD."""
    detail = Schedule80DD(
        disability_type=DisabilitySeverity.SEVERE,
        disability_category=DisabilityCategory.AUTISM_CEREBRAL_PALSY_OR_MULTIPLE,
        deduction_amount=Decimal("125000"),
        dependent_relationship=DependentRelationship.DAUGHTER,
        dependent_pan="ABCDE1234F",
        dependent_aadhaar="123456789012",
        form_10ia_ack_number="ACK80DD123",
        udid_number="UDID80DD123",
    )
    body = _input().model_copy(update={
        "deductions_chapter6a": Chapter6ADeductions(
            amount_80c=Decimal("100000"),
            amount_80dd=Decimal("125000"),
        ),
        "schedule_80dd": detail,
        "form_10ia_filed": True,
    })
    itr1 = _build(body)["ITR"]["ITR1"]
    assert itr1["Schedule80DD"] == {
        "NatureOfDisability": "2",
        "TypeOfDisability": "1",
        "DeductionAmount": 125000,
        "DependentType": "3",
        "DependentPan": "ABCDE1234F",
        "DependentAadhaar": "123456789012",
        "Form10IAAckNum": "ACK80DD123",
        "UDIDNum": "UDID80DD123",
    }
    assert itr1["ITR1_IncomeDeductions"]["DeductUndChapVIA"]["Section80DD"] == 125000


def test_builder_emits_complete_schedule_80u() -> None:
    """A complete self-disability claim must map to official Schedule 80U."""
    detail = Schedule80U(
        disability_type=DisabilitySeverity.NORMAL,
        disability_category=DisabilityCategory.OTHER,
        deduction_amount=Decimal("75000"),
        udid_number="UDID80U123",
    )
    body = _input().model_copy(update={
        "deductions_chapter6a": Chapter6ADeductions(
            amount_80c=Decimal("100000"),
            amount_80u=Decimal("75000"),
        ),
        "schedule_80u": detail,
        "form_10ia_filed": True,
    })
    itr1 = _build(body)["ITR"]["ITR1"]
    assert itr1["Schedule80U"] == {
        "NatureOfDisability": "1",
        "TypeOfDisability": "2",
        "DeductionAmount": 75000,
        "UDIDNum": "UDID80U123",
    }
    assert itr1["ITR1_IncomeDeductions"]["DeductUndChapVIA"]["Section80U"] == 75000


def test_builder_rejects_incomplete_disability_schedules() -> None:
    """Positive disability claims require identity and certificate details."""
    base = _input().model_copy(update={
        "deductions_chapter6a": Chapter6ADeductions(
            amount_80c=Decimal("100000"),
            amount_80dd=Decimal("75000"),
        ),
        "form_10ia_filed": True,
    })
    with pytest.raises(ValueError, match="Schedule 80DD details"):
        _build(base)
    with pytest.raises(ValueError, match="dependent_relationship"):
        _build(base.model_copy(update={
            "schedule_80dd": Schedule80DD(
                deduction_amount=Decimal("75000"),
                udid_number="UDID123",
            )
        }))


def test_builder_allows_optional_disability_certificate_identifiers() -> None:
    """Official schema permits omission of Form 10-IA acknowledgement and UDID."""
    body = _input().model_copy(update={
        "deductions_chapter6a": Chapter6ADeductions(
            amount_80c=Decimal("100000"),
            amount_80u=Decimal("75000"),
        ),
        "schedule_80u": Schedule80U(deduction_amount=Decimal("75000")),
        "form_10ia_filed": True,
    })
    assert _build(body)["ITR"]["ITR1"]["Schedule80U"] == {
        "NatureOfDisability": "1",
        "TypeOfDisability": "2",
        "DeductionAmount": 75000,
    }


def test_builder_rejects_disability_severity_amount_mismatch() -> None:
    """Selected disability severity must determine the fixed statutory amount."""
    body = _input().model_copy(update={
        "deductions_chapter6a": Chapter6ADeductions(
            amount_80c=Decimal("100000"),
            amount_80u=Decimal("75000"),
        ),
        "schedule_80u": Schedule80U(
            disability_type=DisabilitySeverity.SEVERE,
            deduction_amount=Decimal("75000"),
            udid_number="UDID123",
        ),
        "form_10ia_filed": True,
    })
    with pytest.raises(ValueError, match="125000"):
        _build(body)


def test_builder_resolves_legacy_nested_disability_schedule() -> None:
    """Nested shared schedule details must resolve to the same canonical source."""
    detail = Schedule80U(
        deduction_amount=Decimal("75000"),
        udid_number="NESTED-UDID",
    )
    body = _input().model_copy(update={
        "deductions_chapter6a": Chapter6ADeductions(
            amount_80c=Decimal("100000"),
            amount_80u=Decimal("75000"),
            schedule_80u=detail,
        ),
        "form_10ia_filed": True,
    })
    assert _build(body)["ITR"]["ITR1"]["Schedule80U"]["UDIDNum"] == "NESTED-UDID"


def test_builder_rejects_huf_dependent_relationship_for_itr1() -> None:
    """The shared HUF relationship is valid for ITR-4 but not ITR-1."""
    body = _input().model_copy(update={
        "deductions_chapter6a": Chapter6ADeductions(
            amount_80c=Decimal("100000"),
            amount_80dd=Decimal("75000"),
        ),
        "schedule_80dd": Schedule80DD(
            deduction_amount=Decimal("75000"),
            dependent_relationship=DependentRelationship.MEMBER_OF_HUF,
        ),
        "form_10ia_filed": True,
    })
    with pytest.raises(ValueError, match="does not allow"):
        _build(body)


def test_builder_cross_foots_gti_restricted_disability_deduction() -> None:
    """A GTI cap must restrict the schedule and both Chapter VI-A copies equally."""
    body = _input(amount_80c="0", amount_80d="0").model_copy(update={
        "salary_income": SalaryIncome(gross_salary=Decimal("90000")),
        "other_sources_income": OtherSourcesIncome(),
        "deductions_chapter6a": Chapter6ADeductions(amount_80u=Decimal("75000")),
        "schedule_80u": Schedule80U(deduction_amount=Decimal("75000")),
        "form_10ia_filed": True,
        "agriculture_income": Decimal("0"),
    })
    itr1 = _build(body)["ITR"]["ITR1"]
    assert itr1["Schedule80U"]["DeductionAmount"] == 40000
    chapter = itr1["ITR1_IncomeDeductions"]
    assert chapter["DeductUndChapVIA"]["Section80U"] == 40000
    assert chapter["UsrDeductUndChapVIA"]["Section80U"] == 40000


def test_builder_maps_complete_schedule_80e() -> None:
    """Section 80E must preserve every official lender and loan field."""
    entry = Schedule80EEntry(
        loan_taken_from=EducationLoanLenderType.BANK,
        lender_name="State Bank of India",
        account_or_reference_number="EDU/2020-123",
        loan_date=date(2020, 1, 15),
        total_loan_amount=Decimal("500000"),
        outstanding_loan_amount=Decimal("350000"),
        interest_paid=Decimal("40000"),
    )
    body = _input().model_copy(update={
        "deductions_chapter6a": Chapter6ADeductions(
            amount_80c=Decimal("100000"),
            amount_80e=Decimal("40000"),
        ),
        "schedule_80e_entries": [entry],
    })
    itr1 = _build(body)["ITR"]["ITR1"]
    assert itr1["Schedule80E"] == {
        "Schedule80EDtls": [{
            "LoanTknFrom": "B",
            "BankOrInstnName": "State Bank of India",
            "LoanAccNoOfBankOrInstnRefNo": "EDU/2020-123",
            "DateofLoan": "2020-01-15",
            "TotalLoanAmt": 500000,
            "LoanOutstndngAmt": 350000,
            "Interest80E": 40000,
        }],
        "TotalInterest80E": 40000,
    }
    chapter = itr1["ITR1_IncomeDeductions"]
    assert chapter["UsrDeductUndChapVIA"]["Section80E"] == 40000
    assert chapter["DeductUndChapVIA"]["Section80E"] == 40000


def test_builder_preserves_user_80e_when_gti_caps_eligible_interest() -> None:
    """User 80E remains raw while Schedule 80E equals GTI-eligible interest."""
    entry = Schedule80EEntry(
        loan_taken_from=EducationLoanLenderType.INSTITUTION,
        lender_name="Education Finance Institute",
        account_or_reference_number="INST-123",
        loan_date=date(2022, 6, 1),
        total_loan_amount=Decimal("200000"),
        outstanding_loan_amount=Decimal("150000"),
        interest_paid=Decimal("100000"),
    )
    body = _input(amount_80c="0", amount_80d="0").model_copy(update={
        "salary_income": SalaryIncome(gross_salary=Decimal("90000")),
        "other_sources_income": OtherSourcesIncome(),
        "deductions_chapter6a": Chapter6ADeductions(amount_80e=Decimal("100000")),
        "schedule_80e_entries": [entry],
        "agriculture_income": Decimal("0"),
    })
    itr1 = _build(body)["ITR"]["ITR1"]
    chapter = itr1["ITR1_IncomeDeductions"]
    assert chapter["UsrDeductUndChapVIA"]["Section80E"] == 100000
    assert chapter["DeductUndChapVIA"]["Section80E"] == 40000
    assert itr1["Schedule80E"]["TotalInterest80E"] == 40000


def test_builder_allocates_fractional_80e_interest_without_rounding_drift() -> None:
    """Individually rounded loan rows must sum exactly to eligible Section 80E."""
    rows = [
        Schedule80EEntry(
            loan_taken_from=EducationLoanLenderType.BANK,
            lender_name=f"Bank {index}",
            account_or_reference_number=f"LOAN-{index}",
            loan_date=date(2020, 1, index),
            total_loan_amount=Decimal("100"),
            outstanding_loan_amount=Decimal("50"),
            interest_paid=Decimal("0.60"),
        )
        for index in (1, 2)
    ]
    body = _input(amount_80c="0", amount_80d="0").model_copy(update={
        "deductions_chapter6a": Chapter6ADeductions(amount_80e=Decimal("1.20")),
        "schedule_80e_entries": rows,
    })
    schedule = _build(body)["ITR"]["ITR1"]["Schedule80E"]
    assert [row["Interest80E"] for row in schedule["Schedule80EDtls"]] == [1, 0]
    assert schedule["TotalInterest80E"] == 1


def test_builder_rejects_missing_or_mismatched_schedule_80e() -> None:
    """A positive eligible 80E claim requires exactly cross-footed loan rows."""
    body = _input().model_copy(update={
        "deductions_chapter6a": Chapter6ADeductions(
            amount_80c=Decimal("100000"),
            amount_80e=Decimal("40000"),
        )
    })
    with pytest.raises(ValueError, match="requires official loan rows"):
        _build(body)
    entry = Schedule80EEntry(
        loan_taken_from=EducationLoanLenderType.BANK,
        lender_name="Bank",
        account_or_reference_number="LOAN-1",
        loan_date=date(2020, 1, 1),
        total_loan_amount=Decimal("100000"),
        outstanding_loan_amount=Decimal("50000"),
        interest_paid=Decimal("30000"),
    )
    with pytest.raises(ValueError, match="not exceed row interest"):
        _build(body.model_copy(update={"schedule_80e_entries": [entry]}))


def _deduction_loan_row(
    section: str,
    *,
    interest: str = "40000",
) -> ITR1Schedule80EELoanEntry | ITR1Schedule80EEALoanEntry | ITR1Schedule80EEBLoanEntry:
    """Build one complete official loan row for a deduction section."""
    common = {
        "loan_taken_from": EducationLoanLenderType.BANK,
        "lender_name": "State Bank of India",
        "account_or_reference_number": f"{section}-LOAN-1",
        "loan_date": date(2016, 4, 1) if section == "80EE" else date(2019, 4, 1),
        "total_loan_amount": Decimal("3000000"),
        "outstanding_loan_amount": Decimal("2000000"),
        "interest_paid": Decimal(interest),
    }
    if section == "80EE":
        return ITR1Schedule80EELoanEntry(**common)
    if section == "80EEA":
        return ITR1Schedule80EEALoanEntry(**common)
    return ITR1Schedule80EEBLoanEntry(
        **common,
        vehicle_registration_number="DL01EV1234",
    )


@pytest.mark.parametrize(
    ("section", "list_field", "interest_key", "total_key"),
    [
        ("80EE", "loan_details_80ee_list", "Interest80EE", "TotalInterest80EE"),
        ("80EEA", "loan_details_80eea_list", "Interest80EEA", "TotalInterest80EEA"),
        ("80EEB", "loan_details_80eeb_list", "Interest80EEB", "TotalInterest80EEB"),
    ],
)
def test_builder_maps_complete_remaining_loan_schedules(
    section: str,
    list_field: str,
    interest_key: str,
    total_key: str,
) -> None:
    """Every remaining loan schedule must preserve real official row fields."""
    row = _deduction_loan_row(section)
    deductions = Chapter6ADeductions(**{f"amount_{section.lower()}": Decimal("40000")})
    update = {
        "deductions_chapter6a": deductions,
        list_field: [row],
    }
    if section == "80EEA":
        update["property_stamp_duty_value_80eea"] = Decimal("4500000")
    body = _input(amount_80c="0", amount_80d="0").model_copy(update=update)
    itr1 = _build(body)["ITR"]["ITR1"]
    schedule = itr1[f"Schedule{section}"]
    expected_row = {
        "LoanTknFrom": "B",
        "BankOrInstnName": "State Bank of India",
        "LoanAccNoOfBankOrInstnRefNo": f"{section}-LOAN-1",
        "DateofLoan": row.loan_date.isoformat(),
        "TotalLoanAmt": 3000000,
        "LoanOutstndngAmt": 2000000,
        interest_key: 40000,
    }
    if section == "80EEB":
        expected_row["VehicleRegNo"] = "DL01EV1234"
    assert schedule[f"Schedule{section}Dtls"] == [expected_row]
    assert schedule[total_key] == 40000
    if section == "80EEA":
        assert schedule["PropStmpDtyVal"] == 4500000
    chapter = itr1["ITR1_IncomeDeductions"]
    assert chapter["UsrDeductUndChapVIA"][f"Section{section}"] == 40000
    assert chapter["DeductUndChapVIA"][f"Section{section}"] == 40000


def test_builder_allocates_gti_capped_80eeb_and_preserves_user_claim() -> None:
    """80EEB output uses eligible interest while user VIA retains raw interest."""
    row = _deduction_loan_row("80EEB", interest="100000")
    body = _input(amount_80c="0", amount_80d="0").model_copy(update={
        "salary_income": SalaryIncome(gross_salary=Decimal("90000")),
        "other_sources_income": OtherSourcesIncome(),
        "deductions_chapter6a": Chapter6ADeductions(amount_80eeb=Decimal("100000")),
        "loan_details_80eeb_list": [row],
        "agriculture_income": Decimal("0"),
    })
    itr1 = _build(body)["ITR"]["ITR1"]
    chapter = itr1["ITR1_IncomeDeductions"]
    assert chapter["UsrDeductUndChapVIA"]["Section80EEB"] == 100000
    assert chapter["DeductUndChapVIA"]["Section80EEB"] == 40000
    assert itr1["Schedule80EEB"]["TotalInterest80EEB"] == 40000


def test_builder_rejects_legacy_or_incomplete_remaining_loan_schedules() -> None:
    """Official generation must never fabricate missing lender or account fields."""
    body = _input(amount_80c="0", amount_80d="0").model_copy(update={
        "deductions_chapter6a": Chapter6ADeductions(amount_80ee=Decimal("40000")),
    })
    with pytest.raises(ValueError, match="official loan rows"):
        _build(body)


def test_builder_maps_complete_schedule_80g_and_user_eligible_amounts() -> None:
    """Schedule 80G must serialize real donee rows and computed eligibility."""
    donation = Donation80G(
        non_cash_amount=Decimal("20000"),
        qualifying_percentage="50%",
        limit_on_deduction="without limit",
        donee_name="Approved Charitable Trust",
        donee_pan="ABCDE1234F",
        approval_reference_number="AA/80G/2025",
        address=DonationAddress(
            address_line="1 Charity Road",
            city_or_district="Mumbai",
            state_code="27",
            pin_code=400001,
        ),
        ifsc_code="SBIN0000001",
        transaction_ref="TXN-80G-1",
    )
    body = _input(amount_80c="0", amount_80d="0").model_copy(update={
        "deductions_chapter6a": Chapter6ADeductions(
            amount_80g=Decimal("15000"),
            donations_80g=[donation],
        ),
    })
    itr1 = _build(body)["ITR"]["ITR1"]
    schedule = itr1["Schedule80G"]
    row = schedule["Don50PercentNoApprReqd"]["DoneeWithPan"][0]
    assert row == {
        "DoneeWithPanName": "Approved Charitable Trust",
        "DoneePAN": "ABCDE1234F",
        "ArnNbr": "AA/80G/2025",
        "AddressDetail": {
            "AddrDetail": "1 Charity Road",
            "CityOrTownOrDistrict": "Mumbai",
            "StateCode": "27",
            "PinCode": 400001,
        },
        "DonationAmtCash": 0,
        "DonationAmtOtherMode": 20000,
        "TransactionRefNum": "TXN-80G-1",
        "IFSCCode": "SBIN0000001",
        "DonationAmt": 20000,
        "EligibleDonationAmt": 10000,
    }
    assert schedule["TotalDonationsUs80G"] == 20000
    assert schedule["TotalEligibleDonationsUs80G"] == 10000
    chapter = itr1["ITR1_IncomeDeductions"]
    assert chapter["UsrDeductUndChapVIA"]["Section80G"] == 15000
    assert chapter["DeductUndChapVIA"]["Section80G"] == 10000


def test_builder_rejects_incomplete_schedule_80g_identity() -> None:
    """Official Schedule 80G generation must not invent donee details."""
    donation = Donation80G(
        non_cash_amount=Decimal("10000"),
        qualifying_percentage="100%",
        limit_on_deduction="without limit",
    )
    body = _input(amount_80c="0", amount_80d="0").model_copy(update={
        "deductions_chapter6a": Chapter6ADeductions(
            amount_80g=Decimal("10000"),
            donations_80g=[donation],
        ),
    })
    with pytest.raises(ValueError, match="donee identity and address"):
        _build(body)


def test_builder_maps_complete_schedule_80ggc() -> None:
    """Schedule 80GGC must disclose cash while allowing only supported non-cash."""
    contribution = PoliticalContribution(
        cash_amount=Decimal("2000"),
        other_mode_amount=Decimal("10000"),
        contribution_date=date(2025, 4, 1),
        transaction_ref="NEFT-80GGC-001",
        ifsc_code="SBIN0001234",
        political_party_name="National Reform Party",
        political_party_pan="ABCDE1234F",
    )
    body = _input(amount_80c="0", amount_80d="0").model_copy(update={
        "deductions_chapter6a": Chapter6ADeductions(amount_80ggc=Decimal("9000")),
        "schedule_80ggc": Schedule80GGC(contributions=[contribution]),
    })
    itr1 = _build(body)["ITR"]["ITR1"]
    schedule = itr1["Schedule80GGC"]
    assert schedule["Schedule80GGCDetails"] == [{
        "DonationDate": "2025-04-01",
        "DonationAmtCash": 2000,
        "DonationAmtOtherMode": 10000,
        "TransactionRefNum": "NEFT-80GGC-001",
        "IFSCCode": "SBIN0001234",
        "DonationAmt": 12000,
        "EligibleDonationAmt": 9000,
        "PoliticalPartyName": "National Reform Party",
        "PoliticalPartyPAN": "ABCDE1234F",
    }]
    assert schedule["TotalDonationsUs80GGC"] == 12000
    assert schedule["TotalEligibleDonationAmt80GGC"] == 9000
    chapter = itr1["ITR1_IncomeDeductions"]
    assert chapter["UsrDeductUndChapVIA"]["Section80GGC"] == 9000
    assert chapter["DeductUndChapVIA"]["Section80GGC"] == 9000


def test_builder_rejects_80ggc_party_pan_equal_to_assessee_pan() -> None:
    """Direct computation must disallow an 80GGC row using the assessee PAN."""
    contribution = PoliticalContribution(
        other_mode_amount=Decimal("10000"),
        contribution_date=date(2026, 3, 31),
        transaction_ref="NEFT-SELF-PAN",
        ifsc_code="SBIN0001234",
        political_party_name="Invalid Self Party",
        political_party_pan="ABCDE1234F",
    )
    body = _input(amount_80c="0", amount_80d="0").model_copy(update={
        "assessee_pan": "ABCDE1234F",
        "deductions_chapter6a": Chapter6ADeductions(amount_80ggc=Decimal("10000")),
        "schedule_80ggc": Schedule80GGC(contributions=[contribution]),
    })
    result = compute(body)
    details = result.schedules["deductions"].section_details["80GGC"]
    assert details.allowed_deduction == 0
    with pytest.raises(ValueError, match="positive eligible deduction"):
        build_itr1_json(result, body)


def test_builder_rejects_scalar_only_schedule_80ggc() -> None:
    """A positive 80GGC claim cannot produce fabricated contribution rows."""
    body = _input(amount_80c="0", amount_80d="0").model_copy(update={
        "deductions_chapter6a": Chapter6ADeductions(amount_80ggc=Decimal("10000")),
    })
    with pytest.raises(ValueError, match="Schedule 80GGC contribution rows"):
        _build(body)


def test_builder_maps_complete_schedule_80gga() -> None:
    """Schedule 80GGA must map official rows and computed eligible amounts."""
    donation = Donation80GGA(
        relevant_clause=Section80GGAClause.SCIENTIFIC_RESEARCH,
        donee_name="National Research Association",
        address=DonationAddress(
            address_line="10 Science Avenue",
            city_or_district="Bengaluru",
            state_code="29",
            pin_code=560001,
        ),
        donee_pan="ABCDE1234F",
        cash_amount=Decimal("2500"),
        other_mode_amount=Decimal("10000"),
    )
    body = _input(amount_80c="0", amount_80d="0").model_copy(update={
        "deductions_chapter6a": Chapter6ADeductions(amount_80gga=Decimal("12000")),
        "schedule_80gga": Schedule80GGA(donations=[donation]),
    })
    itr1 = _build(body)["ITR"]["ITR1"]
    schedule = itr1["Schedule80GGA"]
    assert schedule["DonationDtlsSciRsrchRuralDev"] == [{
        "RelevantClauseUndrDedClaimed": "80GGA2a",
        "NameOfDonee": "National Research Association",
        "AddressDetail": {
            "AddrDetail": "10 Science Avenue",
            "CityOrTownOrDistrict": "Bengaluru",
            "StateCode": "29",
            "PinCode": 560001,
        },
        "DoneePAN": "ABCDE1234F",
        "DonationAmtCash": 2500,
        "DonationAmtOtherMode": 10000,
        "DonationAmt": 12500,
        "EligibleDonationAmt": 10000,
    }]
    assert schedule["TotalDonationsUs80GGA"] == 12500
    assert schedule["TotalEligibleDonationAmt80GGA"] == 10000
    chapter = itr1["ITR1_IncomeDeductions"]
    assert chapter["UsrDeductUndChapVIA"]["Section80GGA"] == 12000
    assert chapter["DeductUndChapVIA"]["Section80GGA"] == 10000


def test_builder_allocates_fractional_80gga_rows_without_drift() -> None:
    """Official integer 80GGA rows must cross-foot after fractional inputs."""
    donations = [
        Donation80GGA(
            relevant_clause=Section80GGAClause.RURAL_DEVELOPMENT,
            donee_name=f"Rural Trust {index}",
            address=DonationAddress(
                address_line=f"{index} Rural Road",
                city_or_district="Pune",
                state_code="27",
                pin_code=411001,
            ),
            donee_pan=pan,
            other_mode_amount=Decimal("0.60"),
        )
        for index, pan in ((1, "ABCDE1234F"), (2, "WXYZA6789G"))
    ]
    body = _input(amount_80c="0", amount_80d="0").model_copy(update={
        "deductions_chapter6a": Chapter6ADeductions(amount_80gga=Decimal("1.20")),
        "schedule_80gga": Schedule80GGA(donations=donations),
    })
    rows = _build(body)["ITR"]["ITR1"]["Schedule80GGA"][
        "DonationDtlsSciRsrchRuralDev"
    ]
    assert [row["EligibleDonationAmt"] for row in rows] == [1, 0]
    assert sum(row["EligibleDonationAmt"] for row in rows) == 1


def test_builder_rejects_scalar_only_schedule_80gga() -> None:
    """A positive 80GGA claim cannot produce fabricated donation rows."""
    body = _input(amount_80c="0", amount_80d="0").model_copy(update={
        "deductions_chapter6a": Chapter6ADeductions(amount_80gga=Decimal("10000")),
    })
    with pytest.raises(ValueError, match="Schedule 80GGA donation rows"):
        _build(body)


def test_builder_maps_complete_80ddb_details_and_distinct_amounts() -> None:
    """80DDB user fields retain net expenditure while computed amount is capped."""
    body = _input().model_copy(update={
        "deductions_chapter6a": Chapter6ADeductions(
            amount_80c=Decimal("100000"),
            amount_80ddb=Decimal("80000"),
            details_80ddb=Section80DDBDetails(
                user_type=Section80DDBUserType.SELF_OR_DEPENDENT,
                disease=SpecifiedDisease80DDB.MALIGNANT_CANCERS,
                reimbursement_amount=Decimal("10000"),
            ),
        )
    })
    chapter = _build(body)["ITR"]["ITR1"]["ITR1_IncomeDeductions"]
    user = chapter["UsrDeductUndChapVIA"]
    eligible = chapter["DeductUndChapVIA"]
    assert user["Section80DDBUsrType"] == "1"
    assert user["NameOfSpecDisease80DDB"] == "i"
    assert user["Section80DDB"] == 70000
    assert user["TotalChapVIADeductions"] == 170000
    assert eligible["Section80DDB"] == 40000
    assert eligible["TotalChapVIADeductions"] == 140000
    assert "Section80DDBUsrType" not in eligible
    assert "NameOfSpecDisease80DDB" not in eligible


def test_builder_uses_treated_person_category_for_80ddb_cap() -> None:
    """A senior dependent receives the senior cap regardless of assessee age."""
    body = _input().model_copy(update={
        "deductions_chapter6a": Chapter6ADeductions(
            amount_80c=Decimal("100000"),
            amount_80ddb=Decimal("90000"),
            details_80ddb=Section80DDBDetails(
                user_type=Section80DDBUserType.SELF_OR_DEPENDENT_SENIOR,
                disease=SpecifiedDisease80DDB.PARKINSONS_DISEASE,
            ),
        )
    })
    chapter = _build(body)["ITR"]["ITR1"]["ITR1_IncomeDeductions"]
    assert chapter["UsrDeductUndChapVIA"]["Section80DDBUsrType"] == "2"
    assert chapter["DeductUndChapVIA"]["Section80DDB"] == 90000


def test_builder_rejects_80ddb_reimbursement_above_expenditure() -> None:
    """80DDB reimbursement cannot produce a negative net user claim."""
    body = _input().model_copy(update={
        "deductions_chapter6a": Chapter6ADeductions(
            amount_80c=Decimal("100000"),
            amount_80ddb=Decimal("30000"),
            details_80ddb=Section80DDBDetails(
                user_type=Section80DDBUserType.SELF_OR_DEPENDENT,
                disease=SpecifiedDisease80DDB.CHRONIC_RENAL_FAILURE,
                reimbursement_amount=Decimal("40000"),
            ),
        )
    })
    with pytest.raises(ValueError, match="reimbursement"):
        _build(body)


def test_builder_rejects_incomplete_positive_80ddb() -> None:
    """A positive 80DDB claim cannot be emitted without official details."""
    body = _input().model_copy(update={
        "deductions_chapter6a": Chapter6ADeductions(
            amount_80c=Decimal("100000"),
            amount_80ddb=Decimal("40000"),
        )
    })
    with pytest.raises(ValueError, match="80DDB"):
        _build(body)
