"""
Unified filing gateway.

Central entry point that takes a saved flat draft (the frontend ``ReturnDraft``
serialized as a legacy JSON blob) and produces one of:

* A validated tax-computation summary (the same payload the
  ``/tax-summary/compute`` endpoint returns today).
* An official CBDT ITD-compliant JSON document for ITR-1 or ITR-4
  (ITR-2 and ITR-3 remain blocked until their canonical front-end
  mappers are complete).

The gateway enforces that **the same typed input** drives computation,
validation, and JSON generation — the single canonical pipeline mandated
by the Phase 1 audit.
"""

from __future__ import annotations

import datetime
import json
import re
from decimal import Decimal, InvalidOperation
from typing import Any, Optional

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.db.models import User
from app.routers.tax import compute_tax_summary

# ---------------------------------------------------------------------------
# Internal helpers (duplicated from app.routers.tax to avoid circular import)
# ---------------------------------------------------------------------------

_TAN_PATTERN = re.compile(r"^[A-Z]{4}[0-9]{5}[A-Z]$")
_PAN_PATTERN = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]$")
_BSR_PATTERN = re.compile(r"^[0-9]{7}$")
_CHALLAN_SERIAL_PATTERN = re.compile(r"^[0-9]{1,5}$")


class FilingGatewayError(Exception):
    """Raised when the filing gateway cannot produce a valid artifact."""

    def __init__(self, message: str, errors: list[str] | None = None) -> None:
        self.errors = errors or []
        super().__init__(message)


class FilingGatewayResult:
    """Successful gateway result containing summary data and optional JSON."""

    def __init__(
        self,
        *,
        form: str,
        summary: dict[str, Any],
        official_json: dict[str, Any] | None = None,
        computation_status: str = "FORM_COMPUTATION",
        validation_errors: list[str] | None = None,
    ) -> None:
        self.form = form
        self.summary = summary
        self.official_json = official_json
        self.computation_status = computation_status
        self.validation_errors = validation_errors or []

    @property
    def has_official_json(self) -> bool:
        return self.official_json is not None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_filing_artifact(
    *,
    flat_draft: dict[str, Any],
    user: User,
    db: Session | None = None,
    include_official_json: bool = False,
) -> FilingGatewayResult:
    """Run the canonical filing pipeline for a saved flat draft.

    Args:
        flat_draft: The raw JSON blob persisted by the frontend.
        user: Authenticated user (required for compute_tax_summary).
        db: Database session (unused today; reserved for future persistence).
        include_official_json: If True, also build the official CBDT JSON
            for ITR-1 and ITR-4. ITR-2 and ITR-3 raise an error.

    Returns:
        A :class:`FilingGatewayResult` with summary data and optional JSON.

    Raises:
        FilingGatewayError: If the form is unsupported or the typed input
            cannot be constructed/computed.
    """
    form = str(
        flat_draft.get("form", flat_draft.get("itrForm", ""))
    ).strip().upper()

    if form not in {"ITR-1", "ITR-2", "ITR-3", "ITR-4"}:
        raise FilingGatewayError(
            f"Unsupported or missing ITR form: {form!r}",
            errors=["form must be one of ITR-1, ITR-2, ITR-3, or ITR-4"],
        )

    # ── Step 1: Compute tax summary (shared for all forms) ─────────────
    engine_payload = dict(flat_draft)
    engine_payload["form"] = form
    engine_payload["itrForm"] = form
    engine_payload.setdefault("filingDate", None)
    engine_payload.setdefault("dueDate", None)
    engine_payload.setdefault("relief89", 0)

    regime = str(
        engine_payload.get("taxRegime", engine_payload.get("regime", "NEW"))
    ).upper()

    try:
        summary = compute_tax_summary(
            payload=engine_payload, regime=regime, current_user=user
        )
    except HTTPException as exc:
        detail = exc.detail
        message = "CBDT export blocked: tax computation rejected the input."
        errors: list[str] = []
        cg_summary = None
        if isinstance(detail, dict):
            if detail.get("message"):
                message = str(detail.get("message"))
            raw_errors = detail.get("errors", [])
            if isinstance(raw_errors, list):
                errors = [str(e) for e in raw_errors]
            cg_summary = detail.get("capitalGainsSummary")
        elif isinstance(detail, str):
            message = detail
            errors = [detail]
        # If the rejection is due to Section 112A losses or excess, translate
        # the raw engine detail into actionable taxpayer-facing guidance.
        if cg_summary and isinstance(cg_summary, dict):
            issues = cg_summary.get("issues") or []
            if isinstance(issues, list) and issues:
                loss_rows = [
                    str(i.get("row")) for i in issues
                    if isinstance(i, dict) and i.get("code") == "SECTION_112A_LOSS"
                ]
                if loss_rows:
                    errors = [
                        f"Capital-gain transactions in row(s) {', '.join(loss_rows)} "
                        f"result in long-term capital losses under Section 112A. "
                        f"ITR-1 and ITR-4 cannot report capital losses — file ITR-2 or ITR-3."
                    ] + [e for e in errors if "ITR-1" not in e and "ITR-4" not in e]
        raise FilingGatewayError(message, errors=errors or [message])
    except ValueError as exc:
        raise FilingGatewayError(
            "CBDT export blocked: tax computation failed.",
            errors=[str(exc)],
        )

    # ── Step 2: Build official JSON when requested ─────────────────────
    official_json: dict[str, Any] | None = None
    validation_errors: list[str] = []

    if include_official_json:
        if form == "ITR-3":
            raise FilingGatewayError(
                "ITR-3 official CBDT export is not implemented yet.",
                errors=["ITR-3 filing pipeline requires a dedicated implementation."],
            )

        if form == "ITR-2":
            raise FilingGatewayError(
                "ITR-2 official CBDT export requires a complete canonical ITR-2 "
                "filing profile and schedule evidence that the current flat editor "
                "does not supply.",
                errors=[
                    "Complete canonical ITR-2 filing profile is required.",
                    "Canonical employer/property filing details are required.",
                    "Full capital gains/VDA/losses/foreign assets schedules are required.",
                ],
            )

        if form == "ITR-1":
            official_json, validation_errors = _build_itr1_official_json(
                engine_payload, user
            )
        elif form == "ITR-4":
            official_json, validation_errors = _build_itr4_official_json(
                engine_payload, user
            )

    return FilingGatewayResult(
        form=form,
        summary=summary,
        official_json=official_json,
        computation_status=summary.get("filingComputationStatus", "FORM_COMPUTATION"),
        validation_errors=validation_errors,
    )


# ---------------------------------------------------------------------------
# ITR-1 official JSON pipeline
# ---------------------------------------------------------------------------

