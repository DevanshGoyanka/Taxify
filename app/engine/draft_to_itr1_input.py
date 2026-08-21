"""
Canonical mapper: ReturnDraft → ITR1Input.

This is the SINGLE typed mapper for ITR-1. It replaced the two duplicate
flat→typed mappers that had to stay in sync:

  - ``app/routers/tax.py::_compute_tax_summary_impl`` (the ITR-1 branch,
    ~790 lines) — mapped flat blob → typed input for COMPUTE.
  - ``app/engine/filing_gateway.py::_build_itr1_input_from_flat`` (~300
    lines) — mapped flat blob → typed input for CBDT JSON generation
    (deleted in Phase 7; the legacy CBDT endpoint now routes through
    ``flat_to_draft`` → this mapper → the v2 pipeline).

Both re-implemented the same alias-parsing (``row.get("hra",
row.get("hraReceived"))``, ``_first_money(...)`` etc.). This module
does the mapping ONCE, from the canonical typed ``ReturnDraft`` — no
aliases, no guessing.

Phase 1 scope: compute-relevant fields only (income heads, deductions,
TDS/TCS, tax payments, bank accounts). The full ``ITR1FilingProfile``
(address, father name, verification, 7th-proviso, Form 10-IEA) is
constructed in Phase 2 by ``filing_gateway_v2`` because those fields
are not part of ``ReturnDraft`` today (they live in ``Client`` master
and the ``PersonalInfoTab``).

Authority: ``app/schemas/return_draft.py::ReturnDraft`` (the canonical
draft) and ``app/schemas/itr1.py::ITR1Input`` (the typed compute input).
"""

from __future__ import annotations

import datetime
from decimal import Decimal
from typing import Any

from app.schemas.return_draft import (
    BankAccount as DraftBankAccount,
    ChapterVIA,
    DeductionLoan,
    Donation80G,
    Employer,
    GiftIncome,
    HouseProperty,
    InterestIncome,
    Investment80C,
    Policy80D,
    Presumptive44AD,
    Presumptive44ADA,
    Presumptive44AE,
    ReturnDraft,
    Section80D,
    TdsCredit,
    TaxChallan,
    TcsCredit,
    WinningIncome,
)
from app.schemas.itr1 import (
    AssesseeType,
    AgeBracket,
    BankAccount,
    BankAccountType,
    CapitalGainsIncome,
    Chapter6ADeductions,
    Donation80G as ITR1Donation80G,
    Donation80GCategory,
    DonationAddress,
    HousePropertyIncome,
    ITR1Input,
    OtherSourcesIncome,
    PropertyType,
    SalaryIncome,
    TDS1Entry,
    TDS2Entry,
    TCSEntry,
    TaxPaymentDetail,
    TaxRegime,
)


class DraftMappingError(ValueError):
    """Raised when the canonical draft cannot be mapped to ITR1Input."""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _to_date(value: str | None) -> datetime.date | None:
    """Parse a ``YYYY-MM-DD`` string; return None if blank or unparseable."""
    if not value:
        return None
    try:
        return datetime.date.fromisoformat(str(value).strip())
    except ValueError:
        return None


def _age_bracket_from_dob(dob: str | None) -> AgeBracket:
    """Derive the AgeBracket from the assessee's DOB.

    AY 2026-27 → previous year ends 2026-03-31. Age is computed as of
    that date. Falls back to BELOW_60 when DOB is absent (the compute
    engine's historical default).
    """
    if not dob:
        return AgeBracket.BELOW_60
    birth = _to_date(dob)
    if birth is None:
        return AgeBracket.BELOW_60
    # Age as on 31 March 2026 (end of FY 2025-26 for AY 2026-27).
    ref = datetime.date(2026, 3, 31)
    age = ref.year - birth.year - (
        (ref.month, ref.day) < (birth.month, birth.day)
    )
    if age >= 80:
        return AgeBracket.ABOVE_80
    if age >= 60:
        return AgeBracket.SIXTY_TO_80
    return AgeBracket.BELOW_60


