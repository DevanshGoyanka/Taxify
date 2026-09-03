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

from app.schemas.itr1 import AgeBracket, AssesseeType, TaxRegime
from app.schemas.itr4 import (
    GoodsCarriageVehicle,
    ITR4BusinessNature,
    ITR4GstinTurnover,
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
    _map_deduction_loans,
    _map_disability_schedules,
    _map_dividend_quarterly_breakdown,
    _map_compact_exempt_income,
    _map_hra_details,
    _map_24b_loans,
    _map_house_properties,
    _map_80d_schedule,
    _map_80gga,
    _map_80ggc,
    _map_other_sources,
    _map_salary,
    _map_tax_payments,
    _map_tcs,
    _map_tds,
    _map_tds3,
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
        partners_capital=fp.partnerMemberOwnCapital,
        secured_loans=fp.securedLoans,
        unsecured_loans=fp.unsecuredLoans,
        advances_received=fp.advances,
        sundry_creditors=fp.sundryCreditors,
        other_liabilities=fp.otherLiabilities,
        total_capital_liabilities=fp.totalLiabilities,
        fixed_assets=fp.fixedAssets,
        investments_bp=fp.investments,
        inventories=fp.inventory,
        sundry_debtors=fp.sundryDebtors,
        bank_balance=fp.bankBalance,
        cash_in_hand=fp.cashBalance,
        loans_and_advances_given=fp.loansAndAdvances,
        other_assets=fp.otherAssets,
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
    """Map canonical business rows into every applicable presumptive block.

    Args:
        businesses: The ``draft.businesses`` list (any of the three union members).

    Returns:
        ``(primary_scheme, business_44ad, professional_44ada, goods_44ae,
        business_code, profession_code)``. The primary scheme is retained for
        compatibility; populated sub-models are authoritative.
    """
    if not businesses:
        return PresumptiveScheme.NONE, None, None, None, None, None

    ad_rows = [row for row in businesses if isinstance(row, Presumptive44AD)]
    ada_rows = [row for row in businesses if isinstance(row, Presumptive44ADA)]
    ae_rows = [row for row in businesses if isinstance(row, Presumptive44AE)]
    if len(ad_rows) + len(ada_rows) + len(ae_rows) != len(businesses):
        bad = next(
            row for row in businesses
            if not isinstance(row, (Presumptive44AD, Presumptive44ADA, Presumptive44AE))
        )
        raise DraftMappingError(
            f"Unsupported presumptive business row type: {type(bad).__name__}."
        )

    biz_44ad: Optional[PresumptiveBusinessIncome44AD] = None
    prof_44ada: Optional[PresumptiveProfessionalIncome44ADA] = None
    goods_44ae: Optional[PresumptiveGoodsCarriage44AE] = None

    if ad_rows:
        rows = ad_rows
        digital = sum((row.digitalReceipts for row in rows), Decimal("0"))
        cash = sum((row.nonDigitalReceipts for row in rows), Decimal("0"))
        other = sum((row.otherModeReceipts for row in rows), Decimal("0"))
        total_turnover = digital + cash + other
        declared_total = sum((row.declaredIncome for row in rows), Decimal("0"))
        declared = declared_total or None
        biz_44ad = PresumptiveBusinessIncome44AD(
            total_turnover=total_turnover,
            digital_turnover=digital,
            cash_turnover=cash,
            other_mode_turnover=other,
            income_at_six_percent=(
                sum((row.digitalPresumptiveIncome for row in rows), Decimal("0"))
                or None
            ),
            income_at_eight_percent=(
                sum((row.nonDigitalPresumptiveIncome for row in rows), Decimal("0"))
                or None
            ),
            income_declared=declared,
        )
    if ada_rows:
        rows = ada_rows
        gross = sum((row.grossReceipts for row in rows), Decimal("0"))
        digital = sum((row.digitalReceipts for row in rows), Decimal("0"))
        cash = sum((row.nonDigitalReceipts for row in rows), Decimal("0"))
        other = sum((row.otherModeReceipts for row in rows), Decimal("0"))
        if gross == 0:
            gross = digital + cash + other
        declared_total = sum((row.declaredIncome for row in rows), Decimal("0"))
        declared = declared_total or None
        prof_44ada = PresumptiveProfessionalIncome44ADA(
            gross_receipts=gross,
            digital_receipts=digital,
            cash_receipts=cash,
            other_mode_receipts=other,
            income_declared=declared,
        )
    if ae_rows:
        vehicles: list[GoodsCarriageVehicle] = []
        rows = ae_rows
        for business in rows:
          for v in business.vehicles:
              vehicle_type = (v.vehicleType or "OTHER").upper()
              is_heavy = vehicle_type == "HEAVY"
              tonnage = v.tonnage or None
              months = v.ownedMonths or 1
              if months < 1:
                  months = 1
              vehicles.append(GoodsCarriageVehicle(
                  is_heavy_goods_vehicle=is_heavy,
                  gross_vehicle_weight_tons=tonnage if is_heavy else None,
                  months_owned=months,
                  income_declared=v.presumptiveIncome or None,
                  reg_number=v.vehicleNumber or "",
                  owned_leased_hired_flag=(
                      v.ownedLeasedHiredFlag
                      if getattr(v, "ownedLeasedHiredFlag", None)
                      else ("HIRED" if getattr(v, "leasedOrHired", False) else "OWN")
                  ),
                  tonnage_capacity=tonnage,
              ))
        goods_44ae = PresumptiveGoodsCarriage44AE(vehicles=vehicles)

    first_scheme = businesses[0].scheme
    scheme = PresumptiveScheme(first_scheme)
    business_code = next(
        (row.natureCode for row in [*ad_rows, *ae_rows] if row.natureCode), None
    )
    profession_code = next(
        (row.natureCode for row in ada_rows if row.natureCode), None
    )
    return scheme, biz_44ad, prof_44ada, goods_44ae, business_code, profession_code


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
    salary_input, section_17_1, gross_salary = _map_salary(draft.employers, tax_regime)
    hp_input, hp_inputs = _map_house_properties(draft.houseProperties)
    loan_details_24b_list = _map_24b_loans(draft.houseProperties)
    os_input, total_interest, total_dividend, family_pension, total_winnings = (
        _map_other_sources(draft)
    )
    ded_input, structured_80g, schedule_80c_entries = _map_deductions(draft, tax_regime)
    from app.schemas.itr1 import Schedule80CCCEntry, Schedule80G
    via = draft.deductions.chapterVIA
    schedule_80d = (
        _map_80d_schedule(draft.deductions.section80D)
        if tax_regime == TaxRegime.OLD
        else None
    )
    schedule_80g = (
        Schedule80G(
            donations=ded_input.donations_80g or [],
            total_eligible_amount=ded_input.amount_80g,
        )
        if ded_input.donations_80g
        else None
    )
    schedule_80ggc = _map_80ggc(draft) if tax_regime == TaxRegime.OLD else None
    schedule_80dd, schedule_80u = _map_disability_schedules(via)
    if tax_regime == TaxRegime.NEW:
        schedule_80dd = schedule_80u = None
    schedule_80ccc_entries = [
        Schedule80CCCEntry(
            identifier_type=row.identifierType,
            identifier_name=row.identifierName,
            amount=row.amount,
        )
        for row in draft.deductions.pensionContribution80CCC
    ] if tax_regime == TaxRegime.OLD else []
    (
        schedule_80e_entries,
        loan_details_80ee_list,
        loan_details_80eea_list,
        loan_details_80eeb_list,
    ) = _map_deduction_loans(draft)
    if tax_regime == TaxRegime.NEW:
        schedule_80e_entries = []
        loan_details_80ee_list = []
        loan_details_80eea_list = []
        loan_details_80eeb_list = []
    cg_input = _map_capital_gains(draft)

    tds1, tds2, tds_salary, tds_interest, tds_other, claimed_tds, tds_issues = (
        _map_tds(draft.taxes.tds)
    )
    tds3_entries, tds3_total = _map_tds3(draft.taxes.tds)
    claimed_tds += tds3_total
    tcs_entries, total_tcs, tcs_issues = _map_tcs(draft.taxes.tcs)
    tax_payment_entries, advance_tax, sat_total, quarterly = _map_tax_payments(
        draft.taxes.challans
    )
    hra_details = _map_hra_details(draft.employers) if tax_regime == TaxRegime.OLD else None

    # ITR-4-specific: presumptive business income + scheme.
    scheme, biz_44ad, prof_44ada, goods_44ae, business_code, profession_code = (
        _map_presumptive(draft.businesses)
    )
    # Schedule BP financial particulars (CBDT Sl 139 cross-consistency).
    schedule_bp_financial = _map_schedule_bp_financial(draft.businesses)
    ae_salary_interest = sum(
        (
            business.salaryInterestFromFirm
            for business in draft.businesses
            if isinstance(business, Presumptive44AE)
        ),
        Decimal("0"),
    )
    if schedule_bp_financial is not None:
        schedule_bp_financial.salary_to_partners = ae_salary_interest
    first_business = draft.businesses[0] if draft.businesses else None
    schedule_bp_business_natures = (
        [
            ITR4BusinessNature(
                name=business.businessName,
                code=business.natureCode,
                description=business.description,
                    scheme=PresumptiveScheme(business.scheme),
            )
            for business in draft.businesses
            if business.businessName and business.natureCode
        ]
    )
    schedule_bp_gstin_turnovers = (
        [
            ITR4GstinTurnover(gstin=row.gstin, turnover=row.turnover)
            for business in draft.businesses
            for row in business.gstinTurnovers
            if row.gstin
        ]
        if first_business is not None else []
    )

    itr4_input = ITR4Input(
        age_bracket=age_bracket,
        assessee_type={
            "H": AssesseeType.HUF,
            "F": AssesseeType.FIRM,
        }.get(draft.personal.assesseeStatus, AssesseeType.INDIVIDUAL),
        tax_regime=tax_regime,
        presumptive_scheme=scheme,
        business_income_44ad=biz_44ad,
        professional_income_44ada=prof_44ada,
        goods_carriage_44ae=goods_44ae,
        salary_income=salary_input,
        house_property_income=hp_input,
        other_sources_income=os_input,
        deductions_chapter6a=ded_input,
        nature_of_employment=(
            draft.employers[0].natureOfEmployment or None
            if draft.employers else None
        ),
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
        # filing_date/due_date are set by filing_gateway_v2.compute_canonical_itr4
        # from draft.verification.date -- not set here (was previously a
        # date-of-birth placeholder that the gateway never actually
        # overwrote, silently zeroing every return's 234A/B/C interest and
        # 234F/234-I late fees; see
        # Docs/ITR1_FRONTEND_AND_SERIALIZATION_AUDIT_AY2026_27.md).
        filing_date=None,
        due_date=None,
        house_property_count=max(1, len(draft.houseProperties)),
        assessee_pan=draft.personal.pan or None,
        assessee_name=draft.personal.name or None,
        aadhaar_number=draft.personal.aadhaar or None,
        assessee_email_primary=draft.personal.email or None,
        assessee_phone_primary=draft.personal.mobile or None,
        agriculture_income=draft.exemptIncome.grossAgriculturalReceipts,
        exempt_income_breakdown={
            row.subCategory: row.grossAmount
            for row in draft.exemptIncome.otherExemptIncome
            if row.grossAmount > 0
        },
        exempt_income_dropdowns=[
            row.subCategory
            for row in draft.exemptIncome.otherExemptIncome
            if row.grossAmount > 0
        ],
        exempt_income_entries=_map_compact_exempt_income(draft),
        total_exempt_income=sum(
            (row.grossAmount for row in draft.exemptIncome.otherExemptIncome),
            Decimal("0"),
        ),
        other_sources_dropdowns=(
            ["Family Pension"]
            if draft.otherSources.familyPension.grossAmount > 0
            else []
        ),
        dividend_quarterly_breakdown=_map_dividend_quarterly_breakdown(draft),
        schedule_80d=schedule_80d,
        schedule_80g=schedule_80g,
        schedule_80gga=None,
        schedule_80ggc=schedule_80ggc,
        schedule_80dd=schedule_80dd,
        schedule_80u=schedule_80u,
        schedule_80c_entries=schedule_80c_entries,
        schedule_80ccc_entries=schedule_80ccc_entries,
        schedule_80e_entries=schedule_80e_entries,
        loan_details_80ee_list=loan_details_80ee_list,
        loan_details_80eea_list=loan_details_80eea_list,
        loan_details_80eeb_list=loan_details_80eeb_list,
        property_stamp_duty_value_80eea=(
            draft.deductions.loans.section80EEAStampDutyValue
            if loan_details_80eea_list
            else None
        ),
        loan_details_24b_list=loan_details_24b_list,
        hra_details=hra_details,
        schedule_10_13a=hra_details,
        tax_payment_entries=tax_payment_entries,
        tds3_entries=tds3_entries or None,
        total_tds_claimed=claimed_tds,
        total_tcs_claimed=total_tcs,
        schedule_it_total_paid=advance_tax + sat_total,
        schedule_tds1_total=tds_salary,
        schedule_tds2_total_claimed=tds_other,
        schedule_tds3_total_claimed=tds3_total,
        schedule_tcs_total_claimed=total_tcs,
        form_10ia_filed=(
            via.section80DDForm10IA.filed == "Y"
            or via.section80UForm10IA.filed == "Y"
        ),
        form_10ia_filed_80dd=via.section80DDForm10IA.filed == "Y",
        form_10ia_filed_80u=via.section80UForm10IA.filed == "Y",
        form_10ba_filed=bool(via.form10BAAckNum),
        form_10ba_ack_number=via.form10BAAckNum or None,
        pran_number=via.pranNumber or None,
        full_value_of_consideration=(
            cg_input.full_value_of_consideration if cg_input else None
        ),
        business_code=business_code,
        profession_code=profession_code,
        schedule_bp_financial=schedule_bp_financial,
        schedule_bp_business_natures=schedule_bp_business_natures,
        schedule_bp_gstin_turnovers=schedule_bp_gstin_turnovers,
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
        "credit_validation_issues": [*tds_issues, *tcs_issues],
        "presumptive_scheme": scheme.value,
        "presumptive_schemes": [
            value for value, model in (
                ("44AD", biz_44ad),
                ("44ADA", prof_44ada),
                ("44AE", goods_44ae),
            ) if model is not None
        ],
        "business_code": business_code,
    }
    return itr4_input, breakdown
