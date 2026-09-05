"""Tax on income chargeable at special rates for AY 2026-27."""

from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Iterable

from app.engine.constants import (
    LOTTERY_RATE,
    LTCG_112A_EXEMPTION,
    LTCG_112A_RATE_POST_JUL24,
    LTCG_OTHER_RATE_POST_JUL24,
    STCG_111A_RATE_POST_JUL24,
    STCG_111A_RATE_PRE_JUL24,
    UNEXPLAINED_INCOME_RATE,
    VDA_RATE,
)

_ZERO = Decimal("0")
_HUNDRED = Decimal("100")


class SpecialRateSection(str, Enum):
    """Supported Schedule-SI sections."""

    S111 = "111"
    S111A = "111A"
    S112 = "112"
    S112A = "112A"
    S115A = "115A"
    S115AD = "115AD"
    S115BB = "115BB"
    S115BBJ = "115BBJ"
    S115BBA = "115BBA"
    S115BBE = "115BBE"
    S115BBF = "115BBF"
    S115BBG = "115BBG"
    S115BBH = "115BBH"
    S115BBI = "115BBI"
    S115E = "115E"
    # Section 115AD-specific Schedule-SI codes for an FII/FPI assessee's OWN
    # capital gains on securities -- distinct from the generic S115AD above
    # (declared but never dispatched anywhere) and from the unrelated
    # Schedule-OS S5AD1I/S5AD1IP/S5AD1IDIV family (Section 115A(1)(a)/(b)
    # dividend/interest/royalty income, not capital gains). Rates confirmed
    # against the official ITR-2 form's own Schedule SI rate table
    # (Reference Docs by CBDT & ITD/Official ITR FORMS/
    # ITR-2-2026-Eng_extracted_text.txt, rows 2/3/8/11): row 2 groups
    # "111A or 115AD(1)(b)(ii)-Proviso" at 20% (same rate as ordinary 111A,
    # just a distinct SecCode for FII securities with STT paid); row 3 is
    # "115AD (STCG for FIIs on securities where STT not paid)" at 30% (no
    # ordinary-taxpayer equivalent -- for a resident/ordinary NR this same
    # "other STCG" basket is slab-rate, not a flat special rate, but 115AD
    # is a complete code unto itself for FII securities, so it is ALWAYS
    # special-rate, never slab); row 8 is "115AD (LTCG for FIIs on
    # securities)" at 12.5% (same rate as ordinary section 112); row 11
    # groups "112A or 115AD(1)(b)(iii)-Proviso" at 12.5% (same rate as
    # ordinary 112A).
    S115AD_STCG_111A = "5AD1biip"
    S115AD_STCG_OTHER = "5ADii"
    S115AD_LTCG_OTHER = "5ADiii"
    S115AD_LTCG_112A = "5ADiiiP"
    DIVIDEND = "DIVIDEND"
    DTAA_STCG = "DTAASTCG"
    DTAA_LTCG = "DTAALTCG"
    DTAA_OS = "DTAAOS"
    PTI_STCG20 = "PTI_STCG20P"
    PTI_STCG30 = "PTI_STCG30P"
    PTI_LTCG112A = "PTI_LTCG12_5P112A"
    PTI_LTCG125 = "PTI_LTCG12_5P"

    # Section 115A/115AC/115ACA/115AD "any other income chargeable at
    # special rate" dropdown (official Schedule OS ``SourceDescription``
    # enum). Rates confirmed against the official ITR-2 form text
    # (Reference Docs by CBDT & ITD/Official ITR FORMS/ITR-2-2026-Eng.pdf,
    # pages 15-16's Part B-TI Sl.No.2d breakdown and its own Schedule SI
    # table) -- the form explicitly annotates S5A1AIIAA/S5A1AIIAAP/
    # S5A1AIIAA2P (5%/4%/9%, the 194LC(1)-linked interest categories that
    # have been amended by multiple Finance Acts) and the dividend-quarterly
    # breakdown table explicitly annotates S5A1AI/S5A1AA/S5AC1ABD/S5ACA1A/
    # S5AD1IDIV (20%/10%/10%/10%/20%) and Schedule SI's own row 18a
    # (S5A1BA, royalty/FTS, 20% -- NOT the commonly-assumed 10%, confirmed
    # by checking the primary source rather than general knowledge, per
    # this project's own established discipline). S5A1AII/S5A1AIIA/
    # S5A1AIIAB/S5A1AIIAC/S5A1AIII/S5AD1I/S5AD1IP are NOT independently
    # re-annotated by the form (only "chargeable u/s [X]" with no "@X%"),
    # since these are long-stable statutory rates the form doesn't need to
    # restate; their rates below (20%/5%/5%/5%/20%/20%/5%) are the
    # established Section 115A(1)(a)(ii)/(iia)/(iiab)/(iiac)/(iii) and
    # 115AD(1)(i) rates, not independently confirmed against a CBDT
    # document in this pass -- flagged in
    # Docs/ITR2_FRONTEND_AND_SERIALIZATION_AUDIT_AY2026_27.md for a live
    # UAT/ITD cross-check before this path is relied on for a real filing.
    S5A1AI = "5A1ai"
    S5A1AA = "5A1aA"
    S5A1AII = "5A1aii"
    S5A1AIIA = "5A1aiia"
    S5A1AIIAA = "5A1aiiaa"
    S5A1AIIAB = "5A1aiiab"
    S5A1AIIAC = "5A1aiiac"
    S5A1AIII = "5A1aiii"
    S5A1BA = "5A1bA"
    S5AC1AB = "5AC1ab"
    S5AC1ABD = "5AC1abD"
    S5ACA1A = "5ACA1a"
    S5AD1I = "5AD1i"
    S5AD1IP = "5AD1iP"
    S5AD1IDIV = "5AD1iDiv"
    S5A1AIIAAP = "5A1aiiaaP"
    S5A1AIIAA2P = "5A1aiiaa2P"


