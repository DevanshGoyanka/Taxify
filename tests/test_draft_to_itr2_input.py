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
    AccumulatedPfEntry,
    AgriculturalLandParcel,
    AMTCreditEntry,
    AMTDetails,
    BroughtForwardLossEntry,
    DtaaExemptIncomeEntry,
    CGDtaaEntry,
    CGNriProviso48Block,
    CGSection48Block,
    ClubbedIncomeEntry,
    DividendIncome,
    DtaaIncomeEntry,
    Employer,
    ExemptIncomeEntry,
    ForeignAssetEntry,
    ForeignSourceIncomeEntry,
    ForeignTaxReliefEntry,
    GiftIncome,
    HouseProperty,
    ImmovableAssetGain,
    InterestIncome,
    OtherIncomeEntry,
    PassThroughIncomeEntry,
    PersonalInfo,
    ReturnDraft,
    Scrip112A,
    ScheduleSIEntry,
    SalaryNatureRow,
    Section89AEntry,
    SpecialRateIncomeEntry,
    TaxChallan,
    TdsCredit,
    VdaEntry,
    WinningIncome,
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


def test_standard_deduction_not_duplicated_across_multiple_employers() -> None:
    """Regression check for Phase 6i-3 (per the user's explicit request):
    _map_salary() sums every employer's gross salary components into ONE
    SalaryIncome before compute_salary() runs once, so the new-regime
    section 16(ia) standard deduction must stay capped at a single 75000
    total across two employers, not 75000-per-employer (150000)."""
    draft = _filing_ready_itr2_draft()
    draft.employers.append(Employer(id="e2", basic=Decimal("1200000"), tdsDeducted=Decimal("90000")))
    itr2_input, _breakdown = draft_to_itr2_input(draft)

    result = compute_itr2(itr2_input)
    sal_result = result.schedules["salary"]
    assert sal_result.standard_deduction == Decimal("75000")


def test_remaining_section10_exemption_rows_reduce_taxable_salary_for_itr2_too() -> None:
    """draft_to_itr2_input() reuses draft_to_itr1_input.py's own _map_salary()
    wholesale -- the EIC/10(17)/10(14)(i)/10(14)(ii)/115BAC-variant
    undertaxation fix therefore applies to ITR-2 through the exact same
    shared code path, not a separate ITR-2-specific mapping."""
    draft = _filing_ready_itr2_draft()
    draft.employers[0].section10ExemptionRows = [
        SalaryNatureRow(id="r1", natureCode="10(17)", amount=Decimal("30000")),
    ]
    itr2_input, _breakdown = draft_to_itr2_input(draft)
    assert itr2_input.salary_income.other_section10_exempt == Decimal("30000")

    result = compute_itr2(itr2_input)
    sal_result = result.schedules["salary"]
    assert sal_result.exempt_allowances >= Decimal("30000")


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


def test_improvement_financial_year_reaches_itr2_input() -> None:
    """CBDT rule #186: draft.improvementFinancialYear was already collected
    by the frontend but never read into ITR2Input -- a malformed value must
    map to None rather than crashing the pipeline."""
    draft = _filing_ready_itr2_draft()
    draft.capitalGainsSchedule.ltImmovable = [ImmovableAssetGain(
        id="p1", dateOfSale="2025-11-01", dateOfPurchase="2015-04-01",
        fullConsideration=Decimal("8000000"), acquisitionCost=Decimal("3000000"),
        improvementCost=Decimal("500000"), improvementFinancialYear="2018-19",
    )]
    itr2_input, _breakdown = draft_to_itr2_input(draft)
    assert itr2_input.cg_transactions[0].year_of_improvement == "2018-19"

    draft.capitalGainsSchedule.ltImmovable[0].improvementFinancialYear = "FY 2018-2019"
    itr2_input, _breakdown = draft_to_itr2_input(draft)
    assert itr2_input.cg_transactions[0].year_of_improvement is None


