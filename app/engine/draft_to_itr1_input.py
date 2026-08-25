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

from app.engine.common.due_dates import resolve_filing_dates
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
    DependentRelationship,
    DisabilityCategory,
    DisabilitySeverity,
    Donation80GGA,
    Donation80G as ITR1Donation80G,
    Donation80GCategory,
    DonationAddress,
    HousePropertyIncome,
    HRADetails,
    InsurancePolicy,
    ITR1Schedule80EEALoanEntry,
    ITR1Schedule80EEBLoanEntry,
    ITR1Schedule80EELoanEntry,
    ITR1Input,
    LoanDetail,
    OtherSourcesIncome,
    OtherSourceDetail,
    PropertyType,
    SalaryIncome,
    Schedule80CCCEntry,
    Schedule80D,
    Schedule80DD,
    Schedule80EEntry,
    Schedule80G,
    Schedule80GGA,
    Schedule80GGC,
    Schedule80U,
    PoliticalContribution,
    TDS1Entry,
    TDS2Entry,
    TDS3Entry,
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
        annual_rent_received=prop.annualLettingValue if prop.annualLettingValue > 0 else (
            prop.annualRent if prop.annualRent > 0 else prop.maxRent
        ),
        rent_not_realized=prop.unrealizedRent,
        ownership_share_percentage=(
            prop.ownershipShare if prop.isCoOwned else Decimal("100")
        ),
        municipal_taxes_paid=prop.municipalTaxesPaid,
        home_loan_interest_paid=loan_interest,
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


def _map_24b_loans(properties: list[HouseProperty]) -> list[LoanDetail]:
    """Map canonical home-loan evidence to official Schedule 24(b) rows."""
    rows: list[LoanDetail] = []
    for property_sequence_no, prop in enumerate(properties, start=1):
        property_type = _HP_TYPE_MAP.get(prop.propertyType, PropertyType.LET_OUT)
        for loan in prop.homeLoans:
            rows.append(LoanDetail(
                property_sequence_no=property_sequence_no,
                loan_taken_from=loan.lenderType,
                lender_name=loan.lenderName,
                loan_amount=loan.totalLoanAmount,
                sanction_date=_to_date(loan.dateOfLoan),
                account_or_reference_number=loan.loanAccountNo,
                outstanding_loan_amount=loan.loanOutstandingAmount,
                interest_paid_self_occupied=(
                    loan.interestUs24B
                    if property_type == PropertyType.SELF_OCCUPIED
                    else Decimal("0")
                ),
                interest_paid_let_out=(
                    loan.interestUs24B
                    if property_type != PropertyType.SELF_OCCUPIED
                    else Decimal("0")
                ),
            ))
    return rows


# ---------------------------------------------------------------------------
# Other Sources
# ---------------------------------------------------------------------------

_INTEREST_NATURES = {
    "SAVINGS_BANK": "SAV",
    "TERM_DEPOSIT": "IFD",
    "POST_OFFICE": "IFD",
    "SCSS": "IFD",
    "IT_REFUND": "TAX",
    "PF_10_11_FIRST": "10(11)(iP)",
    "PF_10_11_SECOND": "10(11)(iiP)",
    "PF_10_12_FIRST": "10(12)(iP)",
    "PF_10_12_SECOND": "10(12)(iiP)",
    "NSC": "OTH",
    "BONDS": "OTH",
    "SECURITIES": "OTH",
    "OTHER": "OTH",
}
_SAVINGS_KINDS = {"SAVINGS_BANK", "POST_OFFICE"}

_OTHER_INTEREST_DESCRIPTIONS = {
    "NSC": "NSC accrued interest",
    "BONDS": "Interest on bonds or debentures",
    "SECURITIES": "Interest on securities",
    "OTHER": "Other interest income",
}


