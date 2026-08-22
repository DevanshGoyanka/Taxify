"""Canonical ReturnDraft to ITR-1 computation and CBDT filing gateway.

This module is the Phase 2 single pipeline. A canonical draft is mapped once,
computed once, and the same typed input/result pair is reused for both the
headline summary and official JSON generation.
"""

from __future__ import annotations

import datetime
import logging
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from pydantic import ValidationError

from app.engine.calculators.itr1 import ITR1Result, compute as compute_itr1
from app.engine.calculators.itr4 import ITR4Result, compute as compute_itr4
from app.engine.draft_to_itr1_input import DraftMappingError, draft_to_itr1_input
from app.engine.draft_to_itr4_input import draft_to_itr4_input
from app.engine.itd.itr1 import build_itr1_json
from app.engine.itd.itr1_schema import ITR1SchemaValidationError, validate_itr1_json
from app.engine.itd.itr4 import build_itr4_json
from app.engine.itd.itr4_schema import validate_itr4_json
from app.schemas.itr1 import FilingAddress, ITR1FilingProfile, ITR1Input, PropertyFilingProfile
from app.schemas.itr4 import (
    ITR4BankAccount,
    ITR4FilingAddress,
    ITR4FilingProfile,
    ITR4PostalAddress,
    ITR4PropertyProfile,
    ITR4Input,
    ITR4AssesseeStatus,
    ITR4SeventhProvisoDetails,
    ITR4TaxReturnPreparer,
)
from app.schemas.return_draft import ReturnDraft

logger = logging.getLogger("taxify.filing_gateway_v2")


class FilingGatewayV2Error(ValueError):
    """Raised when a canonical draft cannot be computed or filed."""

    def __init__(self, message: str, errors: list[str] | None = None) -> None:
        """Initialize an actionable gateway error.

        Args:
            message: High-level failure description.
            errors: Optional detailed validation messages.
        """
        super().__init__(message)
        self.message = message
        self.errors = errors or [message]


@dataclass(frozen=True)
class ITR1PipelineResult:
    """Immutable output from one canonical ITR-1 computation."""

    typed_input: ITR1Input
    computation: ITR1Result
    breakdown: dict[str, Any]
    summary: dict[str, Any]


def _decimal_float(value: Decimal | int | float) -> float:
    """Convert a finite engine amount to a JSON-compatible number."""
    return float(value)


def _summary_from_result(
    result: ITR1Result,
    breakdown: dict[str, Any],
) -> dict[str, Any]:
    """Build the v2 response while preserving legacy headline aliases."""
    deductions = result.schedules.get("deductions") if result.schedules else None
    raw_deductions = getattr(deductions, "breakdown", {}) if deductions else {}
    deduction_breakdown = {
        str(key): _decimal_float(value) for key, value in raw_deductions.items()
    }
    total_tds = _decimal_float(result.total_tds)
    total_paid = _decimal_float(result.total_taxes_paid)
    balance = _decimal_float(result.balance_payable)
    refund = _decimal_float(result.refund_due)
    issues = list(breakdown.get("credit_validation_issues", []))
    warnings = list(result.warnings)
    return {
        "gti": _decimal_float(result.gross_total_income),
        "grossTotalIncome": _decimal_float(result.gross_total_income),
        "grossTotIncome": _decimal_float(result.gross_total_income),
        "totalDeductions": _decimal_float(result.deductions_total),
        "totalIncome": _decimal_float(result.taxable_income),
        "totalTaxPayable": _decimal_float(result.tax_before_rebate),
        "netTaxLiability": _decimal_float(result.net_tax_liability),
        "totalTaxLiability": _decimal_float(result.net_tax_liability),
        "totalTDS": total_tds,
        "totalTCS": _decimal_float(result.total_tcs),
        "advanceTax": _decimal_float(result.advance_tax_paid),
        "selfAssessmentTax": _decimal_float(result.self_assessment_tax_paid),
        "totalTaxPaid": total_paid,
        "totalTaxesPaid": total_paid,
        "balTaxPayable": balance,
        "taxPayable": balance,
        "balancePayable": balance,
        "refund": refund,
        "refundDue": refund,
        "breakdown": {
            "income": {
                "salary": _decimal_float(result.salary_income),
                "houseProperty": _decimal_float(result.house_property_income),
                "otherSources": _decimal_float(result.other_sources_income),
                "capitalGains112A": _decimal_float(result.capital_gains_112a),
            },
            "deductions": deduction_breakdown,
            "tax": {
                "slabTax": _decimal_float(result.slab_tax),
                "specialRateTax": _decimal_float(result.special_rate_tax),
                "rebate87A": _decimal_float(result.rebate_87a),
                "surcharge": _decimal_float(result.surcharge),
                "cess": _decimal_float(result.health_education_cess),
                "interest": _decimal_float(result.total_interest),
            },
            "credits": {
                "tds": total_tds,
                "tcs": _decimal_float(result.total_tcs),
                "advanceTax": _decimal_float(result.advance_tax_paid),
                "selfAssessmentTax": _decimal_float(result.self_assessment_tax_paid),
            },
        },
        "issues": issues,
        "creditValidationIssues": issues,
        "warnings": warnings,
        "calculationStatus": "CALCULATED_WITH_CREDIT_ISSUES" if issues else "CALCULATED",
        "computedByFormEngine": "ITR-1",
        "filingComputationStatus": "FORM_COMPUTATION",
    }


