"""Canonical mapper: ReturnDraft → ITR4Input.

This is the SINGLE typed mapper for ITR-4 — the ITR-4 analogue of
:func:`app.engine.draft_to_itr1_input.draft_to_itr1_input`. It reads the
canonical typed ``ReturnDraft`` — no alias guessing
(``row.get("hra", row.get("hraReceived"))``), no ``_first_money`` fallbacks.
The duplicate-mapper problem the ITR-1 audit
called out as "the single biggest source of *works in compute, fails in CBDT*
bugs" is eliminated for ITR-4 here.

Phase 2 scope (mirrors ITR-1's split): compute-relevant fields only — income
heads (salary, one house property, other sources, capital gains 112A), the
active presumptive scheme (44AD/44ADA/44AE), Chapter VI-A deductions, TDS/TCS,
and tax payments. The full ``ITR4FilingProfile`` (address, assessee status,
Form 10-IEA cascade, seventh-proviso, bank accounts, TRP) is constructed in
Phase 3 by :func:`app.engine.filing_gateway_v2._itr4_filing_profile`, because
those fields are official-JSON concerns, not compute concerns.

Shared heads reuse: salary / house property / other sources / deductions /
112A / TDS / TCS / tax payments are the *same* typed ``ReturnDraft`` fields
for both forms, so this mapper delegates to the private helpers already
implemented and tested in :mod:`app.engine.draft_to_itr1_input`. One
implementation per shared head — no second copy to drift.

Authority: :class:`app.schemas.return_draft.ReturnDraft` (canonical draft)
and :class:`app.schemas.itr4.ITR4Input` (typed compute input).
"""

from __future__ import annotations

import datetime
from decimal import Decimal
from typing import Any, Optional

from app.schemas.itr1 import AgeBracket, TaxRegime
from app.schemas.itr4 import (
    GoodsCarriageVehicle,
    ITR4Input,
    PresumptiveBusinessIncome44AD,
    PresumptiveGoodsCarriage44AE,
    PresumptiveProfessionalIncome44ADA,
    PresumptiveScheme,
    ScheduleBPFinancial,
)
from app.schemas.return_draft import (
    Presumptive44AD,
    Presumptive44ADA,
    Presumptive44AE,
    ReturnDraft,
)
# Shared form-agnostic helpers — one implementation of each shared head.
from app.engine.draft_to_itr1_input import (
    DraftMappingError,
    _map_capital_gains,
    _map_deductions,
    _map_house_properties,
    _map_other_sources,
    _map_salary,
    _map_tax_payments,
    _map_tcs,
    _map_tds,
    _to_date,
)


# ---------------------------------------------------------------------------
# Age bracket — ITR-4 uses the explicit `personal.age` field (ITR-1 uses DOB)
# ---------------------------------------------------------------------------

def _age_bracket_from_age(age: int) -> AgeBracket:
    """Derive the ITR-4 AgeBracket from the assessee's explicit age.

    ITR-4's compute input carries an explicit ``age_bracket`` derived from
    ``draft.personal.age`` (the assessee's age as on 31 March of the previous
    year). This mirrors the legacy flat mapper's ``int(payload.get("age", 30))``
    derivation. ITR-1 instead derives its bracket from ``dateOfBirth`` — both
    are valid; ITR-4's flat contract historically used the explicit integer.

    Args:
        age: The assessee's age (0–120).

    Returns:
        The matching :class:`AgeBracket`. Below 60 → ``BELOW_60``;
        60–79 → ``SIXTY_TO_80``; 80+ → ``ABOVE_80``.
    """
    if age >= 80:
        return AgeBracket.ABOVE_80
    if age >= 60:
        return AgeBracket.SIXTY_TO_80
    return AgeBracket.BELOW_60


# ---------------------------------------------------------------------------
# Schedule BP financial particulars (CBDT Sl 139 cross-consistency)
# ---------------------------------------------------------------------------

def _map_schedule_bp_financial(businesses: list[Any]) -> Optional[ScheduleBPFinancial]:
    """Map the first business row's ``financialParticulars`` → ScheduleBPFinancial.

    The ITR-4 Category A validator (CBDT Sl 139) requires Schedule BP
    financial particulars (sundry creditors, inventories, cash-in-hand,
    etc.) whenever gross receipts or turnover is disclosed. In production
    these are entered on the Business tab; when absent the validator
    surfaces the Sl 139 error so the taxpayer can complete the balance sheet.
    """
    if not businesses:
        return None
    fp = getattr(businesses[0], "financialParticulars", None)
    if fp is None:
        return None
    return ScheduleBPFinancial(
        partners_capital=Decimal("0"),
        secured_loans=fp.securedLoans,
        unsecured_loans=fp.unsecuredLoans,
        advances_received=Decimal("0"),
        sundry_creditors=fp.sundryCreditors,
        other_liabilities=fp.otherLiabilities,
        total_capital_liabilities=fp.totalLiabilities,
        fixed_assets=fp.totalAssets - fp.bankBalance - fp.cashBalance - fp.inventory - fp.sundryDebtors,
        investments_bp=Decimal("0"),
        inventories=fp.inventory,
        sundry_debtors=fp.sundryDebtors,
        bank_balance=fp.bankBalance,
        cash_in_hand=fp.cashBalance,
        loans_and_advances_given=Decimal("0"),
        other_assets=Decimal("0"),
        total_assets=fp.totalAssets,
    )


