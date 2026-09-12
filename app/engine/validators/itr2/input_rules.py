"""ITR-2 pre-computation validation rules.

The rules in this module validate facts that must be internally consistent before
an ITR-2 computation is attempted.  They intentionally validate only fields
represented by :class:`app.schemas.itr2.ITR2Input`.
"""

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal
from typing import Any

from app.engine.validators.base import Severity, ValidationResult
from app.schemas.itr1 import PropertyType, TaxRegime
from app.schemas.itr2 import AssesseeStatus, CGAssetType, ITR2Input, ResidentialStatus, ReturnFileSection

_ZERO = Decimal("0")
_AY_PATTERN = re.compile(r"^(\d{4})-(\d{2})$")
_ALLOWED_LOSS_HEADS = {
    "HP": 8,
    "STCG": 8,
    "LTCG": 8,
    "NONSPECULATIVE": 8,
    "SPECULATIVE": 4,
}


def _result(
    rule_id: str,
    passed: bool,
    message: str,
    field_path: str,
    expected: Any = None,
    actual: Any = None,
    severity: Severity = Severity.A,
) -> ValidationResult:
    """Build a validation result with the ITR-2 conventions."""
    return ValidationResult(
        rule_id=rule_id,
        severity=severity,
        passed=passed,
        message=message,
        field_path=field_path,
        expected=expected,
        actual=actual,
    )


def _current_assessment_year(inp: ITR2Input) -> int:
    """Return the first year of the assessment year applicable to the input."""
    reference = inp.due_date or inp.filing_date
    return reference.year if reference is not None else 2026


def _parse_assessment_year(value: str) -> int | None:
    """Parse and validate an assessment-year label, returning its first year."""
    match = _AY_PATTERN.fullmatch(value.strip())
    if match is None:
        return None
    first = int(match.group(1))
    second = int(match.group(2))
    return first if second == (first + 1) % 100 else None


def _financial_year_end(inp: ITR2Input) -> date:
    """Return 31 March of the financial year the return is filed for.

    AY 2026-27's financial year (2025-26) ends 31 March 2026; ``due_date``/
    ``filing_date`` fall within the AY (e.g. July 2026), so their calendar
    year — the same value ``_current_assessment_year`` derives — is the FY's
    closing year.
    """
    return date(_current_assessment_year(inp), 3, 31)


