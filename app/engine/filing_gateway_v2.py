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
from app.engine.draft_to_itr1_input import DraftMappingError, draft_to_itr1_input
from app.engine.itd.itr1 import build_itr1_json
from app.engine.itd.itr1_schema import ITR1SchemaValidationError, validate_itr1_json
from app.schemas.itr1 import FilingAddress, ITR1FilingProfile, ITR1Input, PropertyFilingProfile
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
            "The v2 canonical compute endpoint currently supports ITR-1 only."
        )
    pending = [item for item in draft.reconciliation.discrepancies if item.status == "PENDING"]
    print(f"[DEBUG compute_canonical_itr1] form={draft.form} discrepancies={len(draft.reconciliation.discrepancies)} pending={len(pending)} evidence={len(draft.reconciliation.evidence)}", flush=True)
    if pending:
        categories = ", ".join(sorted({item.category for item in pending}))
        print(f"[DEBUG compute_canonical_itr1] REJECT: pending discrepancies categories={categories}", flush=True)
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
        print(f"[DEBUG compute_canonical_itr1] REJECT: out_of_scope={len(out_of_scope)} codes={codes}", flush=True)
        raise FilingGatewayV2Error(
            "Imported evidence contains income outside ITR-1 scope. "
            "Please select the correct form (ITR-2 or ITR-3) before computing.",
            [f"OUT_OF_SCOPE_TAXABLE evidence: {', '.join(codes) or 'unknown codes'}."],
        )
    try:
        typed_input, breakdown = draft_to_itr1_input(draft)
        result = compute_itr1(typed_input)
    except (DraftMappingError, ValidationError, ValueError) as exc:
        print(f"[DEBUG compute_canonical_itr1] REJECT: mapping/compute error: {exc}", flush=True)
        raise FilingGatewayV2Error("ITR-1 mapping or computation failed.", [str(exc)]) from exc
    if result.errors:
        print(f"[DEBUG compute_canonical_itr1] REJECT: result.errors={result.errors}", flush=True)
        raise FilingGatewayV2Error(
            "ITR-1 computation rejected the canonical draft.",
            [str(error) for error in result.errors],
        )
    print(f"[DEBUG compute_canonical_itr1] OK: gti={result.gross_total_income} taxable={result.taxable_income} tax={result.net_tax_liability}", flush=True)
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
    section_codes = {"139(1)": 11, "139(4)": 12}
    return_section = section_codes.get(draft.filing.filingSection)
    if return_section is None:
        raise FilingGatewayV2Error(
            "Official v2 generation currently supports filing sections 139(1) and 139(4).",
            [f"filingSection {draft.filing.filingSection!r} is not supported — use 139(1) or 139(4) for v2 ITR-1 generation."],
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
            aadhaar_number=personal.aadhaar.strip() or None,
            primary_address=address,
            father_name=_required(personal.fatherName, "fatherName"),
            verification_place=_required(draft.verification.place, "verification.place"),
            verification_capacity="S",
            return_file_section=return_section,
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


def generate_cbdt_json(draft: ReturnDraft) -> tuple[dict[str, Any], dict[str, Any]]:
    """Compute once, build official JSON, and validate the CBDT schema.

    Args:
        draft: Saved canonical ITR-1 draft.

    Returns:
        A pair of official CBDT JSON and the summary from the same computation.

    Raises:
        FilingGatewayV2Error: If profile construction, generation, or official
            schema validation fails.
    """
    pipeline = compute_canonical_itr1(draft)
    profiles = _property_profiles(draft)
    typed_input = pipeline.typed_input.model_copy(update={
        "filing_profile": _filing_profile(draft),
        "property_profile": profiles[0],
        "property_profiles": profiles,
    })

    # ── Full CBDT Category A/B/D rule validation ───────────────────────
    # Run the SAME rule suite the interactive /tax compute endpoints
    # enforce, against the typed input + computed result, BEFORE building
    # the official JSON. A Category A (blocking) failure aborts JSON
    # emission so no non-compliant ITR-1 JSON can leave this gateway —
    # critical for Type-3 portal upload where the portal's own validation
    # is the only downstream safety net.
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
        # Official ITR-1 Draft-4 schema violations.  Surface every violation
        # (path + schema path + message), not just the first one, so the
        # operator can fix all defects in one pass instead of round-tripping.
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
        # Any other failure inside the builder (mapping, encoding, digest,
        # unexpected).  Log the full traceback so the root cause is visible
        # in server output rather than just the one-line repr.
        logger.exception(
            "ITR-1 official JSON generation failed: %s: %s",
            type(exc).__name__, exc,
        )
        raise FilingGatewayV2Error(
            "ITR-1 official JSON generation failed.",
            [f"{type(exc).__name__}: {exc}"],
        ) from exc
    return official_json, pipeline.summary
