import datetime
from decimal import Decimal, InvalidOperation
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.db.database import get_db
from app.db.models import User
from app.schemas.itr1 import (
    ITR1Input, SalaryIncome, HousePropertyIncome, OtherSourcesIncome,
    Chapter6ADeductions, CapitalGainsIncome, Donation80G, Donation80GCategory,
    DonationAddress, TDS1Entry, TDS2Entry,
    TCSEntry, PropertyType, AgeBracket, TaxRegime,
)
from app.schemas.itr4 import (
    ITR4Input, PresumptiveScheme, PresumptiveBusinessIncome44AD,
    PresumptiveProfessionalIncome44ADA, PresumptiveGoodsCarriage44AE,
    GoodsCarriageVehicle,
)
from app.engine.calculators.itr1 import compute as compute_itr1
from app.engine.calculators.itr4 import compute as compute_itr4

router = APIRouter(tags=["tax"])


def _money(value: object) -> Decimal:
    """Convert an untrusted JSON monetary value to a non-negative Decimal."""
    if value is None or value == "":
        return Decimal("0")
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid monetary value: {value!r}",
        )
    if not amount.is_finite() or amount < 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Monetary values must be finite and non-negative: {value!r}",
        )
    return amount


def _records(payload: dict, key: str) -> list[dict]:
    """Return validated object records from a JSON array field."""
    value = payload.get(key)
    if value is None:
        return []
    if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"{key} must be an array of objects",
        )
    return value


def _date(value: object, field_name: str) -> Optional[datetime.date]:
    """Parse an optional ISO date or reject an invalid date value."""
    if value is None or value == "":
        return None
    try:
        return datetime.date.fromisoformat(str(value))
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"{field_name} must be an ISO date (YYYY-MM-DD)",
        )