def _build_itr1_official_json(
    engine_payload: dict[str, Any],
    user: User,
) -> tuple[dict[str, Any], list[str]]:
    """Build ITR-1 typed input → compute → build JSON → validate schema."""
    from app.schemas.itr1 import ITR1Input
    from app.engine.calculators.itr1 import compute as compute_itr1
    from app.engine.itd.itr1 import build_itr1_json
    from app.engine.itd.itr1_schema import validate_itr1_json

    errors: list[str] = []

    # Step A: typed input construction.
    # The flat payload is already the accepted /tax-summary/compute contract.
    # For ITR-1 the typed Pydantic model requires fields not present in the
    # flat editor, so we construct it from the same payload the mapper uses.
    # When the mapper eventually gives way to explicit typed adapters this
    # call will become the canonical return-draft-to-ITR1Input mapper.
    try:
        typed_input = _build_itr1_input_from_flat(engine_payload)
    except Exception as exc:
        raise FilingGatewayError(
            "ITR-1 typed input construction failed.",
            errors=[str(exc)],
        )

    # Step A.5: cross-field validation — reject invalid inter-field
    # combinations before computation so the error messages are actionable.
    cross_field_errors = _validate_itr1_cross_fields(typed_input)
    if cross_field_errors:
        raise FilingGatewayError(
            "ITR-1 cross-field validation failed.",
            errors=cross_field_errors,
        )

    # Step B: compute
    try:
        result = compute_itr1(typed_input)
    except ValueError as exc:
        raise FilingGatewayError(
            "ITR-1 computation failed.",
            errors=[str(exc)],
        )

    if result.errors:
        raise FilingGatewayError(
            "ITR-1 computation rejected the input.",
            errors=list(result.errors),
        )

    # Step C: build official JSON
    try:
        itd_json = build_itr1_json(result, typed_input)
    except ValueError as exc:
        raise FilingGatewayError(
            "ITR-1 official JSON generation failed.",
            errors=[str(exc)],
        )

    # Step D: validate against the official schema. A filing artifact is not
    # downloadable unless it fully validates against the AY 2026-27 schema.
    try:
        validate_itr1_json(itd_json)
    except Exception as exc:
        raise FilingGatewayError(
            "ITR-1 official JSON failed schema validation.",
            errors=[str(exc)],
        ) from exc

    return itd_json, errors


# ---------------------------------------------------------------------------
# ITR-4 official JSON pipeline
# ---------------------------------------------------------------------------

def _build_itr4_official_json(
    engine_payload: dict[str, Any],
    user: User,
) -> tuple[dict[str, Any], list[str]]:
    """Build ITR-4 typed input → compute → build JSON → validate schema."""
    from app.schemas.itr4 import ITR4Input
    from app.engine.calculators.itr4 import compute as compute_itr4
    from app.engine.itd.itr4 import build_itr4_json
    from app.engine.itd.itr4_schema import validate_itr4_json

    errors: list[str] = []

    # Step A: typed input construction
    try:
        typed_input = _build_itr4_input_from_flat(engine_payload)
    except Exception as exc:
        raise FilingGatewayError(
            "ITR-4 typed input construction failed.",
            errors=[str(exc)],
        )

    # Step B: compute
    try:
        result = compute_itr4(typed_input)
    except ValueError as exc:
        raise FilingGatewayError(
            "ITR-4 computation failed.",
            errors=[str(exc)],
        )

    # Step C: determine business kwargs for builder
    biz_kwargs = _itr4_builder_kwargs(engine_payload)

    # Step D: build official JSON
    try:
        itd_json = build_itr4_json(result, typed_input, **biz_kwargs)
    except Exception as exc:
        raise FilingGatewayError(
            "ITR-4 official JSON generation failed.",
            errors=[str(exc)],
        )

    # Step E: validate against official schema
    try:
        validate_itr4_json(itd_json)
    except Exception as exc:
        errors.append(f"Official schema warning: {exc}")

    return itd_json, errors


# ---------------------------------------------------------------------------
# Flat → Typed input mappers (ITR-1 and ITR-4)
# ---------------------------------------------------------------------------

def _money(value: object) -> Decimal:
    """Convert an untrusted JSON monetary value to a non-negative Decimal."""
    if value is None or value == "":
        return Decimal("0")
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return Decimal("0")
    if not amount.is_finite() or amount < 0:
        return Decimal("0")
    return amount


def _first_money(*candidates: object) -> Decimal:
    """Return the first non-zero monetary value among candidates.

    The frontend always serializes every HouseProperty field (defaulting
    unused ones to 0), so ``dict.get("annualRent", fallback)`` returns 0
    and never reaches the ``annualLettingValue`` the user entered. This
    helper picks the first candidate that parses to a positive amount.
    """
    for value in candidates:
        amount = _money(value)
        if amount > 0:
            return amount
    return Decimal("0")


def _date(value: object, field_name: str) -> Optional[datetime.date]:
    if value is None or value == "":
        return None
    try:
        return datetime.date.fromisoformat(str(value))
    except ValueError:
        return None


def _records(payload: dict, key: str) -> list[dict]:
    """Return validated object records from a JSON array field."""
    value = payload.get(key)
    if value is None:
        return []
    if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
        return []
    return value


def _validate_itr1_cross_fields(typed_input: Any) -> list[str]:
    """Run cross-field validation rules on the typed ITR-1 input.

    Returns a list of human-readable error strings. An empty list means the
    input passed all cross-field checks. These rules complement the per-field
    Pydantic validators and the official schema validation gate.
    """
    errors: list[str] = []
    ded = typed_input.deductions_chapter6a
    profile = typed_input.filing_profile
    taxpayer_pan = profile.pan.upper() if profile and profile.pan else ""

    # Rule: donee PAN must not equal taxpayer PAN (80G, 80GGA, 80GGC).
    if ded.donations_80g:
        for donation in ded.donations_80g:
            if donation.donee_pan and donation.donee_pan.upper() == taxpayer_pan:
                errors.append(
                    f"Section 80G donee PAN {donation.donee_pan} must not equal "
                    f"the taxpayer PAN"
                )

    if typed_input.schedule_80gga and typed_input.schedule_80gga.donations:
        for donation in typed_input.schedule_80gga.donations:
            if donation.donee_pan and donation.donee_pan.upper() == taxpayer_pan:
                errors.append(
                    f"Section 80GGA donee PAN {donation.donee_pan} must not equal "
                    f"the taxpayer PAN"
                )

    if typed_input.schedule_80ggc and typed_input.schedule_80ggc.contributions:
        for contribution in typed_input.schedule_80ggc.contributions:
            pan = contribution.political_party_pan
            if pan and pan.upper() == taxpayer_pan:
                errors.append(
                    f"Section 80GGC political party PAN {pan} must not equal "
                    f"the taxpayer PAN"
                )

    # Rule: positive 80CCD(1B) claim requires PRAN evidence.
    if ded.amount_80ccd1b > 0 and not getattr(typed_input, 'pran_number', None):
        errors.append(
            "A positive Section 80CCD(1B) claim requires a PRAN number"
        )

    # Rule: TDS claimed must not exceed TDS deducted (TDS2 entries).
    for entry in typed_input.tds2_entries or []:
        if entry.tds_claimed_this_year > entry.tds_deducted:
            errors.append(
                f"TDS2 claimed credit for section {entry.tds_section} "
                f"exceeds the deducted amount"
            )

    # Rule: TDS3 claimed must not exceed TDS deducted.
    for entry in typed_input.tds3_entries or []:
        if entry.tds_claimed > entry.tds_deducted:
            errors.append(
                f"TDS3 claimed credit for tenant {entry.tenant_pan} "
                f"exceeds the deducted amount"
            )

    # Rule: TCS claimed must not exceed TCS collected.
    for entry in typed_input.tcs_entries or []:
        if entry.tcs_credit_claimed > entry.tcs_collected:
            errors.append(
                f"TCS claimed credit for section {entry.tcs_section} "
                f"exceeds the collected amount"
            )

    return errors


