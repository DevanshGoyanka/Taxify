import datetime
from decimal import Decimal
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.db.database import get_db
from app.db.models import User
from app.schemas.itr1 import ITR1Input, SalaryIncome, HousePropertyIncome, OtherSourcesIncome, Chapter6ADeductions, CapitalGainsIncome, PropertyType, AgeBracket, TaxRegime
from app.schemas.itr4 import ITR4Input, PresumptiveScheme, PresumptiveBusinessIncome44AD, PresumptiveProfessionalIncome44ADA
from app.engine.calculators.itr1 import compute as compute_itr1
from app.engine.calculators.itr4 import compute as compute_itr4

router = APIRouter(tags=["tax"])

@router.post("/tax-summary/compute")
@router.post("/api/tax/compute")
def compute_tax_summary(
    payload: dict,
    regime: str = "NEW",
    current_user: User = Depends(get_current_user),
):
    # Determine age
    age = int(payload.get("age", 30) or 30)
    if age >= 80:
        age_bracket = AgeBracket.ABOVE_80
    elif age >= 60:
        age_bracket = AgeBracket.SIXTY_TO_80
    else:
        age_bracket = AgeBracket.BELOW_60
        
    tax_regime = TaxRegime.OLD if regime.upper() == "OLD" else TaxRegime.NEW
    
    # 1. Map Salary
    basic = float(payload.get("basic", 0) or 0)
    da = float(payload.get("da", 0) or 0)
    bonus = float(payload.get("bonus", 0) or 0)
    commission = float(payload.get("commission", 0) or 0)
    hra_received = float(payload.get("hraReceived", 0) or 0)
    perquisites = float(payload.get("perquisites", 0) or 0)
    profits_in_lieu = float(payload.get("profitsInLieu", 0) or 0)
    other_allowance = float(payload.get("otherAllowance", 0) or 0)
    
    gross_salary = basic + da + bonus + commission + hra_received + perquisites + profits_in_lieu + other_allowance
    hra_exempt = float(payload.get("hraExempt", 0) or 0)
    lta_exempt = float(payload.get("ltaExempt", 0) or 0)
    prof_tax = float(payload.get("profTax", 0) or 0)
    ent_allowance = float(payload.get("entertainmentAllowance", 0) or 0)
    is_govt = bool(payload.get("isGovernmentEmployee", False))
    
    salary_input = SalaryIncome(
        gross_salary=Decimal(str(gross_salary)),
        perquisites_value=Decimal(str(perquisites)),
        profits_in_lieu_of_salary=Decimal(str(profits_in_lieu)),
        hra_exempt_amount=Decimal(str(hra_exempt)),
        lta_exempt_amount=Decimal(str(lta_exempt)),
        professional_tax_paid=Decimal(str(prof_tax)),
        entertainment_allowance=Decimal(str(ent_allowance)),
        is_government_employee=is_govt
    )
    
    # 2. Map HP
    hp_type = payload.get("hpType", "self")
    hp_input = HousePropertyIncome(
        property_type=PropertyType.SELF_OCCUPIED if hp_type == "self" else PropertyType.LET_OUT,
        annual_rent_received=Decimal(str(payload.get("grossRent", 0) or 0)),
        municipal_taxes_paid=Decimal(str(payload.get("munTax", 0) or 0)),
        home_loan_interest_paid=Decimal(str(payload.get("homeLoanInt", 0) or payload.get("sopLoanInt", 0) or 0))
    )
    
    # 3. Map Other Sources
    interest_sb = float(payload.get("interestSB", 0) or 0)
    interest_fd = float(payload.get("interestFD", 0) or 0)
    interest_rd = float(payload.get("interestRD", 0) or 0)
    nsc_interest = float(payload.get("nscInterest", 0) or 0)
    scss_interest = float(payload.get("scssInterest", 0) or 0)
    post_office_interest = float(payload.get("postOfficeInterest", 0) or 0)
    other_interest = float(payload.get("otherInterest", 0) or 0)
    
    total_interest = interest_sb + interest_fd + interest_rd + nsc_interest + scss_interest + post_office_interest + other_interest
    
    dividend_shares = float(payload.get("dividendShares", 0) or 0)
    dividend_mf = float(payload.get("dividendMF", 0) or 0)
    dividend_units = float(payload.get("dividendUnits", 0) or 0)
    dividends_legacy = float(payload.get("dividends", 0) or 0)
    total_dividend = dividend_shares + dividend_mf + dividend_units + dividends_legacy
    
    family_pension = float(payload.get("familyPension", 0) or 0)
    lottery = float(payload.get("lotteryIncome", 0) or 0)
    horse_race = float(payload.get("horseRaceIncome", 0) or 0)
    vda_gains = float(payload.get("vdaGains", 0) or 0)
    
    os_input = OtherSourcesIncome(
        savings_bank_interest=Decimal(str(interest_sb + post_office_interest)),
        fixed_deposit_interest=Decimal(str(interest_fd + interest_rd + nsc_interest + scss_interest + other_interest)),
        family_pension_received=Decimal(str(family_pension)),
        dividend_income=Decimal(str(total_dividend))
    )
    
    # 4. Map Deductions
    epf = float(payload.get("s80C_epf", 0) or 0)
    ppf = float(payload.get("s80C_ppf", 0) or 0)
    elss = float(payload.get("s80C_elss", 0) or 0)
    lic = float(payload.get("s80C_lic", 0) or 0)
    home_principal = float(payload.get("s80C_home", 0) or 0)
    total_80c = epf + ppf + elss + lic + home_principal
    
    ded_input = Chapter6ADeductions(
        amount_80c=Decimal(str(total_80c)),
        amount_80ccd1b=Decimal(str(payload.get("s80CCD1B", 0) or 0)),
        amount_80ccd2=Decimal(str(payload.get("s80CCD2", 0) or 0)),
        amount_80d_self_family=Decimal(str(payload.get("s80D_self", 0) or 0)),
        amount_80d_parents=Decimal(str(payload.get("s80D_parent", 0) or 0)),
        amount_80e=Decimal(str(payload.get("s80E", 0) or 0)),
        amount_80tta=Decimal(str(payload.get("s80TTA", 0) or 0)),
        amount_80ttb=Decimal(str(payload.get("s80TTB", 0) or 0)),
        amount_80g=Decimal(str(payload.get("s80G", 0) or 0))
    )
    
    # 5. Map Capital Gains
    cg_input = CapitalGainsIncome(
        ltcg_112a=Decimal(str(payload.get("ltcg112APre", 0) or payload.get("ltcg112APost", 0) or 0))
    )
    
    # Run calculation
    # Check if this is ITR-4 (by checking presumptive turnover/income)
    biz_turnover = float(payload.get("bizTurnover", 0) or 0)
    bp_profit = float(payload.get("bpNetProfit", 0) or 0)
    biz_declared = float(payload.get("bizDeclared", 0) or 0)
    presumptive_type = payload.get("bizPresumptive", "44AD")
    
    is_itr4 = biz_turnover > 0 or bp_profit > 0
    
    if is_itr4:
        # For presumptive schemes use bizDeclared; for Regular use bpNetProfit
        declared_income = biz_declared if presumptive_type in ("44AD", "44ADA") else bp_profit
        
        scheme_enum = PresumptiveScheme.S44AD
        if presumptive_type == "44ADA":
            scheme_enum = PresumptiveScheme.S44ADA
            prof_income = PresumptiveProfessionalIncome44ADA(
                gross_receipts=Decimal(str(biz_turnover)),
                digital_receipts=Decimal(str(biz_turnover)),
                cash_receipts=Decimal("0"),
                income_declared=Decimal(str(declared_income))
            )
            biz_income = None
        else:
            biz_income = PresumptiveBusinessIncome44AD(
                total_turnover=Decimal(str(biz_turnover)),
                digital_turnover=Decimal(str(biz_turnover)),
                cash_turnover=Decimal("0"),
                income_declared=Decimal(str(declared_income))
            )
            prof_income = None
            
        itr4_in = ITR4Input(
            age_bracket=age_bracket,
            tax_regime=tax_regime,
            presumptive_scheme=scheme_enum,
            business_income_44ad=biz_income,
            professional_income_44ada=prof_income,
            salary_income=salary_input,
            house_property_income=hp_input,
            other_sources_income=os_input,
            deductions_chapter6a=ded_input
        )
        res = compute_itr4(itr4_in)
    else:
        # Run ITR-1
        itr1_in = ITR1Input(
            age_bracket=age_bracket,
            tax_regime=tax_regime,
            salary_income=salary_input,
            house_property_income=hp_input,
            other_sources_income=os_input,
            deductions_chapter6a=ded_input,
            capital_gains=cg_input
        )
        res = compute_itr1(itr1_in)
        
    # Build frontend response structure
    gti = float(res.gross_total_income)
    total_deductions = float(res.deductions_total)
    taxable_income = float(res.taxable_income)
    slab_tax = float(res.slab_tax)
    rebate = float(res.rebate_87a)
    tax_after_rebate = float(res.tax_after_rebate)
    surcharge = float(res.surcharge)
    cess = float(res.health_education_cess)
    total_tax_payable = float(res.net_tax_liability)
    
    # Standard deduction
    std_ded = 75000.0 if tax_regime == TaxRegime.NEW else 50000.0
    net_salary = max(0.0, gross_salary - std_ded)
    
    # Tax credits/paid
    tds_salary = float(payload.get("tdsS192", 0) or 0)
    tds_interest = float(payload.get("tds194A", 0) or 0)
    tds_other = float(payload.get("tdsOther", 0) or 0)
    adv_tax = sum(float(payload.get(k, 0) or 0) for k in ["adv15Jun", "adv15Sep", "adv15Dec", "adv15Mar"])
    self_tax = float(payload.get("selfTax", 0) or 0)
    total_tax_paid = tds_salary + tds_interest + tds_other + adv_tax + self_tax
    
    tax_payable = max(0.0, total_tax_payable - total_tax_paid)
    refund = max(0.0, total_tax_paid - total_tax_payable)
    
    return {
        "grossSalary": gross_salary,
        "hraExempt": hra_exempt,
        "netSalary": net_salary,
        "hpIncome": float(res.house_property_income),
        "cgTax": 0.0, # Simple ITR1/4 default
        "bizIncome": float(getattr(res, 'presumptive_income', 0) or getattr(res, 'business_income', 0)),
        "otherIncome": float(res.other_sources_income),
        "vdaTax": vda_gains * 0.3,
        "gti": gti,
        "gtiAfterSetOff": gti,
        "totalDeductions": total_deductions,
        "totalIncome": taxable_income,
        "normalTax": slab_tax,
        "rebate87A": rebate,
        "surcharge": surcharge,
        "cess": cess,
        "totalTaxLiability": total_tax_payable,
        "totalTaxPaid": total_tax_paid,
        "taxPayable": tax_payable,
        "refund": refund,
        "vdaGains": vda_gains,
        "totalInterest": total_interest,
        "interestDeduction80TTA": float(payload.get("s80TTA", 0) or 0),
        "interestDeduction80TTB": float(payload.get("s80TTB", 0) or 0),
        "totalDividend": total_dividend,
        "dividendTaxableAtSpecialRate": 0.0,
        "dividendTaxableAtNormalRate": total_dividend,
        "totalWinnings": lottery + horse_race,
        "winningsTax": (lottery + horse_race) * 0.3,
        "taxableGifts": float(payload.get("giftsFromNonRelatives", 0) or 0),
        "familyPensionDed": min(15000.0, family_pension / 3.0),
        "specialRateIncome": lottery + horse_race + vda_gains,
        "familyPensionIncome": family_pension,
        "tdsS192": tds_salary,
        "tds194A": tds_interest,
        "tdsOther": tds_other,
        "adv15Jun": float(payload.get("adv15Jun", 0) or 0),
        "adv15Sep": float(payload.get("adv15Sep", 0) or 0),
        "adv15Dec": float(payload.get("adv15Dec", 0) or 0),
        "adv15Mar": float(payload.get("adv15Mar", 0) or 0),
        "selfTax": self_tax,
        "tdsEntries": payload.get("tdsEntries", []),
        "selfAssessmentTaxEntries": payload.get("selfAssessmentTaxEntries", []),
        "salaryIncome": gross_salary,
        "salary171": basic + da + bonus + commission + hra_received + other_allowance,
        "salary172": perquisites,
        "salary173": profits_in_lieu,
        "ltaExempt": lta_exempt,
        "gratuityExempt": float(payload.get("gratuityReceived", 0) or 0), # Simplification
        "leaveEncashmentExempt": float(payload.get("leaveEncashmentReceived", 0) or 0),
        "pensionCommutationExempt": float(payload.get("commutationOfPensionReceived", 0) or 0),
        "transportExempt": 0.0,
        "childrenEducationExempt": 0.0,
        "hostelExempt": 0.0,
        "uniformExempt": 0.0,
        "totalSection10Exempt": hra_exempt + lta_exempt,
        "standardDeduction": std_ded,
        "entertainmentAllowanceDed": ent_allowance,
        "professionalTaxDed": prof_tax,
        "totalSection16Deductions": std_ded + prof_tax + ent_allowance,
        "salaryTDS": tds_salary,
        "salaryEmployerCount": len(payload.get("employerEntries", [])),
        "hraCondition1": 0.0,
        "hraCondition2": 0.0,
        "hraCondition3": 0.0,
        "hraIsMetro": bool(payload.get("hraMetro", False)),
        "hraCityClassified": "Metro" if bool(payload.get("hraMetro", False)) else "Non-Metro",
        "taxRegime": regime
    }