def test_nri_dtaa_and_proviso48_fields_reach_itr2_input() -> None:
    """Phase 6i-5: draft_to_itr2_input() must map Schedule CG's NRI-specific
    bare-entry blocks (stSection48/ltNriProviso48/ltForeignAssets, items
    A3/B4/B7) and DTAA claim tables (stDtaa/ltDtaa, items A8/B11) into
    ITR2Input -- previously entirely absent from the mapper despite being
    fully captured by the frontend draft (zero references anywhere in this
    file before this fix)."""
    draft = _filing_ready_itr2_draft()
    draft.capitalGainsSchedule.stSection48 = CGSection48Block(
        nriSttPaid=Decimal("150000"), nriSttNotPaid=Decimal("40000"),
    )
    draft.capitalGainsSchedule.ltNriProviso48 = CGNriProviso48Block(
        ltcgWithoutBenefit=Decimal("700000"), deduction54F=Decimal("100000"),
    )
    draft.capitalGainsSchedule.ltForeignAssets = [
        {"saleValue": "300000", "deduction115F": "50000"},
        {"saleValue": "200000", "deduction115F": "20000"},
    ]
    draft.capitalGainsSchedule.stDtaa = [CGDtaaEntry(
        id="d1", amount=Decimal("25000"), itemNumber="A3b", countryName="Singapore",
        countryCode="65", article="13", treatyRate=Decimal("10"), trcAvailable=True,
        itActSection="111A", itActRate=Decimal("20"), applicableRate=Decimal("10"),
    )]
    draft.capitalGainsSchedule.ltDtaa = [CGDtaaEntry(
        id="d2", amount=Decimal("60000"), itemNumber="B4ciii", countryName="UK",
        countryCode="65", article="14", treatyRate=Decimal("0"), trcAvailable=False,
        itActSection="112", itActRate=Decimal("12.5"), applicableRate=Decimal("0"),
    )]

    itr2_input, _breakdown = draft_to_itr2_input(draft)

    assert itr2_input.cg_nri_stcg_stt_paid == Decimal("150000")
    assert itr2_input.cg_nri_stcg_stt_not_paid == Decimal("40000")
    assert itr2_input.cg_nri_ltcg_without_indexation == Decimal("700000")
    assert itr2_input.cg_nri_ltcg_deduction_54f == Decimal("100000")
    assert itr2_input.cg_nri_115f_sale_value == Decimal("500000")  # 300000 + 200000
    assert itr2_input.cg_nri_115f_deduction == Decimal("70000")  # 50000 + 20000

    assert len(itr2_input.cg_stcg_dtaa_entries) == 1
    stcg_entry = itr2_input.cg_stcg_dtaa_entries[0]
    assert stcg_entry.amount == Decimal("25000")
    assert stcg_entry.country_name == "Singapore"
    assert stcg_entry.sec_it_act == "111A"
    assert stcg_entry.tax_residency_certificate == "Y"
    assert stcg_entry.chargeable_in_india is True

    assert len(itr2_input.cg_ltcg_dtaa_entries) == 1
    ltcg_entry = itr2_input.cg_ltcg_dtaa_entries[0]
    assert ltcg_entry.amount == Decimal("60000")
    assert ltcg_entry.rate_as_per_treaty == Decimal("0")
    assert ltcg_entry.chargeable_in_india is False
    assert ltcg_entry.tax_residency_certificate == "N"

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


def test_pti_hp_and_os_head_income_reaches_gti() -> None:
    """HP-head and OS-head Schedule PTI entries were disclosed in
    SchedulePTIDtls but never reached GTI at all -- STCG/LTCG-head PTI
    entries were already dispatched to Schedule SI, but HP/OS-head entries
    had no calculator path whatsoever, silently understating house-property/
    other-sources income for any taxpayer with pass-through income from
    those two heads."""
    draft = _filing_ready_itr2_draft()
    draft.passThroughIncomeEntries = [
        PassThroughIncomeEntry(
            id="pti1", entityName="ABC REIT", entityPAN="AAATA1234B",
            incomeHead="HP", section="115UA", incomeAmount=Decimal("50000"),
        ),
        PassThroughIncomeEntry(
            id="pti2", entityName="XYZ InvIT", entityPAN="AAATX1234B",
            incomeHead="OS", section="115UB", incomeAmount=Decimal("30000"),
        ),
    ]
    itr2_input, _breakdown = draft_to_itr2_input(draft)
    assert len(itr2_input.pti_entries) == 2

    baseline = compute_itr2(draft_to_itr2_input(_filing_ready_itr2_draft())[0])
    result = compute_itr2(itr2_input)
    assert not result.errors
    assert result.house_property_income == baseline.house_property_income + Decimal("50000")
    assert result.other_sources_income == baseline.other_sources_income + Decimal("30000")


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


