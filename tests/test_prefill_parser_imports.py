"""Regression tests for real ITD Prefill extraction shapes."""

from __future__ import annotations

from app.engine.importers.prefill_parser import parse_prefill_json


def test_salary_tds_rows_create_employers_when_salary_schedule_is_missing() -> None:
    """Form 24Q salary TDS must populate employers without salaries.salary[]."""
    payload = {
        "personalInfo": {"pan": "ABCDE1234F"},
        "form24q": {"intrstFrmSavingBank": 1000},
        "form26as": {},
        "lastFiledITR": {},
        "tdsOnSalaries": {
            "tdsOnSalary": [
                {
                    "employerOrDeductorOrCollectDetl": {
                        "employerOrDeductorOrCollecterName": "ACME PRIVATE LIMITED",
                        "tan": "ABCD12345E",
                    },
                    "incChrgSal": 900000,
                    "totalTDSSal": 90000,
                }
            ]
        },
    }

    result = parse_prefill_json(payload, assessment_year="2026-27")

    assert len(result.employer_entries) == 1
    assert result.employer_entries[0].employer_name == "ACME PRIVATE LIMITED"
    assert result.employer_entries[0].tan == "ABCD12345E"
    assert result.employer_entries[0].salary == 900000
    assert result.employer_entries[0].tds_deducted_from_salary == 90000
    assert len(result.tds_salary_entries) == 1
    assert result.tds_salary_entries[0].section == "192"
    assert result.tds_salary_entries[0].tds_deducted == 90000
    assert result.other_sources.interest_from_savings_bank == 1000


def test_last_filed_itr_natofemployment_does_not_create_employer_stubs() -> None:
    """lastFiledITR.natOfEmployment must NOT create phantom employer rows.

    A salaried-last-year taxpayer who has since become a professional
    (44ADA business) still carries ``lastFiledITR.natOfEmployment``
    like ``["OTH","OTH"]`` in the ITD Prefill JSON.  Those codes are
    historical — there is no current-AY salary to import.  Creating
    empty-stub employer rows used to surface in the frontend as a
    single "Employer from Prefill" placeholder with every salary field
    at ₹0 (because ``mergeDraft`` collapsed both empty stubs into one
    ``id: 'employer-UNKNOWN'`` card).  This regression test pins the
    corrected behaviour: zero employer rows when no salary data is
    present in the ITD Prefill.
    """
    payload = {
        "personalInfo": {"pan": "ACUPG3482G"},
        "form24q": {},
        "form26as": {
            "tdsOnOthThanSals": {
                "tdSonOthThanSal": [
                    {
                        "sectionCode": "94A",
                        "grossAmount": 60000,
                        "headOfIncome": "OS",
                        "employerOrDeductorOrCollectDetl": {
                            "tan": "NGPA14339D",
                            "employerOrDeductorOrCollecterName": "ANAND PURUSHOTTAM AGRAWAL",
                        },
                    },
                ],
            },
        },
        "lastFiledITR": {
            "natOfEmployment": ["OTH", "OTH"],
            "natOfBus44ADA": [{"codeADA": "16001", "nameOfBusiness": "ADV. SUNIT GOYANKA"}],
        },
        "tdsOnSalaries": {},
    }

    result = parse_prefill_json(payload, assessment_year="2026-27")

    assert result.employer_entries == [], (
        f"Expected no employer rows from lastFiledITR.natOfEmployment alone, "
        f"got {result.employer_entries!r}"
    )
    # Sanity: TDS-other rows must still produce bank-interest entries
    # (the 94A sections are interest, not salary).
    assert result.tds_other_entries and result.tds_other_entries[0].section == "94A"