def compute_canonical_itr1(draft: ReturnDraft) -> ITR1PipelineResult:
    """Map and compute a canonical ITR-1 draft exactly once.

    Args:
        draft: Validated canonical return draft.

    Returns:
        Typed input, computation, mapping breakdown, and response summary.

    Raises:
        FilingGatewayV2Error: If form selection, mapping, or computation fails.
    """
    if draft.form != "ITR-1":
        raise FilingGatewayV2Error(
            "The v2 canonical compute endpoint currently supports ITR-1 and "
            "ITR-4 only.",
            [f"Form {draft.form!r} is not supported by the v2 pipeline yet."],
        )
    pending = [item for item in draft.reconciliation.discrepancies if item.status == "PENDING"]
    logger.debug(
        "compute_canonical_itr1 form=%s discrepancies=%d pending=%d evidence=%d",
        draft.form, len(draft.reconciliation.discrepancies),
        len(pending), len(draft.reconciliation.evidence),
    )
    if pending:
        categories = ", ".join(sorted({item.category for item in pending}))
        logger.debug("compute_canonical_itr1 REJECT pending categories=%s", categories)
        raise FilingGatewayV2Error(
            "Manual confirmation is required for imported AIS/TIS reconciliation discrepancies before compute or generation.",
            [f"Pending reconciliation discrepancy: {category}." for category in sorted({item.category for item in pending})],
        )
    # Evidence-contradiction guard: any imported row classified OUT_OF_SCOPE_TAXABLE
    # proves that income outside ITR-1 scope exists in the taxpayer's AIS/TIS/26AS.
    # Allowing a compute with these rows present would silently ignore income that
    # requires ITR-2/3.  The taxpayer must correct the form selection first.
    out_of_scope = [
        e for e in draft.reconciliation.evidence
        if e.role == "OUT_OF_SCOPE_TAXABLE"
    ]
    if out_of_scope:
        codes = sorted({e.sourceCode for e in out_of_scope if e.sourceCode})
        logger.debug("compute_canonical_itr1 REJECT out_of_scope=%d codes=%s", len(out_of_scope), codes)
        raise FilingGatewayV2Error(
            "Imported evidence contains income outside ITR-1 scope. "
            "Please select the correct form (ITR-2 or ITR-3) before computing.",
            [f"OUT_OF_SCOPE_TAXABLE evidence: {', '.join(codes) or 'unknown codes'}."],
        )
    try:
        typed_input, breakdown = draft_to_itr1_input(draft)
        result = compute_itr1(typed_input)
    except (DraftMappingError, ValidationError, ValueError) as exc:
        logger.debug("compute_canonical_itr1 REJECT mapping/compute error: %s", exc)
        raise FilingGatewayV2Error("ITR-1 mapping or computation failed.", [str(exc)]) from exc
    if result.errors:
        logger.debug("compute_canonical_itr1 REJECT result.errors=%s", result.errors)
        raise FilingGatewayV2Error(
            "ITR-1 computation rejected the canonical draft.",
            [str(error) for error in result.errors],
        )
    logger.debug(
        "compute_canonical_itr1 OK gti=%s taxable=%s tax=%s",
        result.gross_total_income, result.taxable_income, result.net_tax_liability,
    )
    return ITR1PipelineResult(
        typed_input=typed_input,
        computation=result,
        breakdown=breakdown,
        summary=_summary_from_result(result, breakdown),
    )