def test_lottery_winnings_are_included_in_total_income_and_taxed_at_115bb() -> None:
    """Lottery winnings entered via ScheduleOSWorkspace reach the calculator.

    Regression test for a defect where ``draft.otherSources.winnings`` was
    aggregated into a ``total_winnings`` breakdown figure by the shared
    ``_map_other_sources()`` helper and then discarded -- never becoming
    part of ``ITR2Input`` at all, so winnings entered by the taxpayer were
    silently dropped from both taxable income and Schedule OS's JSON.
    """
    draft = _filing_ready_itr2_draft()
    draft.otherSources.winnings = [WinningIncome(
        id="w1", type="LOTTERY", grossAmount=Decimal("50000"),
    )]
    itr2_input, _breakdown = draft_to_itr2_input(draft)
    assert any(sie.section == "115BB" and sie.gross_income == Decimal("50000") for sie in itr2_input.si_entries)

    baseline = compute_itr2(draft_to_itr2_input(_filing_ready_itr2_draft())[0])
    result = compute_itr2(itr2_input)
    assert not result.errors
    assert result.special_rate_tax > baseline.special_rate_tax
    # Total Income must include the winnings, not just tax them via SI --
    # otherwise `ti - special_rate_income_for_slab` (which already
    # subtracts this same amount) would shrink slab tax on unrelated
    # income without the winnings ever having been added.
    assert result.other_sources_income == baseline.other_sources_income + Decimal("50000")
    assert result.gross_total_income == baseline.gross_total_income + Decimal("50000")


def test_accumulated_pf_maps_to_section_111_si_entry_and_pf_totals() -> None:
    """Accumulated recognised-PF balance reaches Schedule SI section 111."""
    draft = _filing_ready_itr2_draft()
    draft.otherSources.accumulatedPf = [AccumulatedPfEntry(
        id="pf1", assessmentYear="2024-25",
        incomeBenefit=Decimal("30000"), taxBenefit=Decimal("3000"),
    )]
    itr2_input, _breakdown = draft_to_itr2_input(draft)
    assert any(sie.section == "111" and sie.gross_income == Decimal("30000") for sie in itr2_input.si_entries)
    assert itr2_input.os_pf_income_benefit == Decimal("30000")
    assert itr2_input.os_pf_tax_benefit == Decimal("3000")

    baseline = compute_itr2(draft_to_itr2_input(_filing_ready_itr2_draft())[0])
    result = compute_itr2(itr2_input)
    assert not result.errors
    assert result.other_sources_income == baseline.other_sources_income + Decimal("30000")


def test_taxable_gift_from_non_relative_is_included_income_56_2_x() -> None:
    """A cash gift from a non-relative exceeding INR 50,000 is fully taxable.

    Regression test: ``draft.otherSources.gifts`` had no mapping into
    ``OtherSourcesIncome.income_56_2_x`` at all for ITR-2 -- gifts were
    entirely dropped from taxable income.
    """
    draft = _filing_ready_itr2_draft()
    draft.otherSources.gifts = [GiftIncome(
        id="g1", propertyType="CASH", value=Decimal("100000"),
        donorName="Friend", fromRelative=False, receivedOnMarriage=False,
        considerationKind="WITHOUT_CONSIDERATION",
    )]
    itr2_input, _breakdown = draft_to_itr2_input(draft)
    assert itr2_input.other_sources_income.income_56_2_x == Decimal("100000")
    assert itr2_input.os_gift_breakdown is not None
    assert itr2_input.os_gift_breakdown.aggregate_without_consideration == Decimal("100000")

    baseline = compute_itr2(draft_to_itr2_input(_filing_ready_itr2_draft())[0])
    result = compute_itr2(itr2_input)
    assert not result.errors
    assert result.other_sources_income == baseline.other_sources_income + Decimal("100000")


def test_gift_from_relative_is_exempt() -> None:
    """A gift from a relative is statutorily exempt regardless of amount."""
    draft = _filing_ready_itr2_draft()
    draft.otherSources.gifts = [GiftIncome(
        id="g1", propertyType="CASH", value=Decimal("500000"),
        donorName="Father", fromRelative=True,
        considerationKind="WITHOUT_CONSIDERATION",
    )]
    itr2_input, _breakdown = draft_to_itr2_input(draft)
    assert itr2_input.other_sources_income.income_56_2_x == Decimal("0")
    assert itr2_input.os_gift_breakdown is None


