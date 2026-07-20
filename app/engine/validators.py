"""
Unified Validation Engine for all ITR forms.

Performs three types of validations:
  1. Field-level: type, pattern, min/max, required, enum membership
  2. Cross-field: conditional requirements (if X=Y then Z required)
  3. Arithmetic: computed totals = sum of components

Each rule maps to an ITD validation rule from the CBDT validation documents.
"""

import re
from decimal import Decimal
from enum import Enum
from dataclasses import dataclass, field
from typing import Callable, Optional, Any


class ValidationLevel(str, Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass
class ValidationResult:
    rule_id: str
    level: ValidationLevel
    schedule: str
    field: str
    message: str
    actual_value: Any = None
    expected: Any = None


@dataclass
class ValidationRule:
    rule_id: str
    level: ValidationLevel
    schedule: str
    field: str
    message: str
    condition: Callable[..., bool]


ITR1_RULES: list[ValidationRule] = []
ITR2_RULES: list[ValidationRule] = []
ITR4_RULES: list[ValidationRule] = []


ITR1_RULES.extend([
    ValidationRule("ITR1-F001", ValidationLevel.ERROR, "PartA_GEN1", "PAN",
        "PAN must match pattern [A-Z]{5}[0-9]{4}[A-Z]",
        lambda d: not bool(re.match(r"^[A-Z]{5}[0-9]{4}[A-Z]$", str(d.get("pan", ""))))),
    ValidationRule("ITR1-F002", ValidationLevel.WARNING, "PartA_GEN1", "AadhaarCardNo",
        "Aadhaar must be exactly 12 digits",
        lambda d: bool(d.get("aadhaar")) and not bool(re.match(r"^[0-9]{12}$", str(d.get("aadhaar", ""))))),
    ValidationRule("ITR1-F003", ValidationLevel.ERROR, "Schedule112A", "ltcg_112a",
        "LTCG u/s 112A cannot exceed Rs 1,25,000 for ITR-1",
        lambda d: Decimal(str(d.get("ltcg_112a", 0))) > Decimal("125000")),
    ValidationRule("ITR1-F004", ValidationLevel.ERROR, "PartB-TI", "GTI",
        "Gross Total Income exceeds Rs 50,00,000 - ITR-1 ineligible",
        lambda d: Decimal(str(d.get("gti", 0))) > Decimal("5000000")),
])


ITR1_RULES.extend([
    ValidationRule("ITR1-A001", ValidationLevel.ERROR, "ScheduleS", "GrossSalary",
        "GrossSalary must equal Salary + Perquisites + ProfitsInLieu",
        lambda d: d.get("gross_salary", 0) != (d.get("basic", 0) + d.get("perquisites", 0) + d.get("profits_in_lieu", 0))),
    ValidationRule("ITR1-A002", ValidationLevel.ERROR, "ScheduleS", "StandardDeduction",
        "Standard deduction cannot exceed Rs 75,000 (new) / Rs 50,000 (old)",
        lambda d: d.get("std_deduction", 0) > (75000 if d.get("regime") == "new" else 50000)),
    ValidationRule("ITR1-A003", ValidationLevel.ERROR, "ScheduleVIA", "80C",
        "80C + 80CCC + 80CCD(1) combined cannot exceed Rs 1,50,000",
        lambda d: (d.get("80c", 0) + d.get("80ccc", 0) + d.get("80ccd1", 0)) > 150000),
    ValidationRule("ITR1-A004", ValidationLevel.WARNING, "ScheduleVIA", "80D_Self",
        "80D self/family exceeds age-based limit",
        lambda d: d.get("80d_self", 0) > (50000 if d.get("is_senior") else 25000)),
    ValidationRule("ITR1-A005", ValidationLevel.WARNING, "ScheduleVIA", "80TTA",
        "80TTA deduction exceeds Rs 10,000 limit",
        lambda d: not d.get("is_senior") and d.get("80tta", 0) > 10000),
    ValidationRule("ITR1-A006", ValidationLevel.ERROR, "PartB-TI", "GTI_Arithmetic",
        "GTI does not match sum of income heads",
        lambda d: d.get("gti", 0) != (d.get("salary", 0) + d.get("hp", 0) + d.get("os", 0) + d.get("cg_112a", 0))),
    ValidationRule("ITR1-A007", ValidationLevel.ERROR, "PartB-TI", "TI_Arithmetic",
        "Taxable Income should equal GTI minus Chapter VI-A deductions (rounded to nearest 10)",
        lambda d: abs((d.get("ti", 0) // 10 * 10) - max(0, d.get("gti", 0) - d.get("deductions", 0)) // 10 * 10) > 10),
])


ITR1_RULES.extend([
    ValidationRule("ITR1-C001", ValidationLevel.WARNING, "ScheduleS", "EntertainmentAllowance",
        "Entertainment allowance u/s 16(ii) is only for government employees",
        lambda d: d.get("entertainment_allowance", 0) > 0 and not d.get("is_govt_employee", False)),
    ValidationRule("ITR1-C002", ValidationLevel.WARNING, "ScheduleVIA", "ChVIA_NewRegime",
        "Most Chapter VI-A deductions are not allowed under new regime",
        lambda d: d.get("regime") == "new" and (d.get("80c", 0) > 0 or d.get("80d_self", 0) > 0 or d.get("80tta", 0) > 0)),
    ValidationRule("ITR1-C003", ValidationLevel.ERROR, "PartA_GEN1", "ReceiptNo",
        "Revised return must provide original receipt number",
        lambda d: d.get("filing_section") == 17 and not d.get("receipt_no", "")),
])


ITR2_RULES.extend([
    ValidationRule("ITR2-A001", ValidationLevel.ERROR, "ScheduleCGFor23", "TotalSTCG",
        "TotalSTCG must equal sum of 111A + 20% + 30% + AppRate + DTAA",
        lambda d: abs(d.get("total_stcg", 0) - (
            d.get("stcg_111a", 0) + d.get("stcg_20per", 0) + d.get("stcg_30per", 0)
            + d.get("stcg_app_rate", 0) + d.get("stcg_dtaa", 0))) > 1),
    ValidationRule("ITR2-A002", ValidationLevel.ERROR, "ScheduleCGFor23", "TotalLTCG",
        "TotalLTCG must equal sum of 112A + 12.5% + DTAA",
        lambda d: abs(d.get("total_ltcg", 0) - (
            d.get("ltcg_112a_taxable", 0) + d.get("ltcg_125per", 0) + d.get("ltcg_dtaa", 0))) > 1),
    ValidationRule("ITR2-C001", ValidationLevel.INFO, "ScheduleVIA", "80GGA",
        "80GGA/80GGC claimed -- verify no business income (ITR-2 is for non-business)",
        lambda d: d.get("80gga", 0) > 0 or d.get("80ggc", 0) > 0),
    ValidationRule("ITR2-A003", ValidationLevel.ERROR, "ScheduleVDA", "IncomeFromVDA",
        "VDA income = Consideration - Cost; no other deductions allowed (Sec 115BBH)",
        lambda d: d.get("vda_income", 0) != max(0, d.get("vda_consideration", 0) - d.get("vda_cost", 0))),
])


ITR4_RULES.extend([
    ValidationRule("ITR4-F001", ValidationLevel.ERROR, "ScheduleBP", "44AD_Turnover",
        "44AD turnover cannot exceed Rs 3 crore",
        lambda d: d.get("turnover", 0) > 30000000),
    ValidationRule("ITR4-F002", ValidationLevel.ERROR, "ScheduleBP", "44ADA_Receipts",
        "44ADA gross receipts cannot exceed Rs 75 lakh",
        lambda d: d.get("gross_receipts", 0) > 7500000),
    ValidationRule("ITR4-F003", ValidationLevel.ERROR, "ScheduleBP", "44AE_Vehicles",
        "44AE: Cannot own more than 10 goods carriages at any time",
        lambda d: d.get("vehicle_count", 0) > 10),
    ValidationRule("ITR4-A001", ValidationLevel.WARNING, "ScheduleBP", "44AD_CashRate",
        "Cash receipts > 5% of turnover - 8% rate applies instead of 6% on cash portion",
        lambda d: d.get("total_turnover", 0) > 0 and d.get("cash_turnover", 0) / max(d.get("total_turnover", 0), 1) > 0.05),
    ValidationRule("ITR4-A002", ValidationLevel.ERROR, "ScheduleBP", "44AD_Rate",
        "44AD income must be >= max(6% digital + 8% cash, declared income)",
        lambda d: d.get("presumptive_income", 0) < max(
            d.get("digital_turnover", 0) * 0.06 + d.get("cash_turnover", 0) * 0.08,
            d.get("declared_income", 0))),
])

RULES_BY_ITR = {
    "ITR1": ITR1_RULES,
    "ITR2": ITR2_RULES,
    "ITR4": ITR4_RULES,
}


def validate(data: dict, itr_type: str) -> list[ValidationResult]:
    rules = RULES_BY_ITR.get(itr_type.upper(), [])
    results = []
    for rule in rules:
        try:
            if rule.condition(data):
                results.append(ValidationResult(
                    rule_id=rule.rule_id,
                    level=rule.level,
                    schedule=rule.schedule,
                    field=rule.field,
                    message=rule.message,
                ))
        except Exception as exc:
            results.append(ValidationResult(
                rule_id=rule.rule_id,
                level=ValidationLevel.ERROR,
                schedule=rule.schedule,
                field=rule.field,
                message=f"Validation rule failed: {exc}",
            ))
    return results


def validate_field_required(data: dict, field: str, field_name: str, itr_type: str) -> Optional[ValidationResult]:
    if field not in data or data[field] is None or data[field] == "":
        return ValidationResult(
            rule_id=f"{itr_type}-R001",
            level=ValidationLevel.ERROR,
            schedule="PartA_GEN1",
            field=field,
            message=f"{field_name} is required",
        )
    return None


def validate_pattern(data: dict, field: str, pattern: str, field_name: str, rule_id: str) -> Optional[ValidationResult]:
    val = str(data.get(field, ""))
    if val and not re.match(pattern, val):
        return ValidationResult(
            rule_id=rule_id,
            level=ValidationLevel.ERROR,
            schedule="",
            field=field,
            message=f"{field_name} does not match required pattern {pattern}",
            actual_value=val,
        )
    return None


def validate_range(data: dict, field: str, min_val: Decimal, max_val: Decimal,
                   field_name: str, rule_id: str) -> Optional[ValidationResult]:
    val = Decimal(str(data.get(field, 0)))
    if val < min_val or val > max_val:
        return ValidationResult(
            rule_id=rule_id,
            level=ValidationLevel.ERROR,
            schedule="",
            field=field,
            message=f"{field_name} ({val}) is outside allowed range [{min_val}, {max_val}]",
            actual_value=val,
            expected=f"{min_val}-{max_val}",
        )
    return None