# ---------------------------------------------------------------------------
# Salary
# ---------------------------------------------------------------------------

def _map_salary(employers: list[Employer]) -> tuple[SalaryIncome, Decimal, Decimal]:
    """Map canonical employer rows → ``SalaryIncome`` (aggregate).

    Returns ``(salary_input, section_17_1_salary, gross_salary)`` so the
    caller can surface the breakdown in the compute response without
    re-walking the rows.

    HRA exemption is recomputed per-employer u/s 10(13A) from the three-
    condition test (actual HRA, rent − 10% salary, 50%/40% salary) —
    the engine never trusts a frontend-supplied exempt amount.  When an
    employer has HRA but no rent/metro facts, the exemption for that row
    is zero (mirrors the legacy per-employer recompute in tax.py).
    """
    from app.engine.common.hra import compute_hra_exemption

    basic = sum((e.basic for e in employers), Decimal("0"))
    da = sum((e.da for e in employers), Decimal("0"))
    bonus = sum((e.bonus for e in employers), Decimal("0"))
    commission = sum((e.commission for e in employers), Decimal("0"))
    hra_received = sum((e.hra for e in employers), Decimal("0"))
    other_allowance = sum((e.allowances for e in employers), Decimal("0"))
    perquisites = sum((e.perquisites for e in employers), Decimal("0"))
    profits_in_lieu = sum((e.profitsInLieu for e in employers), Decimal("0"))

    section_17_1 = basic + da + bonus + commission + hra_received + other_allowance
    gross_salary = section_17_1 + perquisites + profits_in_lieu

    # Statutorily recompute the HRA exemption per employer (u/s 10(13A)).
    hra_exempt = Decimal("0")
    for e in employers:
        row_hra = e.hra
        row_rent = e.rentPaid
        row_salary = e.basic + e.da
        row_metro = e.isMetroCity
        if row_hra > 0 and row_rent > 0 and row_salary > 0:
            hra_exempt += compute_hra_exemption(
                actual_hra_received=row_hra,
                rent_paid=row_rent,
                salary=row_salary,
                is_metro=row_metro,
            ).exempt_amount
        # When HRA > 0 but rent/metro facts are missing, exemption is zero
        # for that row — surfaced later as a validation issue, not trusted.

    lta_exempt = sum((e.ltaExempt for e in employers), Decimal("0"))
    prof_tax = sum((e.professionalTax for e in employers), Decimal("0"))
    ent_allowance = sum((e.entertainmentAllowance for e in employers), Decimal("0"))
    is_govt = any(e.isGovernmentEmployee for e in employers)

    salary_input = SalaryIncome(
        gross_salary=gross_salary,
        perquisites_value=perquisites,
        profits_in_lieu_of_salary=profits_in_lieu,
        hra_exempt_amount=hra_exempt,
        lta_exempt_amount=lta_exempt,
        professional_tax_paid=prof_tax,
        entertainment_allowance=ent_allowance,
        is_government_employee=is_govt,
    )
    return salary_input, section_17_1, gross_salary


# ---------------------------------------------------------------------------
# House Property
# ---------------------------------------------------------------------------

_HP_TYPE_MAP = {
    "SELF_OCCUPIED": PropertyType.SELF_OCCUPIED,
    "LET_OUT": PropertyType.LET_OUT,
    "DEEMED_LET_OUT": PropertyType.DEEMED_LET_OUT,
}