def test_gift_below_fifty_thousand_threshold_is_exempt() -> None:
    """A non-relative cash gift at or under INR 50,000 is not taxable."""
    draft = _filing_ready_itr2_draft()
    draft.otherSources.gifts = [GiftIncome(
        id="g1", propertyType="CASH", value=Decimal("50000"),
        donorName="Colleague", fromRelative=False,
        considerationKind="WITHOUT_CONSIDERATION",
    )]
    itr2_input, _breakdown = draft_to_itr2_input(draft)
    assert itr2_input.other_sources_income.income_56_2_x == Decimal("0")
    assert itr2_input.os_gift_breakdown is None


def test_pti_exempt_income_reaches_exempt_income_schedule() -> None:
    """``draft.exemptIncome.passThroughIncomeNotChargeableToTax`` was
    captured on the frontend/draft schema but never read by the mapper at
    all -- ``_map_exempt_income`` only ever looked at ``otherExemptIncome``,
    so this figure (and Schedule EI's own item 5) was silently dropped."""
    draft = _filing_ready_itr2_draft()
    draft.exemptIncome.passThroughIncomeNotChargeableToTax = Decimal("15000")
    itr2_input, _breakdown = draft_to_itr2_input(draft)
    assert itr2_input.exempt_income is not None
    assert itr2_input.exempt_income.pti_exempt_income == Decimal("15000")


def test_other_exempt_income_preserves_per_clause_classification() -> None:
    """CBDT rules #698-745 (Phase 4): the frontend already captures each
    exempt-income row's own category/subCategory, but _map_exempt_income()
    previously rolled every row into a single undifferentiated
    other_exempt/other_description pair, discarding the per-clause
    classification entirely before it reached ITR2Input."""
    draft = _filing_ready_itr2_draft()
    draft.exemptIncome.otherExemptIncome = [
        ExemptIncomeEntry(category="SRPC", subCategory="10(16)", description="Scholarship", grossAmount=Decimal("20000")),
        ExemptIncomeEntry(category="OTH", subCategory="10(17A)", description="Award", grossAmount=Decimal("5000")),
    ]
    itr2_input, _breakdown = draft_to_itr2_input(draft)
    assert itr2_input.exempt_income is not None
    assert itr2_input.exempt_income.other_exempt == Decimal("25000")
    entries = itr2_input.exempt_income.other_exempt_entries
    assert len(entries) == 2
    assert entries[0].category == "SRPC"
    assert entries[0].sub_category == "10(16)"
    assert entries[0].description == "Scholarship"
    assert entries[0].amount == Decimal("20000")
    assert entries[1].sub_category == "10(17A)"


def test_agricultural_land_parcels_reach_agricultural_income_schedule() -> None:
    """CBDT rule #445: per-parcel land detail was previously never mapped
    despite the frontend already collecting it."""
    draft = _filing_ready_itr2_draft()
    draft.exemptIncome.grossAgriculturalReceipts = Decimal("800000")
    draft.exemptIncome.agriculturalLandParcels = [
        AgriculturalLandParcel(
            nameOfDistrict="Nashik", pinCode="422001", measurementOfLand=Decimal("2.5"),
            ownedFlag="O", irrigatedFlag="IRG",
        ),
    ]
    itr2_input, _breakdown = draft_to_itr2_input(draft)
    assert itr2_input.agricultural_income is not None
    land = itr2_input.agricultural_income.land_details
    assert len(land) == 1
    assert land[0].name_of_district == "Nashik"
    assert land[0].pin_code == "422001"
    assert land[0].owned_flag == "O"


def test_dtaa_exempt_income_reaches_exempt_income_schedule() -> None:
    """CBDT rule #434: item 4's own DTAA-not-chargeable detail rows were
    previously never mapped despite the frontend already collecting them."""
    draft = _filing_ready_itr2_draft()
    draft.exemptIncome.dtaaExemptIncome = [
        DtaaExemptIncomeEntry(
            amountOfIncome=Decimal("30000"), natureOfIncome="Pension",
            countryName="United Kingdom", countryCode="35", articleOfDtaa="18",
            headOfIncome="OS", trcFlag="Y",
        ),
    ]
    itr2_input, _breakdown = draft_to_itr2_input(draft)
    assert itr2_input.exempt_income is not None
    dtaa = itr2_input.exempt_income.dtaa_exempt_entries
    assert len(dtaa) == 1
    assert dtaa[0].amount == Decimal("30000")
    assert dtaa[0].nature_of_income == "Pension"
    assert dtaa[0].tax_residency_certificate == "Y"


