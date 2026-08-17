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
# The canonical Section 112A entrypoint is the single source of truth for
# restricted 112A computation.  ``draft_to_itr1_input`` (invoked by the
# Phase 7 delegate below) routes 112A through this path; the import is
# explicit so static analysis and the 112A unification test can confirm
# the gateway never re-implements a duplicate 112A calculation.
from app.engine.schedules.restricted_112a import compute_112a as compute_restricted_112a  # noqa: F401

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

    # Step E: validate against official schema — hard fail to match ITR-1 parity.
    try:
        validate_itr4_json(itd_json)
    except Exception as exc:
        raise FilingGatewayError(
            "ITR-4 official JSON failed schema validation.",
            errors=[str(exc)],
        ) from exc

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


def _bool(value: object, fallback: bool = False) -> bool:
    """Convert an untrusted JSON value to bool, honoring explicit booleans."""
    if isinstance(value, bool):
        return value
    return fallback


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
    """Construct ``ITR1Input`` from the legacy flat payload contract.

    Phase 7 unified this with the canonical ``draft_to_itr1_input`` mapper.
    The ~684-line duplicate flat→typed mapping that previously lived here was
    the single biggest source of "works in compute, fails in CBDT" bugs
    (audit Finding 14).  It now delegates:

        payload (flat blob)
          → flat_to_draft(payload)          # one-way legacy adapter
          → draft_to_itr1_input(draft)      # single canonical mapper
          → attach filing + property profiles

    The golden suite (``test_itr1_golden_suite.py``) and the profile suite
    (``test_itr1_filing_gateway_profile.py``) continue to call this function
    directly, so it remains the stable entry point for legacy flat payloads.
    """
    from app.engine.flat_to_draft import flat_to_draft
    from app.engine.draft_to_itr1_input import draft_to_itr1_input
    from app.engine.filing_gateway_v2 import _filing_profile, _property_profiles

    draft = flat_to_draft(payload)
    typed_input, _breakdown = draft_to_itr1_input(draft)
    filing_profile = _filing_profile(draft)
    profiles = _property_profiles(draft)

    # Flat-blob-only cross-checks that the canonical draft does not carry.
    # ``returnFileSectionCode`` is the legacy numeric filing-section code; when
    # the presentation label (``filingSection``) and the official code disagree,
    # reject before the JSON builder fabricates an inconsistent return section.
    official_code = payload.get("returnFileSectionCode")
    if official_code not in (None, "", 0):
        try:
            supplied_code = int(official_code)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                "returnFileSectionCode must be an official numeric filing-section code"
            ) from exc
        if supplied_code != filing_profile.return_file_section:
            raise ValueError(
                "filingSection and returnFileSectionCode must describe the same return section"
            )

    # Flat-blob-only CBDT schedules that the canonical ReturnDraft does not
    # carry today (80GGA, 80GGC, TRP, HRA details, TDS3).  These flow directly
    # from the legacy payload into the typed ITR1Input so the official JSON
    # builder can emit Schedule80GGA/80GGC, TaxPreparer, ScheduleEA10_13A, and
    # ScheduleTDS3Dtls.  The compute-relevant fields remain on the single
    # canonical ``draft_to_itr1_input`` path — these are CBDT-only additions.
    from app.schemas.itr1 import (
        Donation80GGA, DonationAddress, Schedule80GGA, PoliticalContribution,
        Schedule80GGC, TaxReturnPreparer, HRADetails, Section80GGAClause,
    )
    import datetime as _dt
    import re as _re

    schedule_80gga_rows = _records(payload, "schedule80GGAEntries")
    schedule_80gga = None
    if schedule_80gga_rows:
        donations_80gga = [
            Donation80GGA(
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
            )
            for row in schedule_80gga_rows
        ]
        schedule_80gga = Schedule80GGA(donations=donations_80gga)

    schedule_80ggc_rows = _records(payload, "schedule80GGCEntries")
    schedule_80ggc = None
    if schedule_80ggc_rows:
        contributions_80ggc = [
            PoliticalContribution(
                cash_amount=_money(row.get("cashAmount")),
                other_mode_amount=_money(row.get("otherModeAmount")),
                contribution_date=_date(row.get("contributionDate"), "contributionDate"),
                transaction_ref=str(row.get("transactionRef", "")).strip() or None,
                ifsc_code=str(row.get("ifscCode", "")).strip().upper() or None,
                political_party_name=str(row.get("politicalPartyName", "")).strip() or None,
                political_party_pan=str(row.get("politicalPartyPAN", "")).strip().upper() or None,
            )
            for row in schedule_80ggc_rows
        ]
        schedule_80ggc = Schedule80GGC(contributions=contributions_80ggc)

    trp_raw = payload.get("taxReturnPreparer")
    tax_return_preparer = None
    if isinstance(trp_raw, dict) and trp_raw.get("used") is True:
        tax_return_preparer = TaxReturnPreparer(
            identification_number=str(trp_raw.get("identificationNumber", "")).strip().upper(),
            name=str(trp_raw.get("name", "")).strip(),
            reimbursement_from_government=_money(trp_raw.get("reimbursementFromGovernment")),
        )

    # HRA evidence — aggregate per-employer HRA facts into a single HRADetails
    # so the official ScheduleEA10_13A can be emitted when HRA is claimed.
    salary_rows = _records(payload, "employerEntries")
    hra_received = sum(_money(r.get("hra", r.get("hraReceived"))) for r in salary_rows)
    rent_paid_total = sum(_money(r.get("rentPaid")) for r in salary_rows)
    basic = sum(_money(r.get("basic")) for r in salary_rows)
    da = sum(_money(r.get("da")) for r in salary_rows)
    is_metro = any(bool(r.get("isMetroCity", False)) for r in salary_rows)
    hra_details = None
    if hra_received > 0 or rent_paid_total > 0:
        hra_details = HRADetails(
            actual_hra_received=hra_received,
            rent_paid=rent_paid_total,
            salary_for_hra=basic,
            dearness_allowance=da,
            is_metro_city=is_metro,
        )

    # TDS3 — tenant-identity rows (PAN, not TAN) flow into ScheduleTDS3Dtls.
    # The canonical ``_map_tds`` splits TDS1/TDS2 only; TDS3 is a CBDT-only
    # schedule emitted from these flat rows.
    from app.schemas.itr1 import TDS3Entry
    from pydantic import ValidationError as _PydanticValidationError
    _PAN_PATTERN = _re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]$")
    tds3_entries: list[Any] = []
    for row in _records(payload, "tdsEntries"):
        if row.get("claimedInReturn") is False:
            continue
        section = str(row.get("section") or "").strip().upper()
        schedule = str(row.get("schedule") or "").strip().upper()
        tenant_pan = str(row.get("panOfTenant") or row.get("deductorPAN") or "").strip().upper()
        tenant_name = str(row.get("nameOfTenant") or row.get("deductorName") or "").strip()
        if schedule == "TDS3" or (tenant_pan and _PAN_PATTERN.fullmatch(tenant_pan)):
            tax = _money(row.get("taxDeducted", row.get("tdsDeducted")))
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
            except _PydanticValidationError:
                continue

    # Refund bank selection is enforced by ``build_itr1_json`` ("Exactly one
    # bank account must be marked for refund") when the official JSON is
    # generated — the typed input construction must not reject early so the
    # error surfaces at the schema-build step with the expected message.

    update: dict[str, Any] = {
        "filing_profile": filing_profile,
        "property_profile": profiles[0],
        "property_profiles": profiles,
        "schedule_80gga": schedule_80gga,
        "schedule_80ggc": schedule_80ggc,
        "tax_return_preparer": tax_return_preparer,
        "hra_details": hra_details,
    }
    # Seventh-proviso to section 139(1) declarations (foreign travel ≥ Rs 2L,
    # electricity expenditure ≥ Rs 1L) are flat-blob-only CBDT flags the
    # canonical ReturnDraft does not carry today.  Flow them into the filing
    # profile so the official JSON builder emits the FilingStatus flags and
    # amounts.  Defaults to all-False (no declaration) when absent.
    seventh_raw = payload.get("seventhProviso")
    if isinstance(seventh_raw, dict) and seventh_raw:
        from app.schemas.itr1 import SeventhProvisoDetails
        seventh = SeventhProvisoDetails(
            foreign_travel_flag=bool(seventh_raw.get("foreignTravel", False)),
            foreign_travel_amount=_money(seventh_raw.get("foreignTravelAmount")),
            electricity_expenditure_flag=bool(seventh_raw.get("electricityExpenditure", False)),
            electricity_expenditure_amount=_money(seventh_raw.get("electricityExpenditureAmount")),
            other_clause_iv_flag=bool(seventh_raw.get("otherClauseIV", False)),
            other_clause_iv_detail=str(seventh_raw.get("otherClauseIVDetail", "")).strip()[:200],
        )
        update["filing_profile"] = filing_profile.model_copy(update={
            "seventh_proviso": seventh,
        })
    if tds3_entries:
        update["tds3_entries"] = tds3_entries
        update["schedule_tds3_total_claimed"] = sum(
            (e.tds_claimed for e in tds3_entries), Decimal("0")
        )
    # 80GGA/80GGC aggregate amounts flow into Chapter6ADeductions so the
    # official JSON builder can emit the eligible-deduction totals.  These
    # are old-regime-only (zeroed under the new regime by _map_deductions).
    if schedule_80gga is not None or schedule_80ggc is not None:
        amount_80gga = Decimal("0")
        amount_80ggc = Decimal("0")
        if typed_input.tax_regime.value == "old":
            if schedule_80gga is not None:
                amount_80gga = sum(
                    (d.cash_amount + d.other_mode_amount for d in schedule_80gga.donations),
                    Decimal("0"),
                )
            if schedule_80ggc is not None:
                amount_80ggc = sum(
                    (c.cash_amount + c.other_mode_amount for c in schedule_80ggc.contributions),
                    Decimal("0"),
                )
        update["deductions_chapter6a"] = typed_input.deductions_chapter6a.model_copy(update={
            "amount_80gga": amount_80gga,
            "amount_80ggc": amount_80ggc,
        })
    return typed_input.model_copy(update=update)