def _required(value: str | None, field: str) -> str:
    """Return stripped required text or raise an actionable filing error."""
    cleaned = (value or "").strip()
    if not cleaned:
        raise FilingGatewayV2Error(
            "ITR-1 filing profile is incomplete.",
            [f"personal.{field} is required for official CBDT JSON."],
        )
    return cleaned


def _filing_profile(draft: ReturnDraft) -> ITR1FilingProfile:
    """Construct the official typed filing profile from canonical fields."""
    personal = draft.personal
    try:
        dob = datetime.date.fromisoformat(_required(personal.dateOfBirth, "dateOfBirth"))
    except ValueError as exc:
        if isinstance(exc, FilingGatewayV2Error):
            raise
        raise FilingGatewayV2Error(
            "ITR-1 filing profile is invalid.",
            ["personal.dateOfBirth must be a valid YYYY-MM-DD date."],
        ) from exc
    # CBDT FilingStatus.ReturnFileSec enum (min=11, max=20): the filing
    # section codes the official ITR-1/ITR-4 schema accepts. The frontend
    # FilingStatus.filingSection string codes map to these integers.
    section_codes = {
        "139(1)": 11,   # Before due date u/s 139(1)
        "139(4)": 12,   # Belated/after due date u/s 139(4)
        "139(5)": 17,   # Revised return u/s 139(5)
        "139(9)": 13,   # Defective return u/s 139(9)
        "167": 14,      # Notice u/s 148 (reopening)
        "119(2)(b)": 16,  # Condonation of delay u/s 119(2)(b)
        "173": 18,      # Reassessment u/s 173
        "148": 20,      # Notice u/s 148 (post-search)
    }
    return_section = section_codes.get(draft.filing.filingSection)
    if return_section is None:
        raise FilingGatewayV2Error(
            "The v2 pipeline could not map filingSection to a CBDT ReturnFileSec code.",
            [
                f"filingSection {draft.filing.filingSection!r} is not a supported "
                "section code. Use one of: 139(1), 139(4), 139(5), 139(9), "
                "119(2)(b), 167, 173, 148."
            ],
        )
    if not draft.verification.declarationAccepted:
        raise FilingGatewayV2Error(
            "Verification declaration must be accepted for official ITR-1 JSON.",
            ["verification.declarationAccepted must be true."],
        )
    if draft.verification.capacity != "SELF":
        raise FilingGatewayV2Error(
            "Representative verification is not supported by v2 ITR-1 generation.",
            ["verification.capacity must be SELF for official ITR-1 JSON."],
        )
    secondary_mobile = personal.secondaryMobile.strip() or None
    secondary_email = personal.secondaryEmail.strip() or None
    try:
        address = FilingAddress(
            residence_no=_required(personal.flatNo, "flatNo"),
            residence_name=personal.residenceName.strip(),
            road_or_street=personal.roadOrStreet.strip(),
            locality_or_area=_required(personal.localityOrArea, "localityOrArea"),
            city_or_town_or_district=_required(personal.city, "city"),
            state_code=_required(personal.stateCode, "stateCode"),
            country_code=personal.countryCode.strip() or "91",
            pin_code=personal.pinCode.strip() or None,
            zip_code=personal.zipCode.strip(),
            mobile_country_code=91,
            mobile_no=_required(personal.mobile, "mobile"),
            email=_required(personal.email, "email"),
            secondary_mobile_country_code=(
                int(personal.secondaryMobileCountryCode or "91") if secondary_mobile else 0
            ),
            secondary_mobile_no=secondary_mobile,
            secondary_email=secondary_email,
        )
        surname = personal.surnameOrOrgName.strip() or personal.name.strip()
        return ITR1FilingProfile(
            pan=_required(personal.pan, "pan").upper(),
            first_name=personal.firstName.strip(),
            middle_name=personal.middleName.strip(),
            surname=_required(surname, "surnameOrOrgName"),
            date_of_birth=dob,
            employer_category=_required(
                personal.employerCategory, "personal.employerCategory"
            ),
            aadhaar_number=personal.aadhaar.strip() or None,
            primary_address=address,
            father_name=_required(personal.fatherName, "fatherName"),
            verification_place=_required(draft.verification.place, "verification.place"),
            verification_capacity="S",
            return_file_section=return_section,
            return_type="R" if draft.filing.returnType == "REVISED" else "O",
            original_acknowledgement_no=(
                draft.filing.originalAcknowledgementNumber.strip() or None
                if draft.filing.returnType == "REVISED" else None
            ),
            opt_out_new_tax_regime=draft.regime == "old",
        )
    except (ValidationError, ValueError) as exc:
        if isinstance(exc, FilingGatewayV2Error):
            raise
        raise FilingGatewayV2Error("ITR-1 filing profile is invalid.", [str(exc)]) from exc