def test_unexplained_income_maps_to_115bbe_si_entry_and_is_taxed() -> None:
    """Schedule OS unexplained income (§68/69/etc) reaches a real 115BBE
    Schedule-SI entry and is taxed -- previously had no path into
    ITR2Input at all."""
    draft = _filing_ready_itr2_draft()
    draft.otherSources.unexplainedIncome.cashCreditsUs68 = Decimal("100000")
    draft.otherSources.unexplainedIncome.unexplainedMoneyUs69A = Decimal("50000")
    itr2_input, _breakdown = draft_to_itr2_input(draft)
    assert itr2_input.os_unexplained_income is not None
    assert itr2_input.os_unexplained_income.total == Decimal("150000")
    assert any(
        sie.section == "115BBE" and sie.gross_income == Decimal("150000")
        for sie in itr2_input.si_entries
    )

    baseline = compute_itr2(draft_to_itr2_input(_filing_ready_itr2_draft())[0])
    result = compute_itr2(itr2_input)
    assert not result.errors
    assert result.other_sources_income == baseline.other_sources_income + Decimal("150000")


def test_unexplained_income_combines_with_115bbe_winnings_into_one_entry() -> None:
    """UNEXPLAINED_115BBE-type winnings and the separate unexplainedIncome
    block both feed the same 115BBE bucket, not two competing entries."""
    draft = _filing_ready_itr2_draft()
    draft.otherSources.winnings = [WinningIncome(
        id="w1", type="UNEXPLAINED_115BBE", grossAmount=Decimal("20000"),
    )]
    draft.otherSources.unexplainedIncome.cashCreditsUs68 = Decimal("100000")
    itr2_input, _breakdown = draft_to_itr2_input(draft)
    bbe_entries = [sie for sie in itr2_input.si_entries if sie.section == "115BBE"]
    assert len(bbe_entries) == 1
    assert bbe_entries[0].gross_income == Decimal("120000")


def test_dividend_dtaa_89a_other_income_and_deductions_map_correctly() -> None:
    """Dividend section/quarter detail, DTAA, §89A, other-income, and
    deduction claims all flow from the draft into ITR2Input."""
    draft = _filing_ready_itr2_draft()
    draft.otherSources.dividends = [DividendIncome(
        id="d1", section="DTAA", grossAmount=Decimal("20000"), q2=Decimal("20000"),
    )]
    draft.otherSources.dtaaIncome = [DtaaIncomeEntry(
        id="dt1", amount=Decimal("40000"), natureOfIncome="1ai",
        countryName="Singapore", countryCode="65", dtaaArticle="11",
        rateAsPerTreaty=Decimal("10"), rateAsPerITAct=Decimal("20"),
        taxResidencyCertificate="Y", itemNoIncl="5A1ai", applicableRate=Decimal("10"),
    )]
    draft.otherSources.dtaaAggregates.totalAmountTaxUsDtaa = Decimal("4000")
    draft.otherSources.section89A = [Section89AEntry(id="s1", countryCode="US", amount=Decimal("200000"))]
    draft.otherSources.section89AAggregates.incomeNotified89AOS = Decimal("200000")
    draft.otherSources.section89AAggregates.incomeReliefUs89AOS = Decimal("15000")
    draft.otherSources.otherIncome = [OtherIncomeEntry(
        id="o1", nature="Freelance", amount=Decimal("30000"),
    )]
    draft.otherSources.deductions.expenses = Decimal("2000")

    itr2_input, _breakdown = draft_to_itr2_input(draft)
    assert len(itr2_input.os_dividend_entries) == 1
    assert itr2_input.os_dividend_entries[0].section == "DTAA"
    assert len(itr2_input.os_dtaa_entries) == 1
    assert itr2_input.os_dtaa_aggregate == Decimal("4000")
    assert itr2_input.os_section_89a is not None
    assert itr2_input.os_section_89a.income_notified == Decimal("200000")
    assert itr2_input.os_section_89a.relief == Decimal("15000")
    assert len(itr2_input.os_section_89a.country_entries) == 1
    assert len(itr2_input.os_other_income_entries) == 1
    assert itr2_input.os_deductions is not None
    assert itr2_input.os_deductions.expenses == Decimal("2000")

    result = compute_itr2(itr2_input)
    assert not result.errors


