"""Canonical mapper: ReturnDraft → ITR2Input.

This is the SINGLE typed mapper for ITR-2 — the ITR-2 analogue of
:func:`app.engine.draft_to_itr1_input.draft_to_itr1_input` and
:func:`app.engine.draft_to_itr4_input.draft_to_itr4_input`. It reads the
canonical typed ``ReturnDraft`` — no alias guessing, no flat-blob fallback.
It replaces the flat-payload path (`app/routers/tax.py::
_compute_itr2_from_flat_payload`) that is ITR-2's only working compute path
today (`Docs/ITR2_ITR3_V2_PIPELINE_PRODUCTION_PLAN.md` §1).

Phase 3 scope (mirrors ITR-4's split): compute-relevant fields only. The
full ``ITR2FilingProfile`` (address, verification, receipt/notice numbers)
and per-row official-filing detail (``employer_filing_details``,
``property_filing_details``, ``tds3_filing_details``) are constructed in
Phase 4 by ``filing_gateway_v2.py``, the same way ITR-4's
``filing_profile``/``property_profile`` are built outside this mapper —
those are official-JSON concerns, not compute concerns. ``bank_accounts``
is the one exception: unlike ITR-4 (which has its own distinct
``ITR4BankAccount`` type needing gateway-layer validation), ITR2Input
reuses ITR-1's plain shared ``BankAccount`` type directly, so this mapper
maps it here via the same ``_map_bank_accounts`` helper ITR-1 already uses.

Shared heads reuse: salary / house property / other sources / deductions /
TDS / TCS / tax payments are the *same* typed ``ReturnDraft`` fields ITR-1
and ITR-4 already read, so this mapper delegates to the private helpers
already implemented and tested in :mod:`app.engine.draft_to_itr1_input`.
One implementation per shared head — no second copy to drift.

ITR-2-specific heads (capital gains beyond 112A, VDA, brought-forward
losses, Schedule SI, agricultural/exempt income, FSI/TR/FA/SPI/PTI/AMT/AL/
5A/ESOP) have no ITR-1/4 equivalent and are mapped fresh here from the
Phase 1/2 additive ``ReturnDraft`` fields. ``carriedForwardLossEntries``
(Schedule CFL) is deliberately NOT mapped here — its own type is documented
as "retained for reconciliation only" and ``ITR2Input`` has no field to
receive it; the CBDT JSON's carried-forward figures come from the
calculator's own set-off arithmetic, not user input.

Known, explicitly-scoped gaps (not silently papered over):

1. The capital-gains schedule's 10 generic ``JsonRow``-equivalent fields
   (``stEquity``, ``stNriUnlisted``, ``stOtherAssets``, ``ltProviso112``,
   ``ltNri112115``, ``ltForeignAssets``, ``ltOtherAssets``, ``stSlumpSale``,
   ``ltSlumpSale``, ``buyBackLosses``) are NOT mapped into
   ``cg_transactions``. Those rows have no fixed, guaranteed key shape (the
   frontend left them generic for exactly that reason); mapping them
   correctly requires reading ``CapitalGainsEntryManager.tsx``'s exact
   field-spec key names rather than guessing. Only the concretely-typed
   sources (``schedule112A``, ``schedule115AD``, ``stImmovable``,
   ``ltImmovable``, ``vda``) are mapped in this pass.
2. Schedule 112A/115AD scrips with no ``dateOfTransfer`` captured (the norm
   today — see ``app/schemas/return_draft.py::Scrip112A`` for why) are
   skipped from ``cg_112a_scrips`` rather than assigned a fabricated date.
   The count of skipped scrips is surfaced in the mapper's ``breakdown``
   dict (``cg_112a_scrips_skipped_no_date``) so this is visible, not silent.

Authority: :class:`app.schemas.return_draft.ReturnDraft` (canonical draft)
and :class:`app.schemas.itr2.ITR2Input` (typed compute input).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Optional

from app.schemas.itr1 import TaxRegime
from app.schemas.itr2 import (
    AgriculturalIncome,
    AMTCreditItem,
    AMTInput,
    AssetLiabilityInput,
    BFLossItem,
    CG112AScrip,
    CGAssetType,
    CGTransaction,
    ESOPDeferralInput,
    ExemptIncome,
    ForeignAssetEntry as ITR2ForeignAssetEntry,
    ForeignAssetType as ITR2ForeignAssetType,
    FSICountryEntry,
    ITR2Input,
    LossHead as ITR2LossHead,
    PTIEntry,
    ResidentialStatus as ITR2ResidentialStatus,
    Schedule5AInput,
    ScheduleSIEntry as ITR2ScheduleSIEntry,
    SPIEntry,
    TR1Entry,
    VDATransaction,
)
from app.schemas.return_draft import ReturnDraft

# Shared form-agnostic helpers — one implementation of each shared head.
from app.engine.draft_to_itr1_input import (
    _age_bracket_from_dob,
    _map_bank_accounts,
    _map_deductions,
    _map_house_properties,
    _map_other_sources,
    _map_salary,
    _map_tax_payments,
    _map_tcs,
    _map_tds,
    _map_tds3,
    _to_date,
)


# ---------------------------------------------------------------------------
# Residential status — draft (ROR/RNOR/NR, matches live eligibility.ts) to
# the CBDT wire codes (RES/NRI/NOR) ITR2Input actually needs.
# ---------------------------------------------------------------------------

_RESIDENTIAL_STATUS_TO_CBDT: dict[str, ITR2ResidentialStatus] = {
    "ROR": ITR2ResidentialStatus.RESIDENT,
    "RNOR": ITR2ResidentialStatus.NOT_ORDINARILY_RESIDENT,
    "NR": ITR2ResidentialStatus.NON_RESIDENT,
}


def _map_residential_status(value: str) -> ITR2ResidentialStatus:
    """Translate the draft's ROR/RNOR/NR into the CBDT RES/NRI/NOR codes.

    See ``Docs/ITR2_ITR3_V2_PIPELINE_PRODUCTION_PLAN.md`` Phase 2 for why the
    draft keeps the frontend's already-shipped enum rather than the wire
    codes — this is where the translation actually happens, the same way
    every other mapper translates draft-level values into CBDT-exact codes.
    """
    return _RESIDENTIAL_STATUS_TO_CBDT.get(value, ITR2ResidentialStatus.RESIDENT)


# ---------------------------------------------------------------------------
# Capital gains — full Schedule CG (112A/115AD scrips, land/building, VDA)
# ---------------------------------------------------------------------------

def _map_112a_scrips(draft: ReturnDraft) -> tuple[list[CG112AScrip], int]:
    """Map Schedule 112A + 115AD scrips into ``CG112AScrip`` rows.

    The calculator unions ``cg_transactions`` and ``cg_112a_scrips`` before
    applying the ₹1.25L 112A threshold, so this list — not a duplicate
    presence in ``cg_transactions`` — is the 112A/115AD source of truth.

    Returns:
        ``(scrips, skipped_count)`` — scrips missing ``dateOfTransfer`` are
        excluded rather than assigned a fabricated date; ``skipped_count``
        surfaces how many so the gap is visible, not silent.
    """
    schedule = draft.capitalGainsSchedule
    scrips: list[CG112AScrip] = []
    skipped = 0
    for row in (*schedule.schedule112A, *schedule.schedule115AD):
        transfer_date = _to_date(row.dateOfTransfer)
        if transfer_date is None:
            skipped += 1
            continue
        scrips.append(CG112AScrip(
            isin_code=row.isin or "INNOTREQUIRD",
            share_unit_name=row.name or "NA",
            is_before_31jan2018=row.shareOnOrBefore == "BE",
            date_of_acquisition=_to_date(row.dateOfAcquisition),
            date_of_transfer=transfer_date,
            num_shares_units=row.quantity or Decimal("0.000001"),
            sale_price_per_share=row.salePricePerUnit,
            total_sale_value=row.totalSaleValue,
            cost_acq_without_index=row.costWithoutIndexation,
            fmv_per_share=row.fmvPerUnit,
            total_fmv=row.totalFmv,
            expenditure_on_transfer=row.transferExpenses,
            total_deductions=row.totalDeductions or Decimal("0"),
            stt_paid_on_transfer=True,
        ))
    return scrips, skipped


def _map_immovable_gains(draft: ReturnDraft) -> list[CGTransaction]:
    """Map typed land/building rows (``stImmovable``/``ltImmovable``) into
    ``CGTransaction`` rows, tagged with ``explicit_long_term`` so the
    calculator's ST/LT classification doesn't depend on both dates being
    present (``dateOfPurchase`` is optional on these rows)."""
    schedule = draft.capitalGainsSchedule
    transactions: list[CGTransaction] = []
    for is_long_term, rows in ((False, schedule.stImmovable), (True, schedule.ltImmovable)):
        for row in rows:
            transfer_date = _to_date(row.dateOfSale)
            if transfer_date is None:
                continue
            transactions.append(CGTransaction(
                asset_type=CGAssetType.LAND_BUILDING,
                description=row.propertyAddress or "",
                date_of_acquisition=_to_date(row.dateOfPurchase),
                date_of_transfer=transfer_date,
                full_consideration=row.fullConsideration,
                stamp_duty_value=row.stampDutyValue,
                cost_of_acquisition=row.acquisitionCost,
                indexed_cost=row.indexedAcquisitionCost or Decimal("0"),
                improvement_cost=row.improvementCost or Decimal("0"),
                indexed_improvement=row.indexedImprovementCost or Decimal("0"),
                expenditure_on_transfer=row.transferExpenses,
                explicit_long_term=is_long_term,
                deduction_us54=row.exemptionAmount or Decimal("0") if row.exemptionSection == "54" else Decimal("0"),
                deduction_us54b=row.exemptionAmount or Decimal("0") if row.exemptionSection == "54B" else Decimal("0"),
                deduction_us54ec=row.exemptionAmount or Decimal("0") if row.exemptionSection == "54EC" else Decimal("0"),
                deduction_us54f=row.exemptionAmount or Decimal("0") if row.exemptionSection == "54F" else Decimal("0"),
            ))
    return transactions


def _map_vda_transactions(draft: ReturnDraft) -> list[VDATransaction]:
    """Map Schedule VDA rows. Rows missing either date are skipped — both
    are required by ``VDATransaction`` and by the statutory holding-period
    check it enforces."""
    transactions: list[VDATransaction] = []
    for row in draft.capitalGainsSchedule.vda:
        acquired = _to_date(row.dateOfAcquisition)
        transferred = _to_date(row.dateOfTransfer)
        if acquired is None or transferred is None or transferred <= acquired:
            continue
        transactions.append(VDATransaction(
            date_of_acquisition=acquired,
            date_of_transfer=transferred,
            acquisition_cost=row.acquisitionCost,
            consideration_received=row.consideration,
        ))
    return transactions


# ---------------------------------------------------------------------------
# Brought-forward losses (Schedule CFL opening rows)
# ---------------------------------------------------------------------------

_LOSS_HEAD_MAP: dict[str, ITR2LossHead] = {
    "HP": ITR2LossHead.HOUSE_PROPERTY,
    "STCG": ITR2LossHead.SHORT_TERM_CAPITAL,
    "LTCG": ITR2LossHead.LONG_TERM_CAPITAL,
    "RaceHorse": ITR2LossHead.RACE_HORSE,
}


def _map_bf_losses(draft: ReturnDraft) -> list[BFLossItem]:
    """Map ``broughtForwardLossEntries`` (Phase 2) into ``BFLossItem`` rows."""
    items: list[BFLossItem] = []
    for row in draft.broughtForwardLossEntries:
        if not row.assessmentYear:
            continue
        items.append(BFLossItem(
            assessment_year=row.assessmentYear,
            head=_LOSS_HEAD_MAP.get(row.head, ITR2LossHead.HOUSE_PROPERTY),
            sub_category=row.subCategory,
            original_loss=row.originalLoss,
            brought_forward=row.broughtForward,
            date_of_filing=_to_date(row.dateOfFiling),
        ))
    return items


# ---------------------------------------------------------------------------
# Agricultural + exempt income (Schedule EI)
# ---------------------------------------------------------------------------

def _map_agricultural_income(draft: ReturnDraft) -> Optional[AgriculturalIncome]:
    ei = draft.exemptIncome
    if ei.grossAgriculturalReceipts <= 0 and ei.agriculturalExpenses <= 0:
        return None
    return AgriculturalIncome(
        gross_agricultural_income=ei.grossAgriculturalReceipts,
        agricultural_deductions=ei.agriculturalExpenses,
    )


def _map_exempt_income(draft: ReturnDraft) -> Optional[ExemptIncome]:
    """Map ``otherExemptIncome`` into ``ExemptIncome``.

    Deliberately not bucketed by CBDT subcategory code (ppf/sukanya/bonds/
    NRE/firm-share) — several of those codes have no unambiguous match in
    the existing ``ExemptIncomeSubCategory`` list, and guessing risks
    misclassifying real exempt income. Everything rolls into ``other_exempt``
    with the total preserved exactly; refining the per-category bucketing is
    a follow-up once real user data shows which subcodes actually appear.
    """
    entries = draft.exemptIncome.otherExemptIncome
    total = sum((row.grossAmount for row in entries), Decimal("0"))
    if total <= 0:
        return None
    return ExemptIncome(
        other_exempt=total,
        other_description="; ".join(
            row.description for row in entries if row.description
        )[:125] or None,
    )


# ---------------------------------------------------------------------------
# Foreign schedules (FSI, TR, FA) + clubbing (SPI) + pass-through (PTI)
# ---------------------------------------------------------------------------

def _map_fsi_entries(draft: ReturnDraft) -> list[FSICountryEntry]:
    return [
        FSICountryEntry(
            country_code=row.countryCode,
            tax_identification_no=row.taxIdentificationNo,
            salary_income=row.salaryIncome,
            hp_income=row.hpIncome,
            cg_income=row.cgIncome,
            os_income=row.osIncome,
            tax_paid_outside_india=row.taxPaidOutsideIndia,
            tax_payable_in_india=row.taxPayableInIndia,
            relief_section=row.reliefSection,
        )
        for row in draft.foreignSourceIncome
        if row.countryCode and row.taxIdentificationNo
    ]


def _map_tr1_entries(draft: ReturnDraft) -> list[TR1Entry]:
    return [
        TR1Entry(
            country_code=row.countryCode,
            tax_identification_no=row.taxIdentificationNo,
            income_included_in_this_return=row.incomeIncludedInThisReturn,
            tax_paid_outside_india=row.taxPaidOutsideIndia,
            indian_tax_payable=row.indianTaxPayable,
            relief_claimed=min(row.reliefClaimed, row.taxPaidOutsideIndia, row.indianTaxPayable),
            relief_section=row.reliefSection,
            form67_filed=row.form67Filed,
        )
        for row in draft.foreignTaxRelief
        if row.countryCode and row.taxIdentificationNo
    ]


_FA_ASSET_TYPE_MAP: dict[str, ITR2ForeignAssetType] = {
    "BANK_ACCOUNT": ITR2ForeignAssetType.BANK_ACCOUNT,
    "CUSTODIAL_ACCOUNT": ITR2ForeignAssetType.CUSTODIAL_ACCOUNT,
    "EQUITY_DEBT_INTEREST": ITR2ForeignAssetType.EQUITY_DEBT_INTEREST,
    "CASH_VALUE_INSURANCE": ITR2ForeignAssetType.CASH_VALUE_INSURANCE,
    "FINANCIAL_INTEREST": ITR2ForeignAssetType.FINANCIAL_INTEREST,
    "IMMOVABLE_PROPERTY": ITR2ForeignAssetType.IMMOVABLE_PROPERTY,
    "SIGNING_AUTHORITY": ITR2ForeignAssetType.SIGNING_AUTHORITY,
    "TRUST": ITR2ForeignAssetType.TRUST,
    "OTHER_FOREIGN_INCOME": ITR2ForeignAssetType.OTHER_FOREIGN_INCOME,
    "OTHER_ASSET": ITR2ForeignAssetType.OTHER_ASSET,
}


def _map_foreign_assets(draft: ReturnDraft) -> list[ITR2ForeignAssetEntry]:
    entries: list[ITR2ForeignAssetEntry] = []
    for row in draft.foreignAssets:
        acquired = _to_date(row.openingOrAcquisitionDate)
        if acquired is None or not row.countryCode:
            continue
        entries.append(ITR2ForeignAssetEntry(
            asset_type=_FA_ASSET_TYPE_MAP.get(row.assetType, ITR2ForeignAssetType.OTHER_ASSET),
            country_code=row.countryCode,
            institution_or_entity_name=row.institutionOrEntityName or "NA",
            address=row.address or "NA",
            account_or_asset_identifier=row.accountOrAssetIdentifier or "NA",
            ownership_status=row.ownershipStatus or "Owner",
            opening_or_acquisition_date=acquired,
            peak_value=row.peakValue,
            closing_value=row.closingValue,
            gross_income=row.grossIncome,
            income_offered=row.incomeOffered,
            income_head=row.incomeHead,
        ))
    return entries


def _map_spi_entries(draft: ReturnDraft) -> list[SPIEntry]:
    return [
        SPIEntry(
            specified_person_name=row.specifiedPersonName,
            pan=row.pan or None,
            relationship=row.relationship,
            amount_included=row.amountIncluded,
            head_of_income=row.headOfIncome,
        )
        for row in draft.clubbedIncome
        if row.specifiedPersonName and row.relationship
    ]


def _map_pti_entries(draft: ReturnDraft) -> list[PTIEntry]:
    return [
        PTIEntry(
            entity_name=row.entityName,
            entity_pan=row.entityPAN,
            income_head=row.incomeHead,
            section=row.section,
            income_amount=row.incomeAmount,
            tds_credit=row.tdsCredit,
        )
        for row in draft.passThroughIncomeEntries
        if row.entityName and row.entityPAN
    ]


def _map_amt_input(draft: ReturnDraft) -> Optional[AMTInput]:
    amt = draft.amt
    if amt is None:
        return None
    return AMTInput(
        deduction_10aa=amt.deduction10AA,
        deduction_80ia_to_80rrb_except_80p=amt.deduction80IAto80RRBExcept80P,
        deduction_35ad_net_depreciation=amt.deduction35ADNetDepreciation,
        amt_credits=[
            AMTCreditItem(
                assessment_year=row.assessmentYear,
                credit_brought_forward=row.creditBroughtForward,
            )
            for row in amt.creditsBroughtForward
            if row.assessmentYear
        ],
    )


def _map_asset_liability(draft: ReturnDraft) -> Optional[AssetLiabilityInput]:
    """Map ``assetLiability`` (Schedule AL) — required by ITR2-CALC-027 once
    taxable income exceeds ₹1 crore; previously never wired from the draft,
    so that calc-validation rule could never actually be satisfied."""
    al = draft.assetLiability
    if al is None:
        return None
    return AssetLiabilityInput(
        immovable_property=al.immovableProperty,
        cash_in_hand=al.cashInHand,
        bank_deposits=al.bankDeposits,
        shares_and_securities=al.sharesAndSecurities,
        insurance_policies=al.insurancePolicies,
        loans_and_advances=al.loansAndAdvances,
        jewellery=al.jewellery,
        art=al.art,
        vehicles_boats_aircraft=al.vehiclesBoatsAircraft,
        related_liabilities=al.relatedLiabilities,
    )


def _map_schedule_5a(draft: ReturnDraft) -> Optional[Schedule5AInput]:
    """Map ``portugueseCivilCode`` (Schedule 5A). Requires spouse name and
    PAN — rows missing either are dropped rather than raising, mirroring
    the guard-clause pattern the other optional schedules already use."""
    pcc = draft.portugueseCivilCode
    if pcc is None or not pcc.spouseName or not pcc.spousePAN:
        return None
    return Schedule5AInput(
        spouse_name=pcc.spouseName,
        spouse_pan=pcc.spousePAN,
        spouse_aadhaar=pcc.spouseAadhaar or None,
        hp_amount_apportioned=pcc.hpAmountApportioned,
        cg_amount_apportioned=pcc.cgAmountApportioned,
        os_amount_apportioned=pcc.osAmountApportioned,
        tds_apportioned=pcc.tdsApportioned,
    )


def _map_esop_deferrals(draft: ReturnDraft) -> list[ESOPDeferralInput]:
    return [
        ESOPDeferralInput(
            employer_pan=row.employerPAN,
            dpiit_registration_number=row.dpiitRegistrationNumber,
            assessment_year=row.assessmentYear,
            tax_deferred_brought_forward=row.taxDeferredBroughtForward,
            tax_payable_current_year=row.taxPayableCurrentYear,
            balance_tax_carried_forward=row.balanceTaxCarriedForward,
        )
        for row in draft.esopDeferrals
        if row.employerPAN and row.dpiitRegistrationNumber and row.assessmentYear
    ]


_SI_SECTION_MAP: dict[str, str] = {
    "115BB": "115BB", "115BBE": "115BBE", "115BBF": "115BBF",
    "115BBG": "115BBG", "115BBJ": "115BBJ", "115BBA": "115BBA", "111": "111",
}


def _map_si_entries(draft: ReturnDraft) -> list[ITR2ScheduleSIEntry]:
    return [
        ITR2ScheduleSIEntry(
            section=row.section,
            description=row.description or None,
            gross_income=row.grossIncome,
            deductions=row.deductions,
            tax_rate_pct=row.taxRatePct,
        )
        for row in draft.scheduleSIEntries
        if row.grossIncome > 0
    ]


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def draft_to_itr2_input(
    draft: ReturnDraft,
) -> tuple[ITR2Input, dict[str, Any]]:
    """Map a canonical ``ReturnDraft`` → ``ITR2Input`` for compute + CBDT.

    Args:
        draft: The canonical typed draft. ``draft.form`` should be ``"ITR-2"``;
            this mapper does not enforce that (the gateway dispatcher does).

    Returns:
        ``(itr2_input, breakdown)`` — ``breakdown`` carries the same
        intermediate totals the ITR-1/4 mappers surface, plus
        ``cg_112a_scrips_skipped_no_date`` (see module docstring).

    Raises:
        DraftMappingError: If the draft carries income outside ITR-1/2 scope
            (delegated to :func:`_map_other_sources`, which rejects lottery/
            gaming winnings the same way for every form that calls it).
    """
    tax_regime = TaxRegime.OLD if draft.regime == "old" else TaxRegime.NEW
    age_bracket = _age_bracket_from_dob(draft.personal.dateOfBirth)
    residential_status = _map_residential_status(draft.personal.residentialStatus)

    # Shared heads — one implementation, reused (audit Finding 14 fix).
    salary_input, section_17_1, gross_salary = _map_salary(draft.employers, tax_regime)
    hp_input, hp_inputs = _map_house_properties(draft.houseProperties)
    os_input, total_interest, total_dividend, family_pension, total_winnings = (
        _map_other_sources(draft)
    )
    ded_input, structured_80g, schedule_80c_entries = _map_deductions(draft, tax_regime)

    tds1, tds2, tds_salary, tds_interest, tds_other, claimed_tds, tds_issues = (
        _map_tds(draft.taxes.tds)
    )
    tds3_entries, tds3_total = _map_tds3(draft.taxes.tds)
    claimed_tds += tds3_total
    tcs_entries, total_tcs, tcs_issues = _map_tcs(draft.taxes.tcs)
    tax_payment_entries, advance_tax, sat_total, quarterly = _map_tax_payments(
        draft.taxes.challans
    )

    # ITR-2-specific: full Schedule CG, VDA, brought-forward losses, SI,
    # agricultural/exempt income, FSI/TR/FA/SPI/PTI/AMT.
    cg_112a_scrips, scrips_skipped = _map_112a_scrips(draft)
    cg_transactions = _map_immovable_gains(draft)
    vda_transactions = _map_vda_transactions(draft)
    bf_losses = _map_bf_losses(draft)
    si_entries = _map_si_entries(draft)
    agricultural_income = _map_agricultural_income(draft)
    exempt_income = _map_exempt_income(draft)
    fsi_entries = _map_fsi_entries(draft)
    tr1_entries = _map_tr1_entries(draft)
    foreign_assets = _map_foreign_assets(draft)
    spi_entries = _map_spi_entries(draft)
    pti_entries = _map_pti_entries(draft)
    amt_input = _map_amt_input(draft)
    asset_liability = _map_asset_liability(draft)
    schedule_5a = _map_schedule_5a(draft)
    esop_deferrals = _map_esop_deferrals(draft)
    bank_accounts = _map_bank_accounts(draft.bankAccounts)

    itr2_input = ITR2Input(
        age_bracket=age_bracket,
        tax_regime=tax_regime,
        residential_status=residential_status,
        salary_income=salary_input,
        house_property_income=hp_input if len(hp_inputs) <= 1 else None,
        house_properties=hp_inputs if len(hp_inputs) > 1 else [],
        other_sources_income=os_input,
        cg_transactions=cg_transactions,
        cg_112a_scrips=cg_112a_scrips,
        vda_transactions=vda_transactions,
        bf_losses=bf_losses,
        si_entries=si_entries,
        agricultural_income=agricultural_income,
        exempt_income=exempt_income,
        fsi_entries=fsi_entries,
        tr1_entries=tr1_entries,
        foreign_assets=foreign_assets,
        spi_entries=spi_entries,
        pti_entries=pti_entries,
        amt_input=amt_input,
        asset_liability=asset_liability,
        schedule_5a=schedule_5a,
        esop_deferrals=esop_deferrals,
        deductions_chapter6a=ded_input,
        tds1_entries=tds1,
        tds2_entries=tds2,
        tds3_entries=tds3_entries,
        tcs_entries=tcs_entries,
        tax_payment_entries=tax_payment_entries,
        bank_accounts=bank_accounts,
        advance_tax_paid=advance_tax,
        advance_tax_q1=quarterly[0] or None,
        advance_tax_q2=quarterly[1] or None,
        advance_tax_q3=quarterly[2] or None,
        advance_tax_q4=quarterly[3] or None,
        self_assessment_tax_paid=sat_total,
        # filing_date/due_date: intentionally left unset. Per
        # Docs/ITR1_ITR4_COMPLETE_PIPELINE_REFERENCE.md, this is a real,
        # pre-existing cross-form gap (234A/B/C/F interest silently skipped
        # for ITR-1/4 too) — not invented fresh here, tracked separately.
        filing_date=None,
        due_date=None,
        filing_profile=None,  # Phase 4: constructed by filing_gateway_v2.
        employer_filing_details=[],
        property_filing_details=[],
        tds3_filing_details=[],
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
        "cg_112a_scrips_skipped_no_date": scrips_skipped,
    }
    return itr2_input, breakdown