def _property_profiles(draft: ReturnDraft) -> list[PropertyFilingProfile]:
    """Build property filing profiles in the same order as compute rows."""
    rows = draft.houseProperties
    if not rows:
        personal = draft.personal
        rows_data = [(
            personal.flatNo or personal.residenceName,
            personal.city,
            personal.stateCode,
            personal.countryCode,
            personal.pinCode,
            personal.zipCode,
        )]
    else:
        # Fall back to the property name, then the primary address; also fall
        # back to the taxpayer's city/state/country/pin so a property row that
        # omits those fields still produces a valid PropertyFilingProfile
        # (mirrors the legacy mapper's fallback chain).
        primary_address = draft.personal.flatNo or draft.personal.residenceName
        rows_data = [(
            row.address or row.premisesName or row.name or primary_address,
            row.city or draft.personal.city,
            row.state or draft.personal.stateCode,
            row.countryCode or draft.personal.countryCode,
            row.pinCode or draft.personal.pinCode,
            row.zipCode or draft.personal.zipCode,
        ) for row in rows]
    try:
        return [PropertyFilingProfile(
            address_detail=_required(address, "property.address"),
            city_or_town_or_district=_required(city, "property.city"),
            state_code=_required(state, "property.stateCode"),
            country_code=(country or "91").strip(),
            pin_code=(pin or "").strip() or None,
            zip_code=(zip_code or "").strip() or None,
        ) for address, city, state, country, pin, zip_code in rows_data]
    except (ValidationError, ValueError) as exc:
        if isinstance(exc, FilingGatewayV2Error):
            raise
        raise FilingGatewayV2Error("ITR-1 property filing profile is invalid.", [str(exc)]) from exc


# ===========================================================================
# ITR-4 canonical pipeline (Phase 3)
# ===========================================================================

@dataclass(frozen=True)
class ITR4PipelineResult:
    """Immutable output from one canonical ITR-4 computation."""

    typed_input: ITR4Input
    computation: ITR4Result
    breakdown: dict[str, Any]
    summary: dict[str, Any]


