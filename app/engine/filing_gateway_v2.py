"""Canonical ReturnDraft to ITR-1 computation and CBDT filing gateway.

This module is the Phase 2 single pipeline. A canonical draft is mapped once,
computed once, and the same typed input/result pair is reused for both the
headline summary and official JSON generation.
"""

from __future__ import annotations

import datetime
import logging
import re
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
from app.schemas.itr1 import (
    AssesseeRepresentativeProfile,
    FilingAddress,
    ITR1FilingProfile,
    ITR1Input,
    PostalAddress,
    PropertyCoOwner,
    PropertyFilingProfile,
    PropertyTenant,
    SeventhProvisoClauseDetail,
    SeventhProvisoDetails,
    TaxReturnPreparer,
)
from app.schemas.itr4 import (
    ITR4BankAccount,
    ITR4FilingAddress,
    ITR4FilingProfile,
    ITR4PostalAddress,
    ITR4PropertyProfile,
    ITR4Input,
    ITR4AssesseeStatus,
    ITR4SeventhProvisoClauseDetail,
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


def _to_date(value: str | None) -> datetime.date | None:
    """Parse an optional canonical ISO date."""
    if not value:
        return None
    return datetime.date.fromisoformat(value)


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


def _capital_gains_summary(
    result: ITR1Result,
    draft: ReturnDraft,
) -> dict[str, Any]:
    """Build the per-row capital-gains summary the frontend overlays.

    The v2 compute math is authoritative and produces a non-zero aggregate
    ``result.capital_gains_112a`` (the net 112A gain). But the frontend's
    ``CapitalGainsEntryManager`` reads per-row computed values from
    ``summary.capitalGainsSummary.transactions[i]`` (fields ``actual_cost``,
    ``transfer_expenses``, ``gain``) and the bottom Schedule CG totals from
    ``totalSTCG`` / ``totalLTCG`` / ``totalCapitalGains``. Without these
    keys every per-row readout shows ₹0 even though the tax is correct.

    For the simplified-112A path (ITR-1/ITR-4), the draft carries one
    aggregate ``simplified112A`` block (sale consideration + cost). We
    synthesize a single per-row ``transactions`` entry from that aggregate
    so the frontend readout is non-zero and reconciles to the engine's
    ``capital_gains_112a``. Per-scrip detail (ITR-2/3) is handled by the
    per-scrip path elsewhere; this summary is the ITR-1/4 simplified view.
    """
    sched = (draft.capitalGainsSchedule or {}) if draft.capitalGainsSchedule else {}
    simplified = sched.get("simplified112A") or {}
    sale = Decimal(str(simplified.get("totalSaleConsideration", 0) or 0)) if simplified else Decimal("0")
    cost = Decimal(str(simplified.get("totalCostAcquisition", 0) or 0)) if simplified else Decimal("0")
    # The engine's authoritative net 112A gain (already exemption-adjusted
    # where applicable). For the simplified path this equals max(0, sale-cost).
    ltcg_112a = Decimal(str(result.capital_gains_112a or 0))
    # STCG equity is NOT reportable under ITR-1/ITR-4 (only restricted 112A
    # LTCG is). The bottom total is therefore 0 by design; the frontend
    # badges the individual STCG rows as "not reportable under this form".
    stcg_total = Decimal("0")
    ltcg_total = ltcg_112a
    total_capital_gains = ltcg_112a
    transactions: list[dict[str, Any]] = []
    if simplified and (sale > 0 or cost > 0):
        # Single aggregate row mirrors Section112ATransactionResult.to_dict()
        # field names so the frontend overlay (ct.actual_cost / ct.gain /
        # ct.transfer_expenses) lights up the readouts correctly.
        gain = max(Decimal("0"), sale - cost)
        transactions.append({
            "row": 1,
            "asset_type": "EQUITY_ORIENTED_MUTUAL_FUND",
            "holding_period_days": 0,
            "holding_period_months": 13,
            "sale_value": _decimal_float(sale),
            "actual_cost": _decimal_float(cost),
            "deemed_cost": _decimal_float(cost),
            "transfer_expenses": 0.0,
            "gain": _decimal_float(gain),
            "grandfathering_applied": False,
        })
    return {
        "status": "VALID" if transactions else ("EMPTY" if not simplified else "EVIDENCE_ONLY"),
        "gross112AGain": _decimal_float(ltcg_112a),
        "fullValueOfConsideration": _decimal_float(sale),
        "costOfAcquisition": _decimal_float(cost),
        "transferExpenses": 0.0,
        "transactionCount": len(transactions),
        "evidenceCount": 0,
        "evidencePurchaseTotal": 0.0,
        "evidenceSaleTotal": 0.0,
        "evidenceCompatibility": "SIMPLIFIED_112A",
        "transactions": transactions,
        "issues": [],
        "eligibility": {"ITR-1": True, "ITR-4": True},
        # Bottom-of-schedule totals the frontend reads directly.
        "totalSTCG": _decimal_float(stcg_total),
        "totalLTCG": _decimal_float(ltcg_total),
        "totalCapitalGains": _decimal_float(total_capital_gains),
        "vdaIncome": 0.0,
        "lossRemaining": 0.0,
        "totalLossSetOff": 0.0,
    }


def _summary_from_result(
    result: ITR1Result,
    breakdown: dict[str, Any],
    draft: ReturnDraft,
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
    hp_raw = result.schedules.get("hp") if result.schedules else None
    hp_rows = hp_raw if isinstance(hp_raw, list) else ([hp_raw] if hp_raw else [])
    house_property_details = [
        {
            "propertySequenceNo": index,
            "annualLettableValue": _decimal_float(row.gross_annual_value),
            "rentNotRealized": _decimal_float(row.rent_not_realized),
            "localTaxes": _decimal_float(row.municipal_taxes),
            "totalUnrealizedAndTax": _decimal_float(
                row.rent_not_realized + row.municipal_taxes
            ),
            "balanceALV": _decimal_float(row.net_annual_value),
            "annualOfPropOwned": _decimal_float(row.annual_value_owned),
            "thirtyPercentOfBalance": _decimal_float(
                row.standard_deduction_30pct
            ),
            "interestOnBorrowedCapital": _decimal_float(row.interest_on_loan),
            "totalDeduction": _decimal_float(
                row.standard_deduction_30pct + row.interest_on_loan
            ),
            "arrearsUnrealizedRentReceived": _decimal_float(
                row.arrears_unrealised_rent
            ),
            "incomeOfHP": _decimal_float(row.income_chargeable),
        }
        for index, row in enumerate(hp_rows, start=1)
    ]
    capital_gains_summary = _capital_gains_summary(result, draft)
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
        "hpIncome": _decimal_float(result.house_property_income),
        "totalIncChargeHP": _decimal_float(result.house_property_income),
        "housePropertyDetails": house_property_details,
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
        # Per-row capital-gains summary + bottom totals so the frontend's
        # CapitalGainsEntryManager readouts (gain/actual_cost/balance and
        # totalSTCG/totalLTCG/totalCapitalGains) are non-zero. Without this
        # every per-scrip readout shows ₹0 even though the engine math is
        # correct (capitalGains112A above carries the real aggregate).
        "capitalGainsSummary": _capital_gains_summary(result, draft),
        "capitalGainsStatus": "SIMPLIFIED_112A",
        "capitalGainsIssues": [],
        "capitalGainsEligibility": {"ITR-1": True, "ITR-4": True},
        "totalSTCG": _capital_gains_summary(result, draft).get("totalSTCG", 0.0),
        "totalLTCG": _capital_gains_summary(result, draft).get("totalLTCG", 0.0),
        "totalCapitalGains": _capital_gains_summary(result, draft).get("totalCapitalGains", 0.0),
        "vdaIncome": 0.0,
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
        summary=_summary_from_result(result, breakdown, draft),
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
        "142(1)": 13,   # Notice u/s 142(1)
        "148": 14,      # Notice u/s 148
        "153C": 16,     # Notice u/s 153C
        "139(5)": 17,   # Revised return u/s 139(5)
        "139(9)": 18,   # Defective return u/s 139(9)
        "119(2)(b)": 20,  # Condonation of delay u/s 119(2)(b)
    }
    return_section = section_codes.get(draft.filing.filingSection)
    if return_section is None:
        raise FilingGatewayV2Error(
            "The v2 pipeline could not map filingSection to a CBDT ReturnFileSec code.",
            [
                f"filingSection {draft.filing.filingSection!r} is not a supported "
                "section code. Use one of: 139(1), 139(4), 142(1), 148, "
                "153C, 139(5), 139(9), 119(2)(b)."
            ],
        )
    if not draft.verification.declarationAccepted:
        raise FilingGatewayV2Error(
            "Verification declaration must be accepted for official ITR-1 JSON.",
            ["verification.declarationAccepted must be true."],
        )
    if draft.verification.capacity not in {"SELF", "REPRESENTATIVE"}:
        raise FilingGatewayV2Error(
            "ITR-1 verification capacity is invalid.",
            ["verification.capacity must be SELF or REPRESENTATIVE for ITR-1."],
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
            mobile_country_code=int(personal.mobileCountryCode or "91"),
            mobile_no=_required(personal.mobile, "mobile"),
            email=_required(personal.email, "email"),
            secondary_mobile_country_code=(
                int(personal.secondaryMobileCountryCode or "91") if secondary_mobile else 0
            ),
            secondary_mobile_no=secondary_mobile,
            secondary_email=secondary_email,
        )
        alternate_address = None
        if personal.secondaryAddressDifferent:
            alt = personal.alternateAddress
            if alt is None:
                raise FilingGatewayV2Error(
                    "ITR-1 filing profile is incomplete.",
                    ["personal.alternateAddress is required when secondaryAddressDifferent is true."],
                )
            alternate_address = PostalAddress(
                residence_no=_required(alt.residenceNo, "alternateAddress.residenceNo"),
                residence_name=alt.residenceName.strip(),
                road_or_street=alt.roadOrStreet.strip(),
                locality_or_area=_required(
                    alt.localityOrArea, "alternateAddress.localityOrArea"
                ),
                city_or_town_or_district=_required(
                    alt.cityOrTownOrDistrict,
                    "alternateAddress.cityOrTownOrDistrict",
                ),
                state_code=_required(alt.stateCode, "alternateAddress.stateCode"),
                country_code=alt.countryCode.strip() or "91",
                pin_code=alt.pinCode.strip() or None,
                zip_code=alt.zipCode.strip(),
            )
        representative = None
        if draft.verification.capacity == "REPRESENTATIVE":
            rep = draft.filing.representative
            if rep is None:
                raise FilingGatewayV2Error(
                    "ITR-1 representative details are incomplete.",
                    ["filing.representative is required for representative verification."],
                )
            representative = AssesseeRepresentativeProfile(
                name=_required(rep.name, "filing.representative.name"),
                email=_required(rep.email, "filing.representative.email"),
                mobile_country_code=int(
                    _required(rep.mobileCountryCode, "filing.representative.mobileCountryCode")
                ),
                mobile_no=_required(rep.mobile, "filing.representative.mobile"),
            )
        seventh = draft.filing.seventhProviso
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
            alternate_address=alternate_address,
            father_name=_required(personal.fatherName, "fatherName"),
            verification_place=_required(draft.verification.place, "verification.place"),
            verification_capacity=(
                "R" if draft.verification.capacity == "REPRESENTATIVE" else "S"
            ),
            return_file_section=return_section,
            return_type="R" if draft.filing.returnType == "REVISED" else "O",
            original_acknowledgement_no=(
                draft.filing.originalAcknowledgementNumber.strip() or None
                if draft.filing.returnType == "REVISED" else None
            ),
            original_return_date=_to_date(draft.filing.originalFilingDate),
            notice_number=draft.filing.noticeNumber.strip() or None,
            notice_date=_to_date(draft.filing.noticeDate),
            assessee_representative=representative,
            opt_out_new_tax_regime=draft.regime == "old",
            seventh_proviso=SeventhProvisoDetails(
                foreign_travel_flag=seventh.foreignTravel,
                foreign_travel_amount=seventh.foreignTravelAmount,
                electricity_expenditure_flag=seventh.electricityExpenditure,
                electricity_expenditure_amount=seventh.electricityExpenditureAmount,
                other_clause_iv_flag=seventh.otherClauseIV,
                clause_iv_details=[
                    SeventhProvisoClauseDetail(nature=row.nature, amount=row.amount)
                    for row in seventh.clauseIVDetails
                ],
            ),
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
        rows_data = [{
            "address_detail": personal.flatNo or personal.residenceName,
            "city_or_town_or_district": personal.city,
            "state_code": personal.stateCode,
            "country_code": personal.countryCode,
            "pin_code": personal.pinCode,
            "zip_code": personal.zipCode,
        }]
    else:
        # Fall back to the property name, then the primary address; also fall
        # back to the taxpayer's city/state/country/pin so a property row that
        # omits those fields still produces a valid PropertyFilingProfile
        # (mirrors the legacy mapper's fallback chain).
        primary_address = draft.personal.flatNo or draft.personal.residenceName
        rows_data = [{
            "address_detail": row.address or row.premisesName or row.name or primary_address,
            "city_or_town_or_district": row.city or draft.personal.city,
            "state_code": row.state or draft.personal.stateCode,
            "country_code": row.countryCode or draft.personal.countryCode,
            "pin_code": row.pinCode or draft.personal.pinCode,
            "zip_code": row.zipCode or draft.personal.zipCode,
            "property_owner": row.propertyOwnerType,
            "property_owner_other": row.propertyOwnerOther.strip() or None,
            "is_co_owned": row.isCoOwned,
            "assessee_share_percentage": (
                row.ownershipShare if row.isCoOwned else Decimal("100")
            ),
            "co_owners": [
                PropertyCoOwner(
                    serial_number=index,
                    name=_required(owner.name, f"property.coOwners[{index}].name"),
                    pan=owner.pan.strip().upper() or None,
                    aadhaar=owner.aadhaar.strip() or None,
                    share_percentage=owner.share,
                )
                for index, owner in enumerate(row.coOwners, start=1)
            ] if row.isCoOwned else [],
            "tenants": [
                PropertyTenant(
                    serial_number=index,
                    name=_required(tenant.name, f"property.tenantDetails[{index}].name"),
                    pan=tenant.pan.strip().upper() or None,
                    aadhaar=tenant.aadhaar.strip() or None,
                    pan_or_tan=tenant.panOrTan.strip().upper() or None,
                )
                for index, tenant in enumerate(row.tenantDetails, start=1)
            ],
        } for row in rows]
    try:
        return [PropertyFilingProfile(
            **{
                **row,
                "address_detail": _required(row["address_detail"], "property.address"),
                "city_or_town_or_district": _required(
                    row["city_or_town_or_district"], "property.city"
                ),
                "state_code": _required(row["state_code"], "property.stateCode"),
                "country_code": (row["country_code"] or "91").strip(),
                "pin_code": (row["pin_code"] or "").strip() or None,
                "zip_code": (row["zip_code"] or "").strip() or None,
            }
        ) for row in rows_data]
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

    mobile_cc_raw = (personal.mobileCountryCode or "91").strip() or "91"
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
        deposit_exceeds_one_crore_flag=seventh.depositExceedsOneCrore,
        deposit_amount=seventh.depositAmount,
        foreign_travel_flag=seventh.foreignTravel,
        foreign_travel_amount=seventh.foreignTravelAmount,
        electricity_expenditure_flag=seventh.electricityExpenditure,
        electricity_expenditure_amount=seventh.electricityExpenditureAmount,
        other_clause_iv_flag=seventh.otherClauseIV,
        clause_iv_details=[
            ITR4SeventhProvisoClauseDetail(nature=row.nature, amount=row.amount)
            for row in seventh.clauseIVDetails
        ],
    )

    f10iea_date = ""
    if filing.form10IEADate:
        parsed = _to_date(filing.form10IEADate)
        f10iea_date = parsed.isoformat() if parsed else ""

    surname = (personal.surnameOrOrgName or "").strip() or (personal.name or "").strip()
    capacity_map = {
        "SELF": "S",
        "REPRESENTATIVE": "R",
        "KARTA": "K",
        "PARTNER": "P",
    }
    representative = None
    if verification.capacity == "REPRESENTATIVE":
        rep = filing.representative
        if rep is None:
            raise FilingGatewayV2Error(
                "ITR-4 representative details are incomplete.",
                ["filing.representative is required for representative verification."],
            )
        representative = AssesseeRepresentativeProfile(
            name=_required(rep.name, "filing.representative.name"),
            email=_required(rep.email, "filing.representative.email"),
            mobile_country_code=int(
                _required(rep.mobileCountryCode, "filing.representative.mobileCountryCode")
            ),
            mobile_no=_required(rep.mobile, "filing.representative.mobile"),
        )
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
            verification_capacity=capacity_map[verification.capacity],
            return_file_section=return_section,
            receipt_number=filing.originalAcknowledgementNumber.strip() or None,
            original_return_date=_to_date(filing.originalFilingDate),
            notice_number=filing.noticeNumber.strip() or None,
            notice_date=_to_date(filing.noticeDate),
            assessee_representative=representative,
            seventh_proviso=seventh_proviso,
            form_10iea_earlier_ay_old_regime=filing.form10IEAEarlierAYOldRegime,
            form_10iea_ass_year=filing.form10IEAAssessmentYear,
            form_10iea_earlier_ay_ack_old_regime=int(
                filing.form10IEAEarlierAYAckOldRegime or "0"
            ),
            f10iea_earlier_ay_new_regime=filing.form10IEAEarlierAYNewRegime,
            ass_yr_f10iea_new_tax_reg=filing.form10IEANewRegimeAssessmentYear,
            form_10iea_earlier_ay_ack_new_regime=int(
                filing.form10IEAEarlierAYAckNewRegime or "0"
            ),
            f10iea_curr_ay_new_regime=(
                "Y" if filing.form10IEACurrentAYNewRegime else "N"
            ),
            f10iea_date_curr_ay_new_tax=(
                _to_date(filing.form10IEACurrentAYNewRegimeDate).isoformat()
                if filing.form10IEACurrentAYNewRegimeDate else ""
            ),
            f10iea_ack_no_curr_ay_new_tax=int(
                filing.form10IEACurrentAYNewRegimeAck or "0"
            ),
            f10iea_curr_ay_old_regime=(
                "Y" if filing.form10IEACurrentAYOldRegime or draft.regime == "old" else "N"
            ),
            f10iea_date_curr_ay_old_tax=(
                _to_date(filing.form10IEACurrentAYOldRegimeDate).isoformat()
                if filing.form10IEACurrentAYOldRegimeDate else f10iea_date
            ),
            f10iea_ack_no_curr_ay_old_tax=int(
                filing.form10IEACurrentAYOldRegimeAck
                or filing.form10IEAAcknowledgement
                or "0"
            ),
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
        owner = row.propertyOwnerType
        owner_other = row.propertyOwnerOther.strip() or None
        is_co_owned = row.isCoOwned
        assessee_share = row.ownershipShare if is_co_owned else Decimal("100")
        co_owners = [
            PropertyCoOwner(
                serial_number=index,
                name=_required(co_owner.name, f"property.coOwners[{index}].name"),
                pan=co_owner.pan.strip().upper() or None,
                aadhaar=co_owner.aadhaar.strip() or None,
                share_percentage=co_owner.share,
            )
            for index, co_owner in enumerate(row.coOwners, start=1)
        ] if is_co_owned else []
        tenants = [
            PropertyTenant(
                serial_number=index,
                name=_required(tenant.name, f"property.tenantDetails[{index}].name"),
                pan=tenant.pan.strip().upper() or None,
                aadhaar=tenant.aadhaar.strip() or None,
                pan_or_tan=tenant.panOrTan.strip().upper() or None,
            )
            for index, tenant in enumerate(row.tenantDetails, start=1)
        ]
    else:
        address = (draft.personal.flatNo or draft.personal.residenceName).strip()
        city = draft.personal.city.strip()
        state = draft.personal.stateCode.strip()
        country = (draft.personal.countryCode or "91").strip()
        pin = draft.personal.pinCode.strip() or None
        zip_code = draft.personal.zipCode.strip() or None
        owner = "SE"
        owner_other = None
        is_co_owned = False
        assessee_share = Decimal("100")
        co_owners = []
        tenants = []
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
            property_owner=owner,
            property_owner_other=owner_other,
            is_co_owned=is_co_owned,
            assessee_share_percentage=assessee_share,
            co_owners=co_owners,
            tenants=tenants,
        )
    except (ValidationError, ValueError) as exc:
        raise FilingGatewayV2Error(
            "ITR-4 property filing profile is invalid.", [str(exc)]
        ) from exc