def _build_itr1_input_from_flat(payload: dict[str, Any]) -> Any:
    """Construct ``ITR1Input`` from the same flat payload contract used by
    ``/tax-summary/compute``.

    This is intentionally a thin, read-only mapping that mirrors the
    ITR-1 branch in ``_compute_tax_summary_impl``.  When that function is
    later refactored to accept typed input directly, this helper will
    simply delegate.
    """
    from app.schemas.itr1 import (
        ITR1Input, SalaryIncome, HousePropertyIncome, OtherSourcesIncome,
        Chapter6ADeductions, CapitalGainsIncome, Donation80G,
        Donation80GCategory, DonationAddress, TDS1Entry, TDS2Entry, TDS3Entry,
        TCSEntry, PropertyType, AgeBracket, TaxRegime, ITR1FilingProfile,
        FilingAddress, PostalAddress, PropertyFilingProfile, BankAccount,
        Donation80GGA, Schedule80GGA, Schedule80GGC, PoliticalContribution,
        Section80GGAClause, TaxReturnPreparer, HRADetails,
        SeventhProvisoDetails,
    )

    age = int(payload.get("age", 30) or 30)
    if age >= 80:
        age_bracket = AgeBracket.ABOVE_80
    elif age >= 60:
        age_bracket = AgeBracket.SIXTY_TO_80
    else:
        age_bracket = AgeBracket.BELOW_60

    regime_str = str(payload.get("taxRegime", payload.get("regime", "NEW"))).upper()
    tax_regime = TaxRegime.OLD if regime_str == "OLD" else TaxRegime.NEW

    def required_text(key: str, *, max_length: int | None = None) -> str:
        value = str(payload.get(key, "")).strip()
        if not value:
            raise ValueError(f"{key} is required for official ITR-1 JSON")
        if max_length is not None and len(value) > max_length:
            raise ValueError(f"{key} must not exceed {max_length} characters")
        return value

    def filing_section_code(value: object, official_code: object) -> int:
        section_map = {
            "139(1)": 11,
            "139(4)": 12,
            11: 11,
            12: 12,
            "11": 11,
            "12": 12,
        }
        code = section_map.get(value)
        if code is None:
            raise ValueError(
                "ITR-1 official JSON currently supports filing sections 139(1) and 139(4) only"
            )
        if official_code not in (None, ""):
            try:
                supplied_code = int(official_code)
            except (TypeError, ValueError) as exc:
                raise ValueError("returnFileSectionCode must be an official numeric filing-section code") from exc
            if supplied_code != code:
                raise ValueError("filingSection and returnFileSectionCode must describe the same return section")
        return code

    verification = payload.get("verification")
    verification_data = verification if isinstance(verification, dict) else {}
    if verification_data.get("declarationAccepted") is not True:
        raise ValueError("Verification declaration must be accepted for official ITR-1 JSON")
    if str(verification_data.get("capacity", "SELF")).upper() != "SELF":
        raise ValueError("Representative verification is not supported for official ITR-1 JSON")

    date_of_birth = _date(payload.get("dob"), "dob")
    if date_of_birth is None:
        raise ValueError("dob must be a valid YYYY-MM-DD date for official ITR-1 JSON")

    mobile_country_code_raw = str(payload.get("mobileCountryCode", "91")).strip()
    if not mobile_country_code_raw.isdigit():
        raise ValueError("mobileCountryCode must be numeric for official ITR-1 JSON")

    # Secondary mobile: when a secondary number is provided but the
    # country code is blank, inherit and persist the primary country code
    # so the UI fallback no longer causes a false validation failure.
    secondary_mobile_raw = str(payload.get("secondaryMobile", "")).strip()
    secondary_mobile_country_raw = str(
        payload.get("secondaryMobileCountryCode", "")
    ).strip() or mobile_country_code_raw
    secondary_mobile_no: Optional[str] = None
    secondary_mobile_country_code: int = 0
    if secondary_mobile_raw:
        if not secondary_mobile_country_raw.isdigit():
            raise ValueError(
                "secondaryMobileCountryCode must be numeric for official ITR-1 JSON"
            )
        secondary_mobile_country_code = int(secondary_mobile_country_raw)
        secondary_mobile_no = secondary_mobile_raw

    # Secondary email: optional, omitted from JSON when blank.
    secondary_email_raw = str(payload.get("secondaryEmail", "")).strip() or None

    primary_address = FilingAddress(
        residence_no=required_text("flatNo", max_length=50),
        residence_name=str(payload.get("premises", "")).strip(),
        road_or_street=str(payload.get("road", "")).strip(),
        locality_or_area=required_text("area", max_length=50),
        city_or_town_or_district=required_text("city", max_length=50),
        state_code=required_text("state", max_length=2),
        country_code=str(payload.get("country", "91")).strip() or "91",
        pin_code=(str(payload.get("pincode", "")).strip() or None),
        zip_code=str(payload.get("zipCode", "")).strip(),
        mobile_country_code=int(mobile_country_code_raw),
        mobile_no=required_text("mobile", max_length=10),
        email=required_text("email", max_length=125),
        secondary_mobile_country_code=secondary_mobile_country_code,
        secondary_mobile_no=secondary_mobile_no,
        secondary_email=secondary_email_raw,
    )

    alternate_raw = payload.get("alternateAddress")
    alternate_address = None
    if payload.get("secondaryAddressDifferent") is True:
        if not isinstance(alternate_raw, dict):
            raise ValueError("alternateAddress is required when secondaryAddressDifferent is true")
        alternate_address = PostalAddress(
            residence_no=str(alternate_raw.get("residenceNo", "")).strip(),
            residence_name=str(alternate_raw.get("residenceName", "")).strip(),
            road_or_street=str(alternate_raw.get("roadOrStreet", "")).strip(),
            locality_or_area=str(alternate_raw.get("localityOrArea", "")).strip(),
            city_or_town_or_district=str(alternate_raw.get("cityOrTownOrDistrict", "")).strip(),
            state_code=str(alternate_raw.get("stateCode", "")).strip(),
            country_code=str(alternate_raw.get("countryCode", "91")).strip() or "91",
            pin_code=(str(alternate_raw.get("pinCode", "")).strip() or None),
            zip_code=str(alternate_raw.get("zipCode", "")).strip(),
        )

    # Seventh-proviso to section 139(1) declarations (FilingStatus).
    seventh_proviso_raw = payload.get("seventhProviso")
    seventh_proviso = SeventhProvisoDetails()
    if isinstance(seventh_proviso_raw, dict):
        seventh_proviso = SeventhProvisoDetails(
            foreign_travel_flag=bool(seventh_proviso_raw.get("foreignTravel", False)),
            foreign_travel_amount=_money(seventh_proviso_raw.get("foreignTravelAmount")),
            electricity_expenditure_flag=bool(seventh_proviso_raw.get("electricityExpenditure", False)),
            electricity_expenditure_amount=_money(seventh_proviso_raw.get("electricityExpenditureAmount")),
            other_clause_iv_flag=bool(seventh_proviso_raw.get("otherClauseIV", False)),
            other_clause_iv_detail=str(seventh_proviso_raw.get("otherClauseIVDetail", "")).strip(),
        )

    # New-regime opt-out + Form 10-IEA.
    regime_str_for_opt = str(payload.get("taxRegime", payload.get("regime", "NEW"))).upper()
    opt_out_new_tax_regime = regime_str_for_opt == "OLD"
    form_10iea_ack = str(payload.get("form10IEAAcknowledgement", "")).strip()
    form_10iea_date_raw = payload.get("form10IEADate")
    form_10iea_date = _date(form_10iea_date_raw, "form10IEADate") if form_10iea_date_raw else None

    filing_profile = ITR1FilingProfile(
        pan=required_text("pan", max_length=10).upper(),
        first_name=str(payload.get("firstName", "")).strip(),
        middle_name=str(payload.get("middleName", "")).strip(),
        surname=required_text("surnameOrOrgName", max_length=75) if str(payload.get("surnameOrOrgName", "")).strip() else required_text("name", max_length=75),
        date_of_birth=date_of_birth,
        employer_category=str(payload.get("employerCategory", "OTH")).strip() or "OTH",
        aadhaar_number=(str(payload.get("aadhaar", "")).strip() or None),
        primary_address=primary_address,
        alternate_address=alternate_address,
        father_name=required_text("fatherName", max_length=125),
        verification_place=str(verification_data.get("place", "")).strip(),
        verification_capacity="S",
        return_file_section=filing_section_code(
            payload.get("filingSection", "139(1)"),
            payload.get("returnFileSectionCode"),
        ),
        opt_out_new_tax_regime=opt_out_new_tax_regime,
        seventh_proviso=seventh_proviso,
        form_10iea_acknowledgement=form_10iea_ack,
        form_10iea_date=form_10iea_date,
    )

    # Salary — same mapping as tax.py
    employers = _records(payload, "employerEntries")
    salary_rows = employers if employers else [payload]
    basic = sum(_money(row.get("basic")) for row in salary_rows)
    da = sum(_money(row.get("da")) for row in salary_rows)
    bonus = sum(_money(row.get("bonus")) for row in salary_rows)
    commission = sum(_money(row.get("commission")) for row in salary_rows)
    hra_received = sum(
        _money(row.get("hra", row.get("hraReceived"))) for row in salary_rows
    )
    perquisites = sum(_money(row.get("perquisites")) for row in salary_rows)
    profits_in_lieu = sum(_money(row.get("profitsInLieu")) for row in salary_rows)
    other_allowance = sum(
        _money(row.get("otherAllowance", row.get("allowances"))) for row in salary_rows
    )

    section_17_1_salary = basic + da + bonus + commission + hra_received + other_allowance
    hra_exempt = sum(_money(row.get("hraExempt")) for row in salary_rows)
    lta_exempt = sum(_money(row.get("ltaExempt")) for row in salary_rows)
    prof_tax = sum(
        _money(row.get("professionalTax", row.get("profTax"))) for row in salary_rows
    )
    ent_allowance = sum(
        _money(row.get("entertainmentAllowance")) for row in salary_rows
    )
    is_govt = any(bool(row.get("isGovernmentEmployee", False)) for row in salary_rows)

    salary_input = SalaryIncome(
        gross_salary=section_17_1_salary,
        perquisites_value=perquisites,
        profits_in_lieu_of_salary=profits_in_lieu,
        hra_exempt_amount=hra_exempt,
        lta_exempt_amount=lta_exempt,
        professional_tax_paid=prof_tax,
        entertainment_allowance=ent_allowance,
        is_government_employee=is_govt,
    )

    # HRA evidence — aggregate per-employer HRA facts into a single HRADetails
    # object so the official ScheduleEA10_13A can be emitted when HRA is claimed.
    rent_paid_total = sum(_money(row.get("rentPaid")) for row in salary_rows)
    is_metro = any(bool(row.get("isMetroCity", False)) for row in salary_rows)
    hra_details = None
    if hra_received > 0 or rent_paid_total > 0 or hra_exempt > 0:
        hra_details = HRADetails(
            actual_hra_received=hra_received,
            rent_paid=rent_paid_total,
            salary_for_hra=basic,
            dearness_allowance=da,
            is_metro_city=is_metro,
        )

    # House Property — map every canonical housePropertyEntries row. The
    # CBDT AY 2026-27 ITR-1 V1.1 schema permits at most two PropertyDetails
    # rows; the ITR1Input schema enforces this cap. Legacy single-property
    # payloads (no housePropertyEntries array) fall back to the flat payload.
    properties = _records(payload, "housePropertyEntries")
    if not properties:
        properties = [payload]

    hp_type_map = {
        "SELF": PropertyType.SELF_OCCUPIED,
        "SELF_OCCUPIED": PropertyType.SELF_OCCUPIED,
        "LET_OUT": PropertyType.LET_OUT,
        "DEEMED_LET_OUT": PropertyType.DEEMED_LET_OUT,
    }

    def _build_hp_input(prop: dict) -> HousePropertyIncome:
        raw_hp_type = str(prop.get("propertyType", prop.get("hpType", "self"))).upper()
        property_type = hp_type_map.get(raw_hp_type, PropertyType.LET_OUT)
        loan_interest = _money(prop.get("interestOnLoan"))
        if loan_interest == 0:
            loan_interest = sum(
                _money(loan.get("interestUs24B"))
                for loan in _records(prop, "homeLoans")
            )
        if loan_interest == 0:
            loan_interest = _money(prop.get("homeLoanInt", prop.get("sopLoanInt")))
        return HousePropertyIncome(
            property_type=property_type,
            annual_rent_received=_first_money(
                prop.get("annualRent"),
                prop.get("annualLettingValue"),
                prop.get("grossRent"),
            ),
            municipal_taxes_paid=_first_money(
                prop.get("municipalTaxesPaid"),
                prop.get("munTax"),
            ),
            home_loan_interest_paid=loan_interest,
            municipal_value=_money(prop.get("municipalRateableValue")),
            fair_rent=_money(prop.get("fairRentValue")),
            arrears_unrealised_rent_received=_money(prop.get("arrearsOfRent")),
        )

    def _build_property_profile(prop: dict, fallback: PropertyFilingProfile) -> PropertyFilingProfile:
        address = str(prop.get("address", prop.get("name", ""))).strip() or fallback.address_detail
        return PropertyFilingProfile(
            address_detail=address[:50],
            city_or_town_or_district=str(prop.get("city", payload.get("city", ""))).strip() or fallback.city_or_town_or_district,
            state_code=str(prop.get("state", payload.get("state", ""))).strip() or fallback.state_code,
            country_code=str(prop.get("countryCode", payload.get("country", "91"))).strip() or fallback.country_code,
            pin_code=(str(prop.get("pinCode", payload.get("pincode", ""))).strip() or fallback.pin_code),
            zip_code=(str(prop.get("zipCode", payload.get("zipCode", ""))).strip() or fallback.zip_code),
        )

    hp_inputs = [_build_hp_input(prop) for prop in properties]
    # Backward-compatible single-property scalar (first row).
    hp_input = hp_inputs[0]

    # Other Sources — mirror tax.py
    interest_rows = _records(payload, "interestEntries") or _records(payload, "bankInterestEntries")
    if interest_rows:
        savings_kinds = {"SAVINGS_BANK", "POST_OFFICE"}
        interest_sb = sum(
            _money(row.get("grossAmount"))
            for row in interest_rows
            if str(row.get("kind", row.get("itdTag", ""))).upper() in savings_kinds
        )
        interest_fd = sum(
            _money(row.get("grossAmount"))
            for row in interest_rows
            if str(row.get("kind", row.get("itdTag", ""))).upper() not in savings_kinds
        )
    else:
        interest_sb = _money(payload.get("interestSB"))
        interest_fd = _money(payload.get("interestFD"))
    post_office = _money(payload.get("postOfficeInterest"))

    dividend_rows = _records(payload, "dividendEntries")
    if dividend_rows:
        total_dividend = sum(_money(row.get("grossAmount")) for row in dividend_rows)
    else:
        total_dividend = (
            _money(payload.get("dividendShares"))
            + _money(payload.get("dividendMF"))
            + _money(payload.get("dividendUnits"))
            + _money(payload.get("dividends"))
        )

    family_pension_row = payload.get("familyPensionEntry")
    family_pension = (
        _money(family_pension_row.get("grossAmount"))
        if isinstance(family_pension_row, dict)
        else _money(payload.get("familyPension"))
    )

    os_input = OtherSourcesIncome(
        savings_bank_interest=interest_sb + post_office,
        fixed_deposit_interest=interest_fd,
        family_pension_received=family_pension,
        dividend_income=total_dividend,
    )

    # Deductions — same simplified mapping as tax.py
    investments_80c = payload.get("section80C")
    investment_rows_ded = (
        investments_80c.get("investments", [])
        if isinstance(investments_80c, dict)
        else []
    )
    if investment_rows_ded and all(isinstance(row, dict) for row in investment_rows_ded):
        total_80c = sum(_money(row.get("amount")) for row in investment_rows_ded)
    else:
        total_80c = sum(
            _money(payload.get(key))
            for key in ["s80C_epf", "s80C_ppf", "s80C_elss", "s80C_lic", "s80C_home"]
        )

    section_80d = payload.get("section80D")

    def _category_80d(category: object) -> tuple[Decimal, Decimal]:
        if not isinstance(category, dict):
            return Decimal("0"), Decimal("0")
        policies = category.get("policies") or []
        if not isinstance(policies, list):
            return Decimal("0"), Decimal("0")
        premiums = sum(
            _money(policy.get("premiumAmount"))
            for policy in policies
            if isinstance(policy, dict)
        )
        eligible = premiums + _money(category.get("medicalExpense"))
        preventive = _money(category.get("preventiveCheckup"))
        return eligible, preventive

    if isinstance(section_80d, dict):
        self_is_senior = section_80d.get("selfSeniorCitizen") in {"Y", "S"}
        parents_are_senior = section_80d.get("parentsSeniorCitizen") in {"Y", "P"}
        self_key = "selfFamilySenior" if self_is_senior else "selfFamily"
        parents_key = "parentsSenior" if parents_are_senior else "parents"
        self_80d, _ = _category_80d(section_80d.get(self_key))
        parents_80d, _ = _category_80d(section_80d.get(parents_key))
    else:
        parents_are_senior = False
        self_80d = _money(payload.get("s80D_self"))
        parents_80d = _money(payload.get("s80D_parent"))

    donation_rows = _records(payload, "donationEntries")
    donations = []
    for row in donation_rows:
        category_val = str(row.get("category", "100_NO_APPROVAL"))
        try:
            cat = Donation80GCategory(category_val)
        except ValueError:
            cat = Donation80GCategory.HUNDRED_WITHOUT_LIMIT
        address = None
        if any(row.get(key) for key in ("addrDetail", "city", "stateCode", "pinCode")):
            address = DonationAddress(
                address_line=str(row.get("addrDetail", "")),
                city_or_district=str(row.get("city", "")),
                state_code=str(row.get("stateCode", "")),
                pin_code=int(row.get("pinCode", 0)),
            )
        donations.append(Donation80G(
            category=cat,
            cash_amount=_money(row.get("donationAmtCash")),
            non_cash_amount=_money(row.get("donationAmtOtherMode")),
            donee_name=row.get("doneeName") or None,
            donee_pan=row.get("doneePAN") or None,
            approval_reference_number=row.get("arnNumber") or None,
            address=address,
            transaction_ref=row.get("transactionRefNum") or None,
            ifsc_code=row.get("ifscCode") or None,
        ))

    structured_80g_claim = sum(
        d.cash_amount + d.non_cash_amount for d in donations
    )

    # ── Schedule 80GGA / 80GGC / TRP — must be built before Chapter6ADeductions ──
    schedule_80gga_rows = _records(payload, "schedule80GGAEntries")
    schedule_80gga = None
    if schedule_80gga_rows:
        donations_80gga = []
        for row in schedule_80gga_rows:
            donations_80gga.append(Donation80GGA(
                relevant_clause=Section80GGAClause(str(row.get("relevantClause", ""))),
                donee_name=str(row.get("doneeName", "")).strip(),
                address=DonationAddress(
                    address_line=str(row.get("addressLine", "")).strip(),
                    city_or_district=str(row.get("city", "")).strip(),
                    state_code=str(row.get("stateCode", "")).strip(),
                    pin_code=int(str(row.get("pinCode", "0")).strip() or "0"),
                ),
                donee_pan=str(row.get("doneePAN", "")).strip().upper(),
                cash_amount=_money(row.get("cashAmount")),
                other_mode_amount=_money(row.get("otherModeAmount")),
            ))
        schedule_80gga = Schedule80GGA(donations=donations_80gga)

    schedule_80ggc_rows = _records(payload, "schedule80GGCEntries")
    schedule_80ggc = None
    if schedule_80ggc_rows:
        contributions_80ggc = []
        for row in schedule_80ggc_rows:
            contributions_80ggc.append(PoliticalContribution(
                cash_amount=_money(row.get("cashAmount")),
                other_mode_amount=_money(row.get("otherModeAmount")),
                contribution_date=_date(row.get("contributionDate"), "contributionDate"),
                transaction_ref=str(row.get("transactionRef", "")).strip() or None,
                ifsc_code=str(row.get("ifscCode", "")).strip().upper() or None,
                political_party_name=str(row.get("politicalPartyName", "")).strip() or None,
                political_party_pan=str(row.get("politicalPartyPAN", "")).strip().upper() or None,
            ))
        schedule_80ggc = Schedule80GGC(contributions=contributions_80ggc)

    trp_raw = payload.get("taxReturnPreparer")
    tax_return_preparer = None
    if isinstance(trp_raw, dict) and trp_raw.get("used") is True:
        tax_return_preparer = TaxReturnPreparer(
            identification_number=str(trp_raw.get("identificationNumber", "")).strip().upper(),
            name=str(trp_raw.get("name", "")).strip(),
            reimbursement_from_government=_money(trp_raw.get("reimbursementFromGovernment")),
        )

    old_regime_amount = lambda amount: amount if tax_regime == TaxRegime.OLD else Decimal("0")
    ded_input = Chapter6ADeductions(
        amount_80c=old_regime_amount(total_80c),
        amount_80ccd1b=old_regime_amount(_money(payload.get("s80CCD1B"))),
        amount_80ccd2=_money(payload.get("s80CCD2")),
        amount_80d_self_family=old_regime_amount(self_80d),
        amount_80d_parents=old_regime_amount(parents_80d),
        amount_80d_preventive_self=Decimal("0"),
        amount_80d_preventive_parents=Decimal("0"),
        has_parents_senior=parents_are_senior,
        amount_80e=old_regime_amount(_money(payload.get("s80E"))),
        # Savings-account interest alone qualifies under 80TTA; FD interest does not.
        amount_80tta=old_regime_amount(min(interest_sb + post_office, Decimal("10000"))),
        # 80TTB covers ALL deposit interest (SB + FD + RD + post office)
        # for senior citizens, capped at ₹50,000. Derived, not manual.
        amount_80ttb=old_regime_amount(min(interest_sb + interest_fd + post_office, Decimal("50000"))),
        amount_80g=old_regime_amount(structured_80g_claim if donations else _money(payload.get("s80G"))),
        amount_80gga=old_regime_amount(
            sum((donation.cash_amount + donation.other_mode_amount for donation in schedule_80gga.donations), Decimal("0"))
            if schedule_80gga is not None else _money(payload.get("s80GGA"))
        ),
        amount_80ggc=old_regime_amount(
            sum((contribution.cash_amount + contribution.other_mode_amount for contribution in schedule_80ggc.contributions), Decimal("0"))
            if schedule_80ggc is not None else _money(payload.get("s80GGC"))
        ),
        donations_80g=donations or None,
    )

    # Capital Gains — restricted 112A
    from app.engine.schedules.restricted_112a import compute_112a as compute_restricted_112a

    capital_gain_rows = _records(payload, "capitalGainTransactions")
    cg_input = None
    if capital_gain_rows:
        portfolio = compute_restricted_112a(capital_gain_rows)
        if portfolio.is_valid:
            cg_input = CapitalGainsIncome(
                ltcg_112a=max(Decimal("0"), portfolio.gross_gain),
                cost_of_acquisition=portfolio.cost_of_acquisition,
                full_value_of_consideration=portfolio.full_value_of_consideration,
            )
    else:
        cg_input = CapitalGainsIncome(
            ltcg_112a=_money(payload.get("ltcg112APre")) + _money(payload.get("ltcg112APost"))
        )

    # TDS/TCS
    tds1_entries = []
    tds2_entries = []
    tds3_entries = []
    for row in _records(payload, "tdsEntries"):
        if row.get("claimedInReturn") is False:
            continue
        tan = str(row.get("deductorTAN") or "").strip().upper()
        section = str(row.get("section") or "").strip().upper()
        tax = _money(row.get("taxDeducted", row.get("tdsDeducted")))
        gross = _money(row.get("grossAmount", row.get("incomeAmount")))
        schedule = str(row.get("schedule") or "").strip().upper()
        tenant_pan = str(row.get("panOfTenant") or row.get("deductorPAN") or "").strip().upper()
        tenant_name = str(row.get("nameOfTenant") or row.get("deductorName") or "").strip()
        # TDS3 rows carry tenant identity (PAN + name) rather than a deductor TAN.
        if schedule == "TDS3" or (tenant_pan and _PAN_PATTERN.fullmatch(tenant_pan)):
            try:
                tds3_entries.append(TDS3Entry(
                    tenant_pan=tenant_pan,
                    tenant_name=tenant_name,
                    tenant_aadhaar=str(row.get("aadhaarOfTenant") or "").strip() or None,
                    gross_receipt=_money(row.get("grsRcptToTaxDeduct", row.get("grossAmount"))),
                    tds_deducted=tax,
                    tds_claimed=_money(row.get("tdsClaimed", row.get("taxDeducted"))),
                    tds_section=section or "195",
                    deducted_yr=str(row.get("deductedYr") or "2025"),
                ))
            except ValidationError:
                continue
            continue
        if not tan or not _TAN_PATTERN.fullmatch(tan):
            continue
        try:
            if section in {"192", "S192"}:
                tds1_entries.append(TDS1Entry(
                    employer_tan=tan,
                    employer_name=str(row.get("deductorName") or "") or None,
                    income_chargeable=gross,
                    tds_deducted=tax,
                ))
            elif tax > 0 or gross > 0:
                tds2_entries.append(TDS2Entry(
                    deductor_tan=tan,
                    deductor_name=str(row.get("deductorName") or "") or None,
                    tds_section=section or "194A",
                    gross_amount=gross,
                    tds_deducted=tax,
                ))
        except ValidationError:
            continue

    tcs_entries = []
    for row in _records(payload, "tcsEntries"):
        tan = str(row.get("collectorTAN") or "")
        collected = _money(row.get("taxCollected", row.get("tcsCollected")))
        gross = _money(row.get("grossAmount"))
        if collected > 0 or gross > 0:
            if not tan:
                continue
            tcs_entries.append(TCSEntry(
                collector_tan=tan,
                collector_name=str(row.get("collectorName") or "") or None,
                tcs_section=str(row.get("section") or "206C"),
                gross_amount=gross,
                tcs_collected=collected,
            ))

    # Advance/SAT payments — mirror tax.py quarterly allocation
    advance_entries = _records(payload, "advanceTaxEntries")
    self_assessment_entries = _records(payload, "selfAssessmentTaxEntries")
    financial_year_end = datetime.date(2026, 3, 31)
    normalized_advance = list(advance_entries)
    normalized_sat: list[dict] = []
    for row in self_assessment_entries:
        deposit = _date(row.get("depositDate"), "")
        if deposit is not None and deposit <= financial_year_end:
            normalized_advance.append(row)
        else:
            normalized_sat.append(row)

    quarterly_advance = [Decimal("0")] * 4
    if normalized_advance:
        deadlines = (
            datetime.date(2025, 6, 15),
            datetime.date(2025, 9, 15),
            datetime.date(2025, 12, 15),
            datetime.date(2026, 3, 15),
        )
        for row in normalized_advance:
            amount = _money(row.get("amount"))
            deposit = _date(row.get("depositDate"), "")
            bucket = 3
            if deposit is not None:
                for idx, deadline in enumerate(deadlines):
                    if deposit <= deadline:
                        bucket = idx
                        break
            quarterly_advance[bucket] += amount
    else:
        quarterly_advance = [
            _money(payload.get(k)) for k in ["adv15Jun", "adv15Sep", "adv15Dec", "adv15Mar"]
        ]

    advance_tax_paid = sum(quarterly_advance)

    self_assessment_paid = Decimal("0")
    for row in normalized_sat:
        amount = _money(row.get("amount"))
        if amount > 0:
            bsr = str(row.get("bsrCode") or "").strip()
            challan = str(row.get("challanSerialNo", row.get("challanNo")) or "").strip()
            deposit = _date(row.get("depositDate"), "")
            if deposit is not None and _BSR_PATTERN.fullmatch(bsr) and _CHALLAN_SERIAL_PATTERN.fullmatch(challan) and int(challan) > 0:
                self_assessment_paid += amount
    if not self_assessment_entries and not normalized_sat:
        self_assessment_paid = _money(payload.get("selfTax"))

    bank_root = payload.get("bankAccountData")
    bank_source = bank_root.get("accounts") if isinstance(bank_root, dict) else payload.get("bankAccountDetails")
    bank_rows = bank_source if isinstance(bank_source, list) else []
    bank_accounts = [
        BankAccount(
            account_number=str(row.get("accountNumber", "")).strip(),
            ifsc_code=str(row.get("ifscCode", "")).strip().upper(),
            bank_name=str(row.get("bankName", "")).strip() or None,
            account_type={
                "SB": "savings", "SAVINGS": "savings", "CA": "current", "CURRENT": "current",
                "CC": "cash_credit", "OD": "overdraft", "NRO": "nro", "NRE": "nre",
            }.get(str(row.get("accountType", "")).strip().upper(), str(row.get("accountType", "")).strip()),
            is_primary=row.get("useForRefund") is True,
        )
        for row in bank_rows
        if isinstance(row, dict)
    ]

    # Build a backward-compatible single property_profile from the first row,
    # and a property_profiles list (one per housePropertyEntries row) for the
    # official two-property AY 2026-27 ITR-1 schema. The schema's
    # model_validator reconciles both representations.
    first_prop = properties[0]
    first_address = str(first_prop.get("address", first_prop.get("name", ""))).strip()
    if not first_address:
        first_address = primary_address.residence_no
    property_profile = PropertyFilingProfile(
        address_detail=first_address[:50],
        city_or_town_or_district=str(first_prop.get("city", payload.get("city", ""))).strip() or primary_address.city_or_town_or_district,
        state_code=str(first_prop.get("state", payload.get("state", ""))).strip() or primary_address.state_code,
        country_code=str(first_prop.get("countryCode", payload.get("country", "91"))).strip() or primary_address.country_code,
        pin_code=(str(first_prop.get("pinCode", payload.get("pincode", ""))).strip() or primary_address.pin_code),
        zip_code=(str(first_prop.get("zipCode", payload.get("zipCode", ""))).strip() or None),
    )
    property_profiles = [_build_property_profile(prop, property_profile) for prop in properties]

    return ITR1Input(
        age_bracket=age_bracket,
        tax_regime=tax_regime,
        salary_income=salary_input,
        house_property_income=hp_input,
        house_properties=hp_inputs,
        other_sources_income=os_input,
        deductions_chapter6a=ded_input,
        capital_gains=cg_input,
        tds1_entries=tds1_entries or None,
        tds2_entries=tds2_entries or None,
        tds3_entries=tds3_entries or None,
        tcs_entries=tcs_entries or None,
        advance_tax_paid=advance_tax_paid,
        self_assessment_tax_paid=self_assessment_paid,
        advance_tax_q1=quarterly_advance[0],
        advance_tax_q2=quarterly_advance[1],
        advance_tax_q3=quarterly_advance[2],
        advance_tax_q4=quarterly_advance[3],
        filing_date=_date(payload.get("filingDate"), "filingDate"),
        due_date=_date(payload.get("dueDate"), "dueDate"),
        house_property_count=max(1, len(properties)),
        relief_89=_money(payload.get("relief89", payload.get("relief_89"))),
        filing_profile=filing_profile,
        property_profile=property_profile,
        property_profiles=property_profiles,
        bank_accounts=bank_accounts,
        schedule_80gga=schedule_80gga,
        schedule_80ggc=schedule_80ggc,
        tax_return_preparer=tax_return_preparer,
        hra_details=hra_details,
        pran_number=str(payload.get("s80CCD1B_PRAN", "")).strip() or None,
    )


