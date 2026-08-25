"""Alternate Minimum Tax computation under sections 115JC and 115JD."""

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Iterable, Mapping

from app.engine.common.cess import compute as compute_cess
from app.engine.common.surcharge import compute as compute_surcharge

AMT_RATE: Decimal = Decimal("0.185")
AMT_INCOME_THRESHOLD: Decimal = Decimal("2000000")
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
    )