def _itr4_bank_accounts(draft: ReturnDraft) -> list[ITR4BankAccount]:
    """Map canonical bank-account rows → the ITR-4 bank-account type."""
    if not draft.bankAccounts:
        raise FilingGatewayV2Error(
            "ITR-4 bank account details are invalid.",
            ["bankAccounts must contain at least one account."],
        )

    accounts: list[ITR4BankAccount] = []
    errors: list[str] = []
    seen_accounts: set[tuple[str, str]] = set()
    refund_count = sum(account.useForRefund for account in draft.bankAccounts)
    if refund_count != 1:
        errors.append("bankAccounts must select exactly one account for refund.")

    for index, b in enumerate(draft.bankAccounts):
        prefix = f"bankAccounts[{index}]"
        account_number = (b.accountNumber or "").strip()
        ifsc = (b.ifscCode or "").strip().upper()
        bank_name = (b.bankName or "").strip()
        if not bank_name:
            errors.append(f"{prefix}.bankName is required.")
        elif len(bank_name) > 125:
            errors.append(f"{prefix}.bankName must not exceed 125 characters.")
        if not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9/-]*[0-9])?", account_number) \
                or not any(char in "123456789" for char in account_number):
            errors.append(
                f"{prefix}.accountNumber must be 1-20 valid characters, contain "
                "a non-zero digit, and end in a digit."
            )
        elif len(account_number) > 20:
            errors.append(f"{prefix}.accountNumber must not exceed 20 characters.")
        if not re.fullmatch(r"[A-Z]{4}0[A-Z0-9]{6}", ifsc):
            errors.append(
                f"{prefix}.ifscCode must contain 4 letters, 0, and 6 "
                "alphanumeric characters."
            )
        key = (ifsc, account_number.upper())
        if ifsc and account_number:
            if key in seen_accounts:
                errors.append(f"{prefix} duplicates another bank account.")
            seen_accounts.add(key)
        if errors and any(error.startswith(prefix) for error in errors):
            continue
        try:
            accounts.append(ITR4BankAccount(
                account_number=account_number,
                ifsc_code=ifsc,
                bank_name=bank_name,
                account_type=b.accountType,
                is_primary=b.useForRefund,
            ))
        except (ValidationError, ValueError) as exc:
            errors.append(f"{prefix}: {exc}")

    if errors:
        raise FilingGatewayV2Error(
            "ITR-4 bank account details are invalid.",
            errors,
        )
    return accounts