def _map_other_sources(draft: ReturnDraft) -> tuple[OtherSourcesIncome, Decimal, Decimal, Decimal, Decimal]:
    """Map canonical OS rows → ``OtherSourcesIncome`` + breakdown totals.

    Returns ``(os_input, total_interest, total_dividend, family_pension,
    total_winnings)``.
    """
    interest: list[InterestIncome] = draft.otherSources.interest
    interest_sb = sum(
        (i.grossAmount for i in interest if i.kind == "SAVINGS_BANK"),
        Decimal("0"),
    )
    interest_fd = sum(
        (
            i.grossAmount for i in interest
            if i.kind in {"TERM_DEPOSIT", "POST_OFFICE", "SCSS"}
        ),
        Decimal("0"),
    )
    interest_on_it_refund = sum(
        (i.grossAmount for i in interest if i.kind == "IT_REFUND"),
        Decimal("0"),
    )
    other_interest = sum(
        (
            i.grossAmount for i in interest
            if _INTEREST_NATURES.get(i.kind) not in {"SAV", "IFD", "TAX"}
        ),
        Decimal("0"),
    )
    total_interest = sum((i.grossAmount for i in interest), Decimal("0"))

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
    if (total_winnings > 0 or draft.otherSources.gifts) and draft.form in {"ITR-1", "ITR-4"}:
        raise DraftMappingError(
            "Lottery, gaming, horse-race winnings, and taxable gifts are outside ITR-1/ITR-4; "
            "use ITR-2/ITR-3."
        )

    detail_amounts: dict[str, Decimal] = {}
    other_descriptions: list[str] = []

    def add_detail(nature: str, amount: Decimal, description: str = "") -> None:
        if amount <= 0:
            return
        detail_amounts[nature] = detail_amounts.get(nature, Decimal("0")) + amount
        if nature == "OTH" and description and description not in other_descriptions:
            other_descriptions.append(description)

    for row in interest:
        nature = _INTEREST_NATURES.get(row.kind, "OTH")
        description = row.remarks or _OTHER_INTEREST_DESCRIPTIONS.get(row.kind, "")
        add_detail(nature, row.grossAmount, description)
    add_detail("FAP", family_pension)
    add_detail("DIV", total_dividend)
    for row in draft.otherSources.otherIncome:
        add_detail("OTH", row.amount, row.description or row.nature.replace("_", " ").title())

    source_details = [
        OtherSourceDetail(
            nature=nature,
            amount=amount,
            other_description=(
                "; ".join(other_descriptions)[:125] or "Other income"
                if nature == "OTH" else None
            ),
        )
        for nature, amount in detail_amounts.items()
    ]

    os_input = OtherSourcesIncome(
        savings_bank_interest=interest_sb,
        fixed_deposit_interest=interest_fd,
        family_pension_received=family_pension,
        dividend_income=total_dividend,
        interest_on_it_refund=interest_on_it_refund,
        other_income=(
            other_interest
            + sum((row.amount for row in draft.otherSources.otherIncome), Decimal("0"))
        ),
        source_details=source_details,
    )
    return os_input, total_interest, total_dividend, family_pension, total_winnings


# ---------------------------------------------------------------------------
# Deductions
# ---------------------------------------------------------------------------

def _map_80c(investments: list[Investment80C]) -> Decimal:
    return sum((i.amount for i in investments), Decimal("0"))


def _map_80c_entries(investments: list[Investment80C]) -> list:
    """Map canonical 80C investments → official ``Schedule80CEntry`` rows.

    The CBDT Category A validator requires at least one detail row with an
    identifier number whenever an 80C deduction is claimed. Each canonical
    ``Investment80C`` carries ``identificationNo``/``accountOrPolicyNo`` +
    ``amount`` — these map directly to the official row's
    ``identifier_number``/``payment_type``/``amount``.
    """
    from app.schemas.itr1 import Schedule80CEntry
    entries: list = []
    for inv in investments:
        entries.append(Schedule80CEntry(
            amount=inv.amount,
            payment_type=(inv.accountOrPolicyNo or inv.investmentType or None),
            identifier_number=(inv.identificationNo or None),
        ))
    return entries


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
            total_donation=row.donationAmtCash + row.donationAmtOtherMode,
        ))
    total = sum((d.cash_amount + d.non_cash_amount for d in mapped), Decimal("0"))
    return mapped, total


