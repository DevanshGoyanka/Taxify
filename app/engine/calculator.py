"""
ITR-1 and ITR-4 Tax Computation Engine.

Provides clean, explicit functions to compute taxable income, deductions,
slab-wise tax, 87A rebate, surcharge (with marginal relief), and
health/education cess for AY 2026-27.

All per-slab and cess rounding uses ROUND_HALF_EVEN (banker's rounding)
to match the ITD VBA engine behaviour as implemented in OpenTax.
"""

from decimal import Decimal, ROUND_HALF_UP, ROUND_HALF_EVEN
from typing import Dict, Any, Union
from app.schemas.itr1 import ITR1Input, PropertyType, AgeBracket, TaxRegime
from app.schemas.itr4 import ITR4Input, PresumptiveScheme
from app.engine.constants import (
    OLD_REGIME_SLABS_BELOW_60,
    OLD_REGIME_SLABS_60_TO_80,
    OLD_REGIME_SLABS_ABOVE_80,
    NEW_REGIME_SLABS_AY_2026_27,
    OLD_REGIME_STANDARD_DEDUCTION,
    NEW_REGIME_STANDARD_DEDUCTION,
    OLD_REBATE_TAX_LIMIT,
    OLD_REBATE_INCOME_LIMIT,
    NEW_REBATE_TAX_LIMIT,
    NEW_REBATE_INCOME_LIMIT,
    HEALTH_EDUCATION_CESS_RATE,
    HOUSE_PROPERTY_STANDARD_DEDUCTION,
    HOUSE_PROPERTY_INTEREST_LIMIT_SELF_OCCUPIED,
    SECTION_80C_LIMIT,
    SECTION_80CCD1B_LIMIT,
    SECTION_80D_SELF_FAMILY_LIMIT,
    SECTION_80D_SELF_FAMILY_SENIOR_LIMIT,
    SECTION_80D_PARENTS_LIMIT,
    SECTION_80D_PARENTS_SENIOR_LIMIT,
    SECTION_80TTA_LIMIT,
    SECTION_80TTB_LIMIT,
    PRESUMPTIVE_44AD_DIGITAL,
    PRESUMPTIVE_44AD_CASH,
    PRESUMPTIVE_44ADA_RATE,
    SECTION_80CCH_LIMIT,
    SECTION_80DD_SEVERE_LIMIT,
    SECTION_80DDB_SENIOR_LIMIT,
    SECTION_80EE_LIMIT,
    SECTION_80EEA_LIMIT,
    SECTION_80EEB_LIMIT,
    SECTION_80U_SEVERE_LIMIT,
    SECTION_80GG_RENT_LIMIT,
    SECTION_80GG_GTI_PERCENT,
    SURCHARGE_SLABS,
    SURCHARGE_SLABS_NEW_REGIME,
)

def vba_round(val: Decimal) -> Decimal:
    """Round to nearest integer using ROUND_HALF_EVEN (banker's rounding).
    Matches ITD VBA engine rounding used in OpenTax."""
    return val.quantize(Decimal("1"), rounding=ROUND_HALF_EVEN)


def round_to_nearest_10(val: Decimal) -> Decimal:
    """Round a Decimal to the nearest 10 as per Section 288A/288B."""
    return (val / Decimal("10")).quantize(Decimal("1"), rounding=ROUND_HALF_UP) * Decimal("10")

