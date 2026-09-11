"""Alternate Minimum Tax computation under sections 115JC and 115JD."""

from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Any, Iterable, Mapping

from app.engine.common.cess import compute as compute_cess
from app.engine.common.surcharge import compute as compute_surcharge

AMT_RATE: Decimal = Decimal("0.185")
AMT_INCOME_THRESHOLD: Decimal = Decimal("2000000")
# Section 115JD(3): brought-forward AMT credit may be carried forward and set
# off for 15 assessment years (extended from 10 by Finance Act 2022).
AMTC_MAX_CARRY_FWD_YEARS = 15
_ZERO = Decimal("0")


class AMTAdditionSection(str, Enum):
    """Supported additions used to derive adjusted total income."""

    SECTION_10AA = "10AA"
    SECTION_35AD = "35AD"
    SECTION_80IA = "80-IA"
    SECTION_80IB = "80-IB"
    SECTION_80IC = "80-IC"
    SECTION_80IE = "80-IE"


@dataclass(frozen=True)
class AMTAddition:
    """A typed adjusted-total-income addition.

    Attributes:
        section: Statutory section under which the deduction was claimed.
        amount: Non-negative amount added back to total income.
    """

    section: AMTAdditionSection
    amount: Decimal


@dataclass
class AMTResult:
    """AMT comparison and credit result, with tax totals inclusive of cess."""

    adjusted_total_income: Decimal = _ZERO
    amt_tax_before_surcharge_and_cess: Decimal = _ZERO
    amt_surcharge: Decimal = _ZERO
    amt_cess: Decimal = _ZERO
    amt_tax: Decimal = _ZERO
    regular_tax: Decimal = _ZERO
    amt_applicable: bool = False
    amt_credit: Decimal = _ZERO
    final_tax: Decimal = _ZERO
    # True whenever the section 115JC comparison was genuinely made this year
    # (qualifying addback deductions present, old regime, adjusted total
    # income above the threshold) -- independent of amt_applicable, which
    # additionally requires AMT to have actually WON the comparison. Schedule
    # AMTC's own Sl.1-3 (this year's 115JC tax vs. this year's normal-
    # provisions tax, and the resulting credit-utilization capacity) need
    # real figures every year the chapter is "in play", not just years AMT
    # binds -- False only on the early base_result return below.
    chapter_xii_ba_applicable: bool = False


def _normalize_additions(
    additions: Iterable[AMTAddition] | Mapping[str, Decimal] | None,
) -> tuple[AMTAddition, ...]:
    """Validate and normalize typed additions and legacy mappings."""
    if additions is None:
        return ()
    if isinstance(additions, Mapping):
        normalized: list[AMTAddition] = []
        for section_name, amount in additions.items():
            try:
                section = AMTAdditionSection(str(section_name))
            except ValueError as exc:
                raise ValueError(f"Unsupported AMT addition section: {section_name}") from exc
            normalized.append(AMTAddition(section=section, amount=Decimal(amount)))
        additions_iterable: Iterable[AMTAddition] = normalized
    else:
        additions_iterable = additions

    result: list[AMTAddition] = []
    for addition in additions_iterable:
        if not isinstance(addition, AMTAddition):
            raise TypeError("AMT additions must be AMTAddition instances")
        amount = Decimal(addition.amount)
        if not amount.is_finite() or amount < 0:
            raise ValueError("AMT addition amounts must be finite and non-negative")
        result.append(AMTAddition(addition.section, amount))
    return tuple(result)


def compute(
    total_income: Decimal,
    total_tax_before_cess: Decimal,
    deductions_triggers: Iterable[AMTAddition] | Mapping[str, Decimal] | None,
    regime: str,
    age_bracket: str,
    *,
    regular_tax_includes_cess: bool = True,
) -> AMTResult:
    """Compute AMT, surcharge, cess, and section 115JD credit coherently.

    Args:
        total_income: Total income after deductions.
        total_tax_before_cess: Regular-tax comparison amount. Despite its legacy
            name, existing calculators pass tax inclusive of surcharge and
            cess, so that is the default interpretation.
        deductions_triggers: Typed adjusted-income additions, or a legacy
            section-to-amount mapping.
        regime: Selected tax regime.
        age_bracket: Taxpayer age bracket for surcharge marginal relief.
        regular_tax_includes_cess: Set false only when the supplied regular-tax
            amount excludes cess; cess is then added exactly once.

    Returns:
        AMT result with comparable regular and AMT totals inclusive of cess.

    Raises:
        ValueError: If income, tax, or an addition is invalid.
        TypeError: If an iterable contains an untyped addition.
    """
    from app.schemas.itr1 import TaxRegime

    income = Decimal(total_income)
    supplied_regular_tax = Decimal(total_tax_before_cess)
    if not income.is_finite() or not supplied_regular_tax.is_finite():
        raise ValueError("Income and tax must be finite")
    income = max(_ZERO, income)
    supplied_regular_tax = max(_ZERO, supplied_regular_tax)
    regular_tax = (
        supplied_regular_tax
        if regular_tax_includes_cess
        else supplied_regular_tax + compute_cess(supplied_regular_tax)
    )

    additions = _normalize_additions(deductions_triggers)
    addition_total = sum((addition.amount for addition in additions), _ZERO)
    adjusted_income = income + addition_total
    base_result = AMTResult(
        adjusted_total_income=adjusted_income,
        regular_tax=regular_tax,
        final_tax=regular_tax,
    )
    if addition_total == 0 or regime == TaxRegime.NEW or adjusted_income <= AMT_INCOME_THRESHOLD:
        return base_result

    amt_base_tax = adjusted_income * AMT_RATE
    amt_surcharge = compute_surcharge(
        adjusted_income,
        amt_base_tax,
        regime,
        age_bracket,
    )
    amt_cess = compute_cess(amt_base_tax + amt_surcharge)
    amt_total = amt_base_tax + amt_surcharge + amt_cess
    amt_applies = amt_total > regular_tax
    return AMTResult(
        adjusted_total_income=adjusted_income,
        amt_tax_before_surcharge_and_cess=amt_base_tax,
        amt_surcharge=amt_surcharge,
        amt_cess=amt_cess,
        amt_tax=amt_total,
        regular_tax=regular_tax,
        amt_applicable=amt_applies,
        amt_credit=max(_ZERO, amt_total - regular_tax) if amt_applies else _ZERO,
        final_tax=amt_total if amt_applies else regular_tax,
        chapter_xii_ba_applicable=True,
    )