def _map_80d_schedule(section: Section80D) -> Schedule80D:
    """Preserve policy-level 80D evidence with its official bucket code."""
    self_is_senior = section.selfSeniorCitizen in {"Y", "S"}
    parents_are_senior = section.parentsSeniorCitizen in {"Y", "P"}
    buckets = (
        ("1b" if self_is_senior else "1a", getattr(section, "selfFamilySenior" if self_is_senior else "selfFamily")),
        ("2b" if parents_are_senior else "2a", getattr(section, "parentsSenior" if parents_are_senior else "parents")),
    )
    policies = [
        InsurancePolicy(
            section=code,
            premium_paid=policy.premiumAmount,
            insurer_name=policy.insurerName or None,
            policy_number=policy.policyNo or None,
        )
        for code, category in buckets
        for policy in category.policies
        if policy.premiumAmount > 0
    ]
    return Schedule80D(
        has_self_senior=self_is_senior,
        has_parents_senior=parents_are_senior,
        not_claiming_self=section.selfSeniorCitizen == "S",
        not_claiming_parents=section.parentsSeniorCitizen == "P",
        premium_1a_non_senior=(
            sum((p.premiumAmount for p in section.selfFamily.policies), Decimal("0"))
            if not self_is_senior else Decimal("0")
        ),
        premium_1b_senior=(
            sum((p.premiumAmount for p in section.selfFamilySenior.policies), Decimal("0"))
            if self_is_senior else Decimal("0")
        ),
        premium_2a_parents_non_senior=(
            sum((p.premiumAmount for p in section.parents.policies), Decimal("0"))
            if not parents_are_senior else Decimal("0")
        ),
        premium_2b_parents_senior=(
            sum((p.premiumAmount for p in section.parentsSenior.policies), Decimal("0"))
            if parents_are_senior else Decimal("0")
        ),
        preventive_checkup_self=getattr(section, "selfFamilySenior" if self_is_senior else "selfFamily").preventiveCheckup,
        preventive_checkup_parents=getattr(section, "parentsSenior" if parents_are_senior else "parents").preventiveCheckup,
        medical_expense_self_senior=(
            section.selfFamilySenior.medicalExpense if self_is_senior else Decimal("0")
        ),
        medical_expense_parents_senior=(
            section.parentsSenior.medicalExpense if parents_are_senior else Decimal("0")
        ),
        policies=policies,
    )


def _map_80gga(draft: ReturnDraft) -> Schedule80GGA | None:
    rows = [
        Donation80GGA(
            relevant_clause=row.relevantClause,
            donee_name=row.doneeName,
            donee_pan=row.doneePAN,
            address=DonationAddress(
                address_line=row.addressLine,
                city_or_district=row.city,
                state_code=row.stateCode,
                pin_code=int(row.pinCode or 0),
            ),
            cash_amount=row.cashAmount,
            other_mode_amount=row.otherModeAmount,
        )
        for row in draft.deductions.schedule80GGA
    ]
    return Schedule80GGA(donations=rows) if rows else None


def _map_80ggc(draft: ReturnDraft) -> Schedule80GGC | None:
    rows = [
        PoliticalContribution(
            cash_amount=row.cashAmount,
            other_mode_amount=row.otherModeAmount,
            contribution_date=_to_date(row.contributionDate),
            transaction_ref=row.transactionRef or None,
            ifsc_code=row.ifscCode or None,
            political_party_name=row.politicalPartyName or None,
            political_party_pan=row.politicalPartyPAN or None,
        )
        for row in draft.deductions.schedule80GGC
    ]
    return Schedule80GGC(contributions=rows) if rows else None


_DISABILITY_TYPE_MAP = {
    "1": DisabilityCategory.AUTISM_CEREBRAL_PALSY_OR_MULTIPLE,
    "2": DisabilityCategory.OTHER,
}
_DISABILITY_SEVERITY_MAP = {
    "1": DisabilitySeverity.NORMAL,
    "2": DisabilitySeverity.SEVERE,
}
_DEPENDENT_MAP = {
    "1": DependentRelationship.SPOUSE,
    "2": DependentRelationship.SON,
    "3": DependentRelationship.DAUGHTER,
    "4": DependentRelationship.FATHER,
    "5": DependentRelationship.MOTHER,
    "6": DependentRelationship.BROTHER,
    "7": DependentRelationship.SISTER,
    "8": DependentRelationship.MEMBER_OF_HUF,
}