def test_special_rate_income_entries_map_and_are_taxed_at_correct_nri_rate() -> None:
    """draft.otherSources.specialRateIncome rows (Section 115A/115AC/
    115ACA/115AD/115E "any other income chargeable at special rate" family)
    flow into os_special_rate_entries, get taxed via Schedule SI at the
    correct statutory rate per code, and are added to GTI -- previously had
    no mapping into ITR2Input at all."""
    draft = _filing_ready_itr2_draft()
    draft.otherSources.specialRateIncome = [
        SpecialRateIncomeEntry(id="s1", sourceDescription="5A1bA", sourceAmount=Decimal("100000")),
        SpecialRateIncomeEntry(id="s2", sourceDescription="5AD1i", sourceAmount=Decimal("50000")),
    ]
    itr2_input, _breakdown = draft_to_itr2_input(draft)
    assert len(itr2_input.os_special_rate_entries) == 2
    codes = {e.source_description for e in itr2_input.os_special_rate_entries}
    assert codes == {"5A1bA", "5AD1i"}

    baseline = compute_itr2(draft_to_itr2_input(_filing_ready_itr2_draft())[0])
    result = compute_itr2(itr2_input)
    assert not result.errors
    assert result.other_sources_income == baseline.other_sources_income + Decimal("150000")
    si_by_section = {sie.section: sie for sie in result.schedules["si"].entries}
    assert si_by_section["5A1bA"].tax_rate_pct == Decimal("20")
    assert si_by_section["5A1bA"].tax_amount == Decimal("20000")
    assert si_by_section["5AD1i"].tax_rate_pct == Decimal("20")


def test_special_rate_income_zero_amount_rows_are_excluded() -> None:
    """A zero-amount specialRateIncome row (a blank/unfilled UI row) is
    dropped, matching every other Schedule OS entry mapper's convention."""
    draft = _filing_ready_itr2_draft()
    draft.otherSources.specialRateIncome = [
        SpecialRateIncomeEntry(id="s1", sourceDescription="5A1bA", sourceAmount=Decimal("0")),
    ]
    itr2_input, _breakdown = draft_to_itr2_input(draft)
    assert itr2_input.os_special_rate_entries == []


def test_dtaa_os_income_is_taxed_at_applicable_rate_and_reaches_gti() -> None:
    """draft.otherSources.dtaaIncome rows were previously disclosure-only
    (NRIDTAADtlsSchOS) -- never taxed, never added to GTI. Each entry's own
    per-treaty applicableRate now drives a dedicated Schedule SI "DTAAOS"
    entry, and the amount reaches Gross Total Income, matching every other
    special-rate OS category's treatment."""
    draft = _filing_ready_itr2_draft()
    draft.otherSources.dtaaIncome = [DtaaIncomeEntry(
        id="dt1", amount=Decimal("100000"), natureOfIncome="1b",
        countryName="Singapore", countryCode="65", dtaaArticle="12",
        rateAsPerTreaty=Decimal("10"), rateAsPerITAct=Decimal("20"),
        taxResidencyCertificate="Y", itemNoIncl="5A1bA", applicableRate=Decimal("10"),
    )]
    itr2_input, _breakdown = draft_to_itr2_input(draft)
    assert len(itr2_input.os_dtaa_entries) == 1
    assert itr2_input.os_dtaa_entries[0].applicable_rate == Decimal("10")

    baseline = compute_itr2(draft_to_itr2_input(_filing_ready_itr2_draft())[0])
    result = compute_itr2(itr2_input)
    assert not result.errors
    assert result.other_sources_income == baseline.other_sources_income + Decimal("100000")
    dtaa_entries = [e for e in result.schedules["si"].entries if e.section == "DTAAOS"]
    assert len(dtaa_entries) == 1
    assert dtaa_entries[0].tax_rate_pct == Decimal("10")
    assert dtaa_entries[0].tax_amount == Decimal("10000")