@dataclass
class SpecialRateEntry:
    """A single non-negative Schedule-SI tax basket."""

    section: str = ""
    description: str = ""
    gross_income: Decimal = _ZERO
    deductions: Decimal = _ZERO
    net_income: Decimal = _ZERO
    tax_rate_pct: Decimal = _ZERO
    tax_amount: Decimal = _ZERO
    exemption_available: Decimal = _ZERO
    taxable_income: Decimal = _ZERO


@dataclass
class SpecialRatesResult:
    """Aggregated Schedule-SI income and tax buckets."""

    entries: list[SpecialRateEntry] = field(default_factory=list)
    total_special_rate_income: Decimal = _ZERO
    total_special_rate_tax: Decimal = _ZERO
    surcharge_cap_tax: Decimal = _ZERO
    surcharge_full_tax: Decimal = _ZERO
    surcharge_cap_income: Decimal = _ZERO
    surcharge_full_income: Decimal = _ZERO


_SURCHARGE_CAP_SECTIONS: set[str] = {
    SpecialRateSection.S111A.value,
    SpecialRateSection.S112.value,
    SpecialRateSection.S112A.value,
    SpecialRateSection.DIVIDEND.value,
    SpecialRateSection.PTI_STCG20.value,
    SpecialRateSection.PTI_LTCG112A.value,
    SpecialRateSection.PTI_LTCG125.value,
    SpecialRateSection.S115AD.value,
    # FII/FPI 115AD-specific 111A/112/112A-equivalent codes get the same
    # 15% surcharge cap as their ordinary counterparts, since they are the
    # same underlying tax treatment just disclosed under a different
    # SecCode. S115AD_STCG_OTHER (30%, no ordinary-taxpayer equivalent) is
    # deliberately excluded -- a 30% STCG rate is not among the categories
    # the Finance Act's surcharge cap covers for any taxpayer (VDA, also
    # 30%, is likewise not in this set).
    SpecialRateSection.S115AD_STCG_111A.value,
    SpecialRateSection.S115AD_LTCG_OTHER.value,
    SpecialRateSection.S115AD_LTCG_112A.value,
    # Purely-dividend 115A/115AC/115ACA/115AD sub-clauses -- the Finance
    # Act's 15%-surcharge cap for dividend income applies regardless of
    # which section charges it. The mixed dividend+interest+units category
    # (S5A1AI) is deliberately excluded from this cap: it is not purely
    # dividend income, so capping its surcharge the same way would be an
    # unverified extension of the dividend-specific relief.
    SpecialRateSection.S5A1AA.value,
    SpecialRateSection.S5AC1ABD.value,
    SpecialRateSection.S5ACA1A.value,
    SpecialRateSection.S5AD1IDIV.value,
}