@router.post("/tax-summary/compute")
@router.post("/api/tax/compute")
def compute_tax_summary(
    payload: dict,
    regime: str = "NEW",
    current_user: User = Depends(get_current_user),
):
    assessment_year = str(payload.get("assessmentYear") or "2026-27")
    if assessment_year != "2026-27":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Tax computation currently supports assessment year 2026-27 only.",
        )

    # Determine age
    age = int(payload.get("age", 30) or 30)
    if age >= 80:
        age_bracket = AgeBracket.ABOVE_80
    elif age >= 60:
        age_bracket = AgeBracket.SIXTY_TO_80
    else:
        age_bracket = AgeBracket.BELOW_60
        
    tax_regime = TaxRegime.OLD if regime.upper() == "OLD" else TaxRegime.NEW
    
    # 1. Map Salary. Canonical employer rows take precedence over legacy scalars.
    employers = _records(payload, "employerEntries")
    salary_rows = employers if employers else [payload]
    basic = sum((_money(row.get("basic")) for row in salary_rows), Decimal("0"))
    da = sum((_money(row.get("da")) for row in salary_rows), Decimal("0"))
    bonus = sum((_money(row.get("bonus")) for row in salary_rows), Decimal("0"))
    commission = sum((_money(row.get("commission")) for row in salary_rows), Decimal("0"))
    hra_received = sum(
        (_money(row.get("hra", row.get("hraReceived"))) for row in salary_rows),
        Decimal("0"),
    )
    perquisites = sum((_money(row.get("perquisites")) for row in salary_rows), Decimal("0"))
    profits_in_lieu = sum((_money(row.get("profitsInLieu")) for row in salary_rows), Decimal("0"))
    other_allowance = sum(
        (_money(row.get("otherAllowance", row.get("allowances"))) for row in salary_rows),
        Decimal("0"),
    )

    # gross_salary is section 17(1) salary only. Perquisites and profits in lieu
    # are separate sections and are added exactly once by the salary schedule.
    section_17_1_salary = basic + da + bonus + commission + hra_received + other_allowance
    gross_salary = section_17_1_salary + perquisites + profits_in_lieu
    hra_exempt = sum((_money(row.get("hraExempt")) for row in salary_rows), Decimal("0"))
    lta_exempt = sum((_money(row.get("ltaExempt")) for row in salary_rows), Decimal("0"))
    prof_tax = sum(
        (_money(row.get("professionalTax", row.get("profTax"))) for row in salary_rows),
        Decimal("0"),
    )
    ent_allowance = sum(
        (_money(row.get("entertainmentAllowance")) for row in salary_rows),
        Decimal("0"),
    )
    is_govt = any(bool(row.get("isGovernmentEmployee", False)) for row in salary_rows)

    salary_input = SalaryIncome(
        gross_salary=section_17_1_salary,
        perquisites_value=perquisites,
        profits_in_lieu_of_salary=profits_in_lieu,
        hra_exempt_amount=hra_exempt,
        lta_exempt_amount=lta_exempt,
        professional_tax_paid=prof_tax,
        entertainment_allowance=ent_allowance,
        is_government_employee=is_govt,
    )
    
    # 2. Map the first canonical property; ITR-1/4 computation schemas currently
    # represent one aggregate property schedule.
    properties = _records(payload, "housePropertyEntries")
    property_row = properties[0] if properties else payload
    raw_hp_type = str(property_row.get("propertyType", property_row.get("hpType", "self"))).upper()
    property_type = {
        "SELF": PropertyType.SELF_OCCUPIED,
        "SELF_OCCUPIED": PropertyType.SELF_OCCUPIED,
        "LET_OUT": PropertyType.LET_OUT,
        "DEEMED_LET_OUT": PropertyType.DEEMED_LET_OUT,
    }.get(raw_hp_type, PropertyType.LET_OUT)
    loan_interest = _money(property_row.get("interestOnLoan"))
    if loan_interest == 0:
        loan_interest = sum(
            (_money(loan.get("interestUs24B")) for loan in _records(property_row, "homeLoans")),
            Decimal("0"),
        )
    if loan_interest == 0:
        loan_interest = _money(property_row.get("homeLoanInt", property_row.get("sopLoanInt")))
    hp_input = HousePropertyIncome(
        property_type=property_type,
        annual_rent_received=_money(property_row.get("annualRent", property_row.get("grossRent"))),
        municipal_taxes_paid=_money(property_row.get("municipalTaxesPaid", property_row.get("munTax"))),
        home_loan_interest_paid=loan_interest,
        municipal_value=_money(property_row.get("municipalRateableValue")),
        fair_rent=_money(property_row.get("fairRentValue")),
        arrears_unrealised_rent_received=_money(property_row.get("arrearsOfRent")),
    )
    
    # 3. Map Other Sources. Canonical rows take precedence over scalar aliases.
    interest_rows = _records(payload, "interestEntries") or _records(payload, "bankInterestEntries")
    if interest_rows:
        savings_kinds = {"SAVINGS_BANK", "POST_OFFICE"}
        interest_sb = sum(
            (_money(row.get("grossAmount")) for row in interest_rows if str(row.get("kind", row.get("itdTag", ""))).upper() in savings_kinds),
            Decimal("0"),
        )
        interest_fd = sum(
            (_money(row.get("grossAmount")) for row in interest_rows if str(row.get("kind", row.get("itdTag", ""))).upper() not in savings_kinds),
            Decimal("0"),
        )
        interest_rd = nsc_interest = scss_interest = post_office_interest = other_interest = Decimal("0")
    else:
        interest_sb = _money(payload.get("interestSB"))
        interest_fd = _money(payload.get("interestFD"))
        interest_rd = _money(payload.get("interestRD"))
        nsc_interest = _money(payload.get("nscInterest"))
        scss_interest = _money(payload.get("scssInterest"))
        post_office_interest = _money(payload.get("postOfficeInterest"))
        other_interest = _money(payload.get("otherInterest"))
    total_interest = interest_sb + interest_fd + interest_rd + nsc_interest + scss_interest + post_office_interest + other_interest

    dividend_rows = _records(payload, "dividendEntries")
    if dividend_rows:
        total_dividend = sum((_money(row.get("grossAmount")) for row in dividend_rows), Decimal("0"))
    else:
        total_dividend = (
            _money(payload.get("dividendShares")) + _money(payload.get("dividendMF"))
            + _money(payload.get("dividendUnits")) + _money(payload.get("dividends"))
        )

    family_pension_row = payload.get("familyPensionEntry")
    family_pension = (
        _money(family_pension_row.get("grossAmount"))
        if isinstance(family_pension_row, dict)
        else _money(payload.get("familyPension"))
    )
    winnings_rows = _records(payload, "winningsEntries")
    lottery = _money(payload.get("lotteryIncome")) + sum(
        (_money(row.get("grossAmount")) for row in winnings_rows if str(row.get("type", "")).upper() != "HORSE_RACE"),
        Decimal("0"),
    )
    horse_race = _money(payload.get("horseRaceIncome")) + sum(
        (_money(row.get("grossAmount")) for row in winnings_rows if str(row.get("type", "")).upper() == "HORSE_RACE"),
        Decimal("0"),
    )
    vda_gains = _money(payload.get("vdaGains"))
    if lottery + horse_race + vda_gains > 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Lottery, gaming, horse-race, or VDA income is outside ITR-1/ITR-4; use the applicable ITR-2/ITR-3 computation.",
        )

    os_input = OtherSourcesIncome(
        savings_bank_interest=interest_sb + post_office_interest,
        fixed_deposit_interest=interest_fd + interest_rd + nsc_interest + scss_interest + other_interest,
        family_pension_received=family_pension,
        dividend_income=total_dividend,
    )
    
    # 4. Map deductions from canonical managers where available.
    investments_80c = payload.get("section80C")
    investment_rows = (
        investments_80c.get("investments", [])
        if isinstance(investments_80c, dict)
        else []
    )
    if investment_rows and all(isinstance(row, dict) for row in investment_rows):
        total_80c = sum((_money(row.get("amount")) for row in investment_rows), Decimal("0"))
    else:
        total_80c = sum(
            (_money(payload.get(key)) for key in ["s80C_epf", "s80C_ppf", "s80C_elss", "s80C_lic", "s80C_home"]),
            Decimal("0"),
        )

    section_80d = payload.get("section80D")

    def _category_80d(category: object) -> tuple[Decimal, Decimal]:
        if not isinstance(category, dict):
            return Decimal("0"), Decimal("0")
        policies = category.get("policies") or []
        if not isinstance(policies, list):
            raise HTTPException(status_code=422, detail="Section 80D policies must be an array.")
        premiums = sum(
            (_money(policy.get("premiumAmount")) for policy in policies if isinstance(policy, dict)),
            Decimal("0"),
        )
        eligible_amount = premiums + _money(category.get("medicalExpense"))
        preventive = _money(category.get("preventiveCheckup"))
        return eligible_amount, preventive

    if isinstance(section_80d, dict):
        self_is_senior = section_80d.get("selfSeniorCitizen") in {"Y", "S"}
        parents_are_senior = section_80d.get("parentsSeniorCitizen") in {"Y", "P"}
        self_key = "selfFamilySenior" if self_is_senior else "selfFamily"
        parents_key = "parentsSenior" if parents_are_senior else "parents"
        self_80d, preventive_self = _category_80d(section_80d.get(self_key))
        parents_80d, preventive_parents = _category_80d(section_80d.get(parents_key))
    else:
        parents_are_senior = False
        self_80d = _money(payload.get("s80D_self"))
        parents_80d = _money(payload.get("s80D_parent"))
        preventive_self = Decimal("0")
        preventive_parents = Decimal("0")

    donation_rows = _records(payload, "donationEntries")
    donations = []
    for row in donation_rows:
        category_value = str(row.get("category", "100_NO_APPROVAL"))
        try:
            category = Donation80GCategory(category_value)
        except ValueError:
            category = Donation80GCategory.HUNDRED_WITHOUT_LIMIT
        address = None
        if any(row.get(key) for key in ("addrDetail", "city", "stateCode", "pinCode")):
            address = DonationAddress(
                address_line=str(row.get("addrDetail", "")),
                city_or_district=str(row.get("city", "")),
                state_code=str(row.get("stateCode", "")),
                pin_code=int(row.get("pinCode", 0)),
            )
        donations.append(Donation80G(
            category=category,
            cash_amount=_money(row.get("donationAmtCash")),
            non_cash_amount=_money(row.get("donationAmtOtherMode")),
            donee_name=row.get("doneeName") or None,
            donee_pan=row.get("doneePAN") or None,
            approval_reference_number=row.get("arnNumber") or None,
            address=address,
            transaction_ref=row.get("transactionRefNum") or None,
            ifsc_code=row.get("ifscCode") or None,
        ))

    structured_80g_claim = sum(
        (donation.cash_amount + donation.non_cash_amount for donation in donations),
        Decimal("0"),
    )
    ded_input = Chapter6ADeductions(
        amount_80c=total_80c,
        amount_80ccd1b=_money(payload.get("s80CCD1B")),
        amount_80ccd2=_money(payload.get("s80CCD2")),
        amount_80d_self_family=self_80d,
        amount_80d_parents=parents_80d,
        amount_80d_preventive_self=preventive_self,
        amount_80d_preventive_parents=preventive_parents,
        has_parents_senior=parents_are_senior,
        amount_80e=_money(payload.get("s80E")),
        amount_80tta=_money(payload.get("s80TTA")),
        amount_80ttb=_money(payload.get("s80TTB")),
        amount_80g=(structured_80g_claim if donations else _money(payload.get("s80G"))),
        donations_80g=donations or None,
    )
    
    # 5. Map Capital Gains
    cg_input = CapitalGainsIncome(
        ltcg_112a=_money(payload.get("ltcg112APre")) + _money(payload.get("ltcg112APost"))
    )

    tds1_entries = []
    tds2_entries = []
    for row in _records(payload, "tdsEntries"):
        tan = str(row.get("deductorTAN") or "")
        section = str(row.get("section") or "")
        tax = _money(row.get("taxDeducted", row.get("tdsDeducted")))
        gross = _money(row.get("grossAmount", row.get("incomeAmount")))
        if section in {"192", "S192"}:
            tds1_entries.append(TDS1Entry(
                employer_tan=tan or None,
                employer_name=str(row.get("deductorName") or "") or None,
                income_chargeable=gross,
                tds_deducted=tax,
            ))
        elif tax > 0 or gross > 0:
            if not tan:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="A non-salary TDS claim requires deductor TAN.",
                )
            tds2_entries.append(TDS2Entry(
                deductor_tan=tan,
                deductor_name=str(row.get("deductorName") or "") or None,
                tds_section=section or "194A",
                gross_amount=gross,
                tds_deducted=tax,
            ))

    tcs_entries = []
    for row in _records(payload, "tcsEntries"):
        tan = str(row.get("collectorTAN") or "")
        collected = _money(row.get("taxCollected", row.get("tcsCollected")))
        gross = _money(row.get("grossAmount"))
        if collected > 0 or gross > 0:
            if not tan:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="A TCS claim requires collector TAN.",
                )
            tcs_entries.append(TCSEntry(
                collector_tan=tan,
                collector_name=str(row.get("collectorName") or "") or None,
                tcs_section=str(row.get("section") or "206C"),
                gross_amount=gross,
                tcs_collected=collected,
            ))

    advance_entries = _records(payload, "advanceTaxEntries")
    self_assessment_entries = _records(payload, "selfAssessmentTaxEntries")
    quarterly_advance = [Decimal("0"), Decimal("0"), Decimal("0"), Decimal("0")]
    if advance_entries:
        installment_deadlines = (
            datetime.date(2025, 6, 15), datetime.date(2025, 9, 15),
            datetime.date(2025, 12, 15), datetime.date(2026, 3, 15),
        )
        for row in advance_entries:
            amount = _money(row.get("amount"))
            deposit_date = _date(row.get("depositDate"), "advanceTaxEntries.depositDate")
            if deposit_date is None and amount > 0:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="An advance-tax challan with an amount requires depositDate.",
                )
            bucket = 3
            if deposit_date is not None:
                for index, deadline in enumerate(installment_deadlines):
                    if deposit_date <= deadline:
                        bucket = index
                        break
            quarterly_advance[bucket] += amount
        advance_tax_paid = sum(quarterly_advance, Decimal("0"))
    else:
        quarterly_advance = [
            _money(payload.get("adv15Jun")), _money(payload.get("adv15Sep")),
            _money(payload.get("adv15Dec")), _money(payload.get("adv15Mar")),
        ]
        advance_tax_paid = sum(quarterly_advance, Decimal("0"))
    self_assessment_paid = (
        sum((_money(row.get("amount")) for row in self_assessment_entries), Decimal("0"))
        if self_assessment_entries else _money(payload.get("selfTax"))
    )
    
    # Run calculation. Canonical business rows take precedence.
    business_rows = _records(payload, "businessEntries") or _records(payload, "businesses")
    if len(business_rows) > 1:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Multiple presumptive businesses are not yet supported by this calculation endpoint.",
        )
    business_row = business_rows[0] if business_rows else None
    biz_turnover = _money(payload.get("bizTurnover"))
    bp_profit = _money(payload.get("bizDeclared", payload.get("bpNetProfit")))
    presumptive_type = str(payload.get("bizPresumptive", "44AD"))
    if business_row:
        presumptive_type = str(business_row.get("scheme", presumptive_type))

    requested_form = str(payload.get("form", payload.get("itrForm", ""))).upper()
    is_itr4 = requested_form == "ITR-4" or bool(business_row) or biz_turnover > 0 or bp_profit > 0

    common_input = dict(
        age_bracket=age_bracket,
        tax_regime=tax_regime,
        salary_income=salary_input,
        house_property_income=hp_input,
        other_sources_income=os_input,
        deductions_chapter6a=ded_input,
        capital_gains=cg_input,
        tds1_entries=tds1_entries or None,
        tds2_entries=tds2_entries or None,
        tcs_entries=tcs_entries or None,
        advance_tax_paid=advance_tax_paid,
        self_assessment_tax_paid=self_assessment_paid,
        advance_tax_q1=quarterly_advance[0],
        advance_tax_q2=quarterly_advance[1],
        advance_tax_q3=quarterly_advance[2],
        advance_tax_q4=quarterly_advance[3],
        filing_date=_date(payload.get("filingDate"), "filingDate"),
        due_date=_date(payload.get("dueDate"), "dueDate"),
        house_property_count=max(1, len(properties)),
        relief_89=_money(payload.get("relief89", payload.get("relief_89"))),
    )

    if is_itr4:
        if presumptive_type == "44ADA":
            digital = _money(business_row.get("digitalReceipts")) if business_row else biz_turnover
            cash = _money(business_row.get("nonDigitalReceipts")) if business_row else Decimal("0")
            gross = _money(business_row.get("grossReceipts")) if business_row else biz_turnover
            if gross == 0:
                gross = digital + cash
            declared = _money(business_row.get("declaredIncome")) if business_row else bp_profit
            itr4_in = ITR4Input(
                **common_input,
                presumptive_scheme=PresumptiveScheme.S44ADA,
                professional_income_44ada=PresumptiveProfessionalIncome44ADA(
                    gross_receipts=gross,
                    digital_receipts=digital,
                    cash_receipts=cash,
                    income_declared=declared,
                ),
            )
        elif presumptive_type == "44AE":
            if not business_row:
                raise HTTPException(status_code=422, detail="44AE requires canonical vehicle entries.")
            vehicles = []
            for vehicle in _records(business_row, "vehicles"):
                vehicle_type = str(vehicle.get("vehicleType", "OTHER")).upper()
                vehicles.append(GoodsCarriageVehicle(
                    is_heavy_goods_vehicle=vehicle_type == "HEAVY",
                    gross_vehicle_weight_tons=(
                        _money(vehicle.get("tonnage")) if vehicle_type == "HEAVY" else None
                    ),
                    months_owned=int(vehicle.get("ownedMonths") or 0),
                    income_declared=_money(vehicle.get("presumptiveIncome")) or None,
                ))
            itr4_in = ITR4Input(
                **common_input,
                presumptive_scheme=PresumptiveScheme.S44AE,
                goods_carriage_44ae=PresumptiveGoodsCarriage44AE(vehicles=vehicles),
            )
        elif presumptive_type == "44AD":
            digital = _money(business_row.get("digitalReceipts")) if business_row else biz_turnover
            cash = _money(business_row.get("nonDigitalReceipts")) if business_row else Decimal("0")
            total = digital + cash if business_row else biz_turnover
            declared = _money(business_row.get("declaredIncome")) if business_row else bp_profit
            itr4_in = ITR4Input(
                **common_input,
                presumptive_scheme=PresumptiveScheme.S44AD,
                business_income_44ad=PresumptiveBusinessIncome44AD(
                    total_turnover=total,
                    digital_turnover=digital,
                    cash_turnover=cash,
                    income_declared=declared,
                ),
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Regular business income is outside ITR-4 presumptive computation.",
            )
        res = compute_itr4(itr4_in)
    else:
        res = compute_itr1(ITR1Input(**common_input))

    if res.errors:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"message": "Tax computation is not valid for the selected form.", "errors": res.errors},
        )
        
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
    
    # Use authoritative engine schedule and credit totals.
    std_ded = float(res.salary_deduction_us16ia)
    net_salary = float(res.salary_income)

    tds_salary = float(sum((entry.tds_deducted for entry in tds1_entries), Decimal("0")))
    tds_interest = float(sum((entry.tds_deducted for entry in tds2_entries if entry.tds_section in {"194A", "S194A"}), Decimal("0")))
    tds_other = float(sum((entry.tds_deducted for entry in tds2_entries), Decimal("0"))) - tds_interest
    adv_tax = float(advance_tax_paid)
    self_tax = float(self_assessment_paid)
    total_tax_paid = float(res.total_taxes_paid)
    tax_payable = float(res.balance_payable)
    refund = float(res.refund_due)
    
    return {
        "grossSalary": float(gross_salary),
        "hraExempt": float(hra_exempt),
        "netSalary": net_salary,
        "hpIncome": float(res.house_property_income),
        "cgTax": float(res.special_rate_tax),
        "bizIncome": float(getattr(res, 'presumptive_income', 0) or getattr(res, 'business_income', 0)),
        "otherIncome": float(res.other_sources_income),
        "vdaTax": 0.0,
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
        "vdaGains": 0.0,
        "totalInterest": float(total_interest),
        "interestDeduction80TTA": float(payload.get("s80TTA", 0) or 0),
        "interestDeduction80TTB": float(payload.get("s80TTB", 0) or 0),
        "totalDividend": float(total_dividend),
        "dividendTaxableAtSpecialRate": 0.0,
        "dividendTaxableAtNormalRate": total_dividend,
        "totalWinnings": 0.0,
        "winningsTax": 0.0,
        "taxableGifts": 0.0,
        "familyPensionDed": float(res.schedules["os"].deduction_57iia),
        "specialRateIncome": 0.0,
        "familyPensionIncome": float(family_pension),
        "tdsS192": tds_salary,
        "tds194A": tds_interest,
        "tdsOther": tds_other,
        "adv15Jun": float(quarterly_advance[0]),
        "adv15Sep": float(quarterly_advance[1]),
        "adv15Dec": float(quarterly_advance[2]),
        "adv15Mar": float(quarterly_advance[3]),
        "selfTax": self_tax,
        "tdsEntries": payload.get("tdsEntries", []),
        "selfAssessmentTaxEntries": payload.get("selfAssessmentTaxEntries", []),
        "salaryIncome": float(gross_salary),
        "salary171": float(section_17_1_salary),
        "salary172": float(perquisites),
        "salary173": float(profits_in_lieu),
        "ltaExempt": float(lta_exempt),
        "gratuityExempt": float(payload.get("gratuityReceived", 0) or 0), # Simplification
        "leaveEncashmentExempt": float(payload.get("leaveEncashmentReceived", 0) or 0),
        "pensionCommutationExempt": float(payload.get("commutationOfPensionReceived", 0) or 0),
        "transportExempt": 0.0,
        "childrenEducationExempt": 0.0,
        "hostelExempt": 0.0,
        "uniformExempt": 0.0,
        "totalSection10Exempt": float(hra_exempt + lta_exempt),
        "standardDeduction": std_ded,
        "entertainmentAllowanceDed": float(res.salary_entertainment_allowance),
        "professionalTaxDed": float(res.salary_professional_tax),
        "totalSection16Deductions": float(res.salary_deduction_us16),
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
def calculate_business_income(request: dict, assessmentYear: str = "2025-26"):
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
        "assessmentYear": "2025-26"
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
        "assessmentYear": request.get("assessmentYear", "2025-26"),
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