def test_race_horse_activity_winnings_map_to_os_race_horse() -> None:
    """RACE_HORSE_ACTIVITY winnings map to os_race_horse, distinct from the
    other WinningIncomeType categories that route to Schedule SI."""
    draft = _filing_ready_itr2_draft()
    draft.otherSources.winnings = [WinningIncome(
        id="w1", type="RACE_HORSE_ACTIVITY", receipts=Decimal("500000"),
        deductionUs57=Decimal("300000"), balance=Decimal("200000"),
    )]
    itr2_input, _breakdown = draft_to_itr2_input(draft)
    assert itr2_input.os_race_horse is not None
    assert itr2_input.os_race_horse.receipts == Decimal("500000")
    assert itr2_input.os_race_horse.balance == Decimal("200000")
    assert not any(sie.section in {"115BB", "115BBJ", "115BBE"} for sie in itr2_input.si_entries)

    baseline = compute_itr2(draft_to_itr2_input(_filing_ready_itr2_draft())[0])
    result = compute_itr2(itr2_input)
    assert not result.errors
    assert result.other_sources_income == baseline.other_sources_income + Decimal("200000")


def test_machinery_rent_income_maps_net_of_deductions_without_double_counting() -> None:
    """MACHINERY_RENT-tagged otherIncome rows route to os_machinery_plant_rent
    (net of its own expenses/depreciation deductions, added to GTI), not to
    the generic other_income aggregate -- which would otherwise double-tax
    it (once gross via the shared aggregate, once net via this field)."""
    draft = _filing_ready_itr2_draft()
    draft.otherSources.otherIncome = [OtherIncomeEntry(
        id="o1", nature="MACHINERY_RENT", amount=Decimal("100000"),
    )]
    draft.otherSources.deductions.expenses = Decimal("30000")
    draft.otherSources.deductions.depreciation = Decimal("20000")
    itr2_input, _breakdown = draft_to_itr2_input(draft)
    assert itr2_input.os_machinery_plant_rent == Decimal("100000")
    # Backed out of the generic aggregate to prevent double-counting.
    assert itr2_input.other_sources_income.other_income == Decimal("0")

    baseline = compute_itr2(draft_to_itr2_input(_filing_ready_itr2_draft())[0])
    result = compute_itr2(itr2_input)
    assert not result.errors
    # 100000 - 30000 - 20000 = 50000 net, added to GTI.
    assert result.other_sources_income == baseline.other_sources_income + Decimal("50000")


def test_pass_through_income_is_disclosed_and_not_double_counted() -> None:
    """PASS_THROUGH-tagged otherIncome is backed out of the generic
    aggregate (it is disclosure-only, already taxed as ordinary income
    elsewhere per the frontend's own "at normal rate" label) but not lost
    -- it reaches os_pass_through_income for NatofPassThrghIncome. The
    remaining "OTHER"-natured row is likewise backed out of the generic
    aggregate: it is taxed exclusively via os_other_income_entries (see
    the os_other_income_entries undertaxation-gap fix), not the generic
    aggregate too -- otherwise it would be double-counted the same way
    PASS_THROUGH almost was."""
    draft = _filing_ready_itr2_draft()
    draft.otherSources.otherIncome = [
        OtherIncomeEntry(id="o1", nature="PASS_THROUGH", amount=Decimal("15000")),
        OtherIncomeEntry(id="o2", nature="OTHER", description="Freelance", amount=Decimal("5000")),
    ]
    itr2_input, _breakdown = draft_to_itr2_input(draft)
    assert itr2_input.os_pass_through_income == Decimal("15000")
    assert itr2_input.other_sources_income.other_income == Decimal("0")
    assert len(itr2_input.os_other_income_entries) == 1
    assert itr2_input.os_other_income_entries[0].amount == Decimal("5000")


def test_pf_interest_proviso_kinds_map_to_dedicated_fields() -> None:
    """PF interest-proviso interest kinds are categorized separately, not
    collapsed into the generic other-income aggregate."""
    draft = _filing_ready_itr2_draft()
    draft.otherSources.interest = [
        InterestIncome(id="i1", kind="PF_10_11_FIRST", grossAmount=Decimal("1000")),
        InterestIncome(id="i2", kind="PF_10_12_SECOND", grossAmount=Decimal("2000")),
        InterestIncome(id="i3", kind="BONDS", grossAmount=Decimal("500")),
    ]
    itr2_input, _breakdown = draft_to_itr2_input(draft)
    assert itr2_input.os_pf_interest_10_11_first_proviso == Decimal("1000")
    assert itr2_input.os_pf_interest_10_12_second_proviso == Decimal("2000")
    assert itr2_input.os_interest_from_others == Decimal("500")


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