def _non_negative(value: Decimal | None) -> Decimal:
    """Return a finite monetary value floored at zero."""
    if value is None:
        return _ZERO
    decimal_value = Decimal(value)
    if not decimal_value.is_finite():
        raise ValueError("Monetary values must be finite")
    return max(_ZERO, decimal_value)


def _flat_rate_entry(
    section: SpecialRateSection,
    description: str,
    income: Decimal | None,
    rate_pct: Decimal,
) -> SpecialRateEntry:
    taxable = _non_negative(income)
    return SpecialRateEntry(
        section=section.value,
        description=description,
        gross_income=taxable,
        net_income=taxable,
        tax_rate_pct=rate_pct,
        tax_amount=taxable * rate_pct / _HUNDRED,
        taxable_income=taxable,
    )


def compute_112a(
    ltcg_112a: Decimal | None,
    cost_of_acquisition: Decimal | None = _ZERO,
    *,
    pre_exempted: bool = False,
) -> SpecialRateEntry:
    """Compute section 112A tax, applying its threshold exactly once.

    Args:
        ltcg_112a: Gross gain, or already-thresholded taxable gain when
            ``pre_exempted`` is true.
        cost_of_acquisition: Cost deductible from a gross gain. It must be zero
            when ``pre_exempted`` is true.
        pre_exempted: Whether ``ltcg_112a`` already excludes the annual
            section 112A threshold.

    Returns:
        The section 112A Schedule-SI entry.

    Raises:
        ValueError: If a cost is supplied with an already-thresholded amount.
    """
    gross = _non_negative(ltcg_112a)
    cost = _non_negative(cost_of_acquisition)
    if pre_exempted and cost != _ZERO:
        raise ValueError("cost_of_acquisition must be zero when pre_exempted=True")
    net = gross if pre_exempted else max(_ZERO, gross - cost)
    exemption = _ZERO if pre_exempted else min(net, LTCG_112A_EXEMPTION)
    taxable = net if pre_exempted else net - exemption
    return SpecialRateEntry(
        section=SpecialRateSection.S112A.value,
        description="LTCG on listed equity (STT paid)",
        gross_income=gross,
        deductions=cost,
        net_income=net,
        tax_rate_pct=LTCG_112A_RATE_POST_JUL24,
        tax_amount=taxable * LTCG_112A_RATE_POST_JUL24 / _HUNDRED,
        exemption_available=exemption,
        taxable_income=taxable,
    )


def compute_112a_taxable(taxable_112a: Decimal | None) -> SpecialRateEntry:
    """Compute section 112A from an amount thresholded by the CG schedule.

    Args:
        taxable_112a: Taxable section 112A amount after the annual threshold.

    Returns:
        The section 112A Schedule-SI entry without a second threshold.
    """
    return compute_112a(taxable_112a, pre_exempted=True)


def compute_111a(
    stcg_111a: Decimal | None,
    is_post_jul24: bool = True,
) -> SpecialRateEntry:
    """Compute section 111A tax, at 20% for AY 2026-27 transactions.

    Args:
        stcg_111a: Net section 111A short-term capital gain.
        is_post_jul24: Use the post-23 July 2024 rate. Retained for historical
            caller compatibility; AY 2026-27 callers should leave it true.

    Returns:
        The section 111A Schedule-SI entry.
    """
    rate = STCG_111A_RATE_POST_JUL24 if is_post_jul24 else STCG_111A_RATE_PRE_JUL24
    return _flat_rate_entry(
        SpecialRateSection.S111A,
        "STCG on listed equity (STT paid)",
        stcg_111a,
        rate,
    )


def compute_112(ltcg_112: Decimal | None) -> SpecialRateEntry:
    """Compute post-23 July 2024 section 112 LTCG tax at 12.5%.

    Args:
        ltcg_112: Net taxable long-term capital gain other than section 112A.

    Returns:
        The section 112 Schedule-SI entry.
    """
    return _flat_rate_entry(
        SpecialRateSection.S112,
        "LTCG other than section 112A",
        ltcg_112,
        LTCG_OTHER_RATE_POST_JUL24,
    )