@router.post("/business-income/calculate")
def calculate_business_income(request: dict, assessmentYear: str = "2026-27"):
    scheme = request.get("scheme", "Regular")
    gross_turnover = float(request.get("grossTurnover", 0) or 0)
    declared_income = float(request.get("declaredIncome", 0) or 0)
    net_profit = float(request.get("netProfitPL", 0) or 0)
    
    compliance_notes = []
    
    if scheme == "44AD":
        rate = 0.06
        statutory = gross_turnover * rate
        taxable = max(statutory, declared_income)
        compliance_notes.append("Presumptive rate of 6% applied for digital transactions. If you have cash transactions, 8% applies.")
    elif scheme == "44ADA":
        rate = 0.50
        statutory = gross_turnover * rate
        taxable = max(statutory, declared_income)
        compliance_notes.append("Presumptive rate of 50% applied for professional receipts.")
    else:
        rate = 0.0
        taxable = net_profit
        compliance_notes.append("Regular scheme applied based on Profit & Loss statement.")
        
    return {
        "scheme": scheme,
        "assessmentYear": assessmentYear,
        "grossTurnover": gross_turnover,
        "declaredIncome": declared_income,
        "netProfitPL": net_profit,
        "taxableIncome": taxable,
        "adjustedTaxableIncome": taxable,
        "presumptiveRate": rate,
        "incomeType": "Business" if scheme != "44ADA" else "Professional",
        "isLoss": taxable < 0,
        "businessLoss": abs(taxable) if taxable < 0 else 0,
        "complianceNotes": compliance_notes,
        "timestamp": "2026-07-17T19:20:00Z"
    }