def _map_house_property(prop: HouseProperty) -> HousePropertyIncome:
    """Map one canonical ``HouseProperty`` → the compute ``HousePropertyIncome``."""
    property_type = _HP_TYPE_MAP.get(prop.propertyType, PropertyType.LET_OUT)
    # interestOnLoan is the primary field; fall back to the first homeLoan's
    # interestUs24B when the top-level scalar is zero (mirrors the flat mapper).
    loan_interest = prop.interestOnLoan
    if loan_interest == 0 and prop.homeLoans:
        loan_interest = sum((hl.interestUs24B for hl in prop.homeLoans), Decimal("0"))
    return HousePropertyIncome(
        property_type=property_type,
        annual_rent_received=prop.annualRent if prop.annualRent > 0 else (
            prop.annualLettingValue if prop.annualLettingValue > 0 else prop.maxRent
        ),
        municipal_taxes_paid=prop.municipalTaxesPaid,
        home_loan_interest_paid=loan_interest,
        municipal_value=prop.municipalRateableValue,
        fair_rent=prop.fairRentValue,
        arrears_unrealised_rent_received=prop.arrearsOfRent,
    )


def _map_house_properties(
    properties: list[HouseProperty],
) -> tuple[HousePropertyIncome, list[HousePropertyIncome]]:
    """Return ``(first_row, all_rows)`` for backward compatibility."""
    if not properties:
        hp = HousePropertyIncome(property_type=PropertyType.SELF_OCCUPIED)
        return hp, [hp]
    mapped = [_map_house_property(p) for p in properties]
    return mapped[0], mapped


# ---------------------------------------------------------------------------
# Other Sources
# ---------------------------------------------------------------------------

_SAVINGS_KINDS = {"SAVINGS_BANK", "POST_OFFICE"}


def _map_other_sources(draft: ReturnDraft) -> tuple[OtherSourcesIncome, Decimal, Decimal, Decimal, Decimal]:
    """Map canonical OS rows → ``OtherSourcesIncome`` + breakdown totals.

    Returns ``(os_input, total_interest, total_dividend, family_pension,
    total_winnings)``.
    """
    interest: list[InterestIncome] = draft.otherSources.interest
    interest_sb = sum(
        (i.grossAmount for i in interest if i.kind in _SAVINGS_KINDS),
        Decimal("0"),
    )
    interest_fd = sum(
        (i.grossAmount for i in interest if i.kind not in _SAVINGS_KINDS),
        Decimal("0"),
    )
    total_interest = interest_sb + interest_fd

    total_dividend = sum(
        (d.grossAmount for d in draft.otherSources.dividends),
        Decimal("0"),
    )

    family_pension = draft.otherSources.familyPension.grossAmount

    lottery = sum(
        (w.grossAmount for w in draft.otherSources.winnings
         if w.type != "HORSE_RACE"),
        Decimal("0"),
    )
    horse_race = sum(
        (w.grossAmount for w in draft.otherSources.winnings
         if w.type == "HORSE_RACE"),
        Decimal("0"),
    )
    total_winnings = lottery + horse_race

    # ITR-1 does not permit lottery/gaming/VDA income — reject early so the
    # caller can raise a clear 422 (mirrors the flat mapper's guard).
    if total_winnings > 0 and draft.form in {"ITR-1", "ITR-4"}:
        raise DraftMappingError(
            "Lottery, gaming, or horse-race winnings are outside ITR-1/ITR-4; "
            "use ITR-2/ITR-3."
        )

    os_input = OtherSourcesIncome(
        savings_bank_interest=interest_sb,
        fixed_deposit_interest=interest_fd,
        family_pension_received=family_pension,
        dividend_income=total_dividend,
    )
    return os_input, total_interest, total_dividend, family_pension, total_winnings


# ---------------------------------------------------------------------------
# Deductions
# ---------------------------------------------------------------------------

def _map_80c(investments: list[Investment80C]) -> Decimal:
    return sum((i.amount for i in investments), Decimal("0"))


def _map_80d_category(cat) -> tuple[Decimal, Decimal]:
    """Return ``(eligible_amount, preventive)`` for a canonical 80D category."""
    premiums = sum((p.premiumAmount for p in cat.policies), Decimal("0"))
    eligible = premiums + cat.medicalExpense
    return eligible, cat.preventiveCheckup


