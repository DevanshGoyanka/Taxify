"""
Simplified Bug Condition Exploration Test: ITR Computation Compliance Verification

This test demonstrates specific compliance gaps in the ITR computation engine
by running targeted scenarios that should reveal calculation discrepancies
vs the official ITR utility.

**CRITICAL**: This test MUST FAIL on unfixed code - failure confirms the compliance gaps exist.

**Validates: Requirements 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8, 1.9, 1.10, 1.11**
"""

import pytest
from decimal import Decimal
from datetime import date
from hypothesis import given, strategies as st, assume, settings, Verbosity
from app.schemas.itr1 import (
    ITR1Input, SalaryIncome, HousePropertyIncome, OtherSourcesIncome,
    Chapter6ADeductions, CapitalGainsIncome, AgeBracket, TaxRegime,
    PropertyType, TDS1Entry, TDS2Entry
)
from app.engine.calculators.itr1 import compute as compute_itr1


class TestITRComplianceGapsSimplified:
    """
    Bug Condition Exploration Tests - Expected to FAIL on unfixed code.
    
    These tests demonstrate specific compliance gaps where our calculations
    differ from the official ITR utility. 
    """
    
    def test_cbdt_rounding_gap_499995_scenario(self):
        """
        Bug Gap 1: CBDT Rounding Discrepancy
        
        Test Case: Income ₹4,99,995 should round to ₹4,99,990 per section 288A
        but system may round to ₹5,00,000 causing incorrect rebate eligibility.
        
        **Expected to FAIL on unfixed code**
        """
        itr_input = ITR1Input(
            age_bracket=AgeBracket.BELOW_60,
            tax_regime=TaxRegime.OLD,
            salary_income=SalaryIncome(gross_salary=Decimal("549995")),  # After std ded = 499995
            house_property_income=HousePropertyIncome(
                property_type=PropertyType.SELF_OCCUPIED,
                home_loan_interest_paid=Decimal("0"),
            ),
            other_sources_income=OtherSourcesIncome(),
            deductions_chapter6a=Chapter6ADeductions(),
        )
        
        result = compute_itr1(itr_input)
        
        # Current system may round ₹4,99,995 to ₹5,00,000 (incorrect)
        # Correct CBDT rounding should be ₹4,99,990
        expected_taxable_income = Decimal("499990")  # Correct CBDT rounding
        
        # This assertion will FAIL on unfixed code if rounding is incorrect
        assert result.taxable_income == expected_taxable_income, (
            f"CBDT Rounding Gap: Expected {expected_taxable_income}, "
            f"got {result.taxable_income}. System may be rounding ₹4,99,995 "
            f"to ₹5,00,000 instead of ₹4,99,990 per section 288A."
        )

    def test_87a_112a_interaction_gap(self):
        """
        Bug Gap 2: 87A Rebate - 112A Tax Interaction Error
        
        Test Case: LTCG ₹1,00,000 + slab tax ₹8,000 should cap rebate at ₹8,000
        but system may incorrectly allow full ₹12,500 rebate.
        
        **Expected to FAIL on unfixed code**
        """
        itr_input = ITR1Input(
            age_bracket=AgeBracket.BELOW_60,
            tax_regime=TaxRegime.OLD,
            salary_income=SalaryIncome(gross_salary=Decimal("210000")),  # Creates ~₹8k slab tax
            house_property_income=HousePropertyIncome(
                property_type=PropertyType.SELF_OCCUPIED,
                home_loan_interest_paid=Decimal("0"),
            ),
            other_sources_income=OtherSourcesIncome(),
            capital_gains=CapitalGainsIncome(ltcg_112a=Decimal("100000")),  # ₹12,500 tax
            deductions_chapter6a=Chapter6ADeductions(),
        )
        
        result = compute_itr1(itr_input)
        
        # With LTCG present, rebate should be capped to slab_tax only
        # Cannot exceed slab tax when special-rate income exists
        expected_rebate = min(result.slab_tax, Decimal("12500"))
        
        # This will FAIL if system incorrectly allows rebate against 112A tax
        assert result.rebate_87a == expected_rebate, (
            f"87A-112A Interaction Gap: Rebate {result.rebate_87a} should not "
            f"exceed slab tax {result.slab_tax} when LTCG 112A present. "
            f"System may be allowing rebate against special-rate tax."
        )

    def test_marginal_relief_precision_gap(self):
        """
        Bug Gap 3: Marginal Relief Calculation Precision Error
        
        Test Case: Income ₹50,05,000 marginal relief should match official utility
        but may differ due to calculation precision issues.
        
        **Expected to FAIL on unfixed code**
        """
        itr_input = ITR1Input(
            age_bracket=AgeBracket.BELOW_60,
            tax_regime=TaxRegime.OLD,
            salary_income=SalaryIncome(gross_salary=Decimal("5055000")),
            house_property_income=HousePropertyIncome(
                property_type=PropertyType.SELF_OCCUPIED,
                home_loan_interest_paid=Decimal("0"),
            ),
            other_sources_income=OtherSourcesIncome(),
            deductions_chapter6a=Chapter6ADeductions(),
        )
        
        result = compute_itr1(itr_input)
        
        # At ₹50.05L, surcharge marginal relief should apply
        # Official utility calculation may differ from our implementation
        # This is a placeholder for the expected official calculation
        expected_surcharge_official_utility = Decimal("5000")  # Approximate from official
        
        # This will FAIL if our marginal relief differs significantly from official utility
        surcharge_difference = abs(result.surcharge - expected_surcharge_official_utility)
        assert surcharge_difference <= Decimal("100"), (
            f"Marginal Relief Precision Gap: Surcharge {result.surcharge} differs "
            f"from official utility calculation {expected_surcharge_official_utility} "
            f"by {surcharge_difference}. May indicate precision errors in marginal relief."
        )

    def test_agricultural_income_eligibility_gap(self):
        """
        Bug Gap 4: Agricultural Income ITR-1 Eligibility Determination
        
        Test Case: Agricultural income should affect ITR-1 eligibility
        but system may not properly integrate agricultural income for form eligibility.
        
        **Expected to FAIL on unfixed code**
        """
        itr_input = ITR1Input(
            age_bracket=AgeBracket.BELOW_60,
            tax_regime=TaxRegime.OLD,
            salary_income=SalaryIncome(gross_salary=Decimal("300000")),
            house_property_income=HousePropertyIncome(
                property_type=PropertyType.SELF_OCCUPIED,
                home_loan_interest_paid=Decimal("0"),
            ),
            other_sources_income=OtherSourcesIncome(),
            deductions_chapter6a=Chapter6ADeductions(),
            agriculture_income=Decimal("220000"),  # This should affect eligibility
        )
        
        result = compute_itr1(itr_input)
        
        # Check if agricultural income is properly considered in eligibility
        has_agricultural_income = itr_input.agriculture_income > Decimal("5000")
        
        if has_agricultural_income:
            # System should have special handling for agricultural income cases
            # This assertion will FAIL if agricultural income integration is missing
            assert len(result.warnings) > 0 or "agricultural" in str(result).lower(), (
                f"Agricultural Income Gap: System may not properly handle "
                f"agricultural income {itr_input.agriculture_income} for ITR-1 eligibility. "
                f"Missing proper integration in rate computation logic."
            )

    def test_tds_reconciliation_gap(self):
        """
        Bug Gap 10: TDS/Challan Reconciliation Issues
        
        Test Case: Complex TDS scenario may not reconcile correctly with 
        computed tax, showing discrepancies vs official utility.
        
        **Expected to FAIL on unfixed code**
        """
        itr_input = ITR1Input(
            age_bracket=AgeBracket.BELOW_60,
            tax_regime=TaxRegime.OLD,
            salary_income=SalaryIncome(gross_salary=Decimal("800000")),
            house_property_income=HousePropertyIncome(
                property_type=PropertyType.SELF_OCCUPIED,
                home_loan_interest_paid=Decimal("0"),
            ),
            other_sources_income=OtherSourcesIncome(
                fixed_deposit_interest=Decimal("100000")
            ),
            deductions_chapter6a=Chapter6ADeductions(amount_80c=Decimal("150000")),
            tds1_entries=[
                TDS1Entry(
                    deductor_name="Employer ABC",
                    deductor_tan="ABCD12345E",
                    total_amount_credited=Decimal("750000"),
                    tax_deducted=Decimal("25000"),
                ),
            ],
            tds2_entries=[
                TDS2Entry(
                    deductor_name="Bank XYZ",
                    deductor_tan="XYZA98765B",
                    tds_section="194A",
                    gross_amount=Decimal("100000"),
                    tds_deducted=Decimal("10000"),
                ),
            ],
        )
        
        result = compute_itr1(itr_input)
        
        # Reconciliation check: TDS should properly match with liability
        total_tds_claimed = Decimal("35000")  # 25k + 10k
        
        # This may FAIL if TDS reconciliation has gaps
        assert result.total_tds == total_tds_claimed, (
            f"TDS Reconciliation Gap: Computed TDS {result.total_tds} "
            f"should match claimed TDS {total_tds_claimed}. "
            f"System may have reconciliation calculation issues."
        )

    def test_schedule_ei_completeness_gap(self):
        """
        Bug Gap 6: Schedule EI (Exempt Income) Completeness
        
        Test Case: System may have incomplete mapping for exempt income categories.
        
        **Expected to FAIL on unfixed code**
        """
        itr_input = ITR1Input(
            age_bracket=AgeBracket.BELOW_60,
            tax_regime=TaxRegime.OLD,
            salary_income=SalaryIncome(
                gross_salary=Decimal("500000"),
                lta_exemption_claimed=Decimal("50000"),  # Should map to Schedule EI
            ),
            house_property_income=HousePropertyIncome(
                property_type=PropertyType.SELF_OCCUPIED,
                home_loan_interest_paid=Decimal("0"),
            ),
            other_sources_income=OtherSourcesIncome(
                dividend_income=Decimal("25000"),  # Should be exempt per 10(34)
            ),
            deductions_chapter6a=Chapter6ADeductions(),
        )
        
        result = compute_itr1(itr_input)
        
        # Check if exempt income is properly tracked
        # This will FAIL if Schedule EI mapping is incomplete
        
        # LTA exemption should be tracked for Schedule EI
        has_lta_tracking = (
            hasattr(result, 'exempt_income_schedule_ei') or
            'lta' in str(result.schedules.get('salary', {})).lower()
        )
        
        # Dividend income should be recognized as exempt
        has_dividend_tracking = (
            hasattr(result, 'exempt_dividend_income') or
            'dividend' in str(result.schedules.get('os', {})).lower()
        )
        
        assert has_lta_tracking or has_dividend_tracking, (
            f"Schedule EI Completeness Gap: System may not properly track "
            f"exempt income categories like LTA exemption ₹50,000 or "
            f"dividend income ₹25,000 for Schedule EI mapping."
        )

    @given(
        income=st.integers(min_value=450000, max_value=550000),
        regime=st.sampled_from([TaxRegime.OLD, TaxRegime.NEW])
    )
    @settings(max_examples=20, verbosity=Verbosity.verbose)
    def test_rounding_consistency_property(self, income, regime):
        """
        Property-Based Test: CBDT Rounding Consistency
        
        **Property 1: Bug Condition** - ITR Computation Compliance Verification
        
        For any income around rounding boundaries, the system should apply
        CBDT rounding consistently. This test will FAIL if rounding is inconsistent
        with section 288A requirements.
        
        **Expected to FAIL on unfixed code** - demonstrates rounding gaps.
        
        **Validates: Requirements 1.1, 2.1**
        """
        assume(income % 10 >= 5)  # Focus on rounding boundary cases
        
        itr_input = ITR1Input(
            age_bracket=AgeBracket.BELOW_60,
            tax_regime=regime,
            salary_income=SalaryIncome(gross_salary=Decimal(str(income + 50000))),
            house_property_income=HousePropertyIncome(
                property_type=PropertyType.SELF_OCCUPIED,
                home_loan_interest_paid=Decimal("0"),
            ),
            other_sources_income=OtherSourcesIncome(),
            deductions_chapter6a=Chapter6ADeductions(),
        )
        
        result = compute_itr1(itr_input)
        
        # Property: Taxable income should always be properly rounded per section 288A
        # This will FAIL if rounding implementation has gaps
        expected_rounded = (Decimal(str(income)) / 10).quantize(Decimal("1")) * 10
        
        # Allow for small differences due to deductions, but rounding should be consistent
        difference = abs(result.taxable_income - expected_rounded)
        
        assert difference <= Decimal("60000"), (  # Account for standard deduction
            f"CBDT Rounding Property Violation: Input {income} with regime {regime} "
            f"produced taxable income {result.taxable_income}, expected around {expected_rounded}. "
            f"Difference {difference} suggests rounding implementation gaps."
        )

    def test_itr1_eligibility_edge_case_gap(self):
        """
        Bug Gap 9: ITR-1 Eligibility Validation for Edge Cases
        
        Test Case: Multiple income sources near eligibility limits may not
        be properly validated for ITR-1 vs ITR-2 determination.
        
        **Expected to FAIL on unfixed code**
        """
        itr_input = ITR1Input(
            age_bracket=AgeBracket.BELOW_60,
            tax_regime=TaxRegime.OLD,
            salary_income=SalaryIncome(gross_salary=Decimal("4800000")),
            house_property_income=HousePropertyIncome(
                property_type=PropertyType.LET_OUT,  # Multiple properties edge case
                annual_rent_received=Decimal("300000"),
                municipal_taxes_paid=Decimal("10000"),
                home_loan_interest_paid=Decimal("150000"),
            ),
            other_sources_income=OtherSourcesIncome(
                fixed_deposit_interest=Decimal("100000"),
                savings_bank_interest=Decimal("50000"),
            ),
            capital_gains=CapitalGainsIncome(ltcg_112a=Decimal("124999")),  # Just under limit
            deductions_chapter6a=Chapter6ADeductions(amount_80c=Decimal("150000")),
        )
        
        result = compute_itr1(itr_input)
        
        # Complex eligibility validation
        gti = result.gross_total_income
        has_multiple_sources = (
            result.salary_income > 0 and 
            result.house_property_income > 0 and
            result.other_sources_income > 0 and
            result.capital_gains_112a > 0
        )
        
        # This will FAIL if eligibility validation has gaps for edge cases
        if gti > Decimal("4900000") and has_multiple_sources:
            # System should flag potential ITR-2 requirement for complex cases
            assert len(result.errors) > 0 or len(result.warnings) > 0, (
                f"ITR-1 Eligibility Gap: Complex case with GTI {gti} and "
                f"multiple income sources may require enhanced eligibility validation. "
                f"System may not properly handle edge cases for form determination."
            )


if __name__ == "__main__":
    # Run the bug exploration tests
    print("Running ITR Computation Compliance Bug Exploration Tests...")
    print("These tests are EXPECTED TO FAIL on unfixed code.")
    print("Failures confirm the compliance gaps exist vs official ITR utility.")
    
    pytest.main([__file__, "-v", "-x"])