def _itr4_filing_profile(draft: ReturnDraft) -> ITR4FilingProfile:
    """Construct the official ITR-4 filing profile from canonical fields.

    Mirrors the legacy ``_build_itr4_input_from_flat`` profile construction,
    but reads the typed ``ReturnDraft`` personal/filing/verification fields
    instead of flat-blob aliases. Enforces the same verification gate
    (declaration accepted, SELF capacity) and required-field checks.
    """
    personal = draft.personal
    filing = draft.filing
    verification = draft.verification

    def _required(value: str | None, field: str) -> str:
        cleaned = (value or "").strip()
        if not cleaned:
            raise FilingGatewayV2Error(
                "ITR-4 filing profile is incomplete.",
                [f"personal.{field} is required for official CBDT JSON."],
            )
        return cleaned

    try:
        dob = datetime.date.fromisoformat(_required(personal.dateOfBirth, "dateOfBirth"))
    except ValueError as exc:
        if isinstance(exc, FilingGatewayV2Error):
            raise
        raise FilingGatewayV2Error(
            "ITR-4 filing profile is invalid.",
            ["personal.dateOfBirth must be a valid YYYY-MM-DD date."],
        ) from exc

    if not verification.declarationAccepted:
        raise FilingGatewayV2Error(
            "Verification declaration must be accepted for official ITR-4 JSON.",
            ["verification.declarationAccepted must be true."],
        )
    if verification.capacity != "SELF":
        raise FilingGatewayV2Error(
            "Representative verification is not supported by v2 ITR-4 generation.",
            ["verification.capacity must be SELF for official ITR-4 JSON."],
        )

    # Filing-section code map (mirrors the legacy _filing_section_code).
    section_map = {
        "139(1)": 11, "139(4)": 12, "142(1)": 13, "148": 14,
        "153C": 16, "139(5)": 17, "139(9)": 18, "119(2)(b)": 20,
    }
    return_section = section_map.get(filing.filingSection)
    if return_section is None:
        raise FilingGatewayV2Error(
            "Official v2 ITR-4 generation supports filing sections 139(1), "
            "139(4), 142(1), 148, 153C, 139(5), 139(9), 119(2)(b).",
            [f"filingSection {filing.filingSection!r} is not supported."],
        )

    mobile_cc_raw = (personal.countryCode or "91").strip() or "91"
    if not mobile_cc_raw.isdigit():
        raise FilingGatewayV2Error(
            "ITR-4 filing profile is invalid.",
            ["personal.countryCode must be numeric."],
        )

    secondary_mobile_raw = (personal.secondaryMobile or "").strip()
    secondary_mobile_cc_raw = (
        (personal.secondaryMobileCountryCode or "").strip() or mobile_cc_raw
    )
    secondary_mobile_no: str | None = None
    secondary_mobile_cc: int = 0
    if secondary_mobile_raw:
        if not secondary_mobile_cc_raw.isdigit():
            raise FilingGatewayV2Error(
                "ITR-4 filing profile is invalid.",
                ["personal.secondaryMobileCountryCode must be numeric."],
            )
        secondary_mobile_cc = int(secondary_mobile_cc_raw)
        secondary_mobile_no = secondary_mobile_raw

    secondary_email = (personal.secondaryEmail or "").strip() or None

    landline_std = (personal.landlineStdCode or "0").strip() or "0"
    landline_phone = (personal.landlinePhoneNo or "0").strip() or "0"
    if not landline_std.isdigit():
        landline_std = "0"
    if not landline_phone.isdigit():
        landline_phone = "0"

    status_map = {
        "I": ITR4AssesseeStatus.INDIVIDUAL,
        "H": ITR4AssesseeStatus.HUF,
        "F": ITR4AssesseeStatus.FIRM,
    }
    assessee_status = status_map.get(
        personal.assesseeStatus, ITR4AssesseeStatus.INDIVIDUAL
    )

    try:
        primary_address = ITR4FilingAddress(
            residence_no=_required(personal.flatNo, "flatNo")[:50],
            residence_name=(personal.residenceName or "").strip()[:50],
            road_or_street=(personal.roadOrStreet or "").strip()[:50],
            locality_or_area=_required(personal.localityOrArea, "localityOrArea")[:50],
            city_or_town_or_district=_required(personal.city, "city")[:50],
            state_code=_required(personal.stateCode, "stateCode")[:2],
            country_code=(personal.countryCode or "91").strip() or "91",
            pin_code=(personal.pinCode or "").strip() or None,
            zip_code=(personal.zipCode or "").strip(),
            mobile_country_code=int(mobile_cc_raw),
            mobile_no=_required(personal.mobile, "mobile")[:10],
            email=_required(personal.email, "email")[:125],
            secondary_mobile_country_code=secondary_mobile_cc,
            secondary_mobile_no=secondary_mobile_no,
            secondary_email=secondary_email,
            landline_std_code=int(landline_std),
            landline_phone_no=landline_phone[:12],
        )
    except (ValidationError, ValueError) as exc:
        if isinstance(exc, FilingGatewayV2Error):
            raise
        raise FilingGatewayV2Error(
            "ITR-4 filing profile is invalid.", [str(exc)]
        ) from exc

    alternate_address: ITR4PostalAddress | None = None
    if personal.secondaryAddressDifferent:
        alt = personal.alternateAddress
        if alt is None:
            raise FilingGatewayV2Error(
                "ITR-4 filing profile is incomplete.",
                ["personal.alternateAddress is required when "
                 "secondaryAddressDifferent is true."],
            )
        alternate_address = ITR4PostalAddress(
            residence_no=(alt.residenceNo or "").strip()[:50],
            residence_name=(alt.residenceName or "").strip()[:50],
            road_or_street=(alt.roadOrStreet or "").strip()[:50],
            locality_or_area=(alt.localityOrArea or "").strip()[:50],
            city_or_town_or_district=(alt.cityOrTownOrDistrict or "").strip()[:50],
            state_code=(alt.stateCode or "").strip()[:2],
            country_code=(alt.countryCode or "91").strip() or "91",
            pin_code=(alt.pinCode or "").strip() or None,
            zip_code=(alt.zipCode or "").strip(),
        )

    seventh = draft.filing.seventhProviso
    seventh_proviso = ITR4SeventhProvisoDetails(
        foreign_travel_flag=seventh.foreignTravel,
        foreign_travel_amount=seventh.foreignTravelAmount,
        electricity_expenditure_flag=seventh.electricityExpenditure,
        electricity_expenditure_amount=seventh.electricityExpenditureAmount,
        other_clause_iv_flag=seventh.otherClauseIV,
        other_clause_iv_detail=(seventh.otherClauseIVDetail or "").strip()[:125],
    )

    f10iea_date = ""
    if filing.form10IEADate:
        parsed = _to_date(filing.form10IEADate)
        f10iea_date = parsed.isoformat() if parsed else ""

    surname = (personal.surnameOrOrgName or "").strip() or (personal.name or "").strip()
    try:
        return ITR4FilingProfile(
            pan=_required(personal.pan, "pan").upper(),
            first_name=(personal.firstName or "").strip()[:25],
            middle_name=(personal.middleName or "").strip()[:25],
            surname=_required(surname, "surnameOrOrgName")[:75],
            date_of_birth=dob,
            employer_category=_required(
                personal.employerCategory, "personal.employerCategory"
            ),
            aadhaar_number=(personal.aadhaar or "").strip() or None,
            assessee_status=assessee_status,
            primary_address=primary_address,
            alternate_address=alternate_address,
            father_name=_required(personal.fatherName, "fatherName")[:125],
            verification_place=_required(verification.place, "verification.place")[:50],
            verification_capacity="S",
            return_file_section=return_section,
            seventh_proviso=seventh_proviso,
            f10iea_curr_ay_old_regime=("Y" if draft.regime == "old" else "N"),
            f10iea_date_curr_ay_old_tax=f10iea_date,
        )
    except (ValidationError, ValueError) as exc:
        if isinstance(exc, FilingGatewayV2Error):
            raise
        raise FilingGatewayV2Error(
            "ITR-4 filing profile is invalid.", [str(exc)]
        ) from exc