def calculate_salary_income(salary_input: Any, regime: TaxRegime) -> Decimal:
    """
    Computes net salary income chargeable to tax under Section 15 & 16.

    Sec 17(1) Salary + Sec 17(2) Perquisites + Sec 17(3) Profits in lieu of salary
    = Gross Salary.

    Old Regime deductions u/s 16:
      - Sec 10 exemptions (HRA, LTA) subtracted from gross
      - Standard deduction u/s 16(ia): full ₹50,000 (not user-claimed amount)
      - Entertainment allowance u/s 16(ii): ₹5,000 cap, ONLY for Govt employees
      - Professional tax u/s 16(iii): actual paid, capped at ₹5,000
    New Regime:
      - Standard deduction u/s 16(ia): full ₹75,000 (Finance Act 2024)
      - No HRA/LTA exemptions, no professional tax deduction

    OpenTax ref: itr1_income_builder_service._build_deductions_us16()
    """
    if not salary_input:
        return Decimal("0")

    gross = salary_input.gross_salary + salary_input.perquisites_value + salary_input.profits_in_lieu_of_salary

    if regime == TaxRegime.OLD:
        hra = salary_input.hra_exempt_amount
        lta = salary_input.lta_exempt_amount
        # Professional tax capped at ₹5,000 u/s 16(iii)
        prof_tax = min(salary_input.professional_tax_paid, Decimal("5000"))
        # Entertainment allowance u/s 16(ii): ₹5,000, Govt employees only
        is_govt = getattr(salary_input, "is_government_employee", False)
        ent_allowance = min(salary_input.entertainment_allowance, Decimal("5000")) if is_govt else Decimal("0")

        net_before_std = max(Decimal("0"), gross - hra - lta)
        # Standard deduction = full limit (not user-claimed); OpenTax applies full 50K/75K
        std_ded = OLD_REGIME_STANDARD_DEDUCTION
        chargeable = net_before_std - std_ded - prof_tax - ent_allowance
    else:
        # New regime: full ₹75,000 standard deduction; no other Sec 16 deductions
        std_ded = NEW_REGIME_STANDARD_DEDUCTION
        chargeable = gross - std_ded

    return max(Decimal("0"), chargeable)

def calculate_house_property_income(hp_input: Any, regime: TaxRegime) -> tuple[Decimal, Decimal]:
    """
    Computes house property income under Sections 22, 23, and 24.
    
    Returns a tuple: (chargeable_hp_income, loss_to_carry_or_disallow).
    Under the Old regime, HP loss up to ₹2,00,000 can be set off against other heads.
    Under the New regime, HP loss cannot be set off against other heads (net chargeable is 0).
    """
    if not hp_input:
        return Decimal("0"), Decimal("0")
        
    if hp_input.property_type == PropertyType.SELF_OCCUPIED:
        interest = hp_input.home_loan_interest_paid
        if regime == TaxRegime.OLD:
            # Home loan interest capped at ₹2,00,000 u/s 24(b)
            allowed_interest = min(interest, HOUSE_PROPERTY_INTEREST_LIMIT_SELF_OCCUPIED)
            hp_income = -allowed_interest
        else:
            # New regime: Interest on self-occupied house property is disallowed
            hp_income = Decimal("0")
    else:
        # Let Out or Deemed Let Out
        nav = hp_input.annual_rent_received - hp_input.municipal_taxes_paid
        if nav < 0:
            nav = Decimal("0")

        # 30% standard deduction u/s 24(a) — only when NAV > 0
        std_ded = nav * HOUSE_PROPERTY_STANDARD_DEDUCTION if nav > 0 else Decimal("0")
        interest = hp_input.home_loan_interest_paid

        # Arrears u/s 25A: OpenTax ITR-1 builder returns 0 (not applicable for simple ITR-1)
        # hp_income = NAV − 30% std ded − interest
        hp_income = nav - std_ded - interest

    # Set off rules
    if hp_income < 0:
        if regime == TaxRegime.NEW:
            # New regime: no set off against other heads. Chargeable is 0, loss is disallowed/carried forward
            return Decimal("0"), hp_income
        else:
            # Old regime: set off up to ₹2,00,000
            allowed_loss = max(hp_income, Decimal("-200000"))
            carry_loss = hp_income - allowed_loss
            return allowed_loss, carry_loss
    else:
        return hp_income, Decimal("0")

def calculate_other_sources_income(os_input: Any, regime: TaxRegime) -> Decimal:
    """
    Computes other sources income u/s 56.

    Includes: savings bank interest, FD interest, family pension (gross),
    dividend income.

    Note: Family pension deduction u/s 57(iia) is NOT applied here.
    OpenTax ITR-1 income builder reports family pension at gross in
    OthSrcNatureDesc and does not deduct 1/3rd within income computation.
    OpenTax ref: itr1_income_builder_service._build_interest_income_details()
    """
    if not os_input:
        return Decimal("0")

    return (os_input.savings_bank_interest
            + os_input.fixed_deposit_interest
            + os_input.family_pension_received
            + os_input.dividend_income)

