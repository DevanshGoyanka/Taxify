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