def _map_disability_schedules(via: ChapterVIA) -> tuple[Schedule80DD | None, Schedule80U | None]:
    schedule_80dd = None
    if via.section80DD > 0:
        schedule_80dd = Schedule80DD(
            disability_type=_DISABILITY_SEVERITY_MAP.get(via.section80DDNatureOfDisability, DisabilitySeverity.NORMAL),
            disability_category=_DISABILITY_TYPE_MAP.get(via.section80DDTypeOfDisability, DisabilityCategory.OTHER),
            deduction_amount=via.section80DD,
            dependent_relationship=_DEPENDENT_MAP.get(via.section80DDDependentType),
            dependent_pan=via.section80DDDependentPAN or None,
            dependent_aadhaar=via.section80DDDependentAadhaar or None,
            form_10ia_ack_number=via.section80DDForm10IA.acknowledgementNumber or None,
            udid_number=via.section80DDUDIDNumber or None,
        )
    schedule_80u = None
    if via.section80U > 0:
        schedule_80u = Schedule80U(
            disability_type=_DISABILITY_SEVERITY_MAP.get(via.section80UNatureOfDisability, DisabilitySeverity.NORMAL),
            disability_category=_DISABILITY_TYPE_MAP.get(via.section80UTypeOfDisability, DisabilityCategory.OTHER),
            deduction_amount=via.section80U,
            form_10ia_ack_number=via.section80UForm10IA.acknowledgementNumber or None,
            udid_number=via.section80UUDIDNumber or None,
        )
    return schedule_80dd, schedule_80u


def _map_deduction_loans(draft: ReturnDraft) -> tuple[list, list, list, list]:
    rows: dict[str, list] = {"80E": [], "80EE": [], "80EEA": [], "80EEB": []}
    classes = {
        "80E": Schedule80EEntry,
        "80EE": ITR1Schedule80EELoanEntry,
        "80EEA": ITR1Schedule80EEALoanEntry,
        "80EEB": ITR1Schedule80EEBLoanEntry,
    }
    for loan in draft.deductions.loans.loans:
        payload = dict(
            loan_taken_from=loan.loanTakenFrom,
            lender_name=loan.lenderName,
            account_or_reference_number=loan.loanAccountNo,
            loan_date=_to_date(loan.dateOfLoan),
            total_loan_amount=loan.totalLoanAmount,
            outstanding_loan_amount=loan.outstandingAmount,
            interest_paid=loan.interestAmount,
        )
        if loan.section == "80EEB":
            payload["vehicle_registration_number"] = loan.vehicleRegNo
        rows[loan.section].append(classes[loan.section](**payload))
    return rows["80E"], rows["80EE"], rows["80EEA"], rows["80EEB"]


def _map_hra_details(employers: list[Employer]) -> HRADetails | None:
    relevant = [e for e in employers if e.hra > 0 or e.rentPaid > 0]
    if not relevant:
        return None
    if len({e.isMetroCity for e in relevant}) > 1:
        raise DraftMappingError(
            "A single CBDT Schedule 10(13A) cannot represent mixed metro and "
            "non-metro HRA evidence; split the return data into one consistent "
            "place-of-work classification."
        )
    return HRADetails(
        actual_hra_received=sum((e.hra for e in relevant), Decimal("0")),
        rent_paid=sum((e.rentPaid for e in relevant), Decimal("0")),
        salary_for_hra=sum((e.basic for e in relevant), Decimal("0")),
        dearness_allowance=sum((e.da for e in relevant), Decimal("0")),
        is_metro_city=all(e.isMetroCity for e in relevant),
    )