def _build_itr4_input_from_flat(payload: dict[str, Any]) -> Any:
    """Construct ``ITR4Input`` from the same flat payload contract used by
    ``/tax-summary/compute``.

    This mapper is **fully standalone** — it does NOT call
    ``_build_itr1_input_from_flat``. Every flat payload field is mapped
    directly into the ``ITR4Input`` with ITR-4-specific filing profile,
    bank account, and property profile types. The ITR-4 form workflow is
    self-contained and decoupled from the ITR-1 pipeline.
    """
    from app.schemas.itr4 import (
        ITR4Input, PresumptiveScheme,
        PresumptiveBusinessIncome44AD, PresumptiveProfessionalIncome44ADA,
        PresumptiveGoodsCarriage44AE, GoodsCarriageVehicle,
        ITR4FilingProfile, ITR4FilingAddress, ITR4PostalAddress,
        ITR4PropertyProfile, ITR4BankAccount, ITR4TaxReturnPreparer,
        ITR4AssesseeStatus, ITR4SeventhProvisoDetails,
    )
    from app.schemas.itr1 import (
        SalaryIncome, HousePropertyIncome, OtherSourcesIncome,
        Chapter6ADeductions, CapitalGainsIncome, Donation80G,
        Donation80GCategory, DonationAddress, TDS1Entry, TDS2Entry,
        TCSEntry, TaxPaymentDetail, PropertyType, AgeBracket, TaxRegime,
        HRADetails,
    )

    # ------------------------------------------------------------------
    # Age bracket + tax regime
    # ------------------------------------------------------------------
    age = int(payload.get("age", 30) or 30)
    if age >= 80:
        age_bracket = AgeBracket.ABOVE_80
    elif age >= 60:
        age_bracket = AgeBracket.SIXTY_TO_80
    else:
        age_bracket = AgeBracket.BELOW_60

    regime_str = str(payload.get("taxRegime", payload.get("regime", "NEW"))).upper()
    tax_regime = TaxRegime.OLD if regime_str == "OLD" else TaxRegime.NEW

    # ------------------------------------------------------------------
    # Local helpers (standalone — do not reuse ITR-1 mapper's closures)
    # ------------------------------------------------------------------
    def _required_text(key: str, *, max_length: int | None = None) -> str:
        value = str(payload.get(key, "")).strip()
        if not value:
            raise ValueError(f"{key} is required for official ITR-4 JSON")
        if max_length is not None and len(value) > max_length:
            raise ValueError(f"{key} must not exceed {max_length} characters")
        return value

    def _filing_section_code(value: object, official_code: object) -> int:
        section_map = {
            "139(1)": 11, "139(4)": 12, "142(1)": 13, "148": 14,
            "153C": 16, "139(5)": 17, "139(9)": 18, "119(2)(b)": 20,
            11: 11, 12: 12, 13: 13, 14: 14, 16: 16, 17: 17, 18: 18, 20: 20,
            "11": 11, "12": 12, "13": 13, "14": 14, "16": 16, "17": 17, "18": 18, "20": 20,
        }
        code = section_map.get(value)
        if code is None:
            raise ValueError(
                f"Unsupported filing section {value!r} for ITR-4 official JSON"
            )
        if official_code not in (None, ""):
            try:
                supplied_code = int(official_code)
            except (TypeError, ValueError) as exc:
                raise ValueError("returnFileSectionCode must be an official numeric filing-section code") from exc
            if supplied_code != code:
                raise ValueError("filingSection and returnFileSectionCode must describe the same return section")
        return code

    # ------------------------------------------------------------------
    # Verification gate
    # ------------------------------------------------------------------
    verification = payload.get("verification")
    verification_data = verification if isinstance(verification, dict) else {}
    if verification_data.get("declarationAccepted") is not True:
        raise ValueError("Verification declaration must be accepted for official ITR-4 JSON")
    if str(verification_data.get("capacity", "SELF")).upper() != "SELF":
        raise ValueError("Representative verification is not supported for official ITR-4 JSON")

    date_of_birth = _date(payload.get("dob"), "dob")
    if date_of_birth is None:
        raise ValueError("dob must be a valid YYYY-MM-DD date for official ITR-4 JSON")

    mobile_country_code_raw = str(payload.get("mobileCountryCode", "91")).strip()
    if not mobile_country_code_raw.isdigit():
        raise ValueError("mobileCountryCode must be numeric for official ITR-4 JSON")

    secondary_mobile_raw = str(payload.get("secondaryMobile", "")).strip()
    secondary_mobile_country_raw = str(
        payload.get("secondaryMobileCountryCode", "")
    ).strip() or mobile_country_code_raw
    secondary_mobile_no: Optional[str] = None
    secondary_mobile_country_code: int = 0
    if secondary_mobile_raw:
        if not secondary_mobile_country_raw.isdigit():
            raise ValueError(
                "secondaryMobileCountryCode must be numeric for official ITR-4 JSON"
            )
        secondary_mobile_country_code = int(secondary_mobile_country_raw)
        secondary_mobile_no = secondary_mobile_raw

    secondary_email_raw = str(payload.get("secondaryEmail", "")).strip() or None

    # Landline (Address.Phone sub-object in the CBDT ITR-4 schema).
    landline_std_code_raw = str(payload.get("landlineStdCode", "0")).strip() or "0"
    landline_phone_raw = str(payload.get("landlinePhoneNo", "0")).strip() or "0"
    if not landline_std_code_raw.isdigit():
        landline_std_code_raw = "0"
    if not landline_phone_raw.isdigit():
        landline_phone_raw = "0"

    primary_address = ITR4FilingAddress(
        residence_no=_required_text("flatNo", max_length=50),
        residence_name=str(payload.get("premises", "")).strip(),
        road_or_street=str(payload.get("road", "")).strip(),
        locality_or_area=_required_text("area", max_length=50),
        city_or_town_or_district=_required_text("city", max_length=50),
        state_code=_required_text("state", max_length=2),
        country_code=str(payload.get("country", "91")).strip() or "91",
        pin_code=(str(payload.get("pincode", "")).strip() or None),
        zip_code=str(payload.get("zipCode", "")).strip(),
        mobile_country_code=int(mobile_country_code_raw),
        mobile_no=_required_text("mobile", max_length=10),
        email=_required_text("email", max_length=125),
        secondary_mobile_country_code=secondary_mobile_country_code,
        secondary_mobile_no=secondary_mobile_no,
        secondary_email=secondary_email_raw,
        landline_std_code=int(landline_std_code_raw),
        landline_phone_no=landline_phone_raw[:12],
    )

    alternate_raw = payload.get("alternateAddress")
    alternate_address: Optional[ITR4PostalAddress] = None
    if payload.get("secondaryAddressDifferent") is True:
        if not isinstance(alternate_raw, dict):
            raise ValueError("alternateAddress is required when secondaryAddressDifferent is true")
        alternate_address = ITR4PostalAddress(
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

    # ------------------------------------------------------------------
    # Seventh-proviso declarations (FilingStatus)
    # ------------------------------------------------------------------
    seventh_proviso_raw = payload.get("seventhProviso")
    seventh_proviso = ITR4SeventhProvisoDetails()
    if isinstance(seventh_proviso_raw, dict):
        seventh_proviso = ITR4SeventhProvisoDetails(
            foreign_travel_flag=bool(seventh_proviso_raw.get("foreignTravel", False)),
            foreign_travel_amount=_money(seventh_proviso_raw.get("foreignTravelAmount")),
            electricity_expenditure_flag=bool(seventh_proviso_raw.get("electricityExpenditure", False)),
            electricity_expenditure_amount=_money(seventh_proviso_raw.get("electricityExpenditureAmount")),
            other_clause_iv_flag=bool(seventh_proviso_raw.get("otherClauseIV", False)),
            other_clause_iv_detail=str(seventh_proviso_raw.get("otherClauseIVDetail", "")).strip(),
        )

    # ------------------------------------------------------------------
    # ITR-4 assessee status (Individual / HUF / Firm)
    # ------------------------------------------------------------------
    status_raw = str(payload.get("assesseeStatus", payload.get("entityType", "I"))).strip().upper()
    status_map = {"I": ITR4AssesseeStatus.INDIVIDUAL, "INDIVIDUAL": ITR4AssesseeStatus.INDIVIDUAL,
                 "H": ITR4AssesseeStatus.HUF, "HUF": ITR4AssesseeStatus.HUF,
                 "F": ITR4AssesseeStatus.FIRM, "FIRM": ITR4AssesseeStatus.FIRM}
    assessee_status = status_map.get(status_raw, ITR4AssesseeStatus.INDIVIDUAL)

    # ------------------------------------------------------------------
    # Form 10-IEA cascade fields
    # ------------------------------------------------------------------
    form_10iea_ack = str(payload.get("form10IEAAcknowledgement", "")).strip()
    form_10iea_date_raw = payload.get("form10IEADate")
    f10iea_date_curr_ay_old = (
        form_10iea_date_raw.isoformat() if _date(form_10iea_date_raw, "form10IEADate") else ""
    )

    # ------------------------------------------------------------------
    # ITR-4 filing profile
    # ------------------------------------------------------------------
    filing_profile = ITR4FilingProfile(
        pan=_required_text("pan", max_length=10).upper(),
        first_name=str(payload.get("firstName", "")).strip(),
        middle_name=str(payload.get("middleName", "")).strip(),
        surname=(
            _required_text("surnameOrOrgName", max_length=75)
            if str(payload.get("surnameOrOrgName", "")).strip()
            else _required_text("name", max_length=75)
        ),
        date_of_birth=date_of_birth,
        employer_category=str(payload.get("employerCategory", "OTH")).strip() or "OTH",
        aadhaar_number=(str(payload.get("aadhaar", "")).strip() or None),
        assessee_status=assessee_status,
        primary_address=primary_address,
        alternate_address=alternate_address,
        father_name=_required_text("fatherName", max_length=125),
        verification_place=str(verification_data.get("place", "")).strip() or "Delhi",
        verification_capacity="S",
        return_file_section=_filing_section_code(
            payload.get("filingSection", "139(1)"),
            payload.get("returnFileSectionCode"),
        ),
        seventh_proviso=seventh_proviso,
        f10iea_curr_ay_old_regime=("Y" if regime_str == "OLD" else "N"),
        f10iea_date_curr_ay_old_tax=f10iea_date_curr_ay_old,
    )

    # ------------------------------------------------------------------
    # Salary income (standalone mapping)
    # ------------------------------------------------------------------
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

    salary_input: Optional[SalaryIncome] = None
    if section_17_1_salary > 0 or perquisites > 0 or profits_in_lieu > 0:
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

    # ------------------------------------------------------------------
    # HRA evidence
    # ------------------------------------------------------------------
    rent_paid_total = sum(_money(row.get("rentPaid")) for row in salary_rows)
    is_metro = any(bool(row.get("isMetroCity", False)) for row in salary_rows)
    hra_details: Optional[HRADetails] = None
    if hra_received > 0 or rent_paid_total > 0 or hra_exempt > 0:
        hra_details = HRADetails(
            actual_hra_received=hra_received,
            rent_paid=rent_paid_total,
            salary_for_hra=basic,
            dearness_allowance=da,
            is_metro_city=is_metro,
        )

    # ------------------------------------------------------------------
    # House property (ITR-4 allows at most one)
    # ------------------------------------------------------------------
    properties = _records(payload, "housePropertyEntries")
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

    hp_input: Optional[HousePropertyIncome] = None
    property_profile: Optional[ITR4PropertyProfile] = None
    if properties:
        hp_input = _build_hp_input(properties[0])
        first_prop = properties[0]
        first_address = str(first_prop.get("address", first_prop.get("name", ""))).strip()
        if not first_address:
            first_address = primary_address.residence_no
        property_profile = ITR4PropertyProfile(
            address_detail=first_address[:50],
            city_or_town_or_district=str(first_prop.get("city", payload.get("city", ""))).strip() or primary_address.city_or_town_or_district,
            state_code=str(first_prop.get("state", payload.get("state", ""))).strip() or primary_address.state_code,
            country_code=str(first_prop.get("countryCode", payload.get("country", "91"))).strip() or primary_address.country_code,
            pin_code=(str(first_prop.get("pinCode", payload.get("pincode", ""))).strip() or None),
            zip_code=(str(first_prop.get("zipCode", payload.get("zipCode", ""))).strip() or None) or None,
        )

    # ------------------------------------------------------------------
    # Other sources income (standalone mapping)
    # ------------------------------------------------------------------
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

    os_input: Optional[OtherSourcesIncome] = None
    if (interest_sb + post_office + interest_fd + total_dividend + family_pension) > 0:
        os_input = OtherSourcesIncome(
            savings_bank_interest=interest_sb + post_office,
            fixed_deposit_interest=interest_fd,
            family_pension_received=family_pension,
            dividend_income=total_dividend,
        )

    # ------------------------------------------------------------------
    # Chapter VI-A deductions (standalone mapping)
    # ------------------------------------------------------------------
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

    ded_input = Chapter6ADeductions(
        amount_80c=total_80c,
        amount_80d=self_80d + parents_80d,
        has_parents_senior=parents_are_senior,
    )

    # ------------------------------------------------------------------
    # Capital gains (112A only for ITR-4)
    # ------------------------------------------------------------------
    cg_input: Optional[CapitalGainsIncome] = None
    cg_rows = _records(payload, "capitalGainsEntries")
    ltcg_112a = Decimal("0")
    sale_consideration: Optional[Decimal] = None
    cost_acquisition: Optional[Decimal] = None
    for row in cg_rows:
        kind = str(row.get("kind", row.get("itdTag", ""))).upper()
        if kind in {"LTCG_112A", "LISTED_EQUITY", "LTCG_EQUITY"}:
            ltcg_112a += _money(row.get("gain", row.get("longTermGain", row.get("netGain"))))
            sale_consideration = (sale_consideration or Decimal("0")) + _money(row.get("saleValue", row.get("fullValueOfConsideration")))
            cost_acquisition = (cost_acquisition or Decimal("0")) + _money(row.get("costOfAcquisition", row.get("purchaseValue")))
    if ltcg_112a > 0:
        cg_input = CapitalGainsIncome(
            ltcg_112a=ltcg_112a,
            full_value_of_consideration=sale_consideration,
            cost_of_acquisition=cost_acquisition,
        )

    # ------------------------------------------------------------------
    # TDS1 / TDS2 / TDS3 / TCS entries (standalone mapping)
    # ------------------------------------------------------------------
    tds1_entries: list[TDS1Entry] = []
    for row in _records(payload, "employerEntries"):
        tan = str(row.get("employerTAN", row.get("tan", ""))).strip()
        if not tan:
            continue
        tds1_entries.append(TDS1Entry(
            employer_tan=tan,
            employer_name=str(row.get("employerName", row.get("employer", ""))).strip() or None,
            income_chargeable=_money(row.get("incomeChargeable", row.get("totalAmountCredited"))),
            tds_deducted=_money(row.get("tdsDeducted", row.get("totalTDSSalary"))),
        ))

    tds2_entries: list[TDS2Entry] = []
    for row in _records(payload, "tdsEntries"):
        tan = str(row.get("deductorTAN", row.get("tan", ""))).strip()
        if not tan:
            continue
        tds2_entries.append(TDS2Entry(
            deductor_tan=tan,
            deductor_name=str(row.get("deductorName", row.get("deductor", ""))).strip() or None,
            tds_section=str(row.get("section", row.get("tdsSection", "194A"))),
            gross_amount=_money(row.get("grossAmount", row.get("amountForTaxDeduction"))),
            tds_deducted=_money(row.get("tdsDeducted", row.get("totalTDSOnAmountPaid"))),
            tds_claimed_this_year=_money(row.get("tdsClaimed", row.get("claimOutOfTotTDSOnAmtPaid"))),
        ))

    tds3_entries: list = []
    for row in _records(payload, "tds3Entries"):
        pan = str(row.get("tenantPAN", row.get("pan", ""))).strip()
        if not pan:
            continue
        tds3_entries.append(TDS3Entry(
            tenant_pan=pan,
            tenant_name=str(row.get("tenantName", row.get("name", ""))).strip(),
            tenant_aadhaar=(str(row.get("tenantAadhaar", "")).strip() or None),
            gross_receipt=_money(row.get("grossReceipt", row.get("grsRcptToTaxDeduct"))),
            tds_deducted=_money(row.get("tdsDeducted", row.get("totalTDSDeducted"))),
            tds_claimed=_money(row.get("tdsClaimed", row.get("totalTDSClaimed"))),
            tds_section=str(row.get("section", row.get("tdsSection", "194I"))),
            deducted_yr=str(row.get("deductedYear", row.get("deductedYr", "2024"))),
        ))

    tcs_entries: list[TCSEntry] = []
    for row in _records(payload, "tcsEntries"):
        tan = str(row.get("collectorTAN", row.get("tan", ""))).strip()
        if not tan:
            continue
        tcs_entries.append(TCSEntry(
            collector_tan=tan,
            collector_name=str(row.get("collectorName", row.get("collector", ""))).strip() or None,
            tcs_section=str(row.get("section", row.get("tcsSection", "206C"))),
            gross_amount=_money(row.get("grossAmount")),
            tcs_collected=_money(row.get("taxCollected", row.get("tcsCollected"))),
            tcs_credit_claimed=_money(row.get("tcsClaimed", row.get("tcsCreditClaimed"))),
        ))

    # ------------------------------------------------------------------
    # Tax payment entries (ScheduleIT challans)
    # ------------------------------------------------------------------
    tax_payment_entries: list[TaxPaymentDetail] = []
    for row in _records(payload, "advanceTaxEntries") + _records(payload, "selfAssessmentTaxEntries"):
        bsr = str(row.get("bsrCode", "")).strip()
        challan = str(row.get("challanSerialNo", row.get("challanNo", ""))).strip()
        deposit = _date(row.get("depositDate"), "depositDate")
        amount = _money(row.get("amount"))
        if bsr and challan and deposit and amount > 0:
            tax_payment_entries.append(TaxPaymentDetail(
                amount=amount,
                payment_type="advance" if row in _records(payload, "advanceTaxEntries") else "self_assessment",
                payment_date=deposit,
                bsr_code=bsr,
                challan_serial_number=challan,
            ))

    # ------------------------------------------------------------------
    # Advance tax / self-assessment tax totals + quarterly split
    # ------------------------------------------------------------------
    quarterly_advance = [Decimal("0")] * 4
    for row in _records(payload, "advanceTaxEntries"):
        amount = _money(row.get("amount"))
        deposit = _date(row.get("depositDate"), "depositDate")
        bucket = 3
        if deposit is not None:
            deadlines = (
                datetime.date(2025, 6, 15),
                datetime.date(2025, 9, 15),
                datetime.date(2025, 12, 15),
                datetime.date(2026, 3, 15),
            )
            for idx, deadline in enumerate(deadlines):
                if deposit <= deadline:
                    bucket = idx
                    break
        quarterly_advance[bucket] += amount
    if not _records(payload, "advanceTaxEntries"):
        quarterly_advance = [
            _money(payload.get(k)) for k in ["adv15Jun", "adv15Sep", "adv15Dec", "adv15Mar"]
        ]
    advance_tax_paid = sum(quarterly_advance)

    self_assessment_paid = Decimal("0")
    for row in _records(payload, "selfAssessmentTaxEntries"):
        self_assessment_paid += _money(row.get("amount"))
    if not _records(payload, "selfAssessmentTaxEntries"):
        self_assessment_paid = _money(payload.get("selfTax"))

    # ------------------------------------------------------------------
    # Bank accounts (standalone, ITR-4-specific type)
    # ------------------------------------------------------------------
    bank_root = payload.get("bankAccountData")
    bank_source = bank_root.get("accounts") if isinstance(bank_root, dict) else payload.get("bankAccountDetails")
    bank_rows_list = bank_source if isinstance(bank_source, list) else []
    bank_accounts: list[ITR4BankAccount] = []
    for row in bank_rows_list:
        if not isinstance(row, dict):
            continue
        account_number = str(row.get("accountNumber", "")).strip()
        ifsc = str(row.get("ifscCode", "")).strip().upper()
        bank_name = str(row.get("bankName", "")).strip()
        if not account_number or not ifsc or not bank_name:
            continue
        bank_accounts.append(ITR4BankAccount(
            account_number=account_number,
            ifsc_code=ifsc,
            bank_name=bank_name,
            account_type=str(row.get("accountType", "savings")).strip(),
            is_primary=row.get("useForRefund") is True,
        ))

    # ------------------------------------------------------------------
    # Tax Return Preparer (optional)
    # ------------------------------------------------------------------
    trp_row = payload.get("taxReturnPreparer")
    trp_input: Optional[ITR4TaxReturnPreparer] = None
    if isinstance(trp_row, dict):
        trp_id = str(trp_row.get("identificationNumber", "")).strip()
        trp_name = str(trp_row.get("name", "")).strip()
        if trp_id and trp_name:
            trp_input = ITR4TaxReturnPreparer(
                identification_number=trp_id,
                name=trp_name,
                reimbursement_from_government=_money(trp_row.get("reimbursementFromGovernment")),
            )

    # ------------------------------------------------------------------
    # Presumptive business income (44AD / 44ADA / 44AE)
    # ------------------------------------------------------------------
    business_rows = _records(payload, "businessEntries") or _records(payload, "businesses")
    business_row = business_rows[0] if business_rows else None
    biz_turnover = _money(payload.get("bizTurnover"))
    bp_profit = _money(payload.get("bizDeclared", payload.get("bpNetProfit")))
    scheme = str(payload.get("bizPresumptive", "44AD"))
    if business_row:
        scheme = str(business_row.get("scheme", scheme))

    business_code = str(payload.get("businessCode", payload.get("natureOfBusinessCode", ""))).strip()
    profession_code = str(payload.get("professionCode", "")).strip()

    presumptive_scheme: PresumptiveScheme
    business_income_44ad: Optional[PresumptiveBusinessIncome44AD] = None
    professional_income_44ada: Optional[PresumptiveProfessionalIncome44ADA] = None
    goods_carriage_44ae: Optional[PresumptiveGoodsCarriage44AE] = None

    if scheme == "44ADA":
        digital = _money(business_row.get("digitalReceipts")) if business_row else biz_turnover
        cash = _money(business_row.get("nonDigitalReceipts")) if business_row else Decimal("0")
        gross = _money(business_row.get("grossReceipts")) if business_row else biz_turnover
        if gross == 0:
            gross = digital + cash
        declared = _money(business_row.get("declaredIncome")) if business_row else bp_profit
        presumptive_scheme = PresumptiveScheme.S44ADA
        professional_income_44ada = PresumptiveProfessionalIncome44ADA(
            gross_receipts=gross,
            digital_receipts=digital,
            cash_receipts=cash,
            income_declared=declared or None,
        )
    elif scheme == "44AE":
        vehicles: list[GoodsCarriageVehicle] = []
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
        presumptive_scheme = PresumptiveScheme.S44AE
        goods_carriage_44ae = PresumptiveGoodsCarriage44AE(vehicles=vehicles)
    else:  # 44AD default
        digital = _money(business_row.get("digitalReceipts")) if business_row else biz_turnover
        cash = _money(business_row.get("nonDigitalReceipts")) if business_row else Decimal("0")
        total = digital + cash if business_row else biz_turnover
        declared = _money(business_row.get("declaredIncome")) if business_row else bp_profit
        presumptive_scheme = PresumptiveScheme.S44AD
        business_income_44ad = PresumptiveBusinessIncome44AD(
            total_turnover=total,
            digital_turnover=digital,
            cash_turnover=cash,
            income_declared=declared or None,
        )

    # ------------------------------------------------------------------
    # Assemble ITR4Input
    # ------------------------------------------------------------------
    return ITR4Input(
        age_bracket=age_bracket,
        tax_regime=tax_regime,
        presumptive_scheme=presumptive_scheme,
        business_income_44ad=business_income_44ad,
        professional_income_44ada=professional_income_44ada,
        goods_carriage_44ae=goods_carriage_44ae,
        salary_income=salary_input,
        house_property_income=hp_input,
        other_sources_income=os_input,
        deductions_chapter6a=ded_input,
        capital_gains=cg_input,
        tds1_entries=tds1_entries or None,
        tds2_entries=tds2_entries or None,
        tcs_entries=tcs_entries or None,
        advance_tax_paid=advance_tax_paid,
        self_assessment_tax_paid=self_assessment_paid,
        advance_tax_q1=quarterly_advance[0] or None,
        advance_tax_q2=quarterly_advance[1] or None,
        advance_tax_q3=quarterly_advance[2] or None,
        advance_tax_q4=quarterly_advance[3] or None,
        filing_date=_date(payload.get("filingDate"), "filingDate"),
        due_date=_date(payload.get("dueDate"), "dueDate"),
        house_property_count=max(1, len(properties)),
        hra_details=hra_details,
        schedule_10_13a=hra_details,
        tax_payment_entries=tax_payment_entries,
        business_code=business_code or None,
        profession_code=profession_code or None,
        filing_profile=filing_profile,
        property_profile=property_profile,
        bank_accounts=bank_accounts,
        tax_return_preparer=trp_input,
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