def calculate_chapter6a_deductions(
    ded_input: Any,
    gti: Decimal,
    age_bracket: AgeBracket,
    regime: TaxRegime,
    os_input: Any
) -> Decimal:
    """
    Computes Chapter VI-A deductions (excluding 80G/80GG — compute those via
    calculate_80g_deduction / calculate_80gg_deduction AFTER this call).

    Key rules (OpenTax aligned):
    - 80CCD(2) and 80CCH are allowed in BOTH old and new regimes.
    - 80C + 80CCC + 80CCD(1) share a combined ₹1,50,000 pool (Sec 80CCE).
    - 80TTA (non-senior) and 80TTB (senior) are mutually exclusive.
    - Total capped at GTI.

    OpenTax ref: TaxCalculationService.ded_80cce(), _apply_section_80ccd1b()
    """
    if not ded_input:
        return Decimal("0")

    # Always allowed (both regimes)
    ded_80ccd2 = ded_input.amount_80ccd2
    ded_80cch = min(ded_input.amount_80cch, SECTION_80CCH_LIMIT)

    if regime == TaxRegime.NEW:
        return min(ded_80ccd2 + ded_80cch, gti)

    # ── Sec 80CCE: combined ₹1,50,000 pool for 80C + 80CCC + 80CCD(1) ──
    # OpenTax ref: TaxCalculationService.ded_80cce()
    raw_80c   = ded_input.amount_80c
    raw_80ccc = getattr(ded_input, "amount_80ccc", Decimal("0"))
    raw_80ccd1 = getattr(ded_input, "amount_80ccd1", Decimal("0"))
    combined_80cce = min(raw_80c + raw_80ccc + raw_80ccd1, SECTION_80C_LIMIT)  # cap = 1.5L

    # 80CCD(1B) — extra NPS, outside 80CCE pool
    ded_80ccd1b = min(ded_input.amount_80ccd1b, SECTION_80CCD1B_LIMIT)

    # 80D self/family
    is_senior = age_bracket in (AgeBracket.SIXTY_TO_80, AgeBracket.ABOVE_80)
    cap_self = SECTION_80D_SELF_FAMILY_SENIOR_LIMIT if is_senior else SECTION_80D_SELF_FAMILY_LIMIT
    ded_80d_self = min(ded_input.amount_80d_self_family, cap_self)
    ded_80d_parents = min(ded_input.amount_80d_parents, SECTION_80D_PARENTS_SENIOR_LIMIT)

    # 80TTA / 80TTB — mutually exclusive by age
    ded_interest = Decimal("0")
    if os_input:
        if is_senior:
            total_interest = os_input.savings_bank_interest + os_input.fixed_deposit_interest
            ded_interest = min(ded_input.amount_80ttb, total_interest, SECTION_80TTB_LIMIT)
        else:
            ded_interest = min(ded_input.amount_80tta, os_input.savings_bank_interest, SECTION_80TTA_LIMIT)

    # Other deductions (no combined cap)
    ded_80e   = ded_input.amount_80e
    ded_80dd  = min(ded_input.amount_80dd,  SECTION_80DD_SEVERE_LIMIT)
    ded_80ddb = min(ded_input.amount_80ddb, SECTION_80DDB_SENIOR_LIMIT)
    ded_80u   = min(ded_input.amount_80u,   SECTION_80U_SEVERE_LIMIT)
    ded_80ee  = min(ded_input.amount_80ee,  SECTION_80EE_LIMIT)
    ded_80eea = min(ded_input.amount_80eea, SECTION_80EEA_LIMIT)
    ded_80eeb = min(ded_input.amount_80eeb, SECTION_80EEB_LIMIT)

    total = (combined_80cce + ded_80ccd1b + ded_80ccd2 + ded_80cch
             + ded_80d_self + ded_80d_parents
             + ded_interest + ded_80e
             + ded_80dd + ded_80ddb + ded_80u
             + ded_80ee + ded_80eea + ded_80eeb)
    return min(total, gti)


