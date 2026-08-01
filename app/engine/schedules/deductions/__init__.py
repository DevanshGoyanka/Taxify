"""Chapter VI-A deduction schedules. Each module exposes a compute() function."""

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional
from app.schemas.itr1 import Chapter6ADeductions, AgeBracket, TaxRegime, OtherSourcesIncome
from app.engine.schedules.deductions import (
    section_80c,
    section_80ccd1b,
    section_80ccd2,
    section_80cch,
    section_80d,
    section_80dd,
    section_80ddb,
    section_80u,
    section_80tta,
    section_80ttb,
    section_80e,
    section_80ee,
    section_80eea,
    section_80eeb,
    section_80g,
    section_80gg,
    section_80gga,
    section_80ggc,
    section_80ia,
    section_80ib,
    section_80ic,
    section_10aa,
    section_80ra,
)


@dataclass
class DeductionResult:
    total: Decimal = Decimal("0")
    breakdown: dict = None

    def __post_init__(self):
        if self.breakdown is None:
            self.breakdown = {}


def _cap_breakdown_to_gti(result: DeductionResult, gti: Decimal) -> None:
    """Normalize component keys and allocate the GTI cap across deductions."""
    combined_key = "80C+80CCC+80CCD(1)"
    combined = result.breakdown.get(combined_key, Decimal("0"))
    amount_80ccc = result.breakdown.get("80CCC", Decimal("0"))
    amount_80ccd1 = result.breakdown.get("80CCD(1)", Decimal("0"))
    normalized: dict[str, Decimal] = {}
    for key, amount in result.breakdown.items():
        if key == combined_key:
            amount_80c = max(Decimal("0"), combined - amount_80ccc - amount_80ccd1)
            if amount_80c > 0:
                normalized["80C"] = amount_80c
            continue
        if key in {"80CCC", "80CCD(1)"}:
            if amount > 0:
                normalized[key] = amount
            continue
        normalized[key] = amount

    remaining = max(Decimal("0"), gti)
    capped: dict[str, Decimal] = {}
    for key, amount in normalized.items():
        allowed = min(amount, remaining)
        if allowed > 0:
            capped[key] = allowed
            remaining -= allowed
        if remaining <= 0:
            break
    result.breakdown = capped
    result.total = sum(capped.values(), Decimal("0"))