def _build_itr4_input_from_flat(payload: dict[str, Any]) -> Any:
    """Construct ``ITR4Input`` from the same flat payload contract used by
    ``/tax-summary/compute``.

    Mirrors the ITR-4 branch of ``_compute_tax_summary_impl``.
    """
    from app.schemas.itr4 import (
        ITR4Input, PresumptiveScheme,
        PresumptiveBusinessIncome44AD, PresumptiveProfessionalIncome44ADA,
        PresumptiveGoodsCarriage44AE, GoodsCarriageVehicle,
    )
    from app.schemas.itr1 import (
        SalaryIncome, HousePropertyIncome, OtherSourcesIncome,
        Chapter6ADeductions, CapitalGainsIncome, Donation80G,
        Donation80GCategory, DonationAddress, TDS1Entry, TDS2Entry,
        TCSEntry, PropertyType, AgeBracket, TaxRegime,
    )

    # Reuse the ITR-1 flat→typed mapping for shared components.
    # We construct a minimal ITR1Input-compatible dict and extract
    # the shared component models.
    itr1_partial = _build_itr1_input_from_flat(payload)
    age_bracket = itr1_partial.age_bracket
    tax_regime = itr1_partial.tax_regime
    salary_input = itr1_partial.salary_income
    hp_input = itr1_partial.house_property_income
    os_input = itr1_partial.other_sources_income
    ded_input = itr1_partial.deductions_chapter6a
    cg_input = itr1_partial.capital_gains
    tds1 = itr1_partial.tds1_entries
    tds2 = itr1_partial.tds2_entries
    tds3 = itr1_partial.tds3_entries
    tcs = itr1_partial.tcs_entries
    advance_tax = itr1_partial.advance_tax_paid
    sat_tax = itr1_partial.self_assessment_tax_paid
    q = [
        itr1_partial.advance_tax_q1,
        itr1_partial.advance_tax_q2,
        itr1_partial.advance_tax_q3,
        itr1_partial.advance_tax_q4,
    ]

    # Business rows
    business_rows = _records(payload, "businessEntries") or _records(payload, "businesses")
    business_row = business_rows[0] if business_rows else None
    biz_turnover = _money(payload.get("bizTurnover"))
    bp_profit = _money(payload.get("bizDeclared", payload.get("bpNetProfit")))
    scheme = str(payload.get("bizPresumptive", "44AD"))
    if business_row:
        scheme = str(business_row.get("scheme", scheme))

    properties = _records(payload, "housePropertyEntries")

    if scheme == "44ADA":
        digital = _money(business_row.get("digitalReceipts")) if business_row else biz_turnover
        cash = _money(business_row.get("nonDigitalReceipts")) if business_row else Decimal("0")
        gross = _money(business_row.get("grossReceipts")) if business_row else biz_turnover
        if gross == 0:
            gross = digital + cash
        declared = _money(business_row.get("declaredIncome")) if business_row else bp_profit
        return ITR4Input(
            age_bracket=age_bracket,
            tax_regime=tax_regime,
            salary_income=salary_input,
            house_property_income=hp_input,
            other_sources_income=os_input,
            deductions_chapter6a=ded_input,
            capital_gains=cg_input,
            tds1_entries=tds1 or None,
            tds2_entries=tds2 or None,
            tds3_entries=tds3 or None,
            tcs_entries=tcs or None,
            advance_tax_paid=advance_tax,
            self_assessment_tax_paid=sat_tax,
            advance_tax_q1=q[0],
            advance_tax_q2=q[1],
            advance_tax_q3=q[2],
            advance_tax_q4=q[3],
            filing_date=_date(payload.get("filingDate"), "filingDate"),
            due_date=_date(payload.get("dueDate"), "dueDate"),
            house_property_count=max(1, len(properties)),
            relief_89=itr1_partial.relief_89,
            presumptive_scheme=PresumptiveScheme.S44ADA,
            professional_income_44ada=PresumptiveProfessionalIncome44ADA(
                gross_receipts=gross,
                digital_receipts=digital,
                cash_receipts=cash,
                income_declared=declared,
            ),
        )

    if scheme == "44AE":
        vehicles: list = []
        if business_row:
            for vehicle in _records(business_row, "vehicles"):
                vehicle_type = str(vehicle.get("vehicleType", "OTHER")).upper()
                vehicles.append(GoodsCarriageVehicle(
                    is_heavy_goods_vehicle=vehicle_type == "HEAVY",
                    gross_vehicle_weight_tons=(
                        _money(vehicle.get("tonnage")) if vehicle_type == "HEAVY" else None
                    ),
                    months_owned=int(vehicle.get("ownedMonths") or 0),
                    income_declared=_money(vehicle.get("presumptiveIncome")) or None,
                ))
        return ITR4Input(
            age_bracket=age_bracket,
            tax_regime=tax_regime,
            salary_income=salary_input,
            house_property_income=hp_input,
            other_sources_income=os_input,
            deductions_chapter6a=ded_input,
            capital_gains=cg_input,
            tds1_entries=tds1 or None,
            tds2_entries=tds2 or None,
            tds3_entries=tds3 or None,
            tcs_entries=tcs or None,
            advance_tax_paid=advance_tax,
            self_assessment_tax_paid=sat_tax,
            advance_tax_q1=q[0],
            advance_tax_q2=q[1],
            advance_tax_q3=q[2],
            advance_tax_q4=q[3],
            filing_date=_date(payload.get("filingDate"), "filingDate"),
            due_date=_date(payload.get("dueDate"), "dueDate"),
            house_property_count=max(1, len(properties)),
            relief_89=itr1_partial.relief_89,
            presumptive_scheme=PresumptiveScheme.S44AE,
            goods_carriage_44ae=PresumptiveGoodsCarriage44AE(vehicles=vehicles),
        )

    # Default: 44AD
    digital = _money(business_row.get("digitalReceipts")) if business_row else biz_turnover
    cash = _money(business_row.get("nonDigitalReceipts")) if business_row else Decimal("0")
    total = digital + cash if business_row else biz_turnover
    declared = _money(business_row.get("declaredIncome")) if business_row else bp_profit

    return ITR4Input(
        age_bracket=age_bracket,
        tax_regime=tax_regime,
        salary_income=salary_input,
        house_property_income=hp_input,
        other_sources_income=os_input,
        deductions_chapter6a=ded_input,
        capital_gains=cg_input,
        tds1_entries=tds1 or None,
        tds2_entries=tds2 or None,
        tds3_entries=tds3 or None,
        tcs_entries=tcs or None,
        advance_tax_paid=advance_tax,
        self_assessment_tax_paid=sat_tax,
        advance_tax_q1=q[0],
        advance_tax_q2=q[1],
        advance_tax_q3=q[2],
        advance_tax_q4=q[3],
        filing_date=_date(payload.get("filingDate"), "filingDate"),
        due_date=_date(payload.get("dueDate"), "dueDate"),
        house_property_count=max(1, len(properties)),
        relief_89=itr1_partial.relief_89,
        presumptive_scheme=PresumptiveScheme.S44AD,
        business_income_44ad=PresumptiveBusinessIncome44AD(
            total_turnover=total,
            digital_turnover=digital,
            cash_turnover=cash,
            income_declared=declared,
        ),
    )