def calculate_80g_80gg_deductions(
    ded_input: Any,
    adjusted_gti: Decimal,
    regime: TaxRegime,
) -> Decimal:
    """
    Computes 80G and 80GG deductions AFTER all other deductions.

    80G rules (OpenTax ref: TaxCalculationService.ded_80g):
      - Cash donations capped at ₹2,000 per donation entry.
      - 100% donations: no qualifying limit (without limit).
      - 50% donations: capped at 10% of adjusted GTI.
      - adjusted_gti = GTI − all other Chapter VI-A deductions.

    80GG rules (OpenTax ref: TaxCalculationService.ded_80gg):
      - Min of: ₹60,000 | 25% of adjusted GTI | (rent − 10% of adjusted GTI).
    """
    if regime == TaxRegime.NEW or not ded_input:
        return Decimal("0")

    # ── 80G ──────────────────────────────────────────────────────────────────
    ded_80g = Decimal("0")
    for donation in getattr(ded_input, "donations_80g", []) or []:
        cash_amt     = min(getattr(donation, "cash_amount", Decimal("0")), Decimal("2000"))
        non_cash_amt = getattr(donation, "non_cash_amount", Decimal("0"))
        total_amt    = cash_amt + non_cash_amt
        if total_amt <= 0:
            continue
        pct    = getattr(donation, "qualifying_percentage", "100%")
        factor = Decimal("1") if pct == "100%" else Decimal("0.5")
        deductible = total_amt * factor
        qualifier  = (getattr(donation, "limit_on_deduction", "") or "").lower()
        if qualifier == "with limit":
            ded_80g += min(deductible, adjusted_gti * Decimal("0.10"))
        else:
            ded_80g += deductible  # without limit

    # Fallback: simple scalar field (when donations_80g list is not available)
    if not getattr(ded_input, "donations_80g", None):
        ded_80g = min(getattr(ded_input, "amount_80g", Decimal("0")), adjusted_gti)

    # ── 80GG ─────────────────────────────────────────────────────────────────
    rent_paid = getattr(ded_input, "amount_80gg", Decimal("0"))
    if rent_paid > 0:
        limit1 = SECTION_80GG_RENT_LIMIT
        limit2 = adjusted_gti * SECTION_80GG_GTI_PERCENT
        limit3 = max(Decimal("0"), rent_paid - adjusted_gti * Decimal("0.10"))
        ded_80gg = max(Decimal("0"), min(limit1, limit2, limit3))
    else:
        ded_80gg = Decimal("0")

    return ded_80g + ded_80gg


def calculate_surcharge(taxable_income: Decimal, tax_after_rebate: Decimal, regime: TaxRegime, age_bracket: AgeBracket) -> Decimal:
    """
    Computes surcharge with marginal relief.

    Old regime: 10%/15%/25%/37% depending on income bracket.
    New regime: capped at 25% (Finance Act 2023).
    Marginal relief: ensures (tax + surcharge) does not exceed
    (tax at lower bracket) + (excess income over threshold).

    OpenTax ref: TaxCalculationService._compute_surcharge_amount()
    XL: Sheet9.Surcharge_ii = J74
    """
    slabs = SURCHARGE_SLABS_NEW_REGIME if regime == TaxRegime.NEW else SURCHARGE_SLABS
    surcharge_rate = Decimal("0")
    base_income    = Decimal("0")

    for low, high, rate in slabs:
        if high is None:
            if taxable_income > low:
                surcharge_rate = rate
                base_income    = low
        elif low < taxable_income <= high:
            surcharge_rate = rate
            base_income    = low
            break

    if surcharge_rate == 0:
        return Decimal("0")

    surcharge_before_relief = tax_after_rebate * surcharge_rate

    # Base tax (tax at the lower bracket threshold)
    base_tax = calculate_slab_tax(base_income, age_bracket, regime)
    base_surcharge_rate = Decimal("0")
    for low, high, rate in slabs:
        if high is None:
            if base_income > low:
                base_surcharge_rate = rate
        elif low < base_income <= high:
            base_surcharge_rate = rate
            break
    base_tax_total = base_tax + base_tax * base_surcharge_rate

    excess_tax    = tax_after_rebate + surcharge_before_relief - base_tax_total
    excess_income = taxable_income - base_income
    relief        = max(Decimal("0"), excess_tax - excess_income)
    net_surcharge = vba_round(surcharge_before_relief - relief)
    return max(Decimal("0"), net_surcharge)