def compute_all(
    ded: Optional[Chapter6ADeductions],
    gti: Decimal,
    age_bracket: AgeBracket,
    regime: TaxRegime,
    os_input: Optional[OtherSourcesIncome],
    *,
    cg_112a_income: Decimal = Decimal("0"),
    cg_111a_income: Decimal = Decimal("0"),
    is_parents_senior: bool = False,
    is_80dd_severe: bool = False,
    is_80u_severe: bool = False,
    hra_exempt_amount: Decimal = Decimal("0"),
) -> DeductionResult:
    """Compute all applicable Chapter VI-A deductions and return total + breakdown.

    ``cg_112a_income`` and ``cg_111a_income`` are the taxable portions of those CG
    categories.  They are excluded from adjusted GTI for 80G/80GG per CBDT rules.

    ``hra_exempt_amount`` is used to determine 80GG eligibility (80GG is not
    available when HRA exemption is claimed under s.10(13A)).
    """
    if not ded or gti <= 0:
        return DeductionResult()

    result = DeductionResult()

    def _add(key: str, val: Decimal, allow_new_regime: bool = False):
        if val > 0 and (regime == TaxRegime.OLD or allow_new_regime):
            result.breakdown[key] = val

    # --- Sections allowed in BOTH regimes ---
    r_80ccd2 = section_80ccd2.compute(ded, regime)
    _add("80CCD(2)", r_80ccd2, allow_new_regime=True)

    r_80cch = section_80cch.compute(ded, regime)
    _add("80CCH", r_80cch, allow_new_regime=True)

    if regime == TaxRegime.NEW:
        result.total = min(r_80ccd2 + r_80cch, gti)
        if result.total < r_80ccd2 + r_80cch:
            _cap_breakdown_to_gti(result, gti)
        return result

    # --- Old regime only deductions ---
    r_80c = section_80c.compute(ded, regime)
    _add("80C+80CCC+80CCD(1)", r_80c)
    # Store 80CCC and 80CCD(1) individually for ITD JSON line-item breakout.
    r_80ccc = section_80c.compute_80ccc(ded, regime)
    _add("80CCC", r_80ccc)
    r_80ccd1 = section_80c.compute_80ccd1(ded, regime)
    _add("80CCD(1)", r_80ccd1)

    r_80ccd1b = section_80ccd1b.compute(ded, regime)
    _add("80CCD(1B)", r_80ccd1b)

    r_80d = section_80d.compute(ded, age_bracket, regime, is_parents_senior=is_parents_senior)
    _add("80D", r_80d)

    r_80dd = section_80dd.compute(ded, regime, is_severe=is_80dd_severe)
    _add("80DD", r_80dd)

    r_80ddb = section_80ddb.compute(ded, age_bracket, regime)
    _add("80DDB", r_80ddb)

    r_80u = section_80u.compute(ded, regime, is_severe=is_80u_severe)
    _add("80U", r_80u)

    r_80tta = section_80tta.compute(ded, os_input, age_bracket, regime)
    _add("80TTA", r_80tta)

    r_80ttb = section_80ttb.compute(ded, os_input, age_bracket, regime)
    _add("80TTB", r_80ttb)

    r_80e = section_80e.compute(ded, regime)
    _add("80E", r_80e)

    r_80ee = section_80ee.compute(ded, regime)
    _add("80EE", r_80ee)

    r_80eea = section_80eea.compute(ded, regime)
    _add("80EEA", r_80eea)

    r_80eeb = section_80eeb.compute(ded, regime)
    _add("80EEB", r_80eeb)

    # --- Business-specific deductions (ITR-3 only, old regime) ---
    r_80ia = section_80ia.compute(ded, regime)
    _add("80-IA", r_80ia, allow_new_regime=True)

    r_80ib = section_80ib.compute(ded, regime)
    _add("80-IB", r_80ib, allow_new_regime=True)

    r_80ic = section_80ic.compute(ded, regime)
    _add("80-IC", r_80ic, allow_new_regime=True)

    r_10aa = section_10aa.compute(ded, regime)
    _add("10AA", r_10aa, allow_new_regime=True)

    r_80ra = section_80ra.compute(ded, regime)
    _add("80RA", r_80ra, allow_new_regime=True)

    deductions_before_80g = (
        r_80c + r_80ccd1b + r_80ccd2 + r_80cch
        + r_80d + r_80dd + r_80ddb + r_80u
        + r_80tta + r_80ttb + r_80e + r_80ee + r_80eea + r_80eeb
        + r_80ia + r_80ib + r_80ic + r_10aa + r_80ra
    )
    # Per CBDT: adjusted GTI for 80G/80GG excludes LTCG 112A and STCG 111A
    adjusted_gti = max(Decimal("0"), gti - deductions_before_80g - cg_112a_income - cg_111a_income)

    r_80g = section_80g.compute(ded, adjusted_gti, regime)
    _add("80G", r_80g)

    r_80gg = section_80gg.compute(ded, adjusted_gti, regime, hra_exempt_amount=hra_exempt_amount)
    _add("80GG", r_80gg)

    r_80gga = section_80gga.compute(ded, regime)
    _add("80GGA", r_80gga)

    r_80ggc = section_80ggc.compute(ded, regime)
    _add("80GGC", r_80ggc)

    total = deductions_before_80g + r_80g + r_80gg + r_80gga + r_80ggc
    result.total = min(total, gti)
    if result.total < total:
        _cap_breakdown_to_gti(result, gti)
    return result