def _map_80d(section: Section80D) -> tuple[Decimal, Decimal, Decimal, Decimal, bool]:
    """Return ``(self_80d, parents_80d, preventive_self, preventive_parents,
    parents_are_senior)``."""
    self_is_senior = section.selfSeniorCitizen in {"Y", "S"}
    parents_are_senior = section.parentsSeniorCitizen in {"Y", "P"}
    self_key = "selfFamilySenior" if self_is_senior else "selfFamily"
    parents_key = "parentsSenior" if parents_are_senior else "parents"
    self_80d, prev_self = _map_80d_category(getattr(section, self_key))
    parents_80d, prev_parents = _map_80d_category(getattr(section, parents_key))
    return self_80d, parents_80d, prev_self, prev_parents, parents_are_senior


def _map_donations(donations: list[Donation80G]) -> tuple[list[ITR1Donation80G], Decimal]:
    mapped: list[ITR1Donation80G] = []
    for row in donations:
        address = None
        if any([row.addrDetail, row.city, row.stateCode, row.pinCode]):
            address = DonationAddress(
                address_line=row.addrDetail,
                city_or_district=row.city,
                state_code=row.stateCode,
                pin_code=int(row.pinCode or 0),
            )
        mapped.append(ITR1Donation80G(
            category=Donation80GCategory(row.category),
            cash_amount=row.donationAmtCash,
            non_cash_amount=row.donationAmtOtherMode,
            donee_name=row.doneeName or None,
            donee_pan=row.doneePAN or None,
            approval_reference_number=row.arnNumber or None,
            address=address,
            transaction_ref=row.transactionRefNum or None,
            ifsc_code=row.ifscCode or None,
        ))
    total = sum((d.cash_amount + d.non_cash_amount for d in mapped), Decimal("0"))
    return mapped, total


def _map_deductions(draft: ReturnDraft, tax_regime: TaxRegime) -> tuple[Chapter6ADeductions, Decimal]:
    """Map canonical deductions → ``Chapter6ADeductions`` + total 80G."""
    total_80c = _map_80c(draft.deductions.section80C)
    self_80d, parents_80d, prev_self, prev_parents, parents_senior = _map_80d(
        draft.deductions.section80D
    )
    donations, structured_80g = _map_donations(draft.deductions.section80G)

    via: ChapterVIA = draft.deductions.chapterVIA
    interest_sb = sum(
        (i.grossAmount for i in draft.otherSources.interest if i.kind in _SAVINGS_KINDS),
        Decimal("0"),
    )

    # New regime (u/s 115BAC) excludes almost all Chapter VI-A deductions
    # except employer NPS (80CCD(2)) and the new-regime-specific 80TTA/80TTB
    # exclusion (which is 0 anyway).  Old-regime-only deductions (80C, 80D,
    # 80E, 80G, 80CCD(1B), 80EE/EEA/EEB, 80GG, 80GGA, 80GGC, 80DD, 80DDB,
    # 80U, 80QQB, 80RRB) must be zeroed under the new regime so saved
    # old-regime values cannot leak into new-regime compute.  The draft
    # preserves them for auditability; only the typed compute input is zeroed.
    if tax_regime == TaxRegime.NEW:
        total_80c = Decimal("0")
        self_80d = parents_80d = prev_self = prev_parents = Decimal("0")
        parents_senior = False
        donations = None
        structured_80g = Decimal("0")
        amount_80e = amount_80g = Decimal("0")
    else:
        amount_80e = via.section80E
        amount_80g = structured_80g if donations else via.section80G

    ded_input = Chapter6ADeductions(
        amount_80c=total_80c,
        amount_80ccd1b=Decimal("0") if tax_regime == TaxRegime.NEW else via.section80CCD1B,
        amount_80ccd2=via.section80CCDEmployer,
        amount_80d_self_family=self_80d,
        amount_80d_parents=parents_80d,
        amount_80d_preventive_self=prev_self,
        amount_80d_preventive_parents=prev_parents,
        has_parents_senior=parents_senior,
        amount_80e=amount_80e,
        amount_80tta=(
            min(interest_sb, Decimal("10000"))
            if tax_regime == TaxRegime.OLD
            else Decimal("0")
        ),
        amount_80ttb=Decimal("0") if tax_regime == TaxRegime.NEW else via.section80TTB,
        amount_80g=amount_80g,
        donations_80g=donations or None,
    )
    return ded_input, structured_80g