def compute_115ad_stcg_other(stcg_other: Decimal | None) -> SpecialRateEntry:
    """Compute section 115AD(1)(ii) STCG tax at 30% for an FII/FPI's
    securities other than 111A-equivalent equity/units (STT not paid).

    Unlike an ordinary taxpayer's "other" STCG (slab-rate, never Schedule
    SI), section 115AD is a complete code for FII/FPI securities taxation
    -- this basket is always a flat special rate, never slab-taxed, for an
    assessee flagged as FII/FPI on the filing profile.

    Args:
        stcg_other: Net taxable short-term capital gain on securities other
            than 111A-equivalent equity/units.

    Returns:
        The section 115AD(1)(ii) Schedule-SI entry.
    """
    return _flat_rate_entry(
        SpecialRateSection.S115AD_STCG_OTHER,
        "STCG on securities (FII/FPI, STT not paid) under section 115AD(1)(ii)",
        stcg_other,
        Decimal("30"),
    )


def compute_lottery(lottery_income: Decimal | None) -> SpecialRateEntry:
    """Compute section 115BB lottery and gambling tax."""
    return _flat_rate_entry(SpecialRateSection.S115BB, "Lottery / Gambling / Crossword", lottery_income, LOTTERY_RATE)


def compute_vda(vda_income: Decimal | None) -> SpecialRateEntry:
    """Compute section 115BBH virtual-digital-asset tax."""
    return _flat_rate_entry(SpecialRateSection.S115BBH, "Virtual Digital Assets (Crypto)", vda_income, VDA_RATE)


def compute_115bbe(unexplained_income: Decimal | None) -> SpecialRateEntry:
    """Compute section 115BBE unexplained-income tax."""
    return _flat_rate_entry(SpecialRateSection.S115BBE, "Unexplained cash credits / investments", unexplained_income, UNEXPLAINED_INCOME_RATE)


def compute_115bbf(patent_royalty: Decimal | None) -> SpecialRateEntry:
    """Compute section 115BBF patent-royalty tax at 10%."""
    return _flat_rate_entry(SpecialRateSection.S115BBF, "Royalty on patents (resident)", patent_royalty, Decimal("10"))


def compute_115bbg(carbon_credit_income: Decimal | None) -> SpecialRateEntry:
    """Compute section 115BBG carbon-credit tax at 10%."""
    return _flat_rate_entry(SpecialRateSection.S115BBG, "Transfer of carbon credits", carbon_credit_income, Decimal("10"))


def compute_115bbi(offshore_fund_income: Decimal | None) -> SpecialRateEntry:
    """Compute section 115BBI specified offshore-fund tax at 5%."""
    return _flat_rate_entry(SpecialRateSection.S115BBI, "Specified offshore fund income", offshore_fund_income, Decimal("5"))


def compute_111(accumulated_pf_income: Decimal | None) -> SpecialRateEntry:
    """Compute section 111 tax on accumulated balance of recognised PF.

    Taxed at the taxpayer's slab rate, but reported in Schedule SI for
    separate disclosure. The slab rate is applied at TTI level.

    Args:
        accumulated_pf_income: Taxable accumulated PF balance.

    Returns:
        The section 111 Schedule-SI entry at slab rate (0% placeholder).
    """
    return _flat_rate_entry(SpecialRateSection.S111, "Accumulated balance of recognised PF", accumulated_pf_income, Decimal("0"))


def compute_115bbj(online_gaming_income: Decimal | None) -> SpecialRateEntry:
    """Compute section 115BBJ tax on winnings from online games at 30%."""
    return _flat_rate_entry(SpecialRateSection.S115BBJ, "Winnings from online games", online_gaming_income, LOTTERY_RATE)


def compute_115bba(non_resident_sports_income: Decimal | None) -> SpecialRateEntry:
    """Compute section 115BBA tax on non-resident sportsmen/sports associations at 20%."""
    return _flat_rate_entry(SpecialRateSection.S115BBA, "Income of non-resident sportsmen / sports associations", non_resident_sports_income, Decimal("20"))


def compute_115e_a(investment_income: Decimal | None) -> SpecialRateEntry:
    """Compute section 115E(a) tax on investment income of NRIs at 20%."""
    return _flat_rate_entry(SpecialRateSection.S115E, "Investment income of NRI (Section 115E(a))", investment_income, Decimal("20"))


def compute_115e_b(ltcg_nri: Decimal | None) -> SpecialRateEntry:
    """Compute section 115E(b) tax on LTCG of NRIs on foreign exchange assets at 10%."""
    return _flat_rate_entry(SpecialRateSection.S115E, "LTCG of NRI on foreign exchange assets (Section 115E(b))", ltcg_nri, Decimal("10"))


