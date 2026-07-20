"""
Schedule TDS1: TDS on Salary (Form 16).

TDS deducted by employer(s) on salary payments. Each employer issues
Form 16 with breakdown of salary, deductions, and TDS.

Key fields (matching ITD JSON schema):
  - Employer PAN / TAN
  - Employer Name
  - Income chargeable under head "Salaries"
  - Total TDS deducted

Multiple employers can exist (job change during the year).
"""

from decimal import Decimal
from typing import Optional
from dataclasses import dataclass, field
from app.schemas.itr1 import SalaryIncome, TaxRegime


@dataclass
class TdsSalaryEntry:
    employer_tan: str = ""
    employer_name: str = ""
    income_chargeable: Decimal = Decimal("0")
    tds_deducted: Decimal = Decimal("0")


@dataclass
class TdsSalaryResult:
    entries: list = field(default_factory=list)
    total_income_chargeable: Decimal = Decimal("0")
    total_tds: Decimal = Decimal("0")


def compute(
    salary_input: Optional[SalaryIncome],
    regime: TaxRegime,
    tds_entries: Optional[list[TdsSalaryEntry]] = None,
) -> TdsSalaryResult:
    """Aggregate TDS on salary from one or more employers.

    If tds_entries is None, uses salary_input directly as a single entry.
    """
    if not salary_input:
        return TdsSalaryResult()

    if tds_entries:
        total_income = sum(e.income_chargeable for e in tds_entries)
        total_tds = sum(e.tds_deducted for e in tds_entries)
        return TdsSalaryResult(
            entries=tds_entries,
            total_income_chargeable=total_income,
            total_tds=total_tds,
        )

    gross = salary_input.gross_salary
    return TdsSalaryResult(
        entries=[TdsSalaryEntry(income_chargeable=gross, tds_deducted=Decimal("0"))],
        total_income_chargeable=gross,
        total_tds=Decimal("0"),
    )
