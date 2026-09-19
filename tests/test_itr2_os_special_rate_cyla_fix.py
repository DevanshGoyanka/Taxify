"""Tests for two ITR-2 Schedule OS/CYLA bugs found and fixed on 2026-09-19
while investigating the equivalent gap for ITR-3 (user asked to "check if
Schedule OS for ITR-2 is fully compliant" before porting to ITR-3, to
avoid baking the same bugs into the port).

**Bug 1**: `CYLAInput.non_salary_income` blended special-rate Other
Sources income (lottery/115BB, 115BBJ, unexplained income/115BBE,
accumulated PF/111, patent royalty/115BBF, carbon credits/115BBG,
non-resident sportsmen/115BBA, the NRI/FII 115A-family dropdown, and
DTAA-rate OS income) into the SAME pool used for ordinary cross-head loss
absorption (HP-loss/business-loss set-off). Section 58(4) and the
official form's own Schedule CYLA structure (rows i-xiv) provide no
current-year-loss set-off row for any of these special-rate categories --
only for normal-rate OS income (row x), race horse (row xi, already
correctly excluded via its own dedicated field), and DTAA-rate income
(row xii, disclosure-only passthrough). Confirmed live: a ₹2,00,000 HP
loss against ₹5,00,000 of PURE lottery income was fully "absorbed",
understating GTI and silently extinguishing a loss that should have
carried forward to Schedule CFL instead. This was a known-but-unresolved
gap -- `Docs/ITR2_VALIDATOR_GAP_MAPPING_AY2026_27.md` row #260 had already
named the exact line as "proof pending" without ever closing it out.

**Bug 2**: Schedule OS items 4/5 ("Amounts not deductible u/s 58",
"Profits chargeable to tax u/s 59") were wrongly gated behind
`os_machinery_plant_rent` being nonzero, even though they are standalone
Schedule-OS lines per the official form's own item numbering, not
sub-items of machinery/plant/furniture letting income. A standalone
balancing charge/disallowed amount with no letting income at all was
disclosed in the filed JSON but never actually taxed.
"""

from __future__ import annotations

from decimal import Decimal

from app.engine.calculators.itr2 import compute as compute_itr2
from app.schemas.itr1 import HousePropertyIncome, PropertyType
from app.schemas.itr2 import ITR2Input, OSDeductions, OSSpecialRateEntry, OSDtaaEntry, ScheduleSIEntry


# ---------------------------------------------------------------------------
# Bug 1: special-rate OS income must not be eligible for CYLA loss set-off.
# ---------------------------------------------------------------------------

def test_hp_loss_does_not_absorb_against_lottery_income() -> None:
    typed = ITR2Input(
        age_bracket="below_60", tax_regime="old",
        house_properties=[HousePropertyIncome(
            property_type=PropertyType.SELF_OCCUPIED,
            home_loan_interest_paid=Decimal("200000"),
        )],
        si_entries=[ScheduleSIEntry(section="115BB", gross_income=Decimal("500000"), tax_rate_pct=Decimal("30"))],
    )
    r = compute_itr2(typed)
    assert r.house_property_income == Decimal("-200000")
    assert r.cyla_total_set_off == Decimal("0")
    assert r.gross_total_income == Decimal("500000")


def test_hp_loss_does_not_absorb_against_nri_special_rate_entry() -> None:
    typed = ITR2Input(
        age_bracket="below_60", tax_regime="old",
        house_properties=[HousePropertyIncome(
            property_type=PropertyType.SELF_OCCUPIED,
            home_loan_interest_paid=Decimal("200000"),
        )],
        os_special_rate_entries=[OSSpecialRateEntry(source_description="5A1ai", source_amount=Decimal("500000"))],
    )
    r = compute_itr2(typed)
    assert r.cyla_total_set_off == Decimal("0")
    assert r.gross_total_income == Decimal("500000")


def test_hp_loss_does_not_absorb_against_dtaa_os_income() -> None:
    typed = ITR2Input(
        age_bracket="below_60", tax_regime="old",
        house_properties=[HousePropertyIncome(
            property_type=PropertyType.SELF_OCCUPIED,
            home_loan_interest_paid=Decimal("200000"),
        )],
        os_dtaa_entries=[OSDtaaEntry(
            amount=Decimal("500000"), nature_of_income="1c", country_name="USA", country_code="US",
            dtaa_article="11", rate_as_per_treaty=Decimal("15"), rate_as_per_it_act=Decimal("30"),
            tax_residency_certificate="Y", item_no_incl="1c", applicable_rate=Decimal("15"),
        )],
    )
    r = compute_itr2(typed)
    assert r.cyla_total_set_off == Decimal("0")
    assert r.gross_total_income == Decimal("500000")


def test_hp_loss_still_absorbs_against_normal_rate_os_income() -> None:
    """No regression: ordinary (non-special-rate) OS income must remain a
    valid CYLA absorption target, exactly as before."""
    from app.schemas.itr1 import OtherSourcesIncome

    typed = ITR2Input(
        age_bracket="below_60", tax_regime="old",
        house_properties=[HousePropertyIncome(
            property_type=PropertyType.SELF_OCCUPIED,
            home_loan_interest_paid=Decimal("200000"),
        )],
        other_sources_income=OtherSourcesIncome(savings_bank_interest=Decimal("500000")),
    )
    r = compute_itr2(typed)
    assert r.cyla_total_set_off == Decimal("200000")
    assert r.gross_total_income == Decimal("300000")


# ---------------------------------------------------------------------------
# Bug 2: items 4/5 must apply regardless of machinery-rent presence.
# ---------------------------------------------------------------------------

def test_item5_addback_taxed_without_machinery_rent() -> None:
    typed = ITR2Input(
        age_bracket="below_60", tax_regime="new",
        os_deductions=OSDeductions(profit_chargeable_us59=Decimal("50000")),
    )
    r = compute_itr2(typed)
    assert r.other_sources_income == Decimal("50000")
    assert r.gross_total_income == Decimal("50000")


def test_item4_addback_taxed_without_machinery_rent() -> None:
    typed = ITR2Input(
        age_bracket="below_60", tax_regime="new",
        os_deductions=OSDeductions(amount_not_deductible_us58=Decimal("30000")),
    )
    r = compute_itr2(typed)
    assert r.other_sources_income == Decimal("30000")


def test_item4_5_addback_still_taxed_with_machinery_rent_present() -> None:
    """No regression: the original (already-working) case, machinery rent
    plus items 4/5 together, must still both be taxed."""
    typed = ITR2Input(
        age_bracket="below_60", tax_regime="new",
        os_machinery_plant_rent=Decimal("100000"),
        os_deductions=OSDeductions(profit_chargeable_us59=Decimal("50000")),
    )
    r = compute_itr2(typed)
    assert r.other_sources_income == Decimal("150000")