@router.post("/business-income/validate")
def validate_business_input(request: dict):
    scheme = request.get("scheme", "Regular")
    gross_turnover = float(request.get("grossTurnover", 0) or 0)
    errors = []
    warnings = []
    
    if scheme == "44AD" and gross_turnover > 30000000:
        errors.append("Gross turnover exceeds the Section 44AD presumptive limit of ₹3 crore.")
    elif scheme == "44ADA" and gross_turnover > 7500000:
        errors.append("Gross receipts exceed the Section 44ADA presumptive limit of ₹75 lakh.")
        
    return {
        "isValid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "assessmentYear": "2026-27"
    }

@router.post("/capital-gains/calculate")
def calculate_capital_gains(request: dict):
    asset_type = request.get("assetType", "EQUITY")
    purchase_cost = float(request.get("purchaseCost", 0) or 0)
    sale_cost = float(request.get("saleCost", 0) or 0)
    transfer_expenses = float(request.get("transferExpenses", 0) or 0)
    
    p_date_str = request.get("purchaseDate")
    s_date_str = request.get("saleDate")
    months = 24
    if p_date_str and s_date_str:
        try:
            p_date = datetime.datetime.strptime(p_date_str, "%Y-%m-%d")
            s_date = datetime.datetime.strptime(s_date_str, "%Y-%m-%d")
            months = (s_date.year - p_date.year) * 12 + (s_date.month - p_date.month)
        except Exception:
            pass
            
    threshold = 12 if "EQUITY" in asset_type.upper() or "MUTUAL" in asset_type.upper() else 24
    is_ltcg = months >= threshold
    
    gain = sale_cost - purchase_cost - transfer_expenses
    taxable_gain = max(0.0, gain)
    
    if is_ltcg:
        tax_rate = 0.125
        tax_payable = taxable_gain * tax_rate
        gain_type = "LTCG"
        sec_ref = "112A" if "EQUITY" in asset_type.upper() else "112"
    else:
        tax_rate = 0.15 if "EQUITY" in asset_type.upper() else 0.30
        tax_payable = taxable_gain * tax_rate
        gain_type = "STCG"
        sec_ref = "111A" if "EQUITY" in asset_type.upper() else "Slab"
        
    return {
        "gainType": gain_type,
        "longTerm": is_ltcg,
        "holdingPeriodMonths": months,
        "purchaseCost": purchase_cost,
        "saleCost": sale_cost,
        "costOfAcquisition": purchase_cost,
        "indexedCost": purchase_cost,
        "gain": gain,
        "taxableGain": taxable_gain,
        "taxRate": tax_rate,
        "taxPayable": tax_payable,
        "assessmentYear": request.get("assessmentYear", "2026-27"),
        "scheduleCGReference": "Schedule CG",
        "sectionReference": sec_ref,
        "complianceNotes": ["Holding period computed: {} months.".format(months)]
    }