def validate_itr2_input(inp: ITR2Input) -> list[ValidationResult]:
    """Validate all supported ITR-2 input-level rules.

    Args:
        inp: Fully parsed ITR-2 input model.

    Returns:
        A list containing only actionable failures or warnings.  An empty list
        means that all represented pre-computation invariants passed.
    """
    results: list[ValidationResult] = []

    # Official rules 20/21 and 9 from the 1-100 audit window.
    if inp.filing_section == ReturnFileSection.ON_TIME_139_1 and inp.tax_regime == TaxRegime.OLD:
        if inp.filing_date is not None and inp.due_date is not None and inp.filing_date > inp.due_date:
            results.append(_result(
                "ITR2-IN-REGIME-001", False,
                "The old tax regime cannot be selected after the due date for a section 139(1) return.",
                "tax_regime", "new after due date", inp.tax_regime.value,
            ))

    if inp.filing_profile is not None:
        profile = inp.filing_profile
        if profile.is_fii_fpi and profile.residential_status in {
            ResidentialStatus.RESIDENT, ResidentialStatus.NOT_ORDINARILY_RESIDENT,
        }:
            results.append(_result(
                "ITR2-IN-PROFILE-002", False,
                "Residents and not ordinarily resident taxpayers cannot be FII/FPIs.",
                "filing_profile.is_fii_fpi", False, str(profile.is_fii_fpi),
            ))
        if profile.seventh_proviso_139 and not any((
            profile.foreign_travel_expenditure > _ZERO,
            profile.electricity_expenditure > _ZERO,
            profile.current_account_deposits > _ZERO,
        )):
            results.append(_result(
                "ITR2-IN-PROFILE-003", False,
                "Seventh-proviso filing requires at least one corresponding amount detail.",
                "filing_profile", "one seventh-proviso amount > 0", "all amounts are zero",
            ))

    # ── Schedule S (Salary) — Phase 5A ─────────────────────────────────────
    # Checks pass-through exemption claims the engine does NOT itself cap or
    # compute from a statutory formula (leave-encashment/VRS/commuted-pension
    # exemptions are all engine-computed from gross-received amounts with
    # their own statutory ceiling — see app/engine/schedules/salary.py — so
    # there is no user-suppliable "exempt amount" for those that could
    # violate a cap; re-validating them here would be redundant). Gratuity
    # and retrenchment compensation are genuine exceptions (Phase 6c,
    # 2026-09-11): salary.py's own _exempt_gratuity()/is_cg_sg_employee flag
    # has no pensioner granularity, so it cannot enforce the CBDT rule's real
    # 4-category ₹20L/₹25L split, and retrenchment compensation has no
    # eligibility gate in the calculator at all — both need a pre-compute
    # validator instead, sourced from employer_filing_details[].
    # nature_of_employment (the only field carrying the CBDT 8-way category),
    # since gratuity_received/retrenchment_compensation are single scalars
    # not attributed to one employer -- the "any employer matches" reading
    # mirrors the already-shipped ITR2-IN-VIA-010 (80CCH central-employment
    # check)'s handling of the identical structural mismatch. HRA's own
    # ceiling is NOT re-checked here as a genuine gap (the prior version of
    # this comment claimed "SalaryIncome has no Basic/DA breakout" -- stale:
    # EmployerFilingDetail.salary_for_hra/actual_hra_received/actual_rent_paid/
    # is_metro_city carry exactly that breakout, populated by
    # filing_gateway_v2.py::_itr2_employer_filing_details from the frontend's
    # own Basic/DA employer fields, and app/engine/itd/itr2.py's own Schedule
    # 10(13A) builder (~line 706) already hard-`raise`s on a mismatch against
    # the identical three-way min() formula) -- ITR2-IN-SAL-015 below exists
    # only to surface that same reconciliation as a friendly pre-compute
    # message instead of a raw builder exception, not to add new coverage.
    sal = inp.salary_income
    if sal is not None:
        gross_salary_total = sal.gross_salary + sal.perquisites_value + sal.profits_in_lieu_of_salary
        if inp.tax_regime == TaxRegime.OLD:
            net_salary = max(_ZERO, gross_salary_total - sal.hra_exempt_amount - sal.lta_exempt_amount)
            allowed_standard = min(Decimal("50000"), net_salary)
            if sal.standard_deduction_claimed > allowed_standard:
                results.append(_result(
                    "ITR2-IN-SAL-009", False,
                    "Old-regime standard deduction cannot exceed ₹50,000 or net salary, whichever is lower.",
                    "salary_income.standard_deduction_claimed", str(allowed_standard),
                    str(sal.standard_deduction_claimed),
                ))
        if sal.professional_tax_paid > Decimal("2500"):
            results.append(_result(
                "ITR2-IN-SAL-010", False,
                "Professional tax deduction cannot exceed ₹2,500.",
                "salary_income.professional_tax_paid", "<= 2500", str(sal.professional_tax_paid),
            ))
        if sal.lta_exempt_amount > sal.lta_amount_received:
            results.append(_result(
                "ITR2-IN-SAL-001", False,
                "LTA claimed exempt cannot exceed LTA amount received.",
                "salary_income.lta_exempt_amount",
                f"<= {sal.lta_amount_received}", str(sal.lta_exempt_amount),
            ))
        if sal.sec10_6_embassy_exempt > gross_salary_total:
            results.append(_result(
                "ITR2-IN-SAL-002", False,
                "Sec 10(6) embassy/high-commission exempt allowance cannot exceed gross salary.",
                "salary_income.sec10_6_embassy_exempt",
                f"<= {gross_salary_total}", str(sal.sec10_6_embassy_exempt),
            ))
        if sal.sec10_7_foreign_allowance > gross_salary_total:
            results.append(_result(
                "ITR2-IN-SAL-003", False,
                "Sec 10(7) foreign-service allowance cannot exceed gross salary.",
                "salary_income.sec10_7_foreign_allowance",
                f"<= {gross_salary_total}", str(sal.sec10_7_foreign_allowance),
            ))
        if sal.sec10_10cc_perquisite_tax > sal.perquisites_value:
            results.append(_result(
                "ITR2-IN-SAL-004", False,
                "Sec 10(10CC) employer-paid tax on perquisite cannot exceed the value of perquisites.",
                "salary_income.sec10_10cc_perquisite_tax",
                f"<= {sal.perquisites_value}", str(sal.sec10_10cc_perquisite_tax),
            ))
        if not sal.is_government_employee and sal.entertainment_allowance > _ZERO:
            results.append(_result(
                "ITR2-IN-SAL-005", False,
                "Entertainment allowance deduction u/s 16(ii) is allowed only for government employees.",
                "salary_income.entertainment_allowance", _ZERO, str(sal.entertainment_allowance),
            ))
        if inp.tax_regime == TaxRegime.NEW:
            if sal.hra_exempt_amount > _ZERO or sal.lta_exempt_amount > _ZERO:
                results.append(_result(
                    "ITR2-IN-SAL-006", False,
                    "HRA and LTA exemptions cannot be claimed under the new tax regime.",
                    "salary_income", "hra_exempt_amount == 0 and lta_exempt_amount == 0",
                    f"hra={sal.hra_exempt_amount}, lta={sal.lta_exempt_amount}",
                ))
            if sal.entertainment_allowance > _ZERO:
                results.append(_result(
                    "ITR2-IN-SAL-007", False,
                    "Entertainment allowance u/s 16(ii) cannot be claimed under the new tax regime.",
                    "salary_income.entertainment_allowance", _ZERO, str(sal.entertainment_allowance),
                ))
            if sal.professional_tax_paid > _ZERO:
                results.append(_result(
                    "ITR2-IN-SAL-008", False,
                    "Professional tax u/s 16(iii) cannot be claimed under the new tax regime.",
                    "salary_income.professional_tax_paid", _ZERO, str(sal.professional_tax_paid),
                ))

        # CBDT rule 28: gratuity exemption u/s 10(10) is capped at ₹25,00,000
        # for Central/State Government employees and CG/SG-Pensioners
        # (CGOV/SGOV/PE/PESG), ₹20,00,000 for everyone else (PSU/PSU-Pensioners/
        # Others-Pensioners/Others) -- see this section's own comment above for
        # why employer_filing_details, not is_cg_sg_employee, is the source.
        if sal.gratuity_received > _ZERO and inp.employer_filing_details:
            _gratuity_25l_categories = {"CGOV", "SGOV", "PE", "PESG"}
            if any(d.nature_of_employment in _gratuity_25l_categories for d in inp.employer_filing_details):
                if sal.gratuity_received > Decimal("2500000"):
                    results.append(_result(
                        "ITR2-IN-SAL-011", False,
                        "Gratuity exemption u/s 10(10) cannot exceed ₹25,00,000 for Central/"
                        "State Government employees or CG/SG-Pensioners.",
                        "salary_income.gratuity_received", "<= 2500000", str(sal.gratuity_received),
                    ))
            elif sal.gratuity_received > Decimal("2000000"):
                results.append(_result(
                    "ITR2-IN-SAL-012", False,
                    "Gratuity exemption u/s 10(10) cannot exceed ₹20,00,000 for PSU, "
                    "PSU-Pensioners, Others-Pensioners, or Others employment categories.",
                    "salary_income.gratuity_received", "<= 2000000", str(sal.gratuity_received),
                ))

        # CBDT rules #38/#39: gratuity/commuted-pension exemption u/s 17(1)
        # is not allowed against more than one employer. gratuity_received/
        # commuted_pension_received above are return-wide scalars (summed
        # across employers for the calculator/JSON, which genuinely only
        # need the aggregate -- confirmed against the official schema's own
        # single schedule-level AllwncExemptUs10 block, Phase 6i-3), so the
        # per-employer attribution needed here instead comes from
        # EmployerFilingDetail.gratuity_received/commuted_pension_received
        # (populated by filing_gateway_v2.py::_itr2_employer_filing_details
        # from the frontend's own per-employer Employer.gratuity/
        # commutedPension fields, which were already captured end-to-end
        # and simply never reached this validator). Gating on the AMOUNT
        # (two or more employers each nonzero), not merely on employer
        # count, is what resolves the false-positive worry an earlier pass
        # raised for this exact rule ("a naive multi-employer gate would
        # false-positive on a mid-year job change") -- an ordinary job
        # change has gratuity on at most one employer row, since gratuity
        # requires 5+ years' service and a same-year new hire can never
        # qualify.
        gratuity_claimants = [d for d in inp.employer_filing_details if d.gratuity_received > _ZERO]
        if len(gratuity_claimants) > 1:
            results.append(_result(
                "ITR2-IN-SAL-016", False,
                "Gratuity exemption u/s 17(1) cannot be claimed against more than one employer.",
                "employer_filing_details[].gratuity_received", "<= 1 employer",
                f"{len(gratuity_claimants)} employers",
            ))
        pension_claimants = [d for d in inp.employer_filing_details if d.commuted_pension_received > _ZERO]
        if len(pension_claimants) > 1:
            results.append(_result(
                "ITR2-IN-SAL-017", False,
                "Commuted pension exemption u/s 17(1) cannot be claimed against more than one employer.",
                "employer_filing_details[].commuted_pension_received", "<= 1 employer",
                f"{len(pension_claimants)} employers",
            ))

        # CBDT rule 62: Section 10(10B) retrenchment-compensation exemption is
        # not available to Central/State Government employees or any pensioner
        # category -- it is reserved for industrial workers covered by the
        # Industrial Disputes Act. Uses the fuller 6-category list ITR-1/ITR-4's
        # own already-shipped validators apply (CGOV/SGOV/PE/PESG/PEPS/PEO), not
        # ITR-2's own official rule text's narrower 4-category wording
        # (CGOV/SGOV/PE/PESG only) -- Section 10(10B) is one Income Tax Act
        # provision, not form-specific, and ITR-1's rule #185 and ITR-4's rule
        # #223 both independently state all six categories, so the narrower
        # ITR-2 rule text is treated as an incomplete transcription rather than
        # a deliberately different rule for this one form.
        if sal.retrenchment_compensation > _ZERO and inp.employer_filing_details:
            _retrenchment_ineligible_categories = {"CGOV", "SGOV", "PE", "PESG", "PEPS", "PEO"}
            if any(d.nature_of_employment in _retrenchment_ineligible_categories for d in inp.employer_filing_details):
                results.append(_result(
                    "ITR2-IN-SAL-013", False,
                    "Section 10(10B) retrenchment-compensation exemption is not available to "
                    "Government employees or pensioners; it is limited to industrial workers "
                    "covered by the Industrial Disputes Act.",
                    "salary_income.retrenchment_compensation", "0 for CG/SG/pensioner employment",
                    str(sal.retrenchment_compensation),
                ))

        # CBDT rule 47: only one of Section 10(10B) (retrenchment compensation)
        # or Section 10(10C) (VRS compensation) can be claimed. ITR2Input has
        # one scalar field per section (not a per-row dropdown), so this
        # collapses to "not both nonzero" -- matching ITR-1's ITR1-R123-style
        # and ITR-4's already-shipped R214/R223 mutual-exclusion checks.
        if sal.retrenchment_compensation > _ZERO and sal.vrs_compensation > _ZERO:
            results.append(_result(
                "ITR2-IN-SAL-014", False,
                "Only one of Section 10(10B) retrenchment compensation or Section 10(10C) "
                "VRS compensation can be claimed, not both.",
                "salary_income", "retrenchment_compensation == 0 or vrs_compensation == 0",
                f"retrenchment={sal.retrenchment_compensation}, vrs={sal.vrs_compensation}",
            ))

        # CBDT rules 29/602-606: HRA exemption u/s 10(13A) must equal the least
        # of (a) actual HRA received, (b) actual rent paid less 10% of Basic+DA,
        # and (c) 50%/40% of Basic+DA (metro/non-metro), aggregated across all
        # employers. app/engine/itd/itr2.py's own Schedule 10(13A) builder
        # already enforces this exact reconciliation and raises ValueError on
        # mismatch (~line 706) -- this validator exists only to surface the
        # identical check earlier as a clean pre-compute message. Metro status
        # is taken from the first employer, matching the builder's own
        # `is_metro = section13a_details[0].is_metro_city` (which is itself
        # only reachable because the builder separately rejects mixed
        # metro/non-metro employers).
        if inp.tax_regime == TaxRegime.OLD and sal.hra_exempt_amount > _ZERO and inp.employer_filing_details:
            _hra_received_total = sum((d.actual_hra_received for d in inp.employer_filing_details), _ZERO)
            _rent_paid_total = sum((d.actual_rent_paid for d in inp.employer_filing_details), _ZERO)
            _basic_da_total = sum((d.salary_for_hra for d in inp.employer_filing_details), _ZERO)
            _is_metro = inp.employer_filing_details[0].is_metro_city
            _rent_minus_ten_pct = max(_ZERO, _rent_paid_total - _basic_da_total * Decimal("0.1"))
            _basic_da_rate = _basic_da_total * (Decimal("0.5") if _is_metro else Decimal("0.4"))
            _allowed_hra = min(_hra_received_total, _rent_minus_ten_pct, _basic_da_rate)
            if sal.hra_exempt_amount != _allowed_hra:
                results.append(_result(
                    "ITR2-IN-SAL-015", False,
                    "HRA exemption u/s 10(13A) must equal the least of actual HRA received, "
                    "rent paid less 10% of Basic+DA, and 40%/50% of Basic+DA.",
                    "salary_income.hra_exempt_amount", str(_allowed_hra), str(sal.hra_exempt_amount),
                ))

        # CBDT rule 31: Schedule S's own "Total amount of exempt allowances
        # u/s 10 (other than HRA)" cannot exceed gross salary less HRA --
        # every non-HRA Section 10 exempt-allowance field on this schema
        # summed together.
        _non_hra_exempt_total = (
            sal.lta_exempt_amount + sal.sec10_6_embassy_exempt + sal.sec10_7_foreign_allowance
            + sal.sec10_10cc_perquisite_tax + sal.sec10_14i_prescribed_allowance
            + sal.sec10_14ii_personal_allowance + sal.other_section10_exempt
        )
        _non_hra_ceiling = max(_ZERO, gross_salary_total - sal.hra_exempt_amount)
        if _non_hra_exempt_total > _non_hra_ceiling:
            results.append(_result(
                "ITR2-IN-SAL-018", False,
                "Total exempt allowances u/s 10 (other than HRA) cannot exceed gross salary "
                "less HRA.",
                "salary_income", f"<= {_non_hra_ceiling}", str(_non_hra_exempt_total),
            ))

        # CBDT rule 44: Section 10(10A) commuted-pension exemption is a
        # fraction of the amount actually received (schedules/salary.py's own
        # _exempt_commutted_pension() formula structurally cannot exceed
        # `received` itself) -- but `received` is itself a component of
        # gross salary u/s 17(1), so a `received` figure exceeding the
        # return's own total salary is a genuine data-entry inconsistency
        # this rule catches, not a formula gap.
        if sal.commuted_pension_received > gross_salary_total:
            results.append(_result(
                "ITR2-IN-SAL-019", False,
                "Commuted pension received cannot exceed total salary u/s 17(1).",
                "salary_income.commuted_pension_received", f"<= {gross_salary_total}",
                str(sal.commuted_pension_received),
            ))

        # CBDT rules 49/50: the generic "Section 10(14)(i)/(ii) allowance not
        # otherwise entered" claim (`other_section10_exempt` -- see this
        # section's own comment above distinguishing it from the CEA/hostel-
        # specific `sec10_14i_prescribed_allowance`/`sec10_14ii_personal_allowance`
        # fields, which already carry their own fixed-rate statutory caps)
        # cannot exceed the gross "Other Allowances"/"Other Taxable Salary"
        # received under section 17(1) (`other_allowances_received`, newly
        # added -- previously this schema had no field to check against at
        # all, per this row's own prior "genuine gap" evidence). The official
        # schema does not split this single claim field into a (i)-vs-(ii)
        # sub-breakdown, so one check honestly covers both CBDT rule numbers.
        if sal.other_section10_exempt > sal.other_allowances_received:
            results.append(_result(
                "ITR2-IN-SAL-020", False,
                "Section 10(14)(i)/(ii) allowance exemption cannot exceed the gross "
                "\"Other Allowances\" salary component u/s 17(1) (CBDT rules #49/#50).",
                "salary_income.other_section10_exempt", f"<= {sal.other_allowances_received}",
                str(sal.other_section10_exempt),
            ))

        # CBDT rule 52: Section 80GG (rent paid, no HRA) is capped at ₹5,000/
        # month (₹60,000/year) by its own statutory formula regardless, but
        # the official rule specifically flags ₹55,000 as the ceiling when
        # HRA u/s 10(13A) is simultaneously claimed -- implemented literally
        # per the rule's own text, matching this project's established
        # practice for CBDT rules with an unusual/narrower-than-expected
        # numeric threshold (do not "correct" it to 60000 without re-checking
        # the primary PDF first).
        if sal.hra_exempt_amount > _ZERO and inp.deductions_chapter6a is not None:
            _amount_80gg = inp.deductions_chapter6a.amount_80gg
            if _amount_80gg > Decimal("55000"):
                results.append(_result(
                    "ITR2-IN-SAL-021", False,
                    "Deduction u/s 80GG cannot exceed ₹55,000 when HRA exemption u/s "
                    "10(13A) is also claimed.",
                    "deductions_chapter6a.amount_80gg", "<= 55000", str(_amount_80gg),
                ))

        # CBDT rules 63/64: the same dropdown "nature of perquisite"/"nature
        # of profit in lieu of salary" code cannot be selected more than once
        # per employer block (official NatureOfPerquisites/
        # NatureOfProfitInLieuOfSalary row lists).
        for _detail in inp.employer_filing_details:
            _perq_codes = [row.get("NatureDesc") for row in _detail.nature_of_perquisites_rows]
            _perq_dupes = {c for c in _perq_codes if c and _perq_codes.count(c) > 1}
            if _perq_dupes:
                results.append(_result(
                    "ITR2-IN-SAL-022", False,
                    "The same nature-of-perquisite code cannot be selected more than once "
                    "per employer.",
                    "employer_filing_details[].nature_of_perquisites_rows", "unique NatureDesc",
                    ", ".join(sorted(_perq_dupes)),
                ))
            _pil_codes = [row.get("NatureDesc") for row in _detail.nature_of_profit_in_lieu_rows]
            _pil_dupes = {c for c in _pil_codes if c and _pil_codes.count(c) > 1}
            if _pil_dupes:
                results.append(_result(
                    "ITR2-IN-SAL-023", False,
                    "The same nature-of-profit-in-lieu-of-salary code cannot be selected "
                    "more than once per employer.",
                    "employer_filing_details[].nature_of_profit_in_lieu_rows", "unique NatureDesc",
                    ", ".join(sorted(_pil_dupes)),
                ))

            # CBDT rule 65: the same Section 89A notified-income country
            # cannot be selected more than once per employer block.
            _country_codes = [row.country_code for row in _detail.income_notified_89a_country_rows]
            _country_dupes = {c for c in _country_codes if _country_codes.count(c) > 1}
            if _country_dupes:
                results.append(_result(
                    "ITR2-IN-SAL-024", False,
                    "The same Section 89A notified-income country cannot be selected more "
                    "than once per employer.",
                    "employer_filing_details[].income_notified_89a_country_rows",
                    "unique country_code", ", ".join(sorted(_country_dupes)),
                ))

    # ── Schedule HP (House Property) — Phase 5A ────────────────────────────
    hp_rows = list(inp.house_properties)
    if inp.house_property_income is not None:
        hp_rows.append(inp.house_property_income)
    self_occupied_count = 0
    for index, hp in enumerate(hp_rows):
        path = f"house_properties[{index}]"
        if hp.property_type == PropertyType.SELF_OCCUPIED:
            self_occupied_count += 1
            if inp.tax_regime == TaxRegime.NEW and hp.home_loan_interest_paid > _ZERO:
                results.append(_result(
                    "ITR2-IN-HP-009", False,
                    "Interest on borrowed capital cannot be claimed for a self-occupied property under the new tax regime.",
                    f"{path}.home_loan_interest_paid", _ZERO, str(hp.home_loan_interest_paid),
                ))
        if hp.annual_rent_received == _ZERO and hp.municipal_taxes_paid > _ZERO:
            results.append(_result(
                "ITR2-IN-HP-001", False,
                "Municipal tax is not allowed where gross rent received/receivable/"
                "lettable value is zero.",
                f"{path}.municipal_taxes_paid", _ZERO, str(hp.municipal_taxes_paid),
            ))
        if hp.property_type in (PropertyType.LET_OUT, PropertyType.DEEMED_LET_OUT) and hp.annual_rent_received <= _ZERO:
            results.append(_result(
                "ITR2-IN-HP-002", False,
                "A let-out or deemed-let-out property requires positive gross rent "
                "received/receivable/lettable value.",
                f"{path}.annual_rent_received", "> 0", str(hp.annual_rent_received),
            ))
    if self_occupied_count > 2:
        results.append(_result(
            "ITR2-IN-HP-003", False,
            "No more than two properties can be claimed as self-occupied.",
            "house_properties", "<= 2 self-occupied", str(self_occupied_count),
        ))
    for index, detail in enumerate(inp.property_filing_details):
        path = f"property_filing_details[{index}]"
        if detail.co_owned and detail.assessee_share_percent >= Decimal("100"):
            results.append(_result(
                "ITR2-IN-HP-004", False,
                "A co-owned property must have an assessee share below 100%.",
                f"{path}.assessee_share_percent", "< 100", str(detail.assessee_share_percent),
            ))
        if not detail.co_owned and detail.assessee_share_percent != Decimal("100"):
            results.append(_result(
                "ITR2-IN-HP-005", False,
                "A non-co-owned property's assessee share must equal 100%.",
                f"{path}.assessee_share_percent", "== 100", str(detail.assessee_share_percent),
            ))
        if index < len(hp_rows):
            hp = hp_rows[index]
            if detail.assessee_share_percent == _ZERO and hp.home_loan_interest_paid > _ZERO:
                results.append(_result(
                    "ITR2-IN-HP-007", False,
                    "Interest on borrowed capital cannot be claimed when the "
                    "assessee's co-owned property share is zero.",
                    f"{path}.assessee_share_percent", "> 0 when interest is claimed",
                    f"share={detail.assessee_share_percent}, interest={hp.home_loan_interest_paid}",
                ))
        # CBDT rules 68/751/752/549 (Phase 6d, 2026-09-11): co-owned property
        # shares — sum-to-100 across the assessee and every co-owner, each
        # co-owner's own share within (0, 100), and percent_share treated as
        # effectively required (the schema only requires co_owner_details to
        # be non-empty when co_owned=True, not that each row's percent_share
        # is populated). Mirrors the pattern ITR-4's own already-shipped
        # ITR4-R405/R406/R346 apply to its typed property_profile.co_owners.
        if detail.co_owned:
            _missing_share_indices = [
                j for j, co in enumerate(detail.co_owner_details) if co.percent_share is None
            ]
            if _missing_share_indices:
                results.append(_result(
                    "ITR2-IN-HP-011", False,
                    "Every co-owner row must state its percentage share when the "
                    "property is co-owned.",
                    f"{path}.co_owner_details[*].percent_share", "present",
                    f"missing at indices {_missing_share_indices}",
                ))
            for j, co in enumerate(detail.co_owner_details):
                if co.percent_share is not None and not (_ZERO < co.percent_share < Decimal("100")):
                    results.append(_result(
                        "ITR2-IN-HP-012", False,
                        "A co-owner's percentage share must be greater than 0% and less than 100%.",
                        f"{path}.co_owner_details[{j}].percent_share", "0 < share < 100",
                        str(co.percent_share),
                    ))
            if not _missing_share_indices:
                _co_owner_total = sum(
                    (co.percent_share for co in detail.co_owner_details), _ZERO,
                )
                _combined_share = detail.assessee_share_percent + _co_owner_total
                if _combined_share != Decimal("100"):
                    results.append(_result(
                        "ITR2-IN-HP-010", False,
                        "A co-owned property's assessee share plus every co-owner's "
                        "share must sum to 100%.",
                        f"{path}", "== 100",
                        f"assessee={detail.assessee_share_percent}, "
                        f"co-owners={_co_owner_total}, total={_combined_share}",
                    ))
            _filer_pan = getattr(inp.filing_profile, "pan", None)
            if _filer_pan:
                _matching_pan_indices = [
                    j for j, co in enumerate(detail.co_owner_details) if co.pan == _filer_pan
                ]
                if _matching_pan_indices:
                    results.append(_result(
                        "ITR2-IN-HP-013", False,
                        "A co-owner's PAN cannot be the same as the assessee's own PAN.",
                        f"{path}.co_owner_details[*].pan", f"!= {_filer_pan}",
                        f"matched at indices {_matching_pan_indices}",
                    ))

    # CBDT rule 757: unrealised rent cannot exceed the gross rent/lettable
    # value reported for the property. This is independently user-suppliable
    # in HousePropertyIncome and is consumed by the house-property schedule.
    for index, hp in enumerate(hp_rows):
        if hp.rent_not_realized > hp.annual_rent_received:
            results.append(_result(
                "ITR2-IN-HP-006", False,
                "Unrealised rent cannot exceed gross rent received, receivable, "
                "or lettable value.",
                f"house_properties[{index}].rent_not_realized",
                f"<= {hp.annual_rent_received}", str(hp.rent_not_realized),
            ))

    # ── Chapter VI-A Deductions — Phase 5C ─────────────────────────────────
    # Every section's compute() in app/engine/schedules/deductions/ already
    # self-caps to its statutory limit via min() and independently zeroes
    # under the new regime (verified against every section module: 80C/
    # 80CCC/80CCD1/80CCD1B/80D/80DD/80DDB/80E/80EE/80EEA/80EEB/80G/80GG/
    # 80GGA/80GGC/80TTA/80TTB/80U all gate on `regime == TaxRegime.NEW`;
    # 80CCD(2) and 80CCH do not, correctly, since both remain claimable
    # under the new regime) — so a pre-compute cap/regime validator would be
    # redundant for all of them. The one exception below (VIA-001) exists
    # because the *silent-drop* itself, not the cap, is the thing worth
    # surfacing to the taxpayer pre-compute — same rationale as SAL-006/7/8.
    # What the calculator genuinely does NOT check — no section module takes
    # an assessee-status or residential-status parameter at all — is
    # eligibility by assessee type/residency, which is where 5C's real gap
    # is and where the two rules below are aimed.
    ch6a = inp.deductions_chapter6a
    if ch6a is not None and inp.tax_regime == TaxRegime.NEW:
        _new_regime_disallowed = {
            "80C/80CCC/80CCD(1)": ch6a.amount_80c + ch6a.amount_80ccc + ch6a.amount_80ccd1,
            "80CCD(1B)": ch6a.amount_80ccd1b,
            "80D": ch6a.amount_80d_self_family + ch6a.amount_80d_parents,
            "80DD": ch6a.amount_80dd,
            "80DDB": ch6a.amount_80ddb,
            "80E": ch6a.amount_80e,
            "80EE": ch6a.amount_80ee,
            "80EEA": ch6a.amount_80eea,
            "80EEB": ch6a.amount_80eeb,
            "80G": ch6a.amount_80g,
            "80GG": ch6a.amount_80gg,
            "80GGA": ch6a.amount_80gga,
            "80GGC": ch6a.amount_80ggc,
            "80TTA": ch6a.amount_80tta,
            "80TTB": ch6a.amount_80ttb,
            "80U": ch6a.amount_80u,
        }
        claimed = {section: amount for section, amount in _new_regime_disallowed.items() if amount > _ZERO}
        if claimed:
            results.append(_result(
                "ITR2-IN-VIA-001", False,
                "These Chapter VI-A deductions cannot be claimed under the new tax regime: "
                + ", ".join(sorted(claimed)) + ".",
                "deductions_chapter6a", "all listed sections == 0",
                ", ".join(f"{k}={v}" for k, v in sorted(claimed.items())),
            ))
    if ch6a is not None and inp.filing_profile is not None and inp.filing_profile.assessee_status == AssesseeStatus.HUF:
        _huf_disallowed = {
            "80CCD(1)": ch6a.amount_80ccd1,
            "80CCD(1B)": ch6a.amount_80ccd1b,
            "80CCD(2)": ch6a.amount_80ccd2,
            "80E": ch6a.amount_80e,
            "80EE": ch6a.amount_80ee,
            "80EEA": ch6a.amount_80eea,
            "80EEB": ch6a.amount_80eeb,
            "80U": ch6a.amount_80u,
            # CBDT rule #592: Schedule 80D Sl.no.2 (parents' health insurance)
            # is not available to a HUF assessee -- conspicuously missing from
            # this set even though every other Section-80-series
            # individual-only deduction is already listed here.
            "80D (parents)": ch6a.amount_80d_parents,
        }
        claimed_huf = {section: amount for section, amount in _huf_disallowed.items() if amount > _ZERO}
        if claimed_huf:
            results.append(_result(
                "ITR2-IN-VIA-002", False,
                "These Chapter VI-A deductions are not available to a HUF assessee: "
                + ", ".join(sorted(claimed_huf)) + ".",
                "deductions_chapter6a", "all listed sections == 0",
                ", ".join(f"{k}={v}" for k, v in sorted(claimed_huf.items())),
            ))
    if inp.filing_profile is not None and inp.filing_profile.assessee_status == AssesseeStatus.HUF:
        # CBDT rule 516: Section 89 relief (arrears/advance salary) is an
        # individual-only concession, not available to a HUF assessee.
        # Independent of `ch6a` (relief_89 is a top-level ITR2Input field,
        # not a Chapter VI-A deduction) -- deliberately not nested inside
        # the `ch6a is not None` block above, unlike #592's own 80D check.
        if inp.relief_89 > _ZERO:
            results.append(_result(
                "ITR2-IN-FORM-008", False,
                "Section 89 relief (arrears/advance salary) cannot be claimed by a HUF "
                "assessee.",
                "relief_89", _ZERO, str(inp.relief_89),
            ))
        # CBDT rule 546: the eligible-startup ESOP tax-deferral concession
        # (Section 191(2A)) is available only to an individual employee, not
        # a HUF.
        if inp.esop_deferrals:
            results.append(_result(
                "ITR2-IN-FORM-009", False,
                "Schedule Tax Deferred on ESOP is not applicable to a HUF assessee.",
                "esop_deferrals", "empty", f"{len(inp.esop_deferrals)} entries",
            ))
    if ch6a is not None and inp.tax_regime == TaxRegime.OLD and ch6a.amount_80ee > _ZERO and ch6a.amount_80eea > _ZERO:
        results.append(_result(
            "ITR2-IN-VIA-004", False,
            "Deductions under sections 80EE and 80EEA cannot both be claimed "
            "under the old tax regime.",
            "deductions_chapter6a", "80EE == 0 or 80EEA == 0",
            f"80EE={ch6a.amount_80ee}, 80EEA={ch6a.amount_80eea}",
        ))
    # Section 80EE loan-principal ceiling (₹35,00,000) -- ported from ITR-1's
    # own ITR1-R227 (app/engine/validators/itr1/input_rules.py:2405-2409),
    # which ITR-2 was missing entirely despite ITR2Input.loan_details_80ee_list
    # carrying the identical total_loan_amount field (Docs/
    # ITR2_VALIDATOR_GAP_MAPPING_AY2026_27.md Phase 6b). This is one item out
    # of ITR-1's own richer 80EE/80EEA/80EEB loan-row validation cluster
    # (date-range/missing-rows/interest-total checks) -- ITR-2 is missing
    # that whole cluster, not just this one check; logged as a forward
    # pointer for a future targeted pass rather than expanding this phase's
    # scope to port all of it now.
    for index, row in enumerate(inp.loan_details_80ee_list or []):
        if row.total_loan_amount > Decimal("3500000"):
            results.append(_result(
                "ITR2-IN-VIA-009", False,
                f"Schedule 80EE row {index + 1} loan amount exceeds ₹35,00,000.",
                f"loan_details_80ee_list[{index}].total_loan_amount",
                "<= 3500000", str(row.total_loan_amount),
            ))
    if ch6a is not None and inp.residential_status == ResidentialStatus.NON_RESIDENT:
        _nri_disallowed = {
            "80DD": ch6a.amount_80dd,
            "80DDB": ch6a.amount_80ddb,
            "80U": ch6a.amount_80u,
        }
        claimed_nri = {section: amount for section, amount in _nri_disallowed.items() if amount > _ZERO}
        if claimed_nri:
            results.append(_result(
                "ITR2-IN-VIA-003", False,
                "These Chapter VI-A deductions are not available to a non-resident: "
                + ", ".join(sorted(claimed_nri)) + ".",
                "deductions_chapter6a", "all listed sections == 0",
                ", ".join(f"{k}={v}" for k, v in sorted(claimed_nri.items())),
            ))

    # The schema has no assessee type or business-income field. Its shape itself
    # restricts this form to an individual/HUF without current PGBP income.
    if inp.filing_date is not None and inp.due_date is not None and inp.filing_date < date(2000, 1, 1):
        results.append(_result(
            "ITR2-IN-DATE-001", False, "Filing date is outside the supported filing period.",
            "filing_date", ">= 2000-01-01", str(inp.filing_date),
        ))
    if inp.due_date is not None and inp.filing_date is not None:
        # Filing after due date is legal; it drives interest and fee, so no error.
        if inp.due_date.year > inp.filing_date.year + 1:
            results.append(_result(
                "ITR2-IN-DATE-002", False,
                "Due date cannot be more than one year after the filing date.",
                "due_date", f"<= {inp.filing_date.year + 1}-12-31", str(inp.due_date),
            ))

    for index, tx in enumerate(inp.cg_transactions or []):
        path = f"cg_transactions[{index}]"
        if tx.date_of_acquisition is None or tx.date_of_transfer is None:
            results.append(_result(
                "ITR2-IN-CG-001", False,
                "Capital-gain transactions require acquisition and transfer dates.",
                path, "both dates present", None,
            ))
        elif tx.date_of_transfer <= tx.date_of_acquisition:
            results.append(_result(
                "ITR2-IN-CG-002", False,
                "Transfer date must be later than acquisition date.",
                f"{path}.date_of_transfer", f"> {tx.date_of_acquisition}", str(tx.date_of_transfer),
            ))
        if tx.full_consideration <= _ZERO:
            results.append(_result(
                "ITR2-IN-CG-003", False,
                "A reported transfer must have positive full consideration.",
                f"{path}.full_consideration", "> 0", str(tx.full_consideration),
            ))
        if tx.full_consideration <= _ZERO and tx.expenditure_on_transfer > _ZERO:
            results.append(_result(
                "ITR2-IN-CG-101", False,
                "Transfer expenses cannot be claimed when full consideration is zero.",
                f"{path}.expenditure_on_transfer", _ZERO, str(tx.expenditure_on_transfer),
            ))
            results.append(_result(
                "ITR2-IN-CG-102", False,
                "Transfer expenses cannot be claimed against a zero-consideration capital-gain row.",
                f"{path}.expenditure_on_transfer", _ZERO, str(tx.expenditure_on_transfer),
            ))
            results.append(_result(
                "ITR2-IN-CG-103", False,
                "Transfer expenses cannot be claimed against a zero-consideration capital-gain row.",
                f"{path}.expenditure_on_transfer", _ZERO, str(tx.expenditure_on_transfer),
            ))
            results.append(_result(
                "ITR2-IN-CG-104", False,
                "Transfer expenses cannot be claimed against a zero-consideration capital-gain row.",
                f"{path}.expenditure_on_transfer", _ZERO, str(tx.expenditure_on_transfer),
            ))
            results.append(_result(
                "ITR2-IN-CG-105", False,
                "Transfer expenses cannot be claimed against a zero-consideration capital-gain row.",
                f"{path}.expenditure_on_transfer", _ZERO, str(tx.expenditure_on_transfer),
            ))
            results.append(_result(
                "ITR2-IN-CG-106", False,
                "Transfer expenses cannot be claimed against a zero-consideration capital-gain row.",
                f"{path}.expenditure_on_transfer", _ZERO, str(tx.expenditure_on_transfer),
            ))
            results.append(_result(
                "ITR2-IN-CG-107", False,
                "Transfer expenses cannot be claimed against a zero-consideration capital-gain row.",
                f"{path}.expenditure_on_transfer", _ZERO, str(tx.expenditure_on_transfer),
            ))
            results.append(_result(
                "ITR2-IN-CG-108", False,
                "Transfer expenses cannot be claimed against a zero-consideration capital-gain row.",
                f"{path}.expenditure_on_transfer", _ZERO, str(tx.expenditure_on_transfer),
            ))
        total_exemptions = (
            tx.deduction_us54 + tx.deduction_us54b + tx.deduction_us54ec + tx.deduction_us54f
        )
        gross_gain = max(
            _ZERO,
            tx.full_consideration
            - max(tx.cost_of_acquisition, tx.indexed_cost)
            - tx.expenditure_on_transfer,
        )
        if total_exemptions > gross_gain:
            results.append(_result(
                "ITR2-IN-CG-004", False,
                "Capital-gain exemptions cannot exceed the gain before exemption.",
                path, f"<= {gross_gain}", str(total_exemptions),
            ))
        if tx.asset_type in {CGAssetType.LISTED_EQUITY_111A, CGAssetType.LISTED_EQUITY_112A}:
            stt_paid = bool(tx.is_stt_paid_on_transfer) and (
                tx.asset_type == CGAssetType.LISTED_EQUITY_111A or bool(tx.is_stt_paid_on_acquisition)
            )
            if not stt_paid:
                results.append(_result(
                    "ITR2-IN-CG-005", False,
                    "Sections 111A/112A require applicable securities transaction tax to have been paid.",
                    f"{path}.is_stt_paid_on_transfer", True, stt_paid,
                ))
        if (
            tx.asset_type == CGAssetType.LISTED_EQUITY_112A
            and tx.date_of_acquisition is not None
            and tx.date_of_acquisition <= date(2018, 1, 31)
            and tx.fair_market_value_jan2018 is None
        ):
            results.append(_result(
                "ITR2-IN-CG-006", False,
                "Pre-1 February 2018 section 112A assets require 31 January 2018 FMV.",
                f"{path}.fair_market_value_jan2018", "non-null", None,
            ))
        if tx.asset_type == CGAssetType.LAND_BUILDING and tx.date_of_transfer > _financial_year_end(inp):
            results.append(_result(
                "ITR2-IN-CG-007", False,
                "Date of sale/transfer of land or building cannot be after 31 March "
                "of the financial year.",
                f"{path}.date_of_transfer", f"<= {_financial_year_end(inp)}", str(tx.date_of_transfer),
            ))
        if tx.deduction_us54ec > Decimal("5000000"):
            results.append(_result(
                "ITR2-IN-CG-008", False,
                "Deduction u/s 54EC (investment in specified bonds) is capped at ₹50,00,000.",
                f"{path}.deduction_us54ec", "<= 5000000", str(tx.deduction_us54ec),
            ))

    for index, scrip in enumerate(inp.cg_112a_scrips or []):
        path = f"cg_112a_scrips[{index}]"
        if not scrip.isin_code and not (scrip.share_unit_name or "").strip():
            results.append(_result(
                "ITR2-IN-112A-001", False,
                "Schedule 112A requires either an ISIN or a share/unit name.",
                path, "ISIN or name", None,
            ))
        if scrip.num_shares_units is None or scrip.num_shares_units <= _ZERO:
            results.append(_result(
                "ITR2-IN-112A-002", False,
                "Schedule 112A requires a positive number of shares/units.",
                f"{path}.num_shares_units", "> 0", str(scrip.num_shares_units),
            ))
        if scrip.sale_price_per_share is None or scrip.sale_price_per_share <= _ZERO:
            results.append(_result(
                "ITR2-IN-112A-003", False,
                "Schedule 112A requires a positive sale price per share/unit.",
                f"{path}.sale_price_per_share", "> 0", str(scrip.sale_price_per_share),
            ))
        if scrip.num_shares_units is not None and scrip.sale_price_per_share is not None:
            expected_sale = scrip.num_shares_units * scrip.sale_price_per_share
            if abs(scrip.total_sale_value - expected_sale) > Decimal("1"):
                results.append(_result(
                    "ITR2-IN-112A-004", False,
                    "Total sale value does not reconcile with quantity and unit sale price.",
                    f"{path}.total_sale_value", str(expected_sale), str(scrip.total_sale_value),
                ))
        if scrip.is_before_31jan2018 and (scrip.fmv_per_share is None or scrip.fmv_per_share <= _ZERO):
            results.append(_result(
                "ITR2-IN-112A-005", False,
                "Grandfathered section 112A holdings require a positive FMV per share.",
                f"{path}.fmv_per_share", "> 0", str(scrip.fmv_per_share),
            ))
        supplied_deductions = scrip.total_deductions
        expected_deductions = scrip.cost_acq_without_index + scrip.expenditure_on_transfer
        if supplied_deductions > _ZERO and abs(supplied_deductions - expected_deductions) > Decimal("1"):
            results.append(_result(
                "ITR2-IN-112A-006", False,
                "Schedule 112A total deductions must equal cost plus transfer expenditure.",
                f"{path}.total_deductions", str(expected_deductions), str(supplied_deductions),
            ))
        supplied_balance = scrip.balance
        expected_balance = scrip.total_sale_value - expected_deductions
        if supplied_balance is not None and abs(supplied_balance - expected_balance) > Decimal("1"):
            results.append(_result(
                "ITR2-IN-112A-007", False,
                "Schedule 112A balance must equal sale value less total deductions.",
                f"{path}.balance", str(expected_balance), str(supplied_balance),
            ))
        if not scrip.is_before_31jan2018 and scrip.fmv_per_share > _ZERO:
            results.append(_result(
                "ITR2-IN-112A-008", False,
                "Fair market value as on 31 January 2018 cannot be entered for shares "
                "acquired on or after 1 February 2018 (grandfathering does not apply).",
                f"{path}.fmv_per_share", _ZERO, str(scrip.fmv_per_share),
            ))

    for index, tx in enumerate(inp.vda_transactions or []):
        path = f"vda_transactions[{index}]"
        if tx.date_of_transfer <= tx.date_of_acquisition:
            results.append(_result(
                "ITR2-IN-VDA-001", False, "VDA transfer date must follow acquisition date.",
                f"{path}.date_of_transfer", f"> {tx.date_of_acquisition}", str(tx.date_of_transfer),
            ))
        if tx.date_of_acquisition > _financial_year_end(inp) or tx.date_of_transfer > _financial_year_end(inp):
            results.append(_result(
                "ITR2-IN-VDA-004", False,
                "VDA date of acquisition or date of transfer cannot be after 31 March "
                "of the financial year.",
                path, f"<= {_financial_year_end(inp)}",
                f"acquisition={tx.date_of_acquisition}, transfer={tx.date_of_transfer}",
            ))
        if tx.consideration_received <= _ZERO:
            results.append(_result(
                "ITR2-IN-VDA-002", False, "A reported VDA transfer requires positive consideration.",
                f"{path}.consideration_received", "> 0", str(tx.consideration_received),
            ))
        expected_income = max(_ZERO, tx.consideration_received - tx.acquisition_cost)
        if tx.income_from_vda is not None and tx.income_from_vda != expected_income:
            results.append(_result(
                "ITR2-IN-VDA-003", False,
                "VDA income must equal consideration less acquisition cost; VDA loss is not allowable.",
                f"{path}.income_from_vda", str(expected_income), str(tx.income_from_vda),
            ))

    current_ay = _current_assessment_year(inp)
    for index, loss in enumerate(inp.bf_losses or []):
        path = f"bf_losses[{index}]"
        head = loss.head.value if hasattr(loss.head, "value") else str(loss.head)
        head = head.strip().upper().replace("_", "")
        if head not in _ALLOWED_LOSS_HEADS:
            results.append(_result(
                "ITR2-IN-BFL-001", False,
                "Unsupported brought-forward loss category for ITR-2.",
                f"{path}.head", sorted(_ALLOWED_LOSS_HEADS), loss.head,
            ))
            continue
        loss_ay = _parse_assessment_year(loss.assessment_year)
        if loss_ay is None or loss_ay >= current_ay:
            results.append(_result(
                "ITR2-IN-BFL-002", False,
                "Loss assessment year must be a valid year preceding the current assessment year.",
                f"{path}.assessment_year", f"before {current_ay}-{str(current_ay + 1)[-2:]}", loss.assessment_year,
            ))
        elif current_ay - loss_ay > _ALLOWED_LOSS_HEADS[head]:
            results.append(_result(
                "ITR2-IN-BFL-003", False,
                "Brought-forward loss has expired for its statutory category.",
                f"{path}.assessment_year", f"not older than {_ALLOWED_LOSS_HEADS[head]} AYs", loss.assessment_year,
            ))
        if loss.brought_forward > loss.original_loss:
            results.append(_result(
                "ITR2-IN-BFL-004", False,
                "Brought-forward amount cannot exceed the original loss.",
                f"{path}.brought_forward", f"<= {loss.original_loss}", str(loss.brought_forward),
            ))

    fsi_by_country: dict[str, tuple[Decimal, Decimal]] = {}
    fsi_by_identity: dict[tuple[str, str], tuple[Decimal, Decimal, Decimal]] = {}
    for index, fsi in enumerate(inp.fsi_entries or []):
        path = f"fsi_entries[{index}]"
        expected_total = fsi.salary_income + fsi.hp_income + fsi.cg_income + fsi.os_income
        if fsi.total_income != expected_total:
            results.append(_result(
                "ITR2-IN-FSI-001", False,
                "FSI total income must equal the sum of its income heads.",
                f"{path}.total_income", str(expected_total), str(fsi.total_income),
            ))
        identity = (fsi.country_code.upper(), fsi.tax_identification_no.strip())
        prior_income, prior_tax, prior_relief = fsi_by_identity.get(
            identity, (_ZERO, _ZERO, _ZERO)
        )
        fsi_income = fsi.total_income or _ZERO
        fsi_relief = min(fsi.tax_paid_outside_india, fsi.tax_payable_in_india)
        fsi_by_identity[identity] = (
            prior_income + fsi_income,
            prior_tax + fsi.tax_paid_outside_india,
            prior_relief + fsi_relief,
        )
        income, tax = fsi_by_country.get(fsi.country_code.upper(), (_ZERO, _ZERO))
        fsi_by_country[fsi.country_code.upper()] = (income + fsi_income, tax + fsi.tax_paid_outside_india)
    if inp.fsi_entries and inp.residential_status == ResidentialStatus.NON_RESIDENT:
        results.append(_result(
            "ITR2-IN-FSI-003", False,
            "Schedule FSI is not applicable when residential status is non-resident.",
            "fsi_entries", "empty", f"{len(inp.fsi_entries)} entries",
        ))

    # CBDT rules 446/447/448: a Schedule FSI relief claim against a given
    # income head cannot exceed what that same head actually discloses
    # elsewhere in the return -- summed across every fsi_entries row, since
    # more than one country can carry income under the same head.
    if inp.fsi_entries:
        _fsi_salary_total = sum((fsi.salary_income for fsi in inp.fsi_entries), _ZERO)
        _actual_salary = sal.gross_salary if sal is not None else _ZERO
        if _fsi_salary_total > _actual_salary:
            results.append(_result(
                "ITR2-IN-FSI-004", False,
                "Schedule FSI salary income claimed for relief cannot exceed Schedule Salary's "
                "own gross salary.",
                "fsi_entries[].salary_income", f"<= {_actual_salary}", str(_fsi_salary_total),
            ))
        _fsi_hp_total = sum((fsi.hp_income for fsi in inp.fsi_entries), _ZERO)
        _actual_hp = sum((hp.annual_rent_received for hp in hp_rows), _ZERO) if hp_rows else _ZERO
        if _fsi_hp_total > _actual_hp:
            results.append(_result(
                "ITR2-IN-FSI-005", False,
                "Schedule FSI house-property income claimed for relief cannot exceed the "
                "return's own disclosed house-property income.",
                "fsi_entries[].hp_income", f"<= {_actual_hp}", str(_fsi_hp_total),
            ))
        _fsi_cg_total = sum((fsi.cg_income for fsi in inp.fsi_entries), _ZERO)
        _actual_cg = sum(
            (
                tx.full_consideration - tx.cost_of_acquisition
                for tx in inp.cg_transactions
            ),
            _ZERO,
        ) if inp.cg_transactions else _ZERO
        if _fsi_cg_total > max(_ZERO, _actual_cg):
            results.append(_result(
                "ITR2-IN-FSI-006", False,
                "Schedule FSI capital-gains income claimed for relief cannot exceed the "
                "return's own disclosed capital gains.",
                "fsi_entries[].cg_income", f"<= {max(_ZERO, _actual_cg)}", str(_fsi_cg_total),
            ))

    tr_by_country: dict[str, tuple[Decimal, Decimal]] = {}
    tr_by_identity: dict[tuple[str, str], tuple[Decimal, Decimal, Decimal]] = {}
    for index, tr in enumerate(inp.tr1_entries or []):
        path = f"tr1_entries[{index}]"
        if tr.relief_claimed > min(tr.tax_paid_outside_india, tr.indian_tax_payable):
            results.append(_result(
                "ITR2-IN-TR1-001", False,
                "Foreign-tax relief cannot exceed foreign tax paid or Indian tax payable.",
                f"{path}.relief_claimed",
                f"<= {min(tr.tax_paid_outside_india, tr.indian_tax_payable)}", str(tr.relief_claimed),
            ))
        if inp.residential_status == ResidentialStatus.NON_RESIDENT:
            results.append(_result(
                "ITR2-IN-TR1-003", False,
                "Schedule TR is not applicable when residential status is non-resident.",
                "tr1_entries", "empty", f"{len(inp.tr1_entries)} entries",
            ))
        identity = (tr.country_code.upper(), tr.tax_identification_no.strip())
        prior_income, prior_tax, prior_relief = tr_by_identity.get(
            identity, (_ZERO, _ZERO, _ZERO)
        )
        tr_by_identity[identity] = (
            prior_income + tr.income_included_in_this_return,
            prior_tax + tr.tax_paid_outside_india,
            prior_relief + tr.relief_claimed,
        )
        income, tax = tr_by_country.get(tr.country_code.upper(), (_ZERO, _ZERO))
        tr_by_country[tr.country_code.upper()] = (
            income + tr.income_included_in_this_return,
            tax + tr.tax_paid_outside_india,
        )
    for identity in sorted(set(fsi_by_identity) | set(tr_by_identity)):
        fsi_values = fsi_by_identity.get(identity, (_ZERO, _ZERO, _ZERO))
        tr_values = tr_by_identity.get(identity, (_ZERO, _ZERO, _ZERO))
        if fsi_values[1] != tr_values[1]:
            results.append(_result(
                "ITR2-IN-TR1-004", False,
                "Schedule TR tax paid outside India must match Schedule FSI for each country and TIN.",
                "tr1_entries", str(fsi_values[1]), str(tr_values[1]),
            ))
        if fsi_values[2] != tr_values[2]:
            results.append(_result(
                "ITR2-IN-TR1-005", False,
                "Schedule TR relief must match relief available in Schedule FSI for each country and TIN.",
                "tr1_entries", str(fsi_values[2]), str(tr_values[2]),
            ))
    for country in sorted(set(fsi_by_country) | set(tr_by_country)):
        if fsi_by_country.get(country, (_ZERO, _ZERO)) != tr_by_country.get(country, (_ZERO, _ZERO)):
            results.append(_result(
                "ITR2-IN-TR1-002", False,
                f"FSI and TR1 income/tax totals do not reconcile for country {country}.",
                "tr1_entries", str(fsi_by_country.get(country, (_ZERO, _ZERO))),
                str(tr_by_country.get(country, (_ZERO, _ZERO))),
            ))

    # Schedule TR must not claim relief for a non-resident return.
    if inp.tr1_entries and inp.residential_status == ResidentialStatus.NON_RESIDENT:
        results.append(_result(
            "ITR2-IN-TR1-003", False,
            "Schedule TR is not applicable when residential status is non-resident.",
            "tr1_entries", "empty", f"{len(inp.tr1_entries)} entries",
        ))

    # CBDT rule 154: a plain Resident (not claiming Section 115H's "continue
    # to be taxed as a non-resident on assets acquired while non-resident"
    # option) cannot hold a dividend claim under Section 115AC, which is
    # reserved for non-residents (or residents electing 115H). Rules 153/155
    # (the Schedule-CG-side 112(1)(c)/115AC instances of this same
    # eligibility gate) are Not representable, not merely unimplemented --
    # confirmed via a full grep of `CGAssetType`/`CGTransaction` for any
    # 112(1)(c)/115AC-specific classification: none exists, so no CG
    # transaction in this schema can be identified as claiming either rate
    # in the first place. See the gap-mapping doc's own reclassification note
    # for rows #153/#155.
    if (
        inp.filing_profile is not None
        and inp.filing_profile.residential_status == ResidentialStatus.RESIDENT
        and not inp.filing_profile.benefit_us_115h
        and any(entry.section == "115AC" for entry in inp.os_dividend_entries)
    ):
        results.append(_result(
            "ITR2-IN-OS-007", False,
            "A Resident cannot claim dividend income under Section 115AC without electing "
            "the Section 115H benefit.",
            "os_dividend_entries[].section", "not 115AC unless benefit_us_115h", "115AC",
        ))

    # CBDT rules 199-205/229 (Phase 6j-5): Schedule OS's DTAA claim table
    # (`os_dtaa_entries`) tags each row with which Sl.1/2 source item it's
    # drawn from (`nature_of_income`) -- the sum of DTAA-tagged amounts for a
    # given source item cannot exceed that source item's own declared gross
    # total (a DTAA claim re-tags/exempts part of an existing item, it can
    # never exceed it). One reusable helper covers all eight source items.
    osi = inp.other_sources_income

    def _si_gross(section: str) -> Decimal:
        return sum((sie.gross_income for sie in inp.si_entries if sie.section == section), _ZERO)

    _dtaa_source_totals: dict[str, tuple[Decimal, str]] = {
        "1ai": (osi.dividend_income if osi else _ZERO, "other_sources_income.dividend_income"),
        "1b": (
            (osi.savings_bank_interest + osi.fixed_deposit_interest + osi.interest_on_it_refund)
            if osi else _ZERO,
            "other_sources_income (interest fields)",
        ),
        "1c": (inp.os_machinery_plant_rent, "os_machinery_plant_rent"),
        "1d": (osi.income_56_2_x if osi else _ZERO, "other_sources_income.income_56_2_x"),
        "2ai": (_si_gross("115BB"), 'si_entries (section "115BB")'),
        "2aii": (_si_gross("115BBJ"), 'si_entries (section "115BBJ")'),
        "2d": (
            sum((e.source_amount for e in inp.os_special_rate_entries), _ZERO),
            "os_special_rate_entries",
        ),
        "2e": (
            sum((p.income_amount for p in inp.pti_entries if p.income_head == "OS"), _ZERO),
            "pti_entries (OS head)",
        ),
    }
    for _nature, (_source_total, _source_label) in _dtaa_source_totals.items():
        _dtaa_total = sum(
            (e.amount for e in inp.os_dtaa_entries if e.nature_of_income == _nature), _ZERO,
        )
        if _dtaa_total > _source_total:
            results.append(_result(
                "ITR2-IN-OS-008", False,
                f"DTAA-tagged Other Sources income for item {_nature} cannot exceed its own "
                f"declared source total ({_source_label}).",
                f'os_dtaa_entries[nature_of_income="{_nature}"]', f"<= {_source_total}",
                str(_dtaa_total),
            ))

    # CBDT rule 227: Section 89A income_notified must equal the sum of its
    # own per-country detail rows -- mirrors the sibling
    # `FSICountryEntry.derive_and_validate_total` precedent, but OSSection89A
    # has no such schema-level validator, so this is a pre-compute check
    # instead.
    if inp.os_section_89a is not None:
        _s89a = inp.os_section_89a
        _country_total = sum((e.amount for e in _s89a.country_entries), _ZERO)
        if _s89a.income_notified != _country_total:
            results.append(_result(
                "ITR2-IN-OS-009", False,
                "Section 89A notified income must equal the sum of its own per-country "
                "detail rows.",
                "os_section_89a.income_notified", str(_country_total), str(_s89a.income_notified),
            ))

        # CBDT rule 232: the same Section 89A notified-income country cannot
        # be selected more than once in Schedule OS's own country list
        # (distinct from row #65's per-employer Schedule-S instance of the
        # identical check).
        _s89a_countries = [e.country_code for e in _s89a.country_entries]
        _s89a_dupes = {c for c in _s89a_countries if _s89a_countries.count(c) > 1}
        if _s89a_dupes:
            results.append(_result(
                "ITR2-IN-OS-010", False,
                "The same Section 89A notified-income country cannot be selected more than "
                "once.",
                "os_section_89a.country_entries", "unique country_code",
                ", ".join(sorted(_s89a_dupes)),
            ))

    # CBDT rule 198: Section 115BBF (patent royalty income) is available to
    # a resident patentee only -- a non-resident cannot hold this claim.
    if (
        inp.residential_status == ResidentialStatus.NON_RESIDENT
        and any(sie.section == "115BBF" for sie in inp.si_entries)
    ):
        results.append(_result(
            "ITR2-IN-OS-011", False,
            "A non-resident cannot claim income under Section 115BBF (patent royalty).",
            "si_entries[].section", "not 115BBF for a non-resident", "115BBF",
        ))

    # CBDT rules 214/219-223/231 (Phase 6j-6): each Schedule OS dividend row's
    # own Q1-Q5 quarterly breakdown (used for Section 234C interest support)
    # must sum to exactly that row's own declared `amount` -- one reusable
    # check across every dividend section (general/DTAA/115A1ai/115AC/
    # 115ACA/115AD1i/115A1aA), since `OSDividendEntry` carries one `amount`
    # plus one `q1..q5` breakdown regardless of section.
    for _idx, _div in enumerate(inp.os_dividend_entries):
        _div_quarters_total = _div.q1 + _div.q2 + _div.q3 + _div.q4 + _div.q5
        if _div_quarters_total > _ZERO and _div_quarters_total != _div.amount:
            results.append(_result(
                "ITR2-IN-OS-012", False,
                "A Schedule OS dividend row's quarterly (Q1-Q5) breakdown must sum to its own "
                "declared amount.",
                f"os_dividend_entries[{_idx}]", str(_div.amount), str(_div_quarters_total),
            ))

    # CBDT rules 213/230: the lottery/online-gaming quarterly breakdowns
    # (used for 234C interest support, distinct from the per-row dividend
    # breakdown above) must sum to their own corresponding Schedule-SI gross
    # income total.
    if inp.os_lottery_quarters is not None:
        _lottery_q = inp.os_lottery_quarters
        _lottery_total = _lottery_q.q1 + _lottery_q.q2 + _lottery_q.q3 + _lottery_q.q4 + _lottery_q.q5
        _lottery_si = sum((sie.gross_income for sie in inp.si_entries if sie.section == "115BB"), _ZERO)
        if _lottery_total != _lottery_si:
            results.append(_result(
                "ITR2-IN-OS-013", False,
                "The lottery-income quarterly breakdown must sum to the Section 115BB gross "
                "income declared in Schedule SI.",
                "os_lottery_quarters", str(_lottery_si), str(_lottery_total),
            ))
    if inp.os_gaming_quarters is not None:
        _gaming_q = inp.os_gaming_quarters
        _gaming_total = _gaming_q.q1 + _gaming_q.q2 + _gaming_q.q3 + _gaming_q.q4 + _gaming_q.q5
        _gaming_si = sum((sie.gross_income for sie in inp.si_entries if sie.section == "115BBJ"), _ZERO)
        if _gaming_total != _gaming_si:
            results.append(_result(
                "ITR2-IN-OS-014", False,
                "The online-gaming-winnings quarterly breakdown must sum to the Section 115BBJ "
                "gross income declared in Schedule SI.",
                "os_gaming_quarters", str(_gaming_si), str(_gaming_total),
            ))

    # CBDT rules 192/217/228: deductions/depreciation u/s 57 (other than the
    # family-pension-specific 57(iia), which is engine-computed and always
    # tied to `family_pension_received`) can only be claimed when the
    # corresponding OS income items are actually offered. #192 is the
    # machinery/plant-rent-specific instance (depreciation requires
    # Sl.1c > 0); #217/#228 are the general instance across every non-family-
    # pension OS income item -- one combined check covers all three, since a
    # nonzero deduction with zero income anywhere in the qualifying set is
    # invalid regardless of which specific item the taxpayer meant to net it
    # against.
    if inp.os_deductions is not None:
        _ded = inp.os_deductions
        # #192: depreciation specifically requires machinery/plant rent
        # income (Sl.1c), regardless of any other OS income offered.
        if _ded.depreciation > _ZERO and inp.os_machinery_plant_rent <= _ZERO:
            results.append(_result(
                "ITR2-IN-OS-015", False,
                "Depreciation u/s 57 cannot be claimed against machinery/plant/building rental "
                "income unless that income (Sl.1c) is itself offered.",
                "os_deductions.depreciation", "0 when os_machinery_plant_rent == 0",
                str(_ded.depreciation),
            ))
        # #217/#228: expenses/depreciation more generally require SOME
        # qualifying OS income (other than family pension) to be offered.
        _other_os_income = (
            (osi.savings_bank_interest + osi.fixed_deposit_interest + osi.interest_on_it_refund
             + osi.income_56_2_x + osi.other_income + inp.os_machinery_plant_rent) if osi else _ZERO
        )
        if (_ded.expenses > _ZERO or _ded.depreciation > _ZERO) and _other_os_income <= _ZERO:
            results.append(_result(
                "ITR2-IN-OS-016", False,
                "Expenses/depreciation u/s 57 cannot be claimed unless corresponding Other "
                "Sources income (other than family pension) is offered.",
                "os_deductions", "> 0 only with offered OS income", "0",
            ))

    # ── Schedule OS / Schedule SI / CYLA-BFLA-CFL — Phase 5D ───────────────
    # Schedule OS (`OtherSourcesIncome`) has almost nothing left to validate:
    # it is a flat gross-income-bucket model shared with ITR-1, and ITR-1's
    # own Schedule OS rules (R050/R052/R145) all key off ITR1Input-only
    # fields — `other_sources_dropdowns`, `other_sources_total`,
    # `dividend_quarterly_breakdown` — none of which exist on ITR2Input, so
    # there is nothing to adapt from ITR-1 here. The 57(iia) family-pension
    # deduction cap is engine-computed in app/engine/schedules/other_sources.py
    # (`min(fp/3, cap)`, only applied `if fp > 0`) exactly like 5A's salary
    # exemptions, so it needs no separate validator either.
    # CYLA/BFLA/CFL: `ITR2Input.cf_losses` is never read by the calculator
    # (`app/engine/calculators/itr2.py` derives its own "cfl" schedule from
    # `bf_losses` and current-year losses) — a vestigial input field, so a
    # validator against it would check something with no effect on the
    # filed return. The remaining CBDT catalog rules here (234–274) are
    # column-arithmetic identities against `build_itr2_json`'s own output
    # construction, already build-time-guaranteed.
    # Schedule SI: `ScheduleSIEntry.deductions` and `.tax_rate_pct` are BOTH
    # ignored by every `compute_*` function in
    # app/engine/schedules/special_rates.py (rates are hardcoded constants;
    # only `.gross_income` is read) — but unlike the caps found elsewhere,
    # that isn't itself a reason to skip a rule: Section 58(4) makes any
    # deduction against lottery/game-winning income *legally* invalid, not
    # just uncomputed, so a nonzero claim there is worth rejecting outright
    # rather than letting it silently vanish. `ScheduleSIEntry` itself already
    # has a `reject_disallowed_deductions` model validator blocking this for
    # sections 115BB/115BBE — 115BBJ (online game winnings, same Section 58(4)
    # disallowance) is the one section it does NOT cover, so that's the only
    # one left for this rule to add.
    # CBDT rule 216 (Phase 6f, 2026-09-11): interest expenditure claimed on
    # dividend income u/s 57(1) cannot exceed 20% of dividend income --
    # a genuine, checkable gap the "almost nothing left to validate" comment
    # above didn't address, since OSDeductions.interest_expense_us57 is a
    # real user-suppliable field independent of anything else in this
    # section. Checked against the raw CLAIMED figure (`interest_expense_
    # us57`, form Sl 3aii, JSON `IntExp57`), not the system-computed ELIGIBLE
    # figure (`interest_expense_eligible_us57`, Sl 3aiia, `UsrIntExp57`) --
    # the eligible amount is by definition already capped, so validating it
    # against the same 20% ceiling would be redundant; the claim is the one
    # value that can genuinely violate this rule.
    if inp.other_sources_income is not None and inp.os_deductions is not None:
        _dividend_income = inp.other_sources_income.dividend_income
        _dividend_cap = _dividend_income * Decimal("0.20")
        if inp.os_deductions.interest_expense_us57 > _dividend_cap:
            results.append(_result(
                "ITR2-IN-OS-001", False,
                "Interest expenditure claimed on dividend income u/s 57(1) "
                "cannot exceed 20% of dividend income.",
                "os_deductions.interest_expense_us57", f"<= {_dividend_cap}",
                str(inp.os_deductions.interest_expense_us57),
            ))

    # CBDT rule 211/212 (Phase 6f, 2026-09-11): TaxAccumulatedBalRecPF's
    # header totals (os_pf_income_benefit/os_pf_tax_benefit) and its own
    # per-assessment-year detail rows (os_pf_accumulated_entries) are two
    # independently user-suppliable figures with no reconciliation anywhere
    # -- a taxpayer (or a buggy frontend) could submit header totals that
    # don't actually sum from the detail rows and the builder would emit an
    # internally inconsistent block without complaint, same failure mode as
    # the already-known Schedule 80D per-policy-breakup gap (see "Additional
    # bugs noticed" item 2 in the gap-mapping doc).
    if inp.os_pf_accumulated_entries:
        _pf_income_total = sum((e.income_benefit for e in inp.os_pf_accumulated_entries), _ZERO)
        _pf_tax_total = sum((e.tax_benefit for e in inp.os_pf_accumulated_entries), _ZERO)
        if inp.os_pf_income_benefit != _pf_income_total:
            results.append(_result(
                "ITR2-IN-OS-002", False,
                "Accumulated PF income benefit total must equal the sum of its "
                "per-assessment-year detail rows.",
                "os_pf_income_benefit", str(_pf_income_total), str(inp.os_pf_income_benefit),
            ))
        if inp.os_pf_tax_benefit != _pf_tax_total:
            results.append(_result(
                "ITR2-IN-OS-003", False,
                "Accumulated PF tax benefit total must equal the sum of its "
                "per-assessment-year detail rows.",
                "os_pf_tax_benefit", str(_pf_tax_total), str(inp.os_pf_tax_benefit),
            ))

    # CBDT rule 194 (Phase 6f, 2026-09-11): Schedule OS Sl.8e (race-horse
    # activity balance) must equal 8a-8b+8c+8d (receipts - deduction u/s 57
    # + amounts not deductible u/s 58 + profits chargeable u/s 59) -- the
    # form's own stated formula. OSRaceHorseActivity.balance is a raw,
    # independently user-suppliable field the calculator and builder both
    # trust as-is with no reconciliation against its own components.
    if inp.os_race_horse is not None:
        rh = inp.os_race_horse
        _expected_balance = rh.receipts - rh.deduction_us57 + rh.amount_not_deductible_us58 + rh.profit_chargeable_us59
        if rh.balance != _expected_balance:
            results.append(_result(
                "ITR2-IN-OS-004", False,
                "Race-horse activity balance must equal receipts less deduction "
                "u/s 57 plus amounts not deductible u/s 58 plus profits "
                "chargeable u/s 59.",
                "os_race_horse.balance", str(_expected_balance), str(rh.balance),
            ))

    # CBDT rule 59 (Phase 6g, 2026-09-11): Section 89A (foreign-retirement-
    # account income deferral) is only available to individuals -- an HUF
    # cannot claim it. Checked against filing_profile.assessee_status
    # (Individual='I'/HUF='H'), the same field the existing HUF-restricted
    # deduction checks (ITR2-IN-VIA-002/003) already key off.
    if (
        inp.os_section_89a is not None
        and inp.filing_profile is not None
        and inp.filing_profile.assessee_status == AssesseeStatus.HUF
        and (inp.os_section_89a.income_notified > _ZERO or inp.os_section_89a.relief > _ZERO)
    ):
        results.append(_result(
            "ITR2-IN-OS-005", False,
            "Section 89A (retirement benefit account income deferral) cannot be "
            "claimed by an HUF.",
            "os_section_89a", "present only for AssesseeStatus.INDIVIDUAL",
            f"assessee_status={inp.filing_profile.assessee_status}",
        ))

    # CBDT rules 60/224/226: Section 89A relief cannot exceed the notified
    # income it's claimed against (form Sl.1e, "Income from retirement
    # benefit account maintained in a notified country u/s 89A") -- this
    # single comparison also structurally closes rule #226 ("relief allowed
    # only if income is offered in Sl.1e"), since a nonzero relief against a
    # zero income_notified always fails the same `relief > income_notified`
    # check.
    if inp.os_section_89a is not None and inp.os_section_89a.relief > inp.os_section_89a.income_notified:
        results.append(_result(
            "ITR2-IN-OS-006", False,
            "Section 89A relief cannot exceed the income offered under "
            "retirement benefit account income (Sl.1e).",
            "os_section_89a.relief", f"<= {inp.os_section_89a.income_notified}",
            str(inp.os_section_89a.relief),
        ))

    for index, si in enumerate(inp.si_entries or []):
        if si.section == "115BBJ" and si.deductions > _ZERO:
            results.append(_result(
                "ITR2-IN-SI-001", False,
                "No deduction or allowance is permitted against income taxable "
                "under section 115BBJ (winnings from online games) — section 58(4).",
                f"si_entries[{index}].deductions", _ZERO, str(si.deductions),
            ))

    # CBDT rules 463, 471 and 472: withholding credits require corresponding
    # income in the schedule from which the credit is claimed.
    for index, entry in enumerate(inp.tds2_entries or []):
        if entry.tds_claimed_this_year > entry.gross_amount:
            results.append(_result(
                "ITR2-IN-TDS-002", False,
                "TDS claimed under Schedule TDS2 cannot exceed the corresponding gross income disclosed.",
                f"tds2_entries[{index}].tds_claimed_this_year",
                f"<= {entry.gross_amount}", str(entry.tds_claimed_this_year),
            ))
    total_salary_tds = sum((entry.tds_deducted for entry in inp.tds1_entries), _ZERO)
    if inp.tds1_entries and inp.salary_income is None:
        results.append(_result(
            "ITR2-IN-TDS-003", False,
            "Salary TDS can be claimed only when salary income is disclosed.",
            "salary_income", "present", "absent",
        ))
    elif inp.tds1_entries and inp.salary_income is not None:
        salary_income = (
            inp.salary_income.gross_salary
            + inp.salary_income.perquisites_value
            + inp.salary_income.profits_in_lieu_of_salary
        )
        if total_salary_tds > salary_income:
            results.append(_result(
                "ITR2-IN-TDS-004", False,
                "Total tax deducted from salary cannot exceed income chargeable under Salaries.",
                "tds1_entries", f"<= {salary_income}", str(total_salary_tds),
            ))

    # CBDT rule 542: relief u/s 89 requires salary details.
    if inp.relief_89 > _ZERO and (
        inp.salary_income is None
        or inp.salary_income.gross_salary
        + inp.salary_income.perquisites_value
        + inp.salary_income.profits_in_lieu_of_salary <= _ZERO
    ):
        results.append(_result(
            "ITR2-IN-FORM-003", False,
            "Relief u/s 89 cannot be claimed when salary details are zero or blank.",
            "relief_89", _ZERO, str(inp.relief_89),
        ))

    # CBDT rules 548, 763 and 764: disability claims require their official
    # supporting schedules.  These fields are canonical and calculator-used.
    if ch6a is not None and ch6a.amount_80u > _ZERO and ch6a.schedule_80u is None:
        results.append(_result(
            "ITR2-IN-VIA-005", False,
            "A positive Section 80U deduction requires Schedule 80U disability details.",
            "deductions_chapter6a.schedule_80u", "present", "absent",
        ))
    if ch6a is not None and ch6a.amount_80dd > _ZERO and ch6a.schedule_80dd is None:
        results.append(_result(
            "ITR2-IN-VIA-006", False,
            "A positive Section 80DD deduction requires Schedule 80DD disability details.",
            "deductions_chapter6a.schedule_80dd", "present", "absent",
        ))
    if (
        ch6a is not None
        and ch6a.amount_80dd > _ZERO
        and ch6a.schedule_80dd is not None
        and inp.filing_profile is not None
        and inp.filing_profile.assessee_status == AssesseeStatus.HUF
        and ch6a.schedule_80dd.dependent_relationship is None
    ):
        results.append(_result(
            "ITR2-IN-VIA-007", False,
            "An HUF claiming Section 80DD must identify the dependent as a Member of HUF.",
            "deductions_chapter6a.schedule_80dd.dependent_relationship",
            "MEMBER_OF_HUF", "missing",
        ))

    # CBDT rules 462, 464, 465, 468 and 479: withholding schedules must
    # preserve the distinction between current-year and brought-forward credit,
    # carry the corresponding income, and respect assessee eligibility.
    for index, entry in enumerate(inp.tds2_entries or []):
        path = f"tds2_entries[{index}]"
        if entry.tds_claimed_this_year > _ZERO and entry.gross_amount <= _ZERO:
            results.append(_result(
                "ITR2-IN-TDS-005", False,
                "TDS2 gross income must be disclosed when TDS is claimed.",
                f"{path}.gross_amount", "> 0", str(entry.gross_amount),
            ))
        if entry.brought_forward_tds > _ZERO and entry.tds_deducted > _ZERO:
            results.append(_result(
                "ITR2-IN-TDS-006", False,
                "Current-year TDS and brought-forward TDS must be reported in separate TDS2 rows.",
                path, "not both current-year and brought-forward credit",
                f"brought_forward={entry.brought_forward_tds}, deducted={entry.tds_deducted}",
            ))
        expected_carry_forward = max(
            _ZERO,
            entry.tds_deducted + entry.brought_forward_tds - entry.tds_claimed_this_year,
        )
        if entry.tds_credit_carried_forward != expected_carry_forward:
            results.append(_result(
                "ITR2-IN-TDS-007", False,
                "TDS2 credit carried forward must equal deducted plus brought-forward TDS less claimed TDS.",
                f"{path}.tds_credit_carried_forward", str(expected_carry_forward),
                str(entry.tds_credit_carried_forward),
            ))
    if inp.filing_profile is not None and inp.filing_profile.assessee_status == AssesseeStatus.HUF:
        salary_tds = sum((entry.tds_deducted for entry in inp.tds1_entries), _ZERO)
        if salary_tds > _ZERO:
            results.append(_result(
                "ITR2-IN-TDS-008", False,
                "An HUF cannot claim TDS on salary.",
                "tds1_entries", _ZERO, str(salary_tds),
            ))
    for index, entry in enumerate(inp.tds3_entries or []):
        if entry.tds_claimed > _ZERO and entry.gross_receipt <= _ZERO:
            results.append(_result(
                "ITR2-IN-TDS-009", False,
                "TDS3 gross receipt must be disclosed when TDS is claimed.",
                f"tds3_entries[{index}].gross_receipt", "> 0", str(entry.gross_receipt),
            ))
    # TDS3 carry-forward arithmetic mirrors the TDS2 ledger check.
    for index, entry in enumerate(inp.tds3_entries or []):
        expected_carry = max(_ZERO, entry.tds_deducted + entry.brought_forward_tds - entry.tds_claimed)
        if entry.tds_credit_carried_forward != expected_carry:
            results.append(_result(
                "ITR2-IN-TDS-012", False,
                "TDS3 credit carried forward must equal deducted plus brought-forward TDS less claimed TDS.",
                f"tds3_entries[{index}].tds_credit_carried_forward",
                str(expected_carry), str(entry.tds_credit_carried_forward),
            ))

    # CBDT rule 480: the ESOP deferred-tax ledger has an explicit balance
    # carried-forward field, so its arithmetic can be validated independently
    # of the unavailable Part B-TTI aggregate.
    for index, esop in enumerate(inp.esop_deferrals or []):
        expected_balance = max(
            _ZERO, esop.tax_deferred_brought_forward - esop.tax_payable_current_year,
        )
        if esop.balance_tax_carried_forward != expected_balance:
            results.append(_result(
                "ITR2-IN-ESOP-001", False,
                "ESOP deferred-tax balance carried forward must equal brought-forward tax less current-year tax payable.",
                f"esop_deferrals[{index}].balance_tax_carried_forward",
                str(expected_balance), str(esop.balance_tax_carried_forward),
            ))

    # CBDT rule 754: Section 115F investment must be made within six months
    # after the transfer of the original foreign-exchange asset.
    for index, tx in enumerate(inp.cg_transactions or []):
        for claim_index, claim in enumerate(tx.exemptions):
            if claim.section == "115F" and claim.investment_date is not None:
                if claim.investment_date < claim.transfer_date or (
                    claim.investment_date - claim.transfer_date
                ).days > 183:
                    results.append(_result(
                        "ITR2-IN-CG-009", False,
                        "Section 115F investment must be made within six months after the transfer date.",
                        f"cg_transactions[{index}].exemptions[{claim_index}].investment_date",
                        "within six months after transfer", str(claim.investment_date),
                    ))

    # Canonical exemption rows must not exceed the gain they purport to shelter.
    for index, tx in enumerate(inp.cg_transactions or []):
        for claim_index, claim in enumerate(tx.exemptions):
            claimed = claim.investment_amount + claim.cgas_deposit_amount
            if claimed > claim.eligible_gain:
                results.append(_result(
                    "ITR2-IN-CG-011", False,
                    "A capital-gain exemption investment cannot exceed the eligible gain.",
                    f"cg_transactions[{index}].exemptions[{claim_index}]",
                    f"investment plus CGAS <= {claim.eligible_gain}", str(claimed),
                ))

    # CBDT rule 650: section 192 is salary withholding and cannot be selected
    # on the non-salary TDS schedules.
    for index, entry in enumerate(inp.tds2_entries or []):
        if entry.tds_section.strip().upper() == "192":
            results.append(_result(
                "ITR2-IN-TDS-010", False,
                "Section 192 TDS must be reported in Schedule TDS1, not TDS2.",
                f"tds2_entries[{index}].tds_section", "not 192", entry.tds_section,
            ))
    for index, entry in enumerate(inp.tds3_entries or []):
        if entry.tds_section.strip().upper() == "192":
            results.append(_result(
                "ITR2-IN-TDS-011", False,
                "Section 192 TDS must be reported in Schedule TDS1, not TDS3.",
                f"tds3_entries[{index}].tds_section", "not 192", entry.tds_section,
            ))

    # CBDT rule 647: Section 80DDB claims require the specified-disease
    # evidence object that is carried by the canonical deduction model.
    if ch6a is not None and ch6a.amount_80ddb > _ZERO and ch6a.details_80ddb is None:
        results.append(_result(
            "ITR2-IN-VIA-012", False,
            "A Section 80DDB claim requires specified-disease details.",
            "deductions_chapter6a.details_80ddb", "present", "absent",
        ))

    # CBDT rule 652: the identity date must precede the financial year start
    # for AY 2026-27 (1 April 2025).
    profile_date = getattr(inp.filing_profile, "date_of_birth_or_formation", None) if inp.filing_profile is not None else None
    if profile_date is not None and profile_date >= date(2025, 4, 1):
        results.append(_result(
            "ITR2-IN-PROFILE-001", False,
            "Date of birth or formation must precede 1 April of the assessment year's financial year.",
            "filing_profile.date_of_birth_or_formation", "< 2025-04-01",
            str(profile_date),
        ))

    # CBDT rule 653: Schedule HP interest claims require corresponding filing
    # detail, preventing an interest amount from being emitted without the
    # property identity/address row required by the official return.
    if any(hp.home_loan_interest_paid > _ZERO for hp in hp_rows):
        if len(inp.property_filing_details) < len(hp_rows):
            results.append(_result(
                "ITR2-IN-HP-008", False,
                "House-property interest claims require corresponding property filing details.",
                "property_filing_details", f"at least {len(hp_rows)} rows",
                str(len(inp.property_filing_details)),
            ))

    # CBDT rules 658/659: 80CCH is restricted to eligible Central Government
    # employment and the AY-specific age band.
    if ch6a is not None and ch6a.amount_80cch > _ZERO:
        central_employment = any(
            detail.nature_of_employment == "CGOV"
            for detail in inp.employer_filing_details
        )
        if not central_employment:
            results.append(_result(
                "ITR2-IN-VIA-010", False,
                "Section 80CCH requires Central Government employment details.",
                "employer_filing_details", "one nature_of_employment == CGOV", "none",
            ))
        if profile_date is not None:
            dob = profile_date
            as_of = date(2025, 4, 1)
            age = as_of.year - dob.year - ((as_of.month, as_of.day) < (dob.month, dob.day))
            if age < 17 or age > 27:
                results.append(_result(
                    "ITR2-IN-VIA-011", False,
                    "Section 80CCH is available only for age 17 through 27 on 1 April 2025.",
                    "filing_profile.date_of_birth_or_formation", "age 17..27", str(age),
                ))
        # CBDT rules (ITR-1's own already-shipped ITR1-R186/R186h; ITR-4's
        # ITR4-R073-2/R317): 80CCH also requires a PRAN number and is capped
        # at the lower of 46.2% of Salary u/s 17(1) and ₹2,88,000. ITR-2's own
        # official validation-rules PDF states a conflicting "60% of salary"
        # figure (rule #347) with no absolute cap at all -- since Section
        # 80CCH is one Income Tax Act provision, not form-specific, and two
        # of the three examined forms' official PDFs (ITR-1, ITR-4)
        # independently agree on 46.2%/₹2,88,000, that figure is treated as
        # correct and ITR-2's "60%" text as an isolated drafting error in
        # CBDT's own PDF, not followed. This corrects
        # Docs/ITR2_VALIDATOR_GAP_MAPPING_AY2026_27.md's 2026-09-11 (Phase 6b)
        # retraction of this same finding, made without checking the primary
        # PDF sources directly -- see that doc's updated note.
        if not inp.pran_number:
            results.append(_result(
                "ITR2-IN-VIA-013", False,
                "Section 80CCH (Agniveer Corpus Fund) claim requires a PRAN number.",
                "pran_number", "present", "absent",
            ))
        if ch6a.amount_80cch > Decimal("288000"):
            results.append(_result(
                "ITR2-IN-VIA-014", False,
                "Section 80CCH deduction cannot exceed ₹2,88,000.",
                "deductions_chapter6a.amount_80cch", "<= 288000", str(ch6a.amount_80cch),
            ))
        if sal is not None and sal.gross_salary > _ZERO:
            _cch_limit = sal.gross_salary * Decimal("0.462")
            if ch6a.amount_80cch > _cch_limit:
                results.append(_result(
                    "ITR2-IN-VIA-015", False,
                    f"Section 80CCH deduction exceeds 46.2% of Salary u/s 17(1) "
                    f"(₹{sal.gross_salary}) = ₹{_cch_limit}.",
                    "deductions_chapter6a.amount_80cch", f"<= {_cch_limit}", str(ch6a.amount_80cch),
                ))

    # CBDT rules 610/653: Schedule HP's own Table 24(b) loan-detail rows
    # (`PropertyFilingDetail.home_loan_details`) must actually be populated
    # when a Section 24(b) interest claim exists -- distinct from the
    # already-shipped `ITR2-IN-HP-008` (which only checks that a matching
    # property *identity/address* row exists, not that its own loan-detail
    # sub-table is non-empty). Checked in aggregate (at least one loan-detail
    # row exists anywhere) rather than per-property-index, since `hp_rows`
    # above and `_schedule_hp()`'s own `sources` list order
    # `house_property_income` at opposite ends and are not safely
    # index-matchable against `property_filing_details` here.
    if any(hp.home_loan_interest_paid > _ZERO for hp in hp_rows):
        if not any(detail.home_loan_details for detail in inp.property_filing_details):
            results.append(_result(
                "ITR2-IN-HP-009", False,
                "A Section 24(b) home-loan-interest claim requires at least one loan-detail row "
                "(lender, sanction date, amounts) in Schedule HP's own Table 24(b).",
                "property_filing_details[].home_loan_details", "at least one row", "none",
            ))

    # CBDT rules 305-310: Schedule 80D's own senior-citizen dropdown flags
    # must agree with which premium bucket actually carries a claim.
    sch_80d = inp.schedule_80d
    if sch_80d is not None:
        if sch_80d.premium_1a_non_senior > _ZERO and sch_80d.has_self_senior:
            results.append(_result(
                "ITR2-IN-VIA-016", False,
                'Select "No" for the Self/Family senior-citizen dropdown when the premium is '
                "claimed in the non-senior bucket (Sl.1a).",
                "schedule_80d.has_self_senior", False, True,
            ))
        if sch_80d.premium_1b_senior > _ZERO and not sch_80d.has_self_senior:
            results.append(_result(
                "ITR2-IN-VIA-017", False,
                'Select "Yes" for the Self/Family senior-citizen dropdown when the premium is '
                "claimed in the senior-citizen bucket (Sl.1b).",
                "schedule_80d.has_self_senior", True, False,
            ))
        if sch_80d.premium_2a_parents_non_senior > _ZERO and sch_80d.has_parents_senior:
            results.append(_result(
                "ITR2-IN-VIA-018", False,
                'Select "No" for the Parents senior-citizen dropdown when the premium is claimed '
                "in the non-senior bucket (Sl.2a).",
                "schedule_80d.has_parents_senior", False, True,
            ))
        if sch_80d.premium_2b_parents_senior > _ZERO and not sch_80d.has_parents_senior:
            results.append(_result(
                "ITR2-IN-VIA-019", False,
                'Select "Yes" for the Parents senior-citizen dropdown when the premium is '
                "claimed in the senior-citizen bucket (Sl.2b).",
                "schedule_80d.has_parents_senior", True, False,
            ))
        # Rows #309/#310 (duplicate catalog entries): "select Yes/No" in the
        # general sense is already structurally enforced by the four checks
        # above covering every combination of bucket vs. flag.

    # CBDT rule 349: Section 80TTB (senior-citizen deposit-interest
    # deduction) is not available to a non-resident.
    if ch6a is not None and ch6a.amount_80ttb > _ZERO and inp.residential_status == ResidentialStatus.NON_RESIDENT:
        results.append(_result(
            "ITR2-IN-VIA-020", False,
            "Section 80TTB cannot be claimed by a non-resident.",
            "deductions_chapter6a.amount_80ttb", _ZERO, str(ch6a.amount_80ttb),
        ))

    # CBDT rules 356/357: Schedule 80GGC's own per-contribution detail rows
    # must carry a contribution date when any amount is claimed, and
    # non-cash-mode-specific detail when claimed via a non-cash mode.
    if inp.schedule_80ggc is not None:
        for _idx, _contrib in enumerate(inp.schedule_80ggc.contributions):
            if _contrib.amount > _ZERO and _contrib.contribution_date is None:
                results.append(_result(
                    "ITR2-IN-VIA-021", False,
                    "A Section 80GGC contribution row requires a contribution date when an "
                    "amount is claimed.",
                    f"schedule_80ggc.contributions[{_idx}].contribution_date", "present", "absent",
                ))
            if _contrib.other_mode_amount > _ZERO and not (_contrib.transaction_ref and _contrib.ifsc_code):
                results.append(_result(
                    "ITR2-IN-VIA-022", False,
                    "A Section 80GGC contribution made other than in cash requires transaction "
                    "reference and IFSC details.",
                    f"schedule_80ggc.contributions[{_idx}]",
                    "transaction_ref and ifsc_code present", "missing",
                ))
        # CBDT rule 697: the political party's own name and PAN are required
        # whenever any contribution is claimed at all.
        if inp.schedule_80ggc.total_claimed > _ZERO or any(
            c.amount > _ZERO for c in inp.schedule_80ggc.contributions
        ):
            if not (inp.schedule_80ggc.political_party_name and inp.schedule_80ggc.political_party_pan):
                results.append(_result(
                    "ITR2-IN-VIA-023", False,
                    "Section 80GGC requires the political party's name and PAN.",
                    "schedule_80ggc", "political_party_name and political_party_pan present",
                    "missing",
                ))

    # CBDT rules 363/365: Schedule 80U/80DD require supporting-certificate
    # detail (Form 10-IA acknowledgement or UDID) whenever a deduction is
    # actually claimed.
    if inp.schedule_80u is not None and inp.schedule_80u.deduction_amount > _ZERO:
        if not (inp.schedule_80u.form_10ia_ack_number or inp.schedule_80u.udid_number):
            results.append(_result(
                "ITR2-IN-VIA-024", False,
                "Section 80U requires a Form 10-IA acknowledgement number or UDID when a "
                "deduction is claimed.",
                "schedule_80u", "form_10ia_ack_number or udid_number present", "missing",
            ))
    if inp.schedule_80dd is not None and inp.schedule_80dd.deduction_amount > _ZERO:
        if not (inp.schedule_80dd.form_10ia_ack_number or inp.schedule_80dd.udid_number):
            results.append(_result(
                "ITR2-IN-VIA-025", False,
                "Section 80DD requires a Form 10-IA acknowledgement number or UDID when a "
                "deduction is claimed.",
                "schedule_80dd", "form_10ia_ack_number or udid_number present", "missing",
            ))

    # CBDT rule 642: Schedule 80C's own per-row detail must be present
    # (payment type and policy/document identifier) when that row claims a
    # nonzero amount.
    for _idx, _entry in enumerate(inp.schedule_80c_entries):
        if _entry.amount > _ZERO and not (_entry.payment_type and _entry.identifier_number):
            results.append(_result(
                "ITR2-IN-VIA-026", False,
                "A Schedule 80C row requires a payment type and policy/document identifier "
                "when an amount is claimed.",
                f"schedule_80c_entries[{_idx}]", "payment_type and identifier_number present",
                "missing",
            ))

    # CBDT rules 623/624/626/629: Schedule 80E/80EE/80EEA/80EEB each require
    # at least one loan-detail row when the corresponding deduction is
    # claimed (the row's OWN required fields -- lender, account reference,
    # loan date, amounts -- are already schema-enforced by
    # `OfficialDeductionLoanEntry` the moment a row is constructed, so only
    # the row's *existence* needs checking here).
    if ch6a is not None:
        _loan_backed_deductions = (
            ("80E", ch6a.amount_80e, inp.schedule_80e_entries, "schedule_80e_entries"),
            ("80EE", ch6a.amount_80ee, inp.loan_details_80ee_list, "loan_details_80ee_list"),
            ("80EEA", ch6a.amount_80eea, inp.loan_details_80eea_list, "loan_details_80eea_list"),
            ("80EEB", ch6a.amount_80eeb, inp.loan_details_80eeb_list, "loan_details_80eeb_list"),
        )
        for _section, _amount, _entries, _field in _loan_backed_deductions:
            if _amount > _ZERO and not _entries:
                results.append(_result(
                    "ITR2-IN-VIA-027", False,
                    f"Section {_section} requires at least one loan-detail row when a deduction "
                    "is claimed.",
                    _field, "at least one row", "none",
                ))

        # CBDT rules 628/630/639: each loan-entry class's own sanction-date
        # window (distinct statutory eligibility periods per section).
        _loan_date_windows = (
            ("80EE", inp.loan_details_80ee_list, date(2016, 4, 1), date(2017, 3, 31)),
            ("80EEA", inp.loan_details_80eea_list, date(2019, 4, 1), date(2022, 3, 31)),
            ("80EEB", inp.loan_details_80eeb_list, date(2019, 4, 1), date(2023, 3, 31)),
        )
        for _section, _entries, _start, _end in _loan_date_windows:
            for _idx, _entry in enumerate(_entries):
                if not (_start <= _entry.loan_date <= _end):
                    results.append(_result(
                        "ITR2-IN-VIA-028", False,
                        f"Section {_section}'s loan must be sanctioned between {_start} and "
                        f"{_end}.",
                        f"loan_details_{_section.lower()}_list[{_idx}].loan_date",
                        f"{_start}..{_end}", str(_entry.loan_date),
                    ))

    # CBDT rules 687-690/696: Schedule 80G's own per-donation detail (donee
    # name/PAN/address) is required when a non-cash-mode contribution is
    # claimed, and the donee PAN specifically is required for any donation
    # (cash or non-cash) above zero -- across all four Sl.A/B/C/D blocks
    # (`donation_category`).
    if ch6a is not None and ch6a.donations_80g:
        for _idx, _don in enumerate(ch6a.donations_80g):
            _total_donation = _don.cash_amount + _don.non_cash_amount
            if _total_donation > _ZERO and not _don.donee_pan:
                results.append(_result(
                    "ITR2-IN-VIA-029", False,
                    "A Schedule 80G donation row requires the donee's PAN when an amount is "
                    "claimed.",
                    f"deductions_chapter6a.donations_80g[{_idx}].donee_pan", "present", "absent",
                ))
            if _don.non_cash_amount > _ZERO and not (_don.donee_name and _don.address):
                results.append(_result(
                    "ITR2-IN-VIA-030", False,
                    "A Schedule 80G donation row made in a non-cash mode requires the donee's "
                    "name and address.",
                    f"deductions_chapter6a.donations_80g[{_idx}]",
                    "donee_name and address present", "missing",
                ))

    # CBDT rules 277/313: a donee's PAN cannot equal the filer's own PAN (or
    # Karta's PAN for a HUF) at either Schedule 80G or Schedule 80GGA.
    _filer_pans = set()
    if inp.filing_profile is not None:
        _own_pan = getattr(inp.filing_profile, "pan", None)
        _own_karta_pan = getattr(inp.filing_profile, "karta_pan", None)
        if _own_pan:
            _filer_pans.add(_own_pan)
        if _own_karta_pan:
            _filer_pans.add(_own_karta_pan)
    if _filer_pans and ch6a is not None:
        for _idx, _don in enumerate(ch6a.donations_80g or []):
            if _don.donee_pan and _don.donee_pan in _filer_pans:
                results.append(_result(
                    "ITR2-IN-VIA-031", False,
                    "A Schedule 80G donee's PAN cannot be the same as the assessee's own PAN.",
                    f"deductions_chapter6a.donations_80g[{_idx}].donee_pan",
                    "!= assessee PAN", _don.donee_pan,
                ))
        if inp.schedule_80gga is not None:
            for _idx, _don in enumerate(inp.schedule_80gga.donations):
                if _don.donee_pan in _filer_pans:
                    results.append(_result(
                        "ITR2-IN-VIA-032", False,
                        "A Schedule 80GGA donee's PAN cannot be the same as the assessee's own "
                        "PAN.",
                        f"schedule_80gga.donations[{_idx}].donee_pan",
                        "!= assessee PAN", _don.donee_pan,
                    ))

    # CBDT rule 290: the same donee PAN cannot appear in more than one
    # Schedule 80G qualifying-percentage/limit block (`donation_category`),
    # except the CBDT-published exempt PAN "AAAAR1077P" (PM National Relief
    # Fund and similarly always-100%-eligible funds are exempted from this
    # check on the official form itself).
    if ch6a is not None and ch6a.donations_80g:
        _pan_categories: dict[str, set[str]] = {}
        for _don in ch6a.donations_80g:
            if _don.donee_pan and _don.donee_pan != "AAAAR1077P":
                _pan_categories.setdefault(_don.donee_pan, set()).add(_don.donation_category)
        for _pan, _cats in _pan_categories.items():
            if len(_cats) > 1:
                results.append(_result(
                    "ITR2-IN-VIA-033", False,
                    "The same donee PAN cannot appear in more than one Schedule 80G "
                    "qualifying-percentage/limit block.",
                    "deductions_chapter6a.donations_80g[].donee_pan",
                    "one donation_category per PAN", f"{_pan}: {sorted(_cats)}",
                ))

    # CBDT rule 747: the representative assessee's own contact details
    # cannot match the taxpayer's own (a representative is, by definition,
    # a distinct person acting on the assessee's behalf).
    _rep = getattr(inp.filing_profile, "assessee_representative", None) if inp.filing_profile is not None else None
    _own = getattr(inp.filing_profile, "primary_address", None) if inp.filing_profile is not None else None
    if _rep is not None and _own is not None:
        if _rep.email.strip().lower() == _own.email.strip().lower():
            results.append(_result(
                "ITR2-IN-PROFILE-004", False,
                "The representative assessee's email cannot match the taxpayer's own email.",
                "filing_profile.assessee_representative.email", "!= own email", _rep.email,
            ))
        if _rep.mobile_no == _own.mobile_no:
            results.append(_result(
                "ITR2-IN-PROFILE-005", False,
                "The representative assessee's mobile number cannot match the taxpayer's own.",
                "filing_profile.assessee_representative.mobile_no", "!= own mobile_no",
                _rep.mobile_no,
            ))

    # CBDT rules 520/521: a Schedule IT payment's own chosen classification
    # (advance tax vs. self-assessment tax) must agree with its own
    # payment_date against the financial-year-end cutoff, rather than
    # trusting a manually-selected tag the calculator's own classification
    # already relies on unchecked.
    _fy_end = _financial_year_end(inp)
    for _idx, _pmt in enumerate(inp.tax_payment_entries):
        if _pmt.payment_date is None:
            continue
        if _pmt.payment_type == "self_assessment" and _pmt.payment_date <= _fy_end:
            results.append(_result(
                "ITR2-IN-IT-001", False,
                "A payment dated on or before the financial year end cannot be tagged "
                "self-assessment tax.",
                f"tax_payment_entries[{_idx}].payment_type", "advance", "self_assessment",
            ))
        if _pmt.payment_type == "advance" and _pmt.payment_date > _fy_end:
            results.append(_result(
                "ITR2-IN-IT-002", False,
                "A payment dated after the financial year end cannot be tagged advance tax.",
                f"tax_payment_entries[{_idx}].payment_type", "self_assessment", "advance",
            ))

    # CBDT rule 550: opting out of the new tax regime is not available after
    # the section 139(1) due date.
    if (
        inp.filing_profile is not None
        and inp.filing_profile.opted_out_new_tax_regime
        and inp.filing_date is not None and inp.due_date is not None
        and inp.filing_date > inp.due_date
    ):
        results.append(_result(
            "ITR2-IN-PROFILE-006", False,
            "Opting out of the new tax regime is not available after the section 139(1) due "
            "date.",
            "filing_profile.opted_out_new_tax_regime", False, True,
        ))

    # CBDT rules 173/174: a Schedule 112A/115AD scrip acquired on or after
    # 1 February 2018 (`is_before_31jan2018=False`) has no grandfathering
    # FMV comparison to make -- Col.10/11 (fmv_per_share/total_fmv) must be
    # blank/zero for such a scrip, since they have no computational effect
    # once `is_before_31jan2018` is false and disclosing a nonzero value
    # anyway would misrepresent the scrip as grandfathering-eligible.
    for _label, _scrip_list in (("cg_112a_scrips", inp.cg_112a_scrips), ("cg_115ad_scrips", inp.cg_115ad_scrips)):
        for _idx, _scrip in enumerate(_scrip_list):
            if not _scrip.is_before_31jan2018 and (_scrip.fmv_per_share > _ZERO or _scrip.total_fmv > _ZERO):
                results.append(_result(
                    "ITR2-IN-CG-109" if _label == "cg_112a_scrips" else "ITR2-IN-CG-110",
                    False,
                    "FMV/total FMV must be zero for a scrip acquired on or after 1 February "
                    "2018 (not eligible for section 112A/115AD grandfathering).",
                    f"{_label}[{_idx}].fmv_per_share/total_fmv", "0 when not is_before_31jan2018",
                    f"fmv_per_share={_scrip.fmv_per_share}, total_fmv={_scrip.total_fmv}",
                ))

    # CBDT rule 662: every CGAS claim must point to a disclosed CGAS bank
    # account, matched by account number and account type.
    for index, tx in enumerate(inp.cg_transactions or []):
        for claim_index, claim in enumerate(tx.exemptions):
            if claim.cgas_deposit_amount > _ZERO:
                matched = any(
                    account.account_number == claim.cgas_account_number
                    and account.account_type.strip().upper() == "CGAS"
                    and account.ifsc_code.strip().upper() == (claim.cgas_ifsc or "").strip().upper()
                    for account in inp.bank_accounts
                )
                if not matched:
                    results.append(_result(
                        "ITR2-IN-CG-010", False,
                        "CGAS deposit details must match a disclosed CGAS bank account.",
                        f"cg_transactions[{index}].exemptions[{claim_index}].cgas_account_number",
                        "matching CGAS bank account", claim.cgas_account_number,
                    ))

    # Category D reminders (Category B/D rules 5/6 of 26): these are the
    # non-blocking half of Phase 5E — CBDT flags the return as uploadable but
    # warns that the claim may be disallowed unless the taxpayer separately
    # files the named form. Both `relief_89` and `amount_80gg` are real,
    # calculator-consumed fields (unlike the vestigial AMTInput ones below),
    # so this is a genuine reminder, not noise on a dead field.
    if inp.relief_89 > _ZERO:
        results.append(_result(
            "ITR2-IN-FORM-001", True,
            "Relief u/s 89 is claimed — Form 10E must be filed separately to "
            "sustain this claim.",
            "relief_89", severity=Severity.D,
        ))
    if inp.deductions_chapter6a is not None and inp.deductions_chapter6a.amount_80gg > _ZERO:
        results.append(_result(
            "ITR2-IN-FORM-002", True,
            "Deduction u/s 80GG (rent paid) is claimed — Form 10BA must be "
            "filed separately to sustain this claim.",
            "deductions_chapter6a.amount_80gg", severity=Severity.D,
        ))

    # AMT-001/002 below check `amt_tax`/`adjusted_total_income`/
    # `amt_credit_*` — confirmed by grep of app/engine/calculators/itr2.py
    # that NONE of these four `AMTInput` fields are ever read by the
    # calculator (only `.deduction_10aa`/`.deduction_80ia_to_80rrb_except_80p`/
    # `.deduction_35ad_net_depreciation` are); `_map_amt_input` in
    # draft_to_itr2_input.py never sets them either, so they sit at their
    # Pydantic zero-defaults for every real draft, which is why these two
    # pre-existing rules are harmless in production (0 == 0*rate) rather
    # than a landmine — but they are also not exercising anything real.
    # Left as-is (pre-existing, not part of this phase's scope to remove);
    # the genuinely computed AMT figure is `result.amt_tax`, already
    # covered by ITR2-CALC-009 (total tax reconciliation) and the
    # nonnegative-fields sweep in ITR2-CALC-021.
    if inp.amt_input is not None:
        amt = inp.amt_input
        expected_amt = amt.adjusted_total_income * amt.amt_rate_pct / Decimal("100")
        if abs(amt.amt_tax - expected_amt) > Decimal("1"):
            results.append(_result(
                "ITR2-IN-AMT-001", False,
                "AMT tax must equal adjusted total income multiplied by the AMT rate.",
                "amt_input.amt_tax", str(expected_amt), str(amt.amt_tax),
            ))
        if amt.amt_credit_utilised > amt.amt_credit_brought_forward:
            results.append(_result(
                "ITR2-IN-AMT-002", False,
                "AMT credit utilised cannot exceed credit brought forward.",
                "amt_input.amt_credit_utilised", f"<= {amt.amt_credit_brought_forward}",
                str(amt.amt_credit_utilised),
            ))
        # CBDT rule 421: Schedule AMT Sl.2a (Chapter VI-A "C"-heading
        # additions) must equal the sum of the taxpayer's own actual claimed
        # 80-IA-to-80RRB-except-80P deductions -- these ARE genuinely
        # itemized elsewhere on `Chapter6ADeductions` (unlike this rule's
        # own evidence text, which described a single opaque manual
        # aggregate; the real gap is that `amt_input.deduction_*` is a
        # SEPARATE, independently-editable field never cross-checked
        # against the taxpayer's own actual claims).
        if ch6a is not None:
            # The rule's own literal text names 80QQB/80RRB specifically
            # (`ITR2Input.deduction_80qqb`/`deduction_80rrb`, Phase 6b) --
            # included alongside every other field this codebase actually
            # tracks within the official 80-IA-to-80-RRB-except-80P range
            # (`Chapter6ADeductions.amount_80ia`/`80ib`/`80ic`/`80ra`) for the
            # most complete, defensible reading of what `AMTInput`'s own
            # field name promises, rather than the rule's narrower two-
            # section text alone.
            _expected_80ia_addition = (
                ch6a.amount_80ia + ch6a.amount_80ib + ch6a.amount_80ic + ch6a.amount_80ra
                + inp.deduction_80qqb + inp.deduction_80rrb
            )
            if amt.deduction_80ia_to_80rrb_except_80p != _expected_80ia_addition:
                results.append(_result(
                    "ITR2-IN-AMT-003", False,
                    "Schedule AMT's 80-IA-to-80RRB addition must equal the sum of the "
                    "taxpayer's own actual claimed 80IA/80IB/80IC/80RA deductions.",
                    "amt_input.deduction_80ia_to_80rrb_except_80p",
                    str(_expected_80ia_addition), str(amt.deduction_80ia_to_80rrb_except_80p),
                ))
            if amt.deduction_10aa != ch6a.amount_10aa:
                results.append(_result(
                    "ITR2-IN-AMT-004", False,
                    "Schedule AMT's Section 10AA addition must equal the taxpayer's own "
                    "actual claimed Section 10AA deduction.",
                    "amt_input.deduction_10aa", str(ch6a.amount_10aa), str(amt.deduction_10aa),
                ))

    # CBDT rule 466/467: claimed cannot exceed deducted PLUS brought-forward —
    # not deducted alone. `draft_to_itr1_input._map_tds` maps a real,
    # user-editable draft field (`TdsCredit.broughtFwdTDSAmt`) into
    # `brought_forward_tds`, so omitting it here would reject a taxpayer
    # legitimately claiming brought-forward TDS credit alongside this year's
    # deduction — a live false-rejection risk, not just a theoretical one.
    # `TDS3Entry` carries the identical check as a schema-level
    # `@model_validator` in app/schemas/itr1.py (shared with ITR-1) — that
    # one had the exact same bug (ignored `brought_forward_tds`) and was
    # fixed there instead, since a schema-level fix is the correct location.
    # No separate rule is needed here for TDS3 as a result: a `TDS3Entry`
    # violating the ceiling cannot be constructed at all, so a validator
    # re-checking it here would be unreachable dead code.
    for index, entry in enumerate(inp.tds2_entries or []):
        ceiling = entry.tds_deducted + entry.brought_forward_tds
        if entry.tds_claimed_this_year > ceiling:
            results.append(_result(
                "ITR2-IN-TDS-001", False,
                "TDS claimed this year cannot exceed TDS deducted plus brought-forward TDS.",
                f"tds2_entries[{index}].tds_claimed_this_year",
                f"<= {ceiling}", str(entry.tds_claimed_this_year),
            ))
    for index, entry in enumerate(inp.tcs_entries or []):
        if entry.tcs_credit_claimed > entry.tcs_collected:
            results.append(_result(
                "ITR2-IN-TCS-001", False,
                "TCS credit claimed cannot exceed TCS collected.",
                f"tcs_entries[{index}].tcs_credit_claimed",
                f"<= {entry.tcs_collected}", str(entry.tcs_credit_claimed),
            ))

    # CBDT rules 469/475: TDS2/TDS3/TCS credit ownership marked "Other" (or
    # "spouse/other" for TCS) requires the other person's PAN.
    for index, entry in enumerate(inp.tds2_entries or []):
        if entry.ownership == "O" and not entry.pan_of_other_person:
            results.append(_result(
                "ITR2-IN-TDS-020", False,
                "A TDS credit relating to another person requires that person's PAN.",
                f"tds2_entries[{index}].pan_of_other_person", "present", "absent",
            ))
    for index, entry in enumerate(inp.tds3_entries or []):
        if entry.ownership == "O" and not entry.pan_of_other_person:
            results.append(_result(
                "ITR2-IN-TDS-020", False,
                "A TDS credit relating to another person requires that person's PAN.",
                f"tds3_entries[{index}].pan_of_other_person", "present", "absent",
            ))
    for index, entry in enumerate(inp.tcs_entries or []):
        if entry.ownership == "2" and not entry.pan_of_spouse_or_other_person:
            results.append(_result(
                "ITR2-IN-TCS-002", False,
                "A TCS credit relating to a spouse/other person requires that person's PAN.",
                f"tcs_entries[{index}].pan_of_spouse_or_other_person", "present", "absent",
            ))

    # CBDT rule 473: mirrors TDS2's already-shipped ITR2-IN-TDS-006 -- a TCS
    # row cannot report both brought-forward TCS and current-year collection
    # together; they belong in separate rows.
    for index, entry in enumerate(inp.tcs_entries or []):
        if entry.brought_forward_tds > _ZERO and entry.tcs_collected > _ZERO:
            results.append(_result(
                "ITR2-IN-TCS-005", False,
                "Current-year TCS and brought-forward TCS must be reported in separate TCS "
                "rows.",
                f"tcs_entries[{index}]", "not both current-year and brought-forward credit",
                f"brought_forward={entry.brought_forward_tds}, collected={entry.tcs_collected}",
            ))

    # CBDT rule 474: the full statutory TCS ceiling -- claimed in own hands
    # PLUS spouse/other-person hands cannot exceed collected (own hands) plus
    # collected (spouse/other hands) plus brought-forward. `ITR2-IN-TCS-001`
    # above only checks the narrower `tcs_credit_claimed <= tcs_collected`
    # pair, omitting brought-forward and the spouse/other dimension entirely.
    for index, entry in enumerate(inp.tcs_entries or []):
        _tcs_claimed_total = entry.tcs_credit_claimed + entry.tcs_credit_claimed_spouse_or_other
        _tcs_ceiling = entry.tcs_collected + entry.tcs_collected_spouse_or_other + entry.brought_forward_tds
        if _tcs_claimed_total > _tcs_ceiling:
            results.append(_result(
                "ITR2-IN-TCS-003", False,
                "Total TCS credit claimed (own hands plus spouse/other person) cannot exceed "
                "TCS collected (own plus spouse/other) plus brought-forward TCS.",
                f"tcs_entries[{index}]", f"<= {_tcs_ceiling}", str(_tcs_claimed_total),
            ))

    # CBDT rule 478: TCS credit carried forward must equal collected plus
    # brought-forward minus claimed this year (column 5+6-7).
    for index, entry in enumerate(inp.tcs_entries or []):
        _tcs_expected_cf = max(
            _ZERO,
            entry.tcs_collected + entry.brought_forward_tds - entry.tcs_credit_claimed,
        )
        if entry.tds_credit_carried_forward != _tcs_expected_cf:
            results.append(_result(
                "ITR2-IN-TCS-004", False,
                "TCS credit carried forward must equal collected plus brought-forward minus "
                "claimed this year.",
                f"tcs_entries[{index}].tds_credit_carried_forward",
                str(_tcs_expected_cf), str(entry.tds_credit_carried_forward),
            ))

    # Filing-evidence count checks
    #
    # Audit finding §22.3: this used to require len(employer_filing_details)
    # == len(tds1_entries) whenever employer_filing_details was non-empty,
    # even when tds1_entries was legitimately empty (a salaried employee
    # whose employer deducted zero TDS -- first job, income below the TDS
    # threshold, a Section 197 nil-deduction certificate). _schedule_s()
    # (app/engine/itd/itr2.py) only enforces the count match when
    # tds1_entries is itself non-empty -- ported that same guard here so the
    # validator doesn't reject a return the builder would have accepted.
    if inp.tds1_entries and len(inp.employer_filing_details) != len(inp.tds1_entries):
        results.append(_result(
            "ITR2-IN-FE-001", False,
            "employer_filing_details count must match tds1_entries count.",
            "employer_filing_details",
            f"len == {len(inp.tds1_entries)}",
            f"len == {len(inp.employer_filing_details)}",
        ))
    property_count = int(inp.house_property_income is not None) + len(inp.house_properties)
    if inp.property_filing_details and len(inp.property_filing_details) != property_count:
        results.append(_result(
            "ITR2-IN-FE-002", False,
            "property_filing_details count must match house property count.",
            "property_filing_details",
            f"len == {property_count}",
            f"len == {len(inp.property_filing_details)}",
        ))
    if inp.tds3_filing_details and len(inp.tds3_filing_details) != len(inp.tds3_entries):
        results.append(_result(
            "ITR2-IN-FE-003", False,
            "tds3_filing_details count must match tds3_entries count.",
            "tds3_filing_details",
            f"len == {len(inp.tds3_entries)}",
            f"len == {len(inp.tds3_filing_details)}",
        ))

    # ── Category B/D advisories (Phase 6a) ──────────────────────────────────
    # Non-blocking Severity.D reminders, matching the ITR2-IN-FORM-001/002
    # pattern -- `passed=True` (informational), not a rejection. Wired to
    # existing fields per Docs/ITR2_VALIDATOR_GAP_MAPPING_AY2026_27.md's
    # Category B/D findings; each was a real, representable scenario with no
    # advisory reading the data before this pass.

    # B/D #3: Form 67 is required to sustain a foreign-tax-relief claim u/s
    # 90/90A/91 -- TR1Entry.form67_filed already captures exactly this fact.
    for index, tr1 in enumerate(inp.tr1_entries or []):
        if tr1.relief_claimed > _ZERO and not tr1.form67_filed:
            results.append(_result(
                "ITR2-IN-FORM-004", True,
                "Foreign tax relief is claimed -- Form 67 must be filed separately "
                "to sustain this claim.",
                f"tr1_entries[{index}].relief_claimed", severity=Severity.D,
            ))

    # B/D #21 (Phase 6i-1, 2026-09-11): Form 10F is mandatory for a
    # non-resident to claim the benefit of a DTAA treaty-preferential rate
    # -- without it, the TRC flag itself is considered "No" regardless of
    # what's claimed. Narrower than Form 67's own condition above: only
    # sections 90/90A are treaty-based (91 is unilateral relief, no treaty
    # involved, so Form 10F/TRC are not applicable there), and only a
    # non-resident is in scope, per the rule's own literal text. Deferred
    # in Phase 6a since `form_10f_filed` didn't exist on TR1Entry yet.
    for index, tr1 in enumerate(inp.tr1_entries or []):
        if (
            inp.residential_status == ResidentialStatus.NON_RESIDENT
            and tr1.relief_section in ("90", "90A")
            and tr1.relief_claimed > _ZERO
            and not tr1.form_10f_filed
        ):
            results.append(_result(
                "ITR2-IN-FORM-007", True,
                "Form 10F must be filed to claim a DTAA treaty-preferential rate as a "
                "non-resident -- without it, the TRC claim is treated as 'No'.",
                f"tr1_entries[{index}].relief_claimed", severity=Severity.D,
            ))

    # B/D #4: Form 3CFA is required within the due date when income is
    # returned under Section 115BBF (patent royalty).
    for index, si in enumerate(inp.si_entries or []):
        if si.section == "115BBF" and si.gross_income > _ZERO:
            results.append(_result(
                "ITR2-IN-FORM-005", True,
                "Income is returned under Section 115BBF -- Form 3CFA must be "
                "furnished within the due date to sustain this claim.",
                f"si_entries[{index}].gross_income", severity=Severity.D,
            ))

    # B/D #8/#18 (duplicate-in-substance in the official catalog): a resident
    # taxpayer cannot claim a DTAA-preferential rate via Schedule OS's own
    # NRI-facing DTAA table (OSDtaaEntry models the official
    # "NRIDTAADtlsSchOS" block by name) -- residents claim DTAA relief
    # through Schedule TR/FSI instead.
    if inp.residential_status == ResidentialStatus.RESIDENT and inp.os_dtaa_entries:
        results.append(_result(
            "ITR2-IN-DTAA-001", True,
            "Resident taxpayers cannot claim a DTAA-preferential rate via "
            "Schedule OS -- DTAA benefit is claimed through Schedule TR and FSI "
            "instead. Please re-check the claim.",
            "os_dtaa_entries", severity=Severity.D,
        ))

    # CBDT rule 127 (Sch CG A8 Col.10, Phase 6e, 2026-09-11): the applicable
    # DTAA rate a taxpayer claims cannot exceed the lower of the treaty rate
    # and the domestic IT Act rate -- the whole point of a tax treaty is
    # relief, never a rate worse than either side's own figure.
    # OSDtaaEntry.applicable_rate is a free-standing field with no
    # model_validator or pre-compute check comparing it to
    # min(rate_as_per_treaty, rate_as_per_it_act). No distinct Schedule-CG-
    # side DTAA table is representable in ITR2Input at all (the official
    # schema's own NRICgDTAA/NRITaxUsDTAALtcgType block -- a genuinely
    # separate structure from this OS table, keyed by CG-specific item codes
    # like "A1e"/"A2e_111A" -- has no corresponding ITR2Input field and the
    # calculator's compute_stcg()/compute_ltcg() dtaa parameters are never
    # populated from any real transaction data anywhere in this pipeline;
    # this is a genuinely separate, deeper architectural gap, deliberately
    # not addressed by this rule -- see Docs/
    # ITR2_VALIDATOR_GAP_MAPPING_AY2026_27.md Phase 6e for the full write-up
    # and why it needs its own dedicated phase, not a validator addition.
    for index, entry in enumerate(inp.os_dtaa_entries):
        _dtaa_ceiling = min(entry.rate_as_per_treaty, entry.rate_as_per_it_act)
        if entry.applicable_rate > _dtaa_ceiling:
            results.append(_result(
                "ITR2-IN-DTAA-002", False,
                "The applicable DTAA rate cannot exceed the lower of the treaty "
                "rate and the IT Act rate.",
                f"os_dtaa_entries[{index}].applicable_rate", f"<= {_dtaa_ceiling}",
                str(entry.applicable_rate),
            ))

    # CBDT rule 127's own capital-gains sibling (Phase 6i-5, 2026-09-12):
    # the comment above predicted this exact gap ("no corresponding
    # ITR2Input field... a genuinely separate, deeper architectural gap") --
    # now closed. Same ceiling check as ITR2-IN-DTAA-002, applied to the two
    # new CG-side DTAA entry lists (Schedule CG items A8/B11).
    for index, entry in enumerate(inp.cg_stcg_dtaa_entries):
        _dtaa_ceiling = min(entry.rate_as_per_treaty, entry.rate_as_per_it_act)
        if entry.applicable_rate > _dtaa_ceiling:
            results.append(_result(
                "ITR2-IN-DTAA-003", False,
                "The applicable DTAA rate cannot exceed the lower of the treaty "
                "rate and the IT Act rate.",
                f"cg_stcg_dtaa_entries[{index}].applicable_rate", f"<= {_dtaa_ceiling}",
                str(entry.applicable_rate),
            ))
    for index, entry in enumerate(inp.cg_ltcg_dtaa_entries):
        _dtaa_ceiling = min(entry.rate_as_per_treaty, entry.rate_as_per_it_act)
        if entry.applicable_rate > _dtaa_ceiling:
            results.append(_result(
                "ITR2-IN-DTAA-004", False,
                "The applicable DTAA rate cannot exceed the lower of the treaty "
                "rate and the IT Act rate.",
                f"cg_ltcg_dtaa_entries[{index}].applicable_rate", f"<= {_dtaa_ceiling}",
                str(entry.applicable_rate),
            ))

    # B/D #12/#13: TDS section codes 194Q/194C/194R/194M under Schedule
    # TDS2/TDS3 indicate business-type income, which may not belong on
    # ITR-2. Checked against the raw user-facing section string
    # (TDS2Entry/TDS3Entry.tds_section) -- the same layer every other
    # TDS-section rule in this file already reads, before any schema-code
    # translation happens at JSON-build time.
    _BUSINESS_INDICATING_TDS_SECTIONS = {"194Q", "194C", "194R", "194M"}
    for index, entry in enumerate(inp.tds2_entries or []):
        if entry.tds_section in _BUSINESS_INDICATING_TDS_SECTIONS:
            results.append(_result(
                "ITR2-IN-TDS-013", True,
                f"TDS section {entry.tds_section} under Schedule TDS2 indicates "
                "business-type income -- please confirm ITR-2 is the correct form.",
                f"tds2_entries[{index}].tds_section", severity=Severity.D,
            ))
    for index, entry in enumerate(inp.tds3_entries or []):
        if entry.tds_section in _BUSINESS_INDICATING_TDS_SECTIONS:
            results.append(_result(
                "ITR2-IN-TDS-014", True,
                f"TDS section {entry.tds_section} under Schedule TDS3 indicates "
                "business-type income -- please confirm ITR-2 is the correct form.",
                f"tds3_entries[{index}].tds_section", severity=Severity.D,
            ))

    # B/D #14/#15/#16/#17: TDS suggests income of a specific special-rate
    # nature was derived, but the return doesn't offer any matching income.
    # Conservative by design (flags "zero of this income type declared at
    # all", not an exact amount reconciliation) -- correct for an advisory
    # that must not false-fire on partial, still-being-entered data.
    has_194s_tds = any(
        e.tds_section == "194S" for e in (list(inp.tds2_entries or []) + list(inp.tds3_entries or []))
    )
    if has_194s_tds and not inp.vda_transactions:
        results.append(_result(
            "ITR2-IN-TDS-015", True,
            "TDS under section 194S suggests virtual digital asset income was "
            "derived this year, but no VDA transaction is disclosed -- please "
            "confirm the income has been fully offered to tax.",
            "vda_transactions", severity=Severity.D,
        ))
    si_sections_present = {si.section for si in (inp.si_entries or [])}
    for tds_section, si_section, rule_id, label in (
        ("194B", "115BB", "ITR2-IN-TDS-016", "winnings from lotteries/crossword puzzles/card games"),
        ("194BB", "115BB", "ITR2-IN-TDS-017", "income from owning and maintaining race horses"),
        ("194BA", "115BBJ", "ITR2-IN-TDS-018", "winnings from online games"),
    ):
        has_tds = any(
            e.tds_section == tds_section
            for e in (list(inp.tds2_entries or []) + list(inp.tds3_entries or []))
        )
        if has_tds and si_section not in si_sections_present:
            results.append(_result(
                rule_id, True,
                f"TDS under section {tds_section} suggests {label} was derived "
                f"this year, but no matching Section {si_section} income is "
                "disclosed in Schedule SI -- please confirm the income has been "
                "fully offered to tax.",
                "si_entries", severity=Severity.D,
            ))

    # B/D #19: Form 10EE is required to sustain a claim for relief u/s 89A
    # (notified foreign-retirement-account income), mirroring the Form
    # 10E/89 pattern above.
    if inp.os_section_89a is not None and (
        inp.os_section_89a.income_notified > _ZERO
        or inp.os_section_89a.relief > _ZERO
    ):
        results.append(_result(
            "ITR2-IN-FORM-006", True,
            "Section 89A notified income/relief is claimed -- Form 10EE must be "
            "filed separately to sustain this claim.",
            "os_section_89a", severity=Severity.D,
        ))

    # B/D #22: TDS deducted and claimed under section 194M specifically
    # flags a business-type payment (by an individual/HUF not otherwise
    # liable to deduct TDS) inconsistent with filing ITR-2.
    for index, entry in enumerate(inp.tds2_entries or []):
        if entry.tds_section == "194M":
            results.append(_result(
                "ITR2-IN-TDS-019", True,
                "TDS has been deducted and claimed under section 194M, but "
                "ITR-2 has been filed -- please confirm ITR-2 is the correct form.",
                f"tds2_entries[{index}].tds_section", severity=Severity.D,
            ))

    # B/D #25: cross-check the taxpayer-entered indexed cost of acquisition
    # against the statutory CII formula, using the exact same helper the
    # calculator itself uses (app/engine/schedules/capital_gains.py) so this
    # advisory can never disagree with what the engine actually computes --
    # deliberately not re-deriving the "does indexation still apply
    # post-July-2024" policy question here, only consistency with the
    # engine's own existing formula.
    for index, tx in enumerate(inp.cg_transactions or []):
        if tx.indexed_cost <= _ZERO or tx.date_of_acquisition is None:
            continue
        from app.engine.schedules.capital_gains import _indexed_cost
        expected = _indexed_cost(
            tx.cost_of_acquisition,
            tx.date_of_acquisition.isoformat(),
            tx.date_of_transfer.isoformat(),
        )
        if abs(tx.indexed_cost - expected) > Decimal("1"):
            results.append(_result(
                "ITR2-IN-CG-012", True,
                "Indexed cost of acquisition does not match Cost of acquisition "
                "x CII(year of sale)/CII(year of acquisition) -- please ensure "
                "correct computation in Schedule CG.",
                f"cg_transactions[{index}].indexed_cost",
                str(expected), str(tx.indexed_cost), severity=Severity.D,
            ))

    return results


def run_input_validation(inp: ITR2Input) -> "ValidationReport":
    """Run ITR-2 pre-computation validation and return a standard report."""
    from app.engine.validators.base import ValidationReport

    return ValidationReport(form_type="ITR2", results=validate_itr2_input(inp))