def _itr4_builder_kwargs(payload: dict[str, Any]) -> dict[str, Any]:
    """Extract business kwargs for ``build_itr4_json`` from the flat payload."""
    business_rows = _records(payload, "businessEntries") or _records(payload, "businesses")
    business_row = business_rows[0] if business_rows else None
    scheme = str(payload.get("bizPresumptive", "44AD"))
    if business_row:
        scheme = str(business_row.get("scheme", scheme))

    if scheme == "44ADA":
        digital = float(_money(business_row.get("digitalReceipts")) if business_row else _money(payload.get("bizTurnover")))
        cash = float(_money(business_row.get("nonDigitalReceipts")) if business_row else Decimal("0"))
        gross = float(_money(business_row.get("grossReceipts")) if business_row else _money(payload.get("bizTurnover")))
        if gross == 0:
            gross = digital + cash
        return {
            "bp_gross_turnover": gross,
            "bp_digital_turnover": digital,
            "bp_cash_turnover": cash,
            "bp_scheme": "44ADA",
        }

    if scheme == "44AE":
        return {
            "bp_gross_turnover": 0,
            "bp_digital_turnover": 0,
            "bp_cash_turnover": 0,
            "bp_scheme": "44AE",
        }

    # 44AD
    digital = float(_money(business_row.get("digitalReceipts")) if business_row else _money(payload.get("bizTurnover")))
    cash = float(_money(business_row.get("nonDigitalReceipts")) if business_row else Decimal("0"))
    total = digital + cash if business_row else float(_money(payload.get("bizTurnover")))
    return {
        "bp_gross_turnover": total,
        "bp_digital_turnover": digital,
        "bp_cash_turnover": cash,
        "bp_scheme": "44AD",
    }