def test_section_80qqb_and_80rrb_reach_itr2_input() -> None:
    """Regression for Phase 6b: section80QQB/section80RRB/
    section80QQBRoyaltyIncome (draft.deductions.chapterVIA.*) were never
    read by draft_to_itr2_input() at all -- a taxpayer who filled either
    claim on the frontend had it silently vanish before compute or filing.
    Also the exact test that would have caught this fix's own first
    attempt using the wrong field path (draft.deductions.section80QQB
    instead of the real draft.deductions.chapterVIA.section80QQB) --
    ITR2Input-level tests alone (which skip draft_to_itr2_input entirely)
    do not exercise this mapping at all."""
    draft = _filing_ready_itr2_draft()
    draft.regime = "old"
    draft.deductions.chapterVIA.section80QQB = Decimal("250000")
    draft.deductions.chapterVIA.section80QQBRoyaltyIncome = Decimal("200000")
    draft.deductions.chapterVIA.section80RRB = Decimal("100000")
    draft.deductions.chapterVIA.section80QQBForm10CCDAckNum = "ACK123456"
    draft.deductions.chapterVIA.section80RRBForm10CCEAckNum = "ACK654321"
    itr2_input, _breakdown = draft_to_itr2_input(draft)
    assert itr2_input.deduction_80qqb == Decimal("250000")
    assert itr2_input.royalty_income_80qqb == Decimal("200000")
    assert itr2_input.deduction_80rrb == Decimal("100000")
    # CBDT rules #648/#649: Form 10CCD/10CCE acknowledgement numbers, also
    # collected by the frontend but never read into ITR2Input until now.
    assert itr2_input.form_10ccd_ack_number_80qqb == "ACK123456"
    assert itr2_input.form_10cce_ack_number_80rrb == "ACK654321"
    result = compute_itr2(itr2_input)
    assert not result.errors
    ded = result.schedules["deductions"]
    assert ded.breakdown["80QQB"] == Decimal("200000")
    assert ded.breakdown["80RRB"] == Decimal("100000")


def test_pran_number_reaches_itr2_input() -> None:
    """Regression for Phase 6c: draft.deductions.chapterVIA.pranNumber (the
    same shared ReturnDraft field ITR-1's own mapper already reads for its
    ITR1Input.pran_number) was never read into ITR2Input at all -- ITR2Input
    had no pran_number field, so a Section 80CCH (Agniveer Corpus Fund) PRAN
    entered on the frontend had it silently discarded."""
    draft = _filing_ready_itr2_draft()
    draft.deductions.chapterVIA.pranNumber = "123456789012"
    itr2_input, _breakdown = draft_to_itr2_input(draft)
    assert itr2_input.pran_number == "123456789012"


def test_form10f_filed_reaches_itr2_input() -> None:
    """Regression for Phase 6i-1: ForeignTaxReliefEntry.form10FFiled was
    never read into ITR2Input's TR1Entry.form_10f_filed at all -- the field
    didn't exist on either side until this fix, so this is also the
    mapper-level test that confirms the wiring, not just the schema field."""
    draft = _filing_ready_itr2_draft()
    draft.foreignSourceIncome = [ForeignSourceIncomeEntry(
        id="fsi1", countryCode="US", taxIdentificationNo="123-45-6789",
        salaryIncome=Decimal("500000"), taxPaidOutsideIndia=Decimal("75000"),
        taxPayableInIndia=Decimal("90000"),
    )]
    draft.foreignTaxRelief = [ForeignTaxReliefEntry(
        id="tr1", countryCode="US", taxIdentificationNo="123-45-6789",
        incomeIncludedInThisReturn=Decimal("500000"),
        taxPaidOutsideIndia=Decimal("75000"), indianTaxPayable=Decimal("90000"),
        reliefClaimed=Decimal("75000"), form10FFiled=True,
    )]
    itr2_input, _breakdown = draft_to_itr2_input(draft)
    assert len(itr2_input.tr1_entries) == 1
    assert itr2_input.tr1_entries[0].form_10f_filed is True