def calculate_slab_tax(taxable_income: Decimal, age_bracket: AgeBracket, regime: TaxRegime) -> Decimal:
    """
    Computes the tax payable under progressive slabs before rebate/cess.

    Per-slab tax is rounded using ROUND_HALF_EVEN (banker's rounding) to match
    the ITD VBA engine behaviour as implemented in OpenTax.
    OpenTax ref: TaxCalculationService._compute_slabs()
    """
    if taxable_income <= 0:
        return Decimal("0")

    if regime == TaxRegime.NEW:
        slabs = NEW_REGIME_SLABS_AY_2026_27
    else:
        if age_bracket == AgeBracket.ABOVE_80:
            slabs = OLD_REGIME_SLABS_ABOVE_80
        elif age_bracket == AgeBracket.SIXTY_TO_80:
            slabs = OLD_REGIME_SLABS_60_TO_80
        else:
            slabs = OLD_REGIME_SLABS_BELOW_60

    tax = Decimal("0")
    for lower, upper, rate in slabs:
        if taxable_income <= lower:
            break
        taxable = (
            min(taxable_income, upper) - lower
            if upper is not None
            else taxable_income - lower
        )
        if taxable <= 0:
            continue
        # ROUND_HALF_EVEN per slab — matches OpenTax VBA engine
        slab_tax = vba_round(taxable * rate / Decimal("100"))
        tax += slab_tax

    return tax

def calculate_87a_rebate(taxable_income: Decimal, tax_before_rebate: Decimal, regime: TaxRegime) -> Decimal:
    """
    Computes rebate under Section 87A.

    Old Regime (AY 2026-27):
      Full rebate (slab_tax) when slab_tax ≤ ₹12,500; else ₹0.
      This implicitly enforces the ₹5L income ceiling.
    New Regime (AY 2026-27, Finance Act 2025):
      Full rebate when slab_tax ≤ ₹60,000.
      Marginal relief: rebate = slab_tax − (income − ₹12,00,000).

    OpenTax ref: TaxCalculationService._compute_rebate_amount()
    XL: Part B-TI TTI sheet54 L65 (new) / P65 (old)
    """
    if tax_before_rebate <= 0:
        return Decimal("0")

    if regime == TaxRegime.OLD:
        # XL: P65 — MIN(tax, 12500) when slab_tax <= 12500; else 0
        if tax_before_rebate <= OLD_REBATE_TAX_LIMIT:
            return tax_before_rebate
        return Decimal("0")
    else:
        # New Regime — XL: O65 (Finance Act 2025, AY 2026-27)
        if tax_before_rebate <= NEW_REBATE_TAX_LIMIT:
            return tax_before_rebate
        # Marginal relief: rebate = max(0, slab_tax − (income − 12L))
        return max(Decimal("0"), tax_before_rebate - (taxable_income - NEW_REBATE_INCOME_LIMIT))

def calculate_presumptive_income(itr4_input: ITR4Input) -> Decimal:
    """
    Computes presumptive business/professional income under Sections 44AD, 44ADA, and 44AE.
    
    Validates eligibility limits and returns the net presumptive business income.
    """
    if itr4_input.presumptive_scheme == PresumptiveScheme.NONE:
        return Decimal("0")
        
    if itr4_input.presumptive_scheme == PresumptiveScheme.S44AD:
        ad = itr4_input.business_income_44ad
        if not ad:
            raise ValueError("business_income_44ad must be populated when scheme is 44AD")
            
        # Validate 44AD turnover limits
        if ad.total_turnover > Decimal("30000000"):
            raise ValueError("Turnover exceeds ₹3 crore limit u/s 44AD")
            
        # Check cash threshold for turnover > 2 Crore
        if ad.total_turnover > Decimal("20000000"):
            if ad.cash_turnover > ad.total_turnover * Decimal("0.05"):
                raise ValueError("Cash receipts exceed 5% limit for enhanced turnover of ₹3 crore u/s 44AD")
                
        # Validate turnover split consistency
        if ad.digital_turnover + ad.cash_turnover != ad.total_turnover:
            raise ValueError("digital_turnover + cash_turnover must equal total_turnover")
            
        statutory_profit = (ad.digital_turnover * PRESUMPTIVE_44AD_DIGITAL) + (ad.cash_turnover * PRESUMPTIVE_44AD_CASH)
        if ad.income_declared is not None:
            return max(statutory_profit, ad.income_declared)
        return statutory_profit
        
    elif itr4_input.presumptive_scheme == PresumptiveScheme.S44ADA:
        ada = itr4_input.professional_income_44ada
        if not ada:
            raise ValueError("professional_income_44ada must be populated when scheme is 44ADA")
            
        # Validate 44ADA gross receipts limits
        if ada.gross_receipts > Decimal("7500000"):
            raise ValueError("Gross receipts exceed ₹75 lakh limit u/s 44ADA")
            
        if ada.gross_receipts > Decimal("5000000"):
            if ada.cash_receipts > ada.gross_receipts * Decimal("0.05"):
                raise ValueError("Cash receipts exceed 5% limit for enhanced gross receipts of ₹75 lakh u/s 44ADA")
                
        if ada.digital_receipts + ada.cash_receipts != ada.gross_receipts:
            raise ValueError("digital_receipts + cash_receipts must equal gross_receipts")
            
        statutory_profit = ada.gross_receipts * PRESUMPTIVE_44ADA_RATE
        if ada.income_declared is not None:
            return max(statutory_profit, ada.income_declared)
        return statutory_profit
        
    elif itr4_input.presumptive_scheme == PresumptiveScheme.S44AE:
        ae = itr4_input.goods_carriage_44ae
        if not ae or not ae.vehicles:
            raise ValueError("goods_carriage_44ae and its vehicles must be populated when scheme is 44AE")
            
        if len(ae.vehicles) > 10:
            raise ValueError("Taxpayer cannot own more than 10 vehicles u/s 44AE")
            
        total_profit = Decimal("0")
        for vehicle in ae.vehicles:
            if vehicle.is_heavy_goods_vehicle:
                if vehicle.gross_vehicle_weight_tons is None:
                    raise ValueError("gross_vehicle_weight_tons must be specified for heavy goods vehicles")
                statutory_rate = Decimal("1000") * vehicle.gross_vehicle_weight_tons * Decimal(vehicle.months_owned)
            else:
                statutory_rate = Decimal("7500") * Decimal(vehicle.months_owned)
                
            if vehicle.income_declared is not None:
                total_profit += max(statutory_rate, vehicle.income_declared)
            else:
                total_profit += statutory_rate
                
        return total_profit
        
    return Decimal("0")