@dataclass
class AMTCEntry:
    """One brought-forward AMT credit entry and its current-year disposition."""

    assessment_year: str = ""
    brought_forward: Decimal = _ZERO
    utilised: Decimal = _ZERO
    remaining_carry_forward: Decimal = _ZERO
    expired: bool = False


@dataclass
class AMTCResult:
    """Section 115JD credit utilization against this year's utilization cap.

    Entries are ordered oldest-assessment-year-first (FIFO), matching the
    statute's own "utilize the oldest credit first" convention already used
    for ordinary carried-forward losses (app/engine/schedules/loss_setoff/
    bfla.py). ``total_utilised`` feeds the actual tax reduction; the builder
    formats the same per-entry breakdown for Schedule AMTC's own disclosure
    rows -- single source of truth, both derived from this one computation.
    """

    entries: list[AMTCEntry] = field(default_factory=list)
    total_utilised: Decimal = _ZERO
    total_remaining: Decimal = _ZERO


def _ay_start(assessment_year: str) -> int:
    """Parse the starting year from an assessment-year label, e.g. "2024-25"."""
    cleaned = assessment_year.upper().replace("AY", "").replace(" ", "")
    if not cleaned:
        return 0
    try:
        return int(cleaned.split("-")[0])
    except (TypeError, ValueError):
        return 0


def compute_amtc(credits: Iterable[Any], cap: Decimal, current_ay: str) -> AMTCResult:
    """Apply this year's AMT-credit utilization cap to brought-forward credit.

    Section 115JD(2): brought-forward credit is usable only in a year normal-
    provisions tax exceeds 115JC tax, capped at that excess (``cap``, Schedule
    AMTC Sl.3) -- never below what 115JC would have demanded even this year.
    Oldest unexpired credit is consumed first (FIFO), matching this file's
    own 15-year expiry window (section 115JD(3)) -- mirrors the identical
    oldest-first convention and expiry-window pattern already used for
    ordinary carried-forward losses (``app/engine/schedules/loss_setoff/
    bfla.py``'s ``_MAX_CARRY_FWD``/``_ay_start``).

    Args:
        credits: Brought-forward credit rows (``assessment_year``,
            ``credit_brought_forward`` attributes -- e.g. ``AMTCreditItem``).
        cap: Section 115JD(2) utilization ceiling for the current year -- the
            excess of this year's normal-provisions tax over this year's
            115JC tax, zero in a year AMT itself binds (there is no "spare"
            capacity to absorb old credit when 115JC tax is the higher one).
        current_ay: The filing assessment year, e.g. "2026-27".

    Returns:
        Oldest-first entries with each one's utilized/remaining amount
        (expired entries carry zero utilized/remaining), and the aggregate
        utilized total the calculator applies to reduce tax payable.
    """
    current_year = _ay_start(current_ay)
    remaining_capacity = max(_ZERO, Decimal(cap))
    ordered = sorted(credits, key=lambda c: _ay_start(str(getattr(c, "assessment_year", ""))))

    entries: list[AMTCEntry] = []
    total_utilised = _ZERO
    total_remaining = _ZERO
    for credit in ordered:
        ay = str(getattr(credit, "assessment_year", ""))
        brought_forward = Decimal(getattr(credit, "credit_brought_forward", _ZERO))
        loss_year = _ay_start(ay)
        expired = (
            loss_year > 0 and current_year > 0
            and current_year - loss_year > AMTC_MAX_CARRY_FWD_YEARS
        )
        if expired:
            entries.append(AMTCEntry(ay, brought_forward, _ZERO, _ZERO, expired=True))
            continue
        utilised = min(brought_forward, remaining_capacity)
        remaining_capacity -= utilised
        remaining = brought_forward - utilised
        entries.append(AMTCEntry(ay, brought_forward, utilised, remaining))
        total_utilised += utilised
        total_remaining += remaining

    return AMTCResult(entries=entries, total_utilised=total_utilised, total_remaining=total_remaining)