def _map_deductions(draft: ReturnDraft, tax_regime: TaxRegime) -> tuple[Chapter6ADeductions, Decimal, list]:
    """Map canonical deductions → compute input, total 80G, and Schedule 80C."""
    total_80c = _map_80c(draft.deductions.section80C)
    schedule_80c_entries = _map_80c_entries(draft.deductions.section80C)
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
        schedule_80c_entries = []
        self_80d = parents_80d = prev_self = prev_parents = Decimal("0")
        parents_senior = False
        donations = None
        structured_80g = Decimal("0")
        amount_80e = amount_80g = Decimal("0")
        amount_80ccc = amount_80ccd1 = Decimal("0")
        amount_80dd = amount_80ddb = amount_80u = Decimal("0")
        amount_80ee = amount_80eea = amount_80eeb = Decimal("0")
        amount_80gg = amount_80gga = amount_80ggc = Decimal("0")
        details_80ddb = None
    else:
        loan_interest = {
            section: sum(
                (
                    loan.interestAmount
                    for loan in draft.deductions.loans.loans
                    if loan.section == section
                ),
                Decimal("0"),
            )
            for section in ("80E", "80EE", "80EEA", "80EEB")
        }
        amount_80e = via.section80E or loan_interest["80E"]
        amount_80g = (
            via.section80G
            if via.section80G > 0
            else structured_80g
        )
        amount_80ccc = via.section80CCC
        amount_80ccd1 = via.section80CCDEmployeeOrSE
        amount_80dd = via.section80DD
        amount_80ddb = via.section80DDB
        amount_80u = via.section80U
        amount_80ee = via.section80EE or loan_interest["80EE"]
        amount_80eea = via.section80EEA or loan_interest["80EEA"]
        amount_80eeb = via.section80EEB or loan_interest["80EEB"]
        amount_80gg = via.section80GG
        amount_80gga = via.section80GGA or sum(
            (row.otherModeAmount for row in draft.deductions.schedule80GGA),
            Decimal("0"),
        )
        amount_80ggc = via.section80GGC or sum(
            (row.otherModeAmount for row in draft.deductions.schedule80GGC),
            Decimal("0"),
        )
        details_80ddb = None
        if via.section80DDB > 0 and via.section80DDBUserType and via.section80DDBNameOfSpecDisease:
            from app.schemas.itr1 import Section80DDBDetails
            details_80ddb = Section80DDBDetails(
                user_type=via.section80DDBUserType,
                disease=via.section80DDBNameOfSpecDisease,
            )

    ded_input = Chapter6ADeductions(
        amount_80c=total_80c,
        amount_80ccc=amount_80ccc,
        amount_80ccd1=amount_80ccd1,
        amount_80ccd1b=Decimal("0") if tax_regime == TaxRegime.NEW else via.section80CCD1B,
        amount_80ccd2=via.section80CCDEmployer,
        amount_80cch=via.anyOtherSection80CCH,
        amount_80d_self_family=self_80d,
        amount_80d_parents=parents_80d,
        amount_80d_preventive_self=prev_self,
        amount_80d_preventive_parents=prev_parents,
        has_parents_senior=parents_senior,
        amount_80e=amount_80e,
        amount_80dd=amount_80dd,
        amount_80ddb=amount_80ddb,
        details_80ddb=details_80ddb,
        amount_80u=amount_80u,
        amount_80ee=amount_80ee,
        amount_80eea=amount_80eea,
        amount_80eeb=amount_80eeb,
        amount_80gg=amount_80gg,
        amount_80gga=amount_80gga,
        amount_80ggc=amount_80ggc,
        amount_80tta=Decimal("0") if tax_regime == TaxRegime.NEW else via.section80TTA,
        amount_80ttb=Decimal("0") if tax_regime == TaxRegime.NEW else via.section80TTB,
        amount_80g=amount_80g,
        donations_80g=donations or None,
    )
    return ded_input, structured_80g, schedule_80c_entries


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
        sale = Decimal("0")
        cost = Decimal("0")
        ltcg_112a = Decimal("0")
    return CapitalGainsIncome(
        ltcg_112a=ltcg_112a,
        full_value_of_consideration=sale,
        cost_of_acquisition=cost,
    )