# ---------------------------------------------------------------------------
# Capital Gains (112A only for ITR-1)
# ---------------------------------------------------------------------------

def _map_capital_gains(draft: ReturnDraft) -> CapitalGainsIncome | None:
    """Map the capital-gains schedule to the ITR-1 ``CapitalGainsIncome``.

    ITR-1 permits LTCG u/s 112A only. The canonical draft carries the raw
    ``capitalGainsSchedule`` dict; the authoritative ITR-1/ITR-4 source is
    the structured ``simplified112A`` block (sale consideration minus cost
    of acquisition, floored at 0).  A bare ``ltcg112A`` scalar is NOT
    trusted — older import paths wrote a purchase cost into it,
    fabricating a fake gain that blocked ITR-1 with
    "LTCG u/s 112A of Rs 499975 exceeds Rs 125000".  A purchase with no
    sale is never a capital gain; only a positive (sale - cost) is.
    Full 112A portfolio computation remains in
    ``app.engine.schedules.restricted_112a`` (invoked by the Phase 2
    compute endpoint when canonical transaction evidence is present).
    """
    sched = draft.capitalGainsSchedule or {}
    simplified = sched.get("simplified112A") or {}
    if simplified:
        sale = Decimal(str(simplified.get("totalSaleConsideration", 0) or 0))
        cost = Decimal(str(simplified.get("totalCostAcquisition", 0) or 0))
        ltcg_112a = max(Decimal("0"), sale - cost)
    else:
        ltcg_112a = Decimal("0")
    return CapitalGainsIncome(ltcg_112a=ltcg_112a)


# ---------------------------------------------------------------------------
# TDS / TCS / Tax Payments
# ---------------------------------------------------------------------------

_SALARY_SECTIONS = {"192", "S192"}
import re as _re
_TAN_PATTERN = _re.compile(r"^[A-Z]{4}[0-9]{5}[A-Z]$")


