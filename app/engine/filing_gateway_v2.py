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
from app.engine.calculators.itr2 import ITR2Result, compute as compute_itr2
from app.engine.calculators.itr4 import ITR4Result, compute as compute_itr4
from app.engine.common.due_dates import filing_section_due_date_error, get_due_date
from app.engine.draft_to_itr1_input import (
    _SALARY_SECTIONS,
    _TAN_PATTERN,
    DraftMappingError,
    draft_to_itr1_input,
)
from app.engine.draft_to_itr2_input import draft_to_itr2_input
from app.engine.draft_to_itr4_input import draft_to_itr4_input
from app.engine.personal_profile import (
    NormalizedPropertyProfile,
    PersonalProfileError,
    normalize_bank_accounts,
    normalize_personal_profile,
    normalize_property_details,
    normalize_tax_return_preparer,
    personal_profile_source_hash,
    project_bank_account_itr1,
    project_bank_account_itr4,
    require_field,
    validate_bank_accounts_strict,
)
from app.engine.itd.itr1 import build_itr1_json
from app.engine.itd.itr1_schema import ITR1SchemaValidationError, validate_itr1_json
from app.engine.itd.itr2 import build_itr2_json
from app.engine.itd.itr2_schema import validate_itr2_json
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
from app.schemas.itr2 import (
    AssesseeStatus as ITR2AssesseeStatus,
    CompanyDirectorEntry,
    EmployerFilingDetail,
    ITR2FilingProfile,
    ITR2Input,
    JurisdictionResidenceEntry,
    PropertyFilingDetail,
    ResidentialStatus as ITR2ResidentialStatus,
    SeventhProvisoClauseEntry,
    TDS3FilingDetail,
    UnlistedEquityEntry,
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


def _reject_section_after_due_date(draft: ReturnDraft) -> None:
    """Block a return filed under 139(1) once its due date has gone.

    The date judged against is the one the return declares it is filed on —
    ``verification.date``, the value that becomes the CBDT ``Verification.Date``
    — falling back to today when the return does not declare one.
    """
    try:
        filing_on = _to_date(draft.verification.date)
    except ValueError:
        filing_on = None
    message = filing_section_due_date_error(
        draft.filing.filingSection,
        draft.form,
        draft.assessmentYear or "2026-27",
        filing_on,
    )
    if not message:
        return
    logger.info(
        "Filing section rejected against due date: form=%s ay=%s section=%s filedOn=%s",
        draft.form, draft.assessmentYear, draft.filing.filingSection, filing_on,
    )
    raise FilingGatewayV2Error(
        "The filing section is no longer available — the due date has passed.",
        [message],
    )


@dataclass(frozen=True)
class ITR1PipelineResult:
    """Immutable output from one canonical ITR-1 computation."""

    typed_input: ITR1Input
    computation: ITR1Result
    breakdown: dict[str, Any]
    summary: dict[str, Any]
    personal_profile_source_hash: str = ""


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
    simplified = draft.capitalGainsSchedule.simplified112A
    sale = simplified.totalSaleConsideration
    cost = simplified.totalCostAcquisition
    # Whether the simplified112A block actually carries data — the typed
    # schedule always has the block present (Pydantic default), so "present"
    # now means "non-zero", replacing the old dict-truthiness check.
    has_simplified = sale > 0 or cost > 0
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
    if has_simplified:
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
        "status": "VALID" if transactions else ("EMPTY" if not has_simplified else "EVIDENCE_ONLY"),
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
        profiles = _property_profiles(draft)
        filing_profile = _filing_profile(draft)
        tax_return_preparer = _itr1_tax_return_preparer(draft)
        filing_profile = filing_profile.model_copy(update={
            "bank_accounts": typed_input.bank_accounts,
            "tax_return_preparer": tax_return_preparer,
        })
        # filing_date is the date the return declares it is filed on --
        # verification.date, the same value _reject_section_after_due_date
        # judges the filing section against and that becomes the CBDT
        # Verification.Date. Previously never set here (the mapper leaves
        # ITR1Input.filing_date at its None default), so
        # compute_itr1()'s `if filing_date and due_date:` gate never ran and
        # 234A/234B/234C interest and 234F/234-I late fees were silently
        # zero for every return regardless of actual filing date -- found
        # 2026-09-03, see Docs/ITR1_FRONTEND_AND_SERIALIZATION_AUDIT_AY2026_27.md.
        filing_date = _to_date(draft.verification.date)
        due_date = get_due_date("ITR-1", draft.assessmentYear or "2026-27")
        typed_input = typed_input.model_copy(update={
            "filing_profile": filing_profile,
            "property_profile": profiles[0],
            "property_profiles": profiles,
            "tax_return_preparer": tax_return_preparer,
            "filing_date": filing_date,
            "due_date": due_date,
        })
        result = compute_itr1(typed_input)
    except FilingGatewayV2Error:
        raise
    except (DraftMappingError, ValidationError, ValueError) as exc:
        logger.debug("compute_canonical_itr1 REJECT mapping/compute error: %s", exc)
        errors = getattr(exc, "errors", None) or [str(exc)]
        raise FilingGatewayV2Error(
            "ITR-1 mapping or computation failed.",
            errors,
        ) from exc
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
        personal_profile_source_hash=personal_profile_source_hash(draft),
    )


def _required(value: str | None, field: str) -> str:
    """Return stripped required text or raise an actionable filing error.

    ``field`` may be either a bare personal-info key (``"fatherName"``) or an
    already-qualified draft path (``"verification.place"``). Only the bare form
    is prefixed. Blindly prefixing every field produced messages such as
    ``personal.verification.place`` and ``personal.filing.representative.name``,
    which point at a tab the field does not live on — the operator then cannot
    find the field the error is complaining about.
    """
    cleaned = (value or "").strip()
    if not cleaned:
        path = field if "." in field else f"personal.{field}"
        raise FilingGatewayV2Error(
            "ITR-1 filing profile is incomplete.",
            [f"{path} is required for official CBDT JSON."],
        )
    return cleaned