def _itr4_property_profile(draft: ReturnDraft) -> ITR4PropertyProfile | None:
    """Build the single ITR-4 property profile (one house property allowed).

    Falls back to the taxpayer's primary address when no property row exists
    (mirrors the legacy mapper's fallback chain).
    """
    rows = draft.houseProperties
    if rows:
        row = rows[0]
        address = (row.address or row.premisesName or row.name
                   or draft.personal.flatNo or draft.personal.residenceName).strip()
        city = (row.city or draft.personal.city).strip()
        state = (row.state or draft.personal.stateCode).strip()
        country = (row.countryCode or draft.personal.countryCode or "91").strip()
        pin = (row.pinCode or draft.personal.pinCode).strip() or None
        zip_code = (row.zipCode or draft.personal.zipCode).strip() or None
    else:
        address = (draft.personal.flatNo or draft.personal.residenceName).strip()
        city = draft.personal.city.strip()
        state = draft.personal.stateCode.strip()
        country = (draft.personal.countryCode or "91").strip()
        pin = draft.personal.pinCode.strip() or None
        zip_code = draft.personal.zipCode.strip() or None
    if not address:
        return None
    try:
        return ITR4PropertyProfile(
            address_detail=address[:50],
            city_or_town_or_district=(city or "City")[:50],
            state_code=(state or "07")[:2],
            country_code=country or "91",
            pin_code=pin,
            zip_code=zip_code,
        )
    except (ValidationError, ValueError) as exc:
        raise FilingGatewayV2Error(
            "ITR-4 property filing profile is invalid.", [str(exc)]
        ) from exc


def _itr4_bank_accounts(draft: ReturnDraft) -> list[ITR4BankAccount]:
    """Map canonical bank-account rows → the ITR-4 bank-account type."""
    accounts: list[ITR4BankAccount] = []
    for b in draft.bankAccounts:
        account_number = (b.accountNumber or "").strip()
        ifsc = (b.ifscCode or "").strip().upper()
        bank_name = (b.bankName or "").strip()
        if not account_number or not ifsc or not bank_name:
            continue
        try:
            accounts.append(ITR4BankAccount(
                account_number=account_number[:20],
                ifsc_code=ifsc,
                bank_name=bank_name[:125],
                account_type=(b.accountType or "savings").strip()[:20],
                is_primary=b.useForRefund,
            ))
        except (ValidationError, ValueError):
            continue
    return accounts