def _map_compact_exempt_income(draft: ReturnDraft) -> list[Any]:
    """Map canonical exempt-income rows to the shared compact-form model."""
    from app.schemas.itr1 import CompactExemptIncomeEntry

    return [
        CompactExemptIncomeEntry(
            category=row.category,
            sub_category=row.subCategory,
            description=row.description or None,
            amount=row.grossAmount,
        )
        for row in draft.exemptIncome.otherExemptIncome
        if row.grossAmount > 0
    ]


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
        if row.schedule == "TDS3":
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
                tds_claimed_this_year=row.claimOutOfTotTDSOnAmtPaid or tax,
                financial_year=row.financialYear or (
                    f"{row.deductedYr}-{str(int(row.deductedYr) + 1)[-2:]}"
                    if row.deductedYr else None
                ),
                deducted_year=str(row.deductedYr) if row.deductedYr else None,
                head_of_income=(
                    row.headOfIncome if row.headOfIncome != "NA" else "OS"
                ),
                brought_forward_tds=row.broughtFwdTDSAmt,
                tds_credit_carried_forward=row.amtCarriedFwd,
            ))
            tds_other_total += tax
    tds_interest = sum(
        (e.tds_deducted for e in tds2 if e.tds_section in {"194A", "S194A"}),
        Decimal("0"),
    )
    return tds1, tds2, tds_salary, tds_interest, tds_other_total, claimed_total, issues


def _map_tds3(tds_rows: list[TdsCredit]) -> tuple[list[TDS3Entry], Decimal]:
    mapped: list[TDS3Entry] = []
    total = Decimal("0")
    for row in tds_rows:
        if row.claimedInReturn is False or row.schedule != "TDS3":
            continue
        claimed = row.tdsClaimed or row.taxDeducted
        mapped.append(TDS3Entry(
            tenant_pan=row.panOfTenant,
            tenant_name=row.nameOfTenant,
            tenant_aadhaar=row.aadhaarOfTenant or None,
            gross_receipt=row.grsRcptToTaxDeduct or row.grossAmount,
            tds_deducted=row.taxDeducted,
            tds_claimed=claimed,
            tds_section=row.tdsSectionCode or row.section,
            deducted_yr=str(row.deductedYr or "2025"),
            brought_forward_tds=row.broughtFwdTDSAmt,
            head_of_income=(
                row.headOfIncome
                if row.headOfIncome in {"HP", "BP", "OS", "EI"}
                else "OS"
            ),
            tds_credit_carried_forward=row.amtCarriedFwd,
        ))
        total += claimed
    return mapped, total


def _map_tcs(tcs_rows: list[TcsCredit]) -> tuple[list[TCSEntry], Decimal, list[dict]]:
    mapped: list[TCSEntry] = []
    total = Decimal("0")
    issues: list[dict] = []
    for row in tcs_rows:
        if row.claimedInReturn is False:
            continue
        collected = row.taxCollected
        gross = row.grossAmount
        tan = (row.collectorTAN or "").strip().upper()
        if collected > 0 or gross > 0:
            if not _TAN_PATTERN.fullmatch(tan):
                issues.append({
                    "creditType": "TCS",
                    "section": "206C",
                    "code": "INVALID_TAN_FORMAT",
                    "field": "collectorTAN",
                    "enteredValue": tan,
                })
                continue
            claimed = row.tcsClaimedAmtCollOwnHand or collected
            mapped.append(TCSEntry(
                collector_tan=tan,
                collector_name=row.collectorName or None,
                tcs_section="206C",
                gross_amount=gross,
                tcs_collected=collected,
                tcs_credit_claimed=claimed,
                financial_year=(f"{row.deductedYr}-{str(int(row.deductedYr) + 1)[-2:]}" if row.deductedYr else None),
            ))
            total += claimed
    return mapped, total, issues


def _map_tax_payments(challans: list[TaxChallan]) -> tuple[list[TaxPaymentDetail], Decimal, Decimal, list[Decimal]]:
    """Split challans into advance + self-assessment; derive quarterly advance.

    Returns ``(sat_entries, advance_total, sat_total, quarterly_advance)``.
    """
    payment_entries: list[TaxPaymentDetail] = []
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
            payment_entries.append(TaxPaymentDetail(
                amount=amount,
                payment_type="advance",
                payment_date=deposit_date,
                bsr_code=(row.bsrCode or "").strip(),
                challan_serial_number=str(row.challanSerialNo or "").strip(),
            ))
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
                payment_entries.append(TaxPaymentDetail(
                    amount=amount,
                    payment_type="self_assessment",
                    payment_date=deposit_date,
                    bsr_code=(row.bsrCode or "").strip(),
                    challan_serial_number=str(row.challanSerialNo or "").strip(),
                ))
    return payment_entries, advance_total, sat_total, quarterly