def _filing_profile(draft: ReturnDraft) -> ITR1FilingProfile:
    """Construct the official typed filing profile from canonical fields.

    Phase 5F: a thin adapter over ``app.engine.personal_profile``'s shared
    normalizer for the common-core fields; keeps ITR-1-specific policy here
    — the SELF/REPRESENTATIVE-only capacity gate, the ``is_revised``-gated
    ``original_acknowledgement_no``/``return_type`` fields (ITR-4 has no
    such gating), and no address truncation (ITR-1 has never truncated).
    """
    personal = draft.personal
    verification = draft.verification

    try:
        normalized = normalize_personal_profile(draft, form_error_prefix="ITR-1")
    except PersonalProfileError as exc:
        raise FilingGatewayV2Error(exc.message, exc.errors) from exc
    _reject_section_after_due_date(draft)

    if verification.capacity not in {"SELF", "REPRESENTATIVE"}:
        raise FilingGatewayV2Error(
            "ITR-1 verification capacity is invalid.",
            ["verification.capacity must be SELF or REPRESENTATIVE for ITR-1."],
        )

    try:
        employer_category = require_field(
            normalized.employer_category, "employerCategory", form_error_prefix="ITR-1"
        )
    except PersonalProfileError as exc:
        raise FilingGatewayV2Error(exc.message, exc.errors) from exc

    try:
        addr = normalized.primary_address
        address = FilingAddress(
            residence_no=addr.residence_no,
            residence_name=addr.residence_name,
            road_or_street=addr.road_or_street,
            locality_or_area=addr.locality_or_area,
            city_or_town_or_district=addr.city_or_town_or_district,
            state_code=addr.state_code,
            country_code=addr.country_code,
            pin_code=addr.pin_code,
            zip_code=addr.zip_code,
            mobile_country_code=addr.mobile_country_code,
            mobile_no=addr.mobile_no,
            email=addr.email,
            secondary_mobile_country_code=addr.secondary_mobile_country_code,
            secondary_mobile_no=addr.secondary_mobile_no,
            secondary_email=addr.secondary_email,
        )
        alternate_address = None
        if normalized.alternate_address is not None:
            alt = normalized.alternate_address
            alternate_address = PostalAddress(
                residence_no=alt.residence_no,
                residence_name=alt.residence_name,
                road_or_street=alt.road_or_street,
                locality_or_area=alt.locality_or_area,
                city_or_town_or_district=alt.city_or_town_or_district,
                state_code=alt.state_code,
                country_code=alt.country_code,
                pin_code=alt.pin_code,
                zip_code=alt.zip_code,
            )
        representative = None
        if normalized.representative is not None:
            r = normalized.representative
            representative = AssesseeRepresentativeProfile(
                name=r.name, email=r.email,
                mobile_country_code=r.mobile_country_code, mobile_no=r.mobile_no,
            )
        seventh = normalized.seventh_proviso
        return ITR1FilingProfile(
            pan=normalized.pan,
            first_name=normalized.first_name,
            middle_name=normalized.middle_name,
            surname=normalized.surname,
            date_of_birth=normalized.date_of_birth,
            employer_category=employer_category,
            aadhaar_number=normalized.aadhaar_number,
            primary_address=address,
            alternate_address=alternate_address,
            father_name=normalized.father_name,
            verification_place=normalized.verification_place,
            verification_capacity=(
                "R" if verification.capacity == "REPRESENTATIVE" else "S"
            ),
            return_file_section=normalized.return_file_section,
            return_type="R" if normalized.is_revised else "O",
            original_acknowledgement_no=(
                normalized.original_acknowledgement_no if normalized.is_revised else None
            ),
            original_return_date=normalized.original_return_date,
            notice_number=normalized.notice_number,
            notice_date=normalized.notice_date,
            assessee_representative=representative,
            opt_out_new_tax_regime=normalized.regime_is_old,
            seventh_proviso=SeventhProvisoDetails(
                foreign_travel_flag=seventh.foreign_travel,
                foreign_travel_amount=seventh.foreign_travel_amount,
                electricity_expenditure_flag=seventh.electricity_expenditure,
                electricity_expenditure_amount=seventh.electricity_expenditure_amount,
                other_clause_iv_flag=seventh.other_clause_iv,
                clause_iv_details=[
                    SeventhProvisoClauseDetail(nature=nature, amount=amount)
                    for nature, amount in seventh.clause_iv_details
                ],
            ),
        )
    except (ValidationError, ValueError) as exc:
        raise FilingGatewayV2Error("ITR-1 filing profile is invalid.", [str(exc)]) from exc


def _property_profiles(draft: ReturnDraft) -> list[PropertyFilingProfile]:
    """Build property filing profiles in the same order as compute rows.

    Phase 5F: the "has rows" case uses the shared property normalizer
    (``normalize_property_details``); the "no rows" synthetic single-row
    fallback (using the taxpayer's own address) is ITR-1-specific policy,
    kept here. Unlike ITR-4 (which tolerates a missing address by
    returning no property profile at all), ITR-1 REQUIRES address/city/
    state — that per-form policy is applied here via ``_required`` on the
    shared normalizer's (deliberately non-raising) output.
    """
    rows = draft.houseProperties
    if not rows:
        personal = draft.personal
        normalized_rows = [NormalizedPropertyProfile(
            address_detail=personal.flatNo or personal.residenceName,
            city_or_town_or_district=personal.city,
            state_code=personal.stateCode,
            country_code=personal.countryCode,
            pin_code=personal.pinCode,
            zip_code=personal.zipCode,
            property_owner="SE",
            property_owner_other=None,
            is_co_owned=False,
            assessee_share_percentage=Decimal("100"),
            co_owners=[],
            tenants=[],
        )]
    else:
        try:
            normalized_rows = normalize_property_details(draft, form_error_prefix="ITR-1")
        except PersonalProfileError as exc:
            raise FilingGatewayV2Error(exc.message, exc.errors) from exc
    try:
        return [PropertyFilingProfile(
            address_detail=_required(row.address_detail, "property.address"),
            city_or_town_or_district=_required(row.city_or_town_or_district, "property.city"),
            state_code=_required(row.state_code, "property.stateCode"),
            country_code=(row.country_code or "91").strip(),
            pin_code=(row.pin_code or "").strip() or None,
            zip_code=(row.zip_code or "").strip() or None,
            property_owner=row.property_owner,
            property_owner_other=row.property_owner_other,
            is_co_owned=row.is_co_owned,
            assessee_share_percentage=row.assessee_share_percentage,
            co_owners=[
                PropertyCoOwner(
                    serial_number=c.serial_number, name=c.name, pan=c.pan,
                    aadhaar=c.aadhaar, share_percentage=c.share_percentage,
                )
                for c in row.co_owners
            ],
            tenants=[
                PropertyTenant(
                    serial_number=t.serial_number, name=t.name, pan=t.pan,
                    aadhaar=t.aadhaar, pan_or_tan=t.pan_or_tan,
                )
                for t in row.tenants
            ],
        ) for row in normalized_rows]
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
    personal_profile_source_hash: str = ""