def compute_canonical_itr4(draft: ReturnDraft) -> ITR4PipelineResult:
    """Map and compute a canonical ITR-4 draft exactly once.

    Args:
        draft: Validated canonical return draft (``form == "ITR-4"``).

    Returns:
        Typed input, computation, mapping breakdown, and response summary.

    Raises:
        FilingGatewayV2Error: If mapping or computation fails, or pending
            reconciliation discrepancies / out-of-scope evidence block compute.
    """
    if draft.form != "ITR-4":
        raise FilingGatewayV2Error(
            "compute_canonical_itr4 requires draft.form == 'ITR-4'."
        )
    pending = [
        item for item in draft.reconciliation.discrepancies
        if item.status == "PENDING"
    ]
    if pending:
        categories = ", ".join(sorted({item.category for item in pending}))
        raise FilingGatewayV2Error(
            "Manual confirmation is required for imported AIS/TIS "
            "reconciliation discrepancies before compute or generation.",
            [f"Pending reconciliation discrepancy: {category}."
             for category in sorted({item.category for item in pending})],
        )
    out_of_scope = [
        e for e in draft.reconciliation.evidence
        if e.role == "OUT_OF_SCOPE_TAXABLE"
    ]
    if out_of_scope:
        codes = sorted({e.sourceCode for e in out_of_scope if e.sourceCode})
        raise FilingGatewayV2Error(
            "Imported evidence contains income outside ITR-4 scope. "
            "Please select the correct form (ITR-2 or ITR-3) before computing.",
            [f"OUT_OF_SCOPE_TAXABLE evidence: {', '.join(codes) or 'unknown codes'}."],
        )
    try:
        typed_input, breakdown = draft_to_itr4_input(draft)
        result = compute_itr4(typed_input)
    except (DraftMappingError, ValidationError, ValueError) as exc:
        raise FilingGatewayV2Error(
            "ITR-4 mapping or computation failed.", [str(exc)]
        ) from exc
    if result.errors:
        raise FilingGatewayV2Error(
            "ITR-4 computation rejected the canonical draft.",
            [str(error) for error in result.errors],
        )
    return ITR4PipelineResult(
        typed_input=typed_input,
        computation=result,
        breakdown=breakdown,
        summary=_summary_from_result(result, breakdown),
    )


def _generate_cbdt_json_itr4(draft: ReturnDraft) -> tuple[dict[str, Any], dict[str, Any]]:
    """Build + validate the official ITR-4 CBDT JSON from a canonical draft.

    Runs the full CBDT Category A/B/D rule validators before JSON emission
    (parity with the legacy ``_build_itr4_official_json``).
    """
    pipeline = compute_canonical_itr4(draft)
    filing_profile = _itr4_filing_profile(draft)
    property_profile = _itr4_property_profile(draft)
    bank_accounts = _itr4_bank_accounts(draft)
    typed_input = pipeline.typed_input.model_copy(update={
        "filing_profile": filing_profile,
        "property_profile": property_profile,
        "bank_accounts": bank_accounts,
        "tax_return_preparer": None,
    })

    from app.engine.validators.itr4 import (
        run_input_validation,
        run_calc_validation,
    )

    input_report = run_input_validation(typed_input)
    if not input_report.can_upload:
        raise FilingGatewayV2Error(
            "ITR-4 CBDT Category A input validation failed.",
            [r.message for r in input_report.blocking_errors],
        )
    calc_report = run_calc_validation(typed_input, pipeline.computation)
    if not calc_report.can_upload:
        raise FilingGatewayV2Error(
            "ITR-4 CBDT Category A calculation validation failed.",
            [r.message for r in calc_report.blocking_errors],
        )

    try:
        official_json = build_itr4_json(pipeline.computation, typed_input)
        validate_itr4_json(official_json)
    except Exception as exc:
        logger.exception(
            "ITR-4 official JSON generation failed: %s: %s",
            type(exc).__name__, exc,
        )
        raise FilingGatewayV2Error(
            "ITR-4 official JSON generation failed.",
            [f"{type(exc).__name__}: {exc}"],
        ) from exc
    return official_json, pipeline.summary


