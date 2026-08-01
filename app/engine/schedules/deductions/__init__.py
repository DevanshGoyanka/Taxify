"""Chapter VI-A deduction schedules. Each module exposes a compute() function."""

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional
from app.schemas.itr1 import (
    Chapter6ADeductions,
    AgeBracket,
    TaxRegime,
    OtherSourcesIncome,
    Schedule80GGA,
    Schedule80GGC,
    Schedule80DD,
    Schedule80U,
)
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
    section_details: dict = None

    def __post_init__(self):
        if self.breakdown is None:
            self.breakdown = {}
        if self.section_details is None:
            self.section_details = {}


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
    use_structured_80ddb: bool = False,
    hra_exempt_amount: Decimal = Decimal("0"),
    schedule_80gga: Optional[Schedule80GGA] = None,
    schedule_80ggc: Optional[Schedule80GGC] = None,
    assessee_pan: Optional[str] = None,
    schedule_80c_entries: Optional[list] = None,
    schedule_80e_entries: Optional[list] = None,
    loan_rows_80ee: Optional[list] = None,
    loan_rows_80eea: Optional[list] = None,
    loan_rows_80eeb: Optional[list] = None,
    property_stamp_duty_value_80eea: Optional[Decimal] = None,
    schedule_80dd: Optional[Schedule80DD] = None,
    schedule_80u: Optional[Schedule80U] = None,
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
    details_80c = section_80c.compute_details(ded, schedule_80c_entries, regime)
    result.section_details["80C"] = details_80c
    # Store 80CCC and 80CCD(1) individually for ITD JSON line-item breakout.
    r_80ccc = section_80c.compute_80ccc(ded, regime)
    _add("80CCC", r_80ccc)
    r_80ccd1 = section_80c.compute_80ccd1(ded, regime)
    _add("80CCD(1)", r_80ccd1)

    r_80ccd1b = section_80ccd1b.compute(ded, regime)
    _add("80CCD(1B)", r_80ccd1b)

    r_80d = section_80d.compute(ded, age_bracket, regime, is_parents_senior=is_parents_senior)
    _add("80D", r_80d)

    details_80dd = section_80dd.compute_details(
        ded, schedule_80dd, regime, is_severe=is_80dd_severe,
    )
    result.section_details["80DD"] = details_80dd
    r_80dd = details_80dd.allowed_deduction
    _add("80DD", r_80dd)

    details_80ddb = section_80ddb.compute_details(
        ded,
        age_bracket,
        regime,
        use_structured_details=use_structured_80ddb,
    )
    result.section_details["80DDB"] = details_80ddb
    r_80ddb = details_80ddb.allowed_deduction
    _add("80DDB", r_80ddb)

    details_80u = section_80u.compute_details(
        ded, schedule_80u, regime, is_severe=is_80u_severe,
    )
    result.section_details["80U"] = details_80u
    r_80u = details_80u.allowed_deduction
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

    # 80GG is computed first because an allowed 80GG deduction reduces the
    # adjusted GTI used by Section 80G's shared 10% qualifying ceiling.
    r_80gg = section_80gg.compute(
        ded,
        adjusted_gti,
        regime,
        hra_exempt_amount=hra_exempt_amount,
    )
    _add("80GG", r_80gg)

    adjusted_gti_80g = max(Decimal("0"), adjusted_gti - r_80gg)
    details_80g = section_80g.compute_details(ded, adjusted_gti_80g, regime)
    result.section_details["80G"] = details_80g
    r_80g = details_80g.allowed_deduction
    _add("80G", r_80g)

    consumed_before_80gga = deductions_before_80g + r_80gg + r_80g
    available_80gga = max(Decimal("0"), gti - consumed_before_80gga)
    details_80gga = section_80gga.compute_details(
        ded,
        schedule_80gga,
        available_80gga,
        regime,
    )
    result.section_details["80GGA"] = details_80gga
    r_80gga = details_80gga.allowed_deduction
    _add("80GGA", r_80gga)

    consumed_before_80ggc = consumed_before_80gga + r_80gga
    available_80ggc = max(Decimal("0"), gti - consumed_before_80ggc)
    details_80ggc = section_80ggc.compute_details(
        ded,
        schedule_80ggc,
        available_80ggc,
        regime,
        assessee_pan,
    )
    result.section_details["80GGC"] = details_80ggc
    r_80ggc = details_80ggc.allowed_deduction
    _add("80GGC", r_80ggc)

    total = deductions_before_80g + r_80g + r_80gg + r_80gga + r_80ggc
    result.total = min(total, gti)
    if result.total < total:
        _cap_breakdown_to_gti(result, gti)

    # Compute typed loan-deduction results using the GTI-capped amounts so
    # that per-row allocation lives in the dedicated modules, not the builder.
    capped_80e = result.breakdown.get("80E", Decimal("0"))
    if capped_80e > 0:
        details_80e = section_80e.compute_details(
            ded, schedule_80e_entries, capped_80e, regime,
        )
        result.section_details["80E"] = details_80e

    capped_80ee = result.breakdown.get("80EE", Decimal("0"))
    if capped_80ee > 0:
        details_80ee = section_80ee.compute_details(
            ded, loan_rows_80ee, capped_80ee, regime,
        )
        result.section_details["80EE"] = details_80ee

    capped_80eea = result.breakdown.get("80EEA", Decimal("0"))
    if capped_80eea > 0:
        details_80eea = section_80eea.compute_details(
            ded, loan_rows_80eea, capped_80eea, regime,
        )
        result.section_details["80EEA"] = details_80eea

    capped_80eeb = result.breakdown.get("80EEB", Decimal("0"))
    if capped_80eeb > 0:
        details_80eeb = section_80eeb.compute_details(
            ded, loan_rows_80eeb, capped_80eeb, regime,
        )
        result.section_details["80EEB"] = details_80eeb

    return result