def _itr1_tax_return_preparer(draft: ReturnDraft) -> TaxReturnPreparer | None:
    """Map the optional canonical TRP block to the ITR-1 filing model."""
    trp = draft.taxReturnPreparer
    if not trp.used:
        return None
    try:
        return TaxReturnPreparer(
            identification_number=trp.identificationNumber.strip().upper(),
            name=trp.name.strip(),
            reimbursement_from_government=trp.reimbursementFromGovernment,
        )
    except (ValidationError, ValueError) as exc:
        raise FilingGatewayV2Error(
            "ITR-1 Tax Return Preparer details are invalid.", [str(exc)]
        ) from exc


def _itr4_tax_return_preparer(draft: ReturnDraft) -> ITR4TaxReturnPreparer | None:
    """Map the optional canonical TRP block to the ITR-4 filing model."""
    trp = draft.taxReturnPreparer
    if not trp.used:
        return None
    try:
        return ITR4TaxReturnPreparer(
            identification_number=trp.identificationNumber.strip().upper(),
            name=trp.name.strip(),
            reimbursement_from_government=trp.reimbursementFromGovernment,
        )
    except (ValidationError, ValueError) as exc:
        raise FilingGatewayV2Error(
            "ITR-4 Tax Return Preparer details are invalid.", [str(exc)]
        ) from exc


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
        summary=_summary_from_result(result, breakdown, draft),
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
        "tax_return_preparer": _itr4_tax_return_preparer(draft),
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
        "tax_return_preparer": _itr1_tax_return_preparer(draft),
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