def compute_canonical(draft: ReturnDraft) -> ITR1PipelineResult | ITR4PipelineResult:
    """Form-dispatching compute entrypoint (Phase 3).

    Used by ``tax_v2.compute_tax_summary_v2`` so ITR-1 and ITR-4 both compute
    via the single canonical pipeline — no legacy delegation.

    Args:
        draft: Validated canonical return draft.

    Returns:
        The per-form pipeline result (``ITR1PipelineResult`` or
        ``ITR4PipelineResult``).

    Raises:
        FilingGatewayV2Error: If the form is not ITR-1 or ITR-4 (ITR-2/3 not
            yet supported by the v2 pipeline).
    """
    if draft.form == "ITR-1":
        return compute_canonical_itr1(draft)
    if draft.form == "ITR-4":
        return compute_canonical_itr4(draft)
    raise FilingGatewayV2Error(
        "The v2 canonical compute endpoint currently supports ITR-1 and "
        "ITR-4 only.",
        [f"Form {draft.form!r} is not supported by the v2 pipeline yet."],
    )


def generate_cbdt_json(draft: ReturnDraft) -> tuple[dict[str, Any], dict[str, Any]]:
    """Compute once, build official JSON, and validate the CBDT schema.

    Dispatches on ``draft.form``: ITR-1 → the existing ITR-1 path; ITR-4 →
    the Phase 3 ITR-4 path. Both forms run the full CBDT Category A/B/D rule
    validators before JSON emission.

    Args:
        draft: Saved canonical draft.

    Returns:
        A pair of official CBDT JSON and the summary from the same computation.

    Raises:
        FilingGatewayV2Error: If profile construction, generation, or official
            schema validation fails.
    """
    if draft.form == "ITR-1":
        return _generate_cbdt_json_itr1(draft)
    if draft.form == "ITR-4":
        return _generate_cbdt_json_itr4(draft)
    raise FilingGatewayV2Error(
        "The v2 canonical pipeline currently supports ITR-1 and ITR-4 only.",
        [f"Form {draft.form!r} is not supported by the v2 pipeline yet."],
    )


def _generate_cbdt_json_itr1(draft: ReturnDraft) -> tuple[dict[str, Any], dict[str, Any]]:
    """ITR-1 official JSON generation (the original generate_cbdt_json body)."""
    pipeline = compute_canonical_itr1(draft)
    profiles = _property_profiles(draft)
    typed_input = pipeline.typed_input.model_copy(update={
        "filing_profile": _filing_profile(draft),
        "property_profile": profiles[0],
        "property_profiles": profiles,
    })

    from app.engine.validators.itr1 import (
        run_input_validation,
        run_calc_validation,
    )

    input_report = run_input_validation(typed_input)
    if not input_report.can_upload:
        raise FilingGatewayV2Error(
            "ITR-1 CBDT Category A input validation failed.",
            [r.message for r in input_report.blocking_errors],
        )
    calc_report = run_calc_validation(typed_input, pipeline.computation)
    if not calc_report.can_upload:
        raise FilingGatewayV2Error(
            "ITR-1 CBDT Category A calculation validation failed.",
            [r.message for r in calc_report.blocking_errors],
        )

    try:
        official_json = build_itr1_json(pipeline.computation, typed_input)
        validate_itr1_json(official_json)
    except ITR1SchemaValidationError as exc:
        detail_lines: list[str] = []
        for item in exc.errors:
            detail_lines.append(
                f"schema path {item.get('schema_path') or '$'}: "
                f"json path {item.get('path') or '$'} -> {item.get('message')}"
            )
        logger.error(
            "ITR-1 official schema validation failed: %d violation(s).",
            len(exc.errors),
        )
        for line in detail_lines:
            logger.error("  schema violation: %s", line)
        raise FilingGatewayV2Error(
            "ITR-1 official JSON schema validation failed.",
            detail_lines,
        ) from exc
    except Exception as exc:
        logger.exception(
            "ITR-1 official JSON generation failed: %s: %s",
            type(exc).__name__, exc,
        )
        raise FilingGatewayV2Error(
            "ITR-1 official JSON generation failed.",
            [f"{type(exc).__name__}: {exc}"],
        ) from exc
    return official_json, pipeline.summary