def _map_tds(tds_rows: list[TdsCredit]) -> tuple[list[TDS1Entry], list[TDS2Entry], Decimal, Decimal, Decimal, Decimal, list[dict]]:
    """Split canonical TDS rows into Schedule TDS1 (salary) and TDS2 (other).

    Returns ``(tds1, tds2, tds_salary_total, tds_interest_total,
    tds_other_total, claimed_tds_total, issues)``. Rows with an invalid
    TAN are excluded from the typed engine input (which enforces the TAN
    pattern) but remain in the editable draft; their issue is surfaced in
    ``issues`` so the caller can present it to the taxpayer — mirroring
    the flat mapper's ``row_is_valid`` guard.
    """
    tds1: list[TDS1Entry] = []
    tds2: list[TDS2Entry] = []
    tds_salary = Decimal("0")
    tds_other_total = Decimal("0")
    claimed_total = Decimal("0")
    issues: list[dict] = []
    for row in tds_rows:
        if row.claimedInReturn is False:
            continue
        tax = row.taxDeducted
        gross = row.grossAmount
        claimed_total += tax
        section = (row.section or "").strip().upper()
        tan = (row.deductorTAN or "").strip().upper()
        # Strict engine models receive only filing-valid identifiers. The
        # raw malformed value remains untouched in the editable draft and
        # is surfaced as a structured issue above.
        # Strict engine models receive only filing-valid identifiers. The
        # raw malformed value remains untouched in the editable draft and
        # is surfaced as a structured issue above.  The guard applies to
        # every emitted row (TDS1 salary *and* TDS2 non-salary) regardless
        # of the tax amount — a TDS-2 row with tax == 0 but gross > 0 still
        # reaches the typed ``TDS2Entry`` constructor, whose ``deductor_tan``
        # field enforces the TAN pattern, so an empty/malformed TAN must be
        # skipped here (and surfaced) rather than crashing Pydantic below.
        if not _TAN_PATTERN.fullmatch(tan):
            issues.append({
                "creditType": "TDS",
                "section": section,
                "code": "INVALID_TAN_FORMAT",
                "field": "deductorTAN",
                "enteredValue": tan,
                "amount": float(tax),
                "message": "TAN must contain 4 letters, 5 digits and 1 letter (e.g. ABCD12345E).",
            })
            continue
        if section in _SALARY_SECTIONS:
            tds1.append(TDS1Entry(
                employer_tan=tan,
                employer_name=row.deductorName or None,
                income_chargeable=gross,
                tds_deducted=tax,
            ))
            tds_salary += tax
        elif tax > 0 or gross > 0:
            tds2.append(TDS2Entry(
                deductor_tan=tan,
                deductor_name=row.deductorName or None,
                tds_section=section or "194A",
                gross_amount=gross,
                tds_deducted=tax,
            ))
            tds_other_total += tax
    tds_interest = sum(
        (e.tds_deducted for e in tds2 if e.tds_section in {"194A", "S194A"}),
        Decimal("0"),
    )
    return tds1, tds2, tds_salary, tds_interest, tds_other_total, claimed_total, issues


def _map_tcs(tcs_rows: list[TcsCredit]) -> tuple[list[TCSEntry], Decimal]:
    mapped: list[TCSEntry] = []
    total = Decimal("0")
    for row in tcs_rows:
        if row.claimedInReturn is False:
            continue
        collected = row.taxCollected
        gross = row.grossAmount
        if collected > 0 or gross > 0:
            mapped.append(TCSEntry(
                collector_tan=(row.collectorTAN or "").strip(),
                collector_name=row.collectorName or None,
                tcs_section=(row.tcsCreditOwner or "206C"),
                gross_amount=gross,
                tcs_collected=collected,
            ))
            total += collected
    return mapped, total


def _map_tax_payments(challans: list[TaxChallan]) -> tuple[list[TaxPaymentDetail], Decimal, Decimal, list[Decimal]]:
    """Split challans into advance + self-assessment; derive quarterly advance.

    Returns ``(sat_entries, advance_total, sat_total, quarterly_advance)``.
    """
    sat_entries: list[TaxPaymentDetail] = []
    advance_total = Decimal("0")
    sat_total = Decimal("0")
    quarterly = [Decimal("0"), Decimal("0"), Decimal("0"), Decimal("0")]
    installment_deadlines = (
        datetime.date(2025, 6, 15), datetime.date(2025, 9, 15),
        datetime.date(2025, 12, 15), datetime.date(2026, 3, 15),
    )
    fy_end = datetime.date(2026, 3, 31)
    for row in challans:
        amount = row.amount
        if amount <= 0:
            continue
        deposit_date = _to_date(row.depositDate)
        if row.kind == "ADVANCE_TAX":
            advance_total += amount
            bucket = 3
            if deposit_date is not None:
                for idx, deadline in enumerate(installment_deadlines):
                    if deposit_date <= deadline:
                        bucket = idx
                        break
            quarterly[bucket] += amount
        elif row.kind == "SELF_ASSESSMENT":
            # A SAT row dated on/before FY-end is reclassified as advance tax
            # (mirrors the flat mapper's RECLASSIFIED_AS_ADVANCE_TAX logic).
            if deposit_date is not None and deposit_date <= fy_end:
                advance_total += amount
                bucket = 3
                for idx, deadline in enumerate(installment_deadlines):
                    if deposit_date <= deadline:
                        bucket = idx
                        break
                quarterly[bucket] += amount
            else:
                sat_total += amount
                sat_entries.append(TaxPaymentDetail(
                    amount=amount,
                    payment_type="self_assessment",
                    payment_date=deposit_date,
                    bsr_code=(row.bsrCode or "").strip(),
                    challan_serial_number=str(row.challanSerialNo or "").strip(),
                ))
    return sat_entries, advance_total, sat_total, quarterly