# (SpecialRateSection, description, rate%) for each Schedule OS "any other
# income chargeable at special rate" dropdown code -- see the enum's own
# docstring above for the rate citations and confidence level per entry.
_OTHER_SPECIAL_RATE_TABLE: dict[str, tuple[SpecialRateSection, str, Decimal]] = {
    "5A1ai": (SpecialRateSection.S5A1AI, "Dividend/interest/unit income in foreign currency (115A(1)(a)(i))", Decimal("20")),
    "5A1aA": (SpecialRateSection.S5A1AA, "NR dividend from an IFSC unit (proviso to 115A(1)(a)(A))", Decimal("10")),
    "5A1aii": (SpecialRateSection.S5A1AII, "Interest from govt/Indian concern in foreign currency (115A(1)(a)(ii))", Decimal("20")),
    "5A1aiia": (SpecialRateSection.S5A1AIIA, "Interest from Infrastructure Debt Fund (115A(1)(a)(iia))", Decimal("5")),
    "5A1aiiaa": (SpecialRateSection.S5A1AIIAA, "Interest u/s 194LC(1) (115A(1)(a)(iiaa))", Decimal("5")),
    "5A1aiiab": (SpecialRateSection.S5A1AIIAB, "Interest u/s 194LD (115A(1)(a)(iiab))", Decimal("5")),
    "5A1aiiac": (SpecialRateSection.S5A1AIIAC, "Business-trust distributed interest u/s 194LBA (115A(1)(a)(iiac))", Decimal("5")),
    "5A1aiii": (SpecialRateSection.S5A1AIII, "UTI/mutual-fund unit income in foreign currency (115A(1)(a)(iii))", Decimal("20")),
    "5A1bA": (SpecialRateSection.S5A1BA, "Royalty / fees for technical services (115A(1)(b)(A)&(B))", Decimal("20")),
    "5AC1ab": (SpecialRateSection.S5AC1AB, "NR interest on foreign-currency bonds (115AC(1)(a))", Decimal("10")),
    "5AC1abD": (SpecialRateSection.S5AC1ABD, "NR dividend on foreign-currency GDRs (115AC(1)(b))", Decimal("10")),
    "5ACA1a": (SpecialRateSection.S5ACA1A, "Resident dividend on foreign-currency GDRs (115ACA(1)(a))", Decimal("10")),
    "5AD1i": (SpecialRateSection.S5AD1I, "FII income (other than dividend) on securities (115AD(1)(i))", Decimal("20")),
    "5AD1iP": (SpecialRateSection.S5AD1IP, "FII interest on bonds/govt securities u/s 194LD (115AD(1)(i) proviso)", Decimal("5")),
    "5AD1iDiv": (SpecialRateSection.S5AD1IDIV, "FII dividend on securities (115AD(1)(i))", Decimal("20")),
    "5A1aiiaaP": (SpecialRateSection.S5A1AIIAAP, "Interest per proviso to 194LC(1) (115A(1)(a)(iiaa))", Decimal("4")),
    "5A1aiiaa2P": (SpecialRateSection.S5A1AIIAA2P, "Interest per second proviso to 194LC(1) (115A(1)(a)(iiaa))", Decimal("9")),
}


def compute_other_special_rate_income(source_description: str, amount: Decimal | None) -> SpecialRateEntry:
    """Compute tax for a Schedule OS "any other income chargeable at
    special rate" dropdown entry (official ``SourceDescription`` code).

    ``5BBF``/``5BBG``/``5Ea`` are deliberately not in the lookup table --
    those three already have their own dedicated ``compute_115bbf``/
    ``compute_115bbg``/``compute_115e_a`` handlers; callers should dispatch
    to those directly for consistency with every other caller of this
    module (e.g. Schedule OS's own lottery/PF SI-entries), not duplicate
    them here.
    """
    entry = _OTHER_SPECIAL_RATE_TABLE.get(source_description)
    if entry is None:
        raise ValueError(f"Unsupported special-rate source description: {source_description!r}")
    section, description, rate = entry
    return _flat_rate_entry(section, description, amount, rate)


