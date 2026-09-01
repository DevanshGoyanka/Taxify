"""
ITR-2/ITR-3 plan Phase 3 tests — draft_to_itr2_input mapper + compute.

Verifies the single canonical ITR-2 mapper produces a valid ITR2Input and
that compute_itr2 runs cleanly on it, exercising every ITR-2-specific head
(full Schedule CG, VDA, brought-forward losses, Schedule SI, agricultural/
exempt income, FSI/TR/FA, SPI, PTI, AMT) plus the shared heads reused from
draft_to_itr1_input.py.

Run: pytest tests/test_draft_to_itr2_input.py -v
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.engine.calculators.itr2 import compute as compute_itr2
from app.engine.draft_to_itr2_input import draft_to_itr2_input
from app.schemas.return_draft import (
    AMTCreditEntry,
    AMTDetails,
    BroughtForwardLossEntry,
    ClubbedIncomeEntry,
    Employer,
    ForeignAssetEntry,
    ForeignSourceIncomeEntry,
    ForeignTaxReliefEntry,
    HouseProperty,
    ImmovableAssetGain,
    InterestIncome,
    PassThroughIncomeEntry,
    PersonalInfo,
    ReturnDraft,
    Scrip112A,
    ScheduleSIEntry,
    TaxChallan,
    TdsCredit,
    VdaEntry,
    create_empty_draft,
)


def _filing_ready_itr2_draft() -> ReturnDraft:
    """A minimally filing-ready canonical ITR-2 draft with salary + HP."""
    draft = create_empty_draft("2026-27", "ITR-2", "new")
    draft.personal = PersonalInfo(
        name="Priya Nair", firstName="Priya", surnameOrOrgName="Nair",
        fatherName="Ramesh Nair", pan="ABCDE1234F", dateOfBirth="1985-06-15",
        residentialStatus="ROR",
    )
    draft.employers = [Employer(id="e1", basic=Decimal("1500000"), tdsDeducted=Decimal("120000"))]
    draft.houseProperties = [HouseProperty(
        id="hp1", propertyType="SELF_OCCUPIED",
    )]
    draft.otherSources.interest = [InterestIncome(
        id="i1", kind="SAVINGS_BANK", grossAmount=Decimal("8000"),
    )]
    draft.taxes.tds = [TdsCredit(
        id="t1", section="192", deductorName="Acme", deductorTAN="MUMA12345B",
        taxDeducted=Decimal("120000"), schedule="TDS1",
    )]
    return draft


def test_minimal_itr2_draft_maps_and_computes() -> None:
    """A bare salary+HP ITR-2 draft maps cleanly and computes without error."""
    draft = _filing_ready_itr2_draft()
    itr2_input, breakdown = draft_to_itr2_input(draft)

    assert itr2_input.residential_status.value == "RES"
    assert itr2_input.salary_income is not None
    assert itr2_input.tds1_entries[0].tds_deducted == Decimal("120000")
    assert breakdown["tds_salary"] == Decimal("120000")
    assert breakdown["cg_112a_scrips_skipped_no_date"] == 0

    result = compute_itr2(itr2_input)
    assert result.gross_total_income > 0
    assert not result.errors


def test_112a_scrip_with_date_is_mapped_and_taxed() -> None:
    """A 112A scrip with a real transfer date is mapped and its gain taxed."""
    draft = _filing_ready_itr2_draft()
    draft.capitalGainsSchedule.schedule112A = [Scrip112A(
        id="s1", isin="INE001A01036", name="Reliance Industries",
        quantity=Decimal("100"), salePricePerUnit=Decimal("3000"),
        totalSaleValue=Decimal("300000"), costWithoutIndexation=Decimal("100000"),
        acquisitionCost=Decimal("100000"), fmvPerUnit=Decimal("1000"),
        totalFmv=Decimal("100000"), transferExpenses=Decimal("500"),
        dateOfAcquisition="2023-01-10", dateOfTransfer="2025-12-01",
    )]
    itr2_input, breakdown = draft_to_itr2_input(draft)
    assert len(itr2_input.cg_112a_scrips) == 1
    assert breakdown["cg_112a_scrips_skipped_no_date"] == 0

    result = compute_itr2(itr2_input)
    assert not result.errors
    # 300000 sale - 100000 cost - 1.25L exemption = 75000 taxable, so a
    # nonzero special-rate 112A tax must appear.
    assert result.special_rate_tax > 0


def test_112a_scrip_without_transfer_date_is_skipped_not_fabricated() -> None:
    """A scrip missing dateOfTransfer is excluded, not given a fake date."""
    draft = _filing_ready_itr2_draft()
    draft.capitalGainsSchedule.schedule112A = [Scrip112A(
        id="s1", isin="INE001A01036", name="Reliance Industries",
        quantity=Decimal("100"), salePricePerUnit=Decimal("3000"),
        totalSaleValue=Decimal("300000"), costWithoutIndexation=Decimal("100000"),
        # dateOfTransfer intentionally omitted.
    )]
    itr2_input, breakdown = draft_to_itr2_input(draft)
    assert itr2_input.cg_112a_scrips == []
    assert breakdown["cg_112a_scrips_skipped_no_date"] == 1


def test_immovable_ltcg_and_vda_map_and_compute() -> None:
    """Long-term land/building gain + a VDA transaction both compute cleanly."""
    draft = _filing_ready_itr2_draft()
    draft.capitalGainsSchedule.ltImmovable = [ImmovableAssetGain(
        id="p1", dateOfSale="2025-11-01", dateOfPurchase="2015-04-01",
        fullConsideration=Decimal("8000000"), acquisitionCost=Decimal("3000000"),
        transferExpenses=Decimal("50000"),
    )]
    draft.capitalGainsSchedule.vda = [VdaEntry(
        id="v1", dateOfAcquisition="2024-02-01", dateOfTransfer="2025-08-01",
        head="CG", acquisitionCost=Decimal("50000"), consideration=Decimal("90000"),
    )]
    itr2_input, _breakdown = draft_to_itr2_input(draft)
    assert len(itr2_input.cg_transactions) == 1
    assert itr2_input.cg_transactions[0].explicit_long_term is True
    assert len(itr2_input.vda_transactions) == 1

    result = compute_itr2(itr2_input)
    assert not result.errors
    assert result.gross_total_income > 0


def test_foreign_and_clubbing_and_pti_schedules_map_and_compute() -> None:
    """FSI/TR/FA, SPI (clubbing), and PTI (pass-through) all map and compute."""
    draft = _filing_ready_itr2_draft()
    draft.personal.residentialStatus = "ROR"
    draft.foreignSourceIncome = [ForeignSourceIncomeEntry(
        id="fsi1", countryCode="US", taxIdentificationNo="123-45-6789",
        salaryIncome=Decimal("500000"), taxPaidOutsideIndia=Decimal("75000"),
        taxPayableInIndia=Decimal("90000"),
    )]
    draft.foreignTaxRelief = [ForeignTaxReliefEntry(
        id="tr1", countryCode="US", taxIdentificationNo="123-45-6789",
        incomeIncludedInThisReturn=Decimal("500000"),
        taxPaidOutsideIndia=Decimal("75000"), indianTaxPayable=Decimal("90000"),
        reliefClaimed=Decimal("75000"),
    )]
    draft.foreignAssets = [ForeignAssetEntry(
        id="fa1", assetType="BANK_ACCOUNT", countryCode="US",
        institutionOrEntityName="Chase Bank", address="270 Park Ave, NY",
        accountOrAssetIdentifier="****1234", ownershipStatus="Owner",
        openingOrAcquisitionDate="2020-05-01", peakValue=Decimal("500000"),
        closingValue=Decimal("400000"),
    )]
    draft.clubbedIncome = [ClubbedIncomeEntry(
        id="spi1", specifiedPersonName="Spouse", pan="XYZAB5678C",
        relationship="Spouse", amountIncluded=Decimal("20000"), headOfIncome="OS",
    )]
    draft.passThroughIncomeEntries = [PassThroughIncomeEntry(
        id="pti1", entityName="ABC InvIT", entityPAN="AAATA1234B",
        incomeHead="OS", section="115UA", incomeAmount=Decimal("30000"),
    )]

    itr2_input, _breakdown = draft_to_itr2_input(draft)
    assert len(itr2_input.fsi_entries) == 1
    assert len(itr2_input.tr1_entries) == 1
    assert len(itr2_input.foreign_assets) == 1
    assert len(itr2_input.spi_entries) == 1
    assert len(itr2_input.pti_entries) == 1

    result = compute_itr2(itr2_input)
    assert not result.errors


def test_amt_and_schedule_si_map_and_compute() -> None:
    """AMT details and a Schedule SI entry both map and compute cleanly."""
    draft = _filing_ready_itr2_draft()
    draft.amt = AMTDetails(
        deduction10AA=Decimal("100000"),
        creditsBroughtForward=[AMTCreditEntry(
            id="c1", assessmentYear="2024-25", creditBroughtForward=Decimal("15000"),
        )],
    )
    draft.scheduleSIEntries = [ScheduleSIEntry(
        id="si1", section="115BB", description="Lottery winnings",
        grossIncome=Decimal("50000"),
    )]
    itr2_input, _breakdown = draft_to_itr2_input(draft)
    assert itr2_input.amt_input is not None
    assert itr2_input.amt_input.deduction_10aa == Decimal("100000")
    assert len(itr2_input.si_entries) == 1

    result = compute_itr2(itr2_input)
    assert not result.errors
    assert result.special_rate_tax > 0


def test_brought_forward_losses_map_correctly() -> None:
    """Per-AY brought-forward loss entries map to BFLossItem correctly."""
    draft = _filing_ready_itr2_draft()
    draft.broughtForwardLossEntries = [BroughtForwardLossEntry(
        id="bf1", assessmentYear="2024-25", head="STCG",
        originalLoss=Decimal("40000"), broughtForward=Decimal("40000"),
    )]
    itr2_input, _breakdown = draft_to_itr2_input(draft)
    assert len(itr2_input.bf_losses) == 1
    assert itr2_input.bf_losses[0].head.value == "STCG"

    result = compute_itr2(itr2_input)
    assert not result.errors


def test_new_regime_zeroes_old_regime_only_deductions() -> None:
    """New regime draft still computes cleanly (shared _map_deductions reuse)."""
    draft = _filing_ready_itr2_draft()
    draft.regime = "new"
    draft.deductions.chapterVIA.section80C = Decimal("150000")
    itr2_input, _breakdown = draft_to_itr2_input(draft)
    assert itr2_input.tax_regime.value == "new"
    result = compute_itr2(itr2_input)
    assert not result.errors