_BANK_TYPE_MAP = {
    "SB": BankAccountType("savings"),
    "CA": BankAccountType("current"),
    "CC": BankAccountType("cash_credit"),
    "OD": BankAccountType("overdraft"),
    "NRO": BankAccountType("nro"),
    "OTH": BankAccountType("other"),
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
    loan_details_24b_list = _map_24b_loans(draft.houseProperties)
    os_input, total_interest, total_dividend, family_pension, total_winnings = _map_other_sources(draft)
    ded_input, structured_80g, schedule_80c_entries = _map_deductions(draft, tax_regime)
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
    schedule_80gga = _map_80gga(draft) if tax_regime == TaxRegime.OLD else None
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

    tds1, tds2, tds_salary, tds_interest, tds_other, claimed_tds, tds_issues = _map_tds(draft.taxes.tds)
    tds3_entries, tds3_total = _map_tds3(draft.taxes.tds)
    claimed_tds += tds3_total
    tcs_entries, total_tcs, tcs_issues = _map_tcs(draft.taxes.tcs)
    tax_payment_entries, advance_tax, sat_total, quarterly = _map_tax_payments(draft.taxes.challans)
    bank_accounts = _map_bank_accounts(draft.bankAccounts)
    hra_details = _map_hra_details(draft.employers) if tax_regime == TaxRegime.OLD else None
    # Without these two the calculator skips 234A/B/C and the 234F late fee
    # outright, so a belated return was generated with the right 139(4) section
    # but a zero late-filing fee.
    filing_date, due_date = resolve_filing_dates(
        draft.form or "ITR-1",
        draft.assessmentYear or "2026-27",
        draft.verification.date,
    )

    itr1_input = ITR1Input(
        filing_date=filing_date,
        due_date=due_date,
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
        form_10ia_filed=(
            via.section80DDForm10IA.filed == "Y"
            or via.section80UForm10IA.filed == "Y"
        ),
        form_10ba_filed=bool(via.form10BAAckNum),
        form_10ba_ack_number=via.form10BAAckNum or None,
        pran_number=draft.deductions.chapterVIA.pranNumber or None,
        disease_category=None,
        agniveer_date_of_joining=None,
        date_of_incorporation=None,
        assessee_pan=draft.personal.pan or None,
        assessee_email_primary=draft.personal.email or None,
        assessee_phone_primary=draft.personal.mobile or None,
        representative_email=None,
        representative_phone=None,
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
        other_sources_total=None,
        dividend_quarterly_breakdown=_map_dividend_quarterly_breakdown(draft),
        full_value_of_consideration=(
            cg_input.full_value_of_consideration if cg_input else None
        ),
        schedule_80d=schedule_80d,
        schedule_80g=schedule_80g,
        schedule_80gga=schedule_80gga,
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
        tax_payment_entries=tax_payment_entries,
        bank_accounts=bank_accounts,
        hra_details=hra_details,
        schedule_10_13a=hra_details,
        loan_details_80ee=None,
        loan_details_80eea=None,
        loan_details_80eeb=None,
        is_property_co_owned=False,
        other_co_owner_percentage=Decimal("0"),
        co_ownership_details=None,
        representative_details=None,
        secondary_address=None,
        tds3_entries=tds3_entries or None,
        total_taxes_paid=None,
        total_tds_claimed=claimed_tds,
        total_tcs_claimed=total_tcs,
        schedule_it_total_paid=None,
        schedule_tds1_total=tds_salary,
        schedule_tds2_total_claimed=tds_other,
        schedule_tds3_total_claimed=tds3_total,
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
        "credit_validation_issues": [*tds_issues, *tcs_issues],
    }
    return itr1_input, breakdown