@router.post("/capital-gains/calculate-batch")
def calculate_capital_gains_batch(request: dict):
    txs = request.get("transactions", [])
    results = []
    
    stcg_111a = 0.0
    ltcg_112a = 0.0
    stcg_other = 0.0
    ltcg_112 = 0.0
    total_tax = 0.0
    
    for tx in txs:
        calc = calculate_capital_gains(tx)
        results.append(calc)
        
        gain = calc["taxableGain"]
        tax = calc["taxPayable"]
        is_ltcg = calc["longTerm"]
        sec = calc["sectionReference"]
        
        if is_ltcg:
            if sec == "112A":
                ltcg_112a += gain
            else:
                ltcg_112 += gain
        else:
            if sec == "111A":
                stcg_111a += gain
            else:
                stcg_other += gain
        total_tax += tax
        
    total_gains = stcg_111a + ltcg_112a + stcg_other + ltcg_112
    
    return {
        "transactions": results,
        "summary": {
            "stcg111A": stcg_111a,
            "ltcg112A": ltcg_112a,
            "stcgOther": stcg_other,
            "ltcg112": ltcg_112,
            "totalCapitalGains": total_gains,
            "totalTax": total_tax,
            "lossSetOff": 0.0,
            "netCapitalGains": total_gains,
            "remainingLoss": 0.0
        }
    }