def compute_itr1(input_data: ITR1Input) -> Dict[str, Any]:
    """
    Computes an ITR-1 return from the input schema.

    Calculation order (matches OpenTax TaxCalculationService.calculate()):
    1. Income per head (Salary, HP, Other Sources)
    2. Gross Total Income (GTI)
    3. Chapter VI-A deductions (excl 80G/80GG)
    4. 80G/80GG on adjusted GTI
    5. Taxable Income
    6. Slab tax (ROUND_HALF_EVEN per slab)
    7. Rebate 87A (tax-gate method)
    8. Surcharge with marginal relief
    9. Cess = 4% of (tax_after_rebate + surcharge)
    """
    # 1. Eligibility: LTCG 112A
    if input_data.capital_gains and input_data.capital_gains.ltcg_112a > Decimal("125000"):
        raise ValueError("Ineligible for ITR-1: LTCG u/s 112A exceeds ₹1.25 Lakh")

    # 2. Heads of Income
    salary_income = calculate_salary_income(input_data.salary_income, input_data.tax_regime)
    hp_income, hp_loss_disallowed = calculate_house_property_income(input_data.house_property_income, input_data.tax_regime)
    other_income  = calculate_other_sources_income(input_data.other_sources_income, input_data.tax_regime)
    gti = salary_income + hp_income + other_income

    if gti > Decimal("5000000"):
        raise ValueError("Ineligible for ITR-1: Total income exceeds ₹50 Lakh")

    # 3. Chapter VI-A (all except 80G/80GG)
    deductions_base = calculate_chapter6a_deductions(
        input_data.deductions_chapter6a,
        gti,
        input_data.age_bracket,
        input_data.tax_regime,
        input_data.other_sources_income,
    )

    # 4. 80G/80GG on adjusted GTI (after all other deductions)
    adjusted_gti = max(Decimal("0"), gti - deductions_base)
    deductions_80g_80gg = calculate_80g_80gg_deductions(
        input_data.deductions_chapter6a,
        adjusted_gti,
        input_data.tax_regime,
    )
    deductions = min(deductions_base + deductions_80g_80gg, gti)

    # 5. Taxable Income u/s 288A
    taxable_income = round_to_nearest_10(max(Decimal("0"), gti - deductions))

    # 6. Slab Tax (ROUND_HALF_EVEN per slab — matches OpenTax VBA)
    slab_tax = calculate_slab_tax(taxable_income, input_data.age_bracket, input_data.tax_regime)

    # 7. Rebate 87A
    rebate = calculate_87a_rebate(taxable_income, slab_tax, input_data.tax_regime)
    tax_after_rebate = max(Decimal("0"), slab_tax - rebate)

    # 8. Surcharge (with marginal relief)
    surcharge = calculate_surcharge(taxable_income, tax_after_rebate, input_data.tax_regime, input_data.age_bracket)

    # 9. Cess = 4% of (tax_after_rebate + surcharge)  — XL: Sheet9.EducationCess
    cess = vba_round((tax_after_rebate + surcharge) * HEALTH_EDUCATION_CESS_RATE)

    # 10. Total tax payable u/s 288B
    total_tax_payable = round_to_nearest_10(tax_after_rebate + surcharge + cess)

    return {
        "salary_income":        salary_income,
        "house_property_income": hp_income,
        "other_sources_income": other_income,
        "gross_total_income":   gti,
        "deductions_chapter6a": deductions,
        "taxable_income":       taxable_income,
        "slab_tax":             slab_tax,
        "rebate_87a":           rebate,
        "tax_after_rebate":     tax_after_rebate,
        "surcharge":            surcharge,
        "health_education_cess": cess,
        "total_tax_payable":    total_tax_payable,
        "hp_loss_disallowed":   hp_loss_disallowed,
    }