def compute_dividend_special(section: str, dividend_income: Decimal | None, rate: Decimal) -> SpecialRateEntry:
    """Compute dividend tax at a special rate for non-resident / FII dividend.

    Args:
        section: Section label (e.g. '115A(1)(a)(i)', '115AD(1)(i)').
        dividend_income: Dividend income.
        rate: Special rate percentage.

    Returns:
        The dividend Schedule-SI entry.
    """
    taxable = _non_negative(dividend_income)
    return SpecialRateEntry(
        section=SpecialRateSection.DIVIDEND.value,
        description=f"Dividend income ({section})",
        gross_income=taxable,
        net_income=taxable,
        tax_rate_pct=rate,
        tax_amount=taxable * rate / _HUNDRED,
        taxable_income=taxable,
    )


def compute_dtaa_stcg(stcg_dtaa: Decimal | None, rate: Decimal) -> SpecialRateEntry:
    """Compute DTAA-rate STCG tax."""
    return _flat_rate_entry(SpecialRateSection.DTAA_STCG, "STCG at DTAA rate", stcg_dtaa, rate)


def compute_dtaa_ltcg(ltcg_dtaa: Decimal | None, rate: Decimal) -> SpecialRateEntry:
    """Compute DTAA-rate LTCG tax."""
    return _flat_rate_entry(SpecialRateSection.DTAA_LTCG, "LTCG at DTAA rate", ltcg_dtaa, rate)


def compute_dtaa_os(os_dtaa: Decimal | None, rate: Decimal) -> SpecialRateEntry:
    """Compute DTAA-rate other-source income tax."""
    return _flat_rate_entry(SpecialRateSection.DTAA_OS, "Other source income at DTAA rate", os_dtaa, rate)


def compute_pti_stcg20(pti_income: Decimal | None) -> SpecialRateEntry:
    """Compute pass-through income in the nature of STCG @ 20% (Section 111A)."""
    return _flat_rate_entry(SpecialRateSection.PTI_STCG20, "PTI - STCG @ 20% (Section 111A)", pti_income, STCG_111A_RATE_POST_JUL24)


def compute_pti_stcg30(pti_income: Decimal | None) -> SpecialRateEntry:
    """Compute pass-through income in the nature of STCG @ 30%."""
    return _flat_rate_entry(SpecialRateSection.PTI_STCG30, "PTI - STCG @ 30%", pti_income, Decimal("30"))


def compute_pti_ltcg112a(pti_income: Decimal | None) -> SpecialRateEntry:
    """Compute pass-through income in the nature of LTCG @ 12.5% u/s 112A."""
    return _flat_rate_entry(SpecialRateSection.PTI_LTCG112A, "PTI - LTCG @ 12.5% u/s 112A", pti_income, LTCG_112A_RATE_POST_JUL24)


def compute_pti_ltcg125(pti_income: Decimal | None) -> SpecialRateEntry:
    """Compute pass-through income in the nature of LTCG @ 12.5%."""
    return _flat_rate_entry(SpecialRateSection.PTI_LTCG125, "PTI - LTCG @ 12.5%", pti_income, LTCG_OTHER_RATE_POST_JUL24)


def aggregate(entries: Iterable[SpecialRateEntry] | None) -> SpecialRatesResult:
    """Aggregate entries and split 15%-capped and full-surcharge baskets.

    Args:
        entries: Schedule-SI entries. Negative externally-created values are
            normalized so neither income nor tax can reduce another basket.

    Returns:
        Aggregated special-rate result.
    """
    normalized: list[SpecialRateEntry] = []
    for entry in entries or []:
        entry.taxable_income = _non_negative(entry.taxable_income)
        entry.tax_amount = _non_negative(entry.tax_amount)
        normalized.append(entry)
    cap_entries = [entry for entry in normalized if entry.section in _SURCHARGE_CAP_SECTIONS]
    full_entries = [entry for entry in normalized if entry.section not in _SURCHARGE_CAP_SECTIONS]
    cap_tax = sum((entry.tax_amount for entry in cap_entries), _ZERO)
    full_tax = sum((entry.tax_amount for entry in full_entries), _ZERO)
    return SpecialRatesResult(
        entries=normalized,
        total_special_rate_income=sum((entry.taxable_income for entry in normalized), _ZERO),
        total_special_rate_tax=cap_tax + full_tax,
        surcharge_cap_tax=cap_tax,
        surcharge_full_tax=full_tax,
        surcharge_cap_income=sum((entry.taxable_income for entry in cap_entries), _ZERO),
        surcharge_full_income=sum((entry.taxable_income for entry in full_entries), _ZERO),
    )