_BANK_TYPE_MAP = {
    "SB": BankAccountType("savings"),
    "CA": BankAccountType("current"),
    "CC": BankAccountType("cash_credit"),
    "OD": BankAccountType("overdraft"),
    "NRO": BankAccountType("nro"),
    "OTH": BankAccountType("savings"),  # default unknown → savings
}


def _map_bank_accounts(banks: list[DraftBankAccount]) -> list[BankAccount]:
    mapped: list[BankAccount] = []
    for idx, b in enumerate(banks):
        # ``is_primary`` follows the explicit ``useForRefund`` flag only —
        # ``build_itr1_json`` enforces "exactly one primary" so a defaulting
        # fallback here would mask that validation.  The first account is no
        # longer auto-primary when the flag is unset.
        mapped.append(BankAccount(
            bank_name=b.bankName or None,
            account_number=b.accountNumber or None,
            ifsc_code=b.ifscCode or None,
            account_type=_BANK_TYPE_MAP.get(b.accountType, BankAccountType("savings")),
            is_primary=b.useForRefund,
        ))
    return mapped


def _map_dividend_quarterly_breakdown(draft: ReturnDraft) -> dict[str, Decimal]:
    """Aggregate the five statutory dividend periods from canonical rows.

    The canonical draft stores the periods per dividend row.  Importers that
    do not have a reliable receipt/accrual date leave these values at zero;
    this mapper must preserve genuine user-entered or source-backed values
    rather than inventing a breakup from aggregate dividend income.
    """
    dividends = draft.otherSources.dividends
    if not dividends:
        return {}
    return {
        "Q1": sum((row.q1 for row in dividends), Decimal("0")),
        "Q2": sum((row.q2 for row in dividends), Decimal("0")),
        "Q3": sum((row.q3 for row in dividends), Decimal("0")),
        "Q4": sum((row.q4 for row in dividends), Decimal("0")),
        "Q5": sum((row.q5 for row in dividends), Decimal("0")),
    }


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def draft_to_itr1_input(draft: ReturnDraft) -> tuple[Any, dict[str, Any]]:
    """Map a canonical ``ReturnDraft`` → ``ITR1Input`` for compute + CBDT.

    Args:
        draft: The canonical typed draft (``app.schemas.return_draft``).

    Returns:
        ``(itr1_input, breakdown)`` where ``breakdown`` carries the
        intermediate totals the compute response needs (section_17_1,
        gross_salary, total_interest, total_dividend, family_pension,
        total_winnings, tds_salary, tds_interest, tds_other, claimed_tds,
        advance_tax, self_assessment_tax, quarterly_advance).

    Raises:
        DraftMappingError: If the draft carries income outside ITR-1 scope
            (e.g. lottery winnings) or a required field is missing.
    """
    tax_regime = TaxRegime.OLD if draft.regime == "old" else TaxRegime.NEW
    age_bracket = _age_bracket_from_dob(draft.personal.dateOfBirth)

    salary_input, section_17_1, gross_salary = _map_salary(draft.employers)
    hp_input, hp_inputs = _map_house_properties(draft.houseProperties)
    os_input, total_interest, total_dividend, family_pension, total_winnings = _map_other_sources(draft)
    ded_input, structured_80g = _map_deductions(draft, tax_regime)
    cg_input = _map_capital_gains(draft)

    tds1, tds2, tds_salary, tds_interest, tds_other, claimed_tds, tds_issues = _map_tds(draft.taxes.tds)
    tcs_entries, total_tcs = _map_tcs(draft.taxes.tcs)
    sat_entries, advance_tax, sat_total, quarterly = _map_tax_payments(draft.taxes.challans)
    bank_accounts = _map_bank_accounts(draft.bankAccounts)

    itr1_input = ITR1Input(
        age_bracket=age_bracket,
        tax_regime=tax_regime,
        salary_income=salary_input,
        house_property_income=hp_input,
        house_properties=hp_inputs,
        other_sources_income=os_input,
        deductions_chapter6a=ded_input,
        capital_gains=cg_input,
        cg_transactions=None,
        tds1_entries=tds1 or None,
        tds2_entries=tds2 or None,
        tcs_entries=tcs_entries or None,
        advance_tax_paid=advance_tax,
        self_assessment_tax_paid=sat_total,
        advance_tax_q1=quarterly[0],
        advance_tax_q2=quarterly[1],
        advance_tax_q3=quarterly[2],
        advance_tax_q4=quarterly[3],
        assessee_type=AssesseeType.INDIVIDUAL,
        is_resident=True,
        is_director=False,
        has_foreign_assets=False,
        has_unlisted_equity=False,
        nature_of_employment=(draft.employers[0].natureOfEmployment or None) if draft.employers else None,
        house_property_count=max(1, len(draft.houseProperties)),
        relief_89=Decimal("0"),
        agriculture_income=draft.exemptIncome.grossAgriculturalReceipts,
        filing_section=draft.filing.filingSection,
        original_filing_section=None,
        form_10e_filed=False,
        form_10ia_filed=False,
        form_10ba_filed=False,
        pran_number=draft.deductions.chapterVIA.pranNumber or None,
        disease_category=None,
        agniveer_date_of_joining=None,
        date_of_incorporation=None,
        assessee_pan=draft.personal.pan or None,
        assessee_email_primary=draft.personal.email or None,
        assessee_phone_primary=draft.personal.mobile or None,
        representative_email=None,
        representative_phone=None,
        exempt_income_breakdown={},
        exempt_income_dropdowns=[],
        total_exempt_income=None,
        other_sources_dropdowns=[],
        other_sources_total=None,
        dividend_quarterly_breakdown=_map_dividend_quarterly_breakdown(draft),
        full_value_of_consideration=None,
        schedule_80d=None,
        schedule_80g=None,
        schedule_80gga=None,
        schedule_80ggc=None,
        schedule_80dd=None,
        schedule_80u=None,
        schedule_80c_entries=[],
        schedule_80ccc_entries=[],
        schedule_80e_entries=[],
        loan_details_80ee_list=[],
        loan_details_80eea_list=[],
        loan_details_80eeb_list=[],
        property_stamp_duty_value_80eea=None,
        loan_details_24b_list=[],
        tax_payment_entries=sat_entries,
        bank_accounts=bank_accounts,
        hra_details=None,
        schedule_10_13a=None,
        loan_details_80ee=None,
        loan_details_80eea=None,
        loan_details_80eeb=None,
        is_property_co_owned=False,
        other_co_owner_percentage=Decimal("0"),
        co_ownership_details=None,
        representative_details=None,
        secondary_address=None,
        tds3_entries=None,
        total_taxes_paid=None,
        total_tds_claimed=claimed_tds,
        total_tcs_claimed=total_tcs,
        schedule_it_total_paid=None,
        schedule_tds1_total=tds_salary,
        schedule_tds2_total_claimed=tds_other,
        schedule_tds3_total_claimed=None,
        schedule_tcs_total_claimed=total_tcs,
        filing_profile=None,  # Phase 2: constructed by filing_gateway_v2.
        property_profile=None,
        property_profiles=[],
        tax_return_preparer=None,
    )

    breakdown = {
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
    }
    return itr1_input, breakdown