def _itr4_wire_format_address(addr) -> dict[str, Any]:
    """CBDT schema length-truncation, relocated (not new) — ITR-4's own,
    unchanged behavior, now an explicit step rather than inline in the
    profile builder. Operates on an already-normalized address; never
    mutates the canonical ``NormalizedAddress``/``NormalizedAlternateAddress``
    itself.
    """
    return {
        "residence_no": addr.residence_no[:50],
        "residence_name": addr.residence_name[:50],
        "road_or_street": addr.road_or_street[:50],
        "locality_or_area": addr.locality_or_area[:50],
        "city_or_town_or_district": addr.city_or_town_or_district[:50],
        "state_code": addr.state_code[:2],
        "country_code": addr.country_code,
        "pin_code": addr.pin_code,
        "zip_code": addr.zip_code,
    }


def _itr4_filing_profile(draft: ReturnDraft) -> ITR4FilingProfile:
    """Construct the official ITR-4 filing profile from canonical fields.

    Phase 5F: a thin adapter over ``app.engine.personal_profile``'s shared
    normalizer for the common-core fields (identity, address, filing
    section, verification, representative, seventh proviso), plus ITR-4's
    own wire-format truncation (an explicit, relocated step — see
    ``_itr4_wire_format_address``) and ITR-4-specific fields: assessee
    status (including FIRM), KARTA/PARTNER verification capacities, the
    Form-10IEA regime-switching block, and landline.
    """
    personal = draft.personal
    filing = draft.filing
    verification = draft.verification

    try:
        normalized = normalize_personal_profile(draft, form_error_prefix="ITR-4")
    except PersonalProfileError as exc:
        raise FilingGatewayV2Error(exc.message, exc.errors) from exc
    _reject_section_after_due_date(draft)

    try:
        employer_category = require_field(
            normalized.employer_category, "employerCategory", form_error_prefix="ITR-4"
        )
    except PersonalProfileError as exc:
        raise FilingGatewayV2Error(exc.message, exc.errors) from exc

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

    addr = normalized.primary_address
    try:
        primary_address = ITR4FilingAddress(
            **_itr4_wire_format_address(addr),
            mobile_country_code=addr.mobile_country_code,
            mobile_no=addr.mobile_no[:10],
            email=addr.email[:125],
            secondary_mobile_country_code=addr.secondary_mobile_country_code,
            secondary_mobile_no=addr.secondary_mobile_no,
            secondary_email=addr.secondary_email,
            landline_std_code=int(landline_std),
            landline_phone_no=landline_phone[:12],
        )
    except (ValidationError, ValueError) as exc:
        raise FilingGatewayV2Error(
            "ITR-4 filing profile is invalid.", [str(exc)]
        ) from exc

    alternate_address: ITR4PostalAddress | None = None
    if normalized.alternate_address is not None:
        alternate_address = ITR4PostalAddress(
            **_itr4_wire_format_address(normalized.alternate_address)
        )

    seventh = normalized.seventh_proviso
    seventh_proviso = ITR4SeventhProvisoDetails(
        deposit_exceeds_one_crore_flag=seventh.deposit_exceeds_one_crore,
        deposit_amount=seventh.deposit_amount,
        foreign_travel_flag=seventh.foreign_travel,
        foreign_travel_amount=seventh.foreign_travel_amount,
        electricity_expenditure_flag=seventh.electricity_expenditure,
        electricity_expenditure_amount=seventh.electricity_expenditure_amount,
        other_clause_iv_flag=seventh.other_clause_iv,
        clause_iv_details=[
            ITR4SeventhProvisoClauseDetail(nature=nature, amount=amount)
            for nature, amount in seventh.clause_iv_details
        ],
    )

    f10iea_date = ""
    if filing.form10IEADate:
        parsed = _to_date(filing.form10IEADate)
        f10iea_date = parsed.isoformat() if parsed else ""

    capacity_map = {
        "SELF": "S",
        "REPRESENTATIVE": "R",
        "KARTA": "K",
        "PARTNER": "P",
    }
    representative = None
    if normalized.representative is not None:
        r = normalized.representative
        representative = AssesseeRepresentativeProfile(
            name=r.name, email=r.email,
            mobile_country_code=r.mobile_country_code, mobile_no=r.mobile_no,
        )
    try:
        return ITR4FilingProfile(
            pan=normalized.pan,
            first_name=normalized.first_name[:25],
            middle_name=normalized.middle_name[:25],
            surname=normalized.surname[:75],
            date_of_birth=normalized.date_of_birth,
            employer_category=employer_category,
            aadhaar_number=normalized.aadhaar_number,
            assessee_status=assessee_status,
            primary_address=primary_address,
            alternate_address=alternate_address,
            father_name=normalized.father_name[:125],
            verification_place=normalized.verification_place[:50],
            verification_capacity=capacity_map[verification.capacity],
            return_file_section=normalized.return_file_section,
            receipt_number=normalized.original_acknowledgement_no,
            original_return_date=normalized.original_return_date,
            notice_number=normalized.notice_number,
            notice_date=normalized.notice_date,
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
    (ITR-4-specific policy, kept in this adapter — not shared, since ITR-2's
    contract requires an exact 1:1 count against ``draft.houseProperties``
    instead of a single-row-or-fallback shape). Also ITR-4-specific: a
    present-but-addressless row returns ``None`` rather than raising (ITR-1's
    adapter, by contrast, requires the address) — a real, deliberate
    per-form difference, not incidental duplication.
    """
    rows = draft.houseProperties
    if rows:
        try:
            normalized = normalize_property_details(draft, form_error_prefix="ITR-4")[0]
        except PersonalProfileError as exc:
            raise FilingGatewayV2Error(exc.message, exc.errors) from exc
        address = normalized.address_detail
        city = normalized.city_or_town_or_district
        state = normalized.state_code
        country = normalized.country_code
        pin = normalized.pin_code
        zip_code = normalized.zip_code
        owner = normalized.property_owner
        owner_other = normalized.property_owner_other
        is_co_owned = normalized.is_co_owned
        assessee_share = normalized.assessee_share_percentage
        co_owners = [
            PropertyCoOwner(
                serial_number=c.serial_number, name=c.name, pan=c.pan,
                aadhaar=c.aadhaar, share_percentage=c.share_percentage,
            )
            for c in normalized.co_owners
        ]
        tenants = [
            PropertyTenant(
                serial_number=t.serial_number, name=t.name, pan=t.pan,
                aadhaar=t.aadhaar, pan_or_tan=t.pan_or_tan,
            )
            for t in normalized.tenants
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
    """Map canonical bank-account rows → the ITR-4 bank-account type.

    Phase 5F: parsing (``normalize_bank_accounts``) and the rich ITR-4-style
    rule set (``validate_bank_accounts_strict`` — IFSC/account-number
    format, duplicates, exactly-one-refund-account) both now live in
    ``app.engine.personal_profile``, extracted verbatim (identical message
    text and ``bankAccounts[{index}].*`` prefix). This function still
    decides *when* to raise — ITR-4 raises immediately, before compute,
    exactly as before; that error-delivery timing is deliberately not
    unified with ITR-1's different (``ValidationReport``-based) mechanism.
    """
    if not draft.bankAccounts:
        raise FilingGatewayV2Error(
            "ITR-4 bank account details are invalid.",
            ["bankAccounts must contain at least one account."],
        )
    normalized = normalize_bank_accounts(draft.bankAccounts)
    errors, cleaned = validate_bank_accounts_strict(normalized, error_prefix="bankAccounts")
    if errors:
        raise FilingGatewayV2Error(
            "ITR-4 bank account details are invalid.",
            errors,
        )
    try:
        return [ITR4BankAccount(**project_bank_account_itr4(a)) for a in cleaned]
    except (ValidationError, ValueError) as exc:
        raise FilingGatewayV2Error(
            "ITR-4 bank account details are invalid.", [str(exc)]
        ) from exc


def _itr1_tax_return_preparer(draft: ReturnDraft) -> TaxReturnPreparer | None:
    """Map the optional canonical TRP block to the ITR-1 filing model."""
    normalized = normalize_tax_return_preparer(draft)
    if normalized is None:
        return None
    try:
        return TaxReturnPreparer(
            identification_number=normalized.identification_number,
            name=normalized.name,
            reimbursement_from_government=normalized.reimbursement_from_government,
        )
    except (ValidationError, ValueError) as exc:
        raise FilingGatewayV2Error(
            "ITR-1 Tax Return Preparer details are invalid.", [str(exc)]
        ) from exc


def _itr4_tax_return_preparer(draft: ReturnDraft) -> ITR4TaxReturnPreparer | None:
    """Map the optional canonical TRP block to the ITR-4 filing model."""
    normalized = normalize_tax_return_preparer(draft)
    if normalized is None:
        return None
    try:
        return ITR4TaxReturnPreparer(
            identification_number=normalized.identification_number,
            name=normalized.name,
            reimbursement_from_government=normalized.reimbursement_from_government,
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
        filing_profile = _itr4_filing_profile(draft)
        property_profile = _itr4_property_profile(draft)
        bank_accounts = _itr4_bank_accounts(draft)
        tax_return_preparer = _itr4_tax_return_preparer(draft)
        # See the identical comment in compute_canonical_itr1 -- this was
        # the same shared-root-cause bug, found while auditing ITR-4:
        # ITR4Input.filing_date was set to a placeholder (the taxpayer's
        # date of birth, per draft_to_itr4_input.py's stale "gateway sets
        # filing_date" comment) that this model_copy never actually
        # overwrote, so compute_itr4()'s interest/late-fee gate always saw
        # a "filing date" decades before the due date and computed zero.
        filing_date = _to_date(draft.verification.date)
        due_date = get_due_date("ITR-4", draft.assessmentYear or "2026-27")
        typed_input = typed_input.model_copy(update={
            "filing_profile": filing_profile,
            "property_profile": property_profile,
            "bank_accounts": bank_accounts,
            "tax_return_preparer": tax_return_preparer,
            "filing_date": filing_date,
            "due_date": due_date,
        })
        result = compute_itr4(typed_input)
    except FilingGatewayV2Error:
        raise
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
        personal_profile_source_hash=personal_profile_source_hash(draft),
    )


def _generate_cbdt_json_itr4(draft: ReturnDraft) -> tuple[dict[str, Any], dict[str, Any]]:
    """Build + validate the official ITR-4 CBDT JSON from a canonical draft.

    Runs the full CBDT Category A/B/D rule validators before JSON emission
    (parity with the legacy ``_build_itr4_official_json``).
    """
    pipeline = compute_canonical_itr4(draft)
    typed_input = pipeline.typed_input

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


# ---------------------------------------------------------------------------
# ITR-2 (Docs/ITR2_ITR3_V2_PIPELINE_PRODUCTION_PLAN.md Phase 4)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ITR2PipelineResult:
    """Immutable output from one canonical ITR-2 computation."""

    typed_input: ITR2Input
    computation: ITR2Result
    breakdown: dict[str, Any]
    summary: dict[str, Any]
    personal_profile_source_hash: str = ""


_ITR2_RESIDENTIAL_STATUS: dict[str, ITR2ResidentialStatus] = {
    "ROR": ITR2ResidentialStatus.RESIDENT,
    "RNOR": ITR2ResidentialStatus.NOT_ORDINARILY_RESIDENT,
    "NR": ITR2ResidentialStatus.NON_RESIDENT,
}


def _itr2_filing_profile(draft: ReturnDraft) -> ITR2FilingProfile:
    """Construct the official ITR-2 filing profile from canonical fields.

    Phase 5G follow-up: a thin adapter over ``app.engine.personal_profile``'s
    shared normalizer (closing a gap flagged in review — Phase 5F migrated
    ITR-1/ITR-4 only; ITR-2's builders were left on their own independent
    implementation). ITR-2-specific policy stays here: SELF/KARTA-only
    verification capacity — checked *before* calling the shared normalizer,
    since ITR-2 (unlike ITR-1/ITR-4) does not support REPRESENTATIVE at
    all; letting the shared normalizer's representative-required check run
    first on a REPRESENTATIVE-capacity draft would raise "representative
    details are incomplete" instead of the correct, more specific
    "capacity must be SELF or KARTA" — the two aren't the same error and
    an existing test asserts on the latter's text — the flat (non-nested)
    seventh-proviso fields, and the ITR-2-only declarations (residential
    status, director/unlisted-equity/FII-FPI, Portuguese Civil Code).
    """
    personal = draft.personal
    filing = draft.filing
    verification = draft.verification

    if verification.capacity not in {"SELF", "KARTA"}:
        raise FilingGatewayV2Error(
            "ITR-2 verification capacity is invalid.",
            ["verification.capacity must be SELF or KARTA for ITR-2 — "
             "representative-filed ITR-2 verification is not yet supported."],
        )

    try:
        normalized = normalize_personal_profile(draft, form_error_prefix="ITR-2")
    except PersonalProfileError as exc:
        raise FilingGatewayV2Error(exc.message, exc.errors) from exc
    _reject_section_after_due_date(draft)

    try:
        addr = normalized.primary_address
        address = FilingAddress(
            residence_no=addr.residence_no,
            residence_name=addr.residence_name,
            road_or_street=addr.road_or_street,
            locality_or_area=addr.locality_or_area,
            city_or_town_or_district=addr.city_or_town_or_district,
            state_code=addr.state_code,
            country_code=addr.country_code,
            pin_code=addr.pin_code,
            zip_code=addr.zip_code,
            mobile_country_code=addr.mobile_country_code,
            mobile_no=addr.mobile_no,
            email=addr.email,
            secondary_mobile_country_code=addr.secondary_mobile_country_code,
            secondary_mobile_no=addr.secondary_mobile_no,
            secondary_email=addr.secondary_email,
        )
        alternate_address = None
        if normalized.alternate_address is not None:
            alt = normalized.alternate_address
            alternate_address = PostalAddress(
                residence_no=alt.residence_no,
                residence_name=alt.residence_name,
                road_or_street=alt.road_or_street,
                locality_or_area=alt.locality_or_area,
                city_or_town_or_district=alt.city_or_town_or_district,
                state_code=alt.state_code,
                country_code=alt.country_code,
                pin_code=alt.pin_code,
                zip_code=alt.zip_code,
            )

        seventh = normalized.seventh_proviso
        status_map = {"I": ITR2AssesseeStatus.INDIVIDUAL, "H": ITR2AssesseeStatus.HUF}
        return ITR2FilingProfile(
            pan=normalized.pan,
            assessee_status=status_map.get(personal.assesseeStatus, ITR2AssesseeStatus.INDIVIDUAL),
            first_name=normalized.first_name,
            middle_name=normalized.middle_name,
            surname_or_org_name=normalized.surname,
            date_of_birth_or_formation=normalized.date_of_birth,
            aadhaar_number=normalized.aadhaar_number,
            primary_address=address,
            alternate_address=alternate_address,
            residential_status=_ITR2_RESIDENTIAL_STATUS.get(
                personal.residentialStatus, ITR2ResidentialStatus.RESIDENT
            ),
            return_file_section=normalized.return_file_section,
            receipt_number=normalized.original_acknowledgement_no,
            original_return_date=normalized.original_return_date,
            notice_number=normalized.notice_number,
            notice_date=normalized.notice_date,
            opted_out_new_tax_regime=normalized.regime_is_old,
            seventh_proviso_139=(
                seventh.deposit_exceeds_one_crore
                or seventh.foreign_travel
                or seventh.electricity_expenditure
                or seventh.other_clause_iv
            ),
            deposit_exceeds_one_crore=seventh.deposit_exceeds_one_crore,
            foreign_travel_expenditure=seventh.foreign_travel_amount,
            foreign_travel_flag=seventh.foreign_travel,
            electricity_expenditure=seventh.electricity_expenditure_amount,
            electricity_expenditure_flag=seventh.electricity_expenditure,
            current_account_deposits=seventh.deposit_amount,
            other_clause_iv_flag=seventh.other_clause_iv,
            seventh_proviso_clause_iv_entries=[
                SeventhProvisoClauseEntry(nature=nature, amount=amount)
                for nature, amount in seventh.clause_iv_details
                if nature in {"1", "2"}
            ],
            is_company_director=personal.isDirector,
            company_director_entries=[
                CompanyDirectorEntry(
                    company_name=row.companyName,
                    company_type=row.companyType,
                    pan=row.pan.strip() or None,
                    shares_type=row.sharesType,
                    din=row.din.strip() or None,
                )
                for row in personal.companyDirectorEntries
                if row.companyName
            ],
            held_unlisted_equity=personal.holdsUnlistedShares,
            unlisted_equity_entries=[
                UnlistedEquityEntry(
                    company_name=row.companyName,
                    company_type=row.companyType,
                    pan=row.pan.strip() or None,
                    opening_shares=int(row.openingShares),
                    opening_cost=row.openingCost,
                    acquired_shares=int(row.acquiredShares),
                    date_of_acquisition=_to_date(row.dateOfAcquisition),
                    face_value_per_share=row.faceValuePerShare,
                    issue_price_per_share=int(row.issuePricePerShare),
                    purchase_price_per_share=row.purchasePricePerShare,
                    transferred_shares=int(row.transferredShares),
                    transfer_sale_consideration=row.transferSaleConsideration,
                    closing_shares=int(row.closingShares),
                    closing_cost=row.closingCost,
                )
                for row in personal.unlistedEquityEntries
                if row.companyName
            ],
            is_fii_fpi=filing.isFiiFpi,
            sebi_registration_number=filing.sebiRegistrationNumber.strip() or None,
            lei_number=filing.leiNumber.strip() or None,
            lei_valid_upto_date=_to_date(filing.leiValidUptoDate),
            conditions_res_status=filing.conditionsResStatus or None,
            jurisdiction_residence_entries=[
                JurisdictionResidenceEntry(jurisdiction_code=row.jurisdictionCode, tin=row.tin)
                for row in filing.jurisdictionResidenceEntries
                if row.jurisdictionCode and row.tin
            ],
            total_stay_india_prev_yr=filing.totalStayIndiaPrevYr,
            total_stay_india_4_prec_yr=filing.totalStayIndia4PrecYr,
            benefit_us_115h=filing.benefitUs115H,
            # ITR2Input's cross-schedule validator requires this to equal
            # (schedule_5a is not None). Mirror draft_to_itr2_input.py's
            # _map_schedule_5a guard exactly (spouseName + spousePAN both
            # present) rather than just "object exists", so an in-progress,
            # incomplete Schedule 5A row (mapped to schedule_5a=None) does
            # not falsely claim the schedule applies. The frontend has no
            # control that sets filing.portugueseCivilCodeApplies
            # independently of filling in the schedule itself, so that flag
            # alone cannot be trusted.
            portuguese_civil_code_applies=bool(
                filing.portugueseCivilCodeApplies
                or (
                    draft.portugueseCivilCode is not None
                    and draft.portugueseCivilCode.spouseName
                    and draft.portugueseCivilCode.spousePAN
                )
            ),
            father_name=normalized.father_name,
            verification_place=normalized.verification_place,
            verification_capacity="K" if verification.capacity == "KARTA" else "S",
        )
    except (ValidationError, ValueError) as exc:
        raise FilingGatewayV2Error("ITR-2 filing profile is invalid.", [str(exc)]) from exc


def _itr2_property_filing_details(draft: ReturnDraft) -> list[PropertyFilingDetail]:
    """Map one ``PropertyFilingDetail`` per house property row.

    ``ITR2Input`` requires an exact 1:1 count match against however many
    property rows the draft carries (enforced by
    ``ITR2Input.validate_cross_schedule_contract``) — returning an empty
    list when there are no properties, rather than a placeholder row, keeps
    that count correct in the common no-house-property case.
    """
    details: list[PropertyFilingDetail] = []
    for index, row in enumerate(draft.houseProperties, start=1):
        city = (row.city or draft.personal.city).strip() or "City"
        state = (row.state or draft.personal.stateCode).strip() or "07"
        country = (row.countryCode or draft.personal.countryCode or "91").strip()
        pin = (row.pinCode or draft.personal.pinCode).strip() or None
        zip_code = (row.zipCode or draft.personal.zipCode).strip() or None
        address = (row.address or row.premisesName or row.name
                   or draft.personal.flatNo or draft.personal.residenceName).strip() or "NA"
        try:
            details.append(PropertyFilingDetail(
                address_detail=address[:200],
                city_or_town_or_district=city[:50],
                state_code=state[:2],
                country_code=country or "91",
                pin_code=pin,
                zip_code=zip_code,
                property_owner=row.propertyOwnerType,
                co_owned=row.isCoOwned,
                assessee_share_percent=row.ownershipShare if row.isCoOwned else Decimal("100"),
            ))
        except (ValidationError, ValueError) as exc:
            raise FilingGatewayV2Error(
                f"ITR-2 property filing detail [{index}] is invalid.", [str(exc)]
            ) from exc
    return details


def _itr2_employer_filing_details(draft: ReturnDraft) -> list[EmployerFilingDetail]:
    """Map one ``EmployerFilingDetail`` per row that becomes a TDS1 entry.

    Count must exactly match ``len(tds1_entries)``
    (``ITR2Input.validate_cross_schedule_contract``), so this replays the
    exact same accept/reject filter ``draft_to_itr1_input._map_tds`` uses to
    build ``tds1_entries`` (claimed-in-return, non-TDS3, valid TAN, salary
    section) over ``draft.taxes.tds``, rather than deriving counts from
    ``draft.employers`` independently — the two lists are not guaranteed to
    correspond 1:1 (an employer row need not have a matching TDS credit,
    and vice versa).
    """
    details: list[EmployerFilingDetail] = []
    for index, row in enumerate(draft.taxes.tds, start=1):
        if row.claimedInReturn is False or row.schedule == "TDS3":
            continue
        tan = (row.deductorTAN or "").strip().upper()
        if not _TAN_PATTERN.fullmatch(tan):
            continue
        section = (row.section or "").strip().upper()
        if section not in _SALARY_SECTIONS:
            continue
        employer = next(
            (e for e in draft.employers if (e.employerTAN or "").strip().upper() == tan),
            None,
        )
        # Must be byte-identical to TDS1Entry.employer_name
        # (`row.deductorName or None`, built by draft_to_itr1_input._map_tds)
        # — build_itr2_json's Schedule S rejects any filing-detail row whose
        # name doesn't match its TDS1 entry's name exactly.
        name = row.deductorName or "Employer"
        city = (
            (employer.employerCity if employer else "") or draft.personal.city
        ).strip() or "City"
        state = (
            (employer.employerStateCode if employer else "") or draft.personal.stateCode
        ).strip() or "07"
        address = ((employer.employerAddress if employer else "") or "NA").strip()
        try:
            details.append(EmployerFilingDetail(
                employer_tan=tan,
                employer_name=name[:125],
                nature_of_employment=(employer.natureOfEmployment if employer else "") or "OTH",
                address_detail=address[:200] or "NA",
                city_or_town_or_district=city[:50],
                state_code=state[:2],
            ))
        except (ValidationError, ValueError) as exc:
            raise FilingGatewayV2Error(
                f"ITR-2 employer filing detail [{index}] is invalid.", [str(exc)]
            ) from exc
    return details


def _itr2_tds3_filing_details(draft: ReturnDraft) -> list[TDS3FilingDetail]:
    """Map one ``TDS3FilingDetail`` per row that becomes a TDS3 entry.

    Count must exactly match ``len(tds3_entries)``
    (``ITR2Input.validate_cross_schedule_contract``), so this replays the
    exact same accept/reject filter ``draft_to_itr1_input._map_tds3`` uses
    (claimed-in-return, TDS3 schedule) rather than additionally requiring a
    non-empty PAN here — an empty-PAN row still becomes a ``TDS3Entry`` and
    must still get a matching filing-detail row to keep counts aligned.
    """
    details: list[TDS3FilingDetail] = []
    index = 0
    for row in draft.taxes.tds:
        if row.claimedInReturn is False or row.schedule != "TDS3":
            continue
        index += 1
        pan = (row.panOfTenant or "").strip().upper()
        head = row.headOfIncome if row.headOfIncome in {"HP", "CG", "OS", "EI"} else "OS"
        try:
            details.append(TDS3FilingDetail(
                buyer_tenant_pan=pan,
                head_of_income=head,
            ))
        except (ValidationError, ValueError) as exc:
            raise FilingGatewayV2Error(
                f"ITR-2 TDS3 filing detail [{index}] is invalid.", [str(exc)]
            ) from exc
    return details


def _itr2_capital_gains_summary(result: ITR2Result) -> dict[str, Any]:
    """Real Schedule CG/VDA totals for the ITR-2 response summary.

    Unlike ``_capital_gains_summary`` (ITR-1/4's *simplified* 112A-aggregate
    overlay, keyed to the frontend's aggregate-only CapitalGainsEntryManager
    view — not applicable here since ITR-2 carries the full per-transaction
    Schedule CG, not ``simplified112A``), this reads the true STCG/LTCG
    split and total directly off the engine's own ``schedules["cg"]``
    result rather than approximating or fabricating a per-row overlay.
    """
    cg = result.schedules.get("cg") if result.schedules else None
    stcg_total = _decimal_float(getattr(cg.stcg, "total_stcg", 0)) if cg else 0.0
    ltcg_total = _decimal_float(getattr(cg.ltcg, "total_ltcg", 0)) if cg else 0.0
    total_cg = _decimal_float(getattr(cg, "total_capital_gains", 0)) if cg else 0.0
    return {
        "status": "VALID" if cg is not None else "EMPTY",
        "totalSTCG": stcg_total,
        "totalLTCG": ltcg_total,
        "totalCapitalGains": total_cg,
        "vdaIncome": _decimal_float(result.vda_income),
    }


def _itr2_summary_from_result(
    result: ITR2Result,
    breakdown: dict[str, Any],
    draft: ReturnDraft,
) -> dict[str, Any]:
    """Build the v2 response summary for an ITR-2 computation.

    Mirrors ``_summary_from_result``'s shape (top-level headline aliases and
    breakdown block already consumed by the frontend for ITR-1/4) but reads
    ``ITR2Result``'s own field names throughout: it does not share
    ``ITR1Result``'s ``capital_gains_112a`` / ``advance_tax_paid`` /
    ``self_assessment_tax_paid`` attributes (``ITR2Result`` names these
    ``capital_gains_income`` / ``total_advance_tax`` /
    ``total_self_assessment_tax``), so calling ``_summary_from_result``
    directly on an ``ITR2Result`` raises ``AttributeError`` at runtime.
    """
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
            "thirtyPercentOfBalance": _decimal_float(row.standard_deduction_30pct),
            "interestOnBorrowedCapital": _decimal_float(row.interest_on_loan),
            "totalDeduction": _decimal_float(
                row.standard_deduction_30pct + row.interest_on_loan
            ),
            "arrearsUnrealizedRentReceived": _decimal_float(row.arrears_unrealised_rent),
            "incomeOfHP": _decimal_float(row.income_chargeable),
        }
        for index, row in enumerate(hp_rows, start=1)
    ]
    cg_summary = _itr2_capital_gains_summary(result)
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
        "advanceTax": _decimal_float(result.total_advance_tax),
        "selfAssessmentTax": _decimal_float(result.total_self_assessment_tax),
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
                "capitalGains": _decimal_float(result.capital_gains_income),
            },
            "deductions": deduction_breakdown,
            "tax": {
                "slabTax": _decimal_float(result.slab_tax),
                "specialRateTax": _decimal_float(result.special_rate_tax),
                "amtTax": _decimal_float(result.amt_tax),
                "rebate87A": _decimal_float(result.rebate_87a),
                "surcharge": _decimal_float(result.surcharge),
                "cess": _decimal_float(result.health_education_cess),
                "interest": _decimal_float(result.total_interest),
            },
            "credits": {
                "tds": total_tds,
                "tcs": _decimal_float(result.total_tcs),
                "advanceTax": _decimal_float(result.total_advance_tax),
                "selfAssessmentTax": _decimal_float(result.total_self_assessment_tax),
            },
        },
        "issues": issues,
        "creditValidationIssues": issues,
        "warnings": warnings,
        "calculationStatus": "CALCULATED_WITH_CREDIT_ISSUES" if issues else "CALCULATED",
        "computedByFormEngine": "ITR-2",
        "filingComputationStatus": "FORM_COMPUTATION",
        "capitalGainsSummary": cg_summary,
        "capitalGainsStatus": "FULL_SCHEDULE_CG",
        "capitalGainsIssues": [],
        "capitalGainsEligibility": {"ITR-2": True},
        "totalSTCG": cg_summary["totalSTCG"],
        "totalLTCG": cg_summary["totalLTCG"],
        "totalCapitalGains": cg_summary["totalCapitalGains"],
        "vdaIncome": cg_summary["vdaIncome"],
    }


def compute_canonical_itr2(draft: ReturnDraft) -> ITR2PipelineResult:
    """Map and compute a canonical ITR-2 draft exactly once.

    Phase 5G: prepares the *complete* ``ITR2Input`` — filing profile,
    property/employer/TDS3 filing details all attached — before calling
    ``compute_itr2``, mirroring ``compute_canonical_itr1``/``_itr4``
    exactly (both already do this; ITR-2 was the outlier, deferring this
    construction to JSON-generation time). CBDT Category A/B/D *validation*
    stays where it already is for every form — ``_generate_cbdt_json_itr2``
    — this phase only moves *construction*, not validation.

    Args:
        draft: Validated canonical return draft (``form == "ITR-2"``).

    Returns:
        Typed input (complete, with filing profile attached), computation,
        mapping breakdown, and response summary.

    Raises:
        FilingGatewayV2Error: If mapping, filing-profile construction, or
            computation fails, or pending reconciliation discrepancies
            block compute. Unlike ITR-1/4, ITR-2 has no "out of scope"
            evidence rejection — it is itself the form that
            scope-escalation routes *to*.
    """
    if draft.form != "ITR-2":
        raise FilingGatewayV2Error(
            "compute_canonical_itr2 requires draft.form == 'ITR-2'."
        )
    pending = [
        item for item in draft.reconciliation.discrepancies
        if item.status == "PENDING"
    ]
    if pending:
        raise FilingGatewayV2Error(
            "Manual confirmation is required for imported AIS/TIS "
            "reconciliation discrepancies before compute or generation.",
            [f"Pending reconciliation discrepancy: {category}."
             for category in sorted({item.category for item in pending})],
        )
    try:
        typed_input, breakdown = draft_to_itr2_input(draft)
        filing_profile = _itr2_filing_profile(draft)
        property_filing_details = _itr2_property_filing_details(draft)
        employer_filing_details = _itr2_employer_filing_details(draft)
        tds3_filing_details = _itr2_tds3_filing_details(draft)
        typed_input = typed_input.model_copy(update={
            "filing_profile": filing_profile,
            "filing_section": filing_profile.return_file_section,
            "property_filing_details": property_filing_details,
            "employer_filing_details": employer_filing_details,
            "tds3_filing_details": tds3_filing_details,
        })
        result = compute_itr2(typed_input)
    except FilingGatewayV2Error:
        raise
    except (DraftMappingError, ValidationError, ValueError) as exc:
        raise FilingGatewayV2Error(
            "ITR-2 mapping or computation failed.", [str(exc)]
        ) from exc
    if result.errors:
        raise FilingGatewayV2Error(
            "ITR-2 computation rejected the canonical draft.",
            [str(error) for error in result.errors],
        )
    return ITR2PipelineResult(
        typed_input=typed_input,
        computation=result,
        breakdown=breakdown,
        summary=_itr2_summary_from_result(result, breakdown, draft),
        personal_profile_source_hash=personal_profile_source_hash(draft),
    )


def _generate_cbdt_json_itr2(draft: ReturnDraft) -> tuple[dict[str, Any], dict[str, Any]]:
    """Build + validate the official ITR-2 CBDT JSON from a canonical draft.

    Phase 5G: reuses ``pipeline.typed_input`` — already complete, filing
    profile and all — with no late ``model_copy(update={...})`` enrichment
    and no direct ``ReturnDraft`` reads, matching ITR-1/ITR-4. Runs the full
    CBDT Category A/B/D rule validators before JSON emission —
    ``app/engine/validators/itr2/`` is a thin suite today (Phase 5
    completes it); whatever it does check still runs here, same as every
    other form.
    """
    pipeline = compute_canonical_itr2(draft)
    typed_input = pipeline.typed_input

    from app.engine.validators.itr2 import run_input_validation, run_calc_validation

    input_report = run_input_validation(typed_input)
    if not input_report.can_upload:
        raise FilingGatewayV2Error(
            "ITR-2 CBDT Category A input validation failed.",
            [r.message for r in input_report.blocking_errors],
        )
    calc_report = run_calc_validation(typed_input, pipeline.computation)
    if not calc_report.can_upload:
        raise FilingGatewayV2Error(
            "ITR-2 CBDT Category A calculation validation failed.",
            [r.message for r in calc_report.blocking_errors],
        )

    try:
        official_json = build_itr2_json(pipeline.computation, typed_input)
        validate_itr2_json(official_json)
    except Exception as exc:
        logger.exception(
            "ITR-2 official JSON generation failed: %s: %s",
            type(exc).__name__, exc,
        )
        raise FilingGatewayV2Error(
            "ITR-2 official JSON generation failed.",
            [f"{type(exc).__name__}: {exc}"],
        ) from exc
    return official_json, pipeline.summary


def compute_canonical(
    draft: ReturnDraft,
) -> ITR1PipelineResult | ITR2PipelineResult | ITR4PipelineResult:
    """Form-dispatching compute entrypoint (Phase 3/4).

    Used by ``tax_v2.compute_tax_summary_v2`` so ITR-1, ITR-2, and ITR-4 all
    compute via the single canonical pipeline — no legacy delegation.

    Args:
        draft: Validated canonical return draft.

    Returns:
        The per-form pipeline result (``ITR1PipelineResult``,
        ``ITR2PipelineResult``, or ``ITR4PipelineResult``).

    Raises:
        FilingGatewayV2Error: If the form is not ITR-1, ITR-2, or ITR-4
            (ITR-3 not yet supported by the v2 pipeline).
    """
    if draft.form == "ITR-1":
        return compute_canonical_itr1(draft)
    if draft.form == "ITR-2":
        return compute_canonical_itr2(draft)
    if draft.form == "ITR-4":
        return compute_canonical_itr4(draft)
    raise FilingGatewayV2Error(
        "The v2 canonical compute endpoint currently supports ITR-1, "
        "ITR-2, and ITR-4 only.",
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
    # Log the discriminators that actually decide whether generation succeeds.
    # Without this a 422 gives no way to tell a genuine data gap from a code
    # defect: the filingSection / returnType mismatch that blocked three clients
    # was invisible because nothing recorded which section the draft carried.
    filing = draft.filing
    logger.info(
        "CBDT generation requested: form=%s pan=%s section=%s returnType=%s "
        "origAck=%s origDate=%s declarationAccepted=%s regime=%s",
        draft.form,
        (draft.personal.pan or "").upper() or "<missing>",
        filing.filingSection,
        filing.returnType,
        "set" if (filing.originalAcknowledgementNumber or "").strip() else "empty",
        "set" if filing.originalFilingDate else "empty",
        draft.verification.declarationAccepted,
        draft.regime,
    )

    if draft.form == "ITR-1":
        return _generate_cbdt_json_itr1(draft)
    if draft.form == "ITR-2":
        return _generate_cbdt_json_itr2(draft)
    if draft.form == "ITR-4":
        return _generate_cbdt_json_itr4(draft)
    raise FilingGatewayV2Error(
        "The v2 canonical pipeline currently supports ITR-1, ITR-2, and "
        "ITR-4 only.",
        [f"Form {draft.form!r} is not supported by the v2 pipeline yet."],
    )


def _generate_cbdt_json_itr1(draft: ReturnDraft) -> tuple[dict[str, Any], dict[str, Any]]:
    """ITR-1 official JSON generation (the original generate_cbdt_json body)."""
    pipeline = compute_canonical_itr1(draft)
    typed_input = pipeline.typed_input

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