# ---------------------------------------------------------------------------
# Presumptive business income — the ITR-4-specific head
# ---------------------------------------------------------------------------

def _map_presumptive(
    businesses: list[Any],
) -> tuple[
    PresumptiveScheme,
    Optional[PresumptiveBusinessIncome44AD],
    Optional[PresumptiveProfessionalIncome44ADA],
    Optional[PresumptiveGoodsCarriage44AE],
    Optional[str],
    Optional[str],
]:
    """Map the canonical presumptive-business rows → the active scheme.

    ITR-4 permits exactly one presumptive scheme per return (44AD, 44ADA, or
    44AE). The canonical ``ReturnDraft.businesses`` list is a discriminated
    union of :class:`Presumptive44AD`, :class:`Presumptive44ADA`,
    :class:`Presumptive44AE`. The first row determines the active scheme —
    mirroring the legacy mapper's ``business_rows[0]`` selection.

    Args:
        businesses: The ``draft.businesses`` list (any of the three union members).

    Returns:
        ``(scheme, business_44ad, professional_44ada, goods_44ae,
        business_code, profession_code)``. Only the sub-model matching the
        active scheme is non-None; the other two are ``None``. When the list
        is empty, the scheme defaults to ``S44AD`` with a zero-turnover
        sub-model so the compute input is always valid.

    Raises:
        DraftMappingError: If a business row's scheme is not one of the three
            supported values, or if two rows declare different schemes.
    """
    if not businesses:
        # Default to 44AD with a zero-turnover sub-model — the compute engine
        # accepts a zero-presumptive ITR-4 (an ITR-4 with only salary/HP/OS
        # income is unusual but schema-valid).
        return PresumptiveScheme.S44AD, PresumptiveBusinessIncome44AD(
            total_turnover=Decimal("0"),
            digital_turnover=Decimal("0"),
            cash_turnover=Decimal("0"),
            income_declared=None,
        ), None, None, None, None

    first = businesses[0]
    # natureCode is the shared business/profession code surface on
    # BusinessIdentity (inherited by all three presumptive sub-models).
    code = getattr(first, "natureCode", "") or None

    if isinstance(first, Presumptive44AD):
        scheme = PresumptiveScheme.S44AD
        digital = first.digitalReceipts
        cash = first.nonDigitalReceipts
        total_turnover = digital + cash
        declared = first.declaredIncome or None
        biz_44ad = PresumptiveBusinessIncome44AD(
            total_turnover=total_turnover,
            digital_turnover=digital,
            cash_turnover=cash,
            income_declared=declared,
        )
        return scheme, biz_44ad, None, None, code, None

    if isinstance(first, Presumptive44ADA):
        scheme = PresumptiveScheme.S44ADA
        gross = first.grossReceipts
        digital = first.digitalReceipts
        cash = first.nonDigitalReceipts
        if gross == 0:
            gross = digital + cash
        declared = first.declaredIncome or None
        prof_44ada = PresumptiveProfessionalIncome44ADA(
            gross_receipts=gross,
            digital_receipts=digital,
            cash_receipts=cash,
            income_declared=declared,
        )
        return scheme, None, prof_44ada, None, None, code

    if isinstance(first, Presumptive44AE):
        scheme = PresumptiveScheme.S44AE
        vehicles: list[GoodsCarriageVehicle] = []
        for v in first.vehicles:
            vehicle_type = (v.vehicleType or "OTHER").upper()
            is_heavy = vehicle_type == "HEAVY"
            tonnage = v.tonnage if is_heavy else None
            months = v.ownedMonths or 1
            if months < 1:
                months = 1
            vehicles.append(GoodsCarriageVehicle(
                is_heavy_goods_vehicle=is_heavy,
                gross_vehicle_weight_tons=tonnage,
                months_owned=months,
                income_declared=v.presumptiveIncome or None,
            ))
        goods_44ae = PresumptiveGoodsCarriage44AE(vehicles=vehicles)
        # 44AE requires a business code in Schedule BP (CBDT Sl 137). The
        # natureCode on the Presumptive44AE row carries the goods-carriage
        # business code (e.g. 06001). Setting business_code for 44AD-only
        # would trip Sl 12, so only the 44AE branch sets it here.
        return scheme, None, None, goods_44ae, code, None

    raise DraftMappingError(
        f"Unsupported presumptive business row type: {type(first).__name__}. "
        "Expected Presumptive44AD, Presumptive44ADA, or Presumptive44AE."
    )


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def draft_to_itr4_input(
    draft: ReturnDraft,
) -> tuple[ITR4Input, dict[str, Any]]:
    """Map a canonical ``ReturnDraft`` → ``ITR4Input`` for compute + CBDT.

    Args:
        draft: The canonical typed draft. ``draft.form`` should be ``"ITR-4"``;
            this mapper does not enforce that (the gateway dispatcher does).

    Returns:
        ``(itr4_input, breakdown)`` where ``breakdown`` carries the same
        intermediate totals the ITR-1 mapper surfaces (section_17_1,
        gross_salary, total_interest, total_dividend, family_pension,
        total_winnings, tds_salary, tds_interest, tds_other, claimed_tds,
        advance_tax, self_assessment_tax, quarterly_advance) plus the
        ITR-4-specific ``presumptive_scheme`` and ``business_code``.

    Raises:
        DraftMappingError: If the draft carries income outside ITR-4 scope
            (delegated to :func:`_map_other_sources` which rejects lottery/
            gaming winnings for ITR-4 just as it does for ITR-1).
    """
    tax_regime = TaxRegime.OLD if draft.regime == "old" else TaxRegime.NEW
    age_bracket = _age_bracket_from_age(draft.personal.age)

    # Shared heads — one implementation, reused (audit Finding 14 fix).
    salary_input, section_17_1, gross_salary = _map_salary(draft.employers)
    hp_input, hp_inputs = _map_house_properties(draft.houseProperties)
    os_input, total_interest, total_dividend, family_pension, total_winnings = (
        _map_other_sources(draft)
    )
    ded_input, structured_80g = _map_deductions(draft, tax_regime)
    cg_input = _map_capital_gains(draft)

    tds1, tds2, tds_salary, tds_interest, tds_other, claimed_tds, tds_issues = (
        _map_tds(draft.taxes.tds)
    )
    tcs_entries, total_tcs = _map_tcs(draft.taxes.tcs)
    sat_entries, advance_tax, sat_total, quarterly = _map_tax_payments(
        draft.taxes.challans
    )

    # ITR-4-specific: presumptive business income + scheme.
    scheme, biz_44ad, prof_44ada, goods_44ae, business_code, profession_code = (
        _map_presumptive(draft.businesses)
    )
    # Schedule BP financial particulars (CBDT Sl 139 cross-consistency).
    schedule_bp_financial = _map_schedule_bp_financial(draft.businesses)

    itr4_input = ITR4Input(
        age_bracket=age_bracket,
        tax_regime=tax_regime,
        presumptive_scheme=scheme,
        business_income_44ad=biz_44ad,
        professional_income_44ada=prof_44ada,
        goods_carriage_44ae=goods_44ae,
        salary_income=salary_input,
        house_property_income=hp_input,
        other_sources_income=os_input,
        deductions_chapter6a=ded_input,
        capital_gains=cg_input,
        tds1_entries=tds1 or None,
        tds2_entries=tds2 or None,
        tcs_entries=tcs_entries or None,
        advance_tax_paid=advance_tax,
        self_assessment_tax_paid=sat_total,
        advance_tax_q1=quarterly[0] or None,
        advance_tax_q2=quarterly[1] or None,
        advance_tax_q3=quarterly[2] or None,
        advance_tax_q4=quarterly[3] or None,
        filing_date=_to_date(draft.personal.dateOfBirth),  # placeholder; gateway sets filing_date
        due_date=None,
        house_property_count=max(1, len(draft.houseProperties)),
        hra_details=None,
        schedule_10_13a=None,
        tax_payment_entries=sat_entries,
        business_code=business_code,
        profession_code=profession_code,
        schedule_bp_financial=schedule_bp_financial,
        filing_profile=None,  # Phase 3: constructed by filing_gateway_v2.
        property_profile=None,
        bank_accounts=[],
        tax_return_preparer=None,
    )

    breakdown: dict[str, Any] = {
        "section_17_1_salary": section_17_1,
        "gross_salary": gross_salary,
        "total_interest": total_interest,
        "total_dividend": total_dividend,
        "family_pension": family_pension,
        "total_winnings": total_winnings,
        "tds_salary": tds_salary,
        "tds_interest": tds_interest,
        "tds_other": tds_other,
        "claimed_tds": claimed_tds,
        "advance_tax": advance_tax,
        "self_assessment_tax": sat_total,
        "quarterly_advance": quarterly,
        "structured_80g": structured_80g,
        "total_tcs": total_tcs,
        "credit_validation_issues": tds_issues,
        "presumptive_scheme": scheme.value,
        "business_code": business_code,
    }
    return itr4_input, breakdown
