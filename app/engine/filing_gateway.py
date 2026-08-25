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
            # ITR-4 moved to the v2 canonical pipeline (Phase 3-6).
            # The legacy /clients/.../generate-cbdt-json endpoint now
            # only supports ITR-1/2/3; ITR-4 callers must use the v2
            # endpoint POST /v2/clients/{id}/itr/{year}/generate-cbdt-json.
            raise FilingGatewayError(
                "ITR-4 official CBDT JSON is generated by the v2 canonical pipeline.",
                errors=[
                    "Use POST /v2/clients/{client_id}/itr/{year}/generate-cbdt-json "
                    "for ITR-4 (the legacy flat-blob ITR-4 path is removed)."
                ],
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


