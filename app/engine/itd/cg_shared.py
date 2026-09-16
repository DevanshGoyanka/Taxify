"""
Schedule CG disclosure-row builders shared between ITR-2 and ITR-3.

Both forms carry an identical Schedule CG (verified field-for-field against
their respective official JSON schemas) and both consume the same
``CGTransaction`` list (``app/schemas/itr2.py``, imported by ITR-3's own
input schema). Building each disclosure sub-table exactly once here, rather
than once per form's `itd/itr{N}.py`, is what keeps the two forms from
silently drifting apart on the same statutory computation -- the exact risk
flagged for this schedule specifically (see `CLAUDE.md`'s Schedule CG note
on `app/engine/itd/itr2.py`/`calculators/itr2.py`).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from app.engine.itd.common import _to_rupees
from app.engine.schedules.capital_gains import _is_short_term, _exemption_claim_total, deemed_consideration_50ca

_ZERO = Decimal("0")

# Schedule CG's generic "other assets" bucket (Sl. A6/B9 ITR-3; Sl. A5/B8
# ITR-2). Kept here, not `itd/itr2.py`, since both forms' own formatters
# need it and `itd/itr2.py` already imports FROM this module (not the
# reverse) -- `itd/itr2.py` re-imports these two names from here so its
# own existing internal references, and ITR-3's existing
# ``from app.engine.itd.itr2 import ... as _ITR2_GENERIC_OTHER_ASSET_TYPES``
# import, both keep working unchanged.
_GENERIC_OTHER_ASSET_TYPES = frozenset({
    "unlisted_shares",
    "listed_security",
    "debt_mutual_fund",
    "specified_mutual_fund_50aa",
    "market_linked_debenture_50aa",
    "bonds_debentures",
    "depreciable_asset",
    "jewellery",
    "foreign_asset",
    "other",
})

# The subset of the generic "other assets" bucket that are genuinely
# "securities" for section 115AD purposes (an FII/FPI's own gains on these
# route to NRISecur115AD/NRIOnSec112and115Dtls instead of the ordinary
# SaleOnOtherAssets/SaleofAssetNADtls -- ITR-2 only, since ITR-3 filers are
# never FII/FPI). `jewellery`/`depreciable_asset`/`foreign_asset`/`other`
# are NOT securities and always stay in the ordinary bucket.
_FII_SECURITIES_ASSET_TYPES = frozenset({
    "unlisted_shares",
    "listed_security",
    "debt_mutual_fund",
    "specified_mutual_fund_50aa",
    "market_linked_debenture_50aa",
    "bonds_debentures",
})


def _is_actually_short_111a(tx: Any) -> bool:
    """Same reclassification guard used by both forms' Table E/F disclosures.

    A ``listed_equity_111a``/``equity_oriented_fund_111a`` transaction held
    past the 12-month threshold is reclassified into the 112A LTCG basket
    everywhere else in the pipeline -- this STCG-only disclosure table must
    exclude it too, or its own total includes a gain neither form actually
    taxes as STCG@20%.
    """
    asset_type = tx.asset_type.value if hasattr(tx.asset_type, "value") else tx.asset_type
    if tx.date_of_acquisition is not None:
        return _is_short_term(asset_type, tx.date_of_acquisition, tx.date_of_transfer)
    if getattr(tx, "explicit_long_term", None) is not None:
        return not tx.explicit_long_term
    return True


def build_equity_mf_stt_rows(
    cg_transactions: list,
    is_fii_fpi: bool = False,
) -> list[dict[str, Any]]:
    """
    Build Schedule CG item A3 ("EquityMFonSTT") -- STCG on equity shares/
    units of an equity-oriented fund/business trust, STT paid (s.111A, or
    the s.115AD(1)(b)(ii) proviso for an FII/FPI).

    Official schema: an array capped at ``maxItems: 2``, one row per
    ``MFSectionCode`` ("1A" ordinary / "5AD1biip" FII-FPI); each row's own
    details object is AGGREGATE-ONLY (no scrip identifier field exists).
    ``is_fii_fpi`` is a single filing-profile-level flag (not per-
    transaction, and not a concept ITR-3 filers have at all -- individuals/
    HUF with business income are never FII/FPI), so every matching
    transaction for a given filer always shares the same code -- at most
    one row is ever produced.
    """
    matching = [
        tx for tx in cg_transactions
        if tx.asset_type.value in ("listed_equity_111a", "equity_oriented_fund_111a")
        and _is_actually_short_111a(tx)
    ]
    if not matching:
        return []
    total_consideration = sum((tx.full_consideration for tx in matching), _ZERO)
    total_acquisition_cost = sum((tx.cost_of_acquisition for tx in matching), _ZERO)
    total_improvement_cost = sum((tx.improvement_cost for tx in matching), _ZERO)
    total_expenditure = sum((tx.expenditure_on_transfer for tx in matching), _ZERO)
    total_loss_94 = sum(
        (getattr(tx, "loss_disallowed_94_7_94_8", _ZERO) for tx in matching), _ZERO
    )
    total_deduction = total_acquisition_cost + total_improvement_cost + total_expenditure
    balance_cg = total_consideration - total_deduction
    capgain_on_assets = balance_cg + total_loss_94
    return [{
        "MFSectionCode": "5AD1biip" if is_fii_fpi else "1A",
        "EquityMFonSTTDtls": {
            "FullConsideration": _to_rupees(total_consideration),
            "DeductSec48": {
                "AquisitCost": _to_rupees(total_acquisition_cost),
                "ImproveCost": _to_rupees(total_improvement_cost),
                "ExpOnTrans": _to_rupees(total_expenditure),
                "TotalDedn": _to_rupees(total_deduction),
            },
            "BalanceCG": _to_rupees(balance_cg),
            "LossSec94of7Or94of8": _to_rupees(total_loss_94),
            "CapgainonAssets": _to_rupees(capgain_on_assets),
        },
    }]


def _aggregate_generic_other_assets(
    transactions: list,
    is_long_term: bool,
    asset_types: frozenset = _GENERIC_OTHER_ASSET_TYPES,
) -> dict[str, Any]:
    """
    Raw Decimal aggregates for Schedule CG's generic "other assets" bucket
    (Sl. A6/B9 ITR-3; Sl. A5/B8 ITR-2) -- unlisted shares, debt mutual
    funds, bonds/debentures, jewellery, foreign assets, and any other
    capital asset not covered by an earlier, more specific Schedule CG
    item.

    Both forms' own final JSON shapes (``itd/itr2.py``'s
    ``_other_assets_block`` for ITR-2; this module's
    ``build_itr3_other_assets_stcg_block``/``build_itr3_other_assets_ltcg_block``
    for ITR-3) share this exact same underlying aggregation -- consideration/
    cost/94(7)(8)-loss/exemption-by-section summed across every matching
    transaction of the matching holding period, split into "unquoted
    shares" (``unlisted_shares`` -- section 50CA deeming applies) versus
    "assets other than unquoted shares" (every other generic category)
    sub-totals -- but differ in which extra terms fold into the final
    taxable figure (ITR-3's STCG side additionally carries a deemed-STCG-
    on-depreciable-assets schedule total and a richer, multi-section
    exemption breakdown that ITR-2's simpler equivalent item does not have
    at all; see each form's own formatter for the confirmed form-text
    citation). Only this shared core is centralized here -- each form's
    own final-shape formatter still lives with that form's builder.

    Indexation does not apply to this bucket at all (confirmed by the
    official form's item 5b/8b (ITR-2) / 6b/9b (ITR-3), which only ever ask
    for "cost of acquisition without indexation" here -- the dual indexed/
    non-indexed track is specific to land/building's own section 112(1)(a)
    transitional provision, not this generic bucket).
    """
    unq_consideration = _ZERO
    unq_fmv = _ZERO
    oth_consideration = _ZERO
    total_cost = _ZERO
    total_improvement = _ZERO
    total_expenditure = _ZERO
    total_loss94 = _ZERO
    exemption_by_section: dict[str, Decimal] = {}

    for tx in transactions or []:
        asset_type = tx.asset_type.value if hasattr(tx.asset_type, "value") else tx.asset_type
        if asset_type not in asset_types:
            continue
        is_short = True
        if tx.date_of_acquisition is not None:
            is_short = _is_short_term(asset_type, tx.date_of_acquisition, tx.date_of_transfer)
        elif tx.explicit_long_term is not None:
            is_short = not tx.explicit_long_term
        wanted_short = not is_long_term
        if is_short != wanted_short:
            continue

        total_cost += tx.cost_of_acquisition
        total_improvement += tx.improvement_cost
        total_expenditure += tx.expenditure_on_transfer
        if asset_type == "unlisted_shares":
            unq_consideration += tx.full_consideration
            unq_fmv += tx.fair_market_value_50ca or _ZERO
        else:
            oth_consideration += tx.full_consideration

        if not is_long_term:
            # Sl. A6d/A5d -- 94(7)/94(8) disallowed loss, STCG-only (no
            # such sub-item exists on the LTCG side of this bucket in
            # either form).
            total_loss94 += getattr(tx, "loss_disallowed_94_7_94_8", None) or _ZERO

        # New flat single-claim exemption (Sl. A6f/B9d ITR-3; B8d ITR-2 --
        # `other_asset_gain()` in `capital_gains.py` already validates the
        # section is applicable for this ST/LT combination before the
        # calculator ever subtracts it from the taxed amount; this
        # disclosure-side aggregation mirrors that same set so the two
        # never disagree on which claims are honored).
        section = getattr(tx, "other_assets_exemption_section", None)
        amount = getattr(tx, "other_assets_exemption_amount", None) or _ZERO
        if section and amount:
            exemption_by_section[section] = exemption_by_section.get(section, _ZERO) + amount
        # Legacy rich-evidence claim list (CGAS-tracked) -- ITR-2's own
        # item only ever recognized 54F here; kept for backward
        # compatibility with any pre-existing caller that already
        # populates `exemptions` instead of the new flat fields.
        if is_long_term:
            legacy_54f = _exemption_claim_total(getattr(tx, "exemptions", None), frozenset({"54F"}))
            if legacy_54f:
                exemption_by_section["54F"] = exemption_by_section.get("54F", _ZERO) + legacy_54f

    unq_deemed = deemed_consideration_50ca(unq_consideration, unq_fmv)
    full_consideration = unq_deemed + oth_consideration
    total_ded = total_cost + total_improvement + total_expenditure
    balance = full_consideration - total_ded

    return {
        "unq_consideration": unq_consideration,
        "unq_fmv": unq_fmv,
        "unq_deemed": unq_deemed,
        "oth_consideration": oth_consideration,
        "full_consideration": full_consideration,
        "total_cost": total_cost,
        "total_improvement": total_improvement,
        "total_expenditure": total_expenditure,
        "total_ded": total_ded,
        "balance": balance,
        "total_loss94": total_loss94,
        "exemption_by_section": exemption_by_section,
    }


def _consideration_and_deduction_fields(agg: dict[str, Any]) -> dict[str, Any]:
    """The consideration/cost sub-fields common to every "other assets"
    shape (identical in ITR-2 and ITR-3, both ST and LT)."""
    return {
        "FullValueConsdRecvUnqshr": _to_rupees(agg["unq_consideration"]),
        "FairMrktValueUnqshr": _to_rupees(agg["unq_fmv"]),
        "FullValueConsdSec50CA": _to_rupees(agg["unq_deemed"]),
        "FullValueConsdOthUnqshr": _to_rupees(agg["oth_consideration"]),
        "FullConsideration": _to_rupees(agg["full_consideration"]),
        "DeductSec48": {
            "AquisitCost": _to_rupees(agg["total_cost"]),
            "ImproveCost": _to_rupees(agg["total_improvement"]),
            "ExpOnTrans": _to_rupees(agg["total_expenditure"]),
            "TotalDedn": _to_rupees(agg["total_ded"]),
        },
        "BalanceCG": _to_rupees(agg["balance"]),
    }


def build_itr3_other_assets_stcg_block(
    transactions: list,
    deemed_stcg_depreciable: Decimal = _ZERO,
) -> dict[str, Any]:
    """
    Build ITR-3 Schedule CG item A6 ("SaleOnOtherAssets", STCG) --
    confirmed against the official ITR-3 form PDF (Schedule CG item 6):
    ``6g = 6c + 6d + 6e - 6f`` where 6c = balance, 6d = 94(7)/94(8)
    disallowed loss (added back), 6e = deemed STCG on depreciable assets
    (Schedule DCG's own total), 6f = deduction u/s 54G/54GA.

    Schema-confirmed DIFFERENCE from ITR-2's equivalent item (A5, `itd/
    itr2.py::_other_assets_block`): ITR-3's own ``ShortTermCapGainFor23.
    SaleOnOtherAssets`` inlines two extra REQUIRED fields ITR-2's
    ``EquityOrUnitSec94Type``-shaped equivalent does not have at all --
    ``DeemedStcgOnAssets`` and ``ExemptionOrDednUs54`` (enum restricted to
    "54G"/"54GA" here) -- matching the official ITR-2 form's own item 5
    text having NO 6e/6f-equivalent sub-items (ITR-2 filers have no
    business income and therefore no depreciable-asset block or
    shifting-of-undertaking relief).
    """
    agg = _aggregate_generic_other_assets(transactions, is_long_term=False)
    valid_sections = ("54G", "54GA")
    exemption_by_section = agg["exemption_by_section"]
    exemption_dtls = [
        {"ExemptionSecCode": section, "ExemptionAmount": _to_rupees(exemption_by_section[section])}
        for section in valid_sections if exemption_by_section.get(section)
    ]
    exemption_total = sum((exemption_by_section.get(s, _ZERO) for s in valid_sections), _ZERO)
    capgain_on_assets = agg["balance"] + agg["total_loss94"] + deemed_stcg_depreciable - exemption_total
    return {
        **_consideration_and_deduction_fields(agg),
        "LossSec94of7Or94of8": _to_rupees(agg["total_loss94"]),
        "DeemedStcgOnAssets": _to_rupees(deemed_stcg_depreciable),
        "ExemptionOrDednUs54": {
            **({"ExemptionOrDednUs54Dtls": exemption_dtls} if exemption_dtls else {}),
            "ExemptionGrandTotal": _to_rupees(exemption_total),
        },
        "CapgainonAssets": _to_rupees(capgain_on_assets),
    }


def build_itr3_other_assets_ltcg_block(transactions: list) -> dict[str, Any]:
    """
    Build ITR-3 Schedule CG item B9 ("SaleofAssetNADtls.SaleofAssetNA",
    LTCG) -- confirmed against the official ITR-3 form PDF (Schedule CG
    item 9): ``9e = 9c - 9d`` where 9c = balance, 9d = deduction u/s
    54D/54F/54G/54GA.

    Schema-confirmed: ITR-3's ``LongTermCapGain23.SaleofAssetNADtls.
    SaleofAssetNA`` and ITR-2's own equivalent item (B8) BOTH use the same
    named schema type ``EquityOrUnitSec54Type`` -- but the two forms
    define that name DIFFERENTLY in their own JSON schemas: ITR-2's has a
    flat ``DeductionUs54F`` integer (matching its form item 8's single
    "Deduction under sections 54F" line), while ITR-3's has a nested
    ``ExemptionOrDednUs54`` object supporting "54D"/"54F"/"54G"/"54GA"
    (matching its form item 9's "Deduction under section
    54D/54F/54G/54GA" line) -- the two schemas share a type NAME with an
    incompatible SHAPE, confirmed by direct introspection of both official
    JSON schema files, not assumed from the name alone.
    """
    agg = _aggregate_generic_other_assets(transactions, is_long_term=True)
    valid_sections = ("54D", "54F", "54G", "54GA")
    exemption_by_section = agg["exemption_by_section"]
    exemption_dtls = [
        {"ExemptionSecCode": section, "ExemptionAmount": _to_rupees(exemption_by_section[section])}
        for section in valid_sections if exemption_by_section.get(section)
    ]
    exemption_total = sum((exemption_by_section.get(s, _ZERO) for s in valid_sections), _ZERO)
    capgain_on_assets = agg["balance"] - exemption_total
    return {
        **_consideration_and_deduction_fields(agg),
        "ExemptionOrDednUs54": {
            **({"ExemptionOrDednUs54Dtls": exemption_dtls} if exemption_dtls else {}),
            "ExemptionGrandTotal": _to_rupees(exemption_total),
        },
        "CapgainonAssets": _to_rupees(capgain_on_assets),
    }


def build_stcg_buyback_loss_block(
    loss_20: Decimal, loss_30: Decimal, loss_applicable: Decimal,
) -> dict[str, Any] | None:
    """
    Build Schedule CG's STCG-side ``CapitalLossBuyBackShares`` block --
    Section 46A capital loss on buyback of shares by a domestic company,
    rate-bucketed ("STL20"/"STL30"/"STLAR"). Confirmed identical shape in
    both forms' official JSON schemas by direct introspection. Returns
    ``None`` (the caller omits the key entirely) when there's no such
    loss -- confirmed this field is NOT in either form's own top-level
    ``required`` list, matching this codebase's "no empty placeholder
    objects" convention.
    """
    dtls = []
    if loss_20 < _ZERO:
        dtls.append({"Rate": "STL20", "Amount": _to_rupees(loss_20)})
    if loss_30 < _ZERO:
        dtls.append({"Rate": "STL30", "Amount": _to_rupees(loss_30)})
    if loss_applicable < _ZERO:
        dtls.append({"Rate": "STLAR", "Amount": _to_rupees(loss_applicable)})
    if not dtls:
        return None
    return {
        "CapitalLossBuyBackSharesDtls": dtls,
        "TotalCapitalLossBuyBackShares": _to_rupees(loss_20 + loss_30 + loss_applicable),
    }


def build_ltcg_buyback_loss_block(loss_ltcg: Decimal) -> dict[str, Any] | None:
    """
    Build Schedule CG's LTCG-side ``CapitalLossBuyBackShares`` block --
    unlike the STCG side, the official schema needs only a single flat
    total here (no rate breakdown -- only one LTCG rate applies), confirmed
    by direct introspection. Returns ``None`` when there's no such loss.
    """
    if loss_ltcg >= _ZERO:
        return None
    return {"TotalCapitalLossBuyBackShares": _to_rupees(loss_ltcg)}