def compute_itr4(input_data: ITR4Input) -> Dict[str, Any]:
    """
    Computes an ITR-4 (Sugam) return from the input schema.
    
    Returns a dictionary of all calculation steps.
    """
    # 1. Presumptive Income
    pgbp_income = calculate_presumptive_income(input_data)
    
    # 2. Heads of Income
    salary_income = calculate_salary_income(input_data.salary_income, input_data.tax_regime)
    hp_income, hp_loss_disallowed = calculate_house_property_income(input_data.house_property_income, input_data.tax_regime)
    other_income = calculate_other_sources_income(input_data.other_sources_income, input_data.tax_regime)
    
    # Gross Total Income (GTI)
    gti = salary_income + hp_income + other_income + pgbp_income

    # Eligibility check
    if gti > Decimal("5000000"):
        raise ValueError("Ineligible for ITR-4: Total income exceeds ₹50 Lakh")

    # 3. Chapter VI-A (all except 80G/80GG)
    deductions_base = calculate_chapter6a_deductions(
        input_data.deductions_chapter6a,
        gti,
        input_data.age_bracket,
        input_data.tax_regime,
        input_data.other_sources_income,
    )

    # 4. 80G/80GG on adjusted GTI (after all other deductions)
    adjusted_gti = max(Decimal("0"), gti - deductions_base)
    deductions_80g_80gg = calculate_80g_80gg_deductions(
        input_data.deductions_chapter6a,
        adjusted_gti,
        input_data.tax_regime,
    )
    deductions = min(deductions_base + deductions_80g_80gg, gti)

    # 5. Taxable Income u/s 288A
    taxable_income = round_to_nearest_10(max(Decimal("0"), gti - deductions))

    # 6. Slab Tax (ROUND_HALF_EVEN per slab — matches OpenTax VBA)
    slab_tax = calculate_slab_tax(taxable_income, input_data.age_bracket, input_data.tax_regime)

    # 7. Rebate 87A
    rebate = calculate_87a_rebate(taxable_income, slab_tax, input_data.tax_regime)
    tax_after_rebate = max(Decimal("0"), slab_tax - rebate)

    # 8. Surcharge (with marginal relief)
    surcharge = calculate_surcharge(taxable_income, tax_after_rebate, input_data.tax_regime, input_data.age_bracket)

    # 9. Cess = 4% of (tax_after_rebate + surcharge)  — XL: Sheet9.EducationCess
    cess = vba_round((tax_after_rebate + surcharge) * HEALTH_EDUCATION_CESS_RATE)

    # 10. Total tax payable u/s 288B
    total_tax_payable = round_to_nearest_10(tax_after_rebate + surcharge + cess)

    return {
        "pgbp_income":           pgbp_income,
        "salary_income":         salary_income,
        "house_property_income": hp_income,
        "other_sources_income":  other_income,
        "gross_total_income":    gti,
        "deductions_chapter6a":  deductions,
        "taxable_income":        taxable_income,
        "slab_tax":              slab_tax,
        "rebate_87a":            rebate,
        "tax_after_rebate":      tax_after_rebate,
        "surcharge":             surcharge,
        "health_education_cess": cess,
        "total_tax_payable":     total_tax_payable,
        "hp_loss_disallowed":    hp_loss_disallowed,
    }
