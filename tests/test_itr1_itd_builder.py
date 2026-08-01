"""Official-schema and detail-preservation tests for the ITR-1 JSON builder."""

import json
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from jsonschema import Draft4Validator

from app.engine.calculators.itr1 import compute
from app.engine.itd.itr1 import build_itr1_json
from app.schemas.itr1 import (
    AgeBracket,
    BankAccount,
    Chapter6ADeductions,
    HousePropertyIncome,
    ITR1Input,
    OtherSourcesIncome,
    PropertyType,
    SalaryIncome,
    Schedule80CEntry,
    TDS1Entry,
    TDS2Entry,
    TCSEntry,
    TaxPaymentDetail,
    TaxRegime,
)

_SCHEMA_PATH = (
    Path(__file__).resolve().parents[1]
    / "ITD OFFICAL REFERENCE DOCS"
    / "AY 2026-27 Offical Schema JSON"
    / "ITR-1_2026_Main_V1.1 (1).json"
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
        agriculture_income=Decimal("5000"),
        nature_of_employment="Private",
    )


def _build(body: ITR1Input) -> dict:
    """Compute and build an ITR-1 document with deterministic source data."""
    result = compute(body)
    assert result.errors == []
    return build_itr1_json(result, body)


def test_detailed_document_matches_official_ay_2026_27_schema() -> None:
    """A generated detailed return must satisfy the official Draft-4 schema."""
    schema = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8-sig"))
    errors = list(Draft4Validator(schema).iter_errors(_build(_input())))

    assert errors == [], [
        f"{'/'.join(map(str, error.absolute_path))}: {error.message}"
        for error in errors
    ]


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
