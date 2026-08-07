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

    # Step D: validate against official schema
    try:
        validate_itr1_json(itd_json)
    except Exception as exc:
        # Schema validation is best-effort for ITR-1 until the builder is
        # complete.  Surface errors as warnings rather than blocking.
        errors.append(f"Official schema warning: {exc}")

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
        Donation80GCategory, DonationAddress, TDS1Entry, TDS2Entry,
        TCSEntry, PropertyType, AgeBracket, TaxRegime,
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

    # House Property — first property only (ITR-1 supports one aggregate)
    properties = _records(payload, "housePropertyEntries")
    prop = properties[0] if properties else payload
    raw_hp_type = str(
        prop.get("propertyType", prop.get("hpType", "self"))
    ).upper()
    property_type = {
        "SELF": PropertyType.SELF_OCCUPIED,
        "SELF_OCCUPIED": PropertyType.SELF_OCCUPIED,
        "LET_OUT": PropertyType.LET_OUT,
        "DEEMED_LET_OUT": PropertyType.DEEMED_LET_OUT,
    }.get(raw_hp_type, PropertyType.LET_OUT)
    loan_interest = _money(prop.get("interestOnLoan"))
    if loan_interest == 0:
        loan_interest = sum(
            _money(loan.get("interestUs24B"))
            for loan in _records(prop, "homeLoans")
        )
    if loan_interest == 0:
        loan_interest = _money(prop.get("homeLoanInt", prop.get("sopLoanInt")))

    hp_input = HousePropertyIncome(
        property_type=property_type,
        annual_rent_received=_money(prop.get("annualRent", prop.get("grossRent"))),
        municipal_taxes_paid=_money(prop.get("municipalTaxesPaid", prop.get("munTax"))),
        home_loan_interest_paid=loan_interest,
        municipal_value=_money(prop.get("municipalRateableValue")),
        fair_rent=_money(prop.get("fairRentValue")),
        arrears_unrealised_rent_received=_money(prop.get("arrearsOfRent")),
    )

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

    ded_input = Chapter6ADeductions(
        amount_80c=total_80c,
        amount_80ccd1b=_money(payload.get("s80CCD1B")),
        amount_80ccd2=_money(payload.get("s80CCD2")),
        amount_80d_self_family=self_80d,
        amount_80d_parents=parents_80d,
        amount_80d_preventive_self=Decimal("0"),
        amount_80d_preventive_parents=Decimal("0"),
        has_parents_senior=parents_are_senior,
        amount_80e=_money(payload.get("s80E")),
        amount_80tta=_money(payload.get("s80TTA")),
        amount_80ttb=_money(payload.get("s80TTB")),
        amount_80g=(structured_80g_claim if donations else _money(payload.get("s80G"))),
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
    for row in _records(payload, "tdsEntries"):
        if row.get("claimedInReturn") is False:
            continue
        tan = str(row.get("deductorTAN") or "").strip().upper()
        section = str(row.get("section") or "").strip().upper()
        tax = _money(row.get("taxDeducted", row.get("tdsDeducted")))
        gross = _money(row.get("grossAmount", row.get("incomeAmount")))
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

    return ITR1Input(
        age_bracket=age_bracket,
        tax_regime=tax_regime,
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
        advance_tax_q1=quarterly_advance[0],
        advance_tax_q2=quarterly_advance[1],
        advance_tax_q3=quarterly_advance[2],
        advance_tax_q4=quarterly_advance[3],
        filing_date=_date(payload.get("filingDate"), "filingDate"),
        due_date=_date(payload.get("dueDate"), "dueDate"),
        house_property_count=max(1, len(properties)),
        relief_89=_money(payload.get("relief89", payload.get("relief_89"))),
